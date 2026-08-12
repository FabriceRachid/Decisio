import pytest
from django.utils import timezone

from apps.authentication.models import Organization
from apps.ingestion.models import DataSource, RawData
from apps.nettoyage.models import CleanedData, CleaningJob


def _attach_org(user, name="Org KPI"):
    organization = Organization.objects.create(name=name, created_by=user)
    user.profile.organization = organization
    user.profile.save(update_fields=["organization"])
    return organization


def _build_validated_source(user, *, name="ventes.csv") -> DataSource:
    source = DataSource.objects.create(
        name=name,
        source_type="csv",
        uploaded_by=user,
        status="completed",
        row_count=3,
        column_count=4,
    )

    raw_rows = [
        RawData.objects.create(
            source=source,
            row_number=1,
            data={"date": "2026-04-15", "montant_total": 10000, "client": "Client A", "produit": "Savon"},
        ),
        RawData.objects.create(
            source=source,
            row_number=2,
            data={"date": "2026-04-18", "montant_total": 15000, "client": "Client B", "produit": "Savon"},
        ),
        RawData.objects.create(
            source=source,
            row_number=3,
            data={"date": "2026-03-10", "montant_total": 8000, "client": "Client A", "produit": "Huile"},
        ),
    ]

    job = CleaningJob.objects.create(
        source=source,
        created_by=user,
        status="completed",
        total_rows=3,
        rows_processed=3,
        rows_affected=3,
        progress_percent=100,
        completed_at=timezone.now(),
    )

    for raw in raw_rows:
        CleanedData.objects.create(
            job=job,
            original_data=raw,
            data=raw.data,
            changes_made=[],
            is_validated=True,
            validated_by=user,
        )

    return source


def _build_non_validated_source(user, *, name="brouillon.csv") -> DataSource:
    source = DataSource.objects.create(
        name=name,
        source_type="csv",
        uploaded_by=user,
        status="completed",
        row_count=1,
        column_count=2,
    )
    raw = RawData.objects.create(
        source=source,
        row_number=1,
        data={"date": "2026-04-15", "montant_total": 10000},
    )
    job = CleaningJob.objects.create(
        source=source,
        created_by=user,
        status="completed",
        total_rows=1,
        rows_processed=1,
        rows_affected=1,
        progress_percent=100,
        completed_at=timezone.now(),
    )
    CleanedData.objects.create(
        job=job,
        original_data=raw,
        data=raw.data,
        changes_made=[],
        is_validated=False,
    )
    return source


def _build_customer_source(user, *, name="DimCustomer.csv") -> DataSource:
    source = DataSource.objects.create(
        name=name,
        source_type="csv",
        uploaded_by=user,
        status="completed",
        row_count=4,
        column_count=6,
    )

    rows = [
        {"customerkey": 1, "customeralternatekey": "AW0001", "yearlyincome": 1200000, "birthdate": "1988-05-10", "datefirstpurchase": "2024-01-15", "emailaddress": "a@example.com"},
        {"customerkey": 2, "customeralternatekey": "AW0002", "yearlyincome": 1800000, "birthdate": "1992-03-12", "datefirstpurchase": "2025-06-20", "emailaddress": "b@example.com"},
        {"customerkey": 3, "customeralternatekey": "AW0003", "yearlyincome": 950000, "birthdate": "1985-09-01", "datefirstpurchase": None, "emailaddress": "c@example.com"},
        {"customerkey": 4, "customeralternatekey": "AW0004", "yearlyincome": 1500000, "birthdate": "1990-11-30", "datefirstpurchase": "2023-03-02", "emailaddress": "d@example.com"},
    ]

    raw_rows = [
        RawData.objects.create(source=source, row_number=index + 1, data=row)
        for index, row in enumerate(rows)
    ]

    job = CleaningJob.objects.create(
        source=source,
        created_by=user,
        status="completed",
        total_rows=len(rows),
        rows_processed=len(rows),
        rows_affected=len(rows),
        progress_percent=100,
        completed_at=timezone.now(),
    )

    for raw in raw_rows:
        CleanedData.objects.create(
            job=job,
            original_data=raw,
            data=raw.data,
            changes_made=[],
            is_validated=True,
            validated_by=user,
        )

    return source


def _build_sparse_sales_source(user, *, name="BadlyStructuredSales.xlsx") -> DataSource:
    source = DataSource.objects.create(
        name=name,
        source_type="excel",
        uploaded_by=user,
        status="completed",
        row_count=4,
        column_count=4,
    )
    rows = [
        {"Sales": 139, "Segment": "Corporate", "Order ID": "CA-2013-166380", "Ship Mode": "Standard Class"},
        {"Sales": 16, "Segment": "Consumer", "Order ID": "CA-2013-166485", "Ship Mode": "Standard Class"},
        {"Sales": 66, "Segment": "Consumer", "Order ID": "CA-2013-168536", "Ship Mode": "Standard Class"},
        {"Sales": 1003, "Segment": "Consumer", "Order ID": "CA-2013-168753", "Ship Mode": "Second Class"},
    ]
    raw_rows = [RawData.objects.create(source=source, row_number=index + 1, data=row) for index, row in enumerate(rows)]
    job = CleaningJob.objects.create(
        source=source,
        created_by=user,
        status="completed",
        total_rows=len(rows),
        rows_processed=len(rows),
        rows_affected=len(rows),
        progress_percent=100,
        completed_at=timezone.now(),
    )
    for raw in raw_rows:
        CleanedData.objects.create(job=job, original_data=raw, data=raw.data, changes_made=[], is_validated=True, validated_by=user)
    return source


def _build_stringified_numeric_source(user, *, name="Sales-Export_2019-2020.csv") -> DataSource:
    """Source whose cleaned data stores numerics as strings (regression for source 2)."""
    source = DataSource.objects.create(
        name=name,
        source_type="csv",
        uploaded_by=user,
        status="completed",
        row_count=2,
        column_count=4,
    )
    rows = [
        {"date": "2/12/2020", "cost": "14122.61", "order_value_eur": "17,524.02", "country": "Sweden", "category": "Books"},
        {"date": "3/12/2020", "cost": "92807.78", "order_value_eur": "1,234.56", "country": "France", "category": "Furniture"},
    ]
    raw_rows = [RawData.objects.create(source=source, row_number=index + 1, data=row) for index, row in enumerate(rows)]
    job = CleaningJob.objects.create(
        source=source,
        created_by=user,
        status="completed",
        total_rows=len(rows),
        rows_processed=len(rows),
        rows_affected=len(rows),
        progress_percent=100,
        completed_at=timezone.now(),
    )
    for raw in raw_rows:
        CleanedData.objects.create(job=job, original_data=raw, data=raw.data, changes_made=[], is_validated=True, validated_by=user)
    return source


@pytest.mark.django_db
class TestAutoKPIDetectAPI:
    def test_detect_columns_from_validated_source(self, analyst_client, analyst_user):
        _attach_org(analyst_user, name="Sahel KPI")
        source = _build_validated_source(analyst_user)

        response = analyst_client.post(
            "/api/kpi/auto/detect/",
            {"source_id": source.id},
            format="json",
        )

        assert response.status_code == 200
        data = response.data
        assert data["source_id"] == source.id
        assert data["source_name"] == source.name
        assert "domain_profile" in data
        assert data["domain_profile"]["domain"] == "sales"
        assert data["domain_profile"]["confidence"] in {"moyenne", "forte"}

        assert "columns" in data
        assert "numeric" in data["columns"]
        assert "categorical" in data["columns"]
        assert "date" in data["columns"]

        numeric_names = {c["name"] for c in data["columns"]["numeric"]}
        assert "montant_total" in numeric_names

        date_names = {c["name"] for c in data["columns"]["date"]}
        assert "date" in date_names

        assert "suggestions" in data
        assert any(s["measure_column"] == "montant_total" for s in data["suggestions"])

    def test_detect_rejects_non_validated_source(self, analyst_client, analyst_user):
        _attach_org(analyst_user, name="Sahel KPI")
        source = _build_non_validated_source(analyst_user)

        response = analyst_client.post(
            "/api/kpi/auto/detect/",
            {"source_id": source.id},
            format="json",
        )

        assert response.status_code == 400
        assert "nettoyage validé" in response.data["error"]

    def test_detect_customer_source_detects_domain(self, analyst_client, analyst_user):
        _attach_org(analyst_user, name="Sahel KPI")
        source = _build_customer_source(analyst_user)

        response = analyst_client.post(
            "/api/kpi/auto/detect/",
            {"source_id": source.id},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["domain_profile"]["domain"] == "customers"
        assert "client_id" in response.data["domain_profile"]["matched_signals"]["customers"]

        numeric_names = {c["name"] for c in response.data["columns"]["numeric"]}
        assert "revenu_annuel" in numeric_names or "yearlyincome" in numeric_names

    def test_detect_sparse_english_sales_file(self, analyst_client, analyst_user):
        _attach_org(analyst_user, name="Sahel KPI")
        source = _build_sparse_sales_source(analyst_user)

        response = analyst_client.post(
            "/api/kpi/auto/detect/",
            {"source_id": source.id},
            format="json",
        )

        assert response.status_code == 200
        assert response.data["domain_profile"]["domain"] == "sales"

        numeric_names = {c["name"] for c in response.data["columns"]["numeric"]}
        assert "Sales" in numeric_names or "sales" in numeric_names

        assert len(response.data["columns"]["numeric"]) >= 1
        assert len(response.data["suggestions"]) >= 1

    def test_detect_numeric_columns_stored_as_strings(self, analyst_client, analyst_user):
        """Regression: cleaned data from the standardize rule can persist
        numerics as strings ('14122.61', '17,524.02'). They must still be
        detected as measures."""
        _attach_org(analyst_user, name="Sahel KPI")
        source = _build_stringified_numeric_source(analyst_user)

        response = analyst_client.post(
            "/api/kpi/auto/detect/",
            {"source_id": source.id},
            format="json",
        )

        assert response.status_code == 200
        numeric_names = {c["name"] for c in response.data["columns"]["numeric"]}
        assert "cost" in numeric_names
        assert "order_value_eur" in numeric_names
        assert "country" not in numeric_names
        assert len(response.data["suggestions"]) >= 1

    def test_detect_requires_source_id(self, analyst_client):
        response = analyst_client.post("/api/kpi/auto/detect/", {}, format="json")
        assert response.status_code == 400
        assert "source_id" in response.data["error"]

    def test_list_auto_returns_detection_for_source(self, analyst_client, analyst_user):
        _attach_org(analyst_user, name="Sahel KPI")
        source = _build_validated_source(analyst_user)

        detect = analyst_client.post(
            "/api/kpi/auto/detect/",
            {"source_id": source.id},
            format="json",
        )
        assert detect.status_code == 200

        response = analyst_client.get(f"/api/kpi/auto/?source_id={source.id}")
        assert response.status_code == 200
        assert response.data["source_id"] == source.id
        assert response.data["domain_profile"]["domain"] == "sales"
