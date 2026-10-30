from django.urls import path
from .views import GoogleAuthView, SignupView, LoginView, MeView, UserListView

urlpatterns = [
    path("google/", GoogleAuthView.as_view(), name="auth-google"),
    path("signup/", SignupView.as_view(), name="auth-signup"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("users/", UserListView.as_view(), name="auth-users"),
]
