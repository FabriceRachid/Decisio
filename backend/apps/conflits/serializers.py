"""
M3: Conflict Detection & Resolution Serializers
API representations for conflict data and resolution workflows.
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from apps.conflits.models import (
    ConflictType, Conflict, ConflictResolution, ActivityLog, ScheduledJob
)


class ConflictTypeSerializer(serializers.ModelSerializer):
    """Conflict category definition"""
    
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    
    class Meta:
        model = ConflictType
        fields = [
            'id', 'name', 'code', 'description', 'severity', 'severity_display',
            'auto_resolve', 'resolution_strategy', 'icon', 'color_code', 
            'documentation_url', 'created_at'
        ]
        read_only_fields = ['created_at']


class ConflictResolutionSerializer(serializers.ModelSerializer):
    """Individual resolution decision"""
    
    resolved_by_username = serializers.CharField(
        source='resolved_by.username', read_only=True
    )
    reviewed_by_username = serializers.CharField(
        source='reviewed_by.username', read_only=True, allow_null=True
    )
    approved_by_username = serializers.CharField(
        source='approved_by.username', read_only=True, allow_null=True
    )
    method_display = serializers.CharField(
        source='get_resolution_method_display', read_only=True
    )
    
    class Meta:
        model = ConflictResolution
        fields = [
            'id', 'conflict', 'resolution_method', 'method_display',
            'chosen_value', 'alternative_values', 'resolution_notes',
            'confidence_score', 'is_reversible', 'rollback_data',
            'resolved_by', 'resolved_by_username', 'resolved_at',
            'reviewed_by', 'reviewed_by_username', 'reviewed_at',
            'approval_required', 'approved_by', 'approved_by_username', 'approved_at'
        ]
        read_only_fields = [
            'resolved_by', 'resolved_at', 'reviewed_by', 'reviewed_at',
            'approved_by', 'approved_at'
        ]


class ConflictDetailSerializer(serializers.ModelSerializer):
    """Detailed conflict information with resolutions"""
    
    conflict_type_name = serializers.CharField(
        source='conflict_type.name', read_only=True
    )
    conflict_type_code = serializers.CharField(
        source='conflict_type.code', read_only=True
    )
    conflict_type_obj = ConflictTypeSerializer(
        source='conflict_type', read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )
    assigned_to_username = serializers.CharField(
        source='assigned_to.username', read_only=True, allow_null=True
    )
    acknowledged_by_username = serializers.CharField(
        source='acknowledged_by.username', read_only=True, allow_null=True
    )
    resolutions = ConflictResolutionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Conflict
        fields = [
            'id', 'data_source', 'conflict_type', 'conflict_type_name',
            'conflict_type_code', 'conflict_type_obj', 'affected_table',
            'affected_columns', 'affected_row_ids', 'conflict_details',
            'description', 'status', 'status_display', 'priority',
            'detected_by', 'detected_at', 'acknowledged_by',
            'acknowledged_by_username', 'acknowledged_at',
            'assigned_to', 'assigned_to_username', 'due_date',
            'parent_conflict', 'child_conflicts', 'impact_score',
            'estimated_resolution_time', 'resolved_at',
            'resolution_summary', 'resolutions'
        ]
        read_only_fields = [
            'detected_at', 'acknowledged_at', 'resolved_at', 'resolutions'
        ]


class ConflictListSerializer(serializers.ModelSerializer):
    """Lightweight conflict list view"""
    
    conflict_type_name = serializers.CharField(
        source='conflict_type.name', read_only=True
    )
    conflict_type_code = serializers.CharField(
        source='conflict_type.code', read_only=True
    )
    conflict_type_severity = serializers.CharField(
        source='conflict_type.severity', read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )
    assigned_to_username = serializers.CharField(
        source='assigned_to.username', read_only=True, allow_null=True
    )
    source_name = serializers.CharField(
        source='data_source.name', read_only=True
    )
    resolution_count = serializers.SerializerMethodField()
    
    def get_resolution_count(self, obj):
        return obj.resolutions.count()
    
    class Meta:
        model = Conflict
        fields = [
            'id', 'data_source', 'source_name', 'conflict_type',
            'conflict_type_name', 'conflict_type_code',
            'conflict_type_severity', 'description', 'status',
            'status_display', 'priority', 'detected_at',
            'assigned_to', 'assigned_to_username', 'due_date',
            'impact_score', 'resolution_count'
        ]
        read_only_fields = [
            'data_source', 'conflict_type', 'detected_at'
        ]


class ConflictResolutionGuidanceSerializer(serializers.Serializer):
    """Guided workflow for resolving a conflict"""
    
    conflict_id = serializers.IntegerField()
    conflict_type = serializers.CharField()
    affected_fields = serializers.ListField(child=serializers.CharField())
    affected_rows = serializers.IntegerField()
    guidance = serializers.CharField()
    recommended_strategy = serializers.CharField()
    alternative_strategies = serializers.ListField(child=serializers.CharField())
    impact_analysis = serializers.JSONField()
    steps = serializers.ListField(child=serializers.JSONField())
    estimated_effort = serializers.CharField()
    risk_level = serializers.CharField()


class ConflictResolutionRequestSerializer(serializers.Serializer):
    """Request to resolve a conflict"""
    
    RESOLUTION_METHOD_CHOICES = [
        ('manual_override', 'Manual Override'),
        ('auto_merge', 'Auto Merge'),
        ('default_value', 'Use Default Value'),
        ('user_selected', 'User Selected'),
        ('majority_vote', 'Majority Vote'),
        ('latest_value', 'Latest Value'),
        ('discard', 'Discard Invalid Data'),
    ]
    
    resolution_method = serializers.ChoiceField(choices=RESOLUTION_METHOD_CHOICES)
    chosen_value = serializers.JSONField(required=False, allow_null=True)
    resolution_notes = serializers.CharField(required=False, allow_blank=True)
    requires_approval = serializers.BooleanField(default=False)


class ConflictBulkActionSerializer(serializers.Serializer):
    """Bulk action on multiple conflicts"""
    
    conflict_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    action = serializers.ChoiceField(
        choices=[
            'assign_to_user',
            'change_priority',
            'change_status',
            'add_to_group'
        ]
    )
    assigned_to_id = serializers.IntegerField(required=False, allow_null=True)
    new_priority = serializers.IntegerField(
        required=False, min_value=1, max_value=10
    )
    new_status = serializers.ChoiceField(
        required=False,
        choices=['detected', 'investigating', 'resolving', 'resolved', 'ignored']
    )
    group_name = serializers.CharField(required=False, allow_blank=True)

    def validate_conflict_ids(self, value):
        if len(value) > 100:
            raise serializers.ValidationError("Bulk actions are limited to 100 conflicts per request")
        return list(dict.fromkeys(value))

    def validate(self, attrs):
        action = attrs['action']

        if action == 'assign_to_user' and not attrs.get('assigned_to_id'):
            raise serializers.ValidationError({'assigned_to_id': 'assigned_to_id is required for assign_to_user'})
        if action == 'change_priority' and attrs.get('new_priority') is None:
            raise serializers.ValidationError({'new_priority': 'new_priority is required for change_priority'})
        if action == 'change_status' and not attrs.get('new_status'):
            raise serializers.ValidationError({'new_status': 'new_status is required for change_status'})
        if action == 'add_to_group' and not attrs.get('group_name'):
            raise serializers.ValidationError({'group_name': 'group_name is required for add_to_group'})

        return attrs


class ActivityLogSerializer(serializers.ModelSerializer):
    """Audit trail entry"""
    
    user_email = serializers.CharField(read_only=True)
    action_type_display = serializers.CharField(
        source='get_action_type_display', read_only=True
    )
    
    class Meta:
        model = ActivityLog
        fields = [
            'id', 'user', 'user_email', 'user_role', 'action_type',
            'action_type_display', 'resource_type', 'resource_id',
            'resource_name', 'action_details', 'ip_address',
            'response_time_ms', 'status_code', 'risk_score',
            'flagged_for_review', 'created_at'
        ]
        read_only_fields = [
            'user', 'user_email', 'ip_address', 'response_time_ms',
            'status_code', 'created_at'
        ]


class ConflictDashboardStatSerializer(serializers.Serializer):
    """Dashboard statistics for conflicts"""
    
    total_conflicts = serializers.IntegerField()
    by_status = serializers.DictField()
    by_severity = serializers.DictField()
    by_type = serializers.DictField()
    critical_count = serializers.IntegerField()
    overdue_count = serializers.IntegerField()
    assigned_to_current_user = serializers.IntegerField()
    avg_resolution_time_minutes = serializers.FloatField()
    resolution_rate_percent = serializers.FloatField()


# ─── Reporting ───────────────────────────────────────────────

class ReportConfigSerializer(serializers.ModelSerializer):
    """Scheduled report configuration (wraps ScheduledJob)."""

    schedule_display = serializers.SerializerMethodField()
    last_run_display = serializers.SerializerMethodField()

    class Meta:
        model = ScheduledJob
        fields = [
            "id", "job_name", "job_type", "schedule_type",
            "interval_minutes", "cron_expression", "next_run_at",
            "last_run_at", "last_run_status", "last_run_display",
            "is_active", "job_parameters", "notification_recipients",
            "schedule_display", "created_at",
        ]
        read_only_fields = [
            "id", "job_type", "last_run_at", "last_run_status",
            "next_run_at", "last_run_display", "schedule_display",
            "created_at",
        ]

    def get_schedule_display(self, obj):
        if obj.schedule_type == "interval" and obj.interval_minutes:
            if obj.interval_minutes < 60:
                return f"Toutes les {obj.interval_minutes} min"
            hours = obj.interval_minutes // 60
            return f"Toutes les {hours}h" if hours == 1 else f"Toutes les {hours}h"
        if obj.schedule_type == "cron" and obj.cron_expression:
            return f"Cron: {obj.cron_expression}"
        if obj.schedule_type == "once":
            return "Une fois"
        return "—"

    def get_last_run_display(self, obj):
        if not obj.last_run_at:
            return "Jamais"
        return obj.last_run_at.strftime("%d/%m/%Y %H:%M")


class TriggerReportSerializer(serializers.Serializer):
    """Trigger immediate report generation."""
    config_id = serializers.IntegerField()
