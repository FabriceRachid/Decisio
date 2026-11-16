import { useCallback, useEffect, useMemo, useState } from "react";
import { Calculator, ChevronDown, LayoutDashboard, Sparkles, X, RefreshCw, Table2 } from "lucide-react";
import { apiClient, type AutoKPIDetectResponse, handleApiError } from "@/lib/api";
import { Card } from "@/components/AppShell";
import { cn } from "@/lib/utils";
import { AGG_LABELS, prettifyField } from "@/lib/dashboard-utils";
import { toast } from "@/lib/toast";

type KpiSidebarProps = {
  open: boolean;
  onClose: () => void;
  selectedSourceId: number | null;
  hasActiveFilters: boolean;
  filterList: { field: string; operator: string; value: string[] }[];
  onWidgetAdded: () => void;
};

export function KpiSidebar({ open, onClose, selectedSourceId, hasActiveFilters, filterList, onWidgetAdded }: KpiSidebarProps) {
  const [detected, setDetected] = useState<AutoKPIDetectResponse | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [computing, setComputing] = useState(false);
  const [adding, setAdding] = useState(false);
  const [metricResult, setMetricResult] = useState<any>(null);

  const [config, setConfig] = useState({ measure: "", aggregation: "sum", groupBy: "" });

  useEffect(() => {
    if (!selectedSourceId || !open) return;
    let cancelled = false;
    const detect = async () => {
      try {
        setDetecting(true);
        const result = await apiClient.detectColumns(selectedSourceId);
        if (cancelled) return;
        setDetected(result);
        const firstSuggestion = result.suggestions[0];
        const firstNumeric = result.columns.numeric[0];
        const firstDimension = result.columns.categorical[0] || result.columns.date[0];
        setConfig({
          measure: firstSuggestion?.measure_column || firstNumeric?.name || "",
          aggregation: firstSuggestion?.aggregation || (firstNumeric ? "sum" : "count"),
          groupBy: firstDimension?.name || "",
        });
      } catch {
        if (!cancelled) setDetected(null);
      } finally {
        if (!cancelled) setDetecting(false);
      }
    };
    void detect();
    return () => { cancelled = true; };
  }, [selectedSourceId, open]);

  const measureOptions = useMemo(() => {
    const suggestions = (detected?.suggestions || []).map((s) => ({
      value: s.measure_column, label: s.label || prettifyField(s.measure_column), aggregation: s.aggregation,
    }));
    const existing = new Set(suggestions.map((o) => o.value));
    const numeric = (detected?.columns.numeric || []).filter((c) => !existing.has(c.name)).map((c) => ({
      value: c.name, label: prettifyField(c.name), aggregation: undefined,
    }));
    return [...suggestions, ...numeric];
  }, [detected]);

  const groupByOptions = useMemo(() => [
    ...(detected?.columns.categorical || []).map((c) => ({ value: c.name, label: prettifyField(c.name) })),
    ...(detected?.columns.date || []).map((c) => ({ value: c.name, label: prettifyField(c.name) })),
  ], [detected]);

  const computeMetric = useCallback(async () => {
    if (!selectedSourceId) return;
    if (config.aggregation !== "count" && !config.measure) return;
    try {
      setComputing(true);
      const result = await apiClient.computeMetric({
        source_id: selectedSourceId,
        source_table: "nettoyage_cleaneddata",
        aggregation: config.aggregation,
        measure: config.measure || "id",
        group_by: config.groupBy ? [config.groupBy] : [],
        filters: hasActiveFilters ? filterList : [],
      });
      setMetricResult(result);
    } catch (error) {
      toast("Erreur de calcul", {
        description: handleApiError(error, "Impossible de calculer la métrique."),
        variant: "error",
      });
    } finally {
      setComputing(false);
    }
  }, [selectedSourceId, config, hasActiveFilters, filterList]);

  const addToDashboard = useCallback(async () => {
    if (!selectedSourceId) return;
    try {
      setAdding(true);
      const title = `${AGG_LABELS[config.aggregation] || config.aggregation} ${prettifyField(config.measure || "lignes")}${config.groupBy ? ` par ${prettifyField(config.groupBy)}` : ""}`;
      await apiClient.addWidgetToDashboard(selectedSourceId, {
        title,
        measure: config.measure,
        aggregation: config.aggregation,
        group_by: config.groupBy ? [config.groupBy] : [],
        filters: hasActiveFilters ? filterList : [],
      });
      toast("Indicateur ajouté", {
        description: "Le widget a été ajouté au dashboard.",
        variant: "success",
      });
      onWidgetAdded();
    } catch (error) {
      toast("Ajout impossible", {
        description: handleApiError(error, "L'indicateur n'a pas pu être ajouté."),
        variant: "error",
      });
    } finally {
      setAdding(false);
    }
  }, [selectedSourceId, config, hasActiveFilters, filterList, onWidgetAdded]);

  return (
    <div className={cn(
      "fixed inset-0 z-40 transition-opacity duration-300",
      open ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none",
    )}>
      {open && <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />}
      <div className={cn(
        "absolute right-0 top-0 h-full w-full max-w-lg border-l border-border/60 bg-background shadow-2xl transition-transform duration-300 flex flex-col",
        open ? "translate-x-0" : "translate-x-full",
      )}>
        <div className="flex items-center justify-between border-b border-border/50 px-5 py-4">
          <div className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary/10 text-primary-strong">
              <Sparkles className="h-4 w-4" />
            </span>
            <div>
              <h2 className="text-sm font-bold text-foreground">Constructeur d'indicateur</h2>
              <p className="text-xs text-muted-foreground">Calcule des métriques avancées</p>
            </div>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-muted-foreground hover:bg-secondary">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {detecting ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-8 w-8 animate-spin text-primary-strong" />
            </div>
          ) : !detected ? (
            <div className="rounded-xl border border-dashed border-border/60 p-8 text-center">
              <Calculator className="mx-auto h-8 w-8 text-muted-foreground" />
              <p className="mt-3 text-sm text-muted-foreground">Sélectionne une source pour commencer</p>
            </div>
          ) : (
            <>
              <div className="space-y-4">
                <div>
                  <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-muted-foreground">Mesure</label>
                  <div className="relative">
                    <select
                      value={config.measure}
                      onChange={(e) => {
                        const option = measureOptions.find((o) => o.value === e.target.value);
                        setConfig((prev) => ({ ...prev, measure: e.target.value, aggregation: option?.aggregation || prev.aggregation }));
                      }}
                      className="w-full appearance-none rounded-xl border border-border bg-card px-3 py-2.5 pr-9 text-sm font-medium text-foreground outline-none focus:border-primary"
                    >
                      <option value="">Sélectionner une mesure</option>
                      {measureOptions.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                  </div>
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-muted-foreground">Agrégation</label>
                  <div className="relative">
                    <select
                      value={config.aggregation}
                      onChange={(e) => setConfig((prev) => ({ ...prev, aggregation: e.target.value }))}
                      className="w-full appearance-none rounded-xl border border-border bg-card px-3 py-2.5 pr-9 text-sm font-medium text-foreground outline-none focus:border-primary"
                    >
                      {Object.entries(AGG_LABELS).map(([value, label]) => (
                        <option key={value} value={value}>{label}</option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                  </div>
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-bold uppercase tracking-wide text-muted-foreground">Group by (optionnel)</label>
                  <div className="relative">
                    <select
                      value={config.groupBy}
                      onChange={(e) => setConfig((prev) => ({ ...prev, groupBy: e.target.value }))}
                      className="w-full appearance-none rounded-xl border border-border bg-card px-3 py-2.5 pr-9 text-sm font-medium text-foreground outline-none focus:border-primary"
                    >
                      <option value="">Aucun groupement</option>
                      {groupByOptions.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                  </div>
                </div>

                <button
                  onClick={() => void computeMetric()}
                  disabled={computing || (!config.measure && config.aggregation !== "count")}
                  className="w-full rounded-xl bg-primary py-2.5 text-sm font-semibold text-primary-foreground hover:brightness-110 disabled:opacity-50"
                >
                  {computing ? "Calcul..." : "Calculer"}
                </button>
              </div>

              {metricResult && (
                <div className="rounded-xl border border-border/60 bg-card p-5">
                  {metricResult.breakdown && metricResult.breakdown.length > 0 ? (
                    <div>
                      <p className="mb-3 text-xs font-bold uppercase tracking-wide text-muted-foreground">Résultat groupé</p>
                      <div className="max-h-64 overflow-y-auto space-y-1">
                        {metricResult.breakdown.slice(0, 50).map((row: any, i: number) => {
                          const groupKey = metricResult.group_by?.[0];
                          const label = groupKey ? row[groupKey] : `#${i + 1}`;
                          return (
                            <div key={i} className="flex items-center justify-between rounded-lg bg-secondary/50 px-3 py-1.5 text-sm">
                              <span className="truncate font-medium text-foreground">{String(label)}</span>
                              <span className="ml-2 tabular-nums text-muted-foreground">
                                {Number(row.value).toLocaleString("fr-FR")}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ) : (
                    <div className="text-center">
                      <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Résultat</p>
                      <p className="mt-2 text-4xl font-bold tracking-tight text-foreground">
                        {metricResult.formatted_value || Number(metricResult.value || 0).toLocaleString("fr-FR")}
                      </p>
                      {metricResult.rows_processed !== undefined && (
                        <p className="mt-2 text-xs text-muted-foreground">
                          {metricResult.rows_processed.toLocaleString("fr-FR")} lignes traitées
                        </p>
                      )}
                    </div>
                  )}

                  <button
                    onClick={() => void addToDashboard()}
                    disabled={adding}
                    className="mt-4 w-full inline-flex items-center justify-center gap-2 rounded-xl bg-primary py-2.5 text-sm font-semibold text-primary-foreground hover:brightness-110 disabled:opacity-50"
                  >
                    <LayoutDashboard className={cn("h-4 w-4", adding && "animate-pulse")} />
                    {adding ? "Ajout en cours..." : "Ajouter au dashboard"}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
