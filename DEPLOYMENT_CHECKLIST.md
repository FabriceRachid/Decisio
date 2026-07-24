# Notification System - Deployment Checklist

## Pre-Deployment Verification

### Backend (Django)
- [ ] Code reviewed: [apps/nettoyage/tasks.py](../backend/apps/nettoyage/tasks.py)
- [ ] Code reviewed: [apps/authentication/urls.py](../backend/apps/authentication/urls.py)
- [ ] Migrations verified: `python manage.py migrate --check`
- [ ] No errors in: `python manage.py check`
- [ ] Celery workers can start: `celery -A decisiobi worker --loglevel=info`
- [ ] Redis/broker connection tested

### Database (PostgreSQL)
- [ ] Table exists: `\dt auth_usernotification`
- [ ] Indexes created: Check with `\d auth_usernotification`
- [ ] Sample data loaded correctly

### Frontend (React)
- [ ] Components created from [NOTIFICATION_INTEGRATION_GUIDE.md](../frontend/NOTIFICATION_INTEGRATION_GUIDE.md)
- [ ] NotificationContainer imported in App.tsx
- [ ] useNotifications hook works with API
- [ ] Browser console shows no CORS errors
- [ ] Notifications display as expected

## Deployment Steps

### 1. Backend Deployment

```bash
# 1.1 Pull latest code
git pull origin main

# 1.2 Apply migrations
python manage.py migrate

# 1.3 Collect static files (if needed)
python manage.py collectstatic --noinput

# 1.4 Restart Django server
systemctl restart decisiobi  # or: supervisorctl restart decisiobi

# 1.5 Start/restart Celery worker
celery -A decisiobi worker -l info --logfile=/var/log/celery.log

# 1.6 Verify API work
curl -H "Authorization: Bearer TOKEN" \
  https://api.decisio.com/api/auth/notifications/
```

### 2. Frontend Deployment

```bash
# 2.1 Create React components
# Copy from NOTIFICATION_INTEGRATION_GUIDE.md:
mkdir -p src/hooks src/components
# Create: src/hooks/useNotifications.ts
# Create: src/components/NotificationToast.tsx
# Create: src/components/NotificationContainer.tsx
# Create: src/components/NotificationPanel.tsx

# 2.2 Update App.tsx
# Import NotificationContainer
# Add to JSX: <NotificationContainer />

# 2.3 Build and test
npm run build
npm run preview

# 2.4 Deploy
npm run build

# 2.5 Verify API connectivity
# Check browser console - should see GET requests to /api/auth/notifications/
```

### 3. Verification

```bash
# 3.1 Check backend services
systemctl status decisiobi
systemctl status celery
systemctl status redis

# 3.2 Check logs
tail -f /var/log/django.log | grep -i notification
tail -f /var/log/celery.log | grep -i auto_clean

# 3.3 Test full flow
# 1. Upload file via frontend
# 2. Watch browser for notifications
# 3. Check database:
#    SELECT * FROM auth_usernotification ORDER BY created_at DESC LIMIT 10;
# 4. Verify progression: upload → started → progress → completed
```

## Post-Deployment Monitoring

### Daily Checks

```bash
# Check notification volume
psql -U decisio -d decisio_db -c "
  SELECT DATE(created_at), COUNT(*) 
  FROM auth_usernotification 
  GROUP BY DATE(created_at) 
  ORDER BY DATE(created_at) DESC 
  LIMIT 7;
"

# Check error rate
grep -i "error\|failed" /var/log/django.log | tail -20
grep -i "error\|failed" /var/log/celery.log | tail -20

# Check unread notifications
psql -U decisio -d decisio_db -c "
  SELECT COUNT(*) FROM auth_usernotification WHERE is_read = false;
"
```

### Weekly Review

```bash
# Performance
psql -U decisio -d decisio_db -c "
  SELECT notification_type, COUNT(*), AVG(EXTRACT(EPOCH FROM updated_at - created_at))
  FROM auth_usernotification 
  WHERE created_at > NOW() - INTERVAL '7 days'
  GROUP BY notification_type
  ORDER BY COUNT(*) DESC;
"

# Storage usage
psql -U decisio -d decisio_db -c "
  SELECT 
    pg_size_pretty(pg_total_relation_size('auth_usernotification')) AS table_size,
    COUNT(*) AS row_count
  FROM auth_usernotification;
"
```

## Rollback Plan

If notification system causes issues:

```bash
# 1. Disable notification display (frontend)
# Comment out <NotificationContainer /> in App.tsx
# Redeploy frontend

# 2. Stop auto-cleaning (backend temporary)
# Edit settings.py:
CELERY_TASK_ALWAYS_EAGER = False  # or True to disable async

# 3. Check for database lock
psql -U decisio -d decisio_db -c "
  SELECT * FROM pg_stat_activity WHERE state = 'active';
"

# 4. Clear old notifications (if storage issue)
psql -U decisio -d decisio_db -c "
  DELETE FROM auth_usernotification WHERE created_at < NOW() - INTERVAL '30 days';
"

# 5. Full rollback (if critical)
git revert <commit-hash>
python manage.py migrate
systemctl restart decisiobi
```

## Performance Tuning

### If API is slow

```sql
-- Add index if missing
CREATE INDEX idx_notification_user_created 
ON auth_usernotification(user_id, created_at DESC);

CREATE INDEX idx_notification_user_unread 
ON auth_usernotification(user_id, is_read);
```

### If notifications are missing

```python
# Check if signal is firing
from django.db.models.signals import post_save
from apps.ingestion.models import DataSource
from django.dispatch import receiver

@receiver(post_save, sender=DataSource)
def debug_signal(sender, instance, created, **kwargs):
    print(f"Signal fired: instance={instance}, created={created}")
```

### If Celery tasks not running

```bash
# Check broker connection
celery -A decisiobi inspect active_queues

# Check if workers are listening
celery -A decisiobi inspect stats

# Monitor task events
celery -A decisiobi events

# Check task history
celery -A decisiobi inspect reserved
```

## User Documentation

Once deployed, provide users with:

1. **What to expect:**
   - File upload completes → User sees "✅ File Loaded" notification
   - Cleaning starts automatically → User sees "🔄 Cleaning Started"
   - Cleaning progresses → User sees "🔄 Progress" updates
   - Cleaning completes → User sees "✅ Cleaning Completed" with results

2. **Where to find notifications:**
   - Toast messages appear in top-right corner
   - Full history in notification panel/drawer
   - Click to view detailed results

3. **What the data means:**
   - `rows_affected`: Number of rows cleaned/modified
   - `quality_score`: Overall data quality (0-100%)
   - `progress_percent`: How far through the cleaning process

## Support Contacts

- **Backend Issues:** Check logs in `/var/log/django.log` and `/var/log/celery.log`
- **Database Issues:** Query `auth_usernotification` table
- **Frontend Issues:** Check browser console for API errors
- **Performance Issues:** Check database size and query plans

## Success Criteria

- [ ] All notifications appear in correct order
- [ ] Progress percentages are accurate
- [ ] Completion notification includes quality score and rows affected
- [ ] Users can mark notifications as read
- [ ] No missing notifications
- [ ] No duplicate notifications
- [ ] API response time < 200ms
- [ ] Celery tasks execute within expected timeframe (~15-20s)

## Documentation Links

- **Technical Deep Dive:** [NOTIFICATION_FLOW_IMPLEMENTATION.md](../backend/NOTIFICATION_FLOW_IMPLEMENTATION.md)
- **Testing Procedures:** [NOTIFICATION_TESTING_GUIDE.md](../backend/NOTIFICATION_TESTING_GUIDE.md)
- **Frontend Components:** [NOTIFICATION_INTEGRATION_GUIDE.md](../frontend/NOTIFICATION_INTEGRATION_GUIDE.md)
- **Overview:** [README_NOTIFICATIONS.md](../README_NOTIFICATIONS.md)

## Final Checklist Before Going Live

- [ ] Backend code deployed
- [ ] Migrations applied
- [ ] Celery workers running
- [ ] Frontend components created
- [ ] NotificationContainer integrated in App.tsx
- [ ] API endpoints responding
- [ ] Test file upload works end-to-end
- [ ] Notifications appear in correct order
- [ ] Unread count updates
- [ ] Mark as read works
- [ ] Error cases handled gracefully
- [ ] Logs monitored
- [ ] Database backed up
- [ ] Users notified of new feature
- [ ] Support team trained

✅ You're ready to deploy!
