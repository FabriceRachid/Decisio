import { FC, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import type { PivotConfigState, AvailableField, FilterCondition } from '@/types/pivot';
import type { DataSourceDetail } from '@/lib/api';
import { X, Plus, ChevronDown, Settings2, Database, Filter } from 'lucide-react';
import { cn } from '@/lib/utils';

interface PivotConfigPanelProps {
  config: PivotConfigState;
  availableFields: AvailableField[];
  sources: DataSourceDetail[];
  loadingFields?: boolean;
  onConfigChange: (config: PivotConfigState) => void;
  onSourceChange: (sourceId: number) => void;
  onBuild: () => void;
  isLoading?: boolean;
}

const AGGREGATION_LABELS: Record<string, string> = {
  sum: 'Somme',
  avg: 'Moyenne',
  count: 'Nombre',
  min: 'Minimum',
  max: 'Maximum',
  median: 'Médiane',
  std: 'Écart-type',
};

const OPERATOR_LABELS: Record<string, string> = {
  eq: '=',
  neq: '≠',
  gt: '>',
  gte: '≥',
  lt: '<',
  lte: '≤',
  in: 'Parmi',
  between: 'Entre',
  contains: 'Contient',
};

export const PivotConfigPanel: FC<PivotConfigPanelProps> = ({
  config,
  availableFields,
  sources,
  loadingFields = false,
  onConfigChange,
  onSourceChange,
  onBuild,
  isLoading = false,
}) => {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  const fieldOptions = availableFields.map((f) => ({
    value: f.name,
    label: f.name,
    type: f.type,
  }));

  const numericFields = fieldOptions.filter((f) => f.type === 'decimal' || f.type === 'integer');
  const categoricalFields = fieldOptions.filter((f) => f.type === 'string');

  const handleAddRowField = (field: string) => {
    if (!config.rowFields.includes(field)) {
      onConfigChange({ ...config, rowFields: [...config.rowFields, field] });
    }
  };

  const handleRemoveRowField = (field: string) => {
    onConfigChange({ ...config, rowFields: config.rowFields.filter((f) => f !== field) });
  };

  const handleAddColField = (field: string) => {
    if (!config.columnFields.includes(field)) {
      onConfigChange({ ...config, columnFields: [...config.columnFields, field] });
    }
  };

  const handleRemoveColField = (field: string) => {
    onConfigChange({ ...config, columnFields: config.columnFields.filter((f) => f !== field) });
  };

  const handleAddFilter = () => {
    onConfigChange({
      ...config,
      filters: [...config.filters, { field: '', operator: 'eq', value: '' }],
    });
  };

  const handleUpdateFilter = (index: number, update: Partial<FilterCondition>) => {
    const newFilters = [...config.filters];
    newFilters[index] = { ...newFilters[index], ...update };
    onConfigChange({ ...config, filters: newFilters });
  };

  const handleRemoveFilter = (index: number) => {
    onConfigChange({ ...config, filters: config.filters.filter((_, i) => i !== index) });
  };

  const isValid = config.sourceId && config.valueField && (config.rowFields.length > 0 || config.columnFields.length > 0);

  return (
    <div className="w-full max-w-md space-y-4 p-4 bg-card rounded-lg border border-border/60 shadow-card">
      {/* Source Selection */}
      <div className="space-y-2">
        <Label className="text-sm font-semibold flex items-center gap-2">
          <Database className="h-3.5 w-3.5 text-primary-strong" />
          Source de données
        </Label>
        <Select
          value={config.sourceId ? String(config.sourceId) : ''}
          onValueChange={(v) => onSourceChange(Number(v))}
        >
          <SelectTrigger className="text-xs">
            <SelectValue placeholder="Choisir une source…" />
          </SelectTrigger>
          <SelectContent>
            {sources.map((s) => (
              <SelectItem key={s.id} value={String(s.id)}>
                {s.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex items-center gap-2">
          <Select
            value={config.sourceType}
            onValueChange={(v) => onConfigChange({ ...config, sourceType: v as 'raw' | 'cleaned' })}
          >
            <SelectTrigger className="text-xs flex-1">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="raw">Données Brutes</SelectItem>
              <SelectItem value="cleaned">Données Nettoyées</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Value Field */}
      <div className="space-y-2">
        <Label className="text-sm font-semibold">Calculer</Label>
        {loadingFields ? (
          <div className="text-xs text-muted-foreground p-2">Chargement des colonnes…</div>
        ) : (
          <Select
            value={config.valueField || ''}
            onValueChange={(v) => onConfigChange({ ...config, valueField: v })}
          >
            <SelectTrigger className="text-xs">
              <SelectValue placeholder="Sélectionner une métrique" />
            </SelectTrigger>
            <SelectContent>
              {fieldOptions.map((field) => (
                <SelectItem key={field.value} value={field.value}>
                  {field.label} ({field.type})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {/* Aggregation */}
      <div className="space-y-2">
        <Label className="text-sm font-semibold">Agrégation</Label>
        <Select
          value={config.aggregation}
          onValueChange={(v) => onConfigChange({ ...config, aggregation: v as any })}
        >
          <SelectTrigger className="text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(AGGREGATION_LABELS).map(([key, label]) => (
              <SelectItem key={key} value={key}>{label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Separator />

      {/* Row Fields */}
      <div className="space-y-3">
        <Label className="text-sm font-semibold">Par (Dimensions)</Label>
        <div className="space-y-1">
          {config.rowFields.length === 0 ? (
            <div className="text-xs text-muted-foreground p-2 bg-muted/30 rounded border-dashed border">
              Ajoutez des champs ci-dessous
            </div>
          ) : (
            config.rowFields.map((field) => (
              <Badge key={field} variant="secondary" className="flex items-center justify-between gap-2 px-2 py-1">
                {field}
                <button onClick={() => handleRemoveRowField(field)} className="ml-auto hover:text-destructive">
                  <X className="w-3 h-3" />
                </button>
              </Badge>
            ))
          )}
        </div>
        <div className="text-xs space-y-1 max-h-32 overflow-y-auto">
          {fieldOptions
            .filter((f) => !config.rowFields.includes(f.value) && !config.columnFields.includes(f.value))
            .map((field) => (
              <button
                key={field.value}
                onClick={() => handleAddRowField(field.value)}
                className="block w-full text-left p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition"
              >
                + {field.label}
              </button>
            ))
          }
        </div>
      </div>

      {/* Column Fields */}
      <div className="space-y-3">
        <Label className="text-sm font-semibold">Sous-colonnes (optionnel)</Label>
        <div className="space-y-1">
          {config.columnFields.length === 0 ? (
            <div className="text-xs text-muted-foreground p-2 bg-muted/30 rounded border-dashed border">
              Ajoutez des champs ci-dessous
            </div>
          ) : (
            config.columnFields.map((field) => (
              <Badge key={field} variant="outline" className="flex items-center justify-between gap-2 px-2 py-1">
                {field}
                <button onClick={() => handleRemoveColField(field)} className="ml-auto hover:text-destructive">
                  <X className="w-3 h-3" />
                </button>
              </Badge>
            ))
          )}
        </div>
        <div className="text-xs space-y-1 max-h-32 overflow-y-auto">
          {fieldOptions
            .filter((f) => !config.rowFields.includes(f.value) && !config.columnFields.includes(f.value))
            .map((field) => (
              <button
                key={field.value}
                onClick={() => handleAddColField(field.value)}
                className="block w-full text-left p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition"
              >
                + {field.label}
              </button>
            ))
          }
        </div>
      </div>

      <Separator />

      {/* Filters */}
      <Collapsible open={showFilters} onOpenChange={setShowFilters}>
        <CollapsibleTrigger className="flex items-center gap-2 text-sm font-semibold hover:opacity-70">
          <Filter className="w-4 h-4" />
          Filtres ({config.filters.length})
          <ChevronDown className={cn('w-4 h-4 transition-transform', showFilters && 'rotate-180')} />
        </CollapsibleTrigger>
        <CollapsibleContent className="space-y-3 mt-3">
          {config.filters.map((filter, idx) => (
            <div key={idx} className="flex items-center gap-1 text-xs">
              <Select value={filter.field} onValueChange={(v) => handleUpdateFilter(idx, { field: v })}>
                <SelectTrigger className="w-[100px] text-xs">
                  <SelectValue placeholder="Champ" />
                </SelectTrigger>
                <SelectContent>
                  {categoricalFields.map((f) => (
                    <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={filter.operator} onValueChange={(v) => handleUpdateFilter(idx, { operator: v as any })}>
                <SelectTrigger className="w-[60px] text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(OPERATOR_LABELS).map(([key, label]) => (
                    <SelectItem key={key} value={key}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input
                className="flex-1 text-xs"
                placeholder="Valeur"
                value={typeof filter.value === 'string' ? filter.value : ''}
                onChange={(e) => handleUpdateFilter(idx, { value: e.target.value })}
              />
              <button onClick={() => handleRemoveFilter(idx)} className="text-muted-foreground hover:text-destructive">
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={handleAddFilter} className="w-full text-xs">
            <Plus className="w-3 h-3 mr-1" /> Ajouter un filtre
          </Button>
        </CollapsibleContent>
      </Collapsible>

      {/* Advanced Options */}
      <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
        <CollapsibleTrigger className="flex items-center gap-2 text-sm font-semibold hover:opacity-70">
          <Settings2 className="w-4 h-4" />
          Options avancées
          <ChevronDown className={cn('w-4 h-4 transition-transform', showAdvanced && 'rotate-180')} />
        </CollapsibleTrigger>
        <CollapsibleContent className="space-y-3 mt-3">
          <div className="flex items-center space-x-2">
            <Checkbox
              id="include-totals"
              checked={config.includeTotals}
              onCheckedChange={(c) => onConfigChange({ ...config, includeTotals: Boolean(c) })}
            />
            <Label htmlFor="include-totals" className="text-xs cursor-pointer">Inclure les totaux</Label>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox
              id="format-currency"
              checked={config.formatCurrency}
              onCheckedChange={(c) => onConfigChange({ ...config, formatCurrency: Boolean(c) })}
            />
            <Label htmlFor="format-currency" className="text-xs cursor-pointer">Format FCFA</Label>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <Select value={config.sortBy} onValueChange={(v) => onConfigChange({ ...config, sortBy: v as 'value' | 'label' })}>
              <SelectTrigger className="text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="value">Trier par Valeur</SelectItem>
                <SelectItem value="label">Trier par Libellé</SelectItem>
              </SelectContent>
            </Select>
            <Select value={config.sortDirection} onValueChange={(v) => onConfigChange({ ...config, sortDirection: v as 'asc' | 'desc' })}>
              <SelectTrigger className="text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="asc">Ascendant</SelectItem>
                <SelectItem value="desc">Descendant</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1">
            <Label htmlFor="top-n" className="text-xs">Top N (optionnel)</Label>
            <Input
              id="top-n"
              type="number"
              placeholder="ex: 10"
              value={config.topN || ''}
              onChange={(e) => onConfigChange({ ...config, topN: e.target.value ? parseInt(e.target.value) : null })}
              className="text-xs"
            />
          </div>
        </CollapsibleContent>
      </Collapsible>

      {/* Build Button */}
      <Button onClick={onBuild} disabled={!isValid || isLoading} className="w-full" size="lg">
        {isLoading ? 'Analyse en cours…' : "Lancer l'analyse"}
      </Button>
    </div>
  );
};

export default PivotConfigPanel;
