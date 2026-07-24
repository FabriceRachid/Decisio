# M1 Ingestion Reference

This is the first usable implementation slice of M1.

## What M1 currently does

- previews files before import
- uploads source files through the API
- creates `DataSource` records
- ingests row data into `RawData`
- supports CSV now
- supports JSON now
- supports Excel `.xlsx` now through `openpyxl`
- exposes list and detail endpoints with sample rows
- builds schema profiles for columns
- detects duplicate files by checksum
- detects duplicate rows and duplicate business keys
- validates required columns and missing required values
- supports strict validation to block bad imports
- supports ERP import templates
- supports explicit column mapping from source headers to canonical fields
- enforces RBAC:
  - `analyst` and `admin` can upload
  - `viewer` cannot upload
  - non-admin users only see their own sources

## Endpoints

- `GET /api/ingestion/sources/`
- `GET /api/ingestion/sources/<id>/`
- `GET /api/ingestion/templates/`
- `POST /api/ingestion/sources/preview/`
- `POST /api/ingestion/sources/upload/`

## Auth

Use the same M9 auth mechanisms:

- `Authorization: Bearer <access-token>`
- `Authorization: Token <api-token>`

## Upload payload

`POST /api/ingestion/sources/upload/` expects multipart form data.

Fields:

- `file` required
- `name` optional
- `source_type` optional if it can be inferred from file extension
- `delimiter` optional, default `,`
- `encoding` optional, default `utf-8`
- `has_header` optional, default `true`
- `description` optional
- `tags` optional
- `retention_days` optional, default `90`
- `required_columns` optional
- `key_columns` optional
- `strict_validation` optional, default `false`
- `template_id` optional
- `column_mapping` optional JSON object

## Example

```bash
curl -X POST http://localhost:8000/api/ingestion/sources/upload/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@erp_export.csv" \
  -F "description=Monthly ERP export" \
  -F "delimiter=," \
  -F "has_header=true"
```

Excel uploads use the same endpoint:

```bash
curl -X POST http://localhost:8000/api/ingestion/sources/upload/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@erp_export.xlsx"
```

Preview before import:

```bash
curl -X POST http://localhost:8000/api/ingestion/sources/preview/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@erp_export.csv" \
  -F "required_columns=sku" \
  -F "required_columns=amount" \
  -F "required_columns=region" \
  -F "key_columns=sku"
```

Template-based preview:

```bash
curl -X POST http://localhost:8000/api/ingestion/sources/preview/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@sales_export.csv" \
  -F "template_id=erp_sales_export"
```

Manual mapping on import:

```bash
curl -X POST http://localhost:8000/api/ingestion/sources/upload/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@inventory_export.csv" \
  -F "template_id=erp_inventory_export" \
  -F 'column_mapping={"article":"sku","depot":"warehouse_code","qty":"stock_quantity"}' \
  -F "strict_validation=true"
```

## ERP templates

Templates currently available:

- `erp_sales_export`
- `erp_inventory_export`
- `erp_customer_master`
- `erp_supplier_master`
- `erp_gl_entries`

Each template can define:

- label and description
- dataset type
- required canonical columns
- business key columns
- known aliases from ERP export headers to canonical field names
- dataset-specific business rules

Examples:

- `Invoice Number` -> `document_no`
- `Client` -> `customer_code`
- `Posting Date` -> `document_date`
- `article` -> `sku`
- `depot` -> `warehouse_code`
- `qty` -> `stock_quantity`

## Template catalog

Use:

```bash
curl -X GET http://localhost:8000/api/ingestion/templates/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

The response includes:

- `id`
- `label`
- `description`
- `dataset_type`
- `required_columns`
- `key_columns`
- `business_rules`

## Analysis output

Preview and stored metadata now include:

- `schema_profile`
- `duplicate_summary`
- `validation_summary`
- `validation_errors`
- row-level warning information in preview/sample rows
- applied template metadata
- resolved column mapping

Typical validations:

- missing required columns
- duplicate rows in the file
- duplicate values for business key columns
- missing required values in individual rows
- duplicate file detection using checksum
- template-specific field rules

## Template business rules

Examples currently enforced:

- sales:
  - positive `amount`
  - allowed currencies like `USD`, `EUR`, `XOF`, `GBP`
  - parseable `document_date`
- inventory:
  - non-negative `stock_quantity`
  - non-negative `stock_value`
- customer master:
  - non-empty `customer_code`
  - non-empty `customer_name`
  - allowed `status` values such as `active`, `inactive`, `prospect`
- supplier master:
  - non-empty `supplier_code`
  - non-empty `supplier_name`
- GL entries:
  - parseable `posting_date`
  - non-negative `debit`
  - non-negative `credit`

## Mapping behavior

Column normalization is applied before validation:

- headers are lowercased
- spaces and dashes become underscores
- template alias mapping is applied
- manual `column_mapping` overrides or supplements source header mapping

The result is stored in metadata and used consistently for:

- preview validation
- strict import checks
- persisted `RawData` row structure

## Tests

Run:

```powershell
& "C:\Users\HP 2025\miniconda3\envs\decisio\python.exe" manage.py test apps.ingestion
```

Covered:

- CSV upload success
- Excel upload success
- JSON upload success
- preview validation for missing columns and duplicate keys
- strict validation blocking invalid imports
- template alias mapping
- manual column mapping during import
- preset catalog listing
- dataset-specific business-rule validation
- viewer upload denied
- per-user source visibility
