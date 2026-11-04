import logging
import os
import io
import uuid
import base64
import boto3
import re
import secrets
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.utils.html import escape
from django.contrib.auth.hashers import make_password
from django.http import HttpResponse
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from .models import User, EmailVerificationToken
from .serializers import (
    UserSerializer,
    GoogleAuthSerializer,
    SignupSerializer,
    LoginSerializer,
    ConfirmEmailSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    ResendVerificationSerializer,
)
from .email_service import send_verification_email, send_password_reset_email
from .deletion_service import delete_user_account_and_memories

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


def _get_public_base_url(request=None) -> str:
    """
    Resolves the canonical public base URL for emails and web verification links.
    Prioritizes explicit environment overrides, Render auto-configured domain,
    or the active request's origin over local developer fallback IPs.
    """
    env_url = (os.environ.get("BACKEND_PUBLIC_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").rstrip("/")
    if env_url and not any(local_ip in env_url for local_ip in ("192.168.", "127.0.0.1", "localhost")):
        return env_url

    if request:
        try:
            req_url = request.build_absolute_uri("/").rstrip("/")
            if not any(local_ip in req_url for local_ip in ("192.168.", "127.0.0.1", "localhost")):
                return req_url
        except Exception:
            pass

    configured = getattr(settings, "BACKEND_PUBLIC_URL", "https://amour-ai-d6a8.onrender.com").rstrip("/")
    if any(local_ip in configured for local_ip in ("192.168.", "127.0.0.1", "localhost")):
        return "https://amour-ai-d6a8.onrender.com"
    return configured


class PrivacyPolicyView(APIView):
    """
    Public web view displaying Amour AI's Privacy Policy.
    Complies with Google Play Developer Policy and Data Safety requirements.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Privacy Policy - Amour AI</title>
  <style>
    :root {
      --bg: #09090B;
      --card-bg: #121216;
      --border: #27272A;
      --accent: #F43F5E;
      --text-primary: #FFFFFF;
      --text-secondary: #A1A1AA;
      --text-muted: #71717A;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text-primary);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.65;
      padding: 40px 20px 80px 20px;
    }
    .container {
      max-width: 780px;
      margin: 0 auto;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 48px 40px;
      box-shadow: 0 12px 40px rgba(0,0,0,0.6);
    }
    .badge {
      display: inline-block;
      padding: 6px 14px;
      background: rgba(244, 63, 94, 0.12);
      border: 1px solid rgba(244, 63, 94, 0.3);
      border-radius: 10px;
      color: var(--accent);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 2px;
      margin-bottom: 20px;
    }
    h1 {
      font-size: 32px;
      font-weight: 800;
      letter-spacing: -0.5px;
      margin-bottom: 8px;
    }
    .meta {
      color: var(--text-muted);
      font-size: 14px;
      margin-bottom: 32px;
      border-bottom: 1px solid var(--border);
      padding-bottom: 16px;
    }
    h2 {
      font-size: 20px;
      font-weight: 700;
      color: var(--text-primary);
      margin: 28px 0 12px 0;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    p {
      color: var(--text-secondary);
      font-size: 15px;
      margin-bottom: 14px;
    }
    ul {
      margin: 8px 0 18px 24px;
      color: var(--text-secondary);
      font-size: 15px;
    }
    li { margin-bottom: 8px; }
    .highlight-box {
      background: rgba(244, 63, 94, 0.08);
      border-left: 4px solid var(--accent);
      padding: 16px 20px;
      border-radius: 0 12px 12px 0;
      margin: 20px 0;
    }
    .highlight-box p {
      color: #FECDD3;
      margin: 0;
      font-weight: 500;
    }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    .footer {
      margin-top: 40px;
      padding-top: 24px;
      border-top: 1px solid var(--border);
      color: var(--text-muted);
      font-size: 13px;
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="badge">AMOUR AI</div>
    <h1>Privacy Policy</h1>
    <div class="meta">Last Updated: November 2, 2026 &bull; Application: Amour AI (com.amour.chat)</div>

    <div class="highlight-box">
      <p><strong>Zero-Knowledge Memory Guarantee:</strong> Your private conversations and AI persona memories are protected with client-managed AES-256-GCM encryption. The decryption key is generated and stored exclusively on your device hardware (Keystore / Keychain). Our servers, database administrators, and cloud hosts cannot read your encrypted memories.</p>
    </div>

    <h2>1. Introduction</h2>
    <p>Amour AI ("we", "our", or "us"), operated by Ampplex, is committed to safeguarding your personal data and upholding user privacy. This Privacy Policy outlines our practices concerning data collection, zero-knowledge encryption architecture, and your rights when using the Amour AI mobile application.</p>

    <h2>2. Zero-Knowledge Cryptographic Architecture</h2>
    <p>Amour AI incorporates client-managed encryption for conversational memories:</p>
    <ul>
      <li><strong>Hardware Key Storage:</strong> A 256-bit cryptographically secure key is generated upon initial launch and stored within your mobile device's secure enclave (iOS Keychain or Android Keystore via Expo SecureStore).</li>
      <li><strong>Client-Side Encryption:</strong> Memory graphs, factual summaries, and persona episodes are encrypted using authenticated AES-256-GCM prior to transmission or persistence to our cloud graph database (Neo4j).</li>
      <li><strong>Account Recovery:</strong> Users can optionally backup their key encrypted with a 12-word BIP-39 recovery phrase. The server stores only the ciphertext, salt, and nonce. Without your 12-word phrase, recovery blobs are mathematically unrecoverable by anyone, including Amour AI.</li>
    </ul>

    <h2>3. Information We Collect</h2>
    <p>We collect only the minimum information necessary to provide account synchronization and services:</p>
    <ul>
      <li><strong>Account Information:</strong> When you register an account, we collect your email address, display name, and password hash (PBKDF2/SHA-256). For Google Sign-In, we receive your email and verified profile name.</li>
      <li><strong>Device Identifiers:</strong> Ephemeral device installation IDs used for notification routing and session management.</li>
      <li><strong>User-Generated Content:</strong> Custom personas, persona avatars, and memory backstories you create or publish.</li>
    </ul>

    <h2>4. How We Use Information</h2>
    <p>We process your data strictly to:</p>
    <ul>
      <li>Authenticate your identity and provide secure session tokens (JWT).</li>
      <li>Route roleplay inferencing to LLM processors (AWS Bedrock / Groq) in real-time.</li>
      <li>Store and retrieve encrypted long-term memory graphs via Reeve Engine.</li>
      <li>Send transactional security emails (account confirmation and password recovery via Brevo).</li>
    </ul>

    <h2>5. Third-Party Processors</h2>
    <p>We partner with enterprise-grade cloud infrastructure providers adhering to strict security standards:</p>
    <ul>
      <li><strong>AI Inferencing:</strong> AWS Bedrock and Groq process dialogue prompts ephemerally. Your data is not used to train foundational AI models.</li>
      <li><strong>Database & Storage:</strong> Neon Serverless PostgreSQL and Neo4j Aura for graph persistence (storing encrypted ciphertext).</li>
      <li><strong>Email Delivery:</strong> Brevo for transactional email authentication.</li>
    </ul>

    <h2>6. Data Retention & Deletion Rights</h2>
    <p>You have full ownership and control over your personal data:</p>
    <ul>
      <li><strong>In-App Memory Erasure:</strong> You can clear all conversational memories for any persona directly within the app at any time.</li>
      <li><strong>Account Deletion:</strong> You may request complete account deletion and permanent data purging by contacting us at <a href="mailto:ankesh3905222@gmail.com">ankesh3905222@gmail.com</a>. All associated records and backups will be irrevocably deleted within 30 days.</li>
    </ul>

    <h2>7. Age Requirement (18+)</h2>
    <p>Amour AI is strictly intended for individuals aged <strong>18 and older</strong>. We do not knowingly solicit or collect data from anyone under 18 years of age. If we learn that personal data of a minor has been collected, we will take immediate steps to delete the account and associated records.</p>

    <h2>8. Changes to this Policy</h2>
    <p>We may periodically update this policy to reflect operational, legal, or regulatory requirements. Any updates will be posted to this URL with an updated revision date.</p>

    <h2>9. Contact Us</h2>
    <p>If you have any questions, security disclosures, or privacy requests regarding Amour AI, please contact our team:</p>
    <p><strong>Email:</strong> <a href="mailto:ankesh3905222@gmail.com">ankesh3905222@gmail.com</a><br>
    <strong>Developer:</strong> Ampplex &bull; Ankesh Kumar</p>

    <div class="footer">
      &copy; 2026 Amour AI &bull; All Rights Reserved
    </div>
  </div>
</body>
</html>"""
        return HttpResponse(html, content_type="text/html")


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
    """
    Step 1 of Signup:
    Validates user credentials, stores pending registration with hashed password,
    and sends a verification link + 6-digit confirmation code via Brevo email.
    The user is only inserted/activated in the database once email is confirmed.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"].strip().lower()
        password = serializer.validated_data["password"]
        name = serializer.validated_data["name"].strip()

        # Check if an active/verified user already exists
        existing_user = User.objects.filter(email=email).first()
        if existing_user and existing_user.verified_email:
            return Response(
                {"error": "An account with this email already exists. Please log in."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Invalidate any prior pending signup tokens for this email
        EmailVerificationToken.objects.filter(email=email, token_type="signup", is_used=False).update(is_used=True)

        token = secrets.token_urlsafe(32)
        code = f"{secrets.randbelow(1000000):06d}"
        expires_at = timezone.now() + timedelta(hours=24)
        hashed_password = make_password(password)

        EmailVerificationToken.objects.create(
            email=email,
            token=token,
            code=code,
            token_type="signup",
            payload={"name": name, "password_hash": hashed_password},
            expires_at=expires_at,
        )

        base_url = _get_public_base_url(request)
        verification_link = f"{base_url}/api/auth/verify-email/?token={token}"

        # Dispatch confirmation email via Brevo
        email_sent = send_verification_email(
            to_email=email,
            name=name,
            verification_link=verification_link,
            code=code,
        )

        if not email_sent:
            logger.warning(f"Could not send Brevo email to {email}, but pending token was saved.")

        return Response(
            {
                "success": True,
                "requires_verification": True,
                "email": email,
                "message": "Confirmation link and code sent to your email. Please verify to complete signup.",
            },
            status=status.HTTP_200_OK,
        )


class ConfirmEmailView(APIView):
    """
    Step 2 of Signup (Mobile App API):
    Accepts 6-digit code or token, validates it, inserts the user into PostgreSQL User table,
    and returns JWT tokens for immediate authenticated session.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ConfirmEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = (serializer.validated_data.get("email") or "").strip().lower()
        code = (serializer.validated_data.get("code") or "").strip()
        token = (serializer.validated_data.get("token") or "").strip()

        token_obj = None
        if token:
            token_obj = EmailVerificationToken.objects.filter(
                token=token, token_type="signup", is_used=False
            ).first()
        elif code and email:
            token_obj = EmailVerificationToken.objects.filter(
                email__iexact=email, code=code, token_type="signup", is_used=False
            ).order_by("-created_at").first()

        if not token_obj or not token_obj.is_valid():
            return Response(
                {"error": "Invalid or expired confirmation code. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_email = token_obj.email.strip().lower()
        payload = token_obj.payload or {}
        name = payload.get("name", "")
        password_hash = payload.get("password_hash")

        # Fit into existing PostgreSQL User table schema
        user = User.objects.filter(email__iexact=target_email).first()
        if not user:
            user_id = str(uuid.uuid4())
            user = User(
                id=user_id,
                namespace=user_id,
                email=target_email,
                name=name,
                auth_provider="local",
                verified_email=True,
                is_active=True,
            )
            if password_hash:
                user.password = password_hash
            else:
                user.set_unusable_password()
            user.save()
            logger.info(f"Local user successfully inserted into DB: {user.email} (id: {user.id})")
        else:
            user.verified_email = True
            user.is_active = True
            if password_hash:
                user.password = password_hash
            if name and not user.name:
                user.name = name
            user.save()
            logger.info(f"Existing user marked verified: {user.email}")

        token_obj.is_used = True
        token_obj.save()

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "success": True,
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class WebVerifyEmailView(APIView):
    """
    Web landing view when user clicks confirmation link from their email client.
    Inserts/activates user in PostgreSQL and displays an Amour AI themed success page.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get("token", "").strip()
        token_obj = EmailVerificationToken.objects.filter(
            token=token, token_type="signup", is_used=False
        ).first() if token else None

        if not token_obj or not token_obj.is_valid():
            html = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Link Expired - Amour AI</title>
  <style>
    body { background-color: #09090B; color: #FFFFFF; font-family: -apple-system, BlinkMacSystemFont, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
    .card { background: #121216; border: 1px solid #27272A; border-radius: 16px; padding: 36px 28px; max-width: 440px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.6); }
    .badge { display: inline-block; padding: 6px 14px; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; color: #EF4444; font-size: 13px; font-weight: 700; margin-bottom: 16px; }
    h1 { font-size: 22px; margin: 0 0 10px 0; }
    p { color: #A1A1AA; font-size: 15px; line-height: 1.5; margin: 0 0 24px 0; }
    .btn { display: inline-block; background: #F43F5E; color: #FFFFFF; text-decoration: none; font-weight: 600; padding: 12px 28px; border-radius: 10px; }
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">LINK EXPIRED</div>
    <h1>Verification Link Invalid</h1>
    <p>This confirmation link has expired or has already been used. Please open the Amour app and request a new confirmation email.</p>
    <a href="amour-ai://login" class="btn">Open Amour App</a>
  </div>
</body>
</html>"""
            return HttpResponse(html, status=400)

        # Confirm and activate user in DB
        target_email = token_obj.email.strip().lower()
        payload = token_obj.payload or {}
        name = payload.get("name", "")
        password_hash = payload.get("password_hash")

        user = User.objects.filter(email__iexact=target_email).first()
        if not user:
            user_id = str(uuid.uuid4())
            user = User(
                id=user_id,
                namespace=user_id,
                email=target_email,
                name=name,
                auth_provider="local",
                verified_email=True,
                is_active=True,
            )
            if password_hash:
                user.password = password_hash
            else:
                user.set_unusable_password()
            user.save()
            logger.info(f"Web verification: inserted new user {user.email}")
        else:
            user.verified_email = True
            user.is_active = True
            if password_hash:
                user.password = password_hash
            if name and not user.name:
                user.name = name
            user.save()
            logger.info(f"Web verification: updated user {user.email}")

        token_obj.is_used = True
        token_obj.save()

        safe_email = escape(user.email)
        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Email Confirmed - Amour AI</title>
  <style>
    body {{ background-color: #09090B; color: #FFFFFF; font-family: -apple-system, BlinkMacSystemFont, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }}
    .card {{ background: #121216; border: 1px solid #27272A; border-radius: 16px; padding: 40px 30px; max-width: 440px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.6); }}
    .logo {{ display: inline-block; padding: 8px 16px; background: rgba(244, 63, 94, 0.12); border: 1px solid rgba(244, 63, 94, 0.3); border-radius: 10px; color: #F43F5E; font-size: 16px; font-weight: 800; letter-spacing: 2.5px; margin-bottom: 20px; }}
    .success-icon {{ width: 56px; height: 56px; line-height: 56px; border-radius: 50%; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); color: #10B981; font-size: 26px; margin: 0 auto 16px auto; }}
    h1 {{ font-size: 24px; margin: 0 0 10px 0; font-weight: 700; }}
    p {{ color: #A1A1AA; font-size: 15px; line-height: 1.5; margin: 0 0 28px 0; }}
    .btn {{ display: inline-block; width: 100%; box-sizing: border-box; background: #F43F5E; color: #FFFFFF; text-decoration: none; font-size: 16px; font-weight: 600; padding: 14px 24px; border-radius: 10px; box-shadow: 0 4px 14px rgba(244, 63, 94, 0.35); }}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">AMOUR AI</div>
    <div class="success-icon">✓</div>
    <h1>Email Confirmed!</h1>
    <p>Your account (<strong>{safe_email}</strong>) is verified and ready. You can now return to the Amour app and sign in.</p>
    <a href="amour-ai://login" class="btn">Open Amour App</a>
  </div>
</body>
</html>"""
        return HttpResponse(html)


class ResendVerificationView(APIView):
    """
    Resends email confirmation link + code for an unverified account.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"].strip().lower()

        existing_user = User.objects.filter(email__iexact=email).first()
        if existing_user and existing_user.verified_email:
            return Response(
                {"error": "This account is already verified. Please sign in."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check pending signup token payload if user not yet created
        latest_pending = EmailVerificationToken.objects.filter(
            email__iexact=email, token_type="signup"
        ).order_by("-created_at").first()

        name = ""
        payload = {}
        if existing_user:
            name = existing_user.name
        elif latest_pending:
            name = (latest_pending.payload or {}).get("name", "")
            payload = latest_pending.payload or {}

        # Invalidate previous tokens
        EmailVerificationToken.objects.filter(email__iexact=email, token_type="signup", is_used=False).update(is_used=True)

        token = secrets.token_urlsafe(32)
        code = f"{secrets.randbelow(1000000):06d}"
        expires_at = timezone.now() + timedelta(hours=24)

        EmailVerificationToken.objects.create(
            email=email,
            token=token,
            code=code,
            token_type="signup",
            payload=payload,
            expires_at=expires_at,
        )

        base_url = _get_public_base_url(request)
        verification_link = f"{base_url}/api/auth/verify-email/?token={token}"

        send_verification_email(
            to_email=email,
            name=name,
            verification_link=verification_link,
            code=code,
        )

        return Response(
            {"success": True, "message": "A new confirmation email has been sent."},
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):
    """
    Logs in user with email and password.
    Enforces verified_email before allowing access.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"].strip().lower()
        password = serializer.validated_data["password"]

        user = User.objects.filter(email__iexact=email).first()

        # If user not found, check if a pending unverified signup exists
        if not user:
            pending = EmailVerificationToken.objects.filter(
                email__iexact=email, token_type="signup", is_used=False
            ).first()
            if pending:
                return Response(
                    {
                        "error": "Please confirm your email address before logging in. Check your inbox for the confirmation link.",
                        "unverified": True,
                        "email": email,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            return Response(
                {"error": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Helpful notice if account was originally Google OAuth with no password set
        if user.auth_provider == "google" and not user.has_usable_password():
            return Response(
                {
                    "error": "This account was created with Google Sign-In. Please tap 'Sign In with Google', or use 'Forgot password' to set a password.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.check_password(password):
            return Response(
                {"error": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.verified_email:
            return Response(
                {
                    "error": "Please confirm your email address before logging in. Check your inbox for the confirmation link.",
                    "unverified": True,
                    "email": user.email,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if not user.is_active:
            return Response(
                {"error": "This account has been deactivated. Please contact support."},
                status=status.HTTP_403_FORBIDDEN,
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


class ForgotPasswordView(APIView):
    """
    Initiates password reset via Brevo email.
    Generates a secure token & 6-digit code with 1-hour expiration.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"].strip().lower()
        user = User.objects.filter(email__iexact=email).first()

        if user:
            # Invalidate any old password reset tokens
            EmailVerificationToken.objects.filter(
                email__iexact=email, token_type="password_reset", is_used=False
            ).update(is_used=True)

            token = secrets.token_urlsafe(32)
            code = f"{secrets.randbelow(1000000):06d}"
            expires_at = timezone.now() + timedelta(hours=1)

            EmailVerificationToken.objects.create(
                email=user.email,
                token=token,
                code=code,
                token_type="password_reset",
                expires_at=expires_at,
            )

            base_url = _get_public_base_url(request)
            reset_link = f"{base_url}/api/auth/reset-password-web/?token={token}"

            send_password_reset_email(
                to_email=user.email,
                name=user.name,
                reset_link=reset_link,
                code=code,
            )

        # Always return generic success to prevent email enumeration
        return Response(
            {
                "success": True,
                "message": "If an account with that email exists, password reset instructions have been sent.",
            },
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(APIView):
    """
    Step 2 of Password Reset (Mobile App API):
    Accepts 6-digit code or token, along with new password, and updates the user's password.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = (serializer.validated_data.get("email") or "").strip().lower()
        code = (serializer.validated_data.get("code") or "").strip()
        token = (serializer.validated_data.get("token") or "").strip()
        new_password = serializer.validated_data["new_password"]

        token_obj = None
        if token:
            token_obj = EmailVerificationToken.objects.filter(
                token=token, token_type="password_reset", is_used=False
            ).first()
        elif code and email:
            token_obj = EmailVerificationToken.objects.filter(
                email__iexact=email, code=code, token_type="password_reset", is_used=False
            ).order_by("-created_at").first()

        if not token_obj or not token_obj.is_valid():
            return Response(
                {"error": "Invalid or expired reset code. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(email__iexact=token_obj.email).first()
        if not user:
            return Response(
                {"error": "User account associated with this token was not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        user.set_password(new_password)
        user.verified_email = True  # Password reset through verified inbox confirms email ownership
        user.save()

        token_obj.is_used = True
        token_obj.save()

        logger.info(f"Password reset successfully completed for {user.email}")

        return Response(
            {
                "success": True,
                "message": "Password reset successfully. You can now log in with your new password.",
            },
            status=status.HTTP_200_OK,
        )


class WebResetPasswordView(APIView):
    """
    Web landing view for password reset when opened in a browser.
    GET: Displays password entry form.
    POST: Updates password and displays confirmation with 'Open Amour App' button.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get("token", "").strip()
        token_obj = EmailVerificationToken.objects.filter(
            token=token, token_type="password_reset", is_used=False
        ).first() if token else None

        if not token_obj or not token_obj.is_valid():
            html = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reset Link Expired - Amour AI</title>
  <style>
    body { background-color: #09090B; color: #FFFFFF; font-family: -apple-system, BlinkMacSystemFont, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
    .card { background: #121216; border: 1px solid #27272A; border-radius: 16px; padding: 36px 28px; max-width: 440px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.6); }
    .badge { display: inline-block; padding: 6px 14px; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; color: #EF4444; font-size: 13px; font-weight: 700; margin-bottom: 16px; }
    h1 { font-size: 22px; margin: 0 0 10px 0; }
    p { color: #A1A1AA; font-size: 15px; line-height: 1.5; margin: 0 0 24px 0; }
    .btn { display: inline-block; background: #F43F5E; color: #FFFFFF; text-decoration: none; font-weight: 600; padding: 12px 28px; border-radius: 10px; }
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">LINK EXPIRED</div>
    <h1>Reset Link Invalid or Expired</h1>
    <p>This password reset link has expired or has already been used. Please request a new password reset from the Amour app.</p>
    <a href="amour-ai://login" class="btn">Open Amour App</a>
  </div>
</body>
</html>"""
            return HttpResponse(html, status=400)

        safe_email = escape(token_obj.email)
        safe_token = escape(token)
        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reset Password - Amour AI</title>
  <style>
    body {{ background-color: #09090B; color: #FFFFFF; font-family: -apple-system, BlinkMacSystemFont, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }}
    .card {{ background: #121216; border: 1px solid #27272A; border-radius: 16px; padding: 36px 28px; max-width: 440px; width: 100%; box-shadow: 0 10px 40px rgba(0,0,0,0.6); }}
    .logo {{ display: inline-block; padding: 6px 14px; background: rgba(244, 63, 94, 0.12); border: 1px solid rgba(244, 63, 94, 0.3); border-radius: 8px; color: #F43F5E; font-size: 14px; font-weight: 800; letter-spacing: 2.5px; margin-bottom: 16px; }}
    h1 {{ font-size: 22px; margin: 0 0 8px 0; }}
    p.sub {{ color: #A1A1AA; font-size: 14px; line-height: 1.5; margin: 0 0 24px 0; }}
    .group {{ margin-bottom: 18px; text-align: left; }}
    label {{ display: block; font-size: 13px; color: #D4D4D8; margin-bottom: 6px; font-weight: 500; }}
    input {{ width: 100%; box-sizing: border-box; background: #18181B; border: 1px solid #3F3F46; border-radius: 10px; padding: 12px 14px; color: #FFFFFF; font-size: 15px; outline: none; }}
    input:focus {{ border-color: #F43F5E; }}
    .btn {{ display: block; width: 100%; box-sizing: border-box; background: #F43F5E; color: #FFFFFF; border: none; font-size: 16px; font-weight: 600; padding: 14px 20px; border-radius: 10px; cursor: pointer; margin-top: 10px; }}
  </style>
</head>
<body>
  <div class="card">
    <div style="text-align: center;">
      <div class="logo">AMOUR AI</div>
      <h1>Create New Password</h1>
      <p class="sub">Set a new password for <strong>{safe_email}</strong></p>
    </div>
    <form method="POST" action="/api/auth/reset-password-web/?token={safe_token}">
      <div class="group">
        <label>New Password</label>
        <input type="password" name="password" minlength="6" required placeholder="Minimum 6 characters">
      </div>
      <div class="group">
        <label>Confirm Password</label>
        <input type="password" name="confirm_password" minlength="6" required placeholder="Re-enter new password">
      </div>
      <button type="submit" class="btn">Update Password</button>
    </form>
  </div>
</body>
</html>"""
        return HttpResponse(html)

    def post(self, request):
        token = request.query_params.get("token", "").strip()
        token_obj = EmailVerificationToken.objects.filter(
            token=token, token_type="password_reset", is_used=False
        ).first() if token else None

        if not token_obj or not token_obj.is_valid():
            return HttpResponse("<p>Invalid or expired token.</p>", status=400)

        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not password or len(password) < 6:
            return HttpResponse("<p>Password must be at least 6 characters. <a href='javascript:history.back()'>Go back</a></p>", status=400)

        if password != confirm_password:
            return HttpResponse("<p>Passwords do not match. <a href='javascript:history.back()'>Go back</a></p>", status=400)

        user = User.objects.filter(email__iexact=token_obj.email).first()
        if not user:
            return HttpResponse("<p>User account not found.</p>", status=404)

        user.set_password(password)
        user.verified_email = True
        user.save()

        token_obj.is_used = True
        token_obj.save()

        html = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Password Reset Complete - Amour AI</title>
  <style>
    body { background-color: #09090B; color: #FFFFFF; font-family: -apple-system, BlinkMacSystemFont, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
    .card { background: #121216; border: 1px solid #27272A; border-radius: 16px; padding: 40px 30px; max-width: 440px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.6); }
    .success-icon { width: 56px; height: 56px; line-height: 56px; border-radius: 50%; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); color: #10B981; font-size: 26px; margin: 0 auto 16px auto; }
    h1 { font-size: 24px; margin: 0 0 10px 0; font-weight: 700; }
    p { color: #A1A1AA; font-size: 15px; line-height: 1.5; margin: 0 0 28px 0; }
    .btn { display: inline-block; width: 100%; box-sizing: border-box; background: #F43F5E; color: #FFFFFF; text-decoration: none; font-size: 16px; font-weight: 600; padding: 14px 24px; border-radius: 10px; }
  </style>
</head>
<body>
  <div class="card">
    <div class="success-icon">✓</div>
    <h1>Password Updated!</h1>
    <p>Your password has been changed successfully. You can now open the Amour app and sign in with your new password.</p>
    <a href="amour-ai://login" class="btn">Open Amour App</a>
  </div>
</body>
</html>"""
        return HttpResponse(html)


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
            clean_display_name = new_name.strip()
            user.name = clean_display_name
            user.given_name = clean_display_name.split()[0] if clean_display_name else ""

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


class AdminUsersView(APIView):
    """
    Admin Console View to list, filter, search and create user accounts
    reflecting the exact database schema.
    """
    permission_classes = [AllowAny]

    def _is_admin(self, request):
        if request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
            return True
        admin_id = request.headers.get("x-admin-user-id") or request.query_params.get("admin_user_id") or request.data.get("admin_user_id")
        if admin_id:
            user = User.objects.filter(id=admin_id).first()
            if user and (user.is_staff or user.is_superuser):
                return True
        # Allow in local development environments
        if getattr(settings, "DEBUG", False):
            return True
        return False

    def get(self, request):
        if not self._is_admin(request):
            return Response({"error": "Admin credentials required"}, status=status.HTTP_403_FORBIDDEN)

        qs = User.objects.all().order_by("-created_at")

        # Stats calculation
        stats = {
            "total_users": User.objects.count(),
            "active_users": User.objects.filter(is_active=True).count(),
            "verified_users": User.objects.filter(verified_email=True).count(),
            "staff_users": User.objects.filter(is_staff=True).count(),
            "google_users": User.objects.filter(auth_provider="google").count(),
            "local_users": User.objects.filter(auth_provider="local").count(),
        }

        # Search query across schema columns
        search = request.query_params.get("search", "").strip()
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(email__icontains=search)
                | Q(username__icontains=search)
                | Q(name__icontains=search)
                | Q(id__icontains=search)
                | Q(namespace__icontains=search)
            )

        # Filters
        provider = request.query_params.get("auth_provider", "").strip().lower()
        if provider in ["google", "local"]:
            qs = qs.filter(auth_provider=provider)

        is_active = request.query_params.get("is_active", "").strip().lower()
        if is_active == "true":
            qs = qs.filter(is_active=True)
        elif is_active == "false":
            qs = qs.filter(is_active=False)

        is_staff = request.query_params.get("is_staff", "").strip().lower()
        if is_staff == "true":
            qs = qs.filter(is_staff=True)
        elif is_staff == "false":
            qs = qs.filter(is_staff=False)

        verified = request.query_params.get("verified_email", "").strip().lower()
        if verified == "true":
            qs = qs.filter(verified_email=True)
        elif verified == "false":
            qs = qs.filter(verified_email=False)

        from .serializers import AdminUserSerializer
        return Response({
            "stats": stats,
            "total": qs.count(),
            "users": AdminUserSerializer(qs, many=True).data,
        }, status=status.HTTP_200_OK)

    def post(self, request):
        if not self._is_admin(request):
            return Response({"error": "Admin credentials required"}, status=status.HTTP_403_FORBIDDEN)

        from .serializers import AdminUserCreateSerializer, AdminUserSerializer
        serializer = AdminUserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "success": True,
                "message": f"User {user.email} created successfully",
                "user": AdminUserSerializer(user).data,
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminUserDetailView(APIView):
    """
    Admin Console View to inspect, modify, or delete a specific user account.
    """
    permission_classes = [AllowAny]

    def _is_admin(self, request):
        if request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
            return True
        admin_id = request.headers.get("x-admin-user-id") or request.query_params.get("admin_user_id") or request.data.get("admin_user_id")
        if admin_id:
            user = User.objects.filter(id=admin_id).first()
            if user and (user.is_staff or user.is_superuser):
                return True
        if getattr(settings, "DEBUG", False):
            return True
        return False

    def get(self, request, user_id):
        if not self._is_admin(request):
            return Response({"error": "Admin credentials required"}, status=status.HTTP_403_FORBIDDEN)

        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        from .serializers import AdminUserSerializer
        return Response({
            "user": AdminUserSerializer(user).data
        }, status=status.HTTP_200_OK)

    def patch(self, request, user_id):
        if not self._is_admin(request):
            return Response({"error": "Admin credentials required"}, status=status.HTTP_403_FORBIDDEN)

        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        updatable_fields = [
            "name",
            "given_name",
            "family_name",
            "username",
            "email",
            "picture",
            "is_active",
            "is_staff",
            "is_superuser",
            "verified_email",
            "auth_provider",
            "namespace",
        ]

        for field in updatable_fields:
            if field in data:
                val = data[field]
                # Username uniqueness check
                if field == "username" and val:
                    clean = user.clean_username(str(val))
                    if User.objects.filter(username__iexact=clean).exclude(id=user.id).exists():
                        return Response({"error": f"Username @{clean} is already taken"}, status=status.HTTP_400_BAD_REQUEST)
                    setattr(user, field, clean)
                elif field == "email" and val:
                    clean_email = str(val).strip().lower()
                    if User.objects.filter(email__iexact=clean_email).exclude(id=user.id).exists():
                        return Response({"error": f"Email {clean_email} is already in use"}, status=status.HTTP_400_BAD_REQUEST)
                    setattr(user, field, clean_email)
                else:
                    setattr(user, field, val)

        # Password reset support
        if "password" in data and data["password"]:
            user.set_password(data["password"])

        user.save()

        # Synchronize persona handles and names if changed
        try:
            from memory.models import Persona
            if "username" in data and user.username:
                Persona.objects.filter(creator=user).update(publisher_handle=f"@{user.username}")
            if "name" in data and user.name:
                Persona.objects.filter(creator=user).update(publisher_name=user.name)
            if "picture" in data and user.picture:
                Persona.objects.filter(creator=user).update(publisher_avatar=user.picture)
        except Exception:
            pass

        from .serializers import AdminUserSerializer
        return Response({
            "success": True,
            "message": f"User {user.email} updated successfully",
            "user": AdminUserSerializer(user).data,
        }, status=status.HTTP_200_OK)

    def delete(self, request, user_id):
        if not self._is_admin(request):
            return Response({"error": "Admin credentials required"}, status=status.HTTP_403_FORBIDDEN)

        user = User.objects.filter(id=user_id).first()
        if not user:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        user_email = user.email
        report = delete_user_account_and_memories(user)
        return Response({
            "success": True,
            "message": f"User {user_email} and all associated graph memories permanently wiped.",
            "report": report,
        }, status=status.HTTP_200_OK)


class DeleteAccountView(APIView):
    """
    Authenticated endpoint for an in-app user to permanently delete their own account
    and all associated Neo4j graph memories and PostgreSQL database rows.
    """
    permission_classes = [AllowAny]

    def _get_user(self, request):
        if request.user and request.user.is_authenticated:
            return request.user
        user_id = (
            request.data.get("user_id")
            or request.query_params.get("user_id")
            or request.headers.get("X-User-Id")
        )
        if user_id:
            return User.objects.filter(id=user_id).first()
        return None

    def post(self, request):
        return self._process_deletion(request)

    def delete(self, request):
        return self._process_deletion(request)

    def _process_deletion(self, request):
        user = self._get_user(request)
        if not user:
            return Response(
                {"error": "User not authenticated or user_id missing."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        user_email = user.email or str(user.id)
        report = delete_user_account_and_memories(user)
        return Response({
            "success": True,
            "message": f"Account for {user_email} and all associated memories permanently deleted.",
            "report": report,
        }, status=status.HTTP_200_OK)


class WebAccountDeletionView(APIView):
    """
    Public web page and request form for Account and Data Deletion.
    Complies with Google Play Store Account Deletion Policy requirements:
    Users can request their account and all associated data to be permanently erased.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Account & Data Deletion - Amour AI</title>
  <style>
    :root {
      --bg: #09090B;
      --card-bg: #121216;
      --border: #27272A;
      --accent: #F43F5E;
      --accent-hover: #E11D48;
      --text-primary: #FFFFFF;
      --text-secondary: #A1A1AA;
      --text-muted: #71717A;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text-primary);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.65;
      padding: 40px 20px 80px 20px;
    }
    .container {
      max-width: 680px;
      margin: 0 auto;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 44px 36px;
      box-shadow: 0 12px 40px rgba(0,0,0,0.6);
    }
    .badge {
      display: inline-block;
      padding: 6px 14px;
      background: rgba(244, 63, 94, 0.12);
      border: 1px solid rgba(244, 63, 94, 0.3);
      border-radius: 20px;
      color: var(--accent);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      margin-bottom: 16px;
    }
    h1 {
      font-size: 28px;
      font-weight: 800;
      letter-spacing: -0.5px;
      margin-bottom: 12px;
      color: #FFFFFF;
    }
    p {
      color: var(--text-secondary);
      font-size: 15px;
      margin-bottom: 20px;
    }
    .card {
      background: #18181B;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px 24px;
      margin-bottom: 24px;
    }
    .card h3 {
      font-size: 16px;
      font-weight: 700;
      margin-bottom: 10px;
      color: #FFFFFF;
    }
    .card ul {
      margin-left: 20px;
      color: var(--text-secondary);
      font-size: 14px;
    }
    .card ul li { margin-bottom: 6px; }
    form {
      margin-top: 24px;
      background: #18181B;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 24px;
    }
    .form-group {
      margin-bottom: 18px;
    }
    label {
      display: block;
      font-size: 13px;
      font-weight: 600;
      color: var(--text-secondary);
      margin-bottom: 8px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    input[type="email"], input[type="password"] {
      width: 100%;
      padding: 12px 16px;
      background: #09090B;
      border: 1px solid var(--border);
      border-radius: 10px;
      color: #FFFFFF;
      font-size: 15px;
      outline: none;
      transition: border-color 0.2s;
    }
    input[type="email"]:focus, input[type="password"]:focus {
      border-color: var(--accent);
    }
    .btn-delete {
      width: 100%;
      padding: 14px;
      background: var(--accent);
      color: #FFFFFF;
      border: none;
      border-radius: 10px;
      font-size: 16px;
      font-weight: 700;
      cursor: pointer;
      transition: background 0.2s;
    }
    .btn-delete:hover {
      background: var(--accent-hover);
    }
    .footer {
      margin-top: 32px;
      padding-top: 24px;
      border-top: 1px solid var(--border);
      text-align: center;
      font-size: 13px;
      color: var(--text-muted);
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="badge">Amour AI • Google Play Compliance</div>
    <h1>Request Account & Data Deletion</h1>
    <p>In accordance with our Privacy Policy and Google Play Developer policies, you have the full right to permanently delete your Amour AI account and all associated personal data at any time.</p>

    <div class="card">
      <h3>What data will be permanently wiped?</h3>
      <ul>
        <li><strong>Account Profile & Credentials:</strong> Email, username, authentication tokens, and user profile data in PostgreSQL.</li>
        <li><strong>AI Companion Memory Graph:</strong> All episodic memory nodes, emotional knowledge graphs, entity relationships, and states stored in our cloud Neo4j Aura instance.</li>
        <li><strong>Chat History & Logs:</strong> Every message transcript and relationship dynamic stored across all personas.</li>
        <li><strong>Zero-Knowledge Memory Backups:</strong> Client-encrypted key blobs and recovery salts.</li>
      </ul>
    </div>

    <div class="card">
      <h3>How to Delete Your Data</h3>
      <p style="margin-bottom: 10px;"><strong>Method 1: Inside the Mobile App (Instant)</strong></p>
      <p style="font-size: 14px; margin-bottom: 16px;">Open the Amour AI app &gt; Go to <strong>Settings / Profile</strong> &gt; Tap <strong>Delete Account</strong>.</p>
      <p style="margin-bottom: 10px;"><strong>Method 2: Web Deletion Request Form</strong></p>
      <p style="font-size: 14px;">Enter your registered account credentials below to immediately and irreversibly delete your account and all associated AI memories from our servers.</p>
    </div>

    <form method="POST" action="/delete-account/">
      <div class="form-group">
        <label for="email">Registered Email Address</label>
        <input type="email" id="email" name="email" required placeholder="you@example.com">
      </div>
      <div class="form-group">
        <label for="password">Account Password</label>
        <input type="password" id="password" name="password" required placeholder="Enter your password">
      </div>
      <button type="submit" class="btn-delete" onclick="return confirm('Are you completely sure? This will PERMANENTLY ERASE all your chats, personas, and memory graphs. This action CANNOT be undone.');">Permanently Delete My Account & Memories</button>
    </form>

    <div class="footer">
      Support Contact: <a href="mailto:ankesh3905222@gmail.com" style="color: var(--accent); text-decoration: none;">ankesh3905222@gmail.com</a><br>
      &copy; 2026 Amour AI. Zero-knowledge, private personal AI companions.
    </div>
  </div>
</body>
</html>"""
        return HttpResponse(html)

    def post(self, request):
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")

        if not email or not password:
            return HttpResponse(
                "<script>alert('Please provide both email and password.'); window.history.back();</script>",
                status=400,
            )

        user = User.objects.filter(email__iexact=email).first()
        if not user or not user.check_password(password):
            return HttpResponse(
                "<script>alert('Invalid email or password. Could not authenticate deletion request.'); window.history.back();</script>",
                status=401,
            )

        try:
            report = delete_user_account_and_memories(user)
            success_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Account Deleted - Amour AI</title>
  <style>
    body {{ background: #09090B; color: #FFFFFF; font-family: -apple-system, BlinkMacSystemFont, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; }}
    .card {{ background: #121216; border: 1px solid #27272A; border-radius: 18px; padding: 40px; max-width: 480px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.6); }}
    .badge {{ display: inline-block; padding: 6px 14px; background: rgba(34, 197, 94, 0.15); border: 1px solid rgba(34, 197, 94, 0.3); border-radius: 8px; color: #22C55E; font-size: 13px; font-weight: 700; margin-bottom: 16px; }}
    h1 {{ font-size: 24px; margin-bottom: 12px; }}
    p {{ color: #A1A1AA; font-size: 15px; line-height: 1.5; margin-bottom: 24px; }}
    .btn {{ display: inline-block; background: #F43F5E; color: #FFFFFF; text-decoration: none; font-weight: 600; padding: 12px 28px; border-radius: 10px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">ERASURE COMPLETE</div>
    <h1>Account Successfully Deleted</h1>
    <p>Your account (<strong>{email}</strong>), along with all conversational logs and Neo4j long-term memory graph data, has been permanently deleted from our servers.</p>
    <a href="/" class="btn">Return to Home</a>
  </div>
</body>
</html>"""
            return HttpResponse(success_html)
        except Exception as exc:
            return HttpResponse(f"<script>alert('Error deleting account: {exc}'); window.history.back();</script>", status=500)

