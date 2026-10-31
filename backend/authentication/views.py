import logging
import os
import io
import uuid
import base64
import boto3
import re
from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from .models import User
from .serializers import (
    UserSerializer,
    GoogleAuthSerializer,
    SignupSerializer,
    LoginSerializer,
)

logger = logging.getLogger("amour.auth")

def _verify_google_token(token_str: str):
    request = google_requests.Request()
    for client_id in settings.GOOGLE_CLIENT_IDS:
        try:
            payload = google_id_token.verify_oauth2_token(token_str, request, client_id)
            return payload
        except Exception:
            continue
    try:
        return google_id_token.verify_oauth2_token(token_str, request)
    except Exception as e:
        logger.warning(f"Google ID token verification failed: {e}")
        return None

class GoogleAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        id_token_str = serializer.validated_data.get("id_token")
        profile_data = serializer.validated_data.get("profile")

        email = None
        google_sub = ""
        name = ""
        given_name = ""
        family_name = ""
        picture = ""

        if id_token_str:
            verified_payload = _verify_google_token(id_token_str)
            if verified_payload:
                email = verified_payload.get("email")
                google_sub = verified_payload.get("sub", "")
                name = verified_payload.get("name", "")
                given_name = verified_payload.get("given_name", "")
                family_name = verified_payload.get("family_name", "")
                picture = verified_payload.get("picture", "")

        # Fallback to direct client profile payload if in dev
        if not email and profile_data:
            email = profile_data.get("email")
            google_sub = profile_data.get("id", "")
            name = profile_data.get("name", "")
            given_name = profile_data.get("given_name", "")
            family_name = profile_data.get("family_name", "")
            picture = profile_data.get("picture", "")

        if not email:
            return Response(
                {"error": "Invalid Google token or credentials."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Upsert user in PostgreSQL
        user = User.objects.filter(email=email).first()
        if not user:
            # Use google_sub or generate id
            user_id = str(google_sub) if google_sub else str(User.objects.count() + 1)
            # The user id is their namespace
            namespace = user_id
            user = User.objects.create_user(
                email=email,
                id=user_id,
                namespace=namespace,
                name=name,
                given_name=given_name,
                family_name=family_name,
                picture=picture,
                auth_provider="google",
                google_sub=google_sub,
                verified_email=True,
            )
            logger.info(f"Created new Google user: {email} with namespace: {user.namespace}")
        else:
            # Update latest profile details if not customized
            if name and not user.name:
                user.name = name
            if picture and (not user.picture or "googleusercontent" in user.picture):
                user.picture = picture
            if google_sub:
                user.google_sub = google_sub
            user.verified_email = True
            # Ensure namespace is set to user id
            if not user.namespace:
                user.namespace = user.id
            user.save()

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )

class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        name = serializer.validated_data["name"]

        if User.objects.filter(email=email).exists():
            return Response(
                {"error": "An account with this email already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        import uuid
        user_id = str(uuid.uuid4())
        # User id is their namespace
        namespace = user_id

        user = User.objects.create_user(
            email=email,
            password=password,
            id=user_id,
            namespace=namespace,
            name=name,
            auth_provider="local",
            verified_email=False,
        )

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        user = User.objects.filter(email=email).first()
        if not user or not user.check_password(password):
            return Response(
                {"error": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

class UserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        users = User.objects.all().order_by("-created_at")
        return Response(
            {
                "total": users.count(),
                "users": UserSerializer(users, many=True).data,
            }
        )


class ProfileView(APIView):
    """
    Retrieve or update user profile (username, name, picture).
    Ensures username is unique across all users and formatted properly.
    Links changes to user in PostgreSQL and syncs persona handles/avatars.
    """
    permission_classes = [AllowAny]

    def _get_user(self, request):
        if request.user and request.user.is_authenticated:
            return request.user
        user_id = request.query_params.get("user_id") or request.data.get("user_id")
        if user_id:
            return User.objects.filter(id=user_id).first()
        return None

    def get(self, request):
        user = self._get_user(request)
        if not user:
            return Response({"error": "User not found or unauthenticated"}, status=status.HTTP_404_NOT_FOUND)
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)

    def patch(self, request):
        user = self._get_user(request)
        if not user:
            return Response({"error": "User not found or unauthenticated"}, status=status.HTTP_404_NOT_FOUND)

        new_username = request.data.get("username")
        new_name = request.data.get("name")
        new_picture = request.data.get("picture")

        if new_username is not None:
            clean_username = re.sub(r"[^a-zA-Z0-9_]", "", new_username.strip().lower())
            if len(clean_username) < 3 or len(clean_username) > 30:
                return Response(
                    {"error": "Username must be between 3 and 30 characters (letters, numbers, underscores)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if User.objects.filter(username__iexact=clean_username).exclude(id=user.id).exists():
                return Response(
                    {"error": f"Username '@{clean_username}' is already taken. Please choose another."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.username = clean_username

        if new_name is not None and new_name.strip():
            user.name = new_name.strip()

        if new_picture is not None:
            user.picture = new_picture.strip()

        user.save()

        # Sync updated profile handle & avatar across user's personas
        try:
            from memory.models import Persona
            update_fields = {}
            if user.username:
                update_fields["publisher_handle"] = f"@{user.username}"
            if user.name:
                update_fields["publisher_name"] = user.name
            if user.picture:
                update_fields["publisher_avatar"] = user.picture
            if update_fields:
                Persona.objects.filter(creator=user).update(**update_fields)
        except Exception as exc:
            logger.warning(f"Could not sync persona handles for user {user.id}: {exc}")

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class ProfilePictureUploadView(APIView):
    """
    Uploads user profile picture directly to AWS S3 and links the S3 URL to user.picture in PostgreSQL.
    """
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        user_id = request.data.get("user_id") or (str(request.user.id) if request.user.is_authenticated else None)
        user = User.objects.filter(id=user_id).first() if user_id else None
        if not user:
            return Response({"error": "Valid user_id required to link profile picture"}, status=status.HTTP_400_BAD_REQUEST)

        image_b64 = request.data.get("image_base64")
        file_obj = request.FILES.get("image") or request.FILES.get("file")

        if not image_b64 and not file_obj:
            return Response({"error": "No image data provided"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if image_b64:
                # Remove header if present (e.g. data:image/jpeg;base64,...)
                if "," in image_b64:
                    image_b64 = image_b64.split(",", 1)[1]
                image_data = base64.b64decode(image_b64)
                file_stream = io.BytesIO(image_data)
                filename = f"user_avatars/{user.id}_{uuid.uuid4().hex[:8]}.jpg"
                content_type = "image/jpeg"
            else:
                ext = file_obj.name.split(".")[-1].lower() if "." in file_obj.name else "jpg"
                filename = f"user_avatars/{user.id}_{uuid.uuid4().hex[:8]}.{ext}"
                content_type = file_obj.content_type or "image/jpeg"
                file_stream = file_obj

            s3 = boto3.client(
                "s3",
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_REGION", "us-west-2"),
            )
            bucket = "reeve-devpilot-downloads-309490998255"
            region = os.getenv("AWS_REGION", "us-west-2")

            s3.upload_fileobj(
                file_stream,
                bucket,
                filename,
                ExtraArgs={"ContentType": content_type},
            )
            image_url = f"https://{bucket}.s3.{region}.amazonaws.com/{filename}"

            # Link S3 image URL directly to user in PostgreSQL
            user.picture = image_url
            user.save()

            # Sync persona publisher avatars
            try:
                from memory.models import Persona
                Persona.objects.filter(creator=user).update(publisher_avatar=image_url)
            except Exception:
                pass

            return Response({
                "success": True,
                "url": image_url,
                "user": UserSerializer(user).data,
            }, status=status.HTTP_200_OK)

        except Exception as exc:
            logger.error(f"S3 Profile Picture upload failed: {exc}")
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
