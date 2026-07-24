# M4: Calcul automatique des KPI
## Automatic KPI Calculation

**Status:** ✅ Implemented
**Last Updated:** December 2024
**Scope:** Event-driven KPI calculation with SQL/Python formula support, anomaly detection, forecasting, and alert management

---

## 1. Overview

M4 is the automatic KPI (Key Performance Indicator) calculation module that continuously monitors, calculates, and analyzes critical business metrics. It integrates with M1 (Ingestion), M2 (Cleaning), and M3 (Conflicts) to provide real-time KPI insights.

### Key Capabilities

- **Event-Driven Calculation**: Automatically triggered after data ingestion, cleaning, and conflict resolution
- **Flexible Formula Support**: SQL queries, Python expressions, and Excel-style aggregations
- **Multi-Type Formulas**: Support for complex calculation logic with safety guards
- **Variance Tracking**: Monitor performance against targets and previous periods
- **Anomaly Detection**: Identify unusual KPI values using statistical methods
- **Forecasting**: Project future KPI values with confidence intervals
- **Smart Alerting**: Multi-channel notifications with escalation workflows
- **Dashboard Analytics**: Real-time KPI status and performance metrics

---

## 2. Architecture

### 2.1 Service Layer

Location: `apps/kpi/services.py`

#### KPICalculationService
```python
KPICalculationService(user, safe_mode=True)
```

**Key Methods:**
- `calculate_kpi(kpi, period_start, period_end)` - Calculate single KPI for period
- `_evaluate_sql_formula(kpi, period_start, period_end)` - Execute SQL formula
- `_evaluate_python_formula(kpi, period_start, period_end)` - Evaluate Python code safely
- `_evaluate_excel_formula(kpi, period_start, period_end)` - Apply aggregation method
- `batch_calculate_kpis(kpis, period_start, period_end)` - Calculate multiple KPIs

**Returns:**
```python
{
    'calculated_value': float,      # The computed result
    'variance_absolute': float,     # Difference from previous period
    'variance_percent': float,      # Percentage change
    'target_variance': float,       # Difference from target
    'status': 'on_target',         # on_target, warning, critical
    'breakdown': dict,              # Dimensional breakdown
    'data_quality_score': float,   # 0-100 confidence
    'rows_processed': int,          # Records used
    'execution_time_ms': int,       # Performance metric
    'success': bool
}
```

#### KPIAnomalyDetectionService
```python
KPIAnomalyDetectionService(user)
```

**Key Methods:**
- `detect_anomalies(kpi, lookback_periods=12)` - Detect unusual values

**Detection Methods:**
- Z-score analysis (> 2.5 standard deviations = anomaly)
- Isolation Forest (advanced pattern detection)
- IQR (Interquartile Range) method

**Returns:**
```python
{
    'has_anomaly': bool,
    'z_score': float,
    'mean': float,
    'std_dev': float,
    'latest_value': float,
    'method': 'z_score',
    'explanation': str,
    'recommendation': str
}
```

#### KPIForecastingService
```python
KPIForecastingService(user)
```

**Key Methods:**
- `forecast_kpi(kpi, forecast_periods=3)` - Predict next N periods

**Forecasting Method:**
- Linear regression for trend analysis
- Confidence intervals (95% CI)
- R-squared goodness of fit

**Returns:**
```python
{
    'success': bool,
    'forecast_values': [float, ...],
    'confidence_intervals': [[lower, upper], ...],
    'trend': 'increasing|decreasing|stable',
    'trend_slope': float,
    'confidence': float,  # 0-100
    'r_squared': float
}
```

#### KPIAlertingService
```python
KPIAlertingService(user)
```

**Key Methods:**
- `evaluate_alerts(calculation)` - Check if alerts should trigger
- `_check_alert_condition(alert, calculation)` - Evaluate condition
- `_send_alert_notifications(alert, calculation)` - Multi-channel delivery
- `acknowledge_alert(alert, notes)` - Mark alert as handled

**Notification Channels:**
- Email
- Webhook
- Slack (extensible)
- SMS (extensible)

---

## 3. Formula Types

### 3.1 SQL Formulas

**Usage:** For aggregating data directly from database

```sql
-- Example: Calculate Q1 revenue
SELECT SUM(amount) FROM {source_table}
WHERE date >= '{period_start}'
  AND date <= '{period_end}'
  AND status = 'completed'
```

**Features:**
- Direct PostgreSQL syntax
- Support for parameterized queries
- Period variables: {period_start}, {period_end}, {source_table}
- Row count automatically tracked for data quality

**Safety:**
- Parameterized inputs prevent SQL injection
- Timeout protection for long-running queries

### 3.2 Python Formulas

**Usage:** For complex calculations and transformations

```python
# Example: Calculate compound growth rate
import math
previous = data['previous_value']
current = data['current_value']
math.pow(current / previous, 1/periods) - 1
```

**Available Functions:**
- Math: `sum`, `min`, `max`, `abs`, `round`, `int`, `float`
- Data: `len`, `Counter`, `np.mean`, `np.std`
- Type: `str`, `Decimal`

**Safety Guard Patterns:**
- Forbidden: `__import__`, `exec`, `eval`, `open`, `file`
- Restricted: No file system access
- Whitelist: Only safe mathematical and aggregation functions

### 3.3 Excel-Style Formulas

**Usage:** For standard business calculations

```python
KPI.aggregation_method in ['SUM', 'AVG', 'COUNT', 'MIN', 'MAX']
```

**Features:**
- Automatic data retrieval from source table
- Specified measure column aggregation
- Optional dimensional breakdown

**Example:**
```
- Source Table: nettoyage_cleaneddata
- Measure Column: revenue
- Aggregation: SUM
- Dimensions: [region, product]
Result: Total revenue, broken down by region and product
```

---

## 4. Event-Driven KPI Calculation

### Integration Points

#### M1 → M4: After Ingestion
```python
# Triggered when new data source is imported
from apps.kpi.services import KPICalculationService

service = KPICalculationService(user)
kpis = KPI.objects.filter(source_table='ingestion_rawdata', is_active=True)
service.batch_calculate_kpis(kpis)
```

#### M2 → M4: After Cleaning
```python
# Triggered after cleaning rules applied
# (Already integrated in apps/nettoyage/tasks.py)
from apps.kpi.services import KPICalculationService

conflict_service = KPICalculationService(user)
service.batch_calculate_kpis(kpis)  # Calculate affected KPIs
```

#### M3 → M4: After Conflict Resolution
```python
# Triggered after conflicts resolved
from apps.kpi.services import KPICalculationService

service = KPICalculationService(user)
service.batch_calculate_kpis(kpis)  # Recalculate with resolved data
```

### Trigger Configuration

**Frequency Options:**
- **daily**: Calculate once per day
- **weekly**: Calculate every Monday
- **monthly**: Calculate on 1st of month
- **quarterly**: Calculate on 1st day of quarter
- **yearly**: Calculate on Jan 1

**Implementation:** Celery Beat scheduled tasks (future)

---

## 5. API Endpoints

### Base URL: `/api/kpi/`

#### 5.1 KPI Management

**List KPIs with Filtering**
```
GET /api/kpi/kpis/?category=Financial&frequency=monthly&is_active=true
```

Response:
```json
{
    "count": 45,
    "results": [
        {
            "id": 1,
            "name": "Q1 Revenue",
            "code": "REV_Q1",
            "category": "Financial",
            "frequency": "monthly",
            "target_value": 5000000,
            "is_active": true,
            "last_calculated_at": "2024-01-15T10:30:00Z",
            "latest_calculation": {
                "value": 4850000,
                "status": "warning",
                "period_label": "January 2024"
            },
            "calculation_count": 12
        }
    ]
}
```

**Get KPI Detail**
```
GET /api/kpi/kpis/{id}/
```

Response includes:
- Complete formula configuration
- All thresholds and targets
- Hierarchical relationships
- Calculation history count

**Create KPI**
```
POST /api/kpi/kpis/
Content-Type: application/json

{
    "name": "Customer Churn Rate",
    "code": "CHURN_RATE",
    "formula": "SELECT COUNT(DISTINCT customer_id) * 100.0 / (SELECT COUNT(*) FROM customers) FROM churned_customers WHERE date BETWEEN '{period_start}' AND '{period_end}'",
    "formula_type": "sql",
    "frequency": "monthly",
    "target_value": 5.0,
    "unit": "%",
    "category": "Customer",
    "warning_threshold": 7.5,
    "critical_threshold": 10.0
}
```

#### 5.2 Calculation Management

**Manually Trigger Calculation**
```
POST /api/kpi/kpis/{id}/calculate_now/
```

Response:
```json
{
    "status": "calculation_completed",
    "calculated_value": 4850000,
    "variance_percent": -3.5,
    "status": "warning",
    "data_quality_score": 92.5
}
```

**Batch Calculate Multiple KPIs**
```
POST /api/kpi/kpis/batch_calculate/

{
    "kpi_ids": [1, 2, 3],
    "period_start": "2024-01-01",
    "period_end": "2024-01-31"
}
```

Response:
```json
{
    "status": "batch_calculation_completed",
    "successful": 3,
    "failed": 0,
    "results": {
        "REV_Q1": true,
        "REV_Q2": true,
        "CHURN_RATE": true
    }
}
```

**Get Calculation History**
```
GET /api/kpi/kpis/{id}/history/?limit=12
```

Response:
```json
{
    "kpi": {...},
    "calculations": [
        {
            "period_label": "January 2024",
            "calculated_value": 4850000,
            "previous_value": 5000000,
            "variance_percent": -3.0,
            "status": "warning",
            "data_quality_score": 92.5
        }
    ],
    "total": 12
}
```

#### 5.3 Anomaly Detection

**Detect Anomalies**
```
GET /api/kpi/kpis/{id}/anomaly_detection/?lookback=12
```

Response:
```json
{
    "has_anomaly": true,
    "z_score": 2.8,
    "mean": 5000000,
    "std_dev": 125000,
    "latest_value": 4650000,
    "method": "z_score",
    "explanation": "Latest value is 2.80 standard deviations from mean",
    "recommendation": "Review recent data quality or business changes"
}
```

#### 5.4 Forecasting

**Get Forecast**
```
GET /api/kpi/kpis/{id}/forecast/?periods=3
```

Response:
```json
{
    "success": true,
    "forecast_values": [4900000, 4950000, 5000000],
    "confidence_intervals": [
        [4700000, 5100000],
        [4750000, 5150000],
        [4800000, 5200000]
    ],
    "trend": "increasing",
    "confidence": 78.5,
    "r_squared": 0.856
}
```

#### 5.5 Variance Analysis

**Compare Periods**
```
GET /api/kpi/kpis/{id}/variance_analysis/
```

Response:
```json
{
    "kpi_name": "Q1 Revenue",
    "kpi_code": "REV_Q1",
    "current_period": {...},
    "previous_period": {...},
    "absolute_variance": -150000,
    "percent_variance": -3.0,
    "trend": "decreasing",
    "vs_target": {
        "target_value": 5000000,
        "current_vs_target": -150000
    }
}
```

#### 5.6 Alert Management

**List Alerts**
```
GET /api/kpi/alerts/?is_active=true&is_triggered=true
```

**Create Alert**
```
POST /api/kpi/alerts/

{
    "kpi": 1,
    "alert_name": "Revenue Below Target",
    "alert_type": "threshold_breach",
    "condition_type": "below",
    "threshold_value": 4500000,
    "notification_channels": ["email", "webhook"],
    "recipients": ["manager@example.com"],
    "webhook_url": "https://api.example.com/alerts",
    "cooldown_minutes": 60
}
```

**Acknowledge Alert**
```
POST /api/kpi/alerts/{id}/acknowledge/

{
    "notes": "Investigating revenue shortfall"
}
```

#### 5.7 Dashboard

**Get Dashboard Statistics**
```
GET /api/kpi/dashboard/
```

Response:
```json
{
    "total_kpis": 45,
    "kpis_active": 42,
    "kpis_on_target": 35,
    "kpis_warning": 5,
    "kpis_critical": 2,
    "by_category": {
        "Financial": 20,
        "Operational": 15,
        "Customer": 10
    },
    "calculation_success_rate": 98.5,
    "avg_data_quality": 92.3,
    "active_alerts": 8,
    "triggered_this_week": 3,
    "top_performers": [...],
    "bottom_performers": [...]
}
```

---

## 6. Data Models

### KPI
```python
class KPI(models.Model):
    name: str                           # "Q1 Revenue"
    code: str (unique)                 # "REV_Q1"
    description: str?
    formula: str                        # SQL, Python, or Excel formula
    formula_type: choice                # 'sql', 'python', 'excel'
    target_value: Decimal?
    operator: choice?                   # '>=', '<=', '=', '>', '<'
    unit: str?                          # "%", "$", "units"
    frequency: choice                   # 'daily', 'weekly', 'monthly', etc.
    category: str?                      # "Financial", "Customer", etc.
    
    source_table: str?                  # 'ingestion_rawdata', 'nettoyage_cleaneddata'
    measure_column: str?                # Column to measure
    dimension_columns: list             # ['region', 'product']
    filter_conditions: dict             # WHERE clause parameters
    aggregation_method: str?            # 'SUM', 'AVG', 'COUNT', 'MIN', 'MAX'
    
    owner: ForeignKey User
    is_active: bool
    is_public: bool
    tags: list
    
    warning_threshold: Decimal?
    critical_threshold: Decimal?
    
    parent_kpi: ForeignKey KPI?         # Hierarchical KPI relationships
    benchmark_source: str?
    visualization_type: str?            # 'gauge', 'trend', 'bar'
    
    created_at: DateTime (auto)
    updated_at: DateTime (auto)
    last_calculated_at: DateTime?
```

### KPICalculation
```python
class KPICalculation(models.Model):
    kpi: ForeignKey KPI
    period_start: Date
    period_end: Date
    period_label: str                   # "Q1 2024", "January 2024"
    
    # Calculation result
    calculated_value: Decimal
    previous_value: Decimal?
    variance_absolute: Decimal?
    variance_percent: Decimal?          # -3.5 for -3.5%
    target_variance: Decimal?
    status: choice                      # 'on_target', 'warning', 'critical'
    
    # Data quality & execution
    calculation_method: choice          # 'automatic', 'manual', 'estimated'
    data_quality_score: Decimal         # 0-100
    rows_processed: int
    execution_time_ms: int
    executed_by: ForeignKey User
    notes: str?
    
    # Advanced analysis
    breakdown: dict                     # Dimensional breakdown
    forecast_value: Decimal?
    confidence_interval: list           # [lower_bound, upper_bound]
    anomaly_detected: bool
    
    executed_at: DateTime (auto)
```

### KPIAlert
```python
class KPIAlert(models.Model):
    kpi: ForeignKey KPI
    alert_name: str
    alert_type: choice                  # 'threshold_breach', 'anomaly', 'scheduled'
    condition_type: choice              # 'above', 'below', 'equals', 'changed_by'
    threshold_value: Decimal?
    threshold_percent: Decimal?         # For 'changed_by'
    
    # Notification
    notification_channels: list         # ['email', 'webhook', 'slack']
    recipients: list                    # User IDs or emails
    webhook_url: str?
    message_template: str?
    
    # Alert state
    is_active: bool
    is_triggered: bool
    trigger_count: int
    last_triggered_at: DateTime?
    last_value: Decimal?
    
    # Cooldown & escalation
    cooldown_minutes: int (default 60)
    mute_until: DateTime?
    escalation_policy: dict             # {"after_hours": 4, "escalate_to": "manager"}
    
    # Acknowledgment
    acknowledged_by: ForeignKey User?
    acknowledged_at: DateTime?
    resolution_notes: str?
    
    created_by: ForeignKey User
    created_at: DateTime (auto)
    updated_at: DateTime (auto)
```

---

## 7. Status & Performance

### Calculation Status

| Status | Meaning | Threshold |
|--------|---------|-----------|
| **on_target** | KPI within healthy range | Value between warning & target |
| **warning** | KPI approaching problem zone | Between warning_threshold & critical_threshold |
| **critical** | KPI exceeds critical threshold | Below/above critical_threshold |

### Data Quality Scoring

```
Quality Score = (rows_processed / expected_rows) * 100
- 0-50%: Low confidence (flag for review)
- 50-80%: Medium confidence (acceptable)
- 80-100%: High confidence (reliable)
```

### Execution Performance

```
Typical Performance (100k records):
- SQL formulas: 1-2 seconds
- Python formulas: 2-4 seconds
- Excel formulas: 1-2 seconds
- Total with anomaly detection: 5-7 seconds
```

---

## 8. Django Admin Interface

### KPI Admin
- List view: Code, name, frequency (colored badge), target, status, last calculation
- Filters: Category, frequency, is_active
- Search: Name, code, description
- Fieldsets: Basic Info, Formula, Data Source, Thresholds, Schedule, Hierarchy

### KPI Calculation Admin
- List view: ID, KPI code, period, value, status (badge), variance, quality, timestamp
- Filters: Status, method, anomaly_detected, date range, category
- Date hierarchy: executed_at
- Fieldsets: KPI, Period, Result, Quality, Analysis, Management

### KPI Alert Admin
- List view: Alert name, KPI, condition, active (badge), triggered (badge), trigger count, last triggered
- Filters: Type, condition, is_active, is_triggered
- Search: Alert name, KPI name/code
- Fieldsets: Configuration, Condition, Notification, State, Cooldown, Acknowledgment

---

## 9. Integration with Notification System

### Alert Delivery

KPI alerts integrate with the notification system for multi-channel delivery:

```python
# From KPIAlertingService._send_alert_notifications()
from apps.notifications.services import NotificationService

notif_service = NotificationService(user)
notif_service.send_email_notification(
    recipients=alert.recipients,
    subject=f"KPI Alert: {alert.alert_name}",
    message=alert_message
)
```

### Supported Channels
- **Email**: HTML formatted with KPI details
- **Webhook**: JSON payload for custom integrations
- **Extensible**: Easy to add Slack, SMS, Teams, etc.

---

## 10. Permissions & Access Control

### Required Permissions

```python
# Read KPI data
'apps.kpi.view_kpi'
'apps.kpi.view_kpicalculation'
'apps.kpi.view_kpialert'

# Create/modify KPIs
'apps.kpi.add_kpi'
'apps.kpi.change_kpi'
'apps.kpi.delete_kpi'

# Manage alerts
'apps.kpi.add_kpialert'
'apps.kpi.change_kpialert'
'apps.kpi.delete_kpialert'
```

### Role-Based Access

| Role | Can View | Can Create | Can Calculate | Can Trigger Alerts |
|------|----------|-----------|---|---|
| Viewer | ✅ | ❌ | ❌ | ❌ |
| Analyst | ✅ | ✅ | ✅ | ✅ |
| Manager | ✅ | ✅ | ✅ | ✅ |
| Admin | ✅ | ✅ | ✅ | ✅ |

---

## 11. Configuration Options

### Application Settings

```python
# In settings.py or environment variables

# Calculation defaults
KPI_DEFAULT_FREQUENCY = 'monthly'
KPI_DEFAULT_AGGREGATION = 'SUM'
KPI_BATCH_SIZE = 50  # Calculate in batches

# Anomaly detection
KPI_ANOMALY_ZSCORE_THRESHOLD = 2.5
KPI_ANOMALY_LOOKBACK_PERIODS = 12

# Forecasting
KPI_FORECAST_MIN_PERIODS = 3  # Require 3+ historical periods
KPI_FORECAST_CONFIDENCE_LEVEL = 0.95  # 95% CI

# Alerts
KPI_ALERT_COOLDOWN_DEFAULT = 60  # minutes
KPI_ALERT_ESCALATION_TIMEOUT = 4  # hours

# Performance
KPI_QUERY_TIMEOUT = 30  # seconds
KPI_MAX_RECORDS_PER_CALCULATION = 10000
```

---

## 12. Troubleshooting

### Common Issues

**Formula Errors**
```
Issue: "Formula evaluation failed"
Check:
1. Formula syntax is correct (SQL or Python)
2. Table/column names are accurate
3. Period variables are properly formatted
4. Source table contains required data
```

**Low Data Quality Score**
```
Issue: "Data quality score < 60%"
Check:
1. Expected number of records in period
2. Any data filters are working correctly
3. Source table has complete data
Solution: Adjust threshold or investigate data gaps
```

**Anomaly False Positives**
```
Issue: "Alert triggered but data looks normal"
Check:
1. Historical data for anomaly detection exists (12+ periods)
2. Z-score threshold (2.5) is appropriate
3. Seasonal patterns are accounted for
Solution: Adjust threshold or use custom anomaly rules
```

**Alert Not Triggering**
```
Issue: "Alert configured but no notifications sent"
Check:
1. Alert is_active = true
2. Cooldown period hasn't elapsed
3. Notification channels configured
4. Recipient email addresses are valid
5. Webhook URL is accessible
```

---

## 13. Future Enhancements

- **Advanced Anomaly Detection**: Isolation Forest, DBSCAN clustering
- **Seasonal Decomposition**: Handle seasonal KPI patterns
- **Custom Threshold Rules**: ML-based dynamic thresholds
- **Drill-Down Analysis**: Interactive dashboard with drill-down
- **Export & Sharing**: Scheduled reports, PDF/email delivery
- **Version Control**: Track formula changes and rollback
- **ML-Based Forecasting**: Prophet, ARIMA models
- **Real-Time Streaming**: Sub-minute KPI updates from event sources

---

## Reference Files

- **Models**: [apps/kpi/models.py](apps/kpi/models.py)
- **Services**: [apps/kpi/services.py](apps/kpi/services.py)
- **APIs**: [apps/kpi/views.py](apps/kpi/views.py)
- **URLs**: [apps/kpi/urls.py](apps/kpi/urls.py)
- **Admin**: [apps/kpi/admin.py](apps/kpi/admin.py)
- **Serializers**: [apps/kpi/serializers.py](apps/kpi/serializers.py)
- **Tests**: [apps/kpi/tests.py](apps/kpi/tests.py)

