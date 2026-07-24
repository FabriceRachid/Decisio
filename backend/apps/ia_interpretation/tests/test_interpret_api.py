"""Tests M6 interpret-kpis (mock Groq)."""

from unittest.mock import MagicMock, patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date, timedelta

from apps.kpi.models import KPI, KPICalculation


@pytest.fixture
def analyst_client(db):
    user = User.objects.create_user(username="ia_analyst", password="x", email="ia@example.com")
    user.profile.role = "analyst"
    user.profile.save(update_fields=["role"])
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.django_db
def test_interpret_kpis_success_mocked(analyst_client, settings):
    settings.GROQ_API_KEY = "gsk-test-key"
    client, user = analyst_client
    kpi = KPI.objects.create(
        name="CA test",
        code="CA_T",
        formula="1",
        formula_type="python",
        owner=user,
        is_active=True,
        is_public=True,
    )
    pe = date.today()
    ps = pe - timedelta(days=30)
    KPICalculation.objects.create(
        kpi=kpi,
        period_start=ps,
        period_end=pe,
        calculated_value=Decimal("100.0000"),
        status="on_target",
        executed_by=user,
    )

    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(content="**Constat** : CA à 100."))]
    mock_completion.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
    mock_completion.id = "chatcmpl-test"

    with patch("groq.Groq") as mock_groq_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_completion
        mock_groq_cls.return_value = mock_client

        response = client.post(
            "/api/ia/interpret-kpis/",
            {"question": "Que ressort-il sur le CA ?", "kpi_ids": [kpi.id], "persist": False},
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert "interpretation" in body
    assert "100" in body["interpretation"] or "Constat" in body["interpretation"]
    assert body["model"]
    mock_client.chat.completions.create.assert_called_once()


@pytest.mark.django_db
def test_interpret_kpis_no_api_key(analyst_client, settings):
    client, user = analyst_client
    KPI.objects.create(
        name="X",
        code="X1",
        formula="1",
        formula_type="python",
        owner=user,
        is_active=True,
        is_public=True,
    )
    settings.GROQ_API_KEY = ""

    response = client.post(
        "/api/ia/interpret-kpis/",
        {"question": "Resume les KPI."},
        format="json",
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
