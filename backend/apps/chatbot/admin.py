from django.contrib import admin

from apps.chatbot.models import ChatMessage, ChatSession, QueryHistory


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_name", "bot_personality", "message_count", "is_active", "last_activity_at")
    list_filter = ("bot_personality", "is_active", "channel")
    search_fields = ("user__username", "session_name")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "message_type", "content_type", "intent", "model_used", "created_at")
    list_filter = ("message_type", "content_type", "intent")
    search_fields = ("content",)


@admin.register(QueryHistory)
class QueryHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "query_type", "parsed_intent", "was_successful", "executed_at")
    list_filter = ("query_type", "parsed_intent", "was_successful")
    search_fields = ("query_text",)
