/**
 * usePivotTable Hook
 * Manages pivot table API calls, loading states, and caching
 */

import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import type { PivotConfig, PivotResponse, DrillDownResponse, DrillDownContext } from '@/types/pivot';

export const usePivotTable = () => {
  // Build pivot table mutation
  const buildPivotMutation = useMutation({
    mutationFn: async (config: PivotConfig): Promise<PivotResponse> => {
      const payload = {
        source_id: config.sourceId,
        source_type: config.sourceType,
        row_fields: config.rowFields,
        column_fields: config.columnFields,
        value_field: config.valueField,
        aggregation: config.aggregation,
        filters: config.filters,
        include_totals: config.includeTotals,
        include_running_totals: config.includeRunningTotals,
        format_currency: config.formatCurrency,
        sort_by: config.sortBy,
        sort_direction: config.sortDirection,
        top_n: config.topN,
      };

      const response = await apiClient.buildAdvancedPivot(payload);

      if (!response.success) {
        throw new Error(response.message || 'Failed to build pivot table');
      }

      return response;
    },
    onError: (error) => {
      console.error('Pivot build error:', error);
    },
  });

  // Drill down mutation
  const drillDownMutation = useMutation({
    mutationFn: async (params: {
      pivotConfig: PivotConfig;
      drillDownContext: DrillDownContext;
    }): Promise<DrillDownResponse> => {
      const { pivotConfig, drillDownContext } = params;
      const payload = {
        pivot_config: {
          source_id: pivotConfig.sourceId,
          source_type: pivotConfig.sourceType,
          row_fields: pivotConfig.rowFields,
          column_fields: pivotConfig.columnFields,
          value_field: pivotConfig.valueField,
          aggregation: pivotConfig.aggregation,
          filters: pivotConfig.filters,
        },
        row_key: drillDownContext.rowKey,
        col_key: drillDownContext.colKey,
      };

      const response = await apiClient.drillDownPivot(payload);

      if (!response.success) {
        throw new Error('Failed to drill down');
      }

      return response;
    },
  });

  return {
    buildPivot: buildPivotMutation.mutate,
    buildPivotAsync: buildPivotMutation.mutateAsync,
    drillDown: drillDownMutation.mutate,
    drillDownAsync: drillDownMutation.mutateAsync,
    isBuilding: buildPivotMutation.isPending,
    isDrillingDown: drillDownMutation.isPending,
    pivotData: buildPivotMutation.data,
    drillDownData: drillDownMutation.data,
    error: buildPivotMutation.error || drillDownMutation.error,
    reset: () => {
      buildPivotMutation.reset();
      drillDownMutation.reset();
    },
  };
};

export default usePivotTable;
