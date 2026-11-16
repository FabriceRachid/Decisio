"""
Manual performance benchmark (NOT collected by default).

Run explicitly:
    pytest benchmark_perf.py -s -q

Measures wall-time and DB query count for hot endpoints, cold (cache miss)
vs warm (cache hit).
"""
import time
import pytest

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test.utils import CaptureQueriesContext
from django.db import connection
from rest_framework.test import APIClient

from apps.conflits.models import ActivityLog, Conflict, ConflictType
from apps.ingestion.models import DataSource, RawData


def _setup(size=1):
    """Create one org-less user (endpoints fall back to self-scoped queries)."""
    user = User.objects.create_user(
        username='bench' + str(size),
        email='bench@example.com',
        password='testpass123',
    )
    user.profile.role = 'analyst'
    user.profile.save(update_fields=['role'])
    return user, None


def _seed(user, org, n_sources=5, n_conflicts=20, n_activity=50):
    source_ids = []
    for i in range(n_sources):
        ds = DataSource.objects.create(
            name=f'Source {i}',
            source_type='csv',
            uploaded_by=user,
        )
        source_ids.append(ds.id)
        RawData.objects.create(
            source=ds,
            row_number=i + 1,
            data={'col': f'value{i}', '_row_number': i + 1},
        )

    ctype = ConflictType.objects.create(
        name='Duplicate', code='DUP', severity='high'
    )
    for i in range(n_conflicts):
        Conflict.objects.create(
            data_source_id=source_ids[i % n_sources],
            conflict_type=ctype,
            conflict_details={'issue': f'd{i}'},
            description=f'Conflict {i}',
            status='open' if i % 2 == 0 else 'resolved',
            assigned_to=user if i % 3 == 0 else None,
        )

    for i in range(n_activity):
        ActivityLog.objects.create(
            user=user,
            action_type='create',
            resource_type='Source',
            resource_id=i,
            resource_name=f'Res {i}',
            user_email=user.email,
            user_role='analyst',
        )
    return source_ids


def _measure(client, url, method='get', n=3, warm=False):
    """Return (avg_ms, avg_queries). warm=True means call once first (cache warm)."""
    times = []
    queries = []
    for i in range(n):
        with CaptureQueriesContext(connection) as ctx:
            start = time.perf_counter()
            resp = getattr(client, method)(url)
            elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
        queries.append(len(ctx.captured_queries))
    if warm:
        # first iteration populates cache; report the rest
        times = times[1:]
        queries = queries[1:]
    return (sum(times) / len(times), sum(queries) / len(queries)) if times else (0, 0)


def run_benchmark(n):
    user, org = _setup(n)
    client = APIClient()
    client.force_authenticate(user=user)
    source_ids = _seed(user, org)

    print(f'\n=== Benchmark (scale={n}) ===')
    print('data: {} sources, 20 conflicts, 50 activity logs'.format(n))

    cache.clear()

    # 1. dashboard_stats — cold vs warm
    url = '/api/conflits/conflicts/dashboard_stats/'
    cache.delete(f'conflict_dashboard_stats_{user.id}')
    cold_t, cold_q = _measure(client, url, n=3, warm=False)
    warm_t, warm_q = _measure(client, url, n=5, warm=True)
    print(f'dashboard_stats  cold: {cold_t:8.2f} ms  {cold_q:3.0f} queries')
    print(f'dashboard_stats  warm: {warm_t:8.2f} ms  {warm_q:3.0f} queries')

    # 2. activity_feed — cold vs warm
    url = '/api/conflits/activity-feed/?limit=50'
    cache.delete(f'activity_feed_{user.id}_50')
    cold_t, cold_q = _measure(client, url, n=3, warm=False)
    warm_t, warm_q = _measure(client, url, n=5, warm=True)
    print(f'activity_feed    cold: {cold_t:8.2f} ms  {cold_q:3.0f} queries')
    print(f'activity_feed    warm: {warm_t:8.2f} ms  {warm_q:3.0f} queries')

    # 3. presence list
    url = '/api/auth/presence/'
    t, q = _measure(client, url, n=3, warm=False)
    print(f'presence_list         {t:8.2f} ms  {q:3.0f} queries')

    # 4. source detail (prefetch capped at 10 rows)
    url = f'/api/ingestion/sources/{source_ids[0]}/'
    t, q = _measure(client, url, n=3, warm=False)
    print(f'source_detail         {t:8.2f} ms  {q:3.0f} queries')

    # 5. dashboard auto-build — cold vs warm (cache)
    from apps.dashboard.models import Dashboard, Widget
    key = f"dashboard_auto:{user.id}:{source_ids[0]}"
    slug = f"dashboard-auto-{user.id}-{source_ids[0]}"
    dashboard = Dashboard.objects.create(
        created_by=user, slug=slug, name='Bench', layout={}, grid_columns=12,
    )
    wdefs = [
        ('Count', 'metric_card', 'count', [], 0, 0),
        ('Sum', 'metric_card', 'sum', [], 3, 0),
        ('Count', 'line_chart', 'count', [], 0, 2),
        ('Sum', 'bar_chart', 'sum', [], 6, 0),
        ('Count', 'pie_chart', 'count', [], 0, 5),
        ('Sum', 'area_chart', 'sum', [], 8, 2),
        ('Count', 'metric_card', 'count', [], 6, 4),
        ('Sum', 'bar_chart', 'sum', [], 0, 8),
    ]
    for i, (title, wtype, agg, gb, x, y) in enumerate(wdefs):
        Widget.objects.create(
            dashboard=dashboard,
            widget_type=wtype,
            position_x=x, position_y=y, width=4, height=3,
            configuration={
                'measure': '_row_number', 'aggregation': agg,
                'group_by': [], 'source_id': source_ids[0],
                'source_table': 'ingestion_rawdata', 'auto_generated': True,
            },
            title=title,
        )
    url = f'/api/dashboard/auto-build/?source_id={source_ids[0]}'
    cache.delete(key)
    cold_t, cold_q = _measure(client, url, n=2, warm=False)
    warm_t, warm_q = _measure(client, url, n=5, warm=True)
    print(f'dashboard_load    cold: {cold_t:8.2f} ms  {cold_q:3.0f} queries')
    print(f'dashboard_load    warm: {warm_t:8.2f} ms  {warm_q:3.0f} queries')

    return {
        'dashboard_cold_ms': cold_t,
        'dashboard_warm_ms': warm_t,
        'dashboard_cold_q': cold_q,
        'dashboard_warm_q': warm_q,
        'activity_cold_ms': cold_t,
        'activity_warm_ms': warm_t,
        'source_detail_ms': t,
        'source_detail_q': q,
    }


@pytest.mark.django_db
def test_benchmark_small():
    run_benchmark(1)


@pytest.mark.django_db
def test_benchmark_large():
    run_benchmark(10)