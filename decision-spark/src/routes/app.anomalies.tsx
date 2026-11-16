import { createFileRoute } from "@tanstack/react-router";
import {
  ArrowRight,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Loader2,
  RefreshCw,
  ScanSearch,
  Sparkles,
  UserCheck,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/AppShell";
import {
  EmptyState,
  ErrorState,
  InfoDisclosure,
  LoadingState,
  PageBody,
  Panel,
  SEVERITY_LABELS,
  Segmented,
  StatusBadge,
  SuccessNotice,
  type Tone,
  fieldClass,
  labelClass,
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
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  apiClient,
  handleApiError,
  type AnomalyDetail,
  type AnomalyDetection,
  type DataSourceDetail,
  type IsolationForestResult,
} from "@/lib/api";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/anomalies")({
  beforeLoad: async () => {
    const { requireRoleAccess } = await import("@/lib/rbac");
    await requireRoleAccess("read:dashboard");
  },
  component: AnomaliesPage,
  head: () => ({ meta: [{ title: "Anomalies — DécisioBI" }] }),
});

type SeverityFilter = "all" | "critical" | "high" | "medium" | "low";

const SEVERITY_FILTERS: { value: SeverityFilter; label: string }[] = [
  { value: "all", label: "Toutes" },
  { value: "critical", label: "Critique" },
  { value: "high", label: "Élevée" },
  { value: "medium", label: "Moyenne" },
  { value: "low", label: "Faible" },
];

const STATUS_META: Record<AnomalyDetection["status"], { label: string; tone: Tone }> = {
  new: { label: "Nouvelle", tone: "brand" },
  investigating: { label: "En cours", tone: "info" },
  confirmed: { label: "Confirmée", tone: "warning" },
  resolved: { label: "Résolue", tone: "success" },
  false_positive: { label: "Ignorée", tone: "neutral" },
};

const ACTIVE_STATUSES: AnomalyDetection["status"][] = ["new", "investigating", "confirmed"];
const PAGE_SIZE = 20;

function AnomaliesPage() {
  const [filter, setFilter] = useState<SeverityFilter>("all");
  const [items, setItems] = useState<AnomalyDetection[]>([]);
  const [selected, setSelected] = useState<AnomalyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadingDetailId, setLoadingDetailId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [runningIF, setRunningIF] = useState(false);
  const [showNewPanel, setShowNewPanel] = useState(false);
  const [tab, setTab] = useState<"actives" | "historique">("actives");
  const [sources, setSources] = useState<DataSourceDetail[]>([]);
  const [selectedSourceId, setSelectedSourceId] = useState<number | null>(null);
  const [sourceColumns, setSourceColumns] = useState<string[]>([]);
  const [selectedSourceCols, setSelectedSourceCols] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<IsolationForestResult | null>(null);
  const [actionPending, setActionPending] = useState(false);

  useEffect(() => {
    apiClient
      .listDataSources()
      .then(setSources)
      .catch(() => {});
  }, []);

  const loadAnomalies = useCallback(async () => {
    try {
      setLoading(true);
      setLoadError(null);
      const severity = filter === "all" ? undefined : filter;
      const res = await apiClient.listAnomalies(page, severity);
      setItems(res.results);
      setTotalCount(res.count);
    } catch (error) {
      setLoadError(handleApiError(error, "Erreur lors du chargement des anomalies"));
    } finally {
      setLoading(false);
    }
  }, [page, filter]);

  useEffect(() => {
    void loadAnomalies();
  }, [loadAnomalies]);

  const changeFilter = (next: SeverityFilter) => {
    setFilter(next);
    setPage(1);
  };

  const handleSourceChange = async (id: number) => {
    setSelectedSourceId(id || null);
    setSelectedSourceCols(new Set());
    setResult(null);
    if (!id) {
      setSourceColumns([]);
      return;
    }
    try {
      const detail = await apiClient.getDataSource(id);
      const cols = detail.sample_rows?.[0]?.data ? Object.keys(detail.sample_rows[0].data) : [];
      setSourceColumns(cols);
      setSelectedSourceCols(new Set(cols));
    } catch {
      setSourceColumns([]);
    }
  };

  const toggleCol = (col: string) => {
    setSelectedSourceCols((prev) => {
      const next = new Set(prev);
      if (next.has(col)) next.delete(col);
      else next.add(col);
      return next;
    });
  };

  const handleRunDetection = async () => {
    if (!selectedSourceId || selectedSourceCols.size === 0) return;
    setRunningIF(true);
    setResult(null);
    try {
      const res = await apiClient.runIsolationForest({
        source_id: selectedSourceId,
        feature_columns: Array.from(selectedSourceCols),
        backend: "raw",
        contamination: 0.05,
        max_rows: 5000,
        persist: true,
      });
      setResult(res);
      void loadAnomalies();
      toast(
        `${res.outlier_count} anomalie(s) détectée(s) sur ${res.n_samples.toLocaleString("fr-FR")} lignes`,
        { variant: "info" },
      );
    } catch (err) {
      toast(handleApiError(err, "Erreur lors de la détection"), { variant: "error" });
    } finally {
      setRunningIF(false);
    }
  };

  const handleExamine = async (id: number) => {
    try {
      setLoadingDetailId(id);
      const detail = await apiClient.getAnomalyDetail(id);
      setSelected(detail);
    } catch {
      toast("Erreur lors du chargement du détail", { variant: "error" });
    } finally {
      setLoadingDetailId(null);
    }
  };

  const updateStatus = async (
    id: number,
    payload: Parameters<typeof apiClient.updateAnomalyStatus>[1],
    onDone: () => void,
    errorLabel: string,
  ) => {
    setActionPending(true);
    try {
      await apiClient.updateAnomalyStatus(id, payload);
      const status = payload.status as AnomalyDetection["status"];
      setItems((arr) => arr.map((x) => (x.id === id ? { ...x, status } : x)));
      setSelected(null);
      onDone();
    } catch (error) {
      toast(handleApiError(error, errorLabel), { variant: "error" });
    } finally {
      setActionPending(false);
    }
  };

  const visible =
    tab === "actives" ? items.filter((i) => ACTIVE_STATUSES.includes(i.status)) : items;
  const activeOnPage = items.filter((i) => ACTIVE_STATUSES.includes(i.status)).length;
  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  return (
    <div>
      <PageHeader
        title="Anomalies"
        subtitle="Valeurs statistiquement inhabituelles repérées par Isolation Forest : examinez-les, puis résolvez, affectez ou ignorez."
        actions={
          <>
            <Button variant="outline" onClick={() => void loadAnomalies()} disabled={loading}>
              <RefreshCw className={cn(loading && "animate-spin")} />
              Rafraîchir
            </Button>
            <Button onClick={() => setShowNewPanel(true)}>
              <Sparkles /> Détecter des anomalies
            </Button>
          </>
        }
      />

      <PageBody>
        <InfoDisclosure title="Comprendre les anomalies de données">
          <p>
            Une anomalie est un ensemble de données qui ne se conforme pas au comportement attendu
            <strong className="text-foreground">
              {" "}
              (Chandola, Banerjee &amp; Kumar, 2009 — ACM Computing Surveys)
            </strong>
            . Contrairement aux valeurs manquantes ou aux doublons, une anomalie est une donnée{" "}
            <em>présente et valide en apparence</em> mais statistiquement inhabituelle.
          </p>
          <p>
            Dans DécisioBI, l'algorithme{" "}
            <strong className="text-foreground">Isolation Forest</strong> analyse vos colonnes
            numériques de manière <strong className="text-foreground">multivariée</strong>{" "}
            (plusieurs colonnes simultanément) pour détecter des{" "}
            <strong className="text-foreground">points aberrants</strong> (valeur extrême isolée),
            des <strong className="text-foreground">anomalies contextuelles</strong> (valeur
            anormale dans son contexte), ou des{" "}
            <strong className="text-foreground">anomalies collectives</strong> (groupe de lignes au
            comportement inhabituel). Chaque anomalie reçoit un score de sévérité (faible, moyen,
            élevé, critique) et une explication générée automatiquement pour vous aider à décider
            s'il s'agit d'une erreur de saisie, d'un cas exceptionnel, ou d'un signal à investiguer.
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-lg border border-border bg-secondary/40 p-3 text-xs">
              <p className="font-semibold text-foreground">1 · Point aberrant</p>
              <p className="mt-1">
                Dans une colonne « Montant » dont la moyenne est 50 000 €, une valeur de 500 000 €
                est isolée et très éloignée du reste. L'Isolation Forest la repère car elle
                nécessite très peu de coupes pour être isolée dans l'arbre.
              </p>
            </div>
            <div className="rounded-lg border border-border bg-secondary/40 p-3 text-xs">
              <p className="font-semibold text-foreground">2 · Anomalie contextuelle</p>
              <p className="mt-1">
                Un mois de janvier avec 3 000 commandes alors que la moyenne de janvier des années
                précédentes est de 800. La valeur n'est pas extrême en soi, mais elle est anormale{" "}
                <em>dans son contexte temporel</em>.
              </p>
            </div>
          </div>
          <p className="text-xs">
            <span className="font-medium">Référence :</span> Chandola, V., Banerjee, A., &amp;
            Kumar, V. (2009). <em>Anomaly Detection: A Survey</em>. ACM Computing Surveys, 41(3),
            Article 15.
          </p>
        </InfoDisclosure>

        <Panel
          title={tab === "actives" ? "Anomalies à traiter" : "Historique des anomalies"}
          description={`${totalCount.toLocaleString("fr-FR")} anomalie${totalCount > 1 ? "s" : ""} au total${filter !== "all" ? ` · gravité ${SEVERITY_LABELS[filter].toLowerCase()}` : ""}`}
          icon={ScanSearch}
          bodyClassName="p-0"
          actions={
            <>
              <Segmented
                label="Vue"
                value={tab}
                onChange={setTab}
                options={[
                  {
                    value: "actives",
                    label: "À traiter",
                    count: loading ? undefined : activeOnPage,
                  },
                  { value: "historique", label: "Historique" },
                ]}
              />
              <Segmented
                label="Gravité"
                value={filter}
                onChange={changeFilter}
                options={SEVERITY_FILTERS}
              />
            </>
          }
        >
          {loading ? (
            <LoadingState className="p-5" label="Chargement des anomalies…" rows={4} />
          ) : loadError ? (
            <ErrorState className="m-5" message={loadError} onRetry={() => void loadAnomalies()} />
          ) : visible.length === 0 ? (
            <EmptyState
              className="m-5"
              icon={tab === "actives" ? CheckCircle2 : ScanSearch}
              title={
                tab === "actives"
                  ? "Aucune anomalie à traiter"
                  : "Aucune anomalie dans l'historique"
              }
              description={
                tab === "actives"
                  ? "Tout est sous contrôle sur cette page. Lancez une détection pour analyser une nouvelle source."
                  : "Les anomalies détectées, résolues ou ignorées apparaîtront ici."
              }
              action={
                <Button variant="outline" onClick={() => setShowNewPanel(true)}>
                  <Sparkles /> Lancer une détection
                </Button>
              }
            />
          ) : (
            <ul className="divide-y divide-border">
              {visible.map((a) => {
                const status = STATUS_META[a.status] ?? STATUS_META.new;
                return (
                  <li
                    key={a.id}
                    className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-4 transition-colors hover:bg-secondary/40"
                  >
                    <StatusBadge
                      tone={severityTone(a.severity)}
                      dot
                      className="w-[88px] justify-center"
                    >
                      {SEVERITY_LABELS[a.severity] || a.severity}
                    </StatusBadge>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate font-medium text-foreground">
                          {a.data_source_name || `Source #${a.data_source}`}
                        </p>
                        <span className="text-xs text-muted-foreground">#{a.id}</span>
                        <StatusBadge tone={status.tone}>{status.label}</StatusBadge>
                      </div>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {a.algorithm} · {a.outlier_count} ligne(s) affectée(s) ·{" "}
                        {new Date(a.detected_at).toLocaleDateString("fr-FR")}
                      </p>
                    </div>
                    <div className="hidden text-right md:block">
                      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                        Score
                      </p>
                      <p className="font-display text-base font-semibold tabular-nums">
                        {Number(a.anomaly_score).toFixed(2)}
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void handleExamine(a.id)}
                      disabled={loadingDetailId !== null}
                    >
                      {loadingDetailId === a.id ? (
                        <Loader2 className="animate-spin" />
                      ) : (
                        <>
                          Examiner <ArrowRight />
                        </>
                      )}
                    </Button>
                  </li>
                );
              })}
            </ul>
          )}

          {!loading && !loadError && totalPages > 1 && (
            <div className="flex items-center justify-between gap-4 border-t border-border px-5 py-3">
              <p className="text-xs text-muted-foreground">
                Page {page} sur {totalPages}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  <ChevronLeft /> Précédent
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                >
                  Suivant <ChevronRight />
                </Button>
              </div>
            </div>
          )}
        </Panel>
      </PageBody>

      {/* Lancement d'une détection Isolation Forest */}
      <Sheet open={showNewPanel} onOpenChange={setShowNewPanel}>
        <SheetContent className="flex w-full flex-col gap-0 overflow-y-auto p-0 sm:max-w-lg">
          <SheetHeader className="border-b border-border px-6 py-5 text-left">
            <SheetTitle className="font-display">Détecter des anomalies</SheetTitle>
            <SheetDescription>
              Choisissez une source et les colonnes chiffrées à analyser ensemble.
            </SheetDescription>
          </SheetHeader>

          <div className="flex-1 space-y-5 px-6 py-5">
            <div>
              <label htmlFor="if-source" className={labelClass}>
                Quel fichier analyser ?
              </label>
              <select
                id="if-source"
                value={selectedSourceId ?? ""}
                onChange={(e) => void handleSourceChange(Number(e.target.value))}
                className={cn(fieldClass, "h-10")}
              >
                <option value="">Sélectionner une source…</option>
                {sources.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name ?? `Source #${s.id}`} ({(s.row_count ?? 0).toLocaleString("fr-FR")}{" "}
                    lignes)
                  </option>
                ))}
              </select>
            </div>

            {sourceColumns.length > 0 && (
              <fieldset>
                <div className="mb-1.5 flex items-center justify-between">
                  <legend className="text-[13px] font-medium text-foreground">
                    Colonnes numériques à analyser ({selectedSourceCols.size}/{sourceColumns.length}
                    )
                  </legend>
                  <div className="flex gap-3 text-xs">
                    <button
                      type="button"
                      onClick={() => setSelectedSourceCols(new Set(sourceColumns))}
                      className="font-medium text-primary-strong hover:underline"
                    >
                      Tout
                    </button>
                    <button
                      type="button"
                      onClick={() => setSelectedSourceCols(new Set())}
                      className="font-medium text-muted-foreground hover:text-foreground hover:underline"
                    >
                      Aucun
                    </button>
                  </div>
                </div>
                <p className="mb-2 text-xs text-muted-foreground">
                  Sélectionnez les colonnes contenant des valeurs chiffrées (montants, quantités,
                  taux…).
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {sourceColumns.map((col) => {
                    const active = selectedSourceCols.has(col);
                    return (
                      <button
                        key={col}
                        type="button"
                        aria-pressed={active}
                        onClick={() => toggleCol(col)}
                        className={cn(
                          "rounded-md border px-2.5 py-1 text-xs font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                          active
                            ? "border-foreground bg-foreground text-background"
                            : "border-border text-muted-foreground hover:bg-secondary hover:text-foreground",
                        )}
                      >
                        {col}
                      </button>
                    );
                  })}
                </div>
              </fieldset>
            )}

            {result && (
              <SuccessNotice
                title="Analyse terminée"
                message={`${result.outlier_count} anomalie(s) détectée(s) sur ${result.n_samples.toLocaleString("fr-FR")} lignes (${result.n_samples > 0 ? ((result.outlier_count / result.n_samples) * 100).toFixed(2) : "0.00"} %)`}
              />
            )}
          </div>

          <div className="flex flex-wrap justify-end gap-2 border-t border-border px-6 py-4">
            {result ? (
              <>
                <Button variant="outline" onClick={() => setResult(null)}>
                  Nouvelle analyse
                </Button>
                <Button
                  onClick={() => {
                    setShowNewPanel(false);
                    void loadAnomalies();
                  }}
                >
                  Voir dans la liste
                </Button>
              </>
            ) : (
              <>
                <Button variant="ghost" onClick={() => setShowNewPanel(false)}>
                  Annuler
                </Button>
                <Button
                  onClick={() => void handleRunDetection()}
                  disabled={!selectedSourceId || selectedSourceCols.size === 0 || runningIF}
                >
                  {runningIF ? (
                    <>
                      <Loader2 className="animate-spin" /> Détection en cours…
                    </>
                  ) : (
                    <>
                      <Sparkles /> Lancer la détection
                    </>
                  )}
                </Button>
              </>
            )}
          </div>
        </SheetContent>
      </Sheet>

      {/* Détail et résolution */}
      <Dialog open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
          {selected && (
            <>
              <DialogHeader>
                <DialogTitle className="font-display">Anomalie #{selected.id}</DialogTitle>
                <DialogDescription asChild>
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <StatusBadge tone={severityTone(selected.severity)} dot>
                      {SEVERITY_LABELS[selected.severity] || selected.severity}
                    </StatusBadge>
                    <span>Score : {Number(selected.anomaly_score).toFixed(2)}</span>
                    {selected.confidence > 0 && (
                      <span>Confiance : {(selected.confidence * 100).toFixed(0)} %</span>
                    )}
                  </div>
                </DialogDescription>
              </DialogHeader>

              <dl className="space-y-4 rounded-xl border border-border bg-secondary/40 p-4 text-sm">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <dt className="text-xs font-medium text-muted-foreground">Source</dt>
                    <dd className="mt-1 font-medium">
                      {selected.data_source_name || `Source #${selected.data_source}`}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs font-medium text-muted-foreground">Lignes affectées</dt>
                    <dd className="mt-1 font-medium">{selected.outlier_count} ligne(s)</dd>
                  </div>
                </div>
                {selected.affected_columns?.length > 0 && (
                  <div>
                    <dt className="text-xs font-medium text-muted-foreground">
                      Colonnes impliquées
                    </dt>
                    <dd className="mt-1.5 flex flex-wrap gap-1">
                      {selected.affected_columns.map((col) => (
                        <span
                          key={col}
                          className="rounded-md border border-border bg-card px-2 py-0.5 font-mono text-xs"
                        >
                          {col}
                        </span>
                      ))}
                    </dd>
                  </div>
                )}
                {selected.contribution_scores &&
                  Object.keys(selected.contribution_scores).length > 0 && (
                    <div>
                      <dt className="text-xs font-medium text-muted-foreground">
                        Impact des colonnes sur la détection
                      </dt>
                      <dd className="mt-2 space-y-1.5">
                        {Object.entries(selected.contribution_scores)
                          .sort(([, a], [, b]) => b - a)
                          .map(([col, score]) => (
                            <div key={col} className="flex items-center gap-2">
                              <span className="w-28 truncate font-mono text-xs">{col}</span>
                              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-border">
                                <div
                                  className="h-full rounded-full bg-chart-1"
                                  style={{ width: `${Math.min(100, score * 100)}%` }}
                                />
                              </div>
                              <span className="w-10 text-right text-xs tabular-nums text-muted-foreground">
                                {(score * 100).toFixed(0)} %
                              </span>
                            </div>
                          ))}
                      </dd>
                    </div>
                  )}
              </dl>

              {selected.explanation && (
                <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
                  <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-blue-800">
                    <Sparkles className="h-3.5 w-3.5" /> Ce qu'il faut retenir
                  </p>
                  <p className="mt-2 whitespace-pre-wrap text-sm text-foreground">
                    {selected.explanation}
                  </p>
                  {selected.explanation.includes("que d'habitude") && (
                    <p className="mt-2 border-t border-blue-200 pt-2 text-xs text-muted-foreground">
                      <strong>« que d'habitude »</strong> = comparé à la valeur du milieu quand on
                      trie toutes les lignes. Exemple&nbsp;: si les montants sont [100, 120, 130,
                      150, 50000], la valeur « d'habitude » est 130 (la 3<sup>e</sup> sur 5). 50000
                      est bien plus élevé → anormal.
                    </p>
                  )}
                </div>
              )}

              <DialogFooter className="gap-2 sm:gap-2">
                <Button
                  variant="ghost"
                  disabled={actionPending}
                  onClick={() =>
                    void updateStatus(
                      selected.id,
                      { status: "false_positive", is_reviewed: true },
                      () => toast("Anomalie ignorée", { variant: "warning" }),
                      "Erreur lors de la mise à jour",
                    )
                  }
                >
                  Ignorer
                </Button>
                <Button
                  variant="outline"
                  disabled={actionPending}
                  onClick={() =>
                    void updateStatus(
                      selected.id,
                      { status: "investigating" },
                      () =>
                        toast("Affectation à un responsable", {
                          description: "Notification envoyée à l'équipe",
                          variant: "info",
                        }),
                      "Erreur lors de l'affectation",
                    )
                  }
                >
                  <UserCheck /> Affecter
                </Button>
                <Button
                  disabled={actionPending}
                  onClick={() =>
                    void updateStatus(
                      selected.id,
                      { status: "resolved", is_reviewed: true },
                      () => toast("Anomalie marquée résolue", { variant: "success" }),
                      "Erreur lors de la mise à jour",
                    )
                  }
                >
                  {actionPending ? <Loader2 className="animate-spin" /> : <CheckCircle2 />}
                  Marquer résolue
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
