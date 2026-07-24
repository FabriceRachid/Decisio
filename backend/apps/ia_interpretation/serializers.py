"""M6 — serializers."""

from rest_framework import serializers


class InterpretKpisSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=8000, min_length=3)
    source_id = serializers.IntegerField(required=False, min_value=1)
    widget_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        max_length=40,
    )
    kpi_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        max_length=40,
    )
    max_kpis = serializers.IntegerField(default=15, min_value=1, max_value=30)
    persist = serializers.BooleanField(default=True)
    model = serializers.CharField(required=False, allow_blank=True, max_length=100)
