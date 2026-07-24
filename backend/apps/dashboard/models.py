from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.contrib.auth.models import User


class Dashboard(models.Model):
    """
    Interactive dashboard configurations.
    Defines layout, widgets, and access control for data visualization dashboards.
    """
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    slug = models.SlugField(max_length=200, unique=True, help_text="URL-friendly: sales-overview")
    
    # Layout configuration
    layout = models.JSONField(help_text="Grid layout, widget positions")
    grid_columns = models.IntegerField(default=12, help_text="Bootstrap-style grid")
    refresh_interval = models.IntegerField(default=300, help_text="Auto-refresh seconds")
    
    # Filters & parameters
    default_filters = models.JSONField(default=dict, blank=True, help_text="Pre-applied filters")
    available_parameters = models.JSONField(default=dict, blank=True, help_text="User-controllable params")
    
    # Access control
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_dashboards')
    is_public = models.BooleanField(default=False, help_text="Share with everyone?")
    allowed_roles = models.JSONField(default=list, blank=True, help_text="Which roles can view?")
    allowed_users = models.JSONField(default=list, blank=True, help_text="Specific user IDs")
    
    # Metadata
    category = models.CharField(max_length=100, blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, null=True)
    color_theme = models.CharField(max_length=50, blank=True, null=True)
    tags = models.JSONField(default=list, blank=True)
    is_favorite = models.BooleanField(default=False)
    
    # Analytics
    view_count = models.IntegerField(default=0)
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    
    # Advanced features
    parent_dashboard = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='child_dashboards')
    export_enabled = models.BooleanField(default=True)
    screenshot_url = models.URLField(max_length=500, blank=True, null=True, help_text="Thumbnail preview")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        db_table = 'dashboard_dashboard'
        verbose_name = 'Dashboard'
        verbose_name_plural = 'Dashboards'
        ordering = ['-is_public', '-view_count']


class Widget(models.Model):
    """
    Individual widgets within dashboards.
    Defines chart type, data source, position, and styling.
    """
    WIDGET_TYPE_CHOICES = [
        ('metric_card', 'Metric Card'),
        ('line_chart', 'Line Chart'),
        ('bar_chart', 'Bar Chart'),
        ('pie_chart', 'Pie Chart'),
        ('table', 'Data Table'),
        ('gauge', 'Gauge'),
        ('scatter_plot', 'Scatter Plot'),
        ('heatmap', 'Heatmap'),
    ]
    
    DATA_SOURCE_TYPE_CHOICES = [
        ('kpi', 'KPI'),
        ('query', 'Custom Query'),
        ('api', 'External API'),
        ('static', 'Static Data'),
    ]
    
    TEXT_ALIGNMENT_CHOICES = [
        ('left', 'Left'),
        ('center', 'Center'),
        ('right', 'Right'),
    ]
    
    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name='widgets')
    name = models.CharField(max_length=200, blank=True, null=True)
    widget_type = models.CharField(max_length=50, choices=WIDGET_TYPE_CHOICES)
    
    # Position & size (for drag-and-drop)
    position_x = models.IntegerField(default=0, help_text="Grid column start")
    position_y = models.IntegerField(default=0, help_text="Grid row start")
    width = models.IntegerField(default=3, help_text="Grid columns span")
    height = models.IntegerField(default=2, help_text="Grid rows span")
    min_width = models.IntegerField(default=2)
    min_height = models.IntegerField(default=1)
    
    # Data configuration
    data_source_type = models.CharField(max_length=50, choices=DATA_SOURCE_TYPE_CHOICES, blank=True, null=True)
    data_source_id = models.IntegerField(null=True, blank=True, help_text="Reference to KPI or Query")
    data_query = models.TextField(blank=True, null=True, help_text="Custom SQL query")
    api_endpoint = models.URLField(max_length=500, blank=True, null=True)
    
    # Visualization settings
    configuration = models.JSONField(help_text="Chart-specific settings")
    
    # Display options
    title = models.CharField(max_length=200, blank=True, null=True)
    subtitle = models.CharField(max_length=500, blank=True, null=True)
    show_title = models.BooleanField(default=True)
    show_border = models.BooleanField(default=True)
    background_color = models.CharField(max_length=7, blank=True, null=True, help_text="Hex: #FFFFFF")
    text_alignment = models.CharField(max_length=10, choices=TEXT_ALIGNMENT_CHOICES, default='left')
    
    # Interactivity
    is_drillable = models.BooleanField(default=False, help_text="Click to drill down?")
    drill_down_target = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='drill_down_widgets')
    tooltip_template = models.TextField(blank=True, null=True, help_text="Custom hover text")
    
    # State
    is_visible = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    
    # Advanced features
    cache_key = models.CharField(max_length=100, blank=True, null=True)
    cache_expires_at = models.DateTimeField(null=True, blank=True)
    animation_enabled = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.widget_type} - {self.title or 'Untitled'}"
    
    class Meta:
        db_table = 'dashboard_widget'
        verbose_name = 'Widget'
        verbose_name_plural = 'Widgets'
        ordering = ['position_y', 'position_x']
        indexes = [
            models.Index(fields=['dashboard', 'is_active']),
        ]


class Visualization(models.Model):
    """
    Saved visualization templates.
    Reusable chart configurations that can be used across dashboards.
    """
    VIZ_TYPE_CHOICES = [
        ('line', 'Line Chart'),
        ('bar', 'Bar Chart'),
        ('pie', 'Pie Chart'),
        ('area', 'Area Chart'),
        ('scatter', 'Scatter Plot'),
        ('bubble', 'Bubble Chart'),
        ('heatmap', 'Heatmap'),
        ('treemap', 'Treemap'),
        ('funnel', 'Funnel Chart'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    viz_type = models.CharField(max_length=50, choices=VIZ_TYPE_CHOICES)
    
    # Data sources
    primary_data_source = models.CharField(max_length=100, help_text="Table or view name")
    related_data_sources = models.JSONField(default=dict, blank=True, help_text="JOIN information")
    
    # Configuration
    x_axis_field = models.CharField(max_length=100, blank=True, null=True, help_text="Usually time or category")
    y_axis_fields = models.JSONField(default=list, blank=True, help_text="Measures (can be multiple)")
    group_by_fields = models.JSONField(default=list, blank=True, help_text="Dimensions for grouping")
    filter_conditions = models.JSONField(default=dict, blank=True, help_text="WHERE clauses")
    aggregation_methods = models.JSONField(default=dict, blank=True, help_text="SUM, AVG, COUNT per field")
    
    # Styling
    style_config = models.JSONField(help_text="Colors, fonts, labels, legends")
    template_type = models.CharField(max_length=50, blank=True, null=True, help_text="Standard, comparison, stacked, percent")
    
    # Reusability
    is_template = models.BooleanField(default=True, help_text="Available for all users?")
    is_public = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_visualizations')
    
    usage_count = models.IntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    tags = models.JSONField(default=list, blank=True)
    thumbnail_url = models.URLField(max_length=500, blank=True, null=True, help_text="Preview image")
    
    # Advanced features
    animation_config = models.JSONField(default=dict, blank=True, help_text="Transitions, duration, easing")
    responsive_config = models.JSONField(default=dict, blank=True, help_text="Mobile/tablet adaptations")
    export_formats = models.JSONField(default=list, blank=True, help_text="['PDF', 'PNG', 'CSV', 'Excel']")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_viz_type_display()})"
    
    class Meta:
        db_table = 'dashboard_visualization'
        verbose_name = 'Visualization'
        verbose_name_plural = 'Visualizations'
        ordering = ['-usage_count', '-created_at']


class PreferenceUtilisateur(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    colonnes_tableau = models.JSONField(default=list, help_text='Liste ordonnée des colonnes affichées')
    kpis_visibles = models.JSONField(default=list, help_text='Liste des KPI affichés sur le dashboard')
    kpis_ordre = models.JSONField(default=list, help_text='Ordre d\'affichage des KPI cards')
    layout_dashboard = models.JSONField(default=dict, help_text='Configuration de la disposition des widgets')
    periode_defaut = models.CharField(
        max_length=20,
        default='mois_en_cours',
        choices=[
            ('mois_en_cours', 'Mois en cours'),
            ('trimestre_en_cours', 'Trimestre en cours'),
            ('annee_en_cours', 'Année en cours'),
            ('30_derniers_jours', '30 derniers jours'),
            ('personnalise', 'Période personnalisée'),
        ],
    )
    devise = models.CharField(max_length=5, default='FCFA')
    format_nombres = models.CharField(
        max_length=20,
        default='fr-FR',
        choices=[
            ('fr-FR', 'Français (1 740 000)'),
            ('en-US', 'Anglais (1,740,000)'),
        ],
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Préférence utilisateur'

    def __str__(self):
        return f'Préférences de {self.user.username}'


class VuePersonnalisee(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vues')
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icone = models.CharField(max_length=10, default='📊')
    config = models.JSONField()
    is_default = models.BooleanField(default=False)
    is_partagee = models.BooleanField(default=False)
    ordre = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Vue personnalisée'
        ordering = ['ordre', 'nom']
        constraints = [
            models.CheckConstraint(condition=models.Q(ordre__lte=20), name='max_vues_par_utilisateur'),
        ]

    def clean(self):
        if self.user_id and self.pk is None:
            existing = VuePersonnalisee.objects.filter(user=self.user).count()
            if existing >= 20:
                raise ValidationError({'nom': 'Maximum 20 vues par utilisateur.'})

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.is_default:
                VuePersonnalisee.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
            super().save(*args, **kwargs)

    def __str__(self):
        return self.nom
