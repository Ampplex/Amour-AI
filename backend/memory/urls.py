from django.urls import path
from .views import (
    ReeveStatusView,
    ChatMemoryView,
    StoreMemoryView,
    QueryMemoryView,
    ClearMemoryView,
    BotImageUploadView,
    GenerateAvatarPersonaView,
    PersonaListCreateView,
    PersonaDetailView,
    PersonaLikeToggleView,
    PublisherFollowToggleView,
    PublisherProfileView,
    UserInteractionsView,
)

urlpatterns = [
    path("status/", ReeveStatusView.as_view(), name="memory-status"),
    path("chat/", ChatMemoryView.as_view(), name="memory-chat"),
    path("store/", StoreMemoryView.as_view(), name="memory-store"),
    path("query/", QueryMemoryView.as_view(), name="memory-query"),
    path("clear/", ClearMemoryView.as_view(), name="memory-clear"),
    path("upload-image/", BotImageUploadView.as_view(), name="bot-upload-image"),
    path("generate-persona/", GenerateAvatarPersonaView.as_view(), name="generate-avatar-persona"),
    path("personas/", PersonaListCreateView.as_view(), name="persona-list-create"),
    path("personas/<uuid:persona_id>/", PersonaDetailView.as_view(), name="persona-detail"),
    path("personas/<uuid:persona_id>/like/", PersonaLikeToggleView.as_view(), name="persona-like"),
    path("publishers/<str:handle>/follow/", PublisherFollowToggleView.as_view(), name="publisher-follow"),
    path("publishers/<str:identifier>/profile/", PublisherProfileView.as_view(), name="publisher-profile"),
    path("user-interactions/", UserInteractionsView.as_view(), name="user-interactions"),
    path("interactions/", UserInteractionsView.as_view(), name="interactions"),
]
