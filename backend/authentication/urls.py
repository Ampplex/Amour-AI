from django.urls import path
from .views import (
    GoogleAuthView,
    SignupView,
    ConfirmEmailView,
    WebVerifyEmailView,
    ResendVerificationView,
    LoginView,
    ForgotPasswordView,
    ResetPasswordView,
    WebResetPasswordView,
    MeView,
    UserListView,
    ProfileView,
    ProfilePictureUploadView,
)

urlpatterns = [
    path("google/", GoogleAuthView.as_view(), name="auth-google"),
    path("signup/", SignupView.as_view(), name="auth-signup"),
    path("confirm-email/", ConfirmEmailView.as_view(), name="auth-confirm-email"),
    path("verify-email/", WebVerifyEmailView.as_view(), name="auth-web-verify-email"),
    path("resend-verification/", ResendVerificationView.as_view(), name="auth-resend-verification"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="auth-forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="auth-reset-password"),
    path("reset-password-web/", WebResetPasswordView.as_view(), name="auth-web-reset-password"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("profile/", ProfileView.as_view(), name="auth-profile"),
    path("profile/upload-picture/", ProfilePictureUploadView.as_view(), name="auth-profile-upload-picture"),
    path("users/", UserListView.as_view(), name="auth-users"),
]

