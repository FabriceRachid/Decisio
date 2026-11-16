/**
 * DrillDownModal
 * Modal showing detail rows for a drilled-down pivot cell
 */

import { FC, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { DrillDownResponse, DrillDownContext } from '@/types/pivot';
import { X, Download } from 'lucide-react';

interface DrillDownModalProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  context?: DrillDownContext;
  data?: DrillDownResponse;
  isLoading?: boolean;
  error?: Error | null;
  onExport?: () => void;
}

export const DrillDownModal: FC<DrillDownModalProps> = ({
  isOpen,
  onOpenChange,
  context,
  data,
  isLoading = false,
  error,
  onExport,
}) => {
  const handleExport = () => {
    if (!data?.rows || data.rows.length === 0) return;

    const csv = [
      data.columns.join(','),
      ...data.rows.map((row) =>
        data.columns.map((col) => {
          const val = row[col];
          return typeof val === 'string' ? `"${val.replace(/"/g, '""')}"` : String(val ?? '');
        }).join(',')
      ),
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `drill-down-${Date.now()}.csv`;
    link.click();
    URL.revokeObjectURL(url);

    onExport?.();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-96 overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between">
            <span>Détail - Cellule</span>
            <DialogClose asChild>
              <Button variant="ghost" size="sm">
                <X className="w-4 h-4" />
              </Button>
            </DialogClose>
          </DialogTitle>
          <DialogDescription>
            {context && (
              <div className="flex items-center gap-4 mt-2">
                <Badge variant="outline">Ligne: {context.rowKey}</Badge>
                <Badge variant="outline">Colonne: {context.colKey}</Badge>
                <Badge variant="secondary">Valeur: {context.cellValue}</Badge>
              </div>
            )}
          </DialogDescription>
        </DialogHeader>

        {isLoading && (
          <Card className="p-8 flex items-center justify-center">
            <div className="animate-spin">⏳ Chargement des détails...</div>
          </Card>
        )}

        {error && (
          <Card className="p-4 border-destructive bg-destructive/5 text-destructive">
            Erreur: {error.message}
          </Card>
        )}

        {data && !isLoading && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                📊 <strong>{data.row_count}</strong> lignes détail
              </span>
              <Button
                size="sm"
                variant="outline"
                onClick={handleExport}
                disabled={!data.rows || data.rows.length === 0}
              >
                <Download className="w-4 h-4 mr-1" />
                Exporter CSV
              </Button>
            </div>

            {data.rows && data.rows.length > 0 ? (
              <div className="border border-border/60 rounded-lg overflow-x-auto">
                <Table className="text-xs">
                  <TableHead>
                    <TableRow className="bg-muted">
                      {data.columns.map((col) => (
                        <TableHeader key={col} className="font-semibold text-xs px-2 py-2">
                          {col}
                        </TableHeader>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.rows.map((row, idx) => (
                      <TableRow key={idx} className="hover:bg-muted/50">
                        {data.columns.map((col) => (
                          <TableCell key={`${idx}-${col}`} className="px-2 py-2">
                            {String(row[col] ?? '-')}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <Card className="p-4 text-center text-muted-foreground">
                Aucune donnée détail pour cette cellule
              </Card>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default DrillDownModal;
