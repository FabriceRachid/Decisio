from rest_framework import serializers

from apps.nettoyage.models import CleanedData, CleaningJob, CleaningPipeline, CleaningRule


def _validate_column_names(column_names):
    if column_names is None:
        return []
    if not isinstance(column_names, list):
        raise serializers.ValidationError('column_names must be a list of column names.')

    cleaned = []
    seen = set()
    for item in column_names:
        if not isinstance(item, str):
            raise serializers.ValidationError('Each column name must be a string.')
        normalized = item.strip()
        if not normalized:
            raise serializers.ValidationError('Column names cannot be empty.')
        if normalized not in seen:
            cleaned.append(normalized)
            seen.add(normalized)
    return cleaned


def _validate_column_pattern(pattern):
    if pattern in (None, ''):
        return pattern

    try:
        import re
        re.compile(pattern)
    except re.error as exc:
        raise serializers.ValidationError(f'Invalid regex pattern: {exc}') from exc

    if re.search(r'\((?:[^()]|\\.)*[+*](?:[^()]|\\.)*\)[+*{]', pattern):
        raise serializers.ValidationError('Unsafe regex pattern rejected because it may cause catastrophic backtracking.')

    return pattern


def _validate_rule_parameters(rule_type, parameters):
    params = parameters or {}
    if not isinstance(params, dict):
        raise serializers.ValidationError('parameters must be a JSON object.')

    if rule_type in {'drop_rows_by_missing_threshold', 'drop_columns_by_missing_threshold'}:
        threshold = params.get('threshold')
        if threshold is None:
            raise serializers.ValidationError({'parameters': 'threshold is required for missing-threshold rules.'})
        if not 0 <= float(threshold) <= 1:
            raise serializers.ValidationError({'parameters': 'threshold must be between 0 and 1.'})

    if rule_type == 'regex_replace' and not params.get('pattern'):
        raise serializers.ValidationError({'parameters': 'pattern is required for regex replacement.'})

    if rule_type == 'validate_format' and not params.get('pattern'):
        raise serializers.ValidationError({'parameters': 'pattern is required for format validation.'})

    if rule_type == 'split_column':
        if not params.get('source_column') or not params.get('target_columns'):
            raise serializers.ValidationError({'parameters': 'source_column and target_columns are required for split_column.'})

    if rule_type == 'merge_columns':
        if not params.get('source_columns') or not params.get('target_column'):
            raise serializers.ValidationError({'parameters': 'source_columns and target_column are required for merge_columns.'})

    if rule_type == 'convert_dtype':
        dtype = params.get('dtype')
        if dtype not in {'string', 'integer', 'float', 'boolean', 'date'}:
            raise serializers.ValidationError({'parameters': 'dtype must be one of string, integer, float, boolean, date.'})

    return params


class CleaningRuleValidationMixin:
    def validate_priority(self, value):
        if value < 1 or value > 10:
            raise serializers.ValidationError('Priority must be between 1 and 10.')
        return value

    def validate_column_names(self, value):
        return _validate_column_names(value)

    def validate_column_pattern(self, value):
        return _validate_column_pattern(value)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        rule_type = attrs.get('rule_type') or getattr(self.instance, 'rule_type', None)
        parameters = attrs.get('parameters', getattr(self.instance, 'parameters', {}))
        attrs['parameters'] = _validate_rule_parameters(rule_type, parameters)
        return attrs


class CleaningRuleSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = CleaningRule
        fields = [
            'id',
            'name',
            'description',
            'rule_type',
            'column_pattern',
            'column_names',
            'parameters',
            'priority',
            'is_active',
            'apply_to_all',
            'category',
            'tags',
            'version',
            'execution_count',
            'success_rate',
            'created_by',
            'created_by_username',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'execution_count',
            'success_rate',
            'created_by',
            'created_by_username',
            'created_at',
            'updated_at',
        ]


class CleaningRuleCreateSerializer(CleaningRuleValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = CleaningRule
        fields = [
            'name',
            'description',
            'rule_type',
            'column_pattern',
            'column_names',
            'parameters',
            'priority',
            'is_active',
            'apply_to_all',
            'category',
            'tags',
        ]


class CleaningJobSerializer(serializers.ModelSerializer):
    rule_name = serializers.CharField(source='rule.name', read_only=True)
    result_job_id = serializers.SerializerMethodField()

    class Meta:
        model = CleaningJob
        fields = [
            'id',
            'source',
            'rule',
            'rule_name',
            'status',
            'total_rows',
            'rows_processed',
            'rows_affected',
            'rows_skipped',
            'rows_failed',
            'progress_percent',
            'started_at',
            'completed_at',
            'duration_ms',
            'error_message',
            'export_path',
            'execution_context',
            'result_job_id',
            'created_at',
        ]
        read_only_fields = fields

    def get_result_job_id(self, obj):
        return (obj.execution_context or {}).get('result_job_id')


class CleanedDataSerializer(serializers.ModelSerializer):
    original_row_number = serializers.IntegerField(source='original_data.row_number', read_only=True)
    validated_by_username = serializers.CharField(source='validated_by.username', read_only=True)

    class Meta:
        model = CleanedData
        fields = [
            'id',
            'original_row_number',
            'data',
            'changes_made',
            'quality_score',
            'is_validated',
            'validated_by',
            'validated_by_username',
            'validation_notes',
            'cleaned_at',
        ]
        read_only_fields = fields


class CleaningPreviewRequestSerializer(serializers.Serializer):
    pipeline_id = serializers.IntegerField(required=False, min_value=1)
    rule_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
    )
    include_all_auto_rules = serializers.BooleanField(required=False, default=False)
    quality_gate = serializers.JSONField(required=False, default=dict)
    decision_overrides = serializers.JSONField(required=False, default=list)

    def validate_quality_gate(self, value):
        gate = value or {}
        if not isinstance(gate, dict):
            raise serializers.ValidationError('quality_gate must be a JSON object.')

        min_quality_score = gate.get('min_quality_score')
        if min_quality_score is not None and not 0 <= float(min_quality_score) <= 100:
            raise serializers.ValidationError('min_quality_score must be between 0 and 100.')

        max_missing_value_rate = gate.get('max_missing_value_rate')
        if max_missing_value_rate is not None and not 0 <= float(max_missing_value_rate) <= 1:
            raise serializers.ValidationError('max_missing_value_rate must be between 0 and 1.')

        return gate

    def validate_decision_overrides(self, value):
        overrides = value or []
        if not isinstance(overrides, list):
            raise serializers.ValidationError('decision_overrides must be a list.')
        for item in overrides:
            if not isinstance(item, dict):
                raise serializers.ValidationError('Each decision override must be an object.')
        return overrides


class CleaningApplyRequestSerializer(CleaningPreviewRequestSerializer):
    persist_results = serializers.BooleanField(required=False, default=True)


class CleaningPipelineSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    rule_ids = serializers.PrimaryKeyRelatedField(
        source='rules',
        many=True,
        queryset=CleaningRule.objects.all(),
        required=False,
    )

    class Meta:
        model = CleaningPipeline
        fields = [
            'id',
            'name',
            'description',
            'rule_ids',
            'source_type_scope',
            'quality_gate',
            'is_active',
            'apply_to_all',
            'created_by',
            'created_by_username',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_by_username', 'created_at', 'updated_at']


class CleaningJobValidationSerializer(serializers.Serializer):
    is_validated = serializers.BooleanField(required=False, default=True)
    validation_notes = serializers.CharField(required=False, allow_blank=True, default='')


class CleaningRuleUpdateSerializer(CleaningRuleValidationMixin, serializers.ModelSerializer):
    """Serializer for updating CleaningRule fields"""

    class Meta:
        model = CleaningRule
        fields = [
            'name',
            'description',
            'rule_type',
            'column_pattern',
            'column_names',
            'parameters',
            'priority',
            'is_active',
            'apply_to_all',
            'category',
            'tags',
        ]


class CleaningExportRequestSerializer(serializers.Serializer):
    """Serializer for export requests"""
    format = serializers.ChoiceField(
        choices=['csv', 'excel', 'json'],
        default='csv',
        help_text='Export file format'
    )
    include_metadata = serializers.BooleanField(
        default=False,
        help_text='Include changes_made and quality_score columns'
    )
    include_validation_status = serializers.BooleanField(
        default=False,
        help_text='Include is_validated and validation_notes columns'
    )


class CleaningJobListSerializer(serializers.ModelSerializer):
    """Simplified serializer for list views with filtering"""
    rule_name = serializers.CharField(source='rule.name', read_only=True)
    source_name = serializers.CharField(source='source.name', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    result_job_id = serializers.SerializerMethodField()
    validated_rows = serializers.SerializerMethodField()
    pending_rows = serializers.SerializerMethodField()
    is_fully_validated = serializers.SerializerMethodField()

    class Meta:
        model = CleaningJob
        fields = [
            'id',
            'source',
            'source_name',
            'rule',
            'rule_name',
            'status',
            'error_message',
            'rows_affected',
            'duration_ms',
            'export_path',
            'result_job_id',
            'validated_rows',
            'pending_rows',
            'is_fully_validated',
            'started_at',
            'completed_at',
            'created_by_username',
            'created_at',
        ]
        read_only_fields = fields

    def get_result_job_id(self, obj):
        return (obj.execution_context or {}).get('result_job_id')

    def get_validated_rows(self, obj):
        return obj.cleaned_results.filter(is_validated=True).count()

    def get_pending_rows(self, obj):
        total = obj.cleaned_results.count()
        validated = obj.cleaned_results.filter(is_validated=True).count()
        return max(total - validated, 0)

    def get_is_fully_validated(self, obj):
        total = obj.cleaned_results.count()
        if total == 0:
            return False
        validated = obj.cleaned_results.filter(is_validated=True).count()
        return validated == total
