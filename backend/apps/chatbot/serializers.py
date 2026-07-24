from rest_framework import serializers

from apps.chatbot.models import ChatMessage, ChatSession


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = [
            'id',
            'message_type',
            'content_type',
            'content',
            'intent',
            'entities',
            'sentiment',
            'confidence',
            'response_time_ms',
            'model_used',
            'fallback_used',
            'attached_chart',
            'attached_data',
            'suggested_questions',
            'was_helpful',
            'feedback_text',
            'created_at',
        ]
        read_only_fields = fields


class ChatSessionListSerializer(serializers.ModelSerializer):
    last_message_preview = serializers.SerializerMethodField()

    class Meta:
        model = ChatSession
        fields = [
            'id',
            'session_token',
            'session_name',
            'bot_personality',
            'language_preference',
            'is_active',
            'message_count',
            'resolution_achieved',
            'tags',
            'started_at',
            'last_activity_at',
            'last_message_preview',
        ]
        read_only_fields = fields

    def get_last_message_preview(self, obj):
        last_message = obj.messages.order_by('-created_at').first()
        if not last_message:
            return None
        return {
            'message_type': last_message.message_type,
            'content': last_message.content[:180],
            'created_at': last_message.created_at,
        }


class ChatSessionDetailSerializer(ChatSessionListSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta(ChatSessionListSerializer.Meta):
        fields = ChatSessionListSerializer.Meta.fields + [
            'context',
            'active_data_sources',
            'active_kpis',
            'satisfaction_rating',
            'messages',
        ]


class ChatSessionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = [
            'session_name',
            'bot_personality',
            'language_preference',
            'channel',
            'referral_source',
        ]


class ChatMessageCreateSerializer(serializers.Serializer):
    content = serializers.CharField(max_length=10000)
    persist_analysis = serializers.BooleanField(required=False, default=True)
    model = serializers.CharField(required=False, allow_blank=True, max_length=100)
    context = serializers.JSONField(required=False, default=dict)
