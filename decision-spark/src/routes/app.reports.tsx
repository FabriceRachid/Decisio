import { createFileRoute } from "@tanstack/react-router";
import {
  CalendarClock,
  CheckCircle2,
  Clock,
  Database,
  Download,
  Edit3,
  FileDown,
  FileText,
  Loader2,
  Mail,
  Play,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { PageHeader } from "@/components/AppShell";
import { ConfirmDialog } from "@/components/app/ConfirmDialog";
import { JourneySteps } from "@/components/app/PageHeader";
import {
  EmptyState,
  ErrorState,
  FormField,
  InfoDisclosure,
  LoadingState,
  PageBody,
  Panel,
  Segmented,
  StatCard,
  StatusBadge,
  fieldClass,
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
import { Switch } from "@/components/ui/switch";
import { apiClient, handleApiError, type DataSourceDetail } from "@/lib/api";
import { getUrl } from "@/lib/env";
import { can, getCurrentUserProfile } from "@/lib/rbac";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/reports")({
  beforeLoad: async () => {
    const { requireRoleAccess } = await import("@/lib/rbac");
    await requireRoleAccess("read:dashboard");
  },
  component: ReportsPage,
  head: () => ({ meta: [{ title: "Rapports — DécisioBI" }] }),
});

type ReportConfig = {
  id: number;
  job_name: string;
  schedule_type: "interval" | "cron" | "once";
  interval_minutes?: number | null;
  cron_expression?: string | null;
  schedule_display: string;
  next_run_at?: string | null;
  last_run_at?: string | null;
  last_run_display: string;
  last_run_status?: string | null;
  is_active: boolean;
  job_parameters?: { source_id?: number; source_name?: string };
  notification_recipients?: string[];
  created_at: string;
};

type HistoryItem = {
  filename: string;
  size_bytes: number;
  created_at: number;
  download_url: string;
};

type Tab = "configs" | "history";

type ReportForm = {
  job_name: string;
  source_id: string;
  interval_minutes: number;
  recipients: string;
};

const FREQUENCIES = [
  { value: 60, label: "Toutes les heures" },
  { value: 1440, label: "Tous les jours" },
  { value: 10080, label: "Toutes les semaines" },
  { value: 43200, label: "Tous les mois" },
];

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const emptyForm: ReportForm = {
  job_name: "",
  source_id: "",
  interval_minutes: 10080,
  recipients: "",
};

function freqLabel(
  cfg: Pick<ReportConfig, "schedule_type" | "interval_minutes" | "schedule_display">,
) {
  const min = cfg.interval_minutes;
  if (cfg.schedule_type !== "interval" || !min) return cfg.schedule_display;
  const preset = FREQUENCIES.find((f) => f.value === min);
  if (preset) return preset.label;
  if (min < 60) return `Toutes les ${min} min`;
  if (min < 1440) return `Toutes les ${Math.round(min / 60)} h`;
  return `Tous les ${Math.round(min / 1440)} jours`;
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(0)} Ko`;
  return `${(bytes / 1048576).toFixed(1)} Mo`;
}

function formatDateTime(value: Date | string | number) {
  return new Date(value).toLocaleString("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Les fichiers sont nommés report_{configId}_{horodatage}.pdf côté serveur. */
function configIdFromFilename(filename: string) {
  const m = /^report_(\d+)_/.exec(filename);
  return m ? Number(m[1]) : null;
}

function ReportsPage() {
  const [role, setRole] = useState<string | null>(null);
  const [configs, setConfigs] = useState<ReportConfig[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [sources, setSources] = useState<DataSourceDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [configsError, setConfigsError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("configs");
  const [runningId, setRunningId] = useState<number | null>(null);
  const [pendingId, setPendingId] = useState<number | null>(null);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ReportConfig | null>(null);
  const [form, setForm] = useState<ReportForm>(emptyForm);
  const [formErrors, setFormErrors] = useState<Partial<Record<keyof ReportForm, string>>>({});
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ReportConfig | null>(null);

  const canGenerate = can(role, "write:data");

  useEffect(() => {
    getCurrentUserProfile()
      .then((p) => setRole(p.profile?.role ?? null))
      .catch(() => {});
  }, []);

  const loadConfigs = useCallback(async () => {
    try {
      setConfigsError(null);
      setConfigs(await apiClient.listReportConfigs());
    } catch (err) {
      setConfigsError(handleApiError(err, "Impossible de charger les rapports"));
    }
  }, []);

  const loadHistory = useCallback(async () => {
    try {
      setHistoryError(null);
      setHistory(await apiClient.getReportHistory());
    } catch (err) {
      setHistoryError(handleApiError(err, "Impossible de charger l'historique"));
    }
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([
      loadConfigs(),
      loadHistory(),
      apiClient
        .listDataSources()
        .then(setSources)
        .catch(() => {}),
    ]);
    setLoading(false);
  }, [loadConfigs, loadHistory]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const configNames = useMemo(
    () => new Map(configs.map((c) => [c.id, c.job_name] as const)),
    [configs],
  );
  const activeCount = configs.filter((c) => c.is_active).length;
  const lastGenerated = history[0] ? formatDateTime(history[0].created_at * 1000) : null;

  /* ───────────── Actions ───────────── */

  const openCreate = () => {
    setEditing(null);
    setForm({ ...emptyForm, source_id: sources[0] ? String(sources[0].id) : "" });
    setFormErrors({});
    setFormOpen(true);
  };

  const openEdit = (cfg: ReportConfig) => {
    setEditing(cfg);
    setForm({
      job_name: cfg.job_name,
      source_id: cfg.job_parameters?.source_id ? String(cfg.job_parameters.source_id) : "",
      interval_minutes: cfg.interval_minutes || 10080,
      recipients: (cfg.notification_recipients || []).join(", "),
    });
    setFormErrors({});
    setFormOpen(true);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const errors: Partial<Record<keyof ReportForm, string>> = {};
    const recipients = form.recipients
      .split(/[,;\s]+/)
      .map((r) => r.trim())
      .filter(Boolean);
    if (!form.job_name.trim()) errors.job_name = "Donnez un nom au rapport.";
    if (!form.source_id) errors.source_id = "Choisissez la source à présenter.";
    if (recipients.some((r) => !EMAIL_RE.test(r)))
      errors.recipients = "Une ou plusieurs adresses e-mail sont invalides.";
    setFormErrors(errors);
    if (Object.keys(errors).length > 0) return;

    const source = sources.find((s) => s.id === Number(form.source_id));
    const payload = {
      job_name: form.job_name.trim(),
      schedule_type: "interval" as const,
      interval_minutes: form.interval_minutes,
      job_parameters: {
        source_id: Number(form.source_id),
        source_name: source?.name ?? editing?.job_parameters?.source_name,
      },
      notification_recipients: recipients,
    };

    setSaving(true);
    try {
      if (editing) {
        await apiClient.updateReportConfig(editing.id, payload);
        toast("Rapport mis à jour", { variant: "success" });
      } else {
        await apiClient.createReportConfig(payload);
        toast("Rapport planifié", { variant: "success" });
      }
      setFormOpen(false);
      await loadConfigs();
    } catch (err) {
      toast(handleApiError(err, "Erreur lors de l'enregistrement"), { variant: "error" });
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (cfg: ReportConfig, next: boolean) => {
    setPendingId(cfg.id);
    setConfigs((arr) => arr.map((c) => (c.id === cfg.id ? { ...c, is_active: next } : c)));
    try {
      await apiClient.updateReportConfig(cfg.id, { is_active: next });
      toast(next ? "Planification activée" : "Planification suspendue", { variant: "success" });
    } catch (err) {
      setConfigs((arr) => arr.map((c) => (c.id === cfg.id ? { ...c, is_active: !next } : c)));
      toast(handleApiError(err, "Impossible de modifier le rapport"), { variant: "error" });
    } finally {
      setPendingId(null);
    }
  };

  const handleTrigger = async (cfg: ReportConfig) => {
    setRunningId(cfg.id);
    try {
      const res = await apiClient.triggerReport(cfg.id);
      toast(
        cfg.notification_recipients?.length
          ? `PDF généré et envoyé à ${cfg.notification_recipients.length} destinataire(s)`
          : `PDF généré : ${res.filename}`,
        { variant: "success" },
      );
      await Promise.all([loadConfigs(), loadHistory()]);
    } catch (err) {
      toast(handleApiError(err, "Échec de la génération du PDF"), { variant: "error" });
      void loadConfigs();
    } finally {
      setRunningId(null);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setPendingId(deleteTarget.id);
    try {
      await apiClient.deleteReportConfig(deleteTarget.id);
      setConfigs((arr) => arr.filter((c) => c.id !== deleteTarget.id));
      toast("Rapport supprimé", { variant: "success" });
      setDeleteTarget(null);
    } catch (err) {
      toast(handleApiError(err, "Erreur lors de la suppression"), { variant: "error" });
    } finally {
      setPendingId(null);
    }
  };

  const frequencyOptions =
    FREQUENCIES.some((f) => f.value === form.interval_minutes) || !editing
      ? FREQUENCIES
      : [...FREQUENCIES, { value: form.interval_minutes, label: freqLabel(editing) }];

  return (
    <div>
      <PageHeader
        title="Rapports PDF"
        subtitle="Générez un PDF de votre tableau de bord à la demande ou planifiez son envoi automatique par e-mail."
        actions={
          <>
            <Button variant="outline" onClick={() => void loadAll()} disabled={loading}>
              <RefreshCw className={cn(loading && "animate-spin")} />
              Rafraîchir
            </Button>
            <Button onClick={openCreate} disabled={loading}>
              <Plus /> Nouveau rapport
            </Button>
          </>
        }
      />

      <PageBody>
        <JourneySteps role={role} current="report" />

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard
            label="Rapports planifiés"
            value={configs.length}
            icon={CalendarClock}
            tone="brand"
            loading={loading}
          />
          <StatCard
            label="Planifications actives"
            value={activeCount}
            hint={
              configs.length > activeCount ? `${configs.length - activeCount} en pause` : undefined
            }
            icon={CheckCircle2}
            tone="success"
            loading={loading}
          />
          <StatCard
            label="PDF disponibles"
            value={history.length}
            icon={FileDown}
            tone="info"
            loading={loading}
            onClick={() => setTab("history")}
            active={tab === "history"}
          />
          <StatCard
            label="Dernier PDF"
            value={<span className="text-base">{lastGenerated ?? "—"}</span>}
            icon={Clock}
            loading={loading}
          />
        </div>

        <Panel
          title={tab === "configs" ? "Planifications" : "PDF générés"}
          description={
            tab === "configs"
              ? "Chaque rapport exporte le tableau de bord d'une source au format PDF."
              : "Les 50 derniers PDF générés, du plus récent au plus ancien."
          }
          actions={
            <Segmented
              label="Vue des rapports"
              value={tab}
              onChange={setTab}
              options={[
                { value: "configs", label: "Planifications", count: configs.length },
                { value: "history", label: "PDF générés", count: history.length },
              ]}
            />
          }
          bodyClassName="p-0"
        >
          {loading ? (
            <LoadingState label="Chargement des rapports…" rows={3} className="p-5" />
          ) : tab === "configs" ? (
            configsError ? (
              <ErrorState
                message={configsError}
                onRetry={() => void loadConfigs()}
                className="m-5"
              />
            ) : configs.length === 0 ? (
              <EmptyState
                icon={FileText}
                title="Aucun rapport planifié"
                description="Créez un rapport pour recevoir le PDF de votre tableau de bord chaque jour, semaine ou mois."
                action={
                  <Button onClick={openCreate}>
                    <Plus /> Créer un rapport
                  </Button>
                }
                className="m-5"
              />
            ) : (
              <ul className="divide-y divide-border">
                {configs.map((cfg) => {
                  const running = runningId === cfg.id;
                  const pending = pendingId === cfg.id;
                  const recipients = cfg.notification_recipients || [];
                  return (
                    <li
                      key={cfg.id}
                      className={cn(
                        "flex flex-col gap-3 px-5 py-4 transition-colors hover:bg-secondary/40 lg:flex-row lg:items-center",
                        !cfg.is_active && "opacity-75",
                      )}
                    >
                      <div className="flex min-w-0 flex-1 items-start gap-3">
                        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-primary/15 text-primary-strong">
                          <FileText className="h-5 w-5" />
                        </span>
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="truncate font-medium text-foreground">{cfg.job_name}</p>
                            <StatusBadge tone={cfg.is_active ? "success" : "neutral"} dot>
                              {cfg.is_active ? "Actif" : "En pause"}
                            </StatusBadge>
                            {cfg.last_run_status === "success" && (
                              <StatusBadge tone="info">Dernier envoi réussi</StatusBadge>
                            )}
                            {cfg.last_run_status === "failed" && (
                              <StatusBadge tone="danger">Dernier envoi en échec</StatusBadge>
                            )}
                          </div>
                          <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                            <span className="inline-flex items-center gap-1">
                              <CalendarClock className="h-3.5 w-3.5" /> {freqLabel(cfg)}
                            </span>
                            {cfg.job_parameters?.source_name && (
                              <span className="inline-flex items-center gap-1">
                                <Database className="h-3.5 w-3.5" />{" "}
                                {cfg.job_parameters.source_name}
                              </span>
                            )}
                            <span className="inline-flex items-center gap-1">
                              <Mail className="h-3.5 w-3.5" />
                              {recipients.length === 0
                                ? "Sans envoi e-mail"
                                : `${recipients.length} destinataire${recipients.length > 1 ? "s" : ""}`}
                            </span>
                            <span>Dernière génération : {cfg.last_run_display}</span>
                            {cfg.is_active && cfg.next_run_at && (
                              <span>Prochaine : {formatDateTime(cfg.next_run_at)}</span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex shrink-0 flex-wrap items-center gap-1">
                        {canGenerate && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => void handleTrigger(cfg)}
                            disabled={running}
                          >
                            {running ? <Loader2 className="animate-spin" /> : <Play />}
                            {running ? "Génération…" : "Générer maintenant"}
                          </Button>
                        )}
                        <label className="ml-1 flex items-center gap-2 px-2 text-xs text-muted-foreground">
                          <Switch
                            checked={cfg.is_active}
                            onCheckedChange={(v) => void toggleActive(cfg, v)}
                            disabled={pending}
                            aria-label={
                              cfg.is_active
                                ? `Suspendre « ${cfg.job_name} »`
                                : `Activer « ${cfg.job_name} »`
                            }
                          />
                          <span className="hidden sm:inline">
                            {cfg.is_active ? "Actif" : "Pause"}
                          </span>
                        </label>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => openEdit(cfg)}
                          aria-label={`Modifier « ${cfg.job_name} »`}
                          title="Modifier"
                        >
                          <Edit3 />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="hover:bg-destructive/10 hover:text-destructive"
                          onClick={() => setDeleteTarget(cfg)}
                          aria-label={`Supprimer « ${cfg.job_name} »`}
                          title="Supprimer"
                        >
                          <Trash2 />
                        </Button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )
          ) : historyError ? (
            <ErrorState message={historyError} onRetry={() => void loadHistory()} className="m-5" />
          ) : history.length === 0 ? (
            <EmptyState
              icon={FileDown}
              title="Aucun PDF généré"
              description={
                canGenerate
                  ? "Lancez « Générer maintenant » sur un rapport planifié pour obtenir votre premier PDF."
                  : "Les PDF apparaîtront ici dès qu'un rapport aura été généré."
              }
              className="m-5"
            />
          ) : (
            <ul className="divide-y divide-border">
              {history.map((item) => {
                const cfgId = configIdFromFilename(item.filename);
                const name = cfgId ? configNames.get(cfgId) : undefined;
                return (
                  <li
                    key={item.filename}
                    className="flex items-center gap-4 px-5 py-3 transition-colors hover:bg-secondary/40"
                  >
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-red-50 text-red-700">
                      <FileDown className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-foreground">
                        {name ?? item.filename}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatDateTime(item.created_at * 1000)} · {formatSize(item.size_bytes)}
                        {name && <span className="hidden sm:inline"> · {item.filename}</span>}
                      </p>
                    </div>
                    <Button asChild size="sm" variant="outline">
                      <a href={getUrl(item.download_url)} download target="_blank" rel="noreferrer">
                        <Download /> <span className="hidden sm:inline">Télécharger</span>
                      </a>
                    </Button>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <InfoDisclosure title="Comment fonctionne la planification ?">
          <p>
            Un rapport planifié exporte le tableau de bord de la source choisie au format PDF, à la
            fréquence indiquée. Si des destinataires sont renseignés, le PDF leur est envoyé en
            pièce jointe par e-mail.
          </p>
          <p>
            Suspendez une planification pour arrêter les envois sans perdre sa configuration. «
            Générer maintenant » produit immédiatement un PDF, sans attendre la prochaine échéance.
          </p>
        </InfoDisclosure>
      </PageBody>

      <Dialog open={formOpen} onOpenChange={(open) => !saving && setFormOpen(open)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{editing ? "Modifier le rapport" : "Nouveau rapport"}</DialogTitle>
            <DialogDescription>
              Le PDF reprend le tableau de bord de la source sélectionnée.
            </DialogDescription>
          </DialogHeader>
          <form id="report-form" onSubmit={handleSubmit} className="space-y-4" noValidate>
            <FormField label="Nom du rapport" htmlFor="report-name" error={formErrors.job_name}>
              <input
                id="report-name"
                value={form.job_name}
                onChange={(e) => setForm((f) => ({ ...f, job_name: e.target.value }))}
                placeholder="Ex. : Synthèse hebdomadaire des ventes"
                className={fieldClass}
              />
            </FormField>
            <FormField
              label="Source de données"
              htmlFor="report-source"
              error={formErrors.source_id}
            >
              <select
                id="report-source"
                value={form.source_id}
                onChange={(e) => setForm((f) => ({ ...f, source_id: e.target.value }))}
                className={fieldClass}
              >
                <option value="">Sélectionner une source…</option>
                {sources.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
              {sources.length === 0 && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Aucune source disponible : importez d'abord des données.
                </p>
              )}
            </FormField>
            <FormField label="Fréquence" htmlFor="report-frequency">
              <select
                id="report-frequency"
                value={form.interval_minutes}
                onChange={(e) =>
                  setForm((f) => ({ ...f, interval_minutes: Number(e.target.value) }))
                }
                className={fieldClass}
              >
                {frequencyOptions.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            </FormField>
            <FormField
              label="Destinataires (facultatif)"
              htmlFor="report-recipients"
              error={formErrors.recipients}
              hint="Séparez les adresses par une virgule. Sans destinataire, le PDF est seulement archivé."
            >
              <input
                id="report-recipients"
                value={form.recipients}
                onChange={(e) => setForm((f) => ({ ...f, recipients: e.target.value }))}
                placeholder="direction@pme.fr, equipe@pme.fr"
                className={fieldClass}
              />
            </FormField>
          </form>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFormOpen(false)} disabled={saving}>
              Annuler
            </Button>
            <Button type="submit" form="report-form" disabled={saving}>
              {saving && <Loader2 className="animate-spin" />}
              {editing ? "Enregistrer" : "Planifier le rapport"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Supprimer ce rapport ?"
        description={`La planification « ${deleteTarget?.job_name ?? ""} » sera supprimée. Les PDF déjà générés restent disponibles.`}
        confirmLabel="Supprimer"
        destructive
        pending={pendingId !== null && pendingId === deleteTarget?.id}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
