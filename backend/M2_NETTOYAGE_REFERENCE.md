# M2 Nettoyage Reference

This is the MVP backend implementation of M2: automatic cleaning and standardization on top of M1 imported data.

## Core engine kept for MVP

- `loader_service.py`
- `mapping_service.py`
- `structural_cleaner.py`
- `date_cleaner.py`
- `montant_cleaner.py`
- `text_cleaner.py`
- `coherence_checker.py`
- `context_checker.py`
- `quality_scorer.py`
- `pipeline.py`
- `report.py`

The advanced orchestration, reconstruction, profiling, and LLM/ML helper layers were intentionally removed to keep M2 aligned with the MVP scope.

## Optional ML Profiling kept in MVP

`ml_cleaner.py` is kept as a lightweight optional enrichment layer:

- it does not drive the cleaning logic
- it never blocks the deterministic pipeline
- it enriches the report when optional libraries are installed
- it currently checks lightweight availability/summary for `cleanlab`, `klib`, and `dataprep_ai`

## What M2 currently does

- defines reusable cleaning rules
- defines reusable cleaning pipelines
- previews cleaning results before persistence
- applies one or more rules to an imported `DataSource`
- persists cleaning jobs and cleaned rows
- tracks row-level changes
- computes simple quality scores
- enforces optional quality gates
- returns before/after diff samples in preview
- returns lightweight column profiling in preview
- suggests cleaning rules automatically from source profiling
- auto-selects a default pipeline when configured for a source type
- exposes job detail, replay, and validation endpoints
- returns user-facing business summaries for preview and apply results
- supports automatic rules via `apply_to_all`
- protects preview/apply with RBAC

## Endpoints

- `GET /api/nettoyage/rules/`
- `POST /api/nettoyage/rules/`
- `GET /api/nettoyage/rules/<id>/`
- `GET /api/nettoyage/pipelines/`
- `POST /api/nettoyage/pipelines/`
- `GET /api/nettoyage/pipelines/<id>/`
- `GET /api/nettoyage/jobs/`
- `GET /api/nettoyage/jobs/<id>/`
- `POST /api/nettoyage/jobs/<id>/replay/`
- `POST /api/nettoyage/jobs/<id>/validate/`
- `GET /api/nettoyage/sources/<source_id>/suggestions/`
- `POST /api/nettoyage/sources/<source_id>/preview/`
- `POST /api/nettoyage/sources/<source_id>/apply/`

## Rule types currently implemented

- `standardize`
- `remove_empty_rows`
- `drop_rows_by_missing_threshold`
- `drop_columns_by_missing_threshold`
- `fill_mean`
- `fill_median`
- `fill_mode`
- `fill_value`
- `regex_replace`
- `remove_duplicates`
- `normalize`
- `convert_dtype`
- `value_map`
- `rename_columns`
- `split_column`
- `merge_columns`
- `validate_format`
- `remove_nulls`

## Permissions

- `analyst` and `admin` can create rules, preview cleaning, and apply cleaning
- `viewer` cannot modify or run cleaning pipelines
- non-admin users only operate on sources they uploaded

## Cleaning flow

### Preview

`POST /api/nettoyage/sources/<source_id>/preview/`

Payload:

```json
{
  "pipeline_id": 1,
  "rule_ids": [1, 2],
  "include_all_auto_rules": true,
  "quality_gate": {
    "min_quality_score": 95,
    "max_missing_value_rate": 0.05,
    "block_on_validation_issues": false
  }
}
```

Response includes:

- source info
- resolved rules
- summary
- business summary
- sample cleaned rows
- diff samples
- validation issues

### Apply

`POST /api/nettoyage/sources/<source_id>/apply/`

Payload:

```json
{
  "pipeline_id": 1,
  "rule_ids": [1, 2],
  "include_all_auto_rules": true,
  "quality_gate": {
    "min_quality_score": 95
  }
}
```

Response includes:

- job id
- applied rules
- processing summary
- business summary
- sample cleaned rows

### Suggestions

`GET /api/nettoyage/sources/<source_id>/suggestions/`

Response includes:

- detected issues
- suggested rules with reasons
- recommended default pipeline, if any
- short business summary

### Job detail

`GET /api/nettoyage/jobs/<id>/`

Response includes:

- execution context
- validation summary
- sample cleaned rows
- change summary

### Replay

`POST /api/nettoyage/jobs/<id>/replay/`

Re-runs the job using the stored execution context so the same cleaning plan can be applied again after data review or source refresh.

### Validation

`POST /api/nettoyage/jobs/<id>/validate/`

Allows an analyst or admin to validate or unvalidate cleaned rows in bulk with optional notes before the data is used downstream.

## Persistence model

- one `CleaningJob` is created per executed rule
- pipelines are reusable named rule sets
- `CleanedData` stores the cleaned row snapshot for that job
- `changes_made` records column-level transformations where relevant
- `quality_score` is based on missing-value density after cleaning
- `execution_context` stores the resolved pipeline, rules, and quality gate for replay and audit

## Pipelines

Pipelines let you define:

- ordered reusable rule sets
- optional `source_type_scope`
- a default `quality_gate`

This is the recommended way to standardize a dataset family before later modules depend on it.

If a pipeline is marked `apply_to_all` and matches the source type, it can be auto-selected when the user applies cleaning without explicitly providing rules.

## Example rules

### Standardize text

```json
{
  "name": "Uppercase customer and currency",
  "rule_type": "standardize",
  "column_names": ["customer_code", "currency"],
  "parameters": {
    "mode": "upper"
  },
  "priority": 10,
  "is_active": true,
  "apply_to_all": false,
  "category": "formatting",
  "tags": ["standardization"]
}
```

### Fill missing values

```json
{
  "name": "Fill missing amount with zero",
  "rule_type": "fill_value",
  "column_names": ["amount"],
  "parameters": {
    "value": "0"
  },
  "priority": 8,
  "is_active": true,
  "apply_to_all": true,
  "category": "imputation",
  "tags": ["defaults"]
}
```

### Statistical fill

```json
{
  "name": "Fill amount with mean",
  "rule_type": "fill_mean",
  "column_names": ["amount"],
  "parameters": {},
  "priority": 7,
  "is_active": true,
  "apply_to_all": false,
  "category": "imputation",
  "tags": ["statistics"]
}
```

### Validate format

```json
{
  "name": "Validate customer code format",
  "rule_type": "validate_format",
  "column_names": ["customer_code"],
  "parameters": {
    "pattern": "^[A-Z]{3}$"
  },
  "priority": 6,
  "is_active": true,
  "apply_to_all": false,
  "category": "validation",
  "tags": ["regex"]
}
```

### Normalize dates

```json
{
  "name": "Normalize dates to ISO",
  "rule_type": "normalize",
  "column_names": ["document_date"],
  "parameters": {
    "mode": "date_iso"
  },
  "priority": 6,
  "is_active": true,
  "apply_to_all": false,
  "category": "standardization",
  "tags": ["date"]
}
```

### Remove empty rows

```json
{
  "name": "Remove empty rows",
  "rule_type": "remove_empty_rows",
  "column_names": [],
  "parameters": {},
  "priority": 9,
  "is_active": true,
  "apply_to_all": false,
  "category": "cleanup",
  "tags": ["empty"]
}
```

### Drop sparse rows

```json
{
  "name": "Drop sparse rows",
  "rule_type": "drop_rows_by_missing_threshold",
  "column_names": [],
  "parameters": {
    "threshold": 0.5
  },
  "priority": 8,
  "is_active": true,
  "apply_to_all": false,
  "category": "cleanup",
  "tags": ["missing"]
}
```

### Convert dtype

```json
{
  "name": "Convert document date",
  "rule_type": "convert_dtype",
  "column_names": ["document_date"],
  "parameters": {
    "dtype": "date",
    "dayfirst": true
  },
  "priority": 7,
  "is_active": true,
  "apply_to_all": false,
  "category": "typing",
  "tags": ["date"]
}
```

### Value mapping

```json
{
  "name": "Map country codes",
  "rule_type": "value_map",
  "column_names": ["country"],
  "parameters": {
    "mapping": {
      "USA": "US",
      "U.S.A": "US"
    },
    "case_insensitive": true
  },
  "priority": 7,
  "is_active": true,
  "apply_to_all": false,
  "category": "standardization",
  "tags": ["mapping"]
}
```

### Merge columns

```json
{
  "name": "Build full name",
  "rule_type": "merge_columns",
  "parameters": {
    "source_columns": ["first_name", "last_name"],
    "target_column": "full_name",
    "separator": " "
  },
  "priority": 6,
  "is_active": true,
  "apply_to_all": false,
  "category": "reshaping",
  "tags": ["merge"]
}
```

## Tests

Run:

```powershell
& "C:\Users\HP 2025\miniconda3\envs\decisio\python.exe" manage.py test apps.nettoyage
```

Covered:

- rule listing and creation
- pipeline listing and detail
- cleaning preview
- cleaning apply and persistence
- statistical fill behavior
- quality gate blocking
- diff inspection in preview
- empty-row removal
- missing-threshold row dropping
- dtype conversion
- value mapping
- column merge operations
- RBAC for viewer role
- cleaning job listing

## Current scope

M2 is now much stronger for downstream dependency. The main upgrades still open are:

- chaining with scheduled/background jobs
- UI-driven column selection and diff views
- human validation workflow on `CleanedData`
- source-specific default pipeline assignment
- rollback or replay helpers for cleaning runs
