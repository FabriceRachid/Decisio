# Notification System - Testing Guide

## Quick Start

### 1. Verify Models & Database
```bash
# Check if notifications table exists
python manage.py migrate

# Verify model is registered
python manage.py shell
>>> from apps.authentication.notification_models import UserNotification
>>> UserNotification.objects.count()
```

### 2. Test API Endpoints

#### Get Your Notifications
```bash
# Get all notifications (newest first)
curl -X GET http://localhost:8000/api/auth/notifications/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Response:
{
  "unread_count": 5,
  "total_count": 10,
  "notifications": [
    {
      "id": 1,
      "type": "ingestion_completed",
      "title": "✅ File Loaded: sales_data.csv",
      "message": "Your file has been successfully uploaded with 1000 rows. Cleaning will start automatically in a few seconds.",
      "progress_percent": 100,
      "is_read": false,
      "created_at": "2024-01-15T10:30:45Z",
      "action_url": "/api/ingestion/sources/123/"
    }
    ...
  ]
}
```

#### Get Unread Only
```bash
curl -X GET "http://localhost:8000/api/auth/notifications/?is_read=false" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Get Specific Notification Status
```bash
curl -X GET "http://localhost:8000/api/auth/notifications/?notification_type=cleaning_progress" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Mark Notification as Read
```bash
curl -X PATCH http://localhost:8000/api/auth/notifications/1/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'

# Response:
{
  "message": "Notification marked as read",
  "is_read": true
}
```

#### Mark All as Read
```bash
curl -X POST http://localhost:8000/api/auth/notifications/mark-all-read/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Response:
{
  "message": "Marked 5 notification(s) as read",
  "count": 5
}
```

## End-to-End Test Flow

### Step 1: Create Test User
```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "TestPass123!"
  }'

# Get token
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "TestPass123!"
  }'

# Save TOKEN from response
export TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."
```

### Step 2: Upload a File
```bash
# Create test CSV
cat > test_data.csv << 'EOF'
name,age,city
John,30,NYC
Jane,25,LA
Bob,35,Chicago
EOF

# Upload
curl -X POST http://localhost:8000/api/ingestion/upload/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test_data.csv"

# Response contains source_id
export SOURCE_ID=123
```

### Step 3: Monitor Notifications in Real-Time
```bash
# Polling approach (check every 2 seconds)
while true; do
  echo "Checking notifications..."
  curl -s -X GET http://localhost:8000/api/auth/notifications/ \
    -H "Authorization: Bearer $TOKEN" | jq '.notifications | .[] | {type: .type, title: .title, progress: .progress_percent}'
  sleep 2
done

# You should see progression:
# 1. type: "ingestion_completed" | progress: 100
# 2. type: "cleaning_started" | progress: 5
# 3. type: "cleaning_progress" | progress: 25
# 4. type: "cleaning_progress" | progress: 75
# 5. type: "cleaning_completed" | progress: 100
```

### Step 4: Inspect Notifications
```bash
# Get detailed notification
curl -X GET http://localhost:8000/api/auth/notifications/1/ \
  -H "Authorization: Bearer $TOKEN" | jq .

# Mark as read
curl -X PATCH http://localhost:8000/api/auth/notifications/1/ \
  -H "Authorization: Bearer $TOKEN" | jq .
```

## Django Shell Testing

```python
from django.contrib.auth.models import User
from apps.authentication.notification_models import UserNotification
from apps.authentication.notification_service import *

# Get test user
user = User.objects.get(username='testuser')

# Check notification count
print(user.notifications.count())

# Get unread count
print(user.notifications.filter(is_read=False).count())

# View all notifications chronologically
for notif in user.notifications.all():
    print(f"{notif.created_at} | {notif.notification_type} | {notif.title} | {notif.progress_percent}%")

# Group by type
from django.db.models import Count
user.notifications.values('notification_type').annotate(count=Count('id'))

# Find notifications for specific source
notifs = user.notifications.filter(source_id=123)
for n in notifs:
    print(f"{n.notification_type}: {n.data}")

# Find notifications for specific job
notifs = user.notifications.filter(job_id=456)
for n in notifs:
    print(f"{n.notification_type}: progress={n.progress_percent}%")

# Test creating notification manually
notify_cleaning_started(456, user.id, "test_source.csv")

# Verify it was created
UserNotification.objects.filter(
    user=user,
    notification_type='cleaning_started'
).order_by('-created_at').first()
```

## Expected Notification Sequence

For a single file upload → clean → complete:

```
TIME  | TYPE                     | TITLE                                | PROGRESS
------|--------------------------|--------------------------------------|----------
0s    | ingestion_completed      | ✅ File Loaded: data.csv             | 100%
5s    | cleaning_started         | 🔄 Cleaning Started: data.csv        |   5%
7s    | cleaning_progress        | 🔄 Cleaning in Progress              |  25%
12s   | cleaning_progress        | 🔄 Cleaning in Progress              |  75%
15s   | cleaning_completed       | ✅ Cleaning Completed                | 100%
```

## Database Schema Check

```sql
-- Connect to PostgreSQL
psql -U decisio -d decisio_db

-- Verify table exists
\dt auth_usernotification

-- Check structure
\d auth_usernotification

-- Count notifications
SELECT COUNT(*), notification_type 
FROM auth_usernotification 
GROUP BY notification_type;

-- Find most recent
SELECT id, user_id, notification_type, created_at 
FROM auth_usernotification 
ORDER BY created_at DESC 
LIMIT 20;
```

## Error Scenarios

### Scenario 1: File Upload with No Default Pipeline
```bash
# Expected: Upload completes BUT no cleaning occurs
# Notification: Only "ingestion_completed"
# No "cleaning_started" or later notifications
```

### Scenario 2: Cleaning Fails Midway
```bash
# Upload completes → ✅
# Cleaning starts → 🔄  
# At some point: ❌ cleaning_failed
# Check logs for error details
```

### Scenario 3: User Offline During Processing
```bash
# Upload file
# Go offline (kill network)
# Wait for processing to complete
# Reconnect
# Call GET /api/auth/notifications/
# See all notifications that accumulated while offline
```

## Performance Monitoring

### Check Notification Volume
```python
from apps.authentication.notification_models import UserNotification
from django.utils import timezone
from datetime import timedelta

# Last 24 hours
yesterday = timezone.now() - timedelta(days=1)
count = UserNotification.objects.filter(created_at__gte=yesterday).count()
print(f"Notifications in last 24h: {count}")

# Per user
from django.db.models import Count
per_user = UserNotification.objects.values('user__username').annotate(
    count=Count('id')
).order_by('-count')
for item in per_user[:10]:
    print(f"{item['user__username']}: {item['count']} notifications")
```

### Monitor Unread Count
```python
# System-wide unread
unread = UserNotification.objects.filter(is_read=False).count()
print(f"Unread notifications: {unread}")

# Per user
from django.db.models import Count
unread_per_user = UserNotification.objects.filter(is_read=False).values(
    'user__username'
).annotate(count=Count('id')).order_by('-count')
```

## Cleanup & Maintenance

### Delete Old Notifications
```python
from django.utils import timezone
from datetime import timedelta

# Delete older than 30 days (if not done by scheduler)
cutoff = timezone.now() - timedelta(days=30)
deleted_count, _ = UserNotification.objects.filter(
    created_at__lt=cutoff
).delete()
print(f"Deleted {deleted_count} old notifications")
```

### Clear All Unread Flags
```python
from django.utils import timezone

count = UserNotification.objects.filter(
    is_read=False
).update(
    is_read=True,
    read_at=timezone.now()
)
print(f"Marked {count} as read")
```

## Common Issues & Solutions

### Issue 1: Notifications Not Appearing
**Check:**
```python
# 1. Is the signal being triggered?
# Check Django logs for "trigger_auto_cleaning_on_completion" messages

# 2. Is the task queued?
# Check Celery logs for "auto_clean_after_ingestion" task

# 3. Did notification service get called?
# Check for notify_cleaning_started call in logs

# 4. Is the user correct?
from apps.authentication.notification_models import UserNotification
# Verify notification is created for your user
UserNotification.objects.filter(user_id=YOUR_USER_ID).count()
```

### Issue 2: Wrong Progress Percentages
**Check:**
```python
from apps.authentication.notification_models import UserNotification

# Verify progress sequence
notifs = UserNotification.objects.filter(
    user_id=1, 
    job_id=123
).order_by('created_at')

for n in notifs:
    print(f"{n.created_at} | {n.notification_type} | {n.progress_percent}%")
```

### Issue 3: Celery Not Processing Tasks
```bash
# Check if Celery is running
ps aux | grep celery

# If not running, start it:
celery -A decisiobi worker -l info

# Check task status
python manage.py shell
>>> from celery.result import AsyncResult
>>> result = AsyncResult('task-id-here')
>>> result.status
>>> result.result
```

## Docker Deployment Testing

If using Docker:

```bash
# Check if migrations ran
docker exec decisio_backend python manage.py migrate --check

# Test from inside container
docker exec decisio_backend python manage.py shell << 'EOF'
from apps.authentication.notification_models import UserNotification
print(UserNotification.objects.count())
EOF

# View logs
docker logs -f decisio_backend
docker logs -f decisio_celery
```

## Automated Testing

```bash
# Run notification-specific tests
python manage.py test apps.authentication.tests.test_notifications

# Run all auth tests
python manage.py test apps.authentication

# Test with coverage
coverage run --source='apps.authentication' manage.py test
coverage report
```

## Summary Checklist

- [ ] Database migrations applied (`python manage.py migrate`)
- [ ] Notification model registered in admin
- [ ] Signal connected to DataSource post_save
- [ ] Celery worker running for background tasks
- [ ] Notification service functions tested
- [ ] API endpoints responding
- [ ] File upload triggers signal
- [ ] Auto-cleaning task fires on schedule
- [ ] Progress notifications update correctly
- [ ] Cleanup task scheduled (optional but recommended)
- [ ] Frontend polling/consuming notifications
