import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronUp,
  FileSearch,
  FileSpreadsheet,
  FileText,
  Folder,
  LoaderCircle,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
} from "lucide-react";
import { PageHeader, JourneySteps } from "@/components/app/PageHeader";
import { Stepper, type StepperStep } from "@/components/app/Stepper";
import { ConfirmDialog } from "@/components/app/ConfirmDialog";
import { PageBody, Panel, fieldClass } from "@/components/app/kit";
import { Button } from "@/components/ui/button";
import { RuleReview } from "@/components/RuleReview";
import { DataComparison } from "@/components/DataComparison";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  apiClient,
  type PreviewValidationError,
  type CleaningComparison,
  type CleaningJobDetail,
  type CleaningJobResponse,
  type CleaningPreviewResponse,
  type CleaningSuggestion,
  type DataSourceDetail,
  type ImportTemplate,
  type IngestionJob,
  type IngestionPreviewResponse,
  type SheetRelation,
  type RelationSuggestion,
  type JoinedViewResponse,
  handleApiError,
} from "@/lib/api";
import { toast } from "@/lib/toast";

export const Route = createFileRoute("/app/import")({
  beforeLoad: async () => {
    const { requireRoleAccess } = await import("@/lib/rbac");
    await requireRoleAccess("write:data");
  },
  validateSearch: (search: Record<string, unknown>) => ({
    sourceId: typeof search.sourceId === "string" ? Number(search.sourceId) || undefined : typeof search.sourceId === "number" ? search.sourceId : undefined,
    cleaningJobId:
      typeof search.cleaningJobId === "string"
        ? Number(search.cleaningJobId) || undefined
        : typeof search.cleaningJobId === "number"
          ? search.cleaningJobId
          : undefined,
    step: typeof search.step === "string" ? Number(search.step) || undefined : typeof search.step === "number" ? search.step : undefined,
  }),
  component: ImportPage,
  head: () => ({ meta: [{ title: "Importer données — DécisioBI" }] }),
});

const Card = Panel;

const STEPPER_STEPS: StepperStep<string>[] = [
  { key: "0", label: "Sélection", description: "Fichier source" },
  { key: "1", label: "Aperçu", description: "Structure brute" },
  { key: "2", label: "Relations", description: "Liaisons multi-feuilles" },
  { key: "3", label: "Nettoyage", description: "Règles & assainissement" },
  { key: "4", label: "Validation", description: "Diff avant / après" },
];

const STEPS = ["Sélection", "Aperçu", "Relations", "Nettoyage", "Validation"];
const IMPORT_FLOW_STORAGE_KEY = "decisio.import.flow";
const IMPORT_HISTORY_STORAGE_KEY = "decisio.import.history";
const IMPORT_HANDOFF_STORAGE_KEY = "decisio.import.handoff";
const PREVIEW_ROW_FETCH_LIMIT = 100;

type ImportOptions = {
  headers: boolean;
  encoding: string;
  delimiter: string;
  templateId: string;
};

const DEFAULT_OPTIONS: ImportOptions = {
  headers: true,
  encoding: "utf-8",
  delimiter: ",",
  templateId: "",
};

type ImportFlowSnapshot = {
  step: number;
  sourceId?: number | null;
  cleaningJobId?: number | null;
};

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function inferSourceType(fileName: string): "csv" | "excel" | "json" {
  const normalized = fileName.toLowerCase();
  if (normalized.endsWith(".csv")) return "csv";
  if (normalized.endsWith(".json")) return "json";
  return "excel";
}

function buildImportFormData(file: File, options: ImportOptions) {
  const form = new FormData();
  form.append("file", file);
  form.append("name", file.name);
  form.append("source_type", inferSourceType(file.name));
  form.append("delimiter", options.delimiter);
  form.append("encoding", options.encoding);
  form.append("has_header", String(options.headers));
  form.append("retention_days", "90");
  form.append("strict_validation", "false");
  if (options.templateId) {
    form.append("template_id", options.templateId);
  }
  return form;
}

function renderCellValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number" && Number.isNaN(value)) return "—";
  if (typeof value === "string" && value.trim().toLowerCase() === "nan") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function loadStoredFlow(): ImportFlowSnapshot | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(IMPORT_FLOW_STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ImportFlowSnapshot;
  } catch {
    return null;
  }
}

function storeFlow(snapshot: ImportFlowSnapshot | null) {
  if (typeof window === "undefined") return;
  if (!snapshot) {
    window.localStorage.removeItem(IMPORT_FLOW_STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(IMPORT_FLOW_STORAGE_KEY, JSON.stringify(snapshot));
}

function loadStoredImportHistory(): DataSourceDetail[] {
  if (typeof window === "undefined") return [];
  const raw = window.localStorage.getItem(IMPORT_HISTORY_STORAGE_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return (parsed as DataSourceDetail[]).filter((item) => !item.is_archived);
  } catch {
    return [];
  }
}

function mergeSourceHistory(primary: DataSourceDetail[], secondary: DataSourceDetail[]) {
  const merged = new Map<number, DataSourceDetail>();
  [...primary, ...secondary].forEach((item) => {
    if (!item?.id) return;
    merged.set(item.id, { ...(merged.get(item.id) || {}), ...item });
  });
  return Array.from(merged.values()).sort((left, right) => {
    const leftDate = left.created_at ? new Date(left.created_at).getTime() : 0;
    const rightDate = right.created_at ? new Date(right.created_at).getTime() : 0;
    return rightDate - leftDate;
  });
}

function extractSourcesFromJobs(jobs: IngestionJob[]) {
  return jobs
    .map((job) => job.source_detail)
    .filter((item): item is DataSourceDetail => Boolean(item && item.id && !item.is_archived));
}

function storeImportHistory(sources: DataSourceDetail[]) {
  if (typeof window === "undefined") return;
  const sanitized = sources.map((s) => sanitizeSourceForHistory(s));
  const normalized = mergeSourceHistory(sanitized, []).slice(0, 20);
  window.localStorage.setItem(IMPORT_HISTORY_STORAGE_KEY, JSON.stringify(normalized));
}

function sanitizeSourceForHistory(source: DataSourceDetail) {
  const copy: any = { ...(source || {}) };
  // Remove any transient cleaning UI state or decisions before persisting
  delete copy.selectedQuasiEmpty;
  delete copy.selectedUnmapped;
  delete copy.cleaningSelections;
  delete copy.decision_overrides;
  // sanitize metadata keys that may contain cleaning-time decisions
  if (copy.metadata && typeof copy.metadata === 'object') {
    const meta = { ...(copy.metadata || {}) };
    delete meta.cleaning_choices;
    delete meta.decision_overrides;
    delete meta.execution_context;
    delete meta.preview_decisions;
    copy.metadata = meta;
  }
  return copy as DataSourceDetail;
}

function StepPill({ active, done, label, index, onClick }: { active: boolean; done: boolean; label: string; index: number; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex flex-1 items-center gap-2 whitespace-nowrap rounded-xl px-4 py-2.5 text-sm font-medium transition ${
        active ? "bg-primary text-primary-foreground" : done ? "bg-success/10 text-success" : "text-muted-foreground hover:bg-secondary"
      }`}
    >
      <span
        className={`grid h-5 w-5 place-items-center rounded-full text-[11px] font-semibold ${
          active ? "bg-white/20 text-white" : done ? "bg-success text-white" : "bg-secondary text-foreground"
        }`}
      >
        {done ? <Check className="h-3 w-3" /> : index + 1}
      </span>
      {label}
    </button>
  );
}

function ImportPage() {
  const fileRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate({ from: "/app/import" });
  const search = Route.useSearch();

  const [step, setStep] = useState(0);
  const [options, setOptions] = useState<ImportOptions>(DEFAULT_OPTIONS);
  const [, setTemplates] = useState<ImportTemplate[]>([]);
  const [recentSources, setRecentSources] = useState<DataSourceDetail[]>([]);
  const [sourceToDelete, setSourceToDelete] = useState<DataSourceDetail | null>(null);
  const [deletingSource, setDeletingSource] = useState(false);
  const [currentRole, setCurrentRole] = useState<string | null>(null);

  function extractRoleFromProfile(profile: any): string | null {
    if (!profile) return null;
    const maybe = profile?.profile?.role || profile?.role || profile?.profile?.role_display || profile?.role_display || null;
    return typeof maybe === "string" ? maybe.toLowerCase() : null;
  }

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [importPreview, setImportPreview] = useState<IngestionPreviewResponse | null>(null);
  const [source, setSource] = useState<DataSourceDetail | null>(null);
  const [cleaningSuggestion, setCleaningSuggestion] = useState<CleaningSuggestion | null>(null);
  const [cleaningPreview, setCleaningPreview] = useState<CleaningPreviewResponse | null>(null);
  const [cleaningJob, setCleaningJob] = useState<CleaningJobResponse | null>(null);
  const [cleaningJobDetail, setCleaningJobDetail] = useState<CleaningJobDetail | null>(null);
  const [cleaningJobs, setCleaningJobs] = useState<CleaningJobResponse[]>([]);
  const [comparison, setComparison] = useState<CleaningComparison | null>(null);
  const [validationNotes, setValidationNotes] = useState("");
  const [validationConfirmed, setValidationConfirmed] = useState(false);

  const [previewLoading, setPreviewLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [cleaningLoading, setCleaningLoading] = useState(false);
  const [selectedQuasiEmpty, setSelectedQuasiEmpty] = useState<string[]>([]);
  const [selectedUnmapped, setSelectedUnmapped] = useState<string[]>([]);
  const [selectedSparseRows, setSelectedSparseRows] = useState<number[]>([]);
  const [applyingCleaning, setApplyingCleaning] = useState(false);
  const [validating, setValidating] = useState(false);
  const [previewRowLimit, setPreviewRowLimit] = useState<number>(20);
  const [activeSheet, setActiveSheet] = useState<string>("");
  const [historyOpen, setHistoryOpen] = useState(true);
  const [previewOpen, setPreviewOpen] = useState(true);
  const [historyQuery, setHistoryQuery] = useState("");
  const [historyStatusFilter, setHistoryStatusFilter] = useState<"all" | "completed" | "processing" | "failed">("all");
  const [historyVisibleCount, setHistoryVisibleCount] = useState(6);
  const [relations, setRelations] = useState<SheetRelation[]>([]);
  const [relationSuggestions, setRelationSuggestions] = useState<RelationSuggestion[]>([]);
  const [relationLoading, setRelationLoading] = useState(false);
  const [joinedView, setJoinedView] = useState<JoinedViewResponse | null>(null);
  const [showJoinedView, setShowJoinedView] = useState(false);
  const [showManualForm, setShowManualForm] = useState(false);
  const [manualFromSheet, setManualFromSheet] = useState("");
  const [manualFromColumn, setManualFromColumn] = useState("");
  const [manualToSheet, setManualToSheet] = useState("");
  const [manualToColumn, setManualToColumn] = useState("");
  const [manualRelationName, setManualRelationName] = useState("");
  const [structuralRun, setStructuralRun] = useState<any>(null);
  const [structuralPlan, setStructuralPlan] = useState<any>(null);
  const [ruleReviewPipelineId, setRuleReviewPipelineId] = useState<number | null>(null);
  const [cleaningJobAfterReview, setCleaningJobAfterReview] = useState<any>(null);
  const canWriteData = ["admin", "analyst"].includes((currentRole || "").toLowerCase());

  useEffect(() => {
    if (step === 3 && source && !structuralPlan && !structuralRun) {
      void triggerStructuralDetection();
    }
  }, [step, source?.id]);

  const persistFlow = (snapshot: ImportFlowSnapshot | null) => {
    storeFlow(snapshot);
    void navigate({
      search: {
        sourceId: snapshot?.sourceId || undefined,
        cleaningJobId: snapshot?.cleaningJobId || undefined,
        step: snapshot?.step || undefined,
      },
      replace: true,
    });
  };

  useEffect(() => {
    let cancelled = false;

    const loadBootstrap = async () => {
      const localHistory = loadStoredImportHistory();
      if (!cancelled && localHistory.length) {
        setRecentSources(localHistory);
      }

      // Fetch profile first so UI can determine role even if other endpoints fail
      let profile: any = null;
      try {
        profile = await apiClient.getProfile();
        setCurrentRole(extractRoleFromProfile(profile));
      } catch (err) {
        // Non bloquant: on continue sans rôle (UI restera en lecture seule)
        console.warn("Could not load profile during bootstrap:", err);
      }

      let mergedSources: DataSourceDetail[] = [];

      try {
        const [loadedTemplates, loadedSources, loadedJobs, loadedCleaningJobs] = await Promise.all([
          apiClient.getImportTemplates(),
          apiClient.listDataSources(),
          apiClient.listIngestionJobs(),
          apiClient.getCleaningJobs({ page_size: 200 }),
        ]);
        if (cancelled) return;
        setTemplates(loadedTemplates);
        setCleaningJobs(loadedCleaningJobs.results || []);
        const jobSources = extractSourcesFromJobs(loadedJobs);
        mergedSources = mergeSourceHistory(loadedSources, mergeSourceHistory(jobSources, localHistory));
        setRecentSources(mergedSources);
        storeImportHistory(mergedSources);
      } catch (error) {
        if (cancelled) return;
        toast("Impossible de charger le module d'import", {
          description: handleApiError(error, "Le backend d'import n'a pas répondu."),
          variant: "error",
        });
      }

      const storedFlow = loadStoredFlow();
      const activeFlow: ImportFlowSnapshot | null =
        search.sourceId || search.cleaningJobId || search.step
          ? {
              sourceId: search.sourceId ?? null,
              cleaningJobId: search.cleaningJobId ?? null,
              step: search.step ?? (search.cleaningJobId ? 3 : search.sourceId ? 2 : 0),
            }
          : storedFlow;

      if (activeFlow?.sourceId) {
        const matchingSource = mergedSources.find((item) => item.id === activeFlow.sourceId);
        if (matchingSource) {
          try {
            await resumeSource(matchingSource, activeFlow);
          } catch (err) {
            // Show error but don't prevent UI from rendering role
            toast("Impossible de reprendre cette source", {
              description: handleApiError(err, "Le backend n'a pas pu renvoyer l'aperçu de cette source."),
              variant: "error",
            });
          }
        }
      }
    };

    loadBootstrap();

    return () => {
      cancelled = true;
    };
  }, []);

  const refreshRecentSources = async () => {
    try {
      const [loadedCleaningJobs, loadedSources, loadedJobs] = await Promise.all([
        apiClient.getCleaningJobs({ page_size: 200 }),
        apiClient.listDataSources(),
        apiClient.listIngestionJobs(),
      ]);
      setCleaningJobs(loadedCleaningJobs.results || []);
      const jobSources = extractSourcesFromJobs(loadedJobs);
      const mergedSources = mergeSourceHistory(loadedSources, mergeSourceHistory(jobSources, loadStoredImportHistory()));
      setRecentSources(mergedSources);
      storeImportHistory(mergedSources);
    } catch {
      // Non bloquant pour le flux principal.
    }
  };

  const buildPreviewFromSource = async (dataSource: DataSourceDetail) => {
    const sheets = dataSource.sheets || [];
    const isMultiSheet = sheets.length > 1;

    if (!isMultiSheet) {
      const rawData = await apiClient.getSourceRawData(dataSource.id, 1, PREVIEW_ROW_FETCH_LIMIT);
      const rawRows = Array.isArray(rawData.results) ? rawData.results : [];
      const rows = rawRows.map((row: any) => row.data);
      const columnSet = new Set<string>();
      rows.forEach((row: Record<string, unknown>) => {
        Object.keys(row || {}).forEach((key) => columnSet.add(key));
      });
      const columns = Array.from(columnSet);

      return {
        filename: dataSource.name,
        source_type: dataSource.source_type,
        delimiter: dataSource.delimiter || options.delimiter,
        encoding: dataSource.encoding || options.encoding,
        checksum_md5: dataSource.checksum_md5 || "",
        file_size_bytes: dataSource.file_size_bytes || 0,
        row_count: dataSource.row_count,
        column_count: dataSource.column_count,
        rows,
        columns,
        metadata: dataSource.metadata || {},
        validation_errors: dataSource.validation_errors || [],
        row_validation_results: rawRows.map((row: any) => ({
          row_number: row.row_number,
          data: row.data,
          status: row.validation_status,
          messages: (row.validation_messages || []).map((message: any) => ({
            code: String(message.code || "validation"),
            message: String(message.message || message.detail || "Validation"),
          })),
        })),
        sample_rows: rawRows.map((row: any) => ({
          row_number: row.row_number,
          data: row.data,
          status: row.validation_status,
          messages: (row.validation_messages || []).map((message: any) => ({
            code: String(message.code || "validation"),
            message: String(message.message || message.detail || "Validation"),
          })),
        })),
        can_import: dataSource.status !== "failed",
        multi_sheet: false,
        sheet_count: 1,
        sheets: [],
      } satisfies IngestionPreviewResponse;
    }

    // Multi-sheet: fetch raw data per sheet
    const sheetPreviews = await Promise.all(
      sheets.map(async (sheet) => {
        const rawData = await apiClient.getSourceRawDataBySheet(dataSource.id, sheet.sheet_name, 1, PREVIEW_ROW_FETCH_LIMIT);
        const rawRows = Array.isArray(rawData.results) ? rawData.results : [];
        const rows = rawRows.map((row: any) => row.data);
        const columnSet = new Set<string>();
        rows.forEach((row: Record<string, unknown>) => {
          Object.keys(row || {}).forEach((key) => columnSet.add(key));
        });
        return {
          sheet_name: sheet.sheet_name,
          row_count: sheet.row_count,
          column_count: sheet.column_count,
          columns: sheet.column_names || Array.from(columnSet),
          rows,
          quality_score: sheet.quality_score,
          content_type: sheet.content_type,
          validation_errors: [],
          row_validation_results: rawRows.map((row: any) => ({
            row_number: row.row_number,
            data: row.data,
            status: row.validation_status,
            messages: (row.validation_messages || []).map((message: any) => ({
              code: String(message.code || "validation"),
              message: String(message.message || message.detail || "Validation"),
            })),
          })),
        };
      }),
    );

    // Merge all columns for the flat rows/columns (fallback)
    const allColumns = new Set<string>();
    const allRows: Record<string, unknown>[] = [];
    sheetPreviews.forEach((sp) => {
      sp.columns.forEach((c) => allColumns.add(c));
      allRows.push(...sp.rows);
    });

    return {
      filename: dataSource.name,
      source_type: dataSource.source_type,
      delimiter: dataSource.delimiter || options.delimiter,
      encoding: dataSource.encoding || options.encoding,
      checksum_md5: dataSource.checksum_md5 || "",
      file_size_bytes: dataSource.file_size_bytes || 0,
      row_count: dataSource.row_count,
      column_count: dataSource.column_count,
      rows: allRows,
      columns: Array.from(allColumns),
      metadata: dataSource.metadata || {},
      validation_errors: dataSource.validation_errors || [],
      row_validation_results: sheetPreviews.flatMap((sp) => sp.row_validation_results),
      can_import: dataSource.status !== "failed",
      multi_sheet: true,
      sheet_count: sheets.length,
      sheets: sheetPreviews,
    } satisfies IngestionPreviewResponse;
  };

  const handleDeleteSource = (item: DataSourceDetail) => {
    if (!canWriteData) return;
    setSourceToDelete(item);
  };

  const confirmDeleteSource = async () => {
    if (!sourceToDelete || !canWriteData) return;
    setDeletingSource(true);
    try {
      await apiClient.deleteSource(sourceToDelete.id);
      setRecentSources((prev) => {
        const updated = prev.filter((s) => s.id !== sourceToDelete.id);
        storeImportHistory(updated);
        return updated;
      });
      if (source?.id === sourceToDelete.id) {
        setSource(null);
        setImportPreview(null);
        setStep(0);
        persistFlow(null);
      }
      toast("Source supprimée", {
        description: `${sourceToDelete.name} a été supprimée.`,
        variant: "success",
      });
      setSourceToDelete(null);
    } catch (error) {
      toast("Suppression échouée", {
        description: handleApiError(error, "Impossible de supprimer cette source."),
        variant: "error",
      });
    } finally {
      setDeletingSource(false);
    }
  };

  const resumeSource = async (dataSource: DataSourceDetail, snapshot?: ImportFlowSnapshot | null) => {
    setPreviewLoading(true);
    setCleaningSuggestion(null);
    setCleaningPreview(null);
    setCleaningJob(null);
    setCleaningJobDetail(null);
    setComparison(null);
    setValidationNotes("");
    setValidationConfirmed(false);
    setSelectedFile(null);
    setStructuralPlan(null);
    setStructuralRun(null);

    // Always fetch full detail to get sheets[] populated
    let fullSource = dataSource;
    try {
      fullSource = await apiClient.getDataSource(dataSource.id);
    } catch {
      // fallback to the lightweight object
    }
    setSource(fullSource);
    const mergedHistory = mergeSourceHistory([fullSource], loadStoredImportHistory());
    setRecentSources(mergedHistory);
    storeImportHistory(mergedHistory);

    try {
      const preview = await buildPreviewFromSource(fullSource);
      setImportPreview(preview);
      // Adjust the preview row limit to available sample rows returned by backend
      try {
        const available = (preview?.row_validation_results || []).length || 0;
        if (available > 0 && previewRowLimit > available) {
          setPreviewRowLimit(available);
        }
      } catch {
        // ignore
      }
      setStep(1);
      persistFlow({
        step: snapshot?.step ?? 1,
        sourceId: fullSource.id,
        cleaningJobId: snapshot?.cleaningJobId ?? null,
      });
      toast("Source chargée depuis le backend", {
        description: `${fullSource.name} a été reprise avec son aperçu stocké.`,
        variant: "success",
      });
      if (snapshot?.cleaningJobId && (snapshot.step ?? 0) >= 4) {
        setStep(4);
        await loadValidationStage(snapshot.cleaningJobId);
      } else if ((snapshot?.step ?? 0) >= 3) {
        await loadCleaningStage(fullSource);
      } else {
        await loadRelationsStage(fullSource);
      }
    } catch (error) {
      toast("Impossible de reprendre cette source", {
        description: handleApiError(error, "Le backend n'a pas pu renvoyer l'aperçu de cette source."),
        variant: "error",
      });
    } finally {
      setPreviewLoading(false);
    }
  };

  const handlePreviewFile = async (file: File) => {
    setSelectedFile(file);
    setImportPreview(null);
    setActiveSheet("");
    setSource(null);
    setCleaningSuggestion(null);
    setCleaningPreview(null);
    setCleaningJob(null);
    setCleaningJobDetail(null);
    setComparison(null);
    setValidationNotes("");
    setValidationConfirmed(false);
    persistFlow(null);
    setStep(1);
    setPreviewLoading(true);

    try {
      const preview = await apiClient.previewImport(buildImportFormData(file, options));
      setImportPreview(preview);
      const available = (preview?.row_validation_results || []).length || 0;
      if (available > 0) {
        setPreviewRowLimit(Math.min(20, available));
      }
      toast("Aperçu du fichier prêt", {
        description: `${preview.row_count} lignes détectées et ${preview.column_count} colonnes reconnues.`,
        variant: "success",
      });
    } catch (error) {
      toast("Aperçu impossible", {
        description: handleApiError(error, "Le fichier n'a pas pu être analysé."),
        variant: "error",
      });
    } finally {
      setPreviewLoading(false);
    }
  };

  const onFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    if (files.length > 1) {
      toast("Un fichier à la fois", {
        description: `Le flux linéaire traite d'abord ${files[0].name}. Les autres pourront être importés ensuite.`,
        variant: "warning",
      });
    }
    await handlePreviewFile(files[0]);
  };

  const waitForIngestionCompletion = async (jobId: number) => {
    for (let attempt = 0; attempt < 90; attempt += 1) {
      const job = await apiClient.getIngestionJob(jobId);
      if (job.status === "completed" && job.source_detail) {
        return job;
      }
      if (job.status === "failed") {
        throw new Error(job.error_message || "L'import a échoué.");
      }
      await sleep(1500);
    }
    throw new Error("L'import prend trop de temps à répondre.");
  };

  const loadCleaningStage = async (dataSource: DataSourceDetail) => {
    setCleaningLoading(true);
    setStep(3);
    persistFlow({ step: 3, sourceId: dataSource.id, cleaningJobId: null });
    try {
      const suggestions = await apiClient.getCleaningSuggestions(dataSource.id);
      setCleaningSuggestion(suggestions);

      const preview = await apiClient.previewCleaning(dataSource.id, {
        pipeline_id: suggestions.recommended_pipeline?.id,
        include_all_auto_rules: true,
        rule_ids: [],
        decision_overrides: [],
      });
      setCleaningPreview(preview);
      // initialize selectable lists from preview
      try {
        const quasi = (preview?.cleaning_report?.metadata?.structural_analysis?.quasi_empty_columns || []) as Array<any>;
        setSelectedQuasiEmpty(quasi.map((q) => String(q.column)).filter(Boolean));
      } catch {
        setSelectedQuasiEmpty([]);
      }
      try {
        const unmapped = (preview?.cleaning_report?.mapping?.colonnes_non_mappees || []) as string[];
        setSelectedUnmapped(unmapped || []);
      } catch {
        setSelectedUnmapped([]);
      }
      try {
        const sparseRows = (preview?.cleaning_report?.metadata?.structural_analysis?.sparse_rows || []) as Array<any>;
        setSelectedSparseRows(
          sparseRows
            .map((item) => Number(item.row_number))
            .filter((value) => Number.isFinite(value)),
        );
      } catch {
        setSelectedSparseRows([]);
      }
      toast("Analyse de nettoyage prête", {
        description: `${preview.summary.rows_affected ?? 0} ligne(s) peuvent être ajustées avant validation.`,
        variant: "success",
      });
    } catch (error) {
      toast("Nettoyage non préparé", {
        description: handleApiError(error, "Le moteur de nettoyage n'a pas pu préparer l'analyse."),
        variant: "error",
      });
    } finally {
      setCleaningLoading(false);
    }
  };

  const triggerStructuralDetection = async () => {
    if (!source) return false;
    try {
      const result = await apiClient.structuralDetect(source.id, {});
      setStructuralRun(result);
      setStructuralPlan(result.reconstruction_plan);
      toast("Detection structurale terminee", {
        description: `Confiance: ${Math.round(result.confidence_score * 100)}%`,
        variant: "success",
      });
      return true;
    } catch (error: any) {
      console.error("Structural detection failed:", error);
      toast("Detection structurelle echouee", {
        description: error?.message || "Erreur inconnue. Verifiez que le fichier existe toujours.",
        variant: "error",
      });
      return false;
    }
  };

  const handleImport = async () => {
    if (!selectedFile) {
      toast("Aucun fichier", { description: "Sélectionne d'abord un fichier à importer.", variant: "warning" });
      return;
    }
    if (!canWriteData) {
      toast("Import non autorisé", {
        description: "Ton rôle actuel permet l'aperçu, mais pas l'import réel. Il faut être analyste ou admin.",
        variant: "warning",
      });
      return;
    }

    setUploading(true);
    try {
      const job = await apiClient.uploadImportAsync(buildImportFormData(selectedFile, options));
      toast("Import lancé", {
        description: "Le backend enregistre la source et prépare les données brutes.",
        variant: "info",
      });

      const completedJob = await waitForIngestionCompletion(job.id);
      if (!completedJob.source_detail) {
        throw new Error("La source importée n'a pas été retrouvée après traitement.");
      }

      setSource(completedJob.source_detail);
      setStructuralPlan(null);
      setStructuralRun(null);
      const mergedHistory = mergeSourceHistory([completedJob.source_detail], loadStoredImportHistory());
      setRecentSources(mergedHistory);
      storeImportHistory(mergedHistory);
      persistFlow({ step: 2, sourceId: completedJob.source_detail.id, cleaningJobId: null });
      await refreshRecentSources();
      toast("Import terminé", {
        description: `${completedJob.source_detail.name} est prêt.`,
        variant: "success",
      });
      try {
        await loadRelationsStage(completedJob.source_detail);
      } catch (relError) {
        console.warn("Relations stage failed after successful import:", relError);
        setStep(2);
      }
    } catch (error) {
      toast("Import échoué", {
        description: handleApiError(error, "Le fichier n'a pas pu être importé."),
        variant: "error",
      });
    } finally {
      setCleaningLoading(false);
    }
  };

  const loadRelationsStage = async (dataSource: DataSourceDetail) => {
    setRelationLoading(true);
    setStep(2);
    persistFlow({ step: 2, sourceId: dataSource.id, cleaningJobId: null });
    try {
      const [existingRelations, suggestions] = await Promise.all([
        apiClient.getSheetRelations(dataSource.id),
        apiClient.suggestRelations(dataSource.id),
      ]);
      setRelations(existingRelations);
      setRelationSuggestions(suggestions.suggestions || []);
    } catch (error) {
      console.warn("Relations loading failed:", error);
      setRelations([]);
      setRelationSuggestions([]);
    } finally {
      setRelationLoading(false);
    }
  };

  const handleCreateRelation = async (suggestion: RelationSuggestion) => {
    if (!source) return;
    try {
      const created = await apiClient.createSheetRelation(source.id, {
        relation_name: `${suggestion.from_column}_to_${suggestion.to_column}`,
        from_sheet: suggestion.from_sheet,
        from_column: suggestion.from_column,
        to_sheet: suggestion.to_sheet,
        to_column: suggestion.to_column,
        join_type: "many_to_one",
      });
      setRelations((prev) => [...prev, created]);
      setRelationSuggestions((prev) =>
        prev.filter(
          (s) =>
            !(s.from_sheet === suggestion.from_sheet && s.from_column === suggestion.from_column && s.to_sheet === suggestion.to_sheet && s.to_column === suggestion.to_column),
        ),
      );
      toast("Lien créé", { description: `${suggestion.from_sheet}.${suggestion.from_column} → ${suggestion.to_sheet}.${suggestion.to_column}`, variant: "success" });
    } catch (error) {
      toast("Erreur", { description: handleApiError(error, "Impossible de créer le lien."), variant: "error" });
    }
  };

  const handleDeleteRelation = async (relationId: number) => {
    if (!source) return;
    try {
      await apiClient.deleteSheetRelation(source.id, relationId);
      setRelations((prev) => prev.filter((r) => r.id !== relationId));
      toast("Lien supprimé", { variant: "success" });
    } catch (error) {
      toast("Erreur", { description: handleApiError(error, "Impossible de supprimer le lien."), variant: "error" });
    }
  };

  const handleCreateManualRelation = async () => {
    if (!source || !manualFromSheet || !manualFromColumn || !manualToSheet || !manualToColumn) {
      toast("Champs requis", { description: "Remplis tous les champs du formulaire.", variant: "warning" });
      return;
    }
    try {
      const name = manualRelationName || `${manualFromColumn}_to_${manualToColumn}`;
      const created = await apiClient.createSheetRelation(source.id, {
        relation_name: name,
        from_sheet: manualFromSheet,
        from_column: manualFromColumn,
        to_sheet: manualToSheet,
        to_column: manualToColumn,
        join_type: "many_to_one",
      });
      setRelations((prev) => [...prev, created]);
      setShowManualForm(false);
      setManualFromSheet("");
      setManualFromColumn("");
      setManualToSheet("");
      setManualToColumn("");
      setManualRelationName("");
      toast("Lien créé", { description: `${manualFromSheet}.${manualFromColumn} → ${manualToSheet}.${manualToColumn}`, variant: "success" });
    } catch (error) {
      toast("Erreur", { description: handleApiError(error, "Impossible de créer le lien."), variant: "error" });
    }
  };

  const handleLoadJoinedView = async () => {
    if (!source) return;
    try {
      const result = await apiClient.getJoinedView(source.id, {
        relation_ids: relations.map((r) => r.id),
      });
      setJoinedView(result);
      setShowJoinedView(true);
    } catch (error) {
      toast("Erreur", { description: handleApiError(error, "Impossible de charger l'aperçu croisé."), variant: "error" });
    }
  };


  const waitForCleaningCompletion = async (jobId: number) => {
    for (let attempt = 0; attempt < 120; attempt += 1) {
      const detail = await apiClient.getCleaningJobDetail(jobId);
      if (detail.job.status === "completed") {
        return detail;
      }
      if (detail.job.status === "failed") {
        throw new Error("Le nettoyage a échoué.");
      }
      await sleep(1500);
    }
    throw new Error("Le nettoyage prend trop de temps à répondre.");
  };

  const loadValidationStage = async (jobId: number) => {
    setStep(4);
    if (source) {
      persistFlow({ step: 4, sourceId: source.id, cleaningJobId: jobId });
    }
    const [detail, loadedComparison] = await Promise.all([
      apiClient.getCleaningJobDetail(jobId),
      apiClient.getCleaningComparison(jobId),
    ]);
    setCleaningJobDetail(detail);
    setComparison(loadedComparison);
  };

  const handleApplyCleaning = async () => {
    if (!source || (!cleaningSuggestion && !structuralPlan)) {
      toast("Nettoyage indisponible", {
        description: "La source importée n'est pas encore prête pour le nettoyage.",
        variant: "warning",
      });
      return;
    }
    if (!canWriteData) {
      toast("Nettoyage non autorisé", {
        description: "Ton rôle actuel permet la lecture, mais pas l'application du nettoyage. Il faut être analyste ou admin.",
        variant: "warning",
      });
      return;
    }

    setApplyingCleaning(true);
    try {
      let pipelineId = cleaningSuggestion?.recommended_pipeline?.id ?? null;

      if (structuralPlan && source) {
        toast("Règles structurelles", {
          description: "Création des règles de restructuration (unpivot, etc.)…",
          variant: "info",
        });
        const structuralResult = await apiClient.applyPlan(source.id, structuralPlan, false);
        if (structuralResult?.pipeline_id) {
          pipelineId = structuralResult.pipeline_id;
        }
      }

      const decision_overrides: any[] = [];
      selectedQuasiEmpty.forEach((col) => decision_overrides.push({ action: 'drop_quasi_empty_column', column: col, decision: 'apply' }));
      selectedUnmapped.forEach((col) => decision_overrides.push({ action: 'drop_unmapped_column', column: col, decision: 'apply' }));
      selectedSparseRows.forEach((rowNumber) => decision_overrides.push({ action: 'drop_sparse_row', row_number: rowNumber, decision: 'apply' }));

      const job = await apiClient.applyCleaningAsync(source.id, {
        pipeline_id: pipelineId,
        include_all_auto_rules: true,
        rule_ids: [],
        decision_overrides,
      });
      setCleaningJob(job);
      setStructuralPlan(null);
      setStructuralRun(null);
      persistFlow({ step: 3, sourceId: source.id, cleaningJobId: job.id });
      toast("Nettoyage lancé", {
        description: structuralPlan
          ? "Les règles structurelles et générales sont en cours d'application."
          : "Les règles automatiques recommandées sont en cours d'application.",
        variant: "info",
      });

      const completedDetail = await waitForCleaningCompletion(job.id);
      await loadValidationStage(completedDetail.job.id);
      toast("Nettoyage terminé", {
        description: "Le résultat est prêt pour comparaison et validation.",
        variant: "success",
      });
    } catch (error) {
      toast("Nettoyage échoué", {
        description: handleApiError(error, "Le nettoyage n'a pas pu être appliqué."),
        variant: "error",
      });
    } finally {
      setApplyingCleaning(false);
    }
  };

  const applySelectedSuggestionsPreview = async () => {
    if (!source || !cleaningSuggestion) return;
    setCleaningLoading(true);
    try {
      const decision_overrides: any[] = [];
      selectedQuasiEmpty.forEach((col) => decision_overrides.push({ action: 'drop_quasi_empty_column', column: col, decision: 'apply' }));
      selectedUnmapped.forEach((col) => decision_overrides.push({ action: 'drop_unmapped_column', column: col, decision: 'apply' }));
      selectedSparseRows.forEach((rowNumber) => decision_overrides.push({ action: 'drop_sparse_row', row_number: rowNumber, decision: 'apply' }));

      const preview = await apiClient.previewCleaning(source.id, {
        pipeline_id: cleaningSuggestion.recommended_pipeline?.id,
        include_all_auto_rules: true,
        rule_ids: [],
        decision_overrides,
      });
      setCleaningPreview(preview);
      toast('Aperçu mis à jour', { description: "Les décisions sélectionnées ont été prises en compte dans l'aperçu.", variant: 'success' });
    } catch (err) {
      toast('Impossible d appliquer les suggestions', { description: handleApiError(err, "Le backend n'a pas pu appliquer les décisions."), variant: 'error' });
    } finally {
      setCleaningLoading(false);
    }
  };

  const handleValidate = async (isValidated: boolean) => {
    if (!cleaningJobDetail) return;
    setValidating(true);
    try {
      const result = await apiClient.validateCleaningJob(cleaningJobDetail.job.id, {
        is_validated: isValidated,
        validation_notes: validationNotes,
      });
      toast(isValidated ? "Résultat validé" : "Résultat remis en attente", {
        description: isValidated
          ? `${result.validated_rows} ligne(s) validée(s) pour la suite du processus.`
          : "Le nettoyage reste en attente de revue.",
        variant: isValidated ? "success" : "warning",
      });
      const refreshedDetail = await apiClient.getCleaningJobDetail(cleaningJobDetail.job.id);
      setCleaningJobDetail(refreshedDetail);
      if (isValidated) {
        setValidationConfirmed(true);
        const handoffSourceId = source?.id ?? cleaningJobDetail.job.source_id;
        if (typeof window !== "undefined") {
          window.localStorage.setItem(
            IMPORT_HANDOFF_STORAGE_KEY,
            JSON.stringify({
              sourceId: handoffSourceId,
              sourceName: source?.name ?? cleaningJobDetail.job.source_name,
              cleanedJobId: cleaningJobDetail.job.id,
              validatedAt: new Date().toISOString(),
            }),
          );
        }
        persistFlow(null);
      } else if (source) {
        setValidationConfirmed(false);
        persistFlow({ step: 3, sourceId: source.id, cleaningJobId: cleaningJobDetail.job.id });
      }
    } catch (error) {
      toast("Validation impossible", {
        description: handleApiError(error, "Le statut de validation n'a pas été enregistré."),
        variant: "error",
      });
    } finally {
      setValidating(false);
    }
  };

  const activeSheetData = importPreview?.multi_sheet && importPreview?.sheets
    ? importPreview.sheets.find(s => s.sheet_name === activeSheet) || importPreview.sheets[0]
    : null;

  const previewColumns = activeSheetData ? activeSheetData.columns : (importPreview?.columns || []);
  const previewRows =
    (activeSheetData ? activeSheetData.row_validation_results : importPreview?.row_validation_results)?.map((item) => ({
      row_number: item.row_number,
      data: item.data,
      status: item.status,
      messages: item.messages,
    })) || [];
  const visiblePreviewRows = previewRows.slice(0, previewRowLimit);
  const comparisonRows = comparison?.rows || [];
  const beforeStructureColumns = comparison?.before_columns || [];
  const beforeStructureRows = (comparison?.before_rows_preview || []) as Array<Record<string, any>>;
  const afterStructureColumns = comparison?.after_columns || [];
  const afterStructureRows = (comparison?.after_rows_preview || []) as Array<Record<string, any>>;
  const previewOrchestration = (cleaningPreview?.orchestration || cleaningPreview?.cleaning_report?.metadata?.orchestration || {}) as Record<string, any>;
  const previewCanonicalBuild = (cleaningPreview?.cleaning_report?.metadata?.canonical_build || {}) as Record<string, any>;
  const previewSemanticProfile = (previewCanonicalBuild?.semantic_profile || {}) as Record<string, any>;
  const structuralAnalysis = (cleaningPreview?.cleaning_report?.metadata?.structural_analysis || {}) as Record<string, any>;
  const quasiEmptyColumns = (structuralAnalysis.quasi_empty_columns || []) as Array<{ column: string; fill_rate: number }>;
  const sparseRows = (structuralAnalysis.sparse_rows || []) as Array<{ row_number: number; missing_rate: number }>;
  const unmappedColumns = ((cleaningPreview?.cleaning_report?.mapping?.colonnes_non_mappees || []) as string[]).filter(Boolean);
  const historyItems = mergeSourceHistory(recentSources, source ? [source] : []);
  const cleaningJobsBySource = useMemo(() => {
    const grouped = new Map<number, CleaningJobResponse[]>();
    cleaningJobs.forEach((job) => {
      const sourceId = job.source_id ?? job.source;
      if (!sourceId) return;
      const existing = grouped.get(sourceId) || [];
      existing.push(job);
      existing.sort((left, right) => {
        const leftDate = new Date(left.completed_at || left.created_at || 0).getTime();
        const rightDate = new Date(right.completed_at || right.created_at || 0).getTime();
        return rightDate - leftDate;
      });
      grouped.set(sourceId, existing);
    });
    return grouped;
  }, [cleaningJobs]);
  const getSourceJobs = (sourceId?: number | null) => (sourceId ? cleaningJobsBySource.get(sourceId) || [] : []);
  const getSourcePipelineSummary = (sourceId?: number | null) => {
    const jobs = getSourceJobs(sourceId);
    const latestJob = jobs[0] || null;
    const validatedJob = jobs.find((job) => job.is_fully_validated) || null;
    const completedJob = jobs.find((job) => job.status === "completed") || null;

    if (validatedJob) {
      return {
        stage: "validated",
        label: "Nettoyage validé",
        tone: "bg-emerald-50 text-emerald-700",
        actionLabel: "Continuer vers conflits",
        latestJob: validatedJob,
      };
    }
    if (completedJob) {
      return {
        stage: "pending_validation",
        label: "Validation en attente",
        tone: "bg-amber-50 text-amber-700",
        actionLabel: "Reprendre la validation",
        latestJob: completedJob,
      };
    }
    if (latestJob && (latestJob.status === "queued" || latestJob.status === "running" || latestJob.status === "pending")) {
      return {
        stage: "cleaning_running",
        label: "Nettoyage en cours",
        tone: "bg-sky-50 text-sky-700",
        actionLabel: "Suivre le nettoyage",
        latestJob,
      };
    }
    if (latestJob && latestJob.status === "failed") {
      return {
        stage: "cleaning_failed",
        label: "Nettoyage échoué",
        tone: "bg-rose-50 text-rose-700",
        actionLabel: "Relancer le nettoyage",
        latestJob,
      };
    }
    return {
      stage: "imported",
      label: "Importé",
      tone: "bg-slate-100 text-slate-700",
      actionLabel: "Lancer le nettoyage",
      latestJob: null,
    };
  };
  const filteredHistoryItems = historyItems.filter((item) => {
    const matchesQuery =
      !historyQuery.trim() ||
      item.name.toLowerCase().includes(historyQuery.trim().toLowerCase()) ||
      (item.source_type || "").toLowerCase().includes(historyQuery.trim().toLowerCase());
    const matchesStatus = historyStatusFilter === "all" || item.status === historyStatusFilter;
    return matchesQuery && matchesStatus;
  });
  const visibleHistoryItems = filteredHistoryItems.slice(0, historyVisibleCount);
  const hasMoreHistory = filteredHistoryItems.length > historyVisibleCount;

  const continueSourcePipeline = async (item: DataSourceDetail) => {
    const summary = getSourcePipelineSummary(item.id);
    if (summary.latestJob) {
      if (summary.stage === "validated") {
        toast("Version validée chargée", {
          description: "Le dernier nettoyage validé sert de base pour la détection des conflits.",
          variant: "success",
        });
        void navigate({ to: "/app/conflicts", search: { sourceId: item.id, source: undefined, cleaningJobId: undefined } });
        return;
      }
      if (summary.stage === "pending_validation" || summary.stage === "cleaning_running") {
        setSource(item);
        persistFlow({ step: 3, sourceId: item.id, cleaningJobId: summary.latestJob.id });
        await loadValidationStage(summary.latestJob.id);
        return;
      }
    }
    await resumeSource(item, { sourceId: item.id, step: 2, cleaningJobId: null });
  };

  return (
    <div>
      <input
        ref={fileRef}
        type="file"
        multiple
        accept=".xlsx,.xls,.csv,.json"
        className="hidden"
        onChange={(e) => void onFiles(e.target.files)}
      />

      <PageHeader
        title="Données & Importation"
        subtitle="Importation Excel, CSV ou JSON, aperçu brut, détection de liaisons, règles de nettoyage et validation des jeux de données."
        actions={
          <Button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={!canWriteData}
            className="gap-2"
          >
            <Upload className="h-4 w-4" /> Choisir un fichier
          </Button>
        }
      />

      <PageBody>
        <JourneySteps
          role={currentRole}
          current={step <= 1 ? "import" : step <= 3 ? "prepare" : "validate"}
        />
        <Card className="p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Historique</div>
              <h3 className="mt-2 font-display text-2xl font-semibold">Historique des imports</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Sources reellement enregistrees dans le backend. Tu peux reprendre un import existant sans reimporter le meme fichier.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setHistoryOpen((current) => !current)}
              className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-sm font-medium hover:bg-secondary"
            >
              {historyOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              {historyOpen ? "Réduire" : "Dérouler"}
            </button>
          </div>

          {historyOpen ? (
            <div className="mt-5 space-y-4">
              <div className="flex flex-wrap gap-3">
                <label className="flex min-w-[16rem] flex-1 items-center gap-2 rounded-full border border-border bg-card px-4 py-2.5 text-sm">
                  <Search className="h-4 w-4 text-muted-foreground" />
                  <input
                    value={historyQuery}
                    onChange={(e) => {
                      setHistoryQuery(e.target.value);
                      setHistoryVisibleCount(6);
                    }}
                    placeholder="Rechercher un fichier importé"
                    className="w-full bg-transparent text-foreground placeholder:text-muted-foreground focus:outline-none"
                  />
                </label>
                <select
                  value={historyStatusFilter}
                  onChange={(e) => {
                    setHistoryStatusFilter(e.target.value as "all" | "completed" | "processing" | "failed");
                    setHistoryVisibleCount(6);
                  }}
                  className="rounded-full border border-border bg-card px-4 py-2.5 text-sm font-medium text-foreground focus:border-primary focus:outline-none"
                >
                  <option value="all">Tous les statuts</option>
                  <option value="completed">Terminés</option>
                  <option value="processing">En cours</option>
                  <option value="failed">Échoués</option>
                </select>
              </div>

              <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
              {visibleHistoryItems.length ? (
                visibleHistoryItems.map((item) => (
                  <div
                    key={item.id}
                    className="rounded-2xl border border-border px-4 py-4 text-left transition hover:border-primary/40 hover:bg-secondary/20"
                  >
                    {(() => {
                      const pipeline = getSourcePipelineSummary(item.id);
                      return (
                        <>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-foreground">{item.name}</div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          {item.row_count} lignes · {item.column_count} colonnes
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          Importé le {item.created_at ? new Date(item.created_at).toLocaleString("fr-FR") : "—"}
                        </div>
                      </div>
                      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${pipeline.tone}`}>
                        {pipeline.label}
                      </span>
                    </div>

                    <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
                      <span>{item.source_type?.toUpperCase?.() || "SOURCE"}</span>
                      <span>{getSourceJobs(item.id).length} nettoyage(s)</span>
                    </div>

                    <div className="mt-2 text-xs text-muted-foreground">
                      {pipeline.stage === "validated"
                        ? "La dernière version validée sera réutilisée pour la suite du pipeline."
                        : pipeline.stage === "pending_validation"
                          ? "Un nettoyage terminé attend encore une validation humaine."
                          : pipeline.stage === "cleaning_running"
                            ? "Un nettoyage est déjà en cours sur cette source."
                            : pipeline.stage === "cleaning_failed"
                              ? "La dernière tentative de nettoyage a échoué."
                              : "Cette source est importée, mais pas encore nettoyée."}
                    </div>

                    <div className="mt-4 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => void resumeSource(item)}
                        className="rounded-full border border-border bg-card px-4 py-2 text-sm font-medium hover:bg-secondary"
                      >
                        Ouvrir
                      </button>
                      <button
                        type="button"
                        onClick={() => void continueSourcePipeline(item)}
                        className="inline-flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:brightness-110"
                      >
                        <RefreshCw className="h-3.5 w-3.5" />
                        {pipeline.actionLabel}
                      </button>
                      {canWriteData ? (
                        <button
                          type="button"
                          onClick={() => void handleDeleteSource(item)}
                          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-2 text-xs font-medium text-muted-foreground hover:border-rose-300 hover:bg-rose-50 hover:text-rose-700"
                          title="Supprimer cette source"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      ) : null}
                    </div>
                        </>
                      );
                    })()}
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">
                  {historyItems.length ? "Aucun import ne correspond au filtre actuel." : "Aucune source importée pour l'instant."}
                </p>
              )}
              </div>

              {hasMoreHistory ? (
                <div className="flex justify-center">
                  <button
                    type="button"
                    onClick={() => setHistoryVisibleCount((current) => current + 6)}
                    className="rounded-full border border-border bg-card px-5 py-2.5 text-sm font-medium hover:bg-secondary"
                  >
                    Voir plus
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}
        </Card>

        <Panel className="p-4">
          <Stepper
            steps={STEPPER_STEPS}
            current={String(step)}
            onStepClick={(k) => setStep(Number(k))}
          />
        </Panel>

        <div className="min-w-0 space-y-6">
            {(step === 0 || step === 1) && (
            <Card className="p-6">
              {step === 0 && !importPreview ? (
                <div
                  onClick={() => fileRef.current?.click()}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    void onFiles(e.dataTransfer.files);
                  }}
                  className="cursor-pointer rounded-2xl border-2 border-dashed border-primary/30 bg-primary/[0.04] p-8 text-center transition hover:bg-primary/[0.07]"
                >
                  <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-primary/10 text-primary-strong">
                    <Folder className="h-7 w-7" />
                  </div>
                  <h3 className="mt-5 font-display text-xl font-semibold text-primary-strong">Déposer un fichier</h3>
                  <p className="mt-1 text-sm text-muted-foreground">Excel, CSV ou export ERP. L'analyse démarre ensuite automatiquement.</p>
                  {!canWriteData ? (
                    <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                      Le compte courant est en lecture seule pour ce module. L'aperçu reste disponible, mais l'import réel et l'application du nettoyage demandent le rôle <span className="font-semibold">analyst</span> ou <span className="font-semibold">admin</span>.
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="flex flex-wrap items-start justify-between gap-4 rounded-2xl border border-border bg-secondary/20 px-5 py-4">
                  <div className="min-w-0">
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Fichier en cours</div>
                    <h3 className="mt-2 truncate font-display text-2xl font-semibold text-foreground">
                      {selectedFile?.name || importPreview?.filename || source?.name || "Source importée"}
                    </h3>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold">
                      {importPreview ? (
                        <>
                          <span className="rounded-full bg-primary/10 px-3 py-1 text-primary-strong">{importPreview.row_count} lignes</span>
                          <span className="rounded-full bg-emerald-100 px-3 py-1 text-emerald-700">{visiblePreviewRows.length} lignes chargées</span>
                        </>
                      ) : null}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={() => fileRef.current?.click()}
                      className="rounded-full bg-white px-5 py-2.5 text-sm font-medium text-foreground shadow-sm hover:bg-slate-50"
                    >
                      Changer de fichier
                    </button>
                    {step === 1 && importPreview ? (
                      <button
                        type="button"
                        disabled={!importPreview.can_import || uploading || !canWriteData}
                        onClick={() => void handleImport()}
                        className="rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:brightness-110 disabled:opacity-60"
                      >
                        {uploading ? "Import en cours…" : "Lancer l'import"}
                      </button>
                    ) : null}
                  </div>
                </div>
              )}
            </Card>
            )}

            {step === 1 && (
              <Card className="p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Aperçu</div>
                    <h3 className="mt-2 font-display text-2xl font-semibold">Aperçu du fichier brut</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Cette vue montre le fichier tel qu'il a été lu à l'import, avant toute correction.
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => setPreviewOpen((current) => !current)}
                      className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-sm font-medium hover:bg-secondary"
                    >
                      {previewOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      {previewOpen ? "Réduire" : "Dérouler"}
                    </button>
                    {importPreview ? (
                      <select
                        value={String(previewRowLimit)}
                        onChange={(e) => setPreviewRowLimit(Number(e.target.value))}
                        className="rounded-full border border-border bg-white px-4 py-2 text-sm font-medium text-foreground focus:border-primary focus:outline-none"
                      >
                        <option value="20" disabled={previewRows.length < 20}>20 lignes</option>
                        <option value="50" disabled={previewRows.length < 50}>50 lignes</option>
                        <option value="100" disabled={previewRows.length < 100}>100 lignes</option>
                      </select>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => selectedFile && void handlePreviewFile(selectedFile)}
                      disabled={!selectedFile || previewLoading}
                      className="rounded-full bg-slate-100 px-5 py-2.5 text-sm font-medium text-foreground hover:bg-slate-200 disabled:opacity-60"
                    >
                      Actualiser aperçu
                    </button>
                    {previewLoading ? <LoaderCircle className="h-5 w-5 animate-spin text-primary-strong" /> : null}
                  </div>
                </div>

                {previewOpen ? (
                  importPreview ? (
                  <div className="mt-5 space-y-5">
                    <div className="flex flex-wrap gap-3 text-sm font-semibold">
                      <span className="rounded-full bg-primary/10 px-4 py-2 text-primary-strong">{importPreview.row_count} lignes</span>
                      <span className="rounded-full bg-emerald-100 px-4 py-2 text-emerald-700">{visiblePreviewRows.length} lignes affichées</span>
                      <span className="rounded-full bg-slate-100 px-4 py-2 text-slate-700">{importPreview.column_count} colonnes</span>
                      {previewRows.length > 0 && previewRows.length < importPreview.row_count ? (
                        <span className="rounded-full bg-amber-50 px-3 py-1 text-amber-700">
                          Aperçu partiel : {previewRows.length} lignes disponibles sur {importPreview.row_count}
                        </span>
                      ) : null}
                    </div>

                    {importPreview.multi_sheet && importPreview.sheets && importPreview.sheets.length > 1 ? (
                      <div className="mt-3">
                        <Tabs value={activeSheet || importPreview.sheets[0]?.sheet_name} onValueChange={setActiveSheet}>
                          <TabsList className="flex-wrap h-auto gap-1 bg-transparent p-0">
                            {importPreview.sheets.map((sheet) => (
                              <TabsTrigger
                                key={sheet.sheet_name}
                                value={sheet.sheet_name}
                                className="rounded-full border border-border bg-white px-3 py-1.5 text-xs font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:border-primary"
                              >
                                <FileSpreadsheet className="mr-1.5 h-3 w-3" />
                                {sheet.sheet_name}
                                <span className="ml-1.5 rounded-full bg-black/5 px-1.5 py-0.5 text-[10px]">{sheet.row_count}</span>
                              </TabsTrigger>
                            ))}
                          </TabsList>
                        </Tabs>
                        <p className="mt-2 text-xs text-muted-foreground">
                          {importPreview.sheet_count} feuilles détectées — {activeSheetData?.content_type === 'tableau_indicateurs' ? 'tableau d\'indicateurs' : activeSheetData?.content_type === 'resume_ou_notes' ? 'résumé ou notes' : 'jeu de données structuré'}
                        </p>
                      </div>
                    ) : null}

                    <div className="flex flex-wrap gap-2 text-xs">
                      {(importPreview.validation_errors || []).map((issue: PreviewValidationError) => (
                        <span
                          key={`${issue.code}-${issue.message}`}
                          className={`rounded-full px-3 py-1 font-semibold ${
                            issue.severity === "error"
                              ? "bg-rose-50 text-rose-700"
                              : issue.severity === "warning"
                                ? "bg-amber-50 text-amber-700"
                                : "bg-sky-50 text-sky-700"
                          }`}
                        >
                          {issue.message}
                        </span>
                      ))}
                    </div>

                    <div className="w-full max-w-full overflow-hidden rounded-[1.5rem] border border-border">
                      <div className="max-h-[22rem] w-full max-w-full overflow-x-auto overflow-y-auto">
                        <table className="min-w-full text-sm">
                          <thead className="sticky top-0 z-10 bg-secondary/95 text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
                            <tr>
                              <th className="px-3 py-2.5 text-left">#</th>
                              {previewColumns.map((column) => (
                                <th key={column} className="px-3 py-2.5 text-left">
                                  {column}
                                </th>
                              ))}
                              <th className="px-3 py-2.5 text-left">Statut</th>
                            </tr>
                          </thead>
                          <tbody>
                            {visiblePreviewRows.map((row, index) => (
                              <tr key={`preview-row-${row.row_number}-${index}`} className="border-t border-border">
                                <td className="min-w-[4rem] px-3 py-2.5 align-top font-medium text-muted-foreground">
                                  {row.row_number ?? index + 1}
                                </td>
                                {previewColumns.map((column) => (
                                  <td key={`${index}-${column}`} className="min-w-[11rem] px-3 py-2.5 align-top">
                                    {renderCellValue(row.data?.[column])}
                                  </td>
                                ))}
                                <td className="min-w-[8rem] px-3 py-2.5 align-top">
                                  <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                                    row.status === "valid"
                                      ? "bg-emerald-50 text-emerald-700"
                                      : "bg-amber-50 text-amber-700"
                                  }`}>
                                    {row.status === "valid" ? "valid" : (row.status || "à revoir")}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                  ) : (
                  <EmptyState message="Sélectionne un fichier pour lancer l'analyse et afficher l'aperçu réel." />
                  )
                ) : (
                  <div className="mt-5 rounded-2xl border border-border bg-secondary/20 px-5 py-4 text-sm text-muted-foreground">
                    L'aperçu du fichier est masqué pour alléger la page. Déroule cette section pour revoir la structure brute importée.
                  </div>
                )}
              </Card>
            )}

            {step === 2 && source && (
              <Card className="p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="font-display text-xl font-semibold">Lier les feuilles entre elles</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {source.sheets && source.sheets.length > 1
                        ? "Connecte les colonnes qui existent dans plusieurs feuilles pour croiser les données."
                        : "Ce fichier n'a qu'une seule feuille. Ajoute un fichier avec plusieurs onglets pour créer des liens entre feuilles."}
                    </p>
                  </div>
                  {relationLoading ? <LoaderCircle className="h-5 w-5 animate-spin text-primary-strong" /> : null}
                </div>

                {source.sheets && source.sheets.length > 1 ? (
                  <div className="mt-4 rounded-2xl border border-border bg-secondary/20 p-4 space-y-3 text-sm text-muted-foreground">
                    <div>
                      <h4 className="font-semibold text-foreground">Pourquoi lier les feuilles ?</h4>
                      <p className="mt-1">
                        Un fichier Excel peut contenir des données de natures différentes réparties dans des onglets séparés
                        (ex. : Commandes, Clients, Produits). Pour les croiser dans une analyse, il faut indiquer quelles
                        colonnes partagent le même identifiant. C'est ce que fait cette étape.
                      </p>
                    </div>
                    <div>
                      <h4 className="font-semibold text-foreground">Comment ça marche ?</h4>
                      <p className="mt-1">
                        Le système compare automatiquement les noms et les valeurs des colonnes entre chaque feuille.
                        Lorsqu'une correspondance est trouvée (même nom de colonne, ou valeurs en chevauchement),
                        il propose un lien avec un score de confiance. Tu peux aussi créer un lien manuellement
                        en choisissant la colonne source et la colonne cible.
                      </p>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Les types de jointure : <span className="font-medium text-foreground">Plusieurs → Un</span> (clé étrangère vers clé primaire), <span className="font-medium text-foreground">Un → Un</span> (correspondance 1:1), ou <span className="font-medium text-foreground">Plusieurs ↔ Plusieurs</span> (correspondance multiple).
                    </p>
                  </div>
                ) : null}

                {source.sheets && source.sheets.length > 1 ? (
                  <div className="mt-4">
                    <Tabs value={activeSheet || source.sheets[0]?.sheet_name} onValueChange={setActiveSheet}>
                      <TabsList className="flex-wrap h-auto gap-1 bg-transparent p-0">
                        {source.sheets.map((sheet) => (
                          <TabsTrigger
                            key={sheet.sheet_name}
                            value={sheet.sheet_name}
                            className="rounded-full border border-border bg-white px-3 py-1.5 text-xs font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:border-primary"
                          >
                            <FileSpreadsheet className="mr-1.5 h-3 w-3" />
                            {sheet.sheet_name}
                            <span className="ml-1.5 rounded-full bg-black/5 px-1.5 py-0.5 text-[10px]">{sheet.row_count}</span>
                          </TabsTrigger>
                        ))}
                      </TabsList>
                    </Tabs>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {source.sheets.length} feuilles · {source.row_count} lignes au total
                    </p>
                  </div>
                ) : null}

                {source.sheets && source.sheets.length > 1 ? (
                  !relationLoading && relations.length === 0 && relationSuggestions.length === 0 ? (
                    <EmptyState message="Aucun lien détecté entre les feuilles. Tu peux en créer un manuellement ci-dessous." />
                  ) : (
                    <div className="mt-5 space-y-5">
                      {relations.length > 0 ? (
                        <div className="space-y-3">
                          <h4 className="text-sm font-semibold text-foreground">Liens créés</h4>
                          {relations.map((rel) => (
                            <div key={rel.id} className="flex items-center justify-between gap-3 rounded-xl border border-border bg-secondary/20 px-4 py-3">
                              <div className="min-w-0">
                                <div className="text-sm font-medium text-foreground">
                                  <span className="text-primary-strong">{rel.from_sheet}</span>
                                  <span className="mx-1 text-muted-foreground">.</span>
                                  <span>{rel.from_column}</span>
                                  <span className="mx-2 text-muted-foreground">→</span>
                                  <span className="text-primary-strong">{rel.to_sheet}</span>
                                  <span className="mx-1 text-muted-foreground">.</span>
                                  <span>{rel.to_column}</span>
                                </div>
                                <div className="mt-1 text-xs text-muted-foreground">
                                  {rel.join_type === "many_to_one" ? "Plusieurs → Un" : rel.join_type === "one_to_one" ? "Un → Un" : "Plusieurs ↔ Plusieurs"}
                                  {rel.confidence < 1 ? ` · Confiance : ${(rel.confidence * 100).toFixed(0)}%` : ""}
                                </div>
                              </div>
                              <button
                                type="button"
                                onClick={() => void handleDeleteRelation(rel.id)}
                                className="shrink-0 rounded-lg p-2 text-muted-foreground hover:bg-rose-50 hover:text-rose-600"
                              >
                                <Trash2 className="h-4 w-4" />
                              </button>
                            </div>
                          ))}
                        </div>
                      ) : null}

                      {relationSuggestions.length > 0 ? (
                        <div className="space-y-3">
                          <h4 className="text-sm font-semibold text-foreground">Suggestions du système</h4>
                          {relationSuggestions.map((sug, idx) => (
                            <div key={`sug-${idx}`} className="flex items-center justify-between gap-3 rounded-xl border border-dashed border-primary/30 bg-primary/[0.03] px-4 py-3">
                              <div className="min-w-0">
                                <div className="text-sm font-medium text-foreground">
                                  <span className="text-primary-strong">{sug.from_sheet}</span>
                                  <span className="mx-1 text-muted-foreground">.</span>
                                  <span>{sug.from_column}</span>
                                  <span className="mx-2 text-muted-foreground">→</span>
                                  <span className="text-primary-strong">{sug.to_sheet}</span>
                                  <span className="mx-1 text-muted-foreground">.</span>
                                  <span>{sug.to_column}</span>
                                </div>
                                <div className="mt-1 text-xs text-muted-foreground">
                                  Confiance: {(sug.confidence * 100).toFixed(0)}% · {sug.reason}
                                </div>
                              </div>
                              <button
                                type="button"
                                onClick={() => void handleCreateRelation(sug)}
                                className="shrink-0 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:brightness-110"
                              >
                                Accepter
                              </button>
                            </div>
                          ))}
                        </div>
                      ) : null}

                      {source.sheets && source.sheets.length > 1 ? (
                        <div className="space-y-3">
                          {!showManualForm ? (
                            <button
                              type="button"
                              onClick={() => setShowManualForm(true)}
                              className="rounded-lg border border-dashed border-border px-4 py-2.5 text-sm font-medium text-muted-foreground hover:border-primary/40 hover:text-foreground"
                            >
                              + Ajouter un lien manuellement
                            </button>
                          ) : (
                            <div className="rounded-2xl border border-border bg-secondary/20 p-4 space-y-4">
                              <div className="flex items-center justify-between">
                                <h4 className="text-sm font-semibold text-foreground">Nouveau lien</h4>
                                <button type="button" onClick={() => setShowManualForm(false)} className="text-xs text-muted-foreground hover:text-foreground">Annuler</button>
                              </div>

                              <div className="grid gap-3 sm:grid-cols-2">
                                <div className="space-y-1.5">
                                  <label className="text-xs font-medium text-muted-foreground">Première feuille</label>
                                  <select
                                    value={manualFromSheet}
                                    onChange={(e) => { setManualFromSheet(e.target.value); setManualFromColumn(""); }}
                                    className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm focus:border-primary focus:outline-none"
                                  >
                                    <option value="">Sélectionner…</option>
                                    {source.sheets!.map((s) => (
                                      <option key={s.sheet_name} value={s.sheet_name}>{s.sheet_name}</option>
                                    ))}
                                  </select>
                                </div>
                                <div className="space-y-1.5">
                                  <label className="text-xs font-medium text-muted-foreground">Colonne de la feuille source</label>
                                  <select
                                    value={manualFromColumn}
                                    onChange={(e) => setManualFromColumn(e.target.value)}
                                    disabled={!manualFromSheet}
                                    className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm focus:border-primary focus:outline-none disabled:opacity-50"
                                  >
                                    <option value="">Sélectionner…</option>
                                    {source.sheets!.find((s) => s.sheet_name === manualFromSheet)?.column_names.map((col) => (
                                      <option key={col} value={col}>{col}</option>
                                    ))}
                                  </select>
                                </div>
                                <div className="space-y-1.5">
                                  <label className="text-xs font-medium text-muted-foreground">Deuxième feuille</label>
                                  <select
                                    value={manualToSheet}
                                    onChange={(e) => { setManualToSheet(e.target.value); setManualToColumn(""); }}
                                    className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm focus:border-primary focus:outline-none"
                                  >
                                    <option value="">Sélectionner…</option>
                                    {source.sheets!.filter((s) => s.sheet_name !== manualFromSheet).map((s) => (
                                      <option key={s.sheet_name} value={s.sheet_name}>{s.sheet_name}</option>
                                    ))}
                                  </select>
                                </div>
                                <div className="space-y-1.5">
                                  <label className="text-xs font-medium text-muted-foreground">Colonne correspondante dans l'autre feuille</label>
                                  <select
                                    value={manualToColumn}
                                    onChange={(e) => setManualToColumn(e.target.value)}
                                    disabled={!manualToSheet}
                                    className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm focus:border-primary focus:outline-none disabled:opacity-50"
                                  >
                                    <option value="">Sélectionner…</option>
                                    {source.sheets!.find((s) => s.sheet_name === manualToSheet)?.column_names.map((col) => (
                                      <option key={col} value={col}>{col}</option>
                                    ))}
                                  </select>
                                </div>
                              </div>

                              <div className="space-y-1.5">
                                <label className="text-xs font-medium text-muted-foreground">Nom du lien (optionnel)</label>
                                <input
                                  type="text"
                                  value={manualRelationName}
                                  onChange={(e) => setManualRelationName(e.target.value)}
                                  placeholder={`${manualFromColumn || 'col'}_to_${manualToColumn || 'col'}`}
                                  className="w-full rounded-lg border border-border bg-white px-3 py-2 text-sm focus:border-primary focus:outline-none"
                                />
                              </div>

                              <button
                                type="button"
                                onClick={() => void handleCreateManualRelation()}
                                disabled={!manualFromSheet || !manualFromColumn || !manualToSheet || !manualToColumn}
                                className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:brightness-110 disabled:opacity-60"
                              >
                                Valider le lien
                              </button>
                            </div>
                          )}
                        </div>
                      ) : null}

                      <div className="flex gap-3">
                        <button
                          type="button"
                          onClick={() => void handleLoadJoinedView()}
                          disabled={relations.length === 0}
                          className="rounded-lg border border-border bg-white px-4 py-2 text-sm font-medium text-foreground hover:bg-secondary disabled:opacity-60"
                        >
                          Aperçu des données croisées
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            if (source) {
                              loadCleaningStage(source);
                            }
                          }}
                          className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:brightness-110"
                        >
                          Continuer vers le nettoyage →
                        </button>
                      </div>

                      {showJoinedView && joinedView ? (
                        <div className="mt-4 rounded-2xl border border-border overflow-hidden">
                          <div className="flex items-center justify-between bg-secondary/30 px-4 py-3">
                            <div className="text-sm font-semibold text-foreground">Aperçu croisé ({joinedView.total_rows || joinedView.rows.length} lignes)</div>
                            <button type="button" onClick={() => setShowJoinedView(false)} className="text-xs text-muted-foreground hover:text-foreground">Fermer</button>
                          </div>
                          {joinedView.relations_used.length > 0 ? (
                            <div className="border-b border-border bg-primary/[0.03] px-4 py-2 text-xs text-muted-foreground">
                              Liens appliqués : {joinedView.relations_used.join(" · ")}
                            </div>
                          ) : null}
                          <div className="max-h-[24rem] overflow-auto">
                            <table className="min-w-full text-sm">
                              <thead className="sticky top-0 z-10 bg-card/95 text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
                                <tr>
                                  <th className="px-3 py-2.5 text-left">#</th>
                                  {joinedView.columns.map((col) => (
                                    <th key={col} className="px-3 py-2.5 text-left">{col}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {joinedView.rows.slice(0, 50).map((row, i) => (
                                  <tr key={`jv-${i}`} className="border-t border-border">
                                    <td className="px-3 py-2 text-muted-foreground">{i + 1}</td>
                                    {joinedView.columns.map((col) => (
                                      <td key={`${i}-${col}`} className="px-3 py-2">{String(row[col] ?? "")}</td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          {joinedView.rows.length > 50 ? (
                            <div className="border-t border-border bg-secondary/20 px-4 py-2 text-xs text-muted-foreground">
                              Affichage des 50 premières lignes sur {joinedView.rows.length}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  )
                ) : (
                  <div className="mt-5 text-center py-8">
                    <FileSpreadsheet className="mx-auto h-10 w-10 text-muted-foreground/50 mb-3" />
                    <p className="text-sm text-muted-foreground">
                      Fichier a feuille unique — pas de relations a creer.
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        if (source) {
                          loadCleaningStage(source);
                        }
                      }}
                      className="mt-4 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:brightness-110"
                    >
                      Passer au nettoyage →
                    </button>
                  </div>
                )}
              </Card>
            )}

            {step === 3 && (
              <Card className="p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="font-display text-xl font-semibold">Nettoyage &amp; Règles</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Voici toutes les règles qui vont être appliquées. Valide-les, puis lance le nettoyage.
                    </p>
                  </div>
                  {cleaningLoading || applyingCleaning ? <LoaderCircle className="h-5 w-5 animate-spin text-primary-strong" /> : null}
                </div>

                {cleaningPreview && cleaningSuggestion ? (
                  <div className="mt-5 space-y-5">
                    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                      <StatCard label="Lignes d'origine" value={String(cleaningPreview.summary.initial_row_count ?? source?.row_count ?? 0)} />
                      <StatCard label="Lignes qui changent" value={String(cleaningPreview.summary.rows_affected ?? 0)} />
                      <StatCard label="Lignes retirees" value={String(cleaningPreview.summary.rows_removed ?? 0)} />
                      <StatCard label="Colonnes retirees" value={String(cleaningPreview.summary.columns_removed ?? 0)} />
                    </div>

                    <div className="grid gap-6 xl:grid-cols-2">
                      <div className="space-y-3">
                        <SectionTitle icon={AlertTriangle} title="Problemes detectes" />
                        <ul className="space-y-2 text-sm text-muted-foreground">
                          {cleaningSuggestion.detected_issues.slice(0, 5).map((issue: any) => (
                            <li key={`${issue.code}-${issue.message}`} className="rounded-xl border border-border bg-secondary/20 px-4 py-3">
                              {issue.message}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div className="space-y-3">
                        <SectionTitle icon={Check} title="Corrections proposees" />
                        <ul className="space-y-2 text-sm text-muted-foreground">
                          {cleaningSuggestion.suggested_rules.slice(0, 5).map((suggestion: any, index: number) => (
                            <li key={`${suggestion.rule_type}-${index}`} className="rounded-xl border border-border bg-secondary/20 px-4 py-3">
                              <span className="font-semibold text-foreground">{suggestion.rule_type}</span>
                              <span className="text-muted-foreground"> · {suggestion.reason}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>

                    {(quasiEmptyColumns.length || selectedUnmapped.length || sparseRows.length) ? (
                      <div className="space-y-4 rounded-2xl border border-border p-4">
                        <SectionTitle icon={ShieldCheck} title="ACTIONS MANUELLES" />
                        <p className="text-sm text-muted-foreground">
                          Coche les elements a supprimer.
                        </p>

                        {quasiEmptyColumns.length ? (
                          <div className="space-y-2">
                            <div className="text-sm font-semibold text-foreground">Colonnes quasi vides</div>
                            {quasiEmptyColumns.slice(0, 10).map((item) => {
                              const selected = selectedQuasiEmpty.includes(item.column);
                              return (
                                <label key={`quasi-${item.column}`} className="flex items-center justify-between gap-3 rounded-xl border border-border bg-secondary/20 px-4 py-3 text-sm">
                                  <div>
                                    <div className="font-medium text-foreground">{item.column}</div>
                                    <div className="text-xs text-muted-foreground">Remplie à {(item.fill_rate * 100).toFixed(1)}%</div>
                                  </div>
                                  <input
                                    type="checkbox"
                                    checked={selected}
                                    onChange={(e) =>
                                      setSelectedQuasiEmpty((current) =>
                                        e.target.checked ? Array.from(new Set([...current, item.column])) : current.filter((value) => value !== item.column),
                                      )
                                    }
                                    className="h-4 w-4 accent-primary"
                                  />
                                </label>
                              );
                            })}
                          </div>
                        ) : null}

                        {unmappedColumns.length ? (
                          <div className="space-y-2">
                            <div className="text-sm font-semibold text-foreground">Colonnes non mappées</div>
                            {unmappedColumns.slice(0, 10).map((column) => (
                              <label key={`unmapped-${column}`} className="flex items-center justify-between gap-3 rounded-xl border border-border bg-secondary/20 px-4 py-3 text-sm">
                                <div>
                                  <div className="font-medium text-foreground">{column}</div>
                                  <div className="text-xs text-muted-foreground">Cette colonne ne sera utile au pipeline aval que si tu décides de la garder.</div>
                                </div>
                                <input
                                  type="checkbox"
                                  checked={selectedUnmapped.includes(column)}
                                  onChange={(e) =>
                                    setSelectedUnmapped((current) =>
                                      e.target.checked ? Array.from(new Set([...current, column])) : current.filter((value) => value !== column),
                                    )
                                  }
                                  className="h-4 w-4 accent-primary"
                                />
                              </label>
                            ))}
                          </div>
                        ) : null}

                        {sparseRows.length ? (
                          <div className="space-y-2">
                            <div className="text-sm font-semibold text-foreground">Lignes très incomplètes</div>
                            {sparseRows.slice(0, 10).map((row) => {
                              const selected = selectedSparseRows.includes(row.row_number);
                              return (
                                <label key={`sparse-${row.row_number}`} className="flex items-center justify-between gap-3 rounded-xl border border-border bg-secondary/20 px-4 py-3 text-sm">
                                  <div>
                                    <div className="font-medium text-foreground">Ligne {row.row_number}</div>
                                    <div className="text-xs text-muted-foreground">{(row.missing_rate * 100).toFixed(1)}% de cellules vides</div>
                                  </div>
                                  <input
                                    type="checkbox"
                                    checked={selected}
                                    onChange={(e) =>
                                      setSelectedSparseRows((current) =>
                                        e.target.checked ? Array.from(new Set([...current, row.row_number])) : current.filter((value) => value !== row.row_number),
                                      )
                                    }
                                    className="h-4 w-4 accent-primary"
                                  />
                                </label>
                              );
                            })}
                          </div>
                        ) : null}
                      </div>
                    ) : null}

                    {structuralPlan && source && (
                      <div className="rounded-2xl border border-border p-4">
                        <RuleReview
                          sourceId={source.id}
                          reconstructionPlan={structuralPlan}
                          onExecuteComplete={async (result) => {
                            setCleaningJobAfterReview(result);
                            const jobId = result.job_id;
                            if (jobId) {
                              await loadValidationStage(jobId);
                            }
                            toast("Nettoyage terminé", { variant: "success" });
                          }}
                          onCancel={() => { setStructuralPlan(null); setStructuralRun(null); }}
                        />
                      </div>
                    )}

                    <div className="flex justify-end gap-3">
                      <button
                        type="button"
                        onClick={() => void handleApplyCleaning()}
                        disabled={applyingCleaning || !canWriteData}
                        className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
                      >
                        {applyingCleaning ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                        {applyingCleaning ? "Nettoyage en cours…" : "Appliquer le nettoyage"}
                      </button>
                    </div>
                  </div>
                ) : (
                  <EmptyState message="Le nettoyage sera préparé automatiquement dès que l'import réel sera terminé." />
                )}
              </Card>
            )}

            {step === 4 && (
              <Card className="p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="font-display text-xl font-semibold">Validation du résultat nettoyé</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Cette vue est distincte de l'aperçu d'import. Elle compare l'état brut et l'état nettoyé avant validation finale.
                    </p>
                  </div>
                  {validating ? <LoaderCircle className="h-5 w-5 animate-spin text-primary-strong" /> : null}
                </div>

                {comparison && cleaningJobDetail ? (
                  <div className="mt-5 space-y-5">
                    {source?.sheets && source.sheets.length > 1 ? (
                      <div className="mb-4">
                        <Tabs value={activeSheet || source.sheets[0]?.sheet_name} onValueChange={setActiveSheet}>
                          <TabsList className="flex-wrap h-auto gap-1 bg-transparent p-0">
                            {source.sheets.map((sheet) => (
                              <TabsTrigger
                                key={sheet.sheet_name}
                                value={sheet.sheet_name}
                                className="rounded-full border border-border bg-white px-3 py-1.5 text-xs font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:border-primary"
                              >
                                <FileSpreadsheet className="mr-1.5 h-3 w-3" />
                                {sheet.sheet_name}
                              </TabsTrigger>
                            ))}
                          </TabsList>
                        </Tabs>
                        <p className="mt-2 text-xs text-muted-foreground">
                          Nettoyage appliqué à {source.sheets.length} feuilles
                        </p>
                      </div>
                    ) : null}

                    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                      <StatCard label="Lignes" value={`${comparison.summary.total_rows_before} → ${comparison.summary.total_rows_after}`} />
                      <StatCard label="Lignes affectées" value={String(comparison.summary.rows_affected)} />
                      <StatCard label="Colonnes" value={`${beforeStructureColumns.length || comparison.columns.length} → ${afterStructureColumns.length || comparison.columns.length}`} />
                      <StatCard label="Validation" value={validationConfirmed ? "Validé" : `${cleaningJobDetail.validation_summary.validation_rate}%`} tone="success" />
                    </div>

                    {validationConfirmed ? (
                      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-4">
                        <div className="text-sm font-semibold text-emerald-800">Validation confirmée</div>
                        <p className="mt-1 text-sm text-emerald-700">
                          Le fichier a bien été validé et pris en compte. Passage vers l'étape suivante en cours…
                        </p>
                      </div>
                    ) : null}

                    <div className="grid gap-6 xl:grid-cols-2">
                      <div className="space-y-3">
                        <SectionTitle icon={FileText} title="Structure importée" />
                        <p className="text-sm text-muted-foreground">
                          Le fichier tel qu'il a été lu à l'import, avant compréhension structurelle et nettoyage.
                        </p>
                        <StructurePreviewTable columns={beforeStructureColumns} rows={beforeStructureRows} tone="before" />
                      </div>
                      <div className="space-y-3">
                        <SectionTitle icon={Sparkles} title="Structure après nettoyage" />
                        <p className="text-sm text-muted-foreground">
                          La structure finale obtenue après reconstruction, normalisation et assainissement des données.
                        </p>
                        <StructurePreviewTable columns={afterStructureColumns} rows={afterStructureRows} tone="after" />
                      </div>
                    </div>

                    <div className="space-y-3">
                      <SectionTitle icon={ShieldCheck} title="Diff détaillé ligne par ligne" />
                      <div className="max-h-[34rem] overflow-auto rounded-xl border border-border">
                        <table className="w-full text-sm">
                          <thead className="sticky top-0 z-10 bg-card/95 text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
                            <tr>
                              <th className="px-3 py-2.5 text-left">Ligne</th>
                              <th className="px-3 py-2.5 text-left">Avant</th>
                              <th className="px-3 py-2.5 text-left">Après</th>
                              <th className="px-3 py-2.5 text-left">Statut</th>
                            </tr>
                          </thead>
                          <tbody>
                            {comparisonRows.map((row) => (
                              <tr key={`comparison-${row.row_number}`} className="border-t border-border align-top">
                                <td className="px-3 py-2.5 font-medium text-foreground">{row.row_number}</td>
                                <td className="px-3 py-2.5">
                                  <InlineRecord data={row.before || {}} tone="before" />
                                </td>
                                <td className="px-3 py-2.5">
                                  <InlineRecord data={row.after || {}} tone="after" />
                                </td>
                                <td className="px-3 py-2.5">
                                  <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                                    row.status === "removed"
                                      ? "bg-rose-50 text-rose-700"
                                      : row.changes.length
                                        ? "bg-emerald-50 text-emerald-700"
                                        : "bg-slate-100 text-slate-700"
                                  }`}>
                                    {row.status === "removed" ? "Retirée" : row.changes.length ? "Modifiée" : "Conservée"}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    <div className="grid gap-4 xl:grid-cols-[1fr_auto_auto] xl:items-end">
                      <div>
                        <label className="text-sm font-semibold text-foreground">Note de validation</label>
                        <textarea
                          value={validationNotes}
                          onChange={(e) => setValidationNotes(e.target.value)}
                          rows={3}
                          className="mt-2 w-full rounded-xl border border-border bg-card px-3 py-2.5 text-sm outline-none focus:border-primary"
                          placeholder="Ex. Jeu prêt pour KPI, quelques lignes restent à surveiller sur la zone client."
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => void handleValidate(false)}
                        disabled={validating}
                        className="rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium hover:bg-secondary disabled:opacity-60"
                      >
                        Garder en attente
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleValidate(true)}
                        disabled={validating}
                        className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
                      >
                        Valider pour la suite
                      </button>
                    </div>
                  </div>
                ) : (
                  <EmptyState message="La comparaison avant / après sera disponible dès que le nettoyage réel sera terminé." />
                )}
              </Card>
            )}
        </div>
      </PageBody>

      {/* Confirmation de suppression d'une source */}
      <ConfirmDialog
        open={!!sourceToDelete}
        onOpenChange={(open) => !open && setSourceToDelete(null)}
        title="Supprimer cette source de données ?"
        description={`Êtes-vous sûr de vouloir supprimer la source « ${sourceToDelete?.name} » ? Cette action est irréversible et supprimera l'historique associé.`}
        confirmLabel="Supprimer"
        destructive
        pending={deletingSource}
        onConfirm={confirmDeleteSource}
      />
    </div>
  );
}

function StatCard({ label, value, tone = "default" }: { label: string; value: string; tone?: "default" | "success" | "warning" }) {
  const toneClass =
    tone === "success" ? "border-emerald-200 bg-emerald-50/50" : tone === "warning" ? "border-amber-200 bg-amber-50/50" : "";
  return (
    <div className={`flex min-h-[96px] flex-col justify-between rounded-2xl border border-border p-5 ${toneClass}`}>
      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] leading-4 text-muted-foreground">
        {label}
      </div>
      <div className="mt-3 text-3xl font-semibold leading-none text-foreground">{value}</div>
    </div>
  );
}

function StructurePreviewTable({
  columns,
  rows,
  tone,
}: {
  columns: string[];
  rows: Array<Record<string, any>>;
  tone: "before" | "after";
}) {
  if (!columns.length || !rows.length) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-secondary/20 px-5 py-8 text-center text-sm text-muted-foreground">
        Aucune structure détaillée n'a été remontée pour cette vue.
      </div>
    );
  }

  return (
    <div className={`overflow-hidden rounded-2xl border ${tone === "before" ? "border-amber-200" : "border-emerald-200"}`}>
      <div className={`px-4 py-3 text-xs font-semibold uppercase tracking-[0.16em] ${tone === "before" ? "bg-amber-50 text-amber-800" : "bg-emerald-50 text-emerald-800"}`}>
        {tone === "before" ? "Vue importée" : "Vue nettoyée"}
      </div>
      <div className="max-h-[28rem] overflow-auto">
        <table className="min-w-full text-sm">
          <thead className="sticky top-0 z-10 bg-card/95 text-xs uppercase tracking-wider text-muted-foreground backdrop-blur">
            <tr>
              <th className="px-3 py-2.5 text-left">#</th>
              {columns.map((column) => (
                <th key={column} className="px-3 py-2.5 text-left">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => {
              const data = (row.data || row.before || row.after || {}) as Record<string, any>;
              return (
                <tr key={`structure-${tone}-${row.row_number ?? index}`} className="border-t border-border">
                  <td className="min-w-[4rem] px-3 py-2.5 align-top font-medium text-muted-foreground">
                    {row.row_number ?? index + 1}
                  </td>
                  {columns.map((column) => (
                    <td key={`${tone}-${index}-${column}`} className="min-w-[10rem] px-3 py-2.5 align-top">
                      {renderCellValue(data[column])}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-secondary/20 px-5 py-8 text-center text-sm text-muted-foreground">
      {message}
    </div>
  );
}

function SectionTitle({ icon: Icon, title }: { icon: typeof AlertTriangle; title: string }) {
  return (
    <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
      <Icon className="h-4 w-4 text-primary-strong" />
      {title}
    </div>
  );
}

function DiffBox({ title, tone, data }: { title: string; tone: "before" | "after"; data: Record<string, any> }) {
  return (
    <div className={`rounded-xl border p-3 ${tone === "before" ? "border-amber-200 bg-amber-50/50" : "border-emerald-200 bg-emerald-50/50"}`}>
      <div className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">{title}</div>
      <InlineRecord data={data} tone={tone} />
    </div>
  );
}

function InlineRecord({ data, tone }: { data: Record<string, any>; tone: "before" | "after" }) {
  const entries = Object.entries(data || {}).filter(([, value]) => {
    if (tone !== "after") return true;
    if (value === null || value === undefined || value === "") return false;
    if (typeof value === "number" && Number.isNaN(value)) return false;
    if (typeof value === "string" && value.trim().toLowerCase() === "nan") return false;
    return true;
  });
  if (!entries.length) {
    return <span className="text-xs text-muted-foreground">Aucune donnée</span>;
  }
  return (
    <div className="space-y-1.5">
      {entries.slice(0, 8).map(([key, value]) => (
        <div key={key} className={`rounded-lg px-2 py-1.5 text-xs ${tone === "before" ? "bg-white/70 text-slate-700" : "bg-white/70 text-emerald-900"}`}>
          <span className="font-semibold">{key} :</span> {renderCellValue(value)}
        </div>
      ))}
    </div>
  );
}
