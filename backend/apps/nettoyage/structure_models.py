"""
Models for intelligent structural reconstruction of messy Excel/CSV files.
Tracks structural snapshots, human corrections, and reconstruction runs.
"""
from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField


class RawStructuralSnapshot(models.Model):
    """
    Stores the structural fingerprint of an imported file (not the data itself).
    Captures: merged cells, blank zones, header candidates, column types.
    """
    source = models.ForeignKey(
        'ingestion.DataSource',
        on_delete=models.CASCADE,
        related_name='structural_snapshots',
    )
    sheet_name = models.CharField(max_length=200, blank=True, default='')

    structural_fingerprint = models.JSONField(
        help_text='Structural fingerprint: merged cells, blank zones, header candidates, column types',
    )
    confidence_score = models.DecimalField(
        max_digits=5, decimal_places=4, default=0,
        help_text='Heuristic detection confidence 0-1',
    )
    detected_subtables = models.JSONField(
        default=list, blank=True,
        help_text='List of detected sub-tables with their boundaries',
    )
    header_candidates = models.JSONField(
        default=list, blank=True,
        help_text='Candidate header row indices',
    )
    merged_cells = models.JSONField(
        default=list, blank=True,
        help_text='List of merged cell ranges [{start_row, start_col, end_row, end_col}]',
    )
    blank_zones = models.JSONField(
        default=list, blank=True,
        help_text='Detected blank row/column separators',
    )
    column_types = models.JSONField(
        default=dict, blank=True,
        help_text='Per-column detected types {col_name: type}',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Snapshot of {self.source.name} ({self.sheet_name}) conf={self.confidence_score}"

    class Meta:
        db_table = 'nettoyage_rawstructuralsnapshot'
        verbose_name = 'Raw Structural Snapshot'
        verbose_name_plural = 'Raw Structural Snapshots'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source', 'sheet_name']),
        ]


class CorrectionExample(models.Model):
    """
    A human-validated before/after structural transformation.
    Used as few-shot examples for the LLM and for pgvector similarity search.
    """
    SOURCE_CHOICES = [
        ('heuristic', 'Heuristic Only'),
        ('llm', 'LLM Assisted'),
        ('human', 'Pure Human'),
    ]

    snapshot = models.ForeignKey(
        RawStructuralSnapshot,
        on_delete=models.CASCADE,
        related_name='corrections',
        null=True, blank=True,
    )
    source = models.ForeignKey(
        'ingestion.DataSource',
        on_delete=models.CASCADE,
        related_name='correction_examples',
        null=True, blank=True,
    )

    structural_before = models.JSONField(
        help_text='Structural fingerprint before correction',
    )
    structural_after = models.JSONField(
        help_text='Structural fingerprint after correction (human-validated)',
    )
    reconstruction_plan = models.JSONField(
        default=dict, blank=True,
        help_text='The reconstruction plan that was applied',
    )

    description = models.TextField(
        blank=True, default='',
        help_text='Human-readable description of the correction',
    )
    correction_type = models.CharField(
        max_length=50, blank=True, default='structural',
        help_text='Type: structural, header, merge, split, type_correction',
    )
    sous_type_transformation = models.CharField(
        max_length=50, blank=True, default='',
        help_text=(
            'Cell-level sub-type for filtered similarity search: '
            'extraction_champs_texte_libre, correction_caracteres_ambigus, '
            'scission_valeur_unite, explosion_liste_delimitee, or empty'
        ),
    )

    embedding = models.BinaryField(
        null=True, blank=True,
        help_text='pgvector embedding of the structural fingerprint (all-MiniLM-L6-v2)',
    )

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='correction_examples',
    )
    is_validated = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Correction {self.id} ({self.correction_type}) by {self.created_by}"

    class Meta:
        db_table = 'nettoyage_correctionexample'
        verbose_name = 'Correction Example'
        verbose_name_plural = 'Correction Examples'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['correction_type']),
            models.Index(fields=['source']),
        ]


class CleaningRun(models.Model):
    """
    Journal of each intelligent reconstruction execution.
    Tracks which method was used, confidence, examples consulted, and outcome.
    """
    METHOD_CHOICES = [
        ('heuristic', 'Heuristic Only'),
        ('llm', 'LLM Assisted'),
        ('human_review', 'Human Review Required'),
        ('human_corrected', 'Human Corrected'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('detecting', 'Detecting Structure'),
        ('llm_calling', 'Calling LLM'),
        ('validating', 'Validating'),
        ('awaiting_review', 'Awaiting Human Review'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    source = models.ForeignKey(
        'ingestion.DataSource',
        on_delete=models.CASCADE,
        related_name='cleaning_runs',
    )
    snapshot = models.ForeignKey(
        RawStructuralSnapshot,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cleaning_runs',
    )

    method_used = models.CharField(
        max_length=20, choices=METHOD_CHOICES, default='heuristic',
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending',
    )
    confidence_score = models.DecimalField(
        max_digits=5, decimal_places=4, default=0,
        help_text='Final confidence score after all steps',
    )

    correction_examples_used = models.JSONField(
        default=list, blank=True,
        help_text='IDs of CorrectionExample used as few-shot examples',
    )
    llm_model = models.CharField(max_length=100, blank=True, default='')
    llm_tokens_used = models.IntegerField(default=0)
    llm_duration_ms = models.IntegerField(default=0)

    reconstruction_plan = models.JSONField(
        default=dict, blank=True,
        help_text='Final reconstruction plan applied or proposed',
    )
    validation_gates_passed = models.BooleanField(default=True)
    validation_gates_detail = models.JSONField(
        default=dict, blank=True,
        help_text='Per-gate results',
    )

    sheet_name = models.CharField(max_length=200, blank=True, default='')
    rows_before = models.IntegerField(default=0)
    rows_after = models.IntegerField(default=0)
    columns_before = models.IntegerField(default=0)
    columns_after = models.IntegerField(default=0)
    subtables_detected = models.IntegerField(default=0)

    duration_ms = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, default='')

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cleaning_runs',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"CleaningRun {self.id} on {self.source.name} ({self.method_used})"

    class Meta:
        db_table = 'nettoyage_cleaningrun'
        verbose_name = 'Cleaning Run'
        verbose_name_plural = 'Cleaning Runs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source', 'status']),
            models.Index(fields=['method_used']),
        ]
