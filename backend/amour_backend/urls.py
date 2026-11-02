from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from authentication.views import PrivacyPolicyView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("privacy/", PrivacyPolicyView.as_view(), name="privacy-policy"),
    path("api/privacy/", PrivacyPolicyView.as_view(), name="api-privacy-policy"),
    path("api/auth/", include("authentication.urls")),
    path("api/memory/", include("memory.urls")),
]

if settings.MEDIA_ROOT:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
