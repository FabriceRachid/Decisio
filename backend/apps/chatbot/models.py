from django.db import models
from django.contrib.auth.models import User


class ChatSession(models.Model):
    """
    Chat conversation sessions.
    Tracks multi-turn conversations with context and state.
    """
    CHANNEL_CHOICES = [
        ('web', 'Web Interface'),
        ('mobile', 'Mobile App'),
        ('slack', 'Slack'),
        ('teams', 'Microsoft Teams'),
    ]
    
    BOT_PERSONALITY_CHOICES = [
        ('professional', 'Professional'),
        ('friendly', 'Friendly'),
        ('concise', 'Concise'),
        ('detailed', 'Detailed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session_token = models.CharField(max_length=100, unique=True)
    session_name = models.CharField(max_length=200, blank=True, null=True, help_text="User-friendly name")
    
    # Context
    context = models.JSONField(default=dict, blank=True, help_text="Conversation state, variables")
    active_data_sources = models.JSONField(default=list, blank=True)
    active_kpis = models.JSONField(default=list, blank=True)
    
    # Bot configuration
    bot_personality = models.CharField(max_length=50, choices=BOT_PERSONALITY_CHOICES, default='professional')
    language_preference = models.CharField(max_length=10, default='en')
    
    # State
    is_active = models.BooleanField(default=True)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, blank=True, null=True)
    referral_source = models.CharField(max_length=100, blank=True, null=True)
    
    # Analytics
    message_count = models.IntegerField(default=0)
    satisfaction_rating = models.IntegerField(null=True, blank=True, help_text="1-5 stars")
    resolution_achieved = models.BooleanField(default=False, help_text="Did bot help solve problem?")
    tags = models.JSONField(default=list, blank=True, help_text="Conversation topics")
    
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Chat Session {self.session_token[:8]}... - {self.user.username}"
    
    class Meta:
        db_table = 'chatbot_chatsession'
        verbose_name = 'Chat Session'
        verbose_name_plural = 'Chat Sessions'
        ordering = ['-last_activity_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_token']),
        ]


class ChatMessage(models.Model):
    """
    Individual chat messages in conversations.
    Stores user queries, bot responses, and NLP analysis.
    """
    MESSAGE_TYPE_CHOICES = [
        ('user', 'User Message'),
        ('bot', 'Bot Response'),
        ('system', 'System Message'),
    ]
    
    CONTENT_TYPE_CHOICES = [
        ('text', 'Text'),
        ('question', 'Question'),
        ('chart', 'Chart'),
        ('table', 'Table'),
        ('insight', 'Insight'),
        ('action', 'Action Button'),
    ]
    
    SENTIMENT_CHOICES = [
        ('positive', 'Positive'),
        ('neutral', 'Neutral'),
        ('negative', 'Negative'),
        ('frustrated', 'Frustrated'),
    ]
    
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES, blank=True, null=True)
    
    # Text
    content = models.TextField()
    content_html = models.TextField(blank=True, null=True)
    markdown_content = models.TextField(blank=True, null=True)
    
    # NLP analysis (for user messages)
    intent = models.CharField(max_length=100, blank=True, null=True, help_text="QUERY_KPI, ASK_DATA, etc.")
    entities = models.JSONField(default=dict, blank=True)
    sentiment = models.CharField(max_length=20, choices=SENTIMENT_CHOICES, blank=True, null=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Bot response metadata
    response_time_ms = models.IntegerField(null=True, blank=True)
    model_used = models.CharField(max_length=100, blank=True, null=True)
    fallback_used = models.BooleanField(default=False, help_text="Did NLP fail?")
    
    # Attached data
    attached_chart = models.JSONField(default=dict, blank=True)
    attached_data = models.JSONField(default=dict, blank=True)
    suggested_questions = models.JSONField(default=list, blank=True)
    
    # Feedback
    was_helpful = models.BooleanField(null=True, blank=True)
    feedback_text = models.TextField(blank=True, null=True)
    
    # Advanced features
    thread_parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.get_message_type_display()} - {self.content[:50]}"
    
    class Meta:
        db_table = 'chatbot_chatmessage'
        verbose_name = 'Chat Message'
        verbose_name_plural = 'Chat Messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['message_type']),
            models.Index(fields=['intent']),
        ]


class QueryHistory(models.Model):
    """
    Historical query tracking for analytics and ML training.
    Records what users asked and how the system responded.
    """
    QUERY_TYPE_CHOICES = [
        ('data_query', 'Data Query'),
        ('kpi_query', 'KPI Query'),
        ('insight_request', 'Insight Request'),
        ('how_to', 'How To Question'),
        ('bug_report', 'Bug Report'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    session = models.ForeignKey(ChatSession, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Query
    query_text = models.TextField()
    query_type = models.CharField(max_length=50, choices=QUERY_TYPE_CHOICES)
    
    # NLP results
    parsed_intent = models.CharField(max_length=100, blank=True, null=True)
    extracted_entities = models.JSONField(default=dict, blank=True)
    nlp_confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Execution
    generated_sql = models.TextField(blank=True, null=True)
    execution_plan = models.JSONField(default=dict, blank=True)
    execution_time_ms = models.IntegerField(null=True, blank=True)
    rows_returned = models.IntegerField(null=True, blank=True)
    
    # Result
    result_summary = models.TextField(blank=True, null=True)
    full_result = models.JSONField(blank=True, null=True)
    result_cached = models.BooleanField(default=False)
    cache_key = models.CharField(max_length=100, blank=True, null=True)
    
    # Quality
    was_successful = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, null=True)
    user_satisfaction = models.IntegerField(null=True, blank=True, help_text="1-5 rating")
    user_feedback = models.TextField(blank=True, null=True)
    
    # Learning
    is_training_example = models.BooleanField(default=False, help_text="Use for ML training?")
    improved_response = models.TextField(blank=True, null=True, help_text="Human-edited better response")
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_queries')
    
    # Advanced features
    similar_queries = models.JSONField(default=list, blank=True, help_text="Links to paraphrases")
    complexity_score = models.IntegerField(null=True, blank=True, help_text="How complex was this query?")
    requires_human = models.BooleanField(default=False, help_text="Flag for human review?")
    
    executed_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.query_type} - {self.query_text[:50]}"
    
    class Meta:
        db_table = 'chatbot_queryhistory'
        verbose_name = 'Query History'
        verbose_name_plural = 'Query Histories'
        ordering = ['-executed_at']
        indexes = [
            models.Index(fields=['user', 'executed_at']),
            models.Index(fields=['query_type']),
            models.Index(fields=['parsed_intent']),
        ]
