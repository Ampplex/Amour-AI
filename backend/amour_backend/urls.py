from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from authentication.views import PrivacyPolicyView, WebAccountDeletionView
from authentication.admin_console_view import AdminConsoleWebView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("console/", AdminConsoleWebView.as_view(), name="admin-console"),
    path("admin-console/", RedirectView.as_view(url="/console/", permanent=False)),
    path("privacy/", PrivacyPolicyView.as_view(), name="privacy-policy"),
    path("api/privacy/", PrivacyPolicyView.as_view(), name="api-privacy-policy"),
    path("delete-account/", WebAccountDeletionView.as_view(), name="delete-account"),
    path("api/delete-account/", WebAccountDeletionView.as_view(), name="api-delete-account"),
    path("api/auth/", include("authentication.urls")),
    path("api/memory/", include("memory.urls")),
]

if settings.MEDIA_ROOT:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
