import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  BarChart3,
  ChevronDown,
  FileDown,
  FileSpreadsheet,
  LayoutDashboard,
  Loader2,
  Upload,
} from "lucide-react";
import GridLayout, { noCompactor } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import { PageHeader } from "@/components/AppShell";
import { JourneySteps } from "@/components/app/PageHeader";
import { EmptyState, ErrorState, PageBody, SkeletonCards, StatusBadge } from "@/components/app/kit";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { can, getCurrentUserProfile } from "@/lib/rbac";
import {
  apiClient,
  type AutoKPIDetectResponse,
  type DataSourceDetail,
  handleApiError,
} from "@/lib/api";
import { toast } from "@/lib/toast";
import type { DashboardData, QuickAnalysisConfig, WidgetData } from "@/types/dashboard";
import {
  AGG_LABELS,
  DOMAIN_LABELS,
  FILTER_FIELD_MAP,
  getPeriodDates,
  hasBreakdown,
  prettifyField,
} from "@/lib/dashboard-utils";
import { KpiCard } from "@/components/dashboard/widgets/KpiCard";
import { WidgetCard } from "@/components/dashboard/widgets/WidgetCard";
import { AnalysePanel } from "@/components/dashboard/AnalysePanel";

export const Route = createFileRoute("/app/dashboard")({
  component: DashboardPage,
  head: () => ({ meta: [{ title: "Tableau de bord — DécisioBI" }] }),
});

function DashboardPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [sources, setSources] = useState<DataSourceDetail[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState<number | null>(null);
  const [periodPreset, setPeriodPreset] = useState("30d");
  const [loading, setLoading] = useState(true);
  const [userName, setUserName] = useState("");
  const [role, setRole] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [building, setBuilding] = useState(false);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [availableFilters, setAvailableFilters] = useState<Record<string, string[]> | null>(null);
  const [selectedFilters, setSelectedFilters] = useState<Record<string, string[]>>({});
  const [showFilters, setShowFilters] = useState(false);
  const [detected, setDetected] = useState<AutoKPIDetectResponse | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [addingAnalysis, setAddingAnalysis] = useState(false);
  const [removedWidgetIds, setRemovedWidgetIds] = useState<Set<number>>(new Set());
  const [quickConfig, setQuickConfig] = useState<QuickAnalysisConfig>({
    measure: "",
    aggregation: "sum",
    groupBy: "",
  });

  const [chartOverrides, setChartOverrides] = useState<Record<number, string>>({});
  const gridContainerRef = useRef<HTMLDivElement>(null);
  const [gridWidth, setGridWidth] = useState(1200);
  const layoutDebounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const [layoutKey, setLayoutKey] = useState("dashboard:layout:0");

  useEffect(() => {
    setLayoutKey(`dashboard:layout:${selectedSourceId ?? 0}`);
  }, [selectedSourceId]);

  type SavedLayout = Record<string, { x: number; y: number; w: number; h: number }> & {
    _version?: string;
  };
  const loadSavedLayout = useCallback((): SavedLayout | null => {
    try {
      const raw = window.localStorage.getItem(layoutKey);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }, [layoutKey]);

  const saveLayout = useCallback(
    (items: { i: string; x: number; y: number; w: number; h: number }[]) => {
      const map: Record<string, { x: number; y: number; w: number; h: number }> & {
        _version?: string;
      } = {};
      items.forEach((it) => {
        map[it.i] = { x: it.x, y: it.y, w: it.w, h: it.h };
      });
      map._version = "v3";
      window.localStorage.setItem(layoutKey, JSON.stringify(map));
    },
    [layoutKey],
  );

  const setDashboardWithOverrides = useCallback((data: DashboardData | null) => {
    setDashboard(data);
    if (data?.widgets) {
      const overrides: Record<number, string> = {};
      for (const w of data.widgets) {
        if (w.chart_type_override) overrides[w.id] = w.chart_type_override;
      }
      if (Object.keys(overrides).length > 0) setChartOverrides(overrides);
    }
  }, []);

  const loadSources = useCallback(async () => {
    setLoading(true);
    try {
      const [loadedSources, loadedJobs] = await Promise.all([
        apiClient.listDataSources(),
        apiClient.getCleaningJobs({ page_size: 200 }),
      ]);
      const jobResults = loadedJobs.results || [];
      const validatedSources = loadedSources.filter((source) =>
        jobResults.some(
          (job) => (job.source_id ?? job.source) === source.id && job.is_fully_validated,
        ),
      );
      setSources(validatedSources);
      const storedSourceId =
        typeof window !== "undefined"
          ? Number(window.localStorage.getItem("dashboard:selected-source")) || null
          : null;
      const nextSourceId =
        selectedSourceId && validatedSources.some((s) => s.id === selectedSourceId)
          ? selectedSourceId
          : storedSourceId && validatedSources.some((s) => s.id === storedSourceId)
            ? storedSourceId
            : (validatedSources[0]?.id ?? null);
      setSelectedSourceId(nextSourceId);
    } catch (error) {
      toast("Impossible de charger le dashboard", {
        description: handleApiError(error, "Les sources validées n'ont pas pu être chargées."),
        variant: "error",
      });
    } finally {
      setLoading(false);
    }
  }, [selectedSourceId]);

  const toggleFilter = (field: string, value: string) => {
    setSelectedFilters((prev) => {
      const current = prev[field] || [];
      const next = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value];
      if (next.length === 0) {
        const { [field]: _, ...rest } = prev;
        return rest;
      }
      return { ...prev, [field]: next };
    });
  };

  const filterList = useMemo(() => {
    return Object.entries(selectedFilters)
      .filter(([, values]) => values.length > 0)
      .map(([field, values]) => ({
        field: FILTER_FIELD_MAP[field] || field,
        operator: "in" as const,
        value: values,
      }));
  }, [selectedFilters]);

  const hasActiveFilters = filterList.length > 0;

  useEffect(() => {
    void loadSources();
    getCurrentUserProfile()
      .then((user) => {
        const name = [user.first_name, user.last_name].filter(Boolean).join(" ").trim();
        setUserName(name || user.username);
        setRole(user.profile?.role ?? null);
      })
      .catch(() => {});
  }, [loadSources]);

  useEffect(() => {
    if (selectedSourceId) {
      window.localStorage.setItem("dashboard:selected-source", String(selectedSourceId));
    } else {
      window.localStorage.removeItem("dashboard:selected-source");
    }
  }, [selectedSourceId]);

  useEffect(() => {
    if (!selectedSourceId) {
      setDashboardWithOverrides(null);
      setAvailableFilters(null);
      setDetected(null);
      return;
    }
    setRemovedWidgetIds(new Set());

    let cancelled = false;
    const loadFilters = async () => {
      try {
        const filters = await apiClient.getAvailableFilters({
          source_id: String(selectedSourceId),
        });
        if (!cancelled) setAvailableFilters(filters);
      } catch {
        if (!cancelled) setAvailableFilters(null);
      }
    };
    void loadFilters();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSourceId]);

  const dashboardQuery = useQuery({
    queryKey: ["dashboard-auto", selectedSourceId, periodPreset],
    queryFn: async () => {
      if (!selectedSourceId) return null;
      try {
        const existing = await apiClient.loadDashboard(selectedSourceId);
        if (existing && existing.widgets) return existing;
      } catch (err: unknown) {
        const dashboardError = err as { status?: number };
        if (dashboardError?.status !== 404) throw err;
      }
      const { start, end } = getPeriodDates(periodPreset);
      return apiClient.autoBuildDashboard(selectedSourceId, start, end);
    },
    enabled: !!selectedSourceId,
    staleTime: 60 * 1000,
    gcTime: 5 * 60 * 1000,
    retry: 0,
  });

  useEffect(() => {
    if (!dashboardQuery.data) {
      if (!selectedSourceId) setDashboardWithOverrides(null);
      return;
    }
    setDashboardWithOverrides(dashboardQuery.data);
    setBuilding(false);
  }, [dashboardQuery.data, selectedSourceId, setDashboardWithOverrides]);

  useEffect(() => {
    if (dashboardQuery.data) return;
    if (dashboardQuery.isLoading || dashboardQuery.isFetching) {
      setBuilding(true);
    } else if (dashboardQuery.isError) {
      setDashboardWithOverrides(null);
      setBuilding(false);
    }
  }, [
    dashboardQuery.isLoading,
    dashboardQuery.isFetching,
    dashboardQuery.isError,
    dashboardQuery.data,
  ]);

  useEffect(() => {
    if (!selectedSourceId) {
      setDetected(null);
      setQuickConfig({ measure: "", aggregation: "sum", groupBy: "" });
      return;
    }
    let cancelled = false;
    const detect = async () => {
      try {
        setDetecting(true);
        const result = await apiClient.detectColumns(selectedSourceId);
        if (cancelled) return;
        const firstSuggestion = result.suggestions[0];
        const firstNumeric = result.columns.numeric[0];
        const firstDimension = result.columns.categorical[0] || result.columns.date[0];
        setDetected(result);
        setQuickConfig({
          measure: firstSuggestion?.measure_column || firstNumeric?.name || "",
          aggregation: firstSuggestion?.aggregation || (firstNumeric ? "sum" : "count"),
          groupBy: firstDimension?.name || "",
        });
      } catch {
        if (!cancelled) {
          setDetected(null);
          setQuickConfig({ measure: "", aggregation: "sum", groupBy: "" });
        }
      } finally {
        if (!cancelled) setDetecting(false);
      }
    };
    void detect();
    return () => {
      cancelled = true;
    };
  }, [selectedSourceId]);

  useEffect(() => {
    const el = gridContainerRef.current;
    if (!el) return;
    setGridWidth(el.clientWidth);
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) setGridWidth(entry.contentRect.width);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [dashboard?.widgets.length]);

  const removeWidget = async (widgetId: number) => {
    try {
      await apiClient.deleteWidget(widgetId);
      if (selectedSourceId) {
        queryClient.invalidateQueries({ queryKey: ["dashboard-auto", selectedSourceId] });
      }
    } catch {
      /* widget already deleted or network error — continue anyway */
    }
    setRemovedWidgetIds((prev) => new Set([...prev, widgetId]));
    setDashboard((prev) => {
      if (!prev) return prev;
      return { ...prev, widgets: prev.widgets.filter((w) => w.id !== widgetId) };
    });
  };

  const selectedSource = useMemo(
    () => sources.find((s) => s.id === selectedSourceId) || null,
    [sources, selectedSourceId],
  );

  const measureOptions = useMemo(() => {
    const countOption = { value: "__count__", label: "Nombre de lignes", aggregation: "count" };
    const suggestions = (detected?.suggestions || []).map((s) => ({
      value: s.measure_column,
      label: s.label || prettifyField(s.measure_column),
      aggregation: s.aggregation,
    }));
    const existing = new Set(suggestions.map((o) => o.value));
    const numeric = (detected?.columns.numeric || [])
      .filter((c) => !existing.has(c.name))
      .map((c) => ({
        value: c.name,
        label: prettifyField(c.name),
        aggregation: undefined,
      }));
    return [countOption, ...suggestions, ...numeric];
  }, [detected]);

  const groupByOptions = useMemo(
    () => [
      ...(detected?.columns.categorical || []).map((c) => ({
        value: c.name,
        label: prettifyField(c.name),
      })),
      ...(detected?.columns.date || []).map((c) => ({
        value: c.name,
        label: prettifyField(c.name),
      })),
    ],
    [detected],
  );

  const quickAnalysisTitle = useMemo(() => {
    const aggregation = AGG_LABELS[quickConfig.aggregation] || quickConfig.aggregation;
    const measure = prettifyField(quickConfig.measure || "lignes");
    const group = quickConfig.groupBy ? ` par ${prettifyField(quickConfig.groupBy)}` : "";
    return `${aggregation} ${measure}${group}`;
  }, [quickConfig]);

  const addQuickAnalysis = async () => {
    if (!selectedSourceId) return;
    if (quickConfig.aggregation !== "count" && !quickConfig.measure) {
      toast("Sélection invalide", {
        description: "Choisis une mesure à analyser ou utilise l'agrégation Nombre.",
        variant: "error",
      });
      return;
    }
    try {
      setAddingAnalysis(true);
      await apiClient.addWidgetToDashboard(selectedSourceId, {
        title: quickAnalysisTitle,
        measure: quickConfig.measure,
        aggregation: quickConfig.aggregation,
        group_by: quickConfig.groupBy ? [quickConfig.groupBy] : [],
        filters: hasActiveFilters ? filterList : [],
      });
      await queryClient.invalidateQueries({
        queryKey: ["dashboard-auto", selectedSourceId],
      });
      const label = quickConfig.groupBy ? "graphique" : "carte KPI";
      toast(
        `${label.charAt(0).toUpperCase() + label.slice(1)} ajouté${label === "carte KPI" ? "e" : ""}`,
        {
          description: `La ${label === "carte KPI" ? "carte" : "vue"} est maintenant visible dans le dashboard.`,
          variant: "success",
        },
      );
    } catch (error) {
      toast("Ajout impossible", {
        description: handleApiError(error, "L'analyse n'a pas pu être ajoutée au dashboard."),
        variant: "error",
      });
    } finally {
      setAddingAnalysis(false);
    }
  };

  const handleChartTypeChange = async (widgetId: number, type: string) => {
    setChartOverrides((prev) => ({ ...prev, [widgetId]: type }));
    try {
      await apiClient.updateWidgetChartType(widgetId, type);
    } catch {
      /* échec silencieux — l'état local est déjà mis à jour */
    }
  };

  const handleAnalyseIA = useCallback(
    async (widget: WidgetData) => {
      // Capture widget image
      let widgetImage: string | null = null;
      try {
        const el = document.querySelector(`[data-widget-id="${widget.id}"]`);
        if (el) {
          const { toPng } = await import("html-to-image");
          widgetImage = await toPng(el as HTMLElement, {
            backgroundColor: "#ffffff",
            pixelRatio: 1.5,
            cacheBust: true,
          });
        }
      } catch (e) {
        console.warn("Widget capture failed:", e);
      }

      // Store image for chatbot to pick up
      if (widgetImage) {
        sessionStorage.setItem("widgetAnalysisImage", widgetImage);
        sessionStorage.setItem("widgetAnalysisTitle", widget.title);
      }

      const breakdown = widget.payload?.breakdown || [];
      const groupKey = widget.payload?.group_by?.[0] || "";

      // Extract chart data
      const chartData = breakdown
        .map((row) => ({
          name: groupKey ? String(row[groupKey] ?? "") : String(row.name ?? ""),
          value: Number(row.value || 0),
        }))
        .filter((r) => r.name && Number.isFinite(r.value))
        .sort((a, b) => b.value - a.value);

      // Stats
      const values = chartData.map((d) => d.value);
      const total = values.reduce((s, v) => s + v, 0);
      const max = Math.max(...values);
      const min = Math.min(...values);
      const avg = values.length > 0 ? total / values.length : 0;
      const top3 = chartData
        .slice(0, 3)
        .map((d) => `${d.name}: ${d.value.toLocaleString("fr-FR")}`);
      const bottom3 = chartData
        .slice(-3)
        .map((d) => `${d.name}: ${d.value.toLocaleString("fr-FR")}`);

      // Trend detection
      const trend =
        values.length >= 2
          ? values[0] > values[values.length - 1]
            ? "en hausse"
            : values[0] < values[values.length - 1]
              ? "en baisse"
              : "stable"
          : "";

      // Build rich context
      const contextParts: string[] = [];
      contextParts.push(`ANALYSE DU WIDGET: "${widget.title}"`);
      contextParts.push(`Mesure: ${widget.payload?.measure || "N/A"}`);
      contextParts.push(`Agrégation: ${widget.payload?.aggregation || "somme"}`);
      if (groupKey) contextParts.push(`Dimension: ${groupKey}`);
      contextParts.push(`Type sémantique: ${widget.payload?.semantic_type || "N/A"}`);
      contextParts.push(`--- DONNÉES (${chartData.length} catégories) ---`);
      contextParts.push(`Total: ${total.toLocaleString("fr-FR")}`);
      contextParts.push(`Moyenne: ${Math.round(avg).toLocaleString("fr-FR")}`);
      contextParts.push(
        `Max: ${max.toLocaleString("fr-FR")} | Min: ${min.toLocaleString("fr-FR")}`,
      );
      if (trend) contextParts.push(`Tendance: ${trend}`);
      if (top3.length > 0) contextParts.push(`Top 3: ${top3.join(", ")}`);
      if (bottom3.length > 0) contextParts.push(`Bottom 3: ${bottom3.join(", ")}`);
      contextParts.push(`--- TOUTES LES VALEURS ---`);
      chartData.forEach((d) =>
        contextParts.push(`- ${d.name}: ${d.value.toLocaleString("fr-FR")}`),
      );
      contextParts.push(`--- FIN DONNÉES ---`);

      navigate({
        to: "/app/chatbot",
        search: {
          context: contextParts.join("\n"),
          sourceId: String(selectedSourceId || ""),
        },
      });
    },
    [selectedSourceId, navigate],
  );

  const computeDefaultLayout = useCallback((widgets: WidgetData[]) => {
    const kpis = widgets.filter((w) => w.type === "metric_card");
    const charts = widgets.filter((w) => w.type !== "metric_card");
    const items: { i: string; x: number; y: number; w: number; h: number }[] = [];

    kpis.forEach((w, i) => {
      items.push({ i: String(w.id), x: (i % 3) * 4, y: 0, w: 4, h: 2 });
    });

    charts.forEach((w, i) => {
      items.push({ i: String(w.id), x: (i % 2) * 6, y: 3, w: 6, h: 3 });
    });

    return items;
  }, []);

  const DEFAULT_VERSION = "v3";
  const gridLayout = useMemo(() => {
    if (!dashboard) return [];
    const widgets = dashboard.widgets.filter((w) => !removedWidgetIds.has(w.id));
    const defaultItems = computeDefaultLayout(widgets);
    const defaultMap = new Map(defaultItems.map((it) => [it.i, it]));
    const saved = loadSavedLayout();

    // 1) localStorage cache → rapide, appliqué si tous les widgets sont présents
    if (saved && saved._version === DEFAULT_VERSION) {
      const allFound = widgets.every((w) => saved[String(w.id)]);
      if (allFound) {
        return widgets.map((w) => {
          const s = saved[String(w.id)];
          const def = defaultMap.get(String(w.id))!;
          return {
            i: String(w.id),
            x: s.x,
            y: s.y,
            w: s.w,
            h: s.h,
            minW: 2,
            minH: 2,
          };
        });
      }
    }

    // 2) Backend positions (DB) → source de vérité persistée
    const allHaveBackendPos = widgets.every((w) => w.position?.x != null);
    if (allHaveBackendPos) {
      return widgets.map((w) => ({
        i: String(w.id),
        x: w.position.x,
        y: w.position.y,
        w: w.position.w || defaultMap.get(String(w.id))?.w || 6,
        h: w.position.h || defaultMap.get(String(w.id))?.h || 3,
        minW: 2,
        minH: 2,
      }));
    }

    // 3) Fallback → layout calculé par défaut
    return defaultItems.map((item) => ({ ...item, minW: 2, minH: 2 }));
  }, [dashboard, removedWidgetIds, loadSavedLayout, computeDefaultLayout]);

  type GridItem = { i: string; x: number; y: number; w: number; h: number };
  const handleLayoutChange = useCallback(
    (layout: readonly GridItem[]) => {
      const items = [...layout].map((item) => ({
        id: Number(item.i),
        position_x: item.x,
        position_y: item.y,
        width: item.w,
        height: item.h,
      }));
      saveLayout([...layout]);
      if (layoutDebounceRef.current) clearTimeout(layoutDebounceRef.current);
      layoutDebounceRef.current = setTimeout(async () => {
        try {
          await apiClient.reorderWidgets(items);
        } catch {
          /* silence */
        }
      }, 800);
    },
    [saveLayout],
  );

  const handleSourceChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedSourceId(e.target.value ? Number(e.target.value) : null);
    setSelectedFilters({});
    setShowFilters(false);
  };

  const exportPdf = async () => {
    if (!selectedSourceId || !dashboard) return;
    setExporting(true);
    try {
      const blob = await apiClient.exportDashboardToPDF(selectedSourceId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `dashboard_${dashboard.dashboard.source_name.replace(/\s+/g, "_")}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      toast("Export PDF prêt", {
        description: "Le tableau de bord a été téléchargé.",
        variant: "success",
      });
    } catch (e: unknown) {
      console.error("Export PDF error:", e);
      const exportError = e as { message?: string; statusText?: string };
      const msg =
        exportError?.message ||
        exportError?.statusText ||
        "Impossible de générer le PDF du dashboard.";
      toast("Export échoué", {
        description: msg,
        variant: "error",
      });
    } finally {
      setExporting(false);
    }
  };

  const visibleWidgets = dashboard
    ? dashboard.widgets.filter((w) => !removedWidgetIds.has(w.id))
    : [];
  const stackWidgets = gridWidth < 640;

  const renderWidget = (widget: WidgetData, index: number) =>
    widget.type === "metric_card" || (!hasBreakdown(widget) && widget.type !== "world_map") ? (
      <KpiCard
        widget={widget}
        index={index}
        onRemove={() => removeWidget(widget.id)}
        onAnalyseIA={handleAnalyseIA}
      />
    ) : (
      <WidgetCard
        widget={widget}
        onRemove={() => removeWidget(widget.id)}
        variantIndex={index}
        chartTypeOverride={chartOverrides[widget.id]}
        onChartTypeChange={handleChartTypeChange}
        onAnalyseIA={handleAnalyseIA}
      />
    );

  return (
    <div>
      <PageHeader
        title={dashboard ? dashboard.dashboard.name : "Tableau de bord"}
        subtitle={
          dashboard
            ? `${dashboard.dashboard.source_name}${dashboard.dashboard.domain !== "generic" ? ` · ${DOMAIN_LABELS[dashboard.dashboard.domain] || dashboard.dashboard.domain}` : ""}`
            : "Vos indicateurs clés, générés automatiquement à partir de vos sources validées."
        }
        actions={
          <>
            <label className="sr-only" htmlFor="dashboard-source">
              Source de données
            </label>
            <div className="relative min-w-0 flex-1 sm:flex-none">
              <select
                id="dashboard-source"
                value={selectedSourceId ?? ""}
                onChange={handleSourceChange}
                disabled={loading || sources.length === 0}
                className="h-10 w-full min-w-[200px] appearance-none rounded-lg border border-input bg-card pl-3 pr-9 text-sm font-medium text-foreground transition hover:border-foreground/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60 sm:max-w-[280px]"
              >
                <option value="" disabled>
                  {loading ? "Chargement des sources…" : "Sélectionner une source"}
                </option>
                {sources.map((source) => (
                  <option key={source.id} value={source.id}>
                    {source.name}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            </div>
            {dashboard && (
              <Button
                variant="outline"
                onClick={() => void exportPdf()}
                disabled={exporting}
                title="Exporter le tableau de bord en PDF"
              >
                {exporting ? <Loader2 className="animate-spin" /> : <FileDown />}
                <span className="hidden sm:inline">Exporter en PDF</span>
                <span className="sm:hidden">PDF</span>
              </Button>
            )}
          </>
        }
      />

      <PageBody>
        <section className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="font-display text-lg font-semibold text-foreground">
              {userName ? `Bonjour ${userName}` : "Bonjour"}
            </p>
            <p className="text-sm text-muted-foreground">
              Suivez vos indicateurs, repérez les signaux faibles et décidez en confiance.
            </p>
          </div>
          <JourneySteps role={role} current="visualise" className="-mx-1 xl:mx-0" />
        </section>

        {loading ? (
          <div className="space-y-4" aria-busy="true">
            <SkeletonCards count={3} className="xl:grid-cols-3" />
            <Skeleton className="h-72 w-full rounded-xl" />
          </div>
        ) : building ? (
          <div
            className="rounded-xl border border-border bg-card p-8 shadow-card"
            aria-busy="true"
            aria-live="polite"
          >
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/15 text-primary-strong">
                <LayoutDashboard className="h-5 w-5 animate-pulse" />
              </span>
              <div>
                <p className="font-display text-base font-semibold text-foreground">
                  Génération du tableau de bord…
                </p>
                <p className="text-sm text-muted-foreground">
                  Analyse des colonnes, création des widgets, calcul des indicateurs.
                </p>
              </div>
            </div>
            <SkeletonCards count={3} className="mt-6 xl:grid-cols-3" />
          </div>
        ) : !selectedSource ? (
          sources.length === 0 ? (
            <EmptyState
              icon={FileSpreadsheet}
              title="Aucune source validée pour l'instant"
              description={
                can(role, "write:data")
                  ? "Importez un fichier Excel, CSV ou JSON puis validez-le : le tableau de bord se générera automatiquement avec les indicateurs pertinents."
                  : "Un analyste ou un administrateur doit importer et valider une source pour générer le tableau de bord."
              }
              action={
                can(role, "write:data") ? (
                  <Button
                    onClick={() =>
                      void navigate({
                        to: "/app/import",
                        search: { sourceId: undefined, cleaningJobId: undefined, step: undefined },
                      })
                    }
                  >
                    <Upload /> Importer des données
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <EmptyState
              icon={FileSpreadsheet}
              title="Sélectionnez une source validée"
              description="Choisissez une source dans la liste en haut de page : le tableau de bord se générera automatiquement."
            />
          )
        ) : !dashboard ? (
          dashboardQuery.isError ? (
            <ErrorState
              title="Le tableau de bord n'a pas pu être généré"
              message={handleApiError(
                dashboardQuery.error,
                "La source est peut-être vide ou ses colonnes n'ont pas pu être analysées.",
              )}
              onRetry={() => void dashboardQuery.refetch()}
            />
          ) : (
            <EmptyState
              icon={BarChart3}
              title="Aucun tableau de bord disponible"
              description="La source est peut-être vide ou les colonnes n'ont pas pu être analysées."
            />
          )
        ) : (
          <>
            <AnalysePanel
              quickConfig={quickConfig}
              measureOptions={measureOptions}
              groupByOptions={groupByOptions}
              detectedColumns={detected}
              selectedSourceId={selectedSourceId}
              detecting={detecting}
              addingAnalysis={addingAnalysis}
              hasActiveFilters={hasActiveFilters}
              filterList={filterList}
              onConfigChange={setQuickConfig}
              onAdd={() => void addQuickAnalysis()}
              onAddToDashboard={async (config) => {
                if (!selectedSourceId) return;
                try {
                  await apiClient.addWidgetToDashboard(selectedSourceId, config);
                  await queryClient.invalidateQueries({
                    queryKey: ["dashboard-auto", selectedSourceId],
                  });
                  toast("Graphique ajouté", {
                    description: "Le graphique est maintenant visible dans le tableau de bord.",
                    variant: "success",
                  });
                } catch (error) {
                  toast("Ajout impossible", {
                    description: handleApiError(
                      error,
                      "Le graphique n'a pas pu être ajouté au dashboard.",
                    ),
                    variant: "error",
                  });
                }
              }}
            />

            {visibleWidgets.length > 0 && (
              <section aria-labelledby="dashboard-widgets-title" className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <h2
                      id="dashboard-widgets-title"
                      className="font-display text-base font-semibold text-foreground"
                    >
                      Indicateurs et visualisations
                    </h2>
                    <StatusBadge>{visibleWidgets.length}</StatusBadge>
                  </div>
                  {!stackWidgets && (
                    <p className="text-xs text-muted-foreground">
                      Glissez-déposez et redimensionnez les cartes : la disposition est enregistrée.
                    </p>
                  )}
                </div>
                <div ref={gridContainerRef}>
                  {stackWidgets ? (
                    <div className="space-y-4">
                      {visibleWidgets.map((widget, index) => (
                        <div
                          key={String(widget.id)}
                          data-widget-id={widget.id}
                          className={
                            widget.type === "metric_card" ||
                            (!hasBreakdown(widget) && widget.type !== "world_map")
                              ? "h-[200px]"
                              : "h-[340px]"
                          }
                        >
                          {renderWidget(widget, index)}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <GridLayout
                      className="react-grid-layout-custom"
                      layout={gridLayout}
                      width={gridWidth}
                      gridConfig={{
                        cols: 12,
                        rowHeight: 100,
                        margin: [16, 16] as const,
                        containerPadding: [0, 0] as const,
                        maxRows: Infinity,
                      }}
                      dragConfig={{ enabled: true, cancel: ".react-resizable-handle, button" }}
                      resizeConfig={{ enabled: true }}
                      compactor={noCompactor}
                      onLayoutChange={handleLayoutChange}
                    >
                      {visibleWidgets.map((widget, index) => (
                        <div key={String(widget.id)} data-widget-id={widget.id}>
                          {renderWidget(widget, index)}
                        </div>
                      ))}
                    </GridLayout>
                  )}
                </div>
              </section>
            )}

            {visibleWidgets.length === 0 && (
              <EmptyState
                icon={BarChart3}
                title="Aucun indicateur sur ce tableau de bord"
                description="Utilisez le panneau « Créer un indicateur » ci-dessus pour ajouter une carte KPI ou un graphique."
              />
            )}
          </>
        )}
      </PageBody>
    </div>
  );
}

export default DashboardPage;
