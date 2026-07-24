from django.urls import path

from apps.chatbot.views import (
    ChatSessionDetailView,
    ChatSessionListCreateView,
    ChatSessionMessageListCreateView,
)


urlpatterns = [
    path('sessions/', ChatSessionListCreateView.as_view(), name='chat_session_list_create'),
    path('sessions/<int:session_id>/', ChatSessionDetailView.as_view(), name='chat_session_detail'),
    path('sessions/<int:session_id>/messages/', ChatSessionMessageListCreateView.as_view(), name='chat_session_messages'),
]
