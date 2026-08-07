"""
DRF serializers for intelligent structural reconstruction endpoints.
"""
from rest_framework import serializers


class StructuralFingerprintSerializer(serializers.Serializer):
    total_rows = serializers.IntegerField()
    total_cols = serializers.IntegerField()
    merged_cells = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    blank_rows = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    blank_cols = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    header_candidates = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    subtables = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    column_types = serializers.DictField(required=False, default=dict)
    confidence = serializers.FloatField()
    issues = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class ReconstructionSubtableSerializer(serializers.Serializer):
    index = serializers.IntegerField()
    start_row = serializers.IntegerField()
    end_row = serializers.IntegerField()
    start_col = serializers.IntegerField()
    end_col = serializers.IntegerField()
    header_row = serializers.IntegerField(allow_null=True)
    column_names = serializers.ListField(child=serializers.CharField())
    action = serializers.ChoiceField(choices=['keep', 'split', 'merge', 'drop'], default='keep')


class ReconstructionPlanSerializer(serializers.Serializer):
    subtables = ReconstructionSubtableSerializer(many=True)
    header_adjustments = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    column_renames = serializers.DictField(required=False, default=dict)
    unresolved_zones = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    ambiguities = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    confidence = serializers.FloatField()
    source = serializers.CharField(required=False, default='heuristic')


class ValidationGateSerializer(serializers.Serializer):
    gate = serializers.CharField()
    passed = serializers.BooleanField()
    message = serializers.CharField()
    details = serializers.DictField(required=False, default=dict)


class ValidationReportSerializer(serializers.Serializer):
    all_passed = serializers.BooleanField()
    gates = ValidationGateSerializer(many=True)
    confidence_modifier = serializers.FloatField()
    requires_human_review = serializers.BooleanField()
    failure_reasons = serializers.ListField(child=serializers.CharField())


class CleaningRunSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    source_id = serializers.IntegerField(read_only=True)
    source_name = serializers.CharField(source='source.name', read_only=True)
    sheet_name = serializers.CharField()
    method_used = serializers.CharField()
    status = serializers.CharField()
    confidence_score = serializers.FloatField()
    correction_examples_used = serializers.ListField(child=serializers.IntegerField())
    llm_model = serializers.CharField()
    llm_tokens_used = serializers.IntegerField()
    llm_duration_ms = serializers.IntegerField()
    reconstruction_plan = serializers.DictField()
    validation_gates_passed = serializers.BooleanField()
    validation_gates_detail = serializers.DictField()
    rows_before = serializers.IntegerField()
    rows_after = serializers.IntegerField()
    columns_before = serializers.IntegerField()
    columns_after = serializers.IntegerField()
    subtables_detected = serializers.IntegerField()
    duration_ms = serializers.IntegerField()
    error_message = serializers.CharField()
    created_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)


class CleaningRunListSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    source_id = serializers.IntegerField(read_only=True)
    source_name = serializers.CharField(source='source.name', read_only=True)
    sheet_name = serializers.CharField()
    method_used = serializers.CharField()
    status = serializers.CharField()
    confidence_score = serializers.FloatField()
    subtables_detected = serializers.IntegerField()
    duration_ms = serializers.IntegerField()
    requires_human_review = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()

    def get_requires_human_review(self, obj):
        return getattr(obj, 'status', '') == 'awaiting_review'


class StructuralDetectRequestSerializer(serializers.Serializer):
    sheet_name = serializers.CharField(required=False, allow_blank=True, default='')
    force_llm = serializers.BooleanField(required=False, default=False)
    validation_config = serializers.DictField(required=False, default=dict)


class StructuralDetectResponseSerializer(serializers.Serializer):
    run_id = serializers.IntegerField()
    method_used = serializers.CharField()
    status = serializers.CharField()
    confidence_score = serializers.FloatField()
    structural_fingerprint = StructuralFingerprintSerializer()
    reconstruction_plan = ReconstructionPlanSerializer(allow_null=True)
    validation_report = ValidationReportSerializer(allow_null=True)
    requires_human_review = serializers.BooleanField()
    correction_examples_used = serializers.ListField(child=serializers.IntegerField())
    llm_model = serializers.CharField(required=False, default='')
    llm_tokens_used = serializers.IntegerField(required=False, default=0)
    llm_duration_ms = serializers.IntegerField(required=False, default=0)
    duration_ms = serializers.IntegerField()
    error = serializers.CharField(allow_null=True)


class CorrectionValidateRequestSerializer(serializers.Serializer):
    correction_type = serializers.ChoiceField(
        choices=['structural', 'header', 'merge', 'split', 'type_correction'],
        default='structural',
    )
    description = serializers.CharField(required=False, default='')
    apply_plan = serializers.BooleanField(required=False, default=True)
    execute_cleaning = serializers.BooleanField(
        required=False, default=False,
        help_text='Si True, execute le nettoyage immediatement apres la creation des regles.',
    )


class CorrectionExampleSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    structural_before = serializers.DictField()
    structural_after = serializers.DictField()
    reconstruction_plan = serializers.DictField()
    description = serializers.CharField()
    correction_type = serializers.CharField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default='')
    is_validated = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    similarity = serializers.FloatField(required=False, default=0)
