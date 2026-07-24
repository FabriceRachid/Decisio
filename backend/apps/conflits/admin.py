from django.contrib import admin
from django.utils.html import format_html
from apps.conflits.models import (
    ConflictType, Conflict, ConflictResolution, ActivityLog, SystemConfig
)


@admin.register(ConflictType)
class ConflictTypeAdmin(admin.ModelAdmin):
    """Admin for conflict type definitions"""
    
    list_display = ['name', 'code', 'severity_badge', 'auto_resolve', 'resolution_strategy', 'created_at']
    list_filter = ['severity', 'auto_resolve', 'created_at']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'code', 'description', 'severity')
        }),
        ('Resolution Strategy', {
            'fields': ('auto_resolve', 'resolution_strategy')
        }),
        ('UI Configuration', {
            'fields': ('icon', 'color_code')
        }),
        ('Documentation', {
            'fields': ('documentation_url',)
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def severity_badge(self, obj):
        """Display severity as colored badge"""
        colors = {
            'low': '#28a745',
            'medium': '#ffc107',
            'high': '#fd7e14',
            'critical': '#dc3545'
        }
        color = colors.get(obj.severity, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_severity_display()
        )
    severity_badge.short_description = 'Severity'


@admin.register(Conflict)
class ConflictAdmin(admin.ModelAdmin):
    """Admin for detected conflicts"""
    
    list_display = ['id', 'conflict_type', 'source_name', 'status_badge', 'priority', 'assigned_to_display', 'detected_at']
    list_filter = ['status', 'conflict_type__severity', 'detected_at', 'assigned_to']
    search_fields = ['data_source__name', 'description', 'conflict_type__name']
    readonly_fields = ['detected_at', 'resolved_at']
    date_hierarchy = 'detected_at'
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('data_source', 'conflict_type', 'description', 'status')
        }),
        ('Affected Data', {
            'fields': ('affected_table', 'affected_columns', 'affected_row_ids')
        }),
        ('Conflict Details', {
            'fields': ('conflict_details',)
        }),
        ('Management', {
            'fields': ('priority', 'assigned_to', 'due_date')
        }),
        ('Tracking', {
            'fields': ('acknowledged_by', 'acknowledged_at', 'detected_by')
        }),
        ('Resolution', {
            'fields': ('resolved_at', 'resolution_summary')
        }),
        ('Analysis', {
            'fields': ('impact_score', 'estimated_resolution_time'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('detected_at', 'parent_conflict', 'recurrence_id'),
            'classes': ('collapse',)
        })
    )
    
    def source_name(self, obj):
        return obj.data_source.name
    source_name.short_description = 'Source'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'detected': '#0dcaf0',
            'investigating': '#0d6efd',
            'resolving': '#0d6efd',
            'resolved': '#198754',
            'ignored': '#6c757d'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def assigned_to_display(self, obj):
        return obj.assigned_to.username if obj.assigned_to else '—'
    assigned_to_display.short_description = 'Assigned To'
    
    actions = ['mark_as_resolved', 'mark_as_ignored', 'assign_to_me']
    
    def mark_as_resolved(self, request, queryset):
        updated = queryset.update(status='resolved', resolved_at=None)
        self.message_user(request, f'{updated} conflicts marked as resolved')
    mark_as_resolved.short_description = 'Mark selected as resolved'
    
    def mark_as_ignored(self, request, queryset):
        updated = queryset.update(status='ignored')
        self.message_user(request, f'{updated} conflicts marked as ignored')
    mark_as_ignored.short_description = 'Mark selected as ignored'
    
    def assign_to_me(self, request, queryset):
        updated = queryset.update(assigned_to=request.user)
        self.message_user(request, f'{updated} conflicts assigned to you')
    assign_to_me.short_description = 'Assign selected to me'


@admin.register(ConflictResolution)
class ConflictResolutionAdmin(admin.ModelAdmin):
    """Admin for conflict resolutions"""
    
    list_display = ['id', 'conflict', 'resolution_method', 'confidence_score', 'resolved_by', 'approval_status', 'resolved_at']
    list_filter = ['resolution_method', 'approval_required', 'resolved_at']
    search_fields = ['conflict__description', 'resolved_by__username']
    readonly_fields = ['resolved_at', 'reviewed_at', 'approved_at']
    date_hierarchy = 'resolved_at'
    
    fieldsets = (
        ('Conflict', {
            'fields': ('conflict',)
        }),
        ('Resolution', {
            'fields': ('resolution_method', 'chosen_value', 'alternative_values', 'resolution_notes')
        }),
        ('Quality', {
            'fields': ('confidence_score', 'is_reversible', 'rollback_data')
        }),
        ('Review & Approval', {
            'fields': ('approval_required', 'reviewed_by', 'reviewed_at', 'approved_by', 'approved_at')
        }),
        ('Metadata', {
            'fields': ('resolved_by', 'resolved_at'),
            'classes': ('collapse',)
        })
    )
    
    def approval_status(self, obj):
        if not obj.approval_required:
            return format_html(
                '<span style="background-color: #198754; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px;">Not Required</span>'
            )
        elif obj.approved_at:
            return format_html(
                '<span style="background-color: #198754; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px;">Approved</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #ffc107; color: black; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px;">Pending</span>'
            )
    approval_status.short_description = 'Approval Status'


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """Admin for audit trail"""
    
    list_display = ['id', 'user_email', 'action_type', 'resource_type', 'status_code', 'flagged_badge', 'created_at']
    list_filter = ['action_type', 'resource_type', 'status_code', 'flagged_for_review', 'created_at']
    search_fields = ['user__email', 'resource_name', 'ip_address']
    readonly_fields = ['created_at', 'user', 'user_email', 'ip_address']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('User', {
            'fields': ('user', 'user_email', 'user_role', 'ip_address')
        }),
        ('Action', {
            'fields': ('action_type', 'resource_type', 'resource_id', 'resource_name')
        }),
        ('Details', {
            'fields': ('action_details',)
        }),
        ('Response', {
            'fields': ('status_code', 'response_time_ms')
        }),
        ('Security', {
            'fields': ('risk_score', 'flagged_for_review', 'reviewed_by', 'reviewed_at'),
            'classes': ('collapse',)
        }),
        ('Location', {
            'fields': ('country', 'city'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'session_id'),
            'classes': ('collapse',)
        })
    )
    
    def user_email(self, obj):
        return obj.user.email if obj.user else obj.user_email or 'Anonymous'
    user_email.short_description = 'Email'
    
    def flagged_badge(self, obj):
        if obj.flagged_for_review:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px;">‼️ Flagged</span>'
            )
        return '—'
    flagged_badge.short_description = 'Flagged'
    
    actions = ['mark_as_reviewed']
    
    def mark_as_reviewed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(flagged_for_review=True).update(
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )
        self.message_user(request, f'{updated} activities marked as reviewed')
    mark_as_reviewed.short_description = 'Mark flagged as reviewed'


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    """Admin for system configuration."""
    
    list_display = ['config_key', 'value_type', 'config_value_display', 'category', 'updated_at']
    list_filter = ['value_type', 'category', 'is_editable', 'is_public', 'environment']
    search_fields = ['config_key', 'description']
    readonly_fields = ['changed_at', 'updated_at', 'changed_by']
    
    fieldsets = (
        ('Configuration', {
            'fields': ('config_key', 'config_value', 'value_type')
        }),
        ('Metadata', {
            'fields': ('description', 'category', 'environment')
        }),
        ('Access & Visibility', {
            'fields': ('is_public', 'is_editable')
        }),
        ('Validation', {
            'fields': ('validation_regex', 'allowed_values', 'min_value', 'max_value')
        }),
        ('Change Tracking', {
            'fields': ('changed_by', 'changed_at', 'change_reason', 'previous_value'),
            'classes': ('collapse',)
        }),
        ('Advanced', {
            'fields': ('encrypted', 'requires_restart', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def config_value_display(self, obj):
        """Display config value with truncation."""
        value_str = str(obj.config_value)
        if len(value_str) > 50:
            return value_str[:50] + '...'
        return value_str
    config_value_display.short_description = 'Value'
