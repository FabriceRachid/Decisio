import { createFileRoute, useNavigate } from "@tanstack/react-router";
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  Bot,
  Check,
  ChevronRight,
  Clock,
  Copy,
  Database,
  History,
  LayoutDashboard,
  Loader2,
  RotateCcw,
  Search,
  Sparkles,
  Upload,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { PageHeader } from "@/components/AppShell";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { JourneySteps } from "@/components/app/PageHeader";
import { Stepper, type StepperStep } from "@/components/app/Stepper";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageBody,
  Panel,
  SkeletonCards,
  StatusBadge,
  fieldClass,
} from "@/components/app/kit";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import {
  apiClient,
  handleApiError,
  type AIHistoryItem,
  type DataSourceDetail,
  type SourceKPI,
} from "@/lib/api";
import { can, getCurrentUserProfile } from "@/lib/rbac";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/analyse")({
  component: AnalysePage,
  head: () => ({ meta: [{ title: "Analyse IA — DécisioBI" }] }),
});

const SUGGESTED_QUESTIONS = [
  "Résume l'état de santé de ces KPI",
  "Quelles sont les tendances principales ?",
  "Y a-t-il des anomalies ou signaux faibles ?",
  "Quelles actions recommandes-tu ?",
  "Compare la performance entre les dimensions",
];

type Step = "source" | "kpis" | "question";

const STEPS: StepperStep<Step>[] = [
  { key: "source", label: "Source de données", description: "Jeu de données validé" },
  { key: "kpis", label: "Indicateurs", description: "KPI à interpréter" },
  { key: "question", label: "Question à l'IA", description: "Interprétation en français" },
];

type AiMeta = { model: string; tokens: number | null; time: number | null; kpiCount: number };

const AGG_LABELS: Record<string, string> = {
  sum: "Total",
  avg: "Moyenne",
  count: "Nombre",
  min: "Min",
  max: "Max",
};

const formatAgg = (agg: string) => AGG_LABELS[agg] || agg;

function AnalysePage() {
  const navigate = useNavigate();
  const [role, setRole] = useState<string | null>(null);

  // ── Parcours en 3 étapes ──
  const [step, setStep] = useState<Step>("source");
  const [sources, setSources] = useState<DataSourceDetail[]>([]);
  const [sourceQuery, setSourceQuery] = useState("");
  const [selectedSource, setSelectedSource] = useState<DataSourceDetail | null>(null);
  const [sourceKpis, setSourceKpis] = useState<SourceKPI[]>([]);
  const [selectedWidgetIds, setSelectedWidgetIds] = useState<Set<number>>(new Set());
  const [loadingSources, setLoadingSources] = useState(true);
  const [sourcesError, setSourcesError] = useState<string | null>(null);
  const [loadingKpis, setLoadingKpis] = useState(false);
  const [kpisError, setKpisError] = useState<string | null>(null);

  // ── IA ──
  const [question, setQuestion] = useState("");
  const [aiResponse, setAiResponse] = useState<string | null>(null);
  const [aiMeta, setAiMeta] = useState<AiMeta | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [copied, setCopied] = useState(false);
  const questionRef = useRef<HTMLTextAreaElement>(null);

  // ── Historique ──
  const [history, setHistory] = useState<AIHistoryItem[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    getCurrentUserProfile()
      .then((p) => setRole(p.profile?.role ?? null))
      .catch(() => setRole(null));
  }, []);

  const loadSources = useCallback(async () => {
    try {
      setLoadingSources(true);
      setSourcesError(null);
      const data = await apiClient.listDataSources({ status: "completed" });
      setSources(data);
    } catch (error) {
      setSourcesError(handleApiError(error, "Erreur lors du chargement des sources"));
    } finally {
      setLoadingSources(false);
    }
  }, []);

  useEffect(() => {
    void loadSources();
  }, [loadSources]);

  const loadKpis = async (source: DataSourceDetail) => {
    try {
      setLoadingKpis(true);
      setKpisError(null);
      const result = await apiClient.getKPIsBySource(source.id);
      setSourceKpis(result.kpis);
    } catch (error) {
      setKpisError(handleApiError(error, "Erreur lors du chargement des KPI"));
    } finally {
      setLoadingKpis(false);
    }
  };

  const handleSelectSource = (source: DataSourceDetail) => {
    setSelectedSource(source);
    setStep("kpis");
    setSelectedWidgetIds(new Set());
    setSourceKpis([]);
    setAiResponse(null);
    setAiMeta(null);
    setAiError(null);
    void loadKpis(source);
  };

  const toggleWidget = (widgetId: number) => {
    setSelectedWidgetIds((prev) => {
      const next = new Set(prev);
      if (next.has(widgetId)) next.delete(widgetId);
      else next.add(widgetId);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedWidgetIds.size === sourceKpis.length) {
      setSelectedWidgetIds(new Set());
    } else {
      setSelectedWidgetIds(new Set(sourceKpis.map((k) => k.widget_id)));
    }
  };

  const runAnalysis = async () => {
    if (!question.trim() || !selectedSource || analyzing) return;
    try {
      setAnalyzing(true);
      setAiResponse(null);
      setAiMeta(null);
      setAiError(null);

      const widgetIds = selectedWidgetIds.size > 0 ? Array.from(selectedWidgetIds) : undefined;
      const result = await apiClient.interpretKPIs(question.trim(), {
        source_id: selectedSource.id,
        widget_ids: widgetIds,
      });

      setAiResponse(result.interpretation);
      setAiMeta({
        model: result.model,
        tokens: result.tokens_used,
        time: result.processing_time_ms,
        kpiCount: result.kpi_count,
      });
      toast("Analyse générée", { variant: "success" });
    } catch (error) {
      setAiError(handleApiError(error, "Erreur lors de l'analyse IA"));
    } finally {
      setAnalyzing(false);
    }
  };

  const handleAnalyze = (e: FormEvent) => {
    e.preventDefault();
    void runAnalysis();
  };

  const handleCopy = async () => {
    if (!aiResponse) return;
    try {
      await navigator.clipboard.writeText(aiResponse);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast("Copie impossible dans ce navigateur", { variant: "error" });
    }
  };

  const handleSuggestion = (q: string) => {
    setQuestion(q);
    questionRef.current?.focus();
  };

  const resetQuestion = () => {
    setAiResponse(null);
    setAiMeta(null);
    setAiError(null);
    setQuestion("");
    questionRef.current?.focus();
  };

  const goToStep = (target: Step) => {
    if (target === "source") {
      setStep("source");
      setSelectedSource(null);
      setSourceKpis([]);
      setKpisError(null);
    } else if (target === "kpis") {
      setStep("kpis");
      setAiResponse(null);
      setAiMeta(null);
      setAiError(null);
      setQuestion("");
    }
  };

  const handleBack = () => goToStep(step === "question" ? "kpis" : "source");

  const loadHistory = async () => {
    setHistoryOpen(true);
    try {
      setHistoryLoading(true);
      setHistoryError(null);
      const result = await apiClient.getAIHistory(1);
      setHistory(result.results);
    } catch (error) {
      setHistoryError(handleApiError(error, "Impossible de charger l'historique"));
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleHistoryClick = (item: AIHistoryItem) => {
    setQuestion(item.prompt);
    setAiResponse(item.response);
    setAiError(null);
    setAiMeta({
      model: item.model,
      tokens: item.tokens_used,
      time: item.processing_time_ms,
      kpiCount: item.kpi_count,
    });
    setHistoryOpen(false);
    if (step !== "question") setStep("question");
  };

  const filteredSources = sourceQuery.trim()
    ? sources.filter((s) => s.name.toLowerCase().includes(sourceQuery.trim().toLowerCase()))
    : sources;
  const kpiScope = selectedWidgetIds.size || sourceKpis.length;
  const allSelected = sourceKpis.length > 0 && selectedWidgetIds.size === sourceKpis.length;

  return (
    <>
      <PageHeader
        title="Analyse décisionnelle"
        subtitle="Choisissez une source et des indicateurs, puis demandez à l'IA de les interpréter en français."
        actions={
          <>
            {step !== "source" && (
              <Button variant="outline" onClick={() => goToStep("source")}>
                <RotateCcw /> Nouvelle analyse
              </Button>
            )}
            <Button variant="outline" onClick={() => void loadHistory()}>
              <History /> Historique
            </Button>
          </>
        }
      />

      <PageBody>
        <JourneySteps role={role} current="analyse" />

        <div className="rounded-xl border border-border bg-card px-4 py-3 shadow-card">
          <Stepper
            steps={STEPS}
            current={step}
            onStepClick={goToStep}
            label="Étapes de l'analyse"
          />
        </div>

        <div
          className={cn(
            "grid gap-6",
            step !== "source" && "lg:grid-cols-[minmax(0,1fr)_300px] lg:items-start",
          )}
        >
          <div className="min-w-0 space-y-6">
            {/* ═══════════ Étape 1 : source ═══════════ */}
            {step === "source" && (
              <Panel
                title="Choisir la source de données"
                description="Seules les sources importées avec succès sont proposées."
                icon={Database}
                actions={
                  sources.length > 4 && (
                    <div className="relative w-full sm:w-64">
                      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                      <input
                        type="search"
                        value={sourceQuery}
                        onChange={(e) => setSourceQuery(e.target.value)}
                        placeholder="Rechercher une source…"
                        aria-label="Rechercher une source"
                        className={cn(fieldClass, "pl-9")}
                      />
                    </div>
                  )
                }
              >
                {loadingSources ? (
                  <SkeletonCards count={6} className="xl:grid-cols-3" />
                ) : sourcesError ? (
                  <ErrorState message={sourcesError} onRetry={() => void loadSources()} />
                ) : sources.length === 0 ? (
                  <EmptyState
                    icon={Database}
                    title="Aucune source disponible"
                    description="Importez et préparez un fichier pour pouvoir l'analyser."
                    action={
                      can(role, "write:data") && (
                        <Button
                          onClick={() =>
                            navigate({
                              to: "/app/import",
                              search: {
                                sourceId: undefined,
                                cleaningJobId: undefined,
                                step: undefined,
                              },
                            })
                          }
                        >
                          <Upload /> Importer des données
                        </Button>
                      )
                    }
                  />
                ) : filteredSources.length === 0 ? (
                  <EmptyState
                    icon={Search}
                    title="Aucune source ne correspond"
                    description={`Aucun résultat pour « ${sourceQuery} ».`}
                    action={
                      <Button variant="outline" onClick={() => setSourceQuery("")}>
                        Effacer la recherche
                      </Button>
                    }
                  />
                ) : (
                  <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    {filteredSources.map((source) => (
                      <li key={source.id}>
                        <button
                          type="button"
                          onClick={() => handleSelectSource(source)}
                          className="group flex h-full w-full items-center gap-3 rounded-xl border border-border bg-card p-4 text-left transition hover:border-primary/40 hover:shadow-widget-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-primary/15 text-primary-strong">
                            <Database className="h-5 w-5" />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-semibold text-foreground">
                              {source.name}
                            </span>
                            <span className="mt-0.5 block text-xs text-muted-foreground">
                              {(source.row_count ?? 0).toLocaleString("fr-FR")} lignes ·{" "}
                              <span className="uppercase">{source.source_type}</span>
                            </span>
                          </span>
                          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground transition group-hover:translate-x-0.5" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>
            )}

            {/* ═══════════ Étape 2 : KPI ═══════════ */}
            {step === "kpis" && (
              <Panel
                title="Indicateurs disponibles"
                description="Sélectionnez les KPI à interpréter. Sans sélection, tous les KPI de la source sont analysés."
                icon={BarChart3}
                actions={
                  <Button variant="ghost" size="sm" onClick={handleBack}>
                    <ArrowLeft /> Retour
                  </Button>
                }
              >
                {loadingKpis ? (
                  <LoadingState label="Calcul des indicateurs…" rows={4} />
                ) : kpisError ? (
                  <ErrorState
                    message={kpisError}
                    onRetry={() => selectedSource && void loadKpis(selectedSource)}
                  />
                ) : sourceKpis.length === 0 ? (
                  <EmptyState
                    icon={LayoutDashboard}
                    title="Aucun KPI pour cette source"
                    description="Générez d'abord le tableau de bord de cette source : ses indicateurs seront ensuite disponibles ici."
                    action={
                      <Button onClick={() => navigate({ to: "/app/dashboard" })}>
                        <LayoutDashboard /> Ouvrir le tableau de bord
                      </Button>
                    }
                  />
                ) : (
                  <div className="space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm text-muted-foreground" aria-live="polite">
                        <span className="font-semibold text-foreground tabular-nums">
                          {selectedWidgetIds.size}
                        </span>{" "}
                        / {sourceKpis.length} sélectionné{selectedWidgetIds.size > 1 ? "s" : ""}
                      </p>
                      <Button variant="outline" size="sm" onClick={toggleAll}>
                        {allSelected ? "Tout désélectionner" : "Tout sélectionner"}
                      </Button>
                    </div>

                    <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                      {sourceKpis.map((kpi) => {
                        const checked = selectedWidgetIds.has(kpi.widget_id);
                        return (
                          <li key={kpi.widget_id}>
                            <button
                              type="button"
                              role="checkbox"
                              aria-checked={checked}
                              onClick={() => toggleWidget(kpi.widget_id)}
                              className={cn(
                                "flex h-full w-full flex-col gap-3 rounded-xl border p-4 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                                checked
                                  ? "border-primary bg-primary/5 ring-1 ring-primary"
                                  : "border-border bg-card hover:border-input hover:shadow-widget-hover",
                              )}
                            >
                              <span className="flex items-start justify-between gap-3">
                                <span className="min-w-0 text-sm font-medium text-foreground">
                                  {kpi.title}
                                </span>
                                <span
                                  aria-hidden
                                  className={cn(
                                    "grid h-5 w-5 shrink-0 place-items-center rounded-md border transition",
                                    checked
                                      ? "border-primary bg-primary text-primary-foreground"
                                      : "border-input bg-card",
                                  )}
                                >
                                  {checked && <Check className="h-3.5 w-3.5" />}
                                </span>
                              </span>
                              <span className="font-display text-2xl font-bold tracking-tight text-foreground tabular-nums">
                                {kpi.formatted_value}
                              </span>
                              <span className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                                <StatusBadge>{formatAgg(kpi.aggregation)}</StatusBadge>
                                {kpi.rows_processed.toLocaleString("fr-FR")} lignes
                                {kpi.group_by?.length > 0 && <> · par {kpi.group_by.join(", ")}</>}
                              </span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>

                    <div className="flex flex-col-reverse gap-2 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
                      <p className="text-xs text-muted-foreground">
                        {selectedWidgetIds.size === 0
                          ? `Les ${sourceKpis.length} KPI seront analysés.`
                          : `${selectedWidgetIds.size} KPI seront analysés.`}
                      </p>
                      <Button onClick={() => setStep("question")}>
                        Poser une question <ArrowRight />
                      </Button>
                    </div>
                  </div>
                )}
              </Panel>
            )}

            {/* ═══════════ Étape 3 : question ═══════════ */}
            {step === "question" && (
              <>
                <Panel
                  title="Votre question"
                  description="Formulez votre besoin en langage naturel. Entrée pour envoyer, Maj + Entrée pour un saut de ligne."
                  icon={Bot}
                  actions={
                    <Button variant="ghost" size="sm" onClick={handleBack}>
                      <ArrowLeft /> Retour
                    </Button>
                  }
                >
                  <form onSubmit={handleAnalyze} className="space-y-3">
                    <label htmlFor="ai-question" className="sr-only">
                      Question sur vos KPI
                    </label>
                    <Textarea
                      id="ai-question"
                      ref={questionRef}
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          void runAnalysis();
                        }
                      }}
                      rows={3}
                      placeholder="Ex. : Quels indicateurs se dégradent et pourquoi ?"
                      disabled={analyzing}
                      className="resize-none"
                    />
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex flex-wrap gap-2">
                        {SUGGESTED_QUESTIONS.map((q) => (
                          <button
                            key={q}
                            type="button"
                            onClick={() => handleSuggestion(q)}
                            disabled={analyzing}
                            className="inline-flex items-center gap-1.5 rounded-full border border-border bg-secondary/60 px-3 py-1.5 text-xs font-medium text-muted-foreground transition hover:border-input hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                          >
                            <Sparkles className="h-3 w-3" aria-hidden />
                            {q}
                          </button>
                        ))}
                      </div>
                      <Button
                        type="submit"
                        disabled={analyzing || !question.trim() || !selectedSource}
                        className="ml-auto"
                      >
                        {analyzing ? <Loader2 className="animate-spin" /> : <Sparkles />}
                        {analyzing ? "Analyse en cours…" : "Analyser"}
                      </Button>
                    </div>
                    {!selectedSource && (
                      <p className="text-xs text-muted-foreground">
                        Analyse issue de l'historique : choisissez une source pour poser une
                        nouvelle question.
                      </p>
                    )}
                  </form>
                </Panel>

                {analyzing && (
                  <Panel>
                    <LoadingState label="DécisioBI interprète vos indicateurs…" rows={4} />
                  </Panel>
                )}

                {aiError && !analyzing && (
                  <ErrorState
                    title="L'analyse n'a pas pu être générée"
                    message={aiError}
                    onRetry={() => void runAnalysis()}
                  />
                )}

                {aiResponse && !analyzing && (
                  <Panel
                    title="Interprétation IA"
                    description="Générée à partir de vos KPI : vérifiez les chiffres clés avant de décider."
                    icon={Sparkles}
                    actions={
                      <>
                        <Button variant="outline" size="sm" onClick={() => void handleCopy()}>
                          {copied ? <Check className="text-emerald-600" /> : <Copy />}
                          {copied ? "Copié" : "Copier"}
                        </Button>
                        {selectedSource && (
                          <Button variant="ghost" size="sm" onClick={resetQuestion}>
                            <RotateCcw /> Nouvelle question
                          </Button>
                        )}
                      </>
                    }
                  >
                    <div className="max-w-none text-foreground leading-relaxed">
                      <MarkdownRenderer content={aiResponse} />
                    </div>
                    {aiMeta && (
                      <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-border pt-4">
                        <StatusBadge>Modèle : {aiMeta.model}</StatusBadge>
                        <StatusBadge tone="brand">{aiMeta.kpiCount} KPI analysés</StatusBadge>
                        {aiMeta.time != null && (
                          <StatusBadge>
                            <Clock className="h-3 w-3" /> {(aiMeta.time / 1000).toFixed(1)} s
                          </StatusBadge>
                        )}
                        {aiMeta.tokens != null && (
                          <StatusBadge>{aiMeta.tokens.toLocaleString("fr-FR")} tokens</StatusBadge>
                        )}
                      </div>
                    )}
                  </Panel>
                )}

                {!aiResponse && !analyzing && !aiError && (
                  <EmptyState
                    icon={Sparkles}
                    title="Aucune interprétation pour l'instant"
                    description="Posez une question ou choisissez une suggestion pour obtenir une lecture claire de vos indicateurs."
                  />
                )}
              </>
            )}
          </div>

          {/* ═══════════ Contexte de l'analyse ═══════════ */}
          {step !== "source" && (
            <aside className="space-y-4 lg:sticky lg:top-20">
              <Panel title="Contexte de l'analyse" bodyClassName="space-y-4">
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Source
                  </p>
                  {selectedSource ? (
                    <>
                      <p className="mt-1 truncate text-sm font-semibold text-foreground">
                        {selectedSource.name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {(selectedSource.row_count ?? 0).toLocaleString("fr-FR")} lignes ·{" "}
                        <span className="uppercase">{selectedSource.source_type}</span>
                      </p>
                    </>
                  ) : (
                    <p className="mt-1 text-sm text-muted-foreground">Analyse de l'historique</p>
                  )}
                  <Button
                    variant="link"
                    size="sm"
                    className="h-auto px-0"
                    onClick={() => goToStep("source")}
                  >
                    Changer de source
                  </Button>
                </div>
                {selectedSource && (
                  <div className="border-t border-border pt-4">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Indicateurs
                    </p>
                    <p className="mt-1 text-sm text-foreground">
                      {loadingKpis ? (
                        "Chargement…"
                      ) : (
                        <>
                          <span className="font-semibold tabular-nums">{kpiScope}</span> KPI{" "}
                          {selectedWidgetIds.size > 0 ? "sélectionné(s)" : "(tous)"}
                        </>
                      )}
                    </p>
                    {step === "question" && (
                      <Button
                        variant="link"
                        size="sm"
                        className="h-auto px-0"
                        onClick={() => goToStep("kpis")}
                      >
                        Modifier la sélection
                      </Button>
                    )}
                  </div>
                )}
              </Panel>
              <p className="px-1 text-xs leading-relaxed text-muted-foreground">
                L'assistant s'appuie uniquement sur les KPI calculés par DécisioBI. Pour une
                conversation libre sur vos données, utilisez l'Assistant IA.
              </p>
            </aside>
          )}
        </div>
      </PageBody>

      {/* ═══════════ Historique ═══════════ */}
      <Sheet open={historyOpen} onOpenChange={setHistoryOpen}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-md">
          <SheetHeader>
            <SheetTitle>Historique des analyses</SheetTitle>
            <SheetDescription>Rouvrez une interprétation générée précédemment.</SheetDescription>
          </SheetHeader>
          <div className="mt-6">
            {historyLoading ? (
              <LoadingState label="Chargement de l'historique…" rows={5} />
            ) : historyError ? (
              <ErrorState message={historyError} onRetry={() => void loadHistory()} />
            ) : history.length === 0 ? (
              <EmptyState
                icon={History}
                title="Aucune analyse enregistrée"
                description="Vos interprétations IA apparaîtront ici."
              />
            ) : (
              <ul className="space-y-2">
                {history.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => handleHistoryClick(item)}
                      className="flex w-full items-start gap-3 rounded-xl border border-border bg-card p-3 text-left transition hover:border-primary/40 hover:shadow-widget-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-primary/15 text-primary-strong">
                        <Sparkles className="h-4 w-4" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="line-clamp-2 text-sm font-medium text-foreground">
                          {item.prompt}
                        </span>
                        <span className="mt-1 block text-xs text-muted-foreground">
                          {item.kpi_count} KPI
                          {item.processing_time_ms != null &&
                            ` · ${(item.processing_time_ms / 1000).toFixed(1)} s`}
                          {item.created_at &&
                            ` · ${new Date(item.created_at).toLocaleDateString("fr-FR")}`}
                        </span>
                      </span>
                      <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
