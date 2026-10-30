import logging
from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
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
            # Update latest profile details
            if name:
                user.name = name
            if picture:
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
