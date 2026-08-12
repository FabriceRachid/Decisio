from rest_framework import serializers

from apps.ingestion.models import DataSource, RawData, IngestionJob, DataSourceSheet, SheetRelation


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
            'sheet_name',
            'data',
            'validation_status',
            'validation_messages',
        ]
        read_only_fields = fields


class DataSourceSheetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSourceSheet
        fields = [
            'id',
            'sheet_name',
            'sheet_index',
            'row_count',
            'column_count',
            'column_names',
            'is_active',
            'quality_score',
            'content_type',
            'metadata',
        ]
        read_only_fields = fields


class DataSourceDetailSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)
    sample_rows = serializers.SerializerMethodField()
    sheets = serializers.SerializerMethodField()

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
            'sheets',
        ]
        read_only_fields = fields

    def get_sample_rows(self, obj):
        cached = getattr(obj, 'sample_rows_cache', None)
        if cached is not None:
            return RawDataSerializer(cached, many=True).data
        rows = obj.raw_data_rows.order_by('row_number')[:10]
        return RawDataSerializer(rows, many=True).data

    def get_sheets(self, obj):
        sheets = obj.sheets.all()
        if sheets.exists():
            return DataSourceSheetSerializer(sheets, many=True).data
        # Fallback: build sheet list from metadata (for sources imported before SheetRelation feature)
        meta = obj.metadata or {}
        sheet_names = meta.get('sheet_names') or []
        if len(sheet_names) > 1:
            raw_data = obj.raw_data_rows.all()
            sheet_counts = {}
            sheet_columns = {}
            for row in raw_data:
                sn = row.sheet_name or ''
                sheet_counts[sn] = sheet_counts.get(sn, 0) + 1
                if sn not in sheet_columns:
                    sheet_columns[sn] = set()
                    sheet_columns[sn].update(row.data.keys() if row.data else [])
            result = []
            for idx, name in enumerate(sheet_names):
                result.append({
                    'id': idx,
                    'sheet_name': name,
                    'sheet_index': idx,
                    'row_count': sheet_counts.get(name, 0),
                    'column_count': len(sheet_columns.get(name, set())),
                    'column_names': sorted(sheet_columns.get(name, set())),
                    'is_active': True,
                    'quality_score': None,
                    'content_type': '',
                    'metadata': {},
                })
            return result
        return []


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


class SheetRelationSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = SheetRelation
        fields = [
            'id',
            'relation_name',
            'from_sheet',
            'from_column',
            'to_sheet',
            'to_column',
            'join_type',
            'is_active',
            'confidence',
            'match_ratio',
            'created_by',
            'created_by_username',
            'metadata',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'confidence', 'match_ratio', 'created_by', 'created_at', 'updated_at']


class RelationSuggestionSerializer(serializers.Serializer):
    from_sheet = serializers.CharField()
    from_column = serializers.CharField()
    to_sheet = serializers.CharField()
    to_column = serializers.CharField()
    confidence = serializers.FloatField()
    match_ratio = serializers.FloatField()
    reason = serializers.CharField()


class JoinedViewRequestSerializer(serializers.Serializer):
    sheet_names = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=None,
    )
    relation_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=None,
    )
