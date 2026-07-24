"""
Views for user notification management.
Allows users to fetch their notifications and mark as read.
"""

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from apps.authentication.notification_models import UserNotification
from apps.authentication.permissions import CanReadData
from apps.authentication.serializers import (
    UserNotificationDetailSerializer,
    UserNotificationListSerializer,
)


class NotificationListView(generics.ListAPIView):
    """
    List user notifications with filtering.
    GET /api/auth/notifications/
    GET /api/auth/notifications/?is_read=false  (unread only)
    GET /api/auth/notifications/?notification_type=cleaning_completed
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserNotificationListSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['is_read', 'notification_type']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return self.request.user.notifications.all().order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        # Add summary stats
        user_notifs = self.get_queryset()
        response.data = {
            'unread_count': user_notifs.filter(is_read=False).count(),
            'total_count': user_notifs.count(),
            'notifications': response.data,
        }
        return response


class NotificationDetailView(APIView):
    """Get single notification or mark as read"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, notification_id):
        """GET single notification"""
        try:
            notification = UserNotification.objects.get(
                id=notification_id,
                user=request.user
            )
        except UserNotification.DoesNotExist:
            return Response(
                {'error': 'Notification not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(UserNotificationDetailSerializer(notification).data)
    
    def patch(self, request, notification_id):
        """PATCH to mark as read"""
        try:
            notification = UserNotification.objects.get(
                id=notification_id,
                user=request.user
            )
        except UserNotification.DoesNotExist:
            return Response(
                {'error': 'Notification not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        from apps.authentication.notification_service import mark_notification_as_read
        mark_notification_as_read(notification_id)
        
        return Response({
            'message': 'Notification marked as read',
            'is_read': True,
        })


class NotificationMarkAllReadView(APIView):
    """Mark all unread notifications as read"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """POST to mark all as read"""
        from django.utils import timezone
        
        count = request.user.notifications.filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        
        return Response({
            'message': f'Marked {count} notification(s) as read',
            'count': count,
        })
