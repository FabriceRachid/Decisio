export type DashboardData = {
  dashboard: {
    id: number;
    name: string;
    slug: string;
    source_name: string;
    source_id: number;
    domain: string;
  };
  widgets: WidgetData[];
};

export type WidgetData = {
  id: number;
  title: string;
  type: string;
  position: { x: number; y: number; w: number; h: number };
  auto_generated?: boolean;
  chart_type_override?: string | null;
  payload: {
    nom_kpi?: string;
    value?: number;
    formatted_value?: string;
    rows_processed?: number;
    breakdown?: Array<Record<string, any>>;
    group_by?: string[];
    chart_type?: string;
    data_quality_score?: number;
    measure?: string;
    aggregation?: string;
    error?: string;
    semantic_type?: string;
  };
};

export type ChartDatum = { name: string; value: number };

export type QuickAnalysisConfig = {
  measure: string;
  aggregation: string;
  groupBy: string;
};
