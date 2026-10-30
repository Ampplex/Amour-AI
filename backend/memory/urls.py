from django.urls import path
from .views import (
    ReeveStatusView,
    ChatMemoryView,
    StoreMemoryView,
    QueryMemoryView,
    ClearMemoryView,
    BotImageUploadView,
    GenerateAvatarPersonaView,
)

urlpatterns = [
    path("status/", ReeveStatusView.as_view(), name="memory-status"),
    path("chat/", ChatMemoryView.as_view(), name="memory-chat"),
    path("store/", StoreMemoryView.as_view(), name="memory-store"),
    path("query/", QueryMemoryView.as_view(), name="memory-query"),
    path("clear/", ClearMemoryView.as_view(), name="memory-clear"),
    path("upload-image/", BotImageUploadView.as_view(), name="bot-upload-image"),
    path("generate-persona/", GenerateAvatarPersonaView.as_view(), name="generate-avatar-persona"),
]
