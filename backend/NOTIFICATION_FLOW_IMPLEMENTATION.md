# Multi-Step Notification Flow Implementation

## Overview
This document describes the complete notification system that guides users through the upload → cleaning workflow with step-by-step progress updates.

## User Experience Flow

### Step 1: File Upload Completion ✅
**When:** User uploads a file and it completes ingestion
**Notification:**
- Title: `✅ File Loaded: {filename}`
- Message: `Your file has been successfully uploaded with {row_count} rows. Cleaning will start automatically in a few seconds.`
- Action: Link to view the uploaded source
- Progress: 100% (upload complete)

**Triggered by:** `ingestion/signals.py` → `trigger_auto_cleaning_on_completion`
**Location:** [apps/ingestion/signals.py](apps/ingestion/signals.py)

---

### Step 2: Cleaning Started 🔄
**When:** Auto-cleaning task begins processing the uploaded file
**Notification:**
- Title: `🔄 Cleaning Started: {source_name}`
- Message: `Your data is now being cleaned automatically. This typically takes a few seconds.`
- Action: Link to view the cleaning job
- Progress: 5%

**Triggered by:** `nettoyage/tasks.py` → `auto_clean_after_ingestion` (after 5-second delay)
**Location:** [apps/nettoyage/tasks.py](apps/nettoyage/tasks.py#L44)

---

### Step 3: Cleaning Progress Updates 🔄
**When:** Cleaning is progressing through different stages
**Notifications:** Multiple updates at key checkpoints
- **25% Progress:** Cleaning rules are being applied
- **75% Progress:** Quality checks are running

**Notification Details:**
- Title: `🔄 Cleaning in Progress`
- Message: `Cleaning is {progress_percent}% complete...`
- Data: `rows_affected` count (tracked as cleaning progresses)
- Progress: Updates from 25% → 75% → 100%

**Triggered by:** `nettoyage/tasks.py` → Progress updates during `apply_cleaning()`
**Location:** [apps/nettoyage/tasks.py](apps/nettoyage/tasks.py#L72)

---

### Step 4: Cleaning Completed ✅
**When:** Cleaning finishes successfully with results
**Notification:**
- Title: `✅ Cleaning Completed`
- Message: `Data cleaning finished! {rows_affected} rows affected. Quality score: {quality_score:.1f}%`
- Data: 
  - `rows_affected`: Number of rows cleaned
  - `quality_score`: Average quality score (0-100%)
- Action: Link to detailed comparison view
- Progress: 100%

**Triggered by:** `nettoyage/tasks.py` → End of `auto_clean_after_ingestion` task
**Location:** [apps/nettoyage/tasks.py](apps/nettoyage/tasks.py#L85)

---

### Step 5 (Error Case): Cleaning Failed ❌
**When:** Cleaning encounters an error or doesn't have a default pipeline
**Notification:**
- Title: `❌ Cleaning Failed`
- Message: `An error occurred during cleaning: {error_message}`
- Data: `error` details for debugging
- Progress: 0%

**Triggered by:** `nettoyage/tasks.py` → Exception handling
**Location:** [apps/nettoyage/tasks.py](apps/nettoyage/tasks.py#L120)

---

## Technical Implementation Details

### 1. Notification Models
**File:** [apps/authentication/notification_models.py](apps/authentication/notification_models.py)

```python
class UserNotification(models.Model):
    NOTIFICATION_TYPES = [
        ('ingestion_completed', 'File Upload Complete'),
        ('cleaning_started', 'Cleaning Started'),
        ('cleaning_progress', 'Cleaning Progress'),
        ('cleaning_completed', 'Cleaning Complete'),
        ('cleaning_failed', 'Cleaning Failed'),
    ]
    
    user = ForeignKey(User)
    notification_type = CharField(choices=NOTIFICATION_TYPES)
    title = CharField()
    message = TextField()
    source_id = IntegerField(optional)
    job_id = IntegerField(optional)
    progress_percent = IntegerField(default=0)
    data = JSONField(default=dict)
    action_url = CharField(optional)
    is_read = BooleanField(default=False)
    created_at = DateTimeField(auto_now_add=True)
    read_at = DateTimeField(optional)
```

### 2. Notification Service Functions
**File:** [apps/authentication/notification_service.py](apps/authentication/notification_service.py)

All notification functions follow this pattern:

```python
def notify_[event](user_id, ...args):
    """Create notification for [event]"""
    user = User.objects.get(id=user_id)
    return notify_user(
        user=user,
        notification_type='[type]',
        title='[title]',
        message='[message]',
        progress_percent=[0-100],
        data={...},
        action_url='/api/...',
    )
```

Available functions:
- `notify_ingestion_completed()` - File uploaded ✅
- `notify_cleaning_started()` - Cleaning began 🔄
- `notify_cleaning_progress()` - In-progress updates 🔄
- `notify_cleaning_completed()` - Cleaning finished ✅
- `notify_cleaning_failed()` - Error occurred ❌

### 3. Signal Handler
**File:** [apps/ingestion/signals.py](apps/ingestion/signals.py)

```python
@receiver(post_save, sender=DataSource)
def trigger_auto_cleaning_on_completion(sender, instance, created, update_fields, **kwargs):
    if update_fields and 'status' in update_fields and instance.status == 'completed':
        # Step 1: Notify upload complete
        notify_ingestion_completed(instance.id, instance.uploaded_by.id, ...)
        
        # Step 2: Queue auto-cleaning (5 second delay)
        auto_clean_after_ingestion.apply_async(
            args=(instance.id, instance.uploaded_by.id),
            countdown=5,
        )
```

This ensures:
- User gets immediate confirmation the file loaded ✅
- 5-second delay before cleaning starts (good UX)
- Auto-cleaning is queued asynchronously

### 4. Auto-Clean Task
**File:** [apps/nettoyage/tasks.py](apps/nettoyage/tasks.py)

```python
@shared_task
def auto_clean_after_ingestion(source_id, user_id):
    """Orchestrates entire cleaning workflow with notifications at each step"""
    
    # Step 1: Notify cleaning started 🔄
    notify_cleaning_started(job.id, user_id, source.name)
    
    # Step 2: Progress at 25%
    notify_cleaning_progress(job.id, user_id, 25)
    
    # Step 3: Apply cleaning rules...
    result = apply_cleaning(...)
    
    # Step 4: Progress at 75%
    notify_cleaning_progress(job.id, user_id, 75, ...)
    
    # Step 5: Notify completion with results ✅
    notify_cleaning_completed(job.id, user_id, rows_affected, quality_score)
```

## Frontend Integration

### Notification Display Component
The frontend should display notifications as toast messages or a notification panel:

```typescript
interface Notification {
  id: number
  type: 'ingestion_completed' | 'cleaning_started' | 'cleaning_progress' | 'cleaning_completed' | 'cleaning_failed'
  title: string
  message: string
  progress_percent: number
  is_read: boolean
  created_at: string
  action_url?: string
  data: {
    row_count?: number
    rows_affected?: number
    quality_score?: number
    error?: string
  }
}
```

### WebSocket Updates (Optional)
For real-time updates without polling:

```python
# In notification_service.py
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def notify_user(...):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user.id}",
        {
            "type": "notification_message",
            "notification": notification_data,
        }
    )
```

## Database Queries

### Get Latest Notifications for User
```python
# View endpoint
notifications = UserNotification.objects.filter(
    user_id=request.user.id
).order_by('-created_at')[:20]

# With unread count
unread_count = UserNotification.objects.filter(
    user_id=request.user.id,
    is_read=False
).count()
```

### Get Notifications for a Specific Upload
```python
notifications = UserNotification.objects.filter(
    user_id=user_id,
    source_id=source_id
).order_by('created_at')
# Shows: Upload → Cleaning Started → Progress → Completed
```

### Get Notifications for a Specific Cleaning Job
```python
notifications = UserNotification.objects.filter(
    user_id=user_id,
    job_id=job_id
).order_by('created_at')
# Shows: Cleaning Started → Progress Updates → Completed
```

## Error Handling

### Scenario 1: No Default Pipeline
- Cleaning skips (no error notification)
- User gets "File Loaded" notification only
- User can manually trigger cleaning if desired

### Scenario 2: Cleaning Fails
- User gets "Cleaning Started" notification
- If error occurs: "Cleaning Failed" notification with error details
- Upload is NOT affected - file is safe

### Scenario 3: User Offline
- All notifications are persisted to database
- User sees full notification history when they log back in
- Can mark as read to clear

## Testing the Notification Flow

### 1. Upload a Test File
```bash
# Upload via API or UI
curl -X POST http://localhost:8000/api/ingestion/upload/ \
  -H "Authorization: Bearer TOKEN" \
  -F "file=@test.csv"
```

### 2. Monitor Notifications
```python
# In Django shell
from apps.authentication.models import UserNotification

# Check all notifications
notifications = UserNotification.objects.all().order_by('-created_at')
for n in notifications[:10]:
    print(f"{n.created_at} | {n.notification_type} | {n.title}")

# Check for specific user
user_notifications = UserNotification.objects.filter(user_id=1)
print(f"Total: {user_notifications.count()}")
print(f"Unread: {user_notifications.filter(is_read=False).count()}")
```

### 3. Verify Progress Sequence
```python
# Should see in order:
# 1. ingestion_completed (5 seconds after upload)
# 2. cleaning_started (immediately after)
# 3. cleaning_progress (at 25%)
# 4. cleaning_progress (at 75%)
# 5. cleaning_completed (with results)
```

## API Endpoints for Notifications

### Get All Notifications
```
GET /api/notifications/
GET /api/notifications/?limit=20&offset=0
GET /api/notifications/?unread_only=true
```

### Get Notifications for Source/Job
```
GET /api/notifications/?source_id=123
GET /api/notifications/?job_id=456
```

### Mark as Read
```
PATCH /api/notifications/123/read/
PATCH /api/notifications/mark_all_read/
```

## Configuration

### Cleanup Old Notifications
Add to a periodic task (Celery Beat):

```python
@shared_task
def cleanup_old_notifications():
    """Delete notifications older than 30 days"""
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(days=30)
    UserNotification.objects.filter(created_at__lt=cutoff).delete()
```

### Notification Retention
Configure in settings:
```python
# settings.py
NOTIFICATION_RETENTION_DAYS = 30  # Keep 30 days of history
NOTIFICATION_CLEANUP_SCHEDULE = {
    'task': 'apps.authentication.tasks.cleanup_old_notifications',
    'schedule': crontab(hour=2, minute=0),  # Run daily at 2 AM
}
```

## Summary

The notification system provides **5 sequential, user-friendly updates** that guide users through the complete upload and cleaning process:

1. ✅ **File Loaded** → "Your file is uploaded"
2. 🔄 **Cleaning Started** → "Processing has begun"
3. 🔄 **Progress Updates** → "25% complete... 75% complete"
4. ✅ **Cleaning Complete** → "Finished! {rows_affected} cleaned"
5. ❌ **Error Handling** → "Something went wrong: {details}"

This creates a transparent, reassuring user experience where they always know what's happening with their data.
