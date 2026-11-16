import { useState, useEffect, useRef } from "react";
import {
  ChevronDown,
  LayoutDashboard,
  Loader2,
  Plus,
  RotateCcw,
  Table2,
  Trash2,
  FileSpreadsheet,
  FileText,
  TrendingUp,
  Info,
  ArrowRight,
  BarChart3,
  PieChart as PieChartIcon,
  TrendingDown,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { AGG_LABELS } from "@/lib/dashboard-utils";
import { apiClient } from "@/lib/api";
import { toast } from "@/lib/toast";
import { Badge } from "@/components/ui/badge";
import PivotTableRenderer from "@/components/pivot/PivotTableRenderer";
import PivotChart from "@/components/pivot/PivotChart";
import DrillDownModal from "@/components/pivot/DrillDownModal";
import usePivotTable from "@/hooks/usePivotTable";
import type { QuickAnalysisConfig } from "@/types/dashboard";
import type { DrillDownContext } from "@/types/pivot";

type AnalysePanelProps = {
  quickConfig: QuickAnalysisConfig;
  measureOptions: { value: string; label: string; aggregation?: string }[];
  groupByOptions: { value: string; label: string }[];
  detectedColumns?: {
    columns: {
      numeric?: { name: string }[];
      categorical?: { name: string }[];
      date?: { name: string }[];
    };
  } | null;
  selectedSourceId: number | null;
  detecting: boolean;
  addingAnalysis: boolean;
  hasActiveFilters: boolean;
  filterList: Array<{ field: string; operator: string; value: string[] }>;
  onConfigChange: (config: QuickAnalysisConfig) => void;
  onAdd: () => void;
  onAddToDashboard?: (config: {
    title: string;
    measure: string;
    aggregation: string;
    group_by: string[];
    filters: any[];
    breakdown?: any[];
    chart_type?: string;
  }) => void;
};

export function AnalysePanel({
  quickConfig,
  measureOptions,
  groupByOptions,
  detectedColumns,
  selectedSourceId,
  detecting,
  addingAnalysis,
  hasActiveFilters,
  filterList,
  onConfigChange,
  onAdd,
  onAddToDashboard,
}: AnalysePanelProps) {
  const [extraDimensions, setExtraDimensions] = useState<string[]>([]);
  const [showPivot, setShowPivot] = useState(false);
  const [viewMode, setViewMode] = useState<"table" | "chart">("table");
  const [chartType, setChartType] = useState<"bar" | "line" | "area" | "donut">("bar");
  const [drillDownOpen, setDrillDownOpen] = useState(false);
  const [drillDownContext, setDrillDownContext] = useState<DrillDownContext | undefined>();

  const {
    buildPivot,
    drillDown,
    isBuilding,
    isDrillingDown,
    pivotData,
    drillDownData,
    error,
    reset,
  } = usePivotTable();

  const categoricalFields = (() => {
    if (!detectedColumns?.columns) return [];
    const cols = detectedColumns.columns;
    return [
      ...(cols.categorical || []).map((c) => ({ name: c.name })),
      ...(cols.date || []).map((c) => ({ name: c.name })),
    ];
  })();

  const allRowFields = quickConfig.groupBy
    ? [quickConfig.groupBy, ...extraDimensions]
    : extraDimensions;

  const isCountMode = quickConfig.measure === "__count__";
  const effectiveValueField = isCountMode ? allRowFields[0] || "id" : quickConfig.measure;
  const effectiveAggregation = isCountMode ? "count" : quickConfig.aggregation;

  const handleBuildPivot = () => {
    if (!selectedSourceId || !quickConfig.measure || allRowFields.length === 0) return;
    buildPivot({
      sourceId: selectedSourceId,
      sourceType: "cleaned",
      rowFields: allRowFields,
      columnFields: [],
      valueField: effectiveValueField,
      aggregation: effectiveAggregation as
        | "max"
        | "min"
        | "sum"
        | "avg"
        | "count"
        | "median"
        | "std",
      filters: hasActiveFilters ? (filterList as any) : [],
      includeTotals: true,
      includeRunningTotals: false,
      formatCurrency: false,
      sortBy: "value",
      sortDirection: "desc",
      topN: undefined,
    });
  };

  const handleCellClick = (context: DrillDownContext) => {
    setDrillDownContext(context);
    drillDown({
      pivotConfig: {
        sourceId: selectedSourceId!,
        sourceType: "cleaned",
        rowFields: allRowFields,
        columnFields: [],
        valueField: effectiveValueField,
        aggregation: effectiveAggregation as
          | "max"
          | "min"
          | "sum"
          | "avg"
          | "count"
          | "median"
          | "std",
        filters: hasActiveFilters ? (filterList as any) : [],
        includeTotals: true,
        includeRunningTotals: false,
        formatCurrency: false,
        sortBy: "value",
        sortDirection: "desc",
        topN: undefined,
      },
      drillDownContext: context,
    });
    setDrillDownOpen(true);
  };

  const handleShowPivot = () => {
    setShowPivot(true);
    pivotBuiltRef.current = true;
    handleBuildPivot();
  };

  const handleHidePivot = () => {
    setShowPivot(false);
    reset();
  };

  const pivotBuiltRef = useRef(false);

  useEffect(() => {
    if (showPivot && pivotBuiltRef.current && allRowFields.length > 0 && !isBuilding) {
      handleBuildPivot();
    }
  }, [extraDimensions, quickConfig.groupBy]);

  useEffect(() => {
    pivotBuiltRef.current = false;
  }, [quickConfig.measure, quickConfig.aggregation, quickConfig.groupBy, selectedSourceId]);

  const canAdd =
    !addingAnalysis && !detecting && (!!quickConfig.measure || quickConfig.aggregation === "count");
  const canPivot =
    !isBuilding && !!selectedSourceId && !!quickConfig.measure && allRowFields.length > 0;

  const [exporting, setExporting] = useState<"excel" | "pdf" | null>(null);

  const buildExportPayload = () => ({
    source_id: selectedSourceId,
    source_type: "cleaned" as const,
    row_fields: allRowFields,
    column_fields: [],
    value_field: effectiveValueField,
    aggregation: effectiveAggregation,
  });

  const handleExportExcel = async () => {
    if (!selectedSourceId) {
      toast("Aucune source sélectionnée", { variant: "error" });
      return;
    }
    setExporting("excel");
    try {
      const blob = await apiClient.exportPivotToExcel(buildExportPayload());
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `analyse_export_${Date.now()}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      toast("Export Excel réussi", { variant: "success" });
    } catch (err: any) {
      toast("Échec de l'export Excel", {
        description: err?.message || err?.data?.error || "Erreur inconnue",
        variant: "error",
      });
    } finally {
      setExporting(null);
    }
  };

  const handleExportPDF = async () => {
    if (!selectedSourceId) {
      toast("Aucune source sélectionnée", { variant: "error" });
      return;
    }
    setExporting("pdf");
    try {
      const blob = await apiClient.exportPivotToPDF(buildExportPayload());
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `analyse_export_${Date.now()}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast("Export PDF réussi", { variant: "success" });
    } catch (err: any) {
      toast("Échec de l'export PDF", {
        description: err?.message || err?.data?.error || "Erreur inconnue",
        variant: "error",
      });
    } finally {
      setExporting(null);
    }
  };

  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const selectedMeasure = measureOptions.find((m) => m.value === quickConfig.measure);
  const selectedGroup = groupByOptions.find((g) => g.value === quickConfig.groupBy);

  return (
    <div className="rounded-xl border border-border bg-card shadow-card overflow-hidden">
      {/* Header with toggle */}
      <button
        type="button"
        onClick={() => setPanelCollapsed(!panelCollapsed)}
        aria-expanded={!panelCollapsed}
        className="flex w-full items-center gap-3 border-b border-border px-5 py-4 text-left transition-colors hover:bg-secondary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-primary/15 text-primary-strong">
          <Table2 className="h-4 w-4" />
        </span>
        <div className="flex-1 min-w-0">
          <h2 className="font-display text-[15px] font-semibold text-foreground">
            Créer un indicateur
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {panelCollapsed
              ? "Cliquez pour ouvrir"
              : "Nouvelle carte KPI ou graphique avec répartition"}
          </p>
        </div>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-muted-foreground transition-transform duration-200",
            !panelCollapsed && "rotate-180",
          )}
        />
      </button>

      {/* Collapsible content */}
      {!panelCollapsed && (
        <>
          <div className="p-5">
            {/* Steps indicator */}
            <div className="flex items-center gap-2 mb-5">
              <div
                className={cn(
                  "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold",
                  quickConfig.measure
                    ? "bg-primary/10 text-primary-strong"
                    : "bg-muted text-muted-foreground",
                )}
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/20 text-[10px] font-bold">
                  1
                </span>
                Mesure
              </div>
              <ArrowRight className="h-3 w-3 text-muted-foreground" />
              <div
                className={cn(
                  "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold",
                  quickConfig.groupBy
                    ? "bg-primary/10 text-primary-strong"
                    : "bg-muted text-muted-foreground",
                )}
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/20 text-[10px] font-bold">
                  2
                </span>
                Dimension
              </div>
              <ArrowRight className="h-3 w-3 text-muted-foreground" />
              <div
                className={cn(
                  "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold",
                  showPivot
                    ? "bg-primary/10 text-primary-strong"
                    : "bg-muted text-muted-foreground",
                )}
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/20 text-[10px] font-bold">
                  3
                </span>
                Résultat
              </div>
            </div>

            <div className="grid flex-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {/* Step 1: Mesure */}
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Quoi analyser ?
                </label>
                <p className="mb-2 text-[11px] text-muted-foreground/70">
                  La valeur que vous voulez mesurer (ex: chiffre d'affaires, nombre de ventes).
                </p>
                <div className="relative">
                  <select
                    value={quickConfig.measure}
                    onChange={(e) => {
                      const option = measureOptions.find((item) => item.value === e.target.value);
                      onConfigChange({
                        ...quickConfig,
                        measure: e.target.value,
                        aggregation: option?.aggregation || quickConfig.aggregation,
                      });
                    }}
                    disabled={detecting || measureOptions.length === 0}
                    className="w-full appearance-none rounded-xl border border-border bg-card px-3 py-2.5 pr-9 text-sm font-medium text-foreground outline-none hover:border-primary/40 focus:border-primary disabled:opacity-50"
                  >
                    <option value="">
                      {detecting
                        ? "Détection en cours..."
                        : measureOptions.length
                          ? "— Sélectionnez une mesure —"
                          : "Aucune mesure disponible"}
                    </option>
                    {measureOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                </div>
              </div>

              {/* Step 1b: Calcul */}
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Comment calculer ?
                </label>
                <p className="mb-2 text-[11px] text-muted-foreground/70">
                  La méthode d'agrégation (ex: somme, moyenne, nombre).
                </p>
                <div className="relative">
                  <select
                    value={quickConfig.aggregation}
                    onChange={(e) =>
                      onConfigChange({ ...quickConfig, aggregation: e.target.value })
                    }
                    className="w-full appearance-none rounded-xl border border-border bg-card px-3 py-2.5 pr-9 text-sm font-medium text-foreground outline-none hover:border-primary/40 focus:border-primary"
                  >
                    {Object.entries(AGG_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                </div>
              </div>

              {/* Step 2: Dimension */}
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Par quel critère ?
                </label>
                <p className="mb-2 text-[11px] text-muted-foreground/70">
                  La colonne qui servira de lignes dans le tableau (ex: région, produit).
                </p>
                <div className="relative">
                  <select
                    value={quickConfig.groupBy}
                    onChange={(e) => onConfigChange({ ...quickConfig, groupBy: e.target.value })}
                    disabled={detecting}
                    className="w-full appearance-none rounded-xl border border-border bg-card px-3 py-2.5 pr-9 text-sm font-medium text-foreground outline-none hover:border-primary/40 focus:border-primary disabled:opacity-50"
                  >
                    <option value="">— Sélectionnez une dimension —</option>
                    {groupByOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                </div>
              </div>
            </div>

            {/* Preview sentence */}
            {quickConfig.measure && quickConfig.groupBy && !showPivot && (
              <div className="mt-4 flex items-center gap-2 rounded-lg bg-primary/5 border border-primary/20 px-4 py-2.5 text-sm text-primary-strong">
                <Info className="h-4 w-4 shrink-0" />
                <span>
                  <strong>Résumé :</strong> Afficher la{" "}
                  <span className="font-semibold">
                    {selectedMeasure?.label || quickConfig.measure}
                  </span>{" "}
                  par{" "}
                  <span className="font-semibold">
                    {selectedGroup?.label || quickConfig.groupBy}
                  </span>
                </span>
              </div>
            )}

            {/* Dimensions supplémentaires */}
            {showPivot && categoricalFields.length > 0 && (
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold text-muted-foreground">
                  Dimensions supplémentaires :
                </span>
                {categoricalFields
                  .filter((f) => f.name !== quickConfig.groupBy)
                  .slice(0, 8)
                  .map((f) => {
                    const active = extraDimensions.includes(f.name);
                    return (
                      <button
                        key={f.name}
                        onClick={() =>
                          setExtraDimensions(
                            active
                              ? extraDimensions.filter((d) => d !== f.name)
                              : [...extraDimensions, f.name],
                          )
                        }
                        className={cn(
                          "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors",
                          active
                            ? "border-primary bg-primary/10 text-primary-strong"
                            : "border-dashed border-border text-muted-foreground hover:border-primary/40 hover:text-foreground",
                        )}
                      >
                        {active ? (
                          <Trash2 className="h-2.5 w-2.5" />
                        ) : (
                          <Plus className="h-2.5 w-2.5" />
                        )}
                        {f.name}
                      </button>
                    );
                  })}
              </div>
            )}

            {/* Action buttons */}
            <div className="mt-5 flex items-center gap-3">
              <button
                onClick={onAdd}
                disabled={!canAdd}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-primary/30 bg-primary/10 px-5 text-sm font-semibold text-primary-strong hover:bg-primary/20 disabled:opacity-50"
              >
                <Plus className={cn("h-4 w-4", addingAnalysis && "animate-pulse")} />
                {quickConfig.groupBy ? "Ajouter le graphique" : "Ajouter la carte KPI"}
              </button>
              <button
                onClick={showPivot ? handleHidePivot : handleShowPivot}
                disabled={!canPivot && !showPivot}
                className={cn(
                  "inline-flex h-10 items-center justify-center gap-2 rounded-xl border px-5 text-sm font-semibold transition-colors disabled:opacity-50",
                  showPivot
                    ? "border-primary bg-primary/10 text-primary-strong"
                    : "border-border bg-card text-foreground hover:bg-muted",
                )}
              >
                <Table2 className="h-4 w-4" />
                {showPivot ? "Fermer le tableau" : "Générer le tableau croisé"}
              </button>
              {showPivot && (
                <button
                  onClick={() => {
                    handleHidePivot();
                  }}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-border bg-card px-4 text-sm font-medium text-muted-foreground hover:bg-muted"
                >
                  <RotateCcw className="h-4 w-4" />
                  Recommencer
                </button>
              )}
            </div>
          </div>

          {/* Pivot results */}
          {showPivot && (
            <div className="border-t border-border/50 bg-muted/10 px-5 pb-5 pt-4">
              {error && (
                <div className="mb-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                  {String(
                    error.message ||
                      "Une erreur est survenue lors de la génération du tableau croisé.",
                  )}
                </div>
              )}
              {isBuilding ? (
                <div className="flex flex-col items-center justify-center gap-3 py-12 text-sm text-muted-foreground">
                  <Loader2 className="h-6 w-6 animate-spin text-primary-strong" />
                  <span className="font-medium">Construction du tableau croisé en cours…</span>
                  <span className="text-xs text-muted-foreground/70">
                    Analyse des données et calcul des croisements
                  </span>
                </div>
              ) : pivotData?.data ? (
                <div className="space-y-3">
                  {/* Toolbar: exports + view toggle */}
                  <div className="flex items-center justify-between rounded-lg border border-border/60 bg-card px-4 py-3 shadow-sm">
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="font-medium text-foreground">
                        {pivotData.data.metadata.rows_processed} lignes analysées
                      </span>
                      <span className="text-border">|</span>
                      <span>{pivotData.data.metadata.execution_time_ms}ms</span>
                      <span className="text-border">|</span>
                      <Badge variant="secondary" className="text-xs font-semibold">
                        <TrendingUp className="w-3 h-3 mr-1" />
                        Total :{" "}
                        {new Intl.NumberFormat("fr-FR").format(
                          pivotData.data.totals.grand_total || 0,
                        )}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      {/* View toggle */}
                      <div className="flex items-center rounded-lg border border-border/60 bg-muted/30 p-0.5">
                        <button
                          onClick={() => setViewMode("table")}
                          className={cn(
                            "inline-flex h-7 items-center justify-center gap-1 rounded-md px-2.5 text-xs font-medium transition-colors",
                            viewMode === "table"
                              ? "bg-card shadow-sm text-foreground"
                              : "text-muted-foreground hover:text-foreground",
                          )}
                        >
                          <Table2 className="h-3.5 w-3.5" />
                          Tableau
                        </button>
                        <button
                          onClick={() => setViewMode("chart")}
                          className={cn(
                            "inline-flex h-7 items-center justify-center gap-1 rounded-md px-2.5 text-xs font-medium transition-colors",
                            viewMode === "chart"
                              ? "bg-card shadow-sm text-foreground"
                              : "text-muted-foreground hover:text-foreground",
                          )}
                        >
                          <BarChart3 className="h-3.5 w-3.5" />
                          Graphique
                        </button>
                      </div>

                      {/* Chart type selector */}
                      {viewMode === "chart" && (
                        <div className="flex items-center rounded-lg border border-border/60 bg-muted/30 p-0.5">
                          {[
                            { type: "bar" as const, icon: BarChart3, label: "Barres" },
                            { type: "line" as const, icon: Activity, label: "Courbe" },
                            { type: "area" as const, icon: TrendingDown, label: "Aire" },
                            { type: "donut" as const, icon: PieChartIcon, label: "Donut" },
                          ].map(({ type, icon: Icon, label }) => (
                            <button
                              key={type}
                              onClick={() => setChartType(type)}
                              className={cn(
                                "inline-flex h-7 items-center justify-center gap-1 rounded-md px-2 text-xs font-medium transition-colors",
                                chartType === type
                                  ? "bg-card shadow-sm text-foreground"
                                  : "text-muted-foreground hover:text-foreground",
                              )}
                              title={label}
                            >
                              <Icon className="h-3.5 w-3.5" />
                              <span className="hidden sm:inline">{label}</span>
                            </button>
                          ))}
                        </div>
                      )}

                      {/* Exports */}
                      <div className="h-5 w-px bg-border/60" />
                      <button
                        onClick={handleExportExcel}
                        disabled={exporting !== null}
                        className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-3 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
                      >
                        {exporting === "excel" ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <FileSpreadsheet className="h-3.5 w-3.5" />
                        )}
                        {exporting === "excel" ? "Export…" : "Excel"}
                      </button>
                      <button
                        onClick={handleExportPDF}
                        disabled={exporting !== null}
                        className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg bg-red-600 px-3 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-50"
                      >
                        {exporting === "pdf" ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <FileText className="h-3.5 w-3.5" />
                        )}
                        {exporting === "pdf" ? "Export…" : "PDF"}
                      </button>
                      {onAddToDashboard && pivotData?.data && (
                        <>
                          <div className="h-5 w-px bg-border/60" />
                          <button
                            onClick={() => {
                              const label = isCountMode
                                ? "Nombre de lignes"
                                : selectedMeasure?.label || quickConfig.measure;
                              const dim = selectedGroup?.label || quickConfig.groupBy;
                              const d = pivotData.data;
                              const breakdown = d.row_headers.map((header, i) => ({
                                [d.row_labels[0] || "catégorie"]: header,
                                value:
                                  d.totals?.row_totals?.[i] ??
                                  d.pivot[i]?.reduce(
                                    (a: number, b: number) => a + (typeof b === "number" ? b : 0),
                                    0,
                                  ) ??
                                  0,
                              }));
                              onAddToDashboard({
                                title: `${effectiveAggregation === "count" ? "Nombre" : effectiveAggregation} ${label} par ${dim}`,
                                measure: effectiveValueField,
                                aggregation: effectiveAggregation,
                                group_by: allRowFields,
                                filters: hasActiveFilters ? filterList : [],
                                breakdown,
                                chart_type: chartType,
                              });
                            }}
                            className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg bg-primary px-3 text-xs font-semibold text-primary-foreground hover:brightness-110"
                          >
                            <BarChart3 className="h-3.5 w-3.5" />
                            Ajouter ce graphique au dashboard
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Content: table or chart */}
                  {viewMode === "table" ? (
                    <div className="max-h-[500px] overflow-auto rounded-lg border border-border/40 bg-card">
                      <PivotTableRenderer
                        data={pivotData.data}
                        isLoading={isBuilding}
                        onCellClick={handleCellClick}
                      />
                    </div>
                  ) : (
                    <div className="rounded-lg border border-border/40 bg-card p-4">
                      <PivotChart data={pivotData.data} chartType={chartType} />
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-lg border border-dashed border-border/40 p-8 text-center">
                  <Table2 className="mx-auto h-8 w-8 text-muted-foreground/40" />
                  <p className="mt-2 text-sm text-muted-foreground">
                    Sélectionnez une mesure et une dimension, puis cliquez sur "Générer le tableau
                    croisé"
                  </p>
                </div>
              )}
            </div>
          )}

          <DrillDownModal
            isOpen={drillDownOpen}
            onOpenChange={setDrillDownOpen}
            context={drillDownContext}
            data={drillDownData}
            isLoading={isDrillingDown}
            error={error}
          />
        </>
      )}
    </div>
  );
}
