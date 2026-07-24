from rest_framework import serializers

from apps.ingestion.models import DataSource, RawData, IngestionJob


class DataSourceListSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)

    class Meta:
        model = DataSource
        fields = [
            'id',
            'name',
            'source_type',
            'status',
            'file_size_bytes',
            'row_count',
            'column_count',
            'uploaded_by_username',
            'description',
            'tags',
            'created_at',
            'processed_at',
        ]
        read_only_fields = fields


class RawDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawData
        fields = [
            'row_number',
            'data',
            'validation_status',
            'validation_messages',
        ]
        read_only_fields = fields


class DataSourceDetailSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)
    sample_rows = serializers.SerializerMethodField()

    class Meta:
        model = DataSource
        fields = [
            'id',
            'name',
            'source_type',
            'file_path',
            'file_size_bytes',
            'row_count',
            'column_count',
            'delimiter',
            'encoding',
            'has_header',
            'status',
            'validation_errors',
            'metadata',
            'checksum_md5',
            'retention_days',
            'is_archived',
            'description',
            'tags',
            'schema_version',
            'lineage_info',
            'uploaded_by',
            'uploaded_by_username',
            'created_at',
            'updated_at',
            'processed_at',
            'sample_rows',
        ]
        read_only_fields = fields

    def get_sample_rows(self, obj):
        rows = obj.raw_data_rows.order_by('row_number')[:10]
        return RawDataSerializer(rows, many=True).data


class IngestionRequestSerializer(serializers.Serializer):
    file = serializers.FileField(required=True)
    name = serializers.CharField(required=False, max_length=200)
    source_type = serializers.ChoiceField(
        choices=DataSource.SOURCE_TYPE_CHOICES,
        required=False,
    )
    delimiter = serializers.CharField(required=False, max_length=10, default=',')
    encoding = serializers.CharField(required=False, max_length=20, default='utf-8')
    has_header = serializers.BooleanField(required=False, default=True)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False,
        default=list,
    )
    retention_days = serializers.IntegerField(required=False, min_value=1, max_value=3650, default=90)
    required_columns = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        default=list,
    )
    key_columns = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        default=list,
    )
    strict_validation = serializers.BooleanField(required=False, default=False)
    template_id = serializers.CharField(required=False, allow_blank=True, max_length=100)
    column_mapping = serializers.JSONField(required=False, default=dict)

    def validate(self, attrs):
        uploaded_file = attrs['file']
        inferred_type = self._infer_source_type(uploaded_file.name)
        source_type = attrs.get('source_type') or inferred_type

        if not source_type:
            raise serializers.ValidationError({
                'source_type': 'Could not infer source type from file name. Provide source_type explicitly.'
            })

        attrs['source_type'] = source_type
        attrs['name'] = attrs.get('name') or uploaded_file.name
        return attrs

    def _infer_source_type(self, filename):
        normalized = filename.lower()
        if normalized.endswith('.csv'):
            return 'csv'
        if normalized.endswith('.xlsx') or normalized.endswith('.xls'):
            return 'excel'
        if normalized.endswith('.json'):
            return 'json'
        return None


class DataSourceUploadSerializer(IngestionRequestSerializer):
    pass


class DataSourcePreviewSerializer(IngestionRequestSerializer):
    pass


class IngestionJobSerializer(serializers.ModelSerializer):
    source_detail = DataSourceDetailSerializer(source='source', read_only=True)
    requested_by_username = serializers.CharField(source='requested_by.username', read_only=True)

    class Meta:
        model = IngestionJob
        fields = [
            'id',
            'celery_task_id',
            'requested_by',
            'requested_by_username',
            'status',
            'progress_percent',
            'error_message',
            'started_at',
            'completed_at',
            'created_at',
            'source',
            'source_detail',
        ]
        read_only_fields = fields


class DataSourceUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating DataSource metadata"""
    class Meta:
        model = DataSource
        fields = [
            'name',
            'description',
            'tags',
            'retention_days',
        ]
        read_only_fields = []
    
    def validate_retention_days(self, value):
        if value < 1 or value > 3650:
            raise serializers.ValidationError("Retention days must be between 1 and 3650")
        return value
