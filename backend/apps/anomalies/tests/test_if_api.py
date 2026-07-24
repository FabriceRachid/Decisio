"""Tests for Isolation Forest anomaly API."""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.ingestion.models import DataSource, RawData
from apps.anomalies.models import Anomaly, AnomalyModel


@pytest.fixture
def analyst_api_client(db):
    from django.contrib.auth.models import User

    user = User.objects.create_user(username="anom_analyst", password="x", email="a@a.com")
    user.profile.role = "analyst"
    user.profile.save(update_fields=["role"])
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.django_db
def test_isolation_forest_detects_extreme_value(analyst_api_client):
    client, user = analyst_api_client

    source = DataSource.objects.create(
        name="Demo ventes",
        source_type="csv",
        uploaded_by=user,
        status="pending",
        row_count=5,
    )
    rows = [
        {"amount": 100.0, "qty": 1},
        {"amount": 102.0, "qty": 1},
        {"amount": 98.0, "qty": 1},
        {"amount": 101.0, "qty": 1},
        {"amount": 99999.0, "qty": 1},
    ]
    for i, data in enumerate(rows, start=1):
        RawData.objects.create(source=source, row_number=i, data=data)

    response = client.post(
        "/api/anomalies/isolation_forest/run/",
        {
            "source_id": source.id,
            "feature_columns": ["amount"],
            "backend": "raw",
            "contamination": 0.2,
            "max_rows": 100,
            "persist": False,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["n_samples"] == 5
    assert body["outlier_count"] >= 1
    out_nums = body["outlier_row_numbers"]
    assert 5 in out_nums


@pytest.mark.django_db
def test_isolation_forest_persist(analyst_api_client):
    client, user = analyst_api_client

    source = DataSource.objects.create(
        name="Demo persist",
        source_type="csv",
        uploaded_by=user,
        status="pending",
    )
    for i, amt in enumerate([10.0, 11.0, 10.5, 500.0], start=1):
        RawData.objects.create(source=source, row_number=i, data={"amount": amt})

    response = client.post(
        "/api/anomalies/isolation_forest/run/",
        {
            "source_id": source.id,
            "feature_columns": ["amount"],
            "contamination": 0.25,
            "persist": True,
            "model_name": "Test IF model",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert AnomalyModel.objects.filter(training_source=source).exists()
    assert Anomaly.objects.filter(data_source=source).exists()
    assert "persisted" in response.json()


@pytest.mark.django_db
def test_isolation_forest_forbidden_other_user_source(analyst_api_client, django_user_model):
    client, user = analyst_api_client
    other = django_user_model.objects.create_user(username="other", password="y")
    source = DataSource.objects.create(
        name="Private",
        source_type="csv",
        uploaded_by=other,
        status="pending",
    )
    RawData.objects.create(source=source, row_number=1, data={"amount": 1.0})

    response = client.post(
        "/api/anomalies/isolation_forest/run/",
        {"source_id": source.id, "feature_columns": ["amount"]},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "refuse" in response.json()["detail"].lower() or "acces" in response.json()["detail"].lower()


@pytest.mark.django_db
def test_list_detections_after_persist(analyst_api_client):
    client, user = analyst_api_client
    source = DataSource.objects.create(
        name="List demo",
        source_type="csv",
        uploaded_by=user,
        status="pending",
    )
    for i, amt in enumerate([1.0, 1.1, 1.0, 99.0], start=1):
        RawData.objects.create(source=source, row_number=i, data={"amount": amt})

    run = client.post(
        "/api/anomalies/isolation_forest/run/",
        {
            "source_id": source.id,
            "feature_columns": ["amount"],
            "contamination": 0.2,
            "persist": True,
        },
        format="json",
    )
    assert run.status_code == 200

    lst = client.get("/api/anomalies/detections/")
    assert lst.status_code == 200
    body = lst.json()
    assert body["count"] >= 1
    first = body["results"][0]
    assert "outlier_count" in first
    assert first["data_source"] == source.id

    detail = client.get(f"/api/anomalies/detections/{first['id']}/")
    assert detail.status_code == 200
    assert "row_ids" in detail.json()


@pytest.mark.django_db
def test_list_ml_models(analyst_api_client):
    client, user = analyst_api_client
    source = DataSource.objects.create(
        name="Model list",
        source_type="csv",
        uploaded_by=user,
        status="pending",
    )
    RawData.objects.create(source=source, row_number=1, data={"x": 1.0})
    RawData.objects.create(source=source, row_number=2, data={"x": 1.05})
    client.post(
        "/api/anomalies/isolation_forest/run/",
        {
            "source_id": source.id,
            "feature_columns": ["x"],
            "contamination": 0.3,
            "persist": True,
        },
        format="json",
    )

    r = client.get("/api/anomalies/ml-models/")
    assert r.status_code == 200
    assert r.json()["count"] >= 1
