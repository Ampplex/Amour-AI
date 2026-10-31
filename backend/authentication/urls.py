from django.urls import path
from .views import (
    GoogleAuthView,
    SignupView,
    LoginView,
    MeView,
    UserListView,
    ProfileView,
    ProfilePictureUploadView,
)

urlpatterns = [
    path("google/", GoogleAuthView.as_view(), name="auth-google"),
    path("signup/", SignupView.as_view(), name="auth-signup"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("profile/", ProfileView.as_view(), name="auth-profile"),
    path("profile/upload-picture/", ProfilePictureUploadView.as_view(), name="auth-profile-upload-picture"),
    path("users/", UserListView.as_view(), name="auth-users"),
]
