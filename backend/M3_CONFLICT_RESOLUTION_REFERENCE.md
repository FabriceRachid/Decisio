# M3: Résolution guidée des conflits inter-sources
## Guided Resolution of Inter-Source Conflicts

**Status:** ✅ Implemented
**Last Updated:** December 2024
**Scope:** Full implementation with auto-resolution + guided workflows

---

## 1. Overview

M3 is the conflict resolution module that detects, analyzes, and guides the resolution of data inconsistencies that arise from multiple data sources. It integrates with M1 (Ingestion) and M2 (Cleaning) to provide a complete data quality management pipeline.

### Key Capabilities

- **Automatic Detection**: Identifies 6 types of conflicts during/after data cleaning
- **Guided Workflows**: Step-by-step instructions for resolving each conflict type
- **Smart Guidance**: Context-aware recommendations based on conflict characteristics
- **Approval Workflows**: Support for multi-level approvals on critical resolutions
- **Full Audit Trail**: Comprehensive logging of all conflict-related activities
- **Dashboard Analytics**: Real-time conflict status and resolution metrics

---

## 2. Conflict Detection Architecture

### Detection Service

Location: `apps/conflits/services.py::ConflictDetectionService`

The service runs automatic detection across 6 conflict types:

#### 2.1 Duplicate Records Detection
```python
_detect_duplicates(source, source_type_code)
```
- **Method**: Hash-based record comparison (MD5 of all fields)
- **Threshold**: Flags if duplicate count ≥ 2
- **Severity**: MEDIUM (typically resolvable)
- **Fields Compared**: All non-ID fields
- **Return**: List of duplicate record groups with keys

**Example Scenario:**
```
Source API returns:
- Record A: {"name": "John", "email": "john@example.com", "date": "2024-01-01"}
- Record B: {"name": "John", "email": "john@example.com", "date": "2024-01-01"}
- Record C: {"name": "John", "email": "john@example.com", "date": "2024-01-02"}

Result: Record A & B flagged as duplicates (Record C not duplicate due to date)
```

#### 2.2 Missing Values Detection
```python
_detect_missing_values(source, field_threshold=0.2)
```
- **Method**: Field-level analysis, counts NULL/empty values
- **Threshold**: Flags if missing rate > 20% (configurable)
- **Severity**: HIGH (impacts analysis quality)
- **Failure Example**: Email field 45% empty = HIGH conflict
- **Return**: List of fields with missing percentages

**Threshold Calculation:**
```
Total Records = 1000
Missing Emails = 450
Percentage = 450/1000 = 45%

Since 45% > 20% threshold → HIGH severity conflict
```

#### 2.3 Data Type Issues
```python
_detect_data_type_issues(source, source_type_code)
```
- **Method**: Type consistency analysis via Counter
- **Detection**: Checks if field has multiple types (string, int, float, datetime, bool)
- **Threshold**: Flags if field has 2+ different types
- **Severity**: CRITICAL (blocks analysis)
- **Return**: List of fields with type distribution

**Example Scenario:**
```
Age field contains:
- "25" (string) - 40% of records
- 25 (integer) - 50% of records  
- None (null) - 10% of records

Result: Type mismatch detected (string vs int)
Guidance: Convert all to integer or string
```

#### 2.4 Format Inconsistencies
```python
_detect_format_issues(source, source_type_code)
```
- **Method**: Regex pattern matching for known formats
- **Patterns Checked**:
  - Email: `/^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/`
  - Phone: `/^\+?[1-9]\d{1,14}$/` (E.164 standard)
  - Date: Multiple formats (YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY)
  - UUID: `/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i`
- **Threshold**: Flags if any non-matching values exist
- **Severity**: HIGH (needs standardization)
- **Return**: List of fields with format violations

**Example Scenario:**
```
Email field contains:
- valid@example.com ✓
- invalid.email ✗
- another@domain.co.uk ✓
- missing domain! ✗

Result: 2 emails don't match pattern
Severity: HIGH (40% invalid)
```

#### 2.5 Cross-Source Contradictions
```
Detected by comparing same logical record across sources
E.g., CustomerID 123 has:
- Source A: Email john@old.com
- Source B: Email john@new.com
```

#### 2.6 Automatic Integration with M2

Triggered automatically after cleaning completes:

```python
# In nettoyage/tasks.py::apply_cleaning_async()
from apps.conflits.services import ConflictDetectionService

conflict_service = ConflictDetectionService(user)
conflict_result = conflict_service.detect_conflicts_in_source(
    source=source,
    check_types=[
        'DUPLICATE_RECORDS',
        'MISSING_VALUES',
        'DATA_TYPE_MISMATCH',
        'FORMAT_INCONSISTENCY'
    ]
)

# Non-blocking: wrapped in try/except
if conflict_result['total_conflicts'] > 0:
    logger.warning(f"Detected {conflict_result['total_conflicts']} conflicts...")
```

---

## 3. Guided Resolution Workflows

### Resolution Service

Location: `apps/conflits/services.py::ConflictResolutionService`

#### 3.1 Guidance Generation

```python
get_conflict_resolution_guidance(conflict) → GuidanceObject
```

Returns a comprehensive guidance object with:

```python
{
    'conflict_id': uuid,
    'conflict_type': 'DUPLICATE_RECORDS',
    'guidance': 'How to resolve duplicates...',
    'recommended_strategy': 'CONSOLIDATE',
    'alternative_strategies': ['MERGE', 'KEEP_LATEST'],
    'impact_analysis': {
        'affected_records': 150,
        'dependent_reports': 3,
        'estimated_breakage_risk': 0.15
    },
    'steps': [
        {'step_number': 1, 'action': 'Review duplicate records'},
        {'step_number': 2, 'action': 'Choose consolidation method'},
        ...
    ],
    'estimated_effort': 30,  # minutes
    'risk_level': 'MEDIUM'  # LOW, MEDIUM, HIGH, CRITICAL
}
```

#### 3.2 Conflict-Type-Specific Guidance

**Duplicate Records Resolution:**
```
Recommended Strategy: CONSOLIDATE
Steps:
1. Identify canonical record (usually most recent)
2. Merge field values (keep non-empty, prioritize latest)
3. Update foreign key references
4. Delete duplicate record
5. Log consolidation action

Alternative Strategies:
- MERGE: Combine data from all duplicates
- KEEP_LATEST: Keep only most recent record
- MANUAL_REVIEW: Defer to data steward
```

**Missing Values Resolution:**
```
Recommended Strategy: IMPUTATION (if >50% missing) or QUARANTINE (if <20%)
Steps:
1. Determine missing data pattern (random, systematic)
2. Choose imputation method:
   - For numeric: mean/median/mode
   - For categorical: most frequent value
   - For dates: use creation date or interpolate
3. Apply imputation
4. Flag records as imputed (with confidence score)

Risk Level: HIGH (can introduce false data)
Alternative Strategies:
- EXCLUDE: Filter out records with missing values
- MANUAL_FILL: Have analysts manually review
- INTERPOLATE: Use similar records to infer values
```

**Data Type Mismatch Resolution:**
```
Recommended Strategy: CONVERT_TO_MOST_COMMON
Steps:
1. Identify most common type (distribution analysis)
2. Convert minority types to majority type
3. Flag conversion for review (e.g., may lose precision)
4. Test conversion success rate
5. Rollback if >5% conversion failures

Impact: High risk for custom types
Alternative Strategies:
- CONVERT_TO_STRING: Safest (no data loss)
- SEPARATE_FIELDS: Create two fields (one per type)
- MANUAL_REVIEW: Defer to data steward
```

**Format Inconsistencies Resolution:**
```
Recommended Strategy: STANDARDIZE
Steps:
1. Parse multiple format variants
2. Convert all to canonical format
3. Flag non-standard values
4. Validate against pattern

For Email:
- Canonical: lowercase, remove whitespace
- Invalid → move to alternate field, flag for review

For Phone Numbers:
- Canonical: E.164 format (+1234567890)
- Variants: (123) 456-7890 → +11234567890

Risk: LOW (format change only, no data loss)
```

---

## 4. API Endpoints

### Base URL: `/api/conflits/`

#### 4.1 Conflict Type Management

**List Conflict Types**
```
GET /api/conflits/types/
Response:
[
    {
        "id": "uuid",
        "name": "Duplicate Records",
        "code": "DUPLICATE_RECORDS",
        "description": "...",
        "severity": "medium",
        "auto_resolve": false,
        "resolution_strategy": "manual_review",
        "icon": "⚠️",
        "color_code": "#FFC107"
    }
]
```

#### 4.2 Conflict Management

**List Conflicts**
```
GET /api/conflits/conflicts/?status=detected&priority=high&severity=critical
Response:
{
    "count": 15,
    "next": "...",
    "results": [
        {
            "id": "uuid",
            "conflict_type": "DUPLICATE_RECORDS",
            "source_name": "API Alpha",
            "description": "500 duplicate customer records",
            "status": "detected",
            "priority": "high",
            "detected_at": "2024-01-15T10:30:00Z",
            "assigned_to": null,
            "impact_score": 0.85,
            "resolution_count": 0
        }
    ]
}
```

**Get Conflict Details**
```
GET /api/conflits/conflicts/{id}/
Response:
{
    "id": "uuid",
    "conflict_type": {...},
    "source_name": "API Alpha",
    "description": "...",
    "affected_table": "customers",
    "affected_columns": ["email", "name"],
    "affected_row_ids": [123, 124, 125],
    "conflict_details": {"duplicate_groups": [[123, 124]]},
    "status": "detected",
    "priority": "high",
    "assigned_to": null,
    "detected_at": "2024-01-15T10:30:00Z",
    "resolutions": [
        {"id": "...", "method": "CONSOLIDATE", "resolved_at": "..."}
    ]
}
```

**Get Resolution Guidance**
```
GET /api/conflits/conflicts/{id}/guidance/
Response:
{
    "conflict_id": "uuid",
    "conflict_type": "DUPLICATE_RECORDS",
    "guidance": "To resolve duplicate records...",
    "recommended_strategy": "CONSOLIDATE",
    "alternative_strategies": ["MERGE", "KEEP_LATEST"],
    "impact_analysis": {
        "affected_records": 200,
        "dependent_reports": 3,
        "estimated_breakage_risk": 0.15
    },
    "steps": [
        {"step_number": 1, "action": "Review the 200 duplicate records"},
        {"step_number": 2, "action": "Choose consolidation method"},
        ...
    ],
    "estimated_effort": 45,
    "risk_level": "MEDIUM"
}
```

**Acknowledge Conflict**
```
POST /api/conflits/conflicts/{id}/acknowledge/
Request: {}
Response:
{
    "id": "uuid",
    "status": "investigating",
    "acknowledged_by": "john@example.com",
    "acknowledged_at": "2024-01-15T11:00:00Z"
}
```

**Assign Conflict**
```
POST /api/conflits/conflicts/{id}/assign/
Request:
{
    "assigned_to": "analyst@example.com",
    "due_date": "2024-01-20"
}
Response:
{
    "id": "uuid",
    "assigned_to": "analyst@example.com",
    "due_date": "2024-01-20"
}
```

**Resolve Conflict**
```
POST /api/conflits/conflicts/{id}/resolve/
Request:
{
    "resolution_method": "CONSOLIDATE",
    "chosen_value": "primary_record_id_123",
    "resolution_notes": "Consolidated 5 duplicate customer records",
    "approval_required": true
}
Response:
{
    "id": "uuid",
    "status": "resolved",
    "resolution": {
        "id": "res_uuid",
        "method": "CONSOLIDATE",
        "confidence_score": 0.95,
        "resolved_by": "analyst@example.com",
        "approval_status": "pending"
    }
}
```

**Bulk Actions**
```
POST /api/conflits/conflicts/bulk_action/
Request:
{
    "conflict_ids": ["uuid1", "uuid2", "uuid3"],
    "action": "assign",
    "assigned_to": "team_lead@example.com",
    "priority": "critical",
    "status": "investigating"
}
Response:
{
    "updated_count": 3,
    "message": "3 conflicts assigned to team_lead@example.com"
}
```

**Dashboard Statistics**
```
GET /api/conflits/conflicts/dashboard_stats/
Response:
{
    "total_conflicts": 245,
    "by_status": {
        "detected": 150,
        "investigating": 45,
        "resolving": 30,
        "resolved": 15,
        "ignored": 5
    },
    "by_severity": {
        "low": 50,
        "medium": 100,
        "high": 80,
        "critical": 15
    },
    "by_type": {
        "DUPLICATE_RECORDS": 100,
        "MISSING_VALUES": 80,
        "DATA_TYPE_MISMATCH": 40,
        "FORMAT_INCONSISTENCY": 25
    },
    "critical_conflicts": 15,
    "avg_resolution_time_hours": 8.5,
    "resolution_success_rate": 0.92,
    "pending_approvals": 5
}
```

#### 4.3 Manual Conflict Detection

**Trigger Manual Detection**
```
POST /api/conflits/detect/
Request:
{
    "source_id": "uuid",
    "conflict_types": ["DUPLICATE_RECORDS", "MISSING_VALUES"]
}
Response:
{
    "detection_task_id": "task_uuid",
    "status": "started",
    "message": "Detection started, will be processed asynchronously"
}
```

#### 4.4 Resolution History

**List Resolutions**
```
GET /api/conflits/resolutions/?conflict_id=uuid
Response:
[
    {
        "id": "res_uuid",
        "conflict": "conflict_uuid",
        "method": "CONSOLIDATE",
        "confidence_score": 0.95,
        "resolved_by": "analyst@example.com",
        "resolved_at": "2024-01-15T14:30:00Z",
        "approval_required": true,
        "approved_by": "manager@example.com",
        "approved_at": "2024-01-15T15:00:00Z"
    }
]
```

#### 4.5 Audit Trail

**List Activity Log**
```
GET /api/conflits/activity-log/?action_type=resolution_approved
Response:
[
    {
        "id": "uuid",
        "user_email": "manager@example.com",
        "action_type": "resolution_approved",
        "resource_type": "ConflictResolution",
        "action_details": {"resolution_id": "...", "status": "approved"},
        "status_code": 200,
        "created_at": "2024-01-15T15:00:00Z",
        "ip_address": "192.168.1.1"
    }
]
```

---

## 5. Data Models

### ConflictType
```python
class ConflictType(BaseModel):
    """Defines types of conflicts the system can detect"""
    name: str  # "Duplicate Records"
    code: str  # "DUPLICATE_RECORDS" (unique, immutable)
    description: str
    severity: str  # low, medium, high, critical
    auto_resolve: bool  # Can system auto-resolve?
    resolution_strategy: str  # auto_merge, manual_review, consolidate, etc.
    icon: str?  # Emoji or icon name
    color_code: str?  # UI display color
    documentation_url: str?
```

### Conflict
```python
class Conflict(BaseModel):
    """Detected conflict in data source"""
    data_source: ForeignKey  # M1 DataSource
    conflict_type: ForeignKey  # Type of conflict
    description: str
    status: str  # detected, investigating, resolving, resolved, ignored
    priority: str  # low, medium, high, critical
    
    # Affected data
    affected_table: str
    affected_columns: JSONField  # ["email", "name"]
    affected_row_ids: JSONField  # [123, 124, 125]
    conflict_details: JSONField  # Type-specific data
    
    # Management
    assigned_to: ForeignKey?  # User
    due_date: DateTime?
    detected_by: ForeignKey  # User
    detected_at: DateTime
    
    # Tracking
    acknowledged_by: ForeignKey?  # User
    acknowledged_at: DateTime?
    
    # Metrics
    impact_score: Float  # 0.0 - 1.0
    estimated_resolution_time: Int  # minutes
    
    # Resolution
    resolutions: Reverse relation  # ConflictResolutions
    resolved_at: DateTime?
    resolution_summary: str?
    
    # Optional
    parent_conflict: ForeignKey?  # For conflict hierarchies
    recurrence_id: str?  # Track if conflict re-occurs
```

### ConflictResolution
```python
class ConflictResolution(BaseModel):
    """Records how a conflict was resolved"""
    conflict: ForeignKey  # Conflict
    resolution_method: str  # consolidate, merge, impute, exclude, manual_override
    chosen_value: str  # What value was chosen
    alternative_values: JSONField?  # Other options considered
    resolution_notes: str
    confidence_score: Float  # 0.0 - 1.0
    is_reversible: bool  # Can it be rolled back?
    rollback_data: JSONField?  # Original data for rollback
    
    # Approval workflow
    approval_required: bool
    reviewed_by: ForeignKey?  # User
    reviewed_at: DateTime?
    approved_by: ForeignKey?  # User
    approved_at: DateTime?
    
    # Metadata
    resolved_by: ForeignKey  # User
    resolved_at: DateTime
```

### ActivityLog
```python
class ActivityLog(BaseModel):
    """Audit trail for all conflict-related activities"""
    user: ForeignKey?  # User
    action_type: str  # conflict_detected, conflict_acknowledged, resolution_applied
    resource_type: str  # Conflict, ConflictResolution
    resource_id: str
    resource_name: str
    action_details: JSONField
    status_code: Int  # HTTP or operation status
    response_time_ms: Int?
    
    # Security tracking
    ip_address: str
    user_agent: str?
    session_id: str?
    risk_score: Float?
    flagged_for_review: bool
    reviewed_by: ForeignKey?
    reviewed_at: DateTime?
    
    # Location
    country: str?
    city: str?
    
    created_at: DateTime (auto_now_add)
```

---

## 6. Permissions & Access Control

### Required Permissions

```python
# Read conflicts
'apps.conflits.view_conflict'

# Acknowledge conflicts (mark as investigating)
'apps.conflits.change_conflict'

# Assign conflicts
'apps.conflits.change_conflict' + is_team_lead or is_manager

# Resolve conflicts
'apps.conflits.change_conflict' + is_analyst

# Approve resolutions (if required)
'apps.conflits.change_conflictresolution' + is_manager

# Access audit trail
'apps.conflits.view_activitylog'
```

### User Roles

| Role | Can View | Can Acknowledge | Can Assign | Can Resolve | Can Approve |
|------|----------|-----------------|-----------|------------|------------|
| Analyst | ✅ | ✅ | ❌ | ✅ | ❌ |
| Team Lead | ✅ | ✅ | ✅ | ✅ | ❌ |
| Manager | ✅ | ✅ | ✅ | ✅ | ✅ |
| Data Steward | ✅ | ✅ | ❌ | ❌ | ❌ |
| Admin | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 7. Resolution Strategies Reference

### CONSOLIDATE
- **Use Case**: Duplicate records
- **Process**: Keep canonical record, merge non-empty fields, delete duplicates
- **Risk**: Medium (may lose some field values if not merged properly)
- **Reversible**: Yes (with rollback data)

### MERGE
- **Use Case**: Incomplete records from same entity
- **Process**: Combine all unique non-empty values from multiple records
- **Risk**: Medium (may create invalid combinations)
- **Reversible**: Yes

### MAJORITY_VOTE
- **Use Case**: Conflicting values across sources
- **Process**: Keep most common value across sources
- **Risk**: Low (data-driven decision)
- **Reversible**: Yes

### AUTO_MERGE
- **Use Case**: Non-conflicting fields from different sources
- **Process**: Automatically combine non-overlapping fields
- **Risk**: Low (no manual intervention needed)
- **Reversible**: Yes

### IMPUTE
- **Use Case**: Missing values
- **Process**: Fill missing with statistical method (mean, median, mode, forward-fill)
- **Risk**: High (introduces synthetic data)
- **Reversible**: Yes (track imputation with confidence score)

### EXCLUDE
- **Use Case**: Unsalvageable records or low-confidence fixes
- **Process**: Remove conflicting records from analysis
- **Risk**: Low (conservative approach)
- **Reversible**: Yes (archive excluded records)

### MANUAL_OVERRIDE
- **Use Case**: Any conflict with context-dependent decision
- **Process**: Flag for human analyst, record final decision
- **Risk**: Variable (depends on analyst decision)
- **Reversible**: Yes

---

## 8. Integration Points

### M1: Ingestion ↔ M3: Conflicts

**Trigger**: After data ingestion completes
**Flow**:
1. M1 ingests data from source
2. Data stored in DataSource model
3. Conflict detection can be triggered manually or automatically

**Use Case**: Identify conflicts immediately after new data arrives

### M2: Cleaning ↔ M3: Conflicts

**Trigger**: After cleaning rules applied
**Flow**:
1. M2 applies cleaning rules to data
2. Cleaned data saved to staging table
3. M3 automatically detects new conflicts in cleaned data
4. Conflicts logged and made available for resolution

**Code Location**: `apps/nettoyage/tasks.py::apply_cleaning_async()`

```python
# After cleaning completes
from apps.conflits.services import ConflictDetectionService

conflict_service = ConflictDetectionService(user)
conflict_result = conflict_service.detect_conflicts_in_source(
    source=source,
    check_types=['DUPLICATE_RECORDS', 'MISSING_VALUES', 'DATA_TYPE_MISMATCH']
)

if conflict_result['total_conflicts'] > 0:
    logger.warning(f"Detected {conflict_result['total_conflicts']} conflicts after cleaning")
```

### Dashboard Integration

**Provides**:
- Conflict summary statistics
- By status, severity, type breakdowns
- Resolution rate metrics
- Average resolution time
- Pending approvals count

---

## 9. Django Admin Interface

### Models Registered

**ConflictType Admin**
- List view: name, code, severity (colored badge), auto_resolve, strategy
- Filters: severity, auto_resolve, created_at
- Search: name, code, description
- Fieldsets: Basic Info, Resolution Strategy, UI Configuration, Documentation

**Conflict Admin**
- List view: ID, type, source, status (colored badge), priority, assigned_to, detected_at
- Filters: status, severity, detected_at
- Search: source name, description, conflict type
- Fieldsets: Basic Info, Affected Data, Conflict Details, Management, Tracking, Resolution
- Actions:
  - Mark as resolved
  - Mark as ignored
  - Assign to me

**ConflictResolution Admin**
- List view: ID, conflict, method, confidence score, resolved_by, approval status
- Filters: method, approval_required, resolved_at
- Fieldsets: Conflict, Resolution, Quality, Review & Approval

**ActivityLog Admin**
- List view: ID, user email, action type, resource type, status code, flagged badge
- Filters: action_type, resource_type, status_code, flagged_for_review, created_at
- Search: user email, resource name, IP address
- Fieldsets: User, Action, Details, Response, Security, Location

---

## 10. Testing Strategy

### Unit Tests (services.py)

Test each detection method:
- `test_detect_duplicates_identifies_exact_matches()`
- `test_detect_missing_values_above_threshold()`
- `test_detect_missing_values_below_threshold()`
- `test_detect_type_issues_mixed_types()`
- `test_detect_format_issues_invalid_email()`
- `test_detect_format_issues_valid_formats()`

Test resolution service:
- `test_guidance_duplicate_records()`
- `test_guidance_missing_values()`
- `test_guidance_type_mismatch()`
- `test_resolve_conflict_records_decision()`
- `test_resolve_conflict_requires_approval()`

### Integration Tests (views.py + services.py)

- `test_list_conflicts_with_filters()`
- `test_get_conflict_detail()`
- `test_get_guidance_returns_steps()`
- `test_acknowledge_conflict_changes_status()`
- `test_assign_conflict_to_user()`
- `test_resolve_conflict_via_api()`
- `test_bulk_action_assigns_multiple()`
- `test_dashboard_stats_returns_metrics()`

### End-to-End Tests

- Full workflow: Detect → Acknowledge → Get Guidance → Resolve → Approve
- Try different resolution methods and verify outcomes
- Verify audit trail is properly logged
- Test approval workflow (required vs not required)

---

## 11. Performance Considerations

### Detection Performance

For a source with 100k records:
- Hash-based duplicate detection: ~2 seconds
- Missing value analysis: ~1 second
- Type consistency check: ~1 second
- Format validation: ~3 seconds (regex operations)

**Total**: ~7 seconds for full detection

### Optimization Options

1. **Incremental Detection**: Only check newly ingested rows
2. **Sampling**: Check sample of data for large tables (>1M rows)
3. **Async Processing**: Run detection in background Celery task
4. **Caching**: Cache ConflictType lookups and regex patterns

### Database Indexes

Add indexes on:
```sql
CREATE INDEX idx_conflict_status ON conflicts(status);
CREATE INDEX idx_conflict_assigned_to ON conflicts(assigned_to_id);
CREATE INDEX idx_conflict_detected_at ON conflicts(detected_at);
CREATE INDEX idx_activitylog_user ON activity_log(user_id);
CREATE INDEX idx_activitylog_created ON activity_log(created_at);
```

---

## 12. Configuration & Customization

### System Configuration (via SystemConfig or settings.py)

```python
# Conflict detection thresholds
CONFLICT_MISSING_VALUE_THRESHOLD = 0.20  # 20%
CONFLICT_DUPLICATE_MIN_COUNT = 2
CONFLICT_FORMAT_STRICT_MODE = False

# Resolution defaults
CONFLICT_DEFAULT_PRIORITY = 'medium'
CONFLICT_DEFAULT_STRATEGY = 'manual_review'
CONFLICT_REQUIRES_APPROVAL_FOR_CRITICAL = True
CONFLICT_APPROVAL_TIMEOUT_DAYS = 3

# Performance
CONFLICT_DETECTION_ASYNC = True
CONFLICT_BATCH_SIZE = 1000
CONFLICT_MAX_AFFECTED_ROWS = 10000
```

### Adding Custom Conflict Types

1. Create instance in admin:
   - Name: "Custom Check"
   - Code: "CUSTOM_CHECK"
   - Severity: "high"
   - Strategy: "manual_review"

2. Add detection logic in `ConflictDetectionService._detect_conflicts_in_source()`

3. Add guidance method in `ConflictResolutionService._guide_custom_check()`

---

## 13. Troubleshooting

### Issue: Conflicts not detected after cleaning

**Check**:
1. Is conflict detection async enabled? Check Celery is running
2. Are background tasks processing? Check Celery logs
3. Is detection triggered in apply_cleaning_async()? Check tasks.py

**Solution**:
```bash
# Check Celery status
celery -A decisiobi inspect active

# Run manual detection
python manage.py shell
>>> from apps.conflits.services import ConflictDetectionService
>>> service = ConflictDetectionService(user)
>>> result = service.detect_conflicts_in_source(source)
>>> print(result['total_conflicts'])
```

### Issue: Approval workflow not working

**Check**:
1. Is `approval_required` set on ConflictType?
2. Does user have approval permission?
3. Is `ApprovedBy` set when resolving?

**Solution**: Check ConflictResolution.approval_required flag and user permissions

### Issue: Audit trail not recording activities

**Check**:
1. Is ActivityLogMiddleware enabled? Check settings.py
2. Are signals working? Check Django signals
3. Is user authenticated? Check request.user

**Solution**: Enable logging in views.py by calling `ConflictAuditLog.log_activity()`

---

## 14. Future Enhancements

- **Machine Learning**: Auto-resolution using ML on historical resolutions
- **Custom Rules Engine**: Allow users to define custom conflict detection rules
- **Batch Resolution**: Apply resolution patterns across multiple similar conflicts
- **Predictive SLA**: Automatically calculate due dates based on conflict type
- **Collaboration**: @mention other analysts in conflict resolution comments
- **Export/Reporting**: Generate conflict reports for data quality dashboards
- **Integration**: Sync resolutions back to source systems

---

## Reference Files

- **Models**: `apps/conflits/models.py`
- **Services**: `apps/conflits/services.py`
- **APIs**: `apps/conflits/views.py`
- **URLs**: `apps/conflits/urls.py`
- **Admin**: `apps/conflits/admin.py`
- **Serializers**: `apps/conflits/serializers.py`
- **Tests**: `apps/conflits/tests.py`
- **Integration**: `apps/nettoyage/tasks.py`

