/**
 * PivotTableRenderer
 * Renders pivot table with sorting, formatting, and drill-down
 */

import { FC } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Card } from '@/components/ui/card';
import type { PivotData, DrillDownContext } from '@/types/pivot';
import { cn } from '@/lib/utils';
import { ChevronDown } from 'lucide-react';

interface PivotTableRendererProps {
  data: PivotData;
  isLoading?: boolean;
  onCellClick?: (context: DrillDownContext) => void;
  onSort?: (field: string, direction: 'asc' | 'desc') => void;
}

export const PivotTableRenderer: FC<PivotTableRendererProps> = ({
  data,
  isLoading = false,
  onCellClick,
  onSort,
}) => {
  const formatNumber = (value: number | string): string => {
    if (typeof value === 'string') return value;
    if (Number.isNaN(value)) return '-';
    return new Intl.NumberFormat('fr-FR', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const isTotal = (index: number, isRow: boolean): boolean => {
    if (isRow) return data.row_headers[index]?.toUpperCase() === 'TOTAL';
    return data.col_headers[index]?.toUpperCase() === 'TOTAL';
  };

  if (isLoading) {
    return (
      <Card className="p-8 flex items-center justify-center">
        <div className="animate-spin">Construction du tableau croisé...</div>
      </Card>
    );
  }

  if (!data.pivot || data.pivot.length === 0) {
    return (
      <Card className="p-8 text-center text-muted-foreground">
        Aucune donnée pour cette configuration
      </Card>
    );
  }

  return (
    <div className="rounded-lg border border-border/60 overflow-hidden shadow-card">
      <div className="overflow-x-auto">
        <Table>
          <TableHead>
            <TableRow className="bg-muted hover:bg-muted">
              <TableHeader className="w-32 font-semibold text-xs">
                {data.row_labels.join(' / ') || 'Lignes'}
              </TableHeader>
              {data.col_headers.map((header, idx) => (
                <TableHeader
                  key={`col-${idx}`}
                  className={cn(
                    'text-center font-semibold text-xs cursor-pointer hover:bg-muted/50',
                    isTotal(idx, false) && 'bg-blue-50 font-bold'
                  )}
                  onClick={() => onSort?.(header, 'desc')}
                >
                  <div className="flex items-center justify-center gap-1">
                    {header}
                    {idx < data.col_headers.length - 1 && (
                      <ChevronDown className="w-3 h-3 opacity-50" />
                    )}
                  </div>
                </TableHeader>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {data.row_headers.map((rowHeader, rowIdx) => (
              <TableRow
                key={`row-${rowIdx}`}
                className={cn(
                  isTotal(rowIdx, true) && 'bg-blue-50 font-bold border-t-2 border-blue-200'
                )}
              >
                <TableCell
                  className={cn(
                    'font-medium text-xs px-3 py-2 sticky left-0 bg-muted z-10',
                    isTotal(rowIdx, true) && 'bg-blue-100 font-bold'
                  )}
                >
                  {rowHeader}
                </TableCell>
                {data.pivot[rowIdx].map((cellValue, colIdx) => {
                  const isDrillable =
                    data.drill_down_available[`row_${rowIdx}_col_${colIdx}`] &&
                    !isTotal(rowIdx, true) &&
                    !isTotal(colIdx, false);

                  return (
                    <TableCell
                      key={`cell-${rowIdx}-${colIdx}`}
                      className={cn(
                        'text-right text-xs px-2 py-2 transition-colors',
                        isTotal(rowIdx, true) || isTotal(colIdx, false)
                          ? 'bg-blue-50 font-bold'
                          : 'hover:bg-accent/50',
                        isDrillable && 'cursor-pointer hover:bg-blue-100'
                      )}
                      onClick={() => {
                        if (isDrillable && onCellClick) {
                          onCellClick({
                            rowKey: rowHeader,
                            colKey: data.col_headers[colIdx],
                            rowIndex: rowIdx,
                            colIndex: colIdx,
                            cellValue,
                          });
                        }
                      }}
                    >
                      <div className="flex items-center justify-between gap-1">
                        <span>{formatNumber(cellValue)}</span>
                        {isDrillable && (
                          <span className="opacity-0 group-hover:opacity-100 text-blue-500">
                            ↓
                          </span>
                        )}
                      </div>
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {data.metadata && (
        <div className="flex items-center gap-4 border-t px-4 py-2 text-xs text-muted-foreground">
          <span>{data.metadata.rows_processed.toLocaleString()} lignes traitées</span>
          <span>{data.metadata.execution_time_ms} ms d'exécution</span>
          {data.metadata.data_quality_score != null && (
            <span>Qualité : {data.metadata.data_quality_score}%</span>
          )}
        </div>
      )}
    </div>
  );
};

export default PivotTableRenderer;
