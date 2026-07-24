# M1 (Ingestion) Module - Comprehensive Structural Overview

## 1. MODELS (models.py)

### DataSource Model
**Purpose**: Metadata about uploaded data sources (files, API connections, etc.). Tracks dataset information without storing actual data.

**Fields**:
- `id` (PK): Auto-generated primary key
- `name` (CharField, 200): Source name
- `source_type` (CharField, 20): Choices: 'csv', 'excel', 'api', 'database', 'json'
- `file_path` (CharField, 500, nullable): Relative path to stored file
- `file_size_bytes` (BigIntegerField, nullable): File size in bytes
- `row_count` (IntegerField, nullable): Number of data rows extracted
- `column_count` (IntegerField, nullable): Number of columns
- `delimiter` (CharField, 10, default=','): Column delimiter for CSV files
- `encoding` (CharField, 20, default='utf-8'): File encoding
- `has_header` (BooleanField, default=True): Whether first row contains headers
- `uploaded_by` (ForeignKey → User, CASCADE): User who uploaded the file
- `status` (CharField, 20): Choices: 'pending', 'processing', 'completed', 'failed' (default='pending')
- `validation_errors` (JSONField, default=[]): Validation issues found
- `metadata` (JSONField, default={}): Additional metadata (columns, dtypes, schema profile, duplicates summary, validation summary, template info, column mapping)
- `checksum_md5` (CharField, 32, nullable): MD5 hash to detect duplicate files
- `retention_days` (IntegerField, default=90): Data retention period in days
- `is_archived` (BooleanField, default=False): Soft-delete flag
- `description` (TextField, nullable): Human-readable description
- `tags` (JSONField, default=[]): Tags for categorization
- `schema_version` (IntegerField, default=1): Schema version number for versioning
- `parent_source` (ForeignKey → self, SET_NULL, nullable): Links to previous version
- `lineage_info` (JSONField, default={}): Data provenance information
- `created_at` (DateTimeField, auto_now_add=True): Creation timestamp
- `updated_at` (DateTimeField, auto_now=True): Last update timestamp
- `processed_at` (DateTimeField, nullable): When ingestion completed

**Methods**:
- `__str__()`: Returns "{name} ({source_type})"

**Meta**:
- `db_table`: 'ingestion_datasource'
- `ordering`: ['-created_at']
- Related name from IngestionJob: `ingestion_job` (OneToOneField)
- Related name from RawData: `raw_data_rows` (ForeignKey)

---

### RawData Model
**Purpose**: Stores raw data rows from uploaded sources using JSONB for flexible schema.

**Fields**:
- `id` (PK): Auto-generated primary key
- `source` (ForeignKey → DataSource, CASCADE): Link to parent DataSource
- `row_number` (IntegerField): Original row number in source file
- `data` (JSONField): Raw row data as JSON object
- `data_hash` (CharField, 64, nullable): SHA256 hash to detect duplicate rows
- `validation_status` (CharField, 20): Choices: 'valid', 'invalid', 'warning' (default='valid')
- `validation_messages` (JSONField, default=[]): List of validation issues
- `partition_key` (IntegerField, nullable): For partitioning large datasets
- `is_sample` (BooleanField, default=False): Whether this is a sample row
- `extraction_batch` (IntegerField, nullable): Batch processing ID
- `ingested_at` (DateTimeField, auto_now_add=True): Ingestion timestamp

**Methods**:
- `__str__()`: Returns "Row {row_number} from {source.name}"

**Meta**:
- `db_table`: 'ingestion_rawdata'
- `unique_together`: ['source', 'row_number'] (ensures no duplicate row numbers per source)
- `indexes`: Index on ['source', 'row_number']

---

### IngestionJob Model
**Purpose**: Tracks async ingestion jobs for file uploads. Enables long-running uploads without blocking requests.

**Fields**:
- `id` (PK): Auto-generated primary key
- `celery_task_id` (CharField, 200, unique): Celery task ID for tracking
- `source` (OneToOneField → DataSource, CASCADE, nullable): Associated DataSource
- `status` (CharField, 20): Choices: 'queued', 'processing', 'completed', 'failed', 'cancelled' (default='queued')
- `progress_percent` (IntegerField, default=0): Completion percentage (0-100)
- `error_message` (TextField, nullable): Error description if failed
- `started_at` (DateTimeField, nullable): When processing started
- `completed_at` (DateTimeField, nullable): When processing finished
- `created_at` (DateTimeField, auto_now_add=True): Job creation timestamp

**Methods**:
- `__str__()`: Returns "IngestionJob {celery_task_id} - {status}"

**Meta**:
- `db_table`: 'ingestion_ingestionjob'
- `ordering`: ['-created_at']

---

## 2. SERVICES (services.py)

### Custom Exception
**IngestionError(Exception)**: Raised when an uploaded file cannot be ingested.

---

### ERP Import Templates Dictionary
`ERP_IMPORT_TEMPLATES`: Predefined configurations for common ERP data sources.

**Templates Available**:
1. **erp_sales_export**
   - For: Sales invoices or ERP sales journal exports
   - Required columns: document_no, customer_code, document_date, amount, currency
   - Key columns: document_no

2. **erp_inventory_export**
   - For: Inventory stock snapshots by product and warehouse
   - Required columns: sku, warehouse_code, stock_quantity
   - Key columns: sku, warehouse_code

3. **erp_customer_master**
   - For: Customer master data
   - Required columns: customer_code, customer_name, country
   - Key columns: customer_code

4. **erp_supplier_master**
   - For: Supplier/vendor master data
   - Required columns: supplier_code, supplier_name, country
   - Key columns: supplier_code

5. **erp_gl_entries**
   - For: General ledger journal entries
   - Required columns: entry_no, account_code, posting_date, debit, credit
   - Key columns: entry_no, account_code

Each template contains:
- `label`: Human-readable name
- `description`: Purpose description
- `dataset_type`: Type category
- `required_columns`: Mandatory columns
- `key_columns`: Columns defining unique rows
- `column_aliases`: Alternative column names for matching
- `business_rules`: Validation rules (required_non_empty, positive_number, non_negative_number, allowed_values, date_parseable)

---

### Main Service Functions

#### `preview_uploaded_file(**kwargs) → dict`
**Purpose**: Analyze a source file before import without persisting.

**Parameters**:
- `user`: User object
- `uploaded_file`: File upload object
- `source_type`: 'csv', 'excel', 'json'
- `delimiter`: Column delimiter
- `encoding`: File encoding
- `has_header`: Boolean
- `required_columns`: List of required column names
- `key_columns`: List of key column names
- `template_id`: Optional template ID
- `column_mapping`: Optional column name mapping

**Returns**: Dictionary with:
- `filename`: Original filename
- `source_type`: Detected source type
- `checksum_md5`: MD5 hash
- `file_size_bytes`: Total bytes
- `row_count`: Number of data rows
- `column_count`: Number of columns
- `metadata`: Schema profile, duplicates summary, validation summary
- `validation_errors`: List of validation issues
- `sample_rows`: First 10 rows with validation status
- `can_import`: Boolean indicating if file is importable

---

#### `list_import_templates() → list`
**Purpose**: Get list of available ERP import templates.

**Returns**: List of template dictionaries with id, label, description, dataset_type, required_columns, key_columns, business_rules (sorted by label)

---

#### `ingest_uploaded_file(**kwargs) → DataSource`
**Purpose**: Upload, validate, and persist a data source with raw data rows.

**Parameters**: Same as `preview_uploaded_file` plus:
- `name`: Name for the DataSource record
- `description`: Description text
- `tags`: List of tag strings
- `retention_days`: Data retention period
- `strict_validation`: If True, reject files with validation errors

**Process**:
1. Analyzes file using `_analyze_file_bytes()`
2. Checks strict validation if required
3. Stores file to disk using FileSystemStorage
4. Creates DataSource record with metadata
5. Creates RawData records for each row via bulk_create
6. Sets is_sample=True for first 10 rows

**Returns**: Created DataSource instance

**Raises**: IngestionError if strict_validation fails

---

### Helper Functions

#### `_analyze_file_bytes(**kwargs) → dict`
**Purpose**: Core analysis function - loads, validates, and profiles a file.

**Key Operations**:
- Loads DataFrame using pandas
- Normalizes column names (lowercase, underscores)
- Applies column mapping and template aliases
- Detects duplicate rows by content hash
- Detects duplicate files by MD5 checksum
- Detects duplicate key combinations
- Applies business rules validation
- Builds schema profile
- Returns comprehensive analysis dictionary

---

#### `_load_dataframe(*, source_bytes, source_type, delimiter, encoding, has_header) → pd.DataFrame`
**Purpose**: Load file bytes into pandas DataFrame.

**Supports**: CSV, JSON (standard and line-delimited), Excel

---

#### `_hash_row(row) → str`
**Purpose**: Generate SHA256 hash of a row for duplicate detection.

---

#### `_normalize_row(row) → dict`
**Purpose**: Convert all keys and values to standard format.

---

#### `_build_schema_profile(dataframe) → list`
**Purpose**: Create detailed column metadata.

**Returns**: List of column profiles with:
- name, dtype, null_count, non_null_count, unique_count, sample_values

---

#### `_build_validation_errors(**kwargs) → list`
**Purpose**: Compile all validation issues found during analysis.

**Returns**: List of error dictionaries with severity, code, message, details

---

#### `_build_row_validation_results(**kwargs) → list`
**Purpose**: Validate each row individually.

**Returns**: List of row validation results with:
- row_number, data, status ('valid'/'invalid'/'warning'), messages

---

#### `_duplicate_indexes(values) → list`
**Purpose**: Find row numbers with duplicate content hashes.

---

#### `_duplicate_key_rows(rows, key_columns) → dict`
**Purpose**: Find rows with duplicate key combinations.

---

#### `_build_preview_response(analysis) → dict`
**Purpose**: Format analysis for API response.

---

#### `_apply_column_mapping(dataframe, **, template_config, column_mapping) → tuple`
**Purpose**: Rename columns based on template aliases and custom mapping.

**Returns**: (modified_dataframe, mapping_dict)

---

#### `_resolve_template_config(template_id) → dict`
**Purpose**: Retrieve template configuration or empty dict if not found.

---

#### `_normalize_dataframe_columns(dataframe) → pd.DataFrame`
**Purpose**: Standardize column names using `_canonicalize_column_name()`.

---

#### `_canonicalize_column_name(value) → str`
**Purpose**: Convert column name to canonical form (lowercase, underscores).

---

#### `_merge_unique(base_values, extra_values) → list`
**Purpose**: Merge and deduplicate column lists.

---

#### `_apply_business_rules(row, business_rules) → list`
**Purpose**: Validate row against business rules from template.

**Rules Supported**:
- `required_non_empty`: Column must have value
- `positive_number`: Column must be > 0
- `non_negative_number`: Column must be >= 0
- `allowed_values`: Column must match one of allowed values (with optional case_insensitive)
- `date_parseable`: Column must be parseable as date

**Returns**: List of validation messages with severity, code, column, message

---

#### `_resolve_row_status(messages) → str`
**Purpose**: Determine row validation status from messages.

**Logic**:
- 'invalid' if any message has severity='error'
- 'warning' if any message exists
- 'valid' otherwise

---

#### `_to_float(value) → float | None`
**Purpose**: Safely convert value to float.

---

## 3. VIEWS (views.py)

### ViewSet/View Classes

#### `ImportTemplateListView(APIView)`
**Purpose**: List available ERP import presets.

**Endpoint**: `GET /api/ingestion/templates/`

**Permission**: CanReadData

**Method**:
- `get(request)`: Returns JSON array of templates

**Response**: 200 OK with `{'results': [template, ...]}`

---

#### `DataSourceListView(generics.ListAPIView)`
**Purpose**: List uploaded data sources visible to user with filtering.

**Endpoint**: `GET /api/ingestion/sources/`

**Permission**: CanReadData

**Serializer**: DataSourceListSerializer

**Features**:
- DjangoFilterBackend: Filter by status, source_type, created_at
- SearchFilter: Search in name, description, tags
- OrderingFilter: Order by created_at, name, row_count
- Tag filtering: Via query_params.getlist('tags')
- Multi-user: Admins see all, others see only their own
- Default ordering: '-created_at'

**Query Parameters**:
- `status`: pending, processing, completed, failed
- `source_type`: csv, excel, api, database, json
- `tags`: Filter by tags (can be multiple)
- `created_after`: Filter by creation date (ISO format)
- `uploaded_by`: Username (admin only)
- `search`: Text search
- `ordering`: Field name

---

#### `DataSourceDetailView(generics.RetrieveUpdateDestroyAPIView)`
**Purpose**: Get, update, or delete a single data source.

**Endpoints**:
- `GET /api/ingestion/sources/<id>/`: Retrieve details
- `PUT /api/ingestion/sources/<id>/`: Full update
- `PATCH /api/ingestion/sources/<id>/`: Partial update
- `DELETE /api/ingestion/sources/<id>/`: Delete (archive)

**Permissions**: CanReadData, ownership check in update/destroy

**Serializers**:
- GET: DataSourceDetailSerializer (includes sample rows)
- PUT/PATCH: DataSourceUpdateSerializer (name, description, tags, retention_days)

**Features**:
- Prefetches raw_data_rows
- Ownership validation (owner or admin only)
- Soft delete via archiving (is_archived=True)
- Includes up to 10 sample raw data rows in GET response

**Methods**:
- `update()`: Validates ownership, updates metadata
- `destroy()`: Soft-deletes by setting is_archived=True, returns 204 No Content

---

#### `DataSourceUploadView(APIView)`
**Purpose**: Upload and ingest a source file synchronously.

**Endpoint**: `POST /api/ingestion/sources/upload/`

**Permission**: CanWriteData

**Parsers**: MultiPartParser, FormParser

**Serializer**: DataSourceUploadSerializer

**Process**:
1. Validates request data
2. Calls `ingest_uploaded_file()` from services
3. Returns 201 with DataSourceDetailSerializer on success
4. Returns 400 with error message on IngestionError

**Request Body** (multipart/form-data):
- `file`: Required, file upload
- `name`: Optional, source name
- `source_type`: Optional (csv, excel, json, api, database)
- `delimiter`: Optional, default ','
- `encoding`: Optional, default 'utf-8'
- `has_header`: Optional, default True
- `description`: Optional
- `tags`: Optional, list of strings
- `retention_days`: Optional, default 90
- `required_columns`: Optional, list of column names
- `key_columns`: Optional, list of column names
- `strict_validation`: Optional, default False
- `template_id`: Optional, template ID
- `column_mapping`: Optional, JSON object

**Response**: 201 Created with full DataSource details

---

#### `DataSourceAsyncUploadView(APIView)`
**Purpose**: Upload and ingest file asynchronously via Celery.

**Endpoint**: `POST /api/ingestion/sources/async-upload/`

**Permission**: CanWriteData

**Process**:
1. Validates request data
2. Saves file to disk
3. Creates IngestionJob record
4. Queues Celery task via `process_ingestion_async.delay()`
5. Updates job with Celery task_id

**Response**: 202 Accepted with IngestionJobSerializer

**Client Usage**: Poll `/api/ingestion/jobs/<job_id>/` for status

---

#### `IngestionJobView(generics.RetrieveAPIView)`
**Purpose**: Check status of an async ingestion job.

**Endpoint**: `GET /api/ingestion/jobs/<job_id>/`

**Permission**: CanReadData

**Serializer**: IngestionJobSerializer

**Response**: 200 OK with job status, progress, potentially nested source details

---

#### `DataSourcePreviewView(APIView)`
**Purpose**: Analyze a source file before import.

**Endpoint**: `POST /api/ingestion/sources/preview/`

**Permission**: CanWriteData

**Serializer**: DataSourcePreviewSerializer

**Process**:
1. Validates request data
2. Calls `preview_uploaded_file()` from services
3. Returns 200 with preview analysis (no persistence)

**Response**: 200 OK with preview data including validation errors and sample rows

---

## 4. SERIALIZERS (serializers.py)

### DataSourceListSerializer
**Purpose**: Minimal serializer for list view (non-nested).

**Fields** (all read-only):
- id, name, source_type, status, file_size_bytes, row_count, column_count
- uploaded_by_username (sourced from uploaded_by.username)
- description, tags, created_at, processed_at

---

### RawDataSerializer
**Purpose**: Serializes individual raw data rows.

**Fields** (all read-only):
- row_number, data, validation_status, validation_messages

---

### DataSourceDetailSerializer
**Purpose**: Complete serializer for detail view with embedded sample rows.

**Fields** (all read-only):
- Full model fields: id, name, source_type, file_path, file_size_bytes, row_count, column_count, delimiter, encoding, has_header, status, validation_errors, metadata, checksum_md5, retention_days, is_archived, description, tags, schema_version, lineage_info
- uploaded_by (User ID), uploaded_by_username (string)
- sample_rows (SerializerMethodField - first 10 RawData rows)
- All timestamps: created_at, updated_at, processed_at

**Methods**:
- `get_sample_rows(obj)`: Returns up to 10 RawData rows ordered by row_number

---

### IngestionRequestSerializer (Base)
**Purpose**: Base serializer for file upload requests with validation.

**Fields**:
- file: FileField, required
- name: CharField, 200, optional (defaults to uploaded filename)
- source_type: ChoiceField (csv, excel, api, database, json), optional
- delimiter: CharField, 10, default ','
- encoding: CharField, 20, default 'utf-8'
- has_header: BooleanField, default True
- description: TextField, optional
- tags: ListField of strings, default []
- retention_days: IntegerField, min 1, max 3650, default 90
- required_columns: ListField of strings, default []
- key_columns: ListField of strings, default []
- strict_validation: BooleanField, default False
- template_id: CharField, 100, optional
- column_mapping: JSONField, default {}

**Validation**:
- `validate()`: Infers source_type from filename if not provided, sets name to filename if not provided
- `_infer_source_type(filename)`: Detects type from extension (.csv, .xlsx/.xls, .json)

**Raises**: ValidationError if source_type cannot be determined

---

### DataSourceUploadSerializer
**Purpose**: Serializer for synchronous file upload.

**Inherits**: IngestionRequestSerializer (no additional fields)

---

### DataSourcePreviewSerializer
**Purpose**: Serializer for preview file analysis.

**Inherits**: IngestionRequestSerializer (no additional fields)

---

### IngestionJobSerializer
**Purpose**: Serializer for async job status.

**Fields** (all read-only):
- id, celery_task_id, status, progress_percent, error_message
- started_at, completed_at, created_at
- source (ID), source_detail (nested DataSourceDetailSerializer)

**Methods**:
- `source_detail`: Nested serialization of related DataSource

---

### DataSourceUpdateSerializer
**Purpose**: Serializer for updating DataSource metadata.

**Fields** (all writable):
- name, description, tags, retention_days

**Validation**:
- `validate_retention_days(value)`: Must be between 1 and 3650 days

---

## 5. URL PATTERNS (urls.py)

All endpoints prefixed with `/api/ingestion/`

| Method | Path | View | Name | Description |
|--------|------|------|------|-------------|
| GET | `templates/` | ImportTemplateListView | ingestion_template_list | List ERP templates |
| GET | `sources/` | DataSourceListView | ingestion_source_list | List all sources |
| GET | `sources/<id>/` | DataSourceDetailView | ingestion_source_detail | Get single source |
| PUT | `sources/<id>/` | DataSourceDetailView | ingestion_source_detail | Update source metadata |
| PATCH | `sources/<id>/` | DataSourceDetailView | ingestion_source_detail | Partial update |
| DELETE | `sources/<id>/` | DataSourceDetailView | ingestion_source_detail | Archive source |
| POST | `sources/preview/` | DataSourcePreviewView | ingestion_source_preview | Preview file before import |
| POST | `sources/upload/` | DataSourceUploadView | ingestion_source_upload | Synchronous file upload |
| POST | `sources/async-upload/` | DataSourceAsyncUploadView | ingestion_source_async_upload | Async file upload |
| GET | `jobs/<id>/` | IngestionJobView | ingestion_job_detail | Check async job status |

---

## 6. ADDITIONAL COMPONENTS

### Admin Interface (admin.py)

**DataSourceAdmin**:
- List display: id, name, source_type, status, uploaded_by, row_count, created_at
- Filters: source_type, status, created_at
- Search: name, file_path, uploaded_by__username, checksum_md5
- Readonly: checksum_md5, created_at, updated_at, processed_at

**RawDataAdmin**:
- List display: id, source, row_number, validation_status, ingested_at
- Filters: validation_status, ingested_at
- Search: source__name
- Readonly: ingested_at

**IngestionJobAdmin**:
- List display: id, celery_task_id, status, progress_percent, source, created_at
- Filters: status, created_at
- Search: celery_task_id, source__name
- Readonly: celery_task_id, created_at, started_at, completed_at

---

### Celery Tasks (tasks.py)

**`process_ingestion_async(self, job_id, user_id, file_path, ...)`**:
- **Purpose**: Async task to process file ingestion without blocking the API
- **Max retries**: 3
- **Parameters**: All parameters from upload endpoint
- **Process**: 
  1. Updates IngestionJob status to 'processing'
  2. Reads file from disk
  3. Calls `_analyze_file_bytes()`
  4. Checks strict validation
  5. Creates DataSource and RawData records
  6. Updates IngestionJob with success/failure status
- **Error handling**: Tracks error_message in IngestionJob

---

## Test Coverage Summary

Based on this structure, comprehensive test coverage should include:

### Models Tests
- DataSource CRUD operations and field validation
- RawData constraints (unique_together, row_number ordering)
- IngestionJob status transitions
- Relationship integrity (ForeignKeys, OneToOne)

### Services Tests
- File analysis and validation (_analyze_file_bytes)
- Column normalization and mapping
- Duplicate detection (rows, files, keys)
- Business rule validation
- Schema profiling
- Template loading and application
- Row validation and status resolution
- Full ingestion flow (preview vs actual)

### Views Tests
- Permission checks (CanReadData, CanWriteData, ownership)
- Query parameter filtering and searching
- Synchronous upload with validation
- Async upload with Celery task creation
- Preview functionality
- Job status polling
- Update/delete operations (soft-delete behavior)

### Serializers Tests
- Field serialization (read-only, writable)
- Nested serialization (sample_rows, source_detail)
- Validation (file type inference, retention days bounds)
- Method field computation

### Integration Tests
- End-to-end upload and verification
- Permission-based visibility
- Admin vs user behavior
- Multi-user scenarios
- Large file handling
- Invalid file formats

---

## Key Validation Rules

1. **Columns**: Must be present, non-empty (required columns)
2. **Files**: MD5 checksum tracking to prevent duplicates
3. **Rows**: Row number uniqueness per source, content hash tracking
4. **Keys**: Key combination uniqueness per source
5. **Business Rules**: Template-based validation (positive/negative numbers, allowed values, date format)
6. **Encoding**: UTF-8 default with configurable encoding
7. **Ownership**: Users see only their own sources (unless admin)
8. **Retention**: Default 90 days, customizable 1-3650 days

---

## Data Flow Diagram

```
User Upload Request
    ↓
DataSourceUploadView or DataSourceAsyncUploadView
    ↓
Serializer Validation (DataSourceUploadSerializer)
    ↓
ingest_uploaded_file() or process_ingestion_async()
    ↓
_analyze_file_bytes()
    ↓
_load_dataframe() → _normalize_columns() → _apply_mapping()
    ↓
Duplicate Detection + Business Rules → Validation Errors
    ↓
Create DataSource Record + Bulk Create RawData Records
    ↓
Response to User (with sample rows + validation summary)
```

---

## Filtering Pipeline

```
DataSourceListView
    ↓
Filter by: status, source_type, created_at
    ↓
Filter by: tags (multi-value)
    ↓
Filter by: uploaded_by (admin only)
    ↓
Search in: name, description, tags (full-text)
    ↓
Order by: created_at (default), name, row_count
    ↓
Multi-user filtering: Only own sources (unless admin)
```
