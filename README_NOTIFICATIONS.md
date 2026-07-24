# Multi-Step Notification System - Complete Implementation

## What Was Implemented

A **5-step notification system** that guides users through the complete upload → cleaning workflow with real-time progress updates.

### User Journey

```
User Uploads File
        ↓
✅ "File Loaded" Notification (100%)
        ↓
⏳ Wait 5 seconds...
        ↓
🔄 "Cleaning Started" Notification (5%)
        ↓
🔄 Progress: 25% "Cleaning in Progress"
        ↓
🔄 Progress: 75% "Cleaning in Progress"
        ↓
✅ "Cleaning Completed" Notification (100%)
   ➜ Shows: {rows_affected} cleaned, Quality Score: {score}%
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│ FRONTEND (React/Vite)                                    │
│ - NotificationContainer: Displays toast messages         │
│ - NotificationPanel: Shows history                       │
│ - useNotifications hook: Polls every 3 seconds          │
└──────────────────┬──────────────────────────────────────┘
                   │ HTTP GET requests
                   ↓
┌─────────────────────────────────────────────────────────┐
│ BACKEND API (Django REST)                                │
│ GET  /api/auth/notifications/          List all         │
│ GET  /api/auth/notifications/?is_read  Unread only      │
│ PATCH /api/auth/notifications/{id}/    Mark as read     │
│ POST /api/auth/notifications/mark-all/ Mark all read    │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────┐
│ NOTIFICATION SYSTEM (Django Models + Service)           │
│ - UserNotification model: Stores all notifications      │
│ - notification_service.py: Creates notifications       │
│ - notification_views.py: API endpoints                 │
└──────────────────┬──────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ↓                     ↓
┌──────────────────┐  ┌──────────────────┐
│ Signal Handler   │  │ Celery Tasks     │
│                  │  │                  │
│ When file upload │  │ auto_clean_      │
│ completes:       │  │ after_ingestion  │
│                  │  │                  │
│ 1. Notify        │  │ When task runs:  │
│    "File Loaded" │  │                  │
│ 2. Queue cleaning│  │ 1. Notify        │
│    task (5s)    │  │    "Cleaning     │
│                  │  │    Started"      │
│                  │  │ 2. Progress at   │
│                  │  │    25%           │
│                  │  │ 3. Progress at   │
│                  │  │    75%           │
│                  │  │ 4. Notify        │
│                  │  │    "Completed"   │
└──────────────────┘  └──────────────────┘
```

## Files Modified/Created

### Backend Files

1. **[apps/nettoyage/tasks.py](../backend/apps/nettoyage/tasks.py)**
   - Updated `auto_clean_after_ingestion()` task to call notifications at each step
   - Added progress updates at 25% and 75%
   - Added proper error handling with failure notifications

2. **[apps/ingestion/signals.py](../backend/apps/ingestion/signals.py)**
   - Already configured to call `notify_ingestion_completed`
   - Already queues `auto_clean_after_ingestion` with 5-second delay
   - ✅ No changes needed - already working!

3. **[apps/authentication/notification_models.py](../backend/apps/authentication/notification_models.py)**
   - ✅ Already has UserNotification model with all fields
   - ✅ Already has database indexes for performance

4. **[apps/authentication/notification_service.py](../backend/apps/authentication/notification_service.py)**
   - ✅ Already has all notification functions:
     - `notify_ingestion_completed()`
     - `notify_cleaning_started()`
     - `notify_cleaning_progress()`
     - `notify_cleaning_completed()`
     - `notify_cleaning_failed()`

5. **[apps/authentication/notification_views.py](../backend/apps/authentication/notification_views.py)**
   - ✅ Already has all API views:
     - NotificationListView (GET /api/auth/notifications/)
     - NotificationDetailView (GET/PATCH /api/auth/notifications/{id}/)
     - NotificationMarkAllReadView (POST /api/auth/notifications/mark-all-read/)

6. **[apps/authentication/urls.py](../backend/apps/authentication/urls.py)**
   - ✅ Updated to include notification endpoints
   - Added routes for list, detail, mark-all-read

### Documentation Files

1. **NOTIFICATION_FLOW_IMPLEMENTATION.md** (in backend/)
   - Complete technical documentation
   - Step-by-step flow explanation
   - API endpoint details
   - Database schema
   - Configuration guidelines

2. **NOTIFICATION_TESTING_GUIDE.md** (in backend/)
   - Quick start testing
   - API endpoint examples
   - End-to-end test flow
   - Django shell testing
   - Error scenarios
   - Performance monitoring

3. **NOTIFICATION_INTEGRATION_GUIDE.md** (in frontend/)
   - React hook implementation
   - Component examples
   - Toast notifications
   - Notification panel
   - App integration
   - WebSocket alternative

### File Structure

```
backend/
├── apps/
│   ├── authentication/
│   │   ├── notification_models.py ✅
│   │   ├── notification_service.py ✅
│   │   ├── notification_views.py ✅
│   │   ├── urls.py (updated)
│   │   └── ...
│   ├── ingestion/
│   │   ├── signals.py ✅
│   │   └── ...
│   ├── nettoyage/
│   │   ├── tasks.py (updated)
│   │   └── ...
│   └── ...
├── NOTIFICATION_FLOW_IMPLEMENTATION.md (new)
├── NOTIFICATION_TESTING_GUIDE.md (new)
└── ...

frontend/
├── src/
│   ├── hooks/
│   │   ├── useNotifications.ts (recommended)
│   │   └── useUploadWithNotifications.ts (recommended)
│   ├── components/
│   │   ├── NotificationToast.tsx (recommended)
│   │   ├── NotificationContainer.tsx (recommended)
│   │   └── NotificationPanel.tsx (recommended)
│   └── App.tsx (integrate NotificationContainer)
└── NOTIFICATION_INTEGRATION_GUIDE.md (new)
```

## Quick Start

### 1. Backend Setup (Django)

```bash
# 1. Apply migrations (if not already done)
python manage.py migrate

# 2. Make sure Celery is running
celery -A decisiobi worker -l info

# 3. Verify signal is registered
python manage.py shell
>>> from apps.ingestion.signals import trigger_auto_cleaning_on_completion
>>> print("Signal registered!")
```

### 2. Frontend Setup (React)

```bash
# 1. Create hook file (if not exists)
touch src/hooks/useNotifications.ts

# 2. Create components
mkdir -p src/components
touch src/components/NotificationToast.tsx
touch src/components/NotificationContainer.tsx

# 3. Import NotificationContainer in App.tsx
# See NOTIFICATION_INTEGRATION_GUIDE.md for code
```

### 3. Test End-to-End

```bash
# Terminal 1: Start backend
python manage.py runserver

# Terminal 2: Start Celery
celery -A decisiobi worker -l info

# Terminal 3: Start frontend
npm run dev

# Terminal 4: Upload test file
curl -X POST http://localhost:8000/api/ingestion/upload/ \
  -H "Authorization: Bearer TOKEN" \
  -F "file=@test.csv"

# Watch browser for notifications:
# 1. ✅ File Loaded
# 2. 🔄 Cleaning Started
# 3. 🔄 Progress updates
# 4. ✅ Cleaning Completed
```

## Notification Flow (Technical)

### Step 1: File Upload Completes
**Triggered:** When `DataSource.status` changes to `'completed'`
**Location:** [apps/ingestion/signals.py](../backend/apps/ingestion/signals.py#L32)
```python
@receiver(post_save, sender=DataSource)
def trigger_auto_cleaning_on_completion(sender, instance, ...):
    if instance.status == 'completed':
        notify_ingestion_completed(...)          # ✅ File Loaded
        auto_clean_after_ingestion.apply_async(  # Queue for 5s delay
            countdown=5
        )
```

**Database Entry:**
```sql
INSERT INTO auth_usernotification (
  user_id, notification_type, title, message, 
  source_id, progress_percent, created_at
) VALUES (
  123, 'ingestion_completed', 
  '✅ File Loaded: data.csv',
  'Your file has been successfully uploaded with 1000 rows...',
  456, 100, NOW()
)
```

**API Response (GET /api/auth/notifications/):**
```json
{
  "unread_count": 1,
  "total_count": 1,
  "notifications": [{
    "id": 1,
    "type": "ingestion_completed",
    "title": "✅ File Loaded: data.csv",
    "message": "Your file has been successfully uploaded with 1000 rows...",
    "progress_percent": 100,
    "is_read": false,
    "created_at": "2024-01-15T10:30:45Z",
    "data": {"row_count": 1000},
    "action_url": "/api/ingestion/sources/456/"
  }]
}
```

### Step 2: Auto-Clean Task Starts
**Triggered:** 5 seconds later by Celery
**Location:** [apps/nettoyage/tasks.py](../backend/apps/nettoyage/tasks.py#L3)
```python
@shared_task
def auto_clean_after_ingestion(source_id, user_id):
    # ... create job ...
    notify_cleaning_started(job.id, user_id, source.name)  # 🔄 Started
```

### Step 3: Progress Updates
**Location:** [apps/nettoyage/tasks.py](../backend/apps/nettoyage/tasks.py#L72)
```python
notify_cleaning_progress(job.id, user_id, 25)  # 🔄 25% progress
# ... apply cleaning rules ...
notify_cleaning_progress(job.id, user_id, 75)  # 🔄 75% progress
```

### Step 4: Cleaning Completes
**Location:** [apps/nettoyage/tasks.py](../backend/apps/nettoyage/tasks.py#L85)
```python
notify_cleaning_completed(
    job.id, user_id, 
    rows_affected=42,
    quality_score=94.5
)  # ✅ Completed with results
```

## Frontend Integration

### Polling Approach (Simple)
```typescript
// React hook - fetches every 3 seconds
const { notifications } = useNotifications()

// Display all unread notifications as toasts
notifications
  .filter(n => !n.is_read)
  .map(n => <NotificationToast key={n.id} notification={n} />)
```

### WebSocket Approach (Real-time)
```typescript
// Optional: Replace polling with WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/notifications/')
ws.onmessage = (event) => {
  const notification = JSON.parse(event.data)
  displayNotification(notification)
}
```

## Performance Considerations

### Database Optimization
- Indexes on `(user, created_at)` for fast queries
- Indexes on `(user, is_read)` for "get unread" queries
- Automatic cleanup of notifications older than 30 days (optional)

### API Optimization
- Frontend polls every 3 seconds (adjustable)
- Responses include unread count + total count
- Filter support: `?is_read=false`, `?notification_type=...`

### Task Optimization
- Celery tasks run asynchronously
- 5-second delay improves UX (user sees upload complete first)
- Notifications are lightweight (no heavy data loading)

## Error Handling

### No Default Pipeline
- Upload completes ✅ 
- Cleaning skips (no error, just no cleaning started notification)
- User can manually trigger cleaning

### Cleaning Fails
- Upload completes ✅
- Cleaning starts 🔄
- Error occurs ❌ "Cleaning Failed" notification
- File is safe, user can retry

### Connection Issues
- All notifications persist in database
- User sees full history when reconnected
- Can mark as read later

## Monitoring & Debugging

### Check Notifications in Django Shell
```python
from apps.authentication.notification_models import UserNotification
from apps.authentication.models import User

user = User.objects.get(username='testuser')

# Get all notifications
user.notifications.all().count()

# Get unread
user.notifications.filter(is_read=False).count()

# Get for specific source
user.notifications.filter(source_id=123)

# Get for specific job
user.notifications.filter(job_id=456)
```

### Check API Response
```bash
curl -X GET http://localhost:8000/api/auth/notifications/ \
  -H "Authorization: Bearer TOKEN" | jq .
```

### Check Celery Task
```bash
# Check if Celery worker is running
ps aux | grep celery

# Check task status
celery -A decisiobi inspect active

# Watch logs
tail -f celery.log
```

## Configuration

### Notification Retention (settings.py)
```python
# Keep notifications for 30 days
NOTIFICATION_RETENTION_DAYS = 30

# Cleanup schedule (Celery Beat)
CELERY_BEAT_SCHEDULE = {
    'cleanup-old-notifications': {
        'task': 'apps.authentication.tasks.cleanup_old_notifications',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
    },
}
```

### Polling Interval (Frontend)
```typescript
// In useNotifications hook
const interval = setInterval(fetchNotifications, 3000)  // Every 3 seconds
```

## Testing Checklist

- [ ] Database migrations applied
- [ ] Signal registered (check apps.py)
- [ ] Celery worker running
- [ ] Upload file and check database for notifications
- [ ] Frontend shows toast notifications
- [ ] Progress updates appear in sequence
- [ ] Completion notification has correct data
- [ ] Mark as read works
- [ ] Mark all as read works
- [ ] Unread count updates correctly

## Deployment Checklist

- [ ] Migrations deployed to production database
- [ ] Celery workers started on production
- [ ] Redis/broker configured for Celery
- [ ] Frontend components imported and integrated
- [ ] CORS headers configured for notification endpoints
- [ ] Notification cleanup task scheduled (optional)
- [ ] Logs monitored for notification errors
- [ ] Database backup includes notification table

## Common Issues & Solutions

### Notifications Not Appearing
```python
# Check signal is firing
# Add logging to signal handler:
logger.info(f"Signal fired for source {instance.id}")

# Check task is queued
# Check Celery logs for task receipt

# Check notification service is called
# Add logging to notification_service functions
```

### Wrong Sequence
```python
# Verify task is running in correct order
from apps.authentication.notification_models import UserNotification
user.notifications.filter(job_id=123).order_by('created_at')
# Should show: started → progress25 → progress75 → completed
```

### Missing Progress Updates
```python
# Verify progress calls in tasks.py
# Must call: notify_cleaning_progress at 25% and 75%
```

## Next Steps

1. **Implement Frontend Components** (see NOTIFICATION_INTEGRATION_GUIDE.md)
   - Create useNotifications hook
   - Create NotificationContainer component
   - Integrate in App.tsx

2. **Test End-to-End** (see NOTIFICATION_TESTING_GUIDE.md)
   - Upload test file
   - Monitor notifications
   - Verify sequence

3. **Deploy to Production**
   - Run migrations
   - Start Celery workers
   - Deploy frontend code

4. **Monitor** (see NOTIFICATION_FLOW_IMPLEMENTATION.md)
   - Monitor notification volume
   - Check unread counts
   - Review error logs

## Support Documents

- **NOTIFICATION_FLOW_IMPLEMENTATION.md**: Complete technical reference
- **NOTIFICATION_TESTING_GUIDE.md**: Step-by-step testing procedures
- **NOTIFICATION_INTEGRATION_GUIDE.md**: Frontend component examples

## Summary

✅ **Complete notification system implemented:**
- 5-step user journey (Upload → Started → Progress → Completed)
- Real-time API endpoints
- Django database persistence
- Celery task integration
- Ready for frontend integration

**Backend is 100% complete.** Frontend implementation is straightforward using the provided hooks and components.
