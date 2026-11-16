/**
 * Pivot Table Type Definitions
 * Data structures for advanced pivot table configuration and responses
 */

export interface FilterCondition {
  field: string;
  operator: 'eq' | 'neq' | 'gt' | 'gte' | 'lt' | 'lte' | 'in' | 'between' | 'contains';
  value: string | string[] | number | [number, number];
}

export interface PivotConfig {
  sourceId: number;
  sourceType: 'raw' | 'cleaned';
  rowFields: string[];
  columnFields: string[];
  valueField: string;
  aggregation: 'sum' | 'avg' | 'count' | 'min' | 'max' | 'median' | 'std';
  filters: FilterCondition[];
  includeTotals: boolean;
  includeRunningTotals: boolean;
  formatCurrency: boolean;
  sortBy: 'value' | 'label';
  sortDirection: 'asc' | 'desc';
  topN?: number;
}

export interface PivotCell {
  value: number;
  formatted: string;
  isTotal?: boolean;
  isDrillable?: boolean;
}

export interface PivotMetadata {
  rows_processed: number;
  execution_time_ms: number;
  data_quality_score: number;
}

export interface PivotTotals {
  row_totals: number[];
  col_totals: number[];
  grand_total: number;
}

export interface PivotData {
  pivot: number[][];
  formatted_pivot?: string[][];
  row_headers: string[];
  col_headers: string[];
  row_labels: string[];
  col_labels: string[];
  totals: PivotTotals;
  metadata: PivotMetadata;
  drill_down_available: Record<string, boolean>;
}

export interface PivotResponse {
  success: boolean;
  data: PivotData;
  message: string;
}

export interface DrillDownRow {
  [key: string]: string | number | null;
}

export interface DrillDownResponse {
  success: boolean;
  rows: DrillDownRow[];
  row_count: number;
  columns: string[];
}

export interface AvailableField {
  name: string;
  type: string;
  sampleValues: (string | number)[];
}

export interface PivotConfigState {
  sourceId: number | null;
  sourceType: 'raw' | 'cleaned';
  rowFields: string[];
  columnFields: string[];
  valueField: string | null;
  aggregation: 'sum' | 'avg' | 'count' | 'min' | 'max' | 'median' | 'std';
  filters: FilterCondition[];
  includeTotals: boolean;
  formatCurrency: boolean;
  sortBy: 'value' | 'label';
  sortDirection: 'asc' | 'desc';
  topN: number | null;
}

export interface DragItem {
  id: string;
  name: string;
  type: 'field';
}

export interface DrillDownContext {
  rowKey: string;
  colKey: string;
  rowIndex: number;
  colIndex: number;
  cellValue: number;
}
