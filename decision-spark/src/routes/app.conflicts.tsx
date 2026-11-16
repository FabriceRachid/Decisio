import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeftRight,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock,
  Edit3,
  FileSpreadsheet,
  GitMerge,
  Info,
  Loader2,
  RefreshCcw,
  ShieldCheck,
  Sparkles,
  Upload,
} from "lucide-react";

import { PageHeader } from "@/components/AppShell";
import {
  EmptyState,
  ErrorState,
  InfoDisclosure,
  PageBody,
  Panel,
  SEVERITY_LABELS,
  Segmented,
  SkeletonCards,
  StatCard,
  StatusBadge,
  type Tone,
  fieldClass,
  severityTone,
} from "@/components/app/kit";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { apiClient, type CleaningJobResponse, type DataSourceDetail } from "@/lib/api";
import { can, getCurrentUserProfile } from "@/lib/rbac";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/conflicts")({
  beforeLoad: async () => {
    const { requireRoleAccess } = await import("@/lib/rbac");
    await requireRoleAccess("read:conflicts");
  },
  validateSearch: (search: Record<string, unknown>) => ({
    sourceId:
      typeof search.sourceId === "string"
        ? Number(search.sourceId) || undefined
        : typeof search.sourceId === "number"
          ? search.sourceId
          : undefined,
    source:
      typeof search.source === "string"
        ? Number(search.source) || undefined
        : typeof search.source === "number"
          ? search.source
          : undefined,
    cleaningJobId:
      typeof search.cleaningJobId === "string"
        ? Number(search.cleaningJobId) || undefined
        : typeof search.cleaningJobId === "number"
          ? search.cleaningJobId
          : undefined,
  }),
  component: ConflictsPage,
  head: () => ({ meta: [{ title: "Conflits de données — DécisioBI" }] }),
});

type ResolutionMethod =
  | "manual_override"
  | "auto_merge"
  | "default_value"
  | "user_selected"
  | "majority_vote"
  | "latest_value"
  | "discard";

type ConflictRecord = {
  id: number;
  data_source?: number;
  source_name?: string;
  conflict_type_name?: string;
  conflict_type_code?: string;
  conflict_type_obj?: {
    resolution_strategy?: string | null;
    severity?: string;
  };
  description?: string | null;
  status: string;
  status_display?: string;
  priority?: number;
  impact_score?: string | number | null;
  affected_columns?: string[];
  affected_row_ids?: string[];
  conflict_details?: Record<string, unknown>;
  assigned_to_username?: string | null;
  detected_at?: string;
  resolutions?: Array<{
    id: number;
    resolution_method: string;
    method_display?: string;
    resolved_at?: string;
    resolution_notes?: string | null;
  }>;
};

type DatasetBasis = "validated_cleaning" | null;

type SourcePipelineState = {
  stage: "validated" | "pending_validation" | "cleaning_running" | "cleaning_failed" | "imported";
  label: string;
  tone: Tone;
  helper: string;
  latestJob: CleaningJobResponse | null;
};

type StatusFilter = "all" | "detected" | "in_progress" | "closed";

const isClosed = (status: string) => status === "resolved" || status === "ignored";
const isInProgress = (status: string) => status === "investigating" || status === "resolving";

function statusTone(status: string): Tone {
  if (status === "resolved") return "success";
  if (status === "ignored") return "neutral";
  if (isInProgress(status)) return "info";
  return "warning";
}

function getStatusLabel(status: string, backendLabel?: string) {
  if (status === "detected") return "Nouveau conflit";
  if (status === "investigating") return "Pris en charge";
  if (status === "resolving") return "En attente de validation";
  if (status === "resolved") return "Résolu";
  if (status === "ignored") return "Ignoré";
  return backendLabel || status;
}

function summarizeConflictDetails(details?: Record<string, unknown>) {
  if (!details) return [];

  const summary: string[] = [];
  if (typeof details.duplicate_count === "number")
    summary.push(`Doublons exacts : ${details.duplicate_count}`);
  if (typeof details.conflict_group_count === "number")
    summary.push(`Groupes métier en conflit : ${details.conflict_group_count}`);
  if (typeof details.missing_count === "number")
    summary.push(`Valeurs manquantes : ${details.missing_count}`);
  if (typeof details.missing_rate === "number")
    summary.push(`Taux manquant : ${(details.missing_rate * 100).toFixed(1)} %`);
  if (typeof details.field_count === "number")
    summary.push(`Champs concernés : ${details.field_count}`);
  if (typeof details.field === "string" && details.field)
    summary.push(`Champ critique : ${details.field}`);
  if (typeof details.invalid_count === "number")
    summary.push(`Valeurs invalides : ${details.invalid_count}`);

  return summary;
}

function toSupportedResolutionMethod(value?: string | null): ResolutionMethod {
  const supported: ResolutionMethod[] = [
    "manual_override",
    "auto_merge",
    "default_value",
    "user_selected",
    "majority_vote",
    "latest_value",
    "discard",
  ];
  return supported.includes(value as ResolutionMethod)
    ? (value as ResolutionMethod)
    : "user_selected";
}

function getPipelineSummary(jobs: CleaningJobResponse[]): SourcePipelineState {
  const latestJob = jobs[0] || null;
  const validatedJob = jobs.find((job) => job.is_fully_validated) || null;
  const completedJob = jobs.find((job) => job.status === "completed") || null;

  if (validatedJob) {
    return {
      stage: "validated",
      label: "Nettoyage validé",
      tone: "success",
      helper: "Les conflits sont analysés sur la dernière version nettoyée et validée.",
      latestJob: validatedJob,
    };
  }
  if (completedJob) {
    return {
      stage: "pending_validation",
      label: "Validation en attente",
      tone: "warning",
      helper: "Une version nettoyée existe, mais elle n'a pas encore été validée.",
      latestJob: completedJob,
    };
  }
  if (
    latestJob &&
    (latestJob.status === "queued" ||
      latestJob.status === "running" ||
      latestJob.status === "pending")
  ) {
    return {
      stage: "cleaning_running",
      label: "Nettoyage en cours",
      tone: "info",
      helper: "Attendez la fin du nettoyage ou revenez plus tard pour reprendre.",
      latestJob,
    };
  }
  if (latestJob && latestJob.status === "failed") {
    return {
      stage: "cleaning_failed",
      label: "Nettoyage échoué",
      tone: "danger",
      helper: "La dernière tentative de nettoyage a échoué.",
      latestJob,
    };
  }
  return {
    stage: "imported",
    label: "Importé",
    tone: "neutral",
    helper: "Aucun nettoyage validé : cette source ne peut pas encore être contrôlée.",
    latestJob: null,
  };
}

function basisLabel(basis: DatasetBasis) {
  return basis === "validated_cleaning" ? "dernier nettoyage validé" : "non disponible";
}

function summarizeAffectedRows(rowIds?: string[], totalRows?: number | null) {
  if (!rowIds || rowIds.length === 0) return "Lignes non précisées";
  if (totalRows && rowIds.length >= totalRows) return "Toutes les lignes sont affectées";
  if (rowIds.length <= 6) return `Lignes ${rowIds.join(", ")}`;
  return `${rowIds.length} lignes affectées, dont ${rowIds.slice(0, 5).join(", ")}…`;
}

function notifyConflictsChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("decisiobi:conflicts-changed"));
  }
}

const SEVERITY_BORDER: Record<Tone, string> = {
  danger: "border-l-red-500",
  warning: "border-l-amber-500",
  info: "border-l-blue-500",
  neutral: "border-l-border",
  success: "border-l-emerald-500",
  brand: "border-l-primary",
};

function ConflictsPage() {
  const search = Route.useSearch();
  const navigate = useNavigate({ from: "/app/conflicts" });
  const selectedSourceId = (search?.sourceId as number) || (search?.source as number) || null;

  const [role, setRole] = useState<string | null>(null);
  const [availableSources, setAvailableSources] = useState<DataSourceDetail[]>([]);
  const [jobsBySource, setJobsBySource] = useState<Record<number, CleaningJobResponse[]>>({});
  const [selectedSource, setSelectedSource] = useState<DataSourceDetail | null>(null);
  const [activeDataset, setActiveDataset] = useState<DatasetBasis>(null);
  const [detectionSummary, setDetectionSummary] = useState<string | null>(null);
  const [conflicts, setConflicts] = useState<ConflictRecord[]>([]);
  const [manualMap, setManualMap] = useState<Record<number, string>>({});
  const [editingMap, setEditingMap] = useState<Record<number, boolean>>({});
  const [guidanceOpenFor, setGuidanceOpenFor] = useState<number | null>(null);
  const [guidanceData, setGuidanceData] = useState<Record<string, unknown> | null>(null);
  const [loadingGuidance, setLoadingGuidance] = useState(false);
  const [loadingCatalog, setLoadingCatalog] = useState(false);
  const [catalogError, setCatalogError] = useState(false);
  const [loadingConflicts, setLoadingConflicts] = useState(false);
  const [conflictsError, setConflictsError] = useState(false);
  const [expandedConflictId, setExpandedConflictId] = useState<number | null>(null);
  const [recommendedConflictId, setRecommendedConflictId] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [pendingId, setPendingId] = useState<number | null>(null);

  const sourceCards = useMemo(
    () =>
      availableSources
        .map((source) => ({
          source,
          summary: getPipelineSummary(jobsBySource[source.id] || []),
        }))
        .filter((item) => item.summary.stage === "validated"),
    [availableSources, jobsBySource],
  );

  const sourceContext = selectedSourceId ? jobsBySource[selectedSourceId] || [] : [];
  const sourcePipeline = getPipelineSummary(sourceContext);

  const resolvedCount = conflicts.filter((c) => isClosed(c.status)).length;
  const inProgressCount = conflicts.filter((c) => isInProgress(c.status)).length;
  const pendingCount = conflicts.filter((c) => c.status === "detected").length;
  const criticalCount = conflicts.filter(
    (c) => c.conflict_type_obj?.severity === "critical",
  ).length;

  const filteredConflicts = conflicts.filter((c) => {
    if (statusFilter === "detected") return c.status === "detected";
    if (statusFilter === "in_progress") return isInProgress(c.status);
    if (statusFilter === "closed") return isClosed(c.status);
    return true;
  });

  const hydrateConflictLocalState = (items: ConflictRecord[]) => {
    setManualMap((previous) => {
      const next = { ...previous };
      for (const item of items) {
        if (!(item.id in next)) next[item.id] = "";
      }
      return next;
    });
    setEditingMap((previous) => {
      const next = { ...previous };
      for (const item of items) {
        if (!(item.id in next)) next[item.id] = false;
      }
      return next;
    });
  };

  const loadSourceCatalog = async () => {
    setLoadingCatalog(true);
    setCatalogError(false);
    try {
      const [sources, jobsPage] = await Promise.all([
        apiClient.listDataSources({ ordering: "-created_at" }),
        apiClient.getCleaningJobs({ page: 1, page_size: 200 }),
      ]);
      setAvailableSources(sources);
      const grouped: Record<number, CleaningJobResponse[]> = {};
      for (const job of jobsPage.results || []) {
        const sourceId = job.source;
        if (!sourceId) continue;
        if (!grouped[sourceId]) grouped[sourceId] = [];
        grouped[sourceId].push(job);
      }
      Object.values(grouped).forEach((jobs) =>
        jobs.sort((left, right) => {
          const leftDate = new Date(left.completed_at || left.created_at || 0).getTime();
          const rightDate = new Date(right.completed_at || right.created_at || 0).getTime();
          return rightDate - leftDate;
        }),
      );
      setJobsBySource(grouped);
    } catch (error) {
      console.error("Failed to load conflict source catalog", error);
      setCatalogError(true);
      toast("Impossible de charger les sources disponibles", { variant: "error" });
    } finally {
      setLoadingCatalog(false);
    }
  };

  const ensureEligibleSource = (sourceId: number) => {
    const summary = getPipelineSummary(jobsBySource[sourceId] || []);
    if (summary.stage !== "validated") {
      setSelectedSource(null);
      setConflicts([]);
      setActiveDataset(null);
      setDetectionSummary(null);
      toast("Source non éligible au contrôle", {
        description:
          "Seuls les fichiers dont le nettoyage a été validé peuvent entrer dans la gestion des conflits.",
        variant: "error",
      });
      void navigate({
        to: "/app/conflicts",
        search: { sourceId: undefined, source: undefined, cleaningJobId: undefined },
      });
      return false;
    }
    return true;
  };

  const loadExistingConflicts = async (sourceId: number) => {
    setLoadingConflicts(true);
    setConflictsError(false);
    try {
      if (!ensureEligibleSource(sourceId)) return;
      const [source, page] = await Promise.all([
        apiClient.getDataSource(sourceId),
        apiClient.getConflicts({ data_source: sourceId, page: 1, page_size: 100 }),
      ]);
      const detailedConflicts = await Promise.all(
        (page.results || []).map(async (conflict: { id: number }) => ({
          ...conflict,
          ...(await apiClient.getConflict(conflict.id)),
        })),
      );
      setSelectedSource(source);
      setConflicts(detailedConflicts);
      setActiveDataset("validated_cleaning");
      setDetectionSummary(
        detailedConflicts.length > 0
          ? `${detailedConflicts.length} conflit(s) déjà détecté(s) pour cette version validée.`
          : "Aucun conflit détecté pour cette version validée.",
      );
      hydrateConflictLocalState(detailedConflicts);
      setExpandedConflictId(detailedConflicts[0]?.id ?? null);
      notifyConflictsChanged();
    } catch (error) {
      console.error("Failed to load conflicts", error);
      setConflictsError(true);
      toast("Impossible de charger les conflits pour cette source", { variant: "error" });
    } finally {
      setLoadingConflicts(false);
    }
  };

  const analyzeSource = async (sourceId: number) => {
    setLoadingConflicts(true);
    setConflictsError(false);
    try {
      if (!ensureEligibleSource(sourceId)) return;
      const [source, detection] = await Promise.all([
        apiClient.getDataSource(sourceId),
        apiClient.detectConflicts(sourceId),
      ]);
      const detailedConflicts = (detection?.conflicts || []) as ConflictRecord[];
      setSelectedSource(source);
      setConflicts(detailedConflicts);
      setActiveDataset("validated_cleaning");
      setDetectionSummary(typeof detection?.summary === "string" ? detection.summary : null);
      hydrateConflictLocalState(detailedConflicts);
      setExpandedConflictId(detailedConflicts[0]?.id ?? null);
      notifyConflictsChanged();
    } catch (error) {
      console.error("Failed to analyze conflicts", error);
      toast("Impossible de réanalyser les conflits pour cette source", { variant: "error" });
    } finally {
      setLoadingConflicts(false);
    }
  };

  const resolve = async (
    conflictId: number,
    payload: {
      resolution_method: string;
      chosen_value?: unknown;
      resolution_notes: string;
      requires_approval?: boolean;
    },
  ) => {
    setEditingMap((previous) => ({ ...previous, [conflictId]: false }));
    setPendingId(conflictId);
    try {
      await apiClient.resolveConflict(conflictId, payload);
      toast("Conflit résolu", { description: payload.resolution_notes, variant: "success" });
      if (selectedSourceId) {
        await loadExistingConflicts(selectedSourceId);
      }
      notifyConflictsChanged();
    } catch (error) {
      console.error("Resolve conflict failed", error);
      toast("Échec de la résolution", { variant: "error" });
    } finally {
      setPendingId(null);
    }
  };

  const acknowledge = async (conflictId: number) => {
    setPendingId(conflictId);
    try {
      await apiClient.acknowledgeConflict(conflictId);
      toast("Conflit pris en charge", { variant: "success" });
      if (selectedSourceId) {
        await loadExistingConflicts(selectedSourceId);
        setExpandedConflictId(conflictId);
      }
      notifyConflictsChanged();
    } catch (error) {
      console.error("Acknowledge conflict failed", error);
      toast("Impossible de prendre en charge ce conflit", { variant: "error" });
    } finally {
      setPendingId(null);
    }
  };

  const openGuidance = async (conflictId: number) => {
    setGuidanceOpenFor(conflictId);
    setGuidanceData(null);
    setLoadingGuidance(true);
    try {
      const data = await apiClient.getConflictGuidance(conflictId);
      setGuidanceData(data || null);
    } catch (error) {
      console.error("Failed to load guidance", error);
      toast("Impossible de charger la guidance", { variant: "error" });
      setGuidanceOpenFor(null);
    } finally {
      setLoadingGuidance(false);
    }
  };

  const continueWithGuidance = async () => {
    if (!guidanceOpenFor) {
      setGuidanceOpenFor(null);
      return;
    }
    const conflict = conflicts.find((item) => item.id === guidanceOpenFor);
    if (!conflict) {
      setGuidanceOpenFor(null);
      return;
    }

    if (conflict.status === "detected") {
      try {
        await apiClient.acknowledgeConflict(conflict.id);
        if (selectedSourceId) {
          await loadExistingConflicts(selectedSourceId);
        }
        setExpandedConflictId(conflict.id);
        setRecommendedConflictId(conflict.id);
        toast("Traitement démarré", {
          description:
            "Le conflit est maintenant pris en charge. Vous pouvez passer à la décision finale.",
          variant: "success",
        });
      } catch (error) {
        console.error("Acknowledge from guidance failed", error);
        toast("Impossible de préparer la résolution", { variant: "error" });
      }
    } else {
      setExpandedConflictId(conflict.id);
      setRecommendedConflictId(conflict.id);
      toast("Recommandation prête", {
        description:
          "Vous pouvez maintenant résoudre le conflit avec cette recommandation ou choisir une décision manuelle.",
        variant: "info",
      });
    }
    setGuidanceOpenFor(null);
  };

  useEffect(() => {
    void loadSourceCatalog();
    getCurrentUserProfile()
      .then((profile) => setRole(profile.profile?.role ?? null))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedSourceId) {
      setSelectedSource(null);
      setConflicts([]);
      setActiveDataset(null);
      setDetectionSummary(null);
      return;
    }
    setStatusFilter("all");
    void loadExistingConflicts(selectedSourceId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSourceId]);

  const clearSource = () =>
    void navigate({
      to: "/app/conflicts",
      search: { sourceId: undefined, source: undefined, cleaningJobId: undefined },
    });

  return (
    <div>
      <PageHeader
        title="Conflits de données"
        subtitle={
          selectedSource
            ? `${selectedSource.name} · base analysée : ${basisLabel(activeDataset)}`
            : "Repérez les incohérences restantes et décidez comment les traiter avant l'analyse."
        }
        actions={
          selectedSourceId ? (
            <>
              <Button variant="outline" onClick={clearSource}>
                <ArrowLeftRight /> Changer de source
              </Button>
              <Button
                onClick={() => selectedSourceId && void analyzeSource(selectedSourceId)}
                disabled={loadingConflicts}
              >
                <RefreshCcw className={cn(loadingConflicts && "animate-spin")} /> Réanalyser
              </Button>
            </>
          ) : undefined
        }
      />

      <PageBody>
        <InfoDisclosure title="Qu'est-ce qu'un conflit de données ?" icon={Info}>
          <p>
            Selon la norme <span className="font-medium text-foreground">ISO 8000</span> (norme
            internationale pour la qualité des données), un conflit est une incohérence détectée
            dans les données qui compromet leur intégrité. L'ISO 8000 définit six dimensions de
            qualité : unicité, complétude, cohérence, validité, exactitude et fraîcheur. Un conflit
            survient lorsqu'une de ces dimensions n'est pas respectée.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              {
                t: "Doublons",
                d: "Enregistrements identiques détectés par hash MD5.",
                dim: "unicité",
              },
              {
                t: "Valeurs manquantes",
                d: "Champs absents dans plus de 20 % des lignes.",
                dim: "complétude",
              },
              {
                t: "Types mélangés",
                d: "Une même colonne contient des types différents (texte et nombre).",
                dim: "cohérence",
              },
              {
                t: "Formats incohérents",
                d: "Valeurs qui ne respectent pas le format attendu (email, téléphone, date).",
                dim: "validité",
              },
            ].map((item) => (
              <div key={item.t} className="rounded-lg border border-border bg-secondary/40 p-3">
                <p className="font-semibold text-foreground">{item.t}</p>
                <p className="mt-1 text-xs">
                  {item.d} Correspond à la dimension{" "}
                  <span className="font-medium text-foreground">{item.dim}</span> de l'ISO 8000.
                </p>
              </div>
            ))}
          </div>
          <p className="text-xs">
            <span className="font-medium text-foreground">Références :</span> ISO 8000-2:2020 (Data
            Quality Management), ISO 25012:2008 (Data Quality Model), DAMA-DMBOK 2nd Edition (Data
            Management Body of Knowledge).
          </p>
        </InfoDisclosure>

        {!selectedSourceId && (
          <Panel
            title="Choisir une source"
            description="Sélectionnez un fichier dont le nettoyage a déjà été validé."
            icon={FileSpreadsheet}
          >
            {loadingCatalog ? (
              <SkeletonCards count={4} className="xl:grid-cols-2" />
            ) : catalogError ? (
              <ErrorState
                title="Impossible de charger les sources disponibles"
                onRetry={() => void loadSourceCatalog()}
              />
            ) : sourceCards.length === 0 ? (
              <EmptyState
                icon={ShieldCheck}
                title="Aucune source validée pour le moment"
                description="Les conflits s'analysent sur des données nettoyées et validées. Terminez la préparation d'une source pour commencer le contrôle."
                action={
                  can(role, "write:data") ? (
                    <Button
                      onClick={() =>
                        void navigate({
                          to: "/app/import",
                          search: {
                            sourceId: undefined,
                            cleaningJobId: undefined,
                            step: undefined,
                          },
                        })
                      }
                    >
                      <Upload /> Importer & préparer
                    </Button>
                  ) : undefined
                }
              />
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {sourceCards.map(({ source, summary }) => (
                  <button
                    key={source.id}
                    type="button"
                    onClick={() =>
                      void navigate({
                        to: "/app/conflicts",
                        search: {
                          sourceId: source.id,
                          source: undefined,
                          cleaningJobId: undefined,
                        },
                      })
                    }
                    className="group rounded-xl border border-border bg-card p-5 text-left transition hover:border-foreground/20 hover:shadow-widget-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <p className="truncate font-display text-base font-semibold text-foreground">
                          {source.name}
                        </p>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {source.row_count.toLocaleString("fr-FR")} lignes · {source.column_count}{" "}
                          colonnes
                        </p>
                      </div>
                      <StatusBadge tone={summary.tone} dot>
                        {summary.label}
                      </StatusBadge>
                    </div>
                    <p className="mt-3 text-sm text-muted-foreground">{summary.helper}</p>
                    <p className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-primary-strong">
                      Analyser les conflits
                      <span aria-hidden className="transition group-hover:translate-x-0.5">
                        →
                      </span>
                    </p>
                  </button>
                ))}
              </div>
            )}
          </Panel>
        )}

        {selectedSourceId && (
          <>
            <section
              aria-label="Synthèse des conflits"
              className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
            >
              <StatCard
                label="Conflits détectés"
                value={conflicts.length}
                hint={
                  criticalCount
                    ? `dont ${criticalCount} critique${criticalCount > 1 ? "s" : ""}`
                    : "Aucun conflit critique"
                }
                icon={GitMerge}
                tone={criticalCount ? "danger" : "neutral"}
                loading={loadingConflicts}
                onClick={() => setStatusFilter("all")}
                active={statusFilter === "all"}
              />
              <StatCard
                label="À traiter"
                value={pendingCount}
                hint="Nouveaux, non pris en charge"
                icon={AlertTriangle}
                tone="warning"
                loading={loadingConflicts}
                onClick={() => setStatusFilter("detected")}
                active={statusFilter === "detected"}
              />
              <StatCard
                label="En cours"
                value={inProgressCount}
                hint="Pris en charge ou en validation"
                icon={Clock}
                tone="info"
                loading={loadingConflicts}
                onClick={() => setStatusFilter("in_progress")}
                active={statusFilter === "in_progress"}
              />
              <StatCard
                label="Clôturés"
                value={resolvedCount}
                hint="Résolus ou ignorés"
                icon={CheckCircle2}
                tone="success"
                loading={loadingConflicts}
                onClick={() => setStatusFilter("closed")}
                active={statusFilter === "closed"}
              />
            </section>

            <Panel
              title="Conflits de la source"
              description={
                <span className="inline-flex flex-wrap items-center gap-2">
                  {selectedSource && (
                    <StatusBadge tone={sourcePipeline.tone} dot>
                      {sourcePipeline.label}
                    </StatusBadge>
                  )}
                  {detectionSummary}
                </span>
              }
              icon={GitMerge}
              actions={
                <Segmented
                  label="Filtrer par statut"
                  value={statusFilter}
                  onChange={setStatusFilter}
                  options={[
                    { value: "all", label: "Tous", count: conflicts.length },
                    { value: "detected", label: "À traiter", count: pendingCount },
                    { value: "in_progress", label: "En cours", count: inProgressCount },
                    { value: "closed", label: "Clôturés", count: resolvedCount },
                  ]}
                />
              }
              bodyClassName="space-y-4"
            >
              {loadingConflicts ? (
                <div
                  className="flex items-center gap-2 py-8 text-sm text-muted-foreground"
                  aria-live="polite"
                >
                  <Loader2 className="h-4 w-4 animate-spin" /> Analyse des conflits en cours…
                </div>
              ) : conflictsError ? (
                <ErrorState
                  title="Impossible de charger les conflits pour cette source"
                  onRetry={() => selectedSourceId && void loadExistingConflicts(selectedSourceId)}
                />
              ) : conflicts.length === 0 ? (
                <EmptyState
                  icon={ShieldCheck}
                  title="Aucun conflit bloquant détecté"
                  description="Cette source peut poursuivre vers l'analyse sans arbitrage supplémentaire."
                />
              ) : filteredConflicts.length === 0 ? (
                <EmptyState
                  icon={CheckCircle2}
                  title="Aucun conflit dans ce filtre"
                  action={
                    <Button variant="outline" onClick={() => setStatusFilter("all")}>
                      Afficher tous les conflits
                    </Button>
                  }
                />
              ) : (
                filteredConflicts.map((conflict) => (
                  <ConflictCard
                    key={conflict.id}
                    conflict={conflict}
                    sourceName={selectedSource?.name}
                    totalRows={selectedSource?.row_count ?? null}
                    expanded={expandedConflictId === conflict.id}
                    onToggle={() =>
                      setExpandedConflictId((current) =>
                        current === conflict.id ? null : conflict.id,
                      )
                    }
                    editing={editingMap[conflict.id] ?? false}
                    manualValue={manualMap[conflict.id] ?? ""}
                    onManualChange={(value) =>
                      setManualMap((previous) => ({ ...previous, [conflict.id]: value }))
                    }
                    onEdit={(value) =>
                      setEditingMap((previous) => ({ ...previous, [conflict.id]: value }))
                    }
                    recommended={recommendedConflictId === conflict.id}
                    pending={pendingId === conflict.id}
                    onGuidance={() => void openGuidance(conflict.id)}
                    onAcknowledge={() => void acknowledge(conflict.id)}
                    onResolve={(payload) => void resolve(conflict.id, payload)}
                  />
                ))
              )}
            </Panel>
          </>
        )}
      </PageBody>

      <Dialog
        open={guidanceOpenFor !== null}
        onOpenChange={(open) => !open && setGuidanceOpenFor(null)}
      >
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="font-display">Guidance de résolution</DialogTitle>
            <DialogDescription>
              Le système propose une méthode de traitement pour ce conflit.
            </DialogDescription>
          </DialogHeader>

          {loadingGuidance ? (
            <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Chargement de la guidance…
            </div>
          ) : guidanceData ? (
            <div className="space-y-4">
              <div className="rounded-xl border border-border bg-secondary/40 p-4">
                <p className="font-semibold text-foreground">
                  {String(guidanceData.guidance || "Aide disponible")}
                </p>
                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                  <StatusBadge tone="brand">
                    Recommandation : {String(guidanceData.recommended_strategy || "—")}
                  </StatusBadge>
                  <StatusBadge tone={severityTone(String(guidanceData.risk_level || ""))}>
                    Risque : {String(guidanceData.risk_level || "—")}
                  </StatusBadge>
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-lg border border-border p-3 text-sm">
                  <p className="text-xs font-medium text-muted-foreground">Champs concernés</p>
                  <p className="mt-1 font-medium">
                    {Array.isArray(guidanceData.affected_fields)
                      ? guidanceData.affected_fields.join(", ") || "Non précisés"
                      : "Non précisés"}
                  </p>
                </div>
                <div className="rounded-lg border border-border p-3 text-sm">
                  <p className="text-xs font-medium text-muted-foreground">Volume concerné</p>
                  <p className="mt-1 font-medium">
                    {String(guidanceData.affected_rows ?? "—")} ligne(s)
                  </p>
                </div>
              </div>

              {Array.isArray(guidanceData.steps) && guidanceData.steps.length > 0 && (
                <div>
                  <p className="text-sm font-semibold">Marche à suivre</p>
                  <ol className="mt-2 max-h-48 space-y-2 overflow-auto rounded-lg border border-border p-3 text-sm">
                    {guidanceData.steps.map((step, index) => {
                      const item = step as Record<string, unknown>;
                      return (
                        <li key={index} className="flex gap-3">
                          <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-secondary text-[11px] font-bold">
                            {String(item.step ?? index + 1)}
                          </span>
                          <div>
                            <p className="font-medium">{String(item.description || "Étape")}</p>
                            {item.action ? (
                              <p className="text-muted-foreground">{String(item.action)}</p>
                            ) : null}
                          </div>
                        </li>
                      );
                    })}
                  </ol>
                </div>
              )}

              {guidanceData.impact_analysis ? (
                <div className="rounded-lg border border-border p-3 text-sm">
                  <p className="font-semibold text-foreground">Analyse d'impact</p>
                  <pre className="mt-2 overflow-auto whitespace-pre-wrap font-mono text-xs text-muted-foreground">
                    {JSON.stringify(guidanceData.impact_analysis, null, 2)}
                  </pre>
                </div>
              ) : null}
            </div>
          ) : (
            <EmptyState
              className="py-8"
              title="Aucune guidance disponible"
              description="Vous pouvez tout de même résoudre ce conflit par une décision manuelle."
            />
          )}

          <DialogFooter className="gap-2 sm:gap-2">
            <Button variant="outline" onClick={() => setGuidanceOpenFor(null)}>
              Fermer
            </Button>
            {guidanceData && !loadingGuidance && (
              <Button onClick={() => void continueWithGuidance()}>
                <Sparkles /> Continuer avec cette recommandation
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

type ResolvePayload = {
  resolution_method: string;
  chosen_value?: unknown;
  resolution_notes: string;
  requires_approval?: boolean;
};

function ConflictCard({
  conflict,
  sourceName,
  totalRows,
  expanded,
  onToggle,
  editing,
  manualValue,
  onManualChange,
  onEdit,
  recommended,
  pending,
  onGuidance,
  onAcknowledge,
  onResolve,
}: {
  conflict: ConflictRecord;
  sourceName?: string;
  totalRows: number | null;
  expanded: boolean;
  onToggle: () => void;
  editing: boolean;
  manualValue: string;
  onManualChange: (value: string) => void;
  onEdit: (value: boolean) => void;
  recommended: boolean;
  pending: boolean;
  onGuidance: () => void;
  onAcknowledge: () => void;
  onResolve: (payload: ResolvePayload) => void;
}) {
  const severity = conflict.conflict_type_obj?.severity;
  const sevTone = severityTone(severity);
  const detailSummary = summarizeConflictDetails(conflict.conflict_details);
  const lastResolution = conflict.resolutions?.[0] || null;
  const closed = isClosed(conflict.status);
  const rowSummary = summarizeAffectedRows(conflict.affected_row_ids, totalRows);
  const isCritical = severity === "critical";
  const strategy = toSupportedResolutionMethod(conflict.conflict_type_obj?.resolution_strategy);
  const detailId = `conflict-detail-${conflict.id}`;

  return (
    <article
      className={cn(
        "overflow-hidden rounded-xl border border-l-4 border-border bg-card",
        SEVERITY_BORDER[sevTone],
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-4 p-5">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge tone={statusTone(conflict.status)} dot>
              {getStatusLabel(conflict.status, conflict.status_display)}
            </StatusBadge>
            <StatusBadge tone={sevTone}>
              Gravité : {severity ? SEVERITY_LABELS[severity] || severity : "—"}
            </StatusBadge>
          </div>
          <h3 className="font-display text-base font-semibold text-foreground">
            {conflict.conflict_type_name || "Conflit détecté"}
          </h3>
          <p className="text-sm text-muted-foreground">
            {conflict.description || "Le système a détecté un écart nécessitant un arbitrage."}
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span>
              Colonnes :{" "}
              <span className="font-medium text-foreground">
                {conflict.affected_columns?.join(", ") || "Non précisées"}
              </span>
            </span>
            <span>{rowSummary}</span>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={onToggle}
          aria-expanded={expanded}
          aria-controls={detailId}
        >
          {expanded ? "Réduire" : "Voir le détail"}
          <ChevronDown className={cn("transition-transform", expanded && "rotate-180")} />
        </Button>
      </div>

      {expanded && (
        <div id={detailId}>
          <div className="grid gap-4 border-t border-border p-5 md:grid-cols-2">
            <div className="rounded-lg border border-border bg-secondary/40 p-4">
              <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                <FileSpreadsheet className="h-3.5 w-3.5" /> Source et portée
              </p>
              <dl className="mt-3 space-y-1.5 text-sm">
                <div>
                  <dt className="inline text-muted-foreground">Source : </dt>
                  <dd className="inline font-medium">
                    {sourceName || conflict.source_name || "Non disponible"}
                  </dd>
                </div>
                <div>
                  <dt className="inline text-muted-foreground">Type : </dt>
                  <dd className="inline font-medium">
                    {conflict.conflict_type_name || conflict.conflict_type_code || "Conflit"}
                  </dd>
                </div>
                <div>
                  <dt className="inline text-muted-foreground">Colonnes : </dt>
                  <dd className="inline font-medium">
                    {conflict.affected_columns?.join(", ") || "Non précisées"}
                  </dd>
                </div>
                <div className="text-muted-foreground">{rowSummary}</div>
              </dl>
            </div>

            <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-4">
              <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-amber-800">
                <AlertTriangle className="h-3.5 w-3.5" /> Ce qui justifie l'alerte
              </p>
              <ul className="mt-3 space-y-1.5 text-sm text-foreground">
                {detailSummary.length > 0 ? (
                  detailSummary.map((item) => <li key={item}>{item}</li>)
                ) : (
                  <li className="text-muted-foreground">
                    Les détails techniques existent, mais aucun résumé métier court n'a été fourni
                    pour ce conflit.
                  </li>
                )}
              </ul>
            </div>
          </div>

          {editing && (
            <div className="flex flex-col gap-2 border-t border-border bg-secondary/40 p-4 sm:flex-row sm:items-center">
              <label htmlFor={`manual-${conflict.id}`} className="sr-only">
                Valeur à retenir
              </label>
              <input
                id={`manual-${conflict.id}`}
                type="text"
                placeholder="Saisir la valeur à retenir"
                value={manualValue}
                onChange={(event) => onManualChange(event.target.value)}
                className={cn(fieldClass, "h-10 flex-1")}
                autoFocus
              />
              <div className="flex gap-2">
                <Button
                  disabled={!manualValue || pending}
                  onClick={() =>
                    manualValue &&
                    onResolve({
                      resolution_method: "manual_override",
                      chosen_value: { manual_value: manualValue },
                      resolution_notes: `Valeur retenue manuellement : ${manualValue}`,
                      requires_approval: isCritical,
                    })
                  }
                >
                  <Check /> Valider
                </Button>
                <Button variant="outline" onClick={() => onEdit(false)}>
                  Annuler
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {closed ? (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-emerald-200 bg-emerald-50/70 px-5 py-3">
          <p className="flex items-center gap-2 text-sm font-semibold text-emerald-800">
            <CheckCircle2 className="h-4 w-4" />
            {getStatusLabel(conflict.status, conflict.status_display)}
          </p>
          {lastResolution && (
            <p className="text-xs text-emerald-900/80">
              Dernière résolution :{" "}
              {lastResolution.method_display || lastResolution.resolution_method}
            </p>
          )}
        </div>
      ) : conflict.status === "detected" ? (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-4">
          <div>
            <p className="text-sm font-semibold text-foreground">
              Étape 1 · Comprendre et prendre en charge
            </p>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Consultez l'aide si nécessaire, puis démarrez le traitement avant de choisir une
              résolution.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={onGuidance}>
              <Sparkles /> Voir la guidance
            </Button>
            <Button onClick={onAcknowledge} disabled={pending}>
              {pending ? <Loader2 className="animate-spin" /> : <Check />}
              Démarrer le traitement
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-4">
          <div>
            <p className="text-sm font-semibold text-foreground">Étape 2 · Résoudre le conflit</p>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Le conflit est pris en charge. Choisissez la décision qui le clôture.
            </p>
            {recommended && (
              <p className="mt-1.5 text-sm font-medium text-emerald-700">
                Recommandation chargée : appliquez-la ou saisissez votre propre décision.
              </p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" onClick={onGuidance}>
              <Sparkles /> Recommandation
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                onEdit(true);
                if (!expanded) onToggle();
              }}
            >
              <Edit3 /> Décision manuelle
            </Button>
            <Button
              disabled={pending}
              onClick={() =>
                onResolve({
                  resolution_method: strategy,
                  resolution_notes: `Stratégie recommandée appliquée : ${strategy}`,
                  requires_approval: isCritical,
                })
              }
            >
              {pending ? <Loader2 className="animate-spin" /> : <CheckCircle2 />}
              Résoudre avec la recommandation
            </Button>
          </div>
        </div>
      )}
    </article>
  );
}
