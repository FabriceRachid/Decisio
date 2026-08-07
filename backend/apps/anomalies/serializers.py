"""M7 — serializers for anomaly detection API."""

from rest_framework import serializers

from apps.anomalies.models import Anomaly, AnomalyModel


class IsolationForestRunSerializer(serializers.Serializer):
    source_id = serializers.IntegerField(min_value=1)
    feature_columns = serializers.ListField(
        child=serializers.CharField(max_length=200),
        min_length=1,
        max_length=32,
    )
    backend = serializers.ChoiceField(choices=("raw", "cleaned"), default="raw")
    contamination = serializers.FloatField(default=0.05, min_value=0.001, max_value=0.5)
    max_rows = serializers.IntegerField(default=5000, min_value=10, max_value=50000)
    persist = serializers.BooleanField(default=False)
    model_name = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate_feature_columns(self, value):
        cleaned = [str(c).strip() for c in value if str(c).strip()]
        if not cleaned:
            raise serializers.ValidationError("Au moins une colonne valide est requise.")
        if len(set(cleaned)) != len(cleaned):
            raise serializers.ValidationError("Les noms de colonnes doivent etre uniques.")
        return cleaned


class AnomalyListSerializer(serializers.ModelSerializer):
    data_source_name = serializers.CharField(source="data_source.name", read_only=True)
    model_name = serializers.CharField(source="model.name", read_only=True)
    algorithm = serializers.CharField(source="model.algorithm", read_only=True)
    outlier_count = serializers.SerializerMethodField()

    class Meta:
        model = Anomaly
        fields = [
            "id",
            "data_source",
            "data_source_name",
            "model",
            "model_name",
            "algorithm",
            "anomaly_score",
            "severity",
            "status",
            "confidence",
            "outlier_count",
            "detected_at",
        ]

    def get_outlier_count(self, obj):
        rows = obj.row_ids
        return len(rows) if isinstance(rows, list) else 0


class AnomalyDetailSerializer(AnomalyListSerializer):
    class Meta:
        model = Anomaly
        fields = AnomalyListSerializer.Meta.fields + [
            "row_ids",
            "affected_columns",
            "contribution_scores",
            "explanation",
            "anomaly_type",
            "pattern_description",
            "is_reviewed",
            "review_notes",
        ]


class AnomalyStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Anomaly
        fields = [
            "status",
            "is_reviewed",
            "review_notes",
        ]


class AnomalyModelListSerializer(serializers.ModelSerializer):
    training_source_name = serializers.CharField(source="training_source.name", read_only=True, allow_null=True)

    class Meta:
        model = AnomalyModel
        fields = [
            "id",
            "name",
            "algorithm",
            "algorithm_version",
            "training_source",
            "training_source_name",
            "training_features",
            "training_samples",
            "is_active",
            "last_inference_at",
            "inference_count",
            "created_at",
        ]
