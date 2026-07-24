from rest_framework import serializers

from apps.dashboard.models import Dashboard, Widget, PreferenceUtilisateur, VuePersonnalisee
from apps.dashboard.services import discover_available_columns, discover_available_kpis
from apps.kpi.serializers import DashboardPreviewRequestSerializer, DashboardPreviewResponseSerializer


class RankingItemSerializer(serializers.Serializer):
    name = serializers.CharField()
    revenue = serializers.FloatField()
    revenue_label = serializers.CharField()
    share_percent = serializers.FloatField(required=False)
    quantity = serializers.FloatField(required=False)


class SalesTrendItemSerializer(serializers.Serializer):
    label = serializers.CharField()
    value = serializers.FloatField()


class DashboardAnalyticsSummarySerializer(serializers.Serializer):
    sources_count = serializers.IntegerField()
    rows_count = serializers.IntegerField()
    revenue_total = serializers.FloatField()


class DashboardAnalyticsSerializer(serializers.Serializer):
    summary = DashboardAnalyticsSummarySerializer()
    sales_trend = SalesTrendItemSerializer(many=True)
    top_products = RankingItemSerializer(many=True)
    top_clients = RankingItemSerializer(many=True)
    territories = RankingItemSerializer(many=True)


class DashboardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dashboard
        fields = [
            'id', 'name', 'description', 'slug', 'layout', 'grid_columns', 'refresh_interval',
            'default_filters', 'available_parameters', 'is_public', 'allowed_roles', 'allowed_users',
            'category', 'icon', 'color_theme', 'tags', 'is_favorite', 'view_count', 'last_viewed_at',
            'parent_dashboard', 'export_enabled', 'screenshot_url', 'is_active', 'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'slug': {'required': False, 'allow_blank': True},
        }


class WidgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Widget
        fields = [
            'id', 'dashboard', 'name', 'widget_type', 'position_x', 'position_y', 'width', 'height',
            'min_width', 'min_height', 'data_source_type', 'data_source_id', 'data_query', 'api_endpoint',
            'configuration', 'title', 'subtitle', 'show_title', 'show_border', 'background_color',
            'text_alignment', 'is_drillable', 'drill_down_target', 'tooltip_template', 'is_visible',
            'is_active', 'cache_key', 'cache_expires_at', 'animation_enabled', 'created_at', 'updated_at',
        ]


class WidgetPositionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    position_x = serializers.IntegerField()
    position_y = serializers.IntegerField()
    width = serializers.IntegerField(required=False)
    height = serializers.IntegerField(required=False)


class WidgetReorderSerializer(serializers.Serializer):
    widgets = WidgetPositionSerializer(many=True, min_length=1)


class DashboardPreviewSerializer(DashboardPreviewResponseSerializer):
    class Meta:
        ref_name = 'DashboardPreviewResponse'


class DashboardPreviewRequestWrapperSerializer(DashboardPreviewRequestSerializer):
    class Meta:
        ref_name = 'DashboardPreviewRequest'


class PreferenceUtilisateurSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreferenceUtilisateur
        fields = [
            'id', 'user', 'colonnes_tableau', 'kpis_visibles', 'kpis_ordre',
            'layout_dashboard', 'periode_defaut', 'devise', 'format_nombres', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'updated_at']

    def validate_colonnes_tableau(self, value):
        request = self.context.get('request')
        if not request:
            return value
        available = set(discover_available_columns(request.user))
        invalid = [column for column in value if column not in available]
        if invalid:
            raise serializers.ValidationError(f"Colonnes inconnues: {', '.join(invalid)}")
        return value

    def validate_kpis_visibles(self, value):
        request = self.context.get('request')
        if not request:
            return value
        available = set(discover_available_kpis(request.user))
        invalid = [kpi for kpi in value if kpi not in available]
        if invalid:
            raise serializers.ValidationError(f"KPI inconnus: {', '.join(invalid)}")
        return value

    def validate_kpis_ordre(self, value):
        return value


class VuePersonnaliseeSerializer(serializers.ModelSerializer):
    proprietaire = serializers.CharField(source='user.get_full_name', read_only=True)

    class Meta:
        model = VuePersonnalisee
        fields = [
            'id', 'user', 'nom', 'description', 'icone', 'config', 'is_default',
            'is_partagee', 'ordre', 'proprietaire', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'proprietaire', 'created_at', 'updated_at']

    def validate_config(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('config must be an object')
        return value
