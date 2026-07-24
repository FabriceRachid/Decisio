import logging

from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.authentication.permissions import CanReadData
from apps.chatbot.models import ChatSession
from apps.chatbot.serializers import (
    ChatMessageCreateSerializer,
    ChatMessageSerializer,
    ChatSessionCreateSerializer,
    ChatSessionDetailSerializer,
    ChatSessionListSerializer,
)
from apps.chatbot.services import create_chat_session, process_chat_message
from apps.ia_interpretation.services import KPIInterpretationError

logger = logging.getLogger(__name__)


class ChatSessionListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, CanReadData]
    pagination_class = None

    def get_queryset(self):
        return (
            ChatSession.objects.filter(user=self.request.user)
            .prefetch_related('messages')
            .order_by('-last_activity_at')
        )

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ChatSessionCreateSerializer
        return ChatSessionListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = create_chat_session(user=request.user, **serializer.validated_data)
        return Response(ChatSessionDetailSerializer(session).data, status=status.HTTP_201_CREATED)


class ChatSessionDetailView(generics.RetrieveDestroyAPIView):
    permission_classes = [IsAuthenticated, CanReadData]
    serializer_class = ChatSessionDetailSerializer

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user).prefetch_related('messages')

    def get_object(self):
        return get_object_or_404(self.get_queryset(), id=self.kwargs['session_id'])

    def delete(self, request, *args, **kwargs):
        session = self.get_object()
        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChatSessionMessageListCreateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, CanReadData]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ChatMessageCreateSerializer
        return ChatMessageSerializer

    def get_session(self):
        return get_object_or_404(
            ChatSession.objects.filter(user=self.request.user).prefetch_related('messages'),
            id=self.kwargs['session_id'],
        )

    def get(self, request, *args, **kwargs):
        session = self.get_session()
        return Response(ChatMessageSerializer(session.messages.all(), many=True).data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        session = self.get_session()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = process_chat_message(
                session=session,
                user=request.user,
                content=serializer.validated_data['content'],
                persist_analysis=serializer.validated_data['persist_analysis'],
                model=serializer.validated_data.get('model'),
                context=serializer.validated_data.get('context'),
            )
        except KPIInterpretationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("chatbot message failed")
            return Response(
                {'detail': f"Erreur interne lors du traitement : {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                'session': ChatSessionListSerializer(result['session']).data,
                'user_message': ChatMessageSerializer(result['user_message']).data,
                'bot_message': ChatMessageSerializer(result['bot_message']).data,
                'analysis_id': result['analysis_id'],
            },
            status=status.HTTP_201_CREATED,
        )
