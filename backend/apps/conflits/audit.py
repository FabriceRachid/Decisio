"""
Audit trail utilities for DecisioBI.
Provides log_activity() for tracking all user actions across the application.
"""

import logging
import threading
from typing import Any, Dict, Optional

from django.contrib.auth.models import User
from django.utils import timezone

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def _get_client_ip(request) -> Optional[str]:
    if request is None:
        return None
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _get_user_agent(request) -> str:
    if request is None:
        return ''
    return request.META.get('HTTP_USER_AGENT', '')


def log_activity(
    action_type: str,
    resource_type: str,
    resource_id: Any = None,
    resource_name: str = '',
    details: Optional[Dict[str, Any]] = None,
    user: Optional[User] = None,
    request=None,
    status_code: int = 200,
    risk_score: Optional[int] = None,
):
    """
    Log a user activity to ActivityLog.

    Usage:
        log_activity('create', 'Dashboard', dashboard.id, dashboard.name, request=request)
        log_activity('login', 'User', user.id, user.username, request=request)
        log_activity('delete', 'Widget', widget.id, widget.name, request=request, risk_score=30)
    """
    from apps.conflits.models import ActivityLog

    if user is None and request is not None:
        user = getattr(request, 'user', None)

    if user is None or not user.is_authenticated:
        return

    profile = getattr(user, 'profile', None)

    log_entry = ActivityLog(
        user=user,
        user_email=user.email,
        user_role=getattr(profile, 'role', None),
        action_type=action_type,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=str(resource_name)[:500] if resource_name else '',
        action_details=details or {},
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request)[:500],
        status_code=status_code,
        risk_score=risk_score,
    )

    if risk_score and risk_score >= 50:
        log_entry.flagged_for_review = True

    try:
        log_entry.save()
    except Exception as e:
        logger.warning(f"Failed to save activity log: {e}")


def get_client_ip(request) -> Optional[str]:
    return _get_client_ip(request)
