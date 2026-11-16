import { createFileRoute } from "@tanstack/react-router";
import {
  BellRing,
  BellOff,
  CheckCheck,
  Edit3,
  Gauge,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { PageHeader } from "@/components/AppShell";
import { ConfirmDialog } from "@/components/app/ConfirmDialog";
import {
  EmptyState,
  ErrorState,
  FormField as Field,
  InfoDisclosure,
  LoadingState,
  PageBody,
  Panel,
  Segmented,
  StatCard,
  StatusBadge,
  type Tone,
  fieldClass,
  labelClass,
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
import {
  apiClient,
  handleApiError,
  type KPI,
  type KPIAlert,
  type KPIAlertChannel,
  type KPIAlertCondition,
  type KPIAlertPayload,
  type KPIAlertType,
} from "@/lib/api";
import { can, getCurrentUserProfile } from "@/lib/rbac";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/alerts")({
  beforeLoad: async () => {
    const { requireRoleAccess } = await import("@/lib/rbac");
    await requireRoleAccess("read:alerts");
  },
  component: AlertsPage,
  head: () => ({ meta: [{ title: "Alertes KPI — DécisioBI" }] }),
});

const ALERT_TYPE_LABELS: Record<KPIAlertType, string> = {
  threshold_breach: "Dépassement de seuil",
  anomaly: "Détection d'anomalie",
  scheduled: "Rapport programmé",
};

const CONDITION_LABELS: Record<KPIAlertCondition, string> = {
  above: "Supérieur à",
  below: "Inférieur à",
  equals: "Égal à",
  changed_by: "Variation d'au moins",
};

const CONDITION_SYMBOLS: Record<KPIAlertCondition, string> = {
  above: ">",
  below: "<",
  equals: "=",
  changed_by: "Δ ≥",
};

type Filter = "all" | "to_ack" | "active" | "paused";

type AlertForm = {
  kpi: number;
  alert_name: string;
  alert_type: KPIAlertType;
  condition_type: KPIAlertCondition;
  threshold: string;
  channels: KPIAlertChannel[];
  recipients: string;
  webhook_url: string;
  message_template: string;
  cooldown_minutes: string;
  is_active: boolean;
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const emptyForm = (kpiId = 0): AlertForm => ({
  kpi: kpiId,
  alert_name: "",
  alert_type: "threshold_breach",
  condition_type: "above",
  threshold: "",
  channels: ["email"],
  recipients: "",
  webhook_url: "",
  message_template: "",
  cooldown_minutes: "60",
  is_active: true,
});

function formatNumber(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString("fr-FR", { maximumFractionDigits: 4 }) : "—";
}

function formatDate(value?: string | null) {
  if (!value) return null;
  return new Date(value).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
}

/** Une alerte déclenchée reste « à acquitter » tant qu'aucun acquittement n'est postérieur au dernier déclenchement. */
function needsAck(alert: KPIAlert) {
  if (!alert.is_triggered) return false;
  if (!alert.acknowledged_at) return true;
  if (!alert.last_triggered_at) return false;
  return new Date(alert.acknowledged_at) < new Date(alert.last_triggered_at);
}

function conditionText(
  alert: Pick<KPIAlert, "condition_type" | "threshold_value" | "threshold_percent">,
) {
  const symbol = CONDITION_SYMBOLS[alert.condition_type] ?? alert.condition_type;
  if (alert.condition_type === "changed_by")
    return `${symbol} ${formatNumber(alert.threshold_percent)} %`;
  return `${symbol} ${formatNumber(alert.threshold_value)}`;
}

function alertState(alert: KPIAlert): { label: string; tone: Tone } {
  if (!alert.is_active) return { label: "En pause", tone: "neutral" };
  if (needsAck(alert)) return { label: "Déclenchée", tone: "danger" };
  if (alert.is_triggered) return { label: "Acquittée", tone: "info" };
  return { label: "Sous surveillance", tone: "success" };
}

function AlertsPage() {
  const [role, setRole] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<KPIAlert[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [kpisError, setKpisError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");

  const [formOpen, setFormOpen] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<AlertForm>(emptyForm());
  const [formErrors, setFormErrors] = useState<Partial<Record<keyof AlertForm, string>>>({});

  const [ackTarget, setAckTarget] = useState<KPIAlert | null>(null);
  const [ackNotes, setAckNotes] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<KPIAlert | null>(null);
  const [pendingId, setPendingId] = useState<number | null>(null);

  const canWrite = can(role, "write:data");

  useEffect(() => {
    getCurrentUserProfile()
      .then((p) => setRole(p.profile?.role ?? null))
      .catch(() => {});
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    const [alertsRes, kpisRes] = await Promise.allSettled([
      apiClient.getAlerts({ page_size: 100 }),
      apiClient.getKPIs({ page_size: 100 }),
    ]);
    if (alertsRes.status === "fulfilled") {
      setAlerts(alertsRes.value.results || []);
      setTotalCount(alertsRes.value.count ?? alertsRes.value.results?.length ?? 0);
    } else {
      setLoadError(handleApiError(alertsRes.reason, "Impossible de charger les alertes"));
    }
    if (kpisRes.status === "fulfilled") {
      setKpis(kpisRes.value.results || []);
      setKpisError(false);
    } else {
      setKpisError(true);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const counts = useMemo(
    () => ({
      all: alerts.length,
      to_ack: alerts.filter((a) => a.is_active && needsAck(a)).length,
      active: alerts.filter((a) => a.is_active).length,
      paused: alerts.filter((a) => !a.is_active).length,
    }),
    [alerts],
  );

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return alerts.filter((a) => {
      if (filter === "to_ack" && !(a.is_active && needsAck(a))) return false;
      if (filter === "active" && !a.is_active) return false;
      if (filter === "paused" && a.is_active) return false;
      if (!q) return true;
      return [a.alert_name, a.kpi_name, a.kpi_code].some((v) => v?.toLowerCase().includes(q));
    });
  }, [alerts, filter, query]);

  /* ───────────── Formulaire ───────────── */

  const openCreate = () => {
    setEditingId(null);
    setForm(emptyForm(kpis[0]?.id ?? 0));
    setFormErrors({});
    setFormOpen(true);
  };

  const openEdit = async (alert: KPIAlert) => {
    setEditingId(alert.id);
    setFormErrors({});
    setFormOpen(true);
    setFormLoading(true);
    try {
      const d = await apiClient.getAlert(String(alert.id));
      const isPercent = d.condition_type === "changed_by";
      setForm({
        kpi: d.kpi_detail?.id ?? 0,
        alert_name: d.alert_name,
        alert_type: d.alert_type,
        condition_type: d.condition_type,
        threshold: String((isPercent ? d.threshold_percent : d.threshold_value) ?? ""),
        channels: (d.notification_channels || []).filter(
          (c): c is KPIAlertChannel => c === "email" || c === "webhook",
        ),
        recipients: (d.recipients || []).join(", "),
        webhook_url: d.webhook_url || "",
        message_template: d.message_template || "",
        cooldown_minutes: String(d.cooldown_minutes ?? 60),
        is_active: d.is_active,
      });
    } catch (error) {
      toast(handleApiError(error, "Impossible de charger l'alerte"), { variant: "error" });
      setFormOpen(false);
    } finally {
      setFormLoading(false);
    }
  };

  const toggleChannel = (channel: KPIAlertChannel) =>
    setForm((f) => ({
      ...f,
      channels: f.channels.includes(channel)
        ? f.channels.filter((c) => c !== channel)
        : [...f.channels, channel],
    }));

  const validate = (): KPIAlertPayload | null => {
    const errors: Partial<Record<keyof AlertForm, string>> = {};
    const recipients = form.recipients
      .split(/[,;\s]+/)
      .map((r) => r.trim())
      .filter(Boolean);
    const threshold = Number(form.threshold.replace(",", "."));
    const cooldown = Number(form.cooldown_minutes);

    if (!form.alert_name.trim()) errors.alert_name = "Donnez un nom à l'alerte.";
    if (!form.kpi) errors.kpi = "Choisissez l'indicateur à surveiller.";
    if (form.threshold.trim() === "" || !Number.isFinite(threshold))
      errors.threshold = "Saisissez une valeur numérique.";
    if (!Number.isInteger(cooldown) || cooldown < 0)
      errors.cooldown_minutes = "Nombre entier de minutes (0 ou plus).";
    if (form.channels.includes("email")) {
      if (recipients.length === 0) errors.recipients = "Ajoutez au moins un destinataire.";
      else if (recipients.some((r) => !EMAIL_RE.test(r)))
        errors.recipients = "Une ou plusieurs adresses e-mail sont invalides.";
    }
    if (form.channels.includes("webhook") && !/^https?:\/\//i.test(form.webhook_url.trim()))
      errors.webhook_url = "URL http(s) requise pour le webhook.";

    setFormErrors(errors);
    if (Object.keys(errors).length > 0) return null;

    const isPercent = form.condition_type === "changed_by";
    return {
      kpi: form.kpi,
      alert_name: form.alert_name.trim(),
      alert_type: form.alert_type,
      condition_type: form.condition_type,
      threshold_value: isPercent ? null : threshold,
      threshold_percent: isPercent ? threshold : null,
      notification_channels: form.channels,
      recipients: form.channels.includes("email") ? recipients : [],
      webhook_url: form.channels.includes("webhook") ? form.webhook_url.trim() : null,
      message_template: form.message_template.trim() || null,
      is_active: form.is_active,
      cooldown_minutes: cooldown,
    };
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const payload = validate();
    if (!payload) return;
    setSaving(true);
    try {
      if (editingId) {
        await apiClient.updateAlert(String(editingId), payload);
        toast("Alerte mise à jour", { variant: "success" });
      } else {
        await apiClient.createAlert(payload);
        toast("Alerte créée : elle sera évaluée au prochain calcul du KPI", {
          variant: "success",
        });
      }
      setFormOpen(false);
      await loadData();
    } catch (error) {
      toast(handleApiError(error, "Erreur lors de l'enregistrement"), { variant: "error" });
    } finally {
      setSaving(false);
    }
  };

  /* ───────────── Actions de ligne ───────────── */

  const toggleActive = async (alert: KPIAlert, next: boolean) => {
    setPendingId(alert.id);
    setAlerts((arr) => arr.map((a) => (a.id === alert.id ? { ...a, is_active: next } : a)));
    try {
      await apiClient.patchAlert(String(alert.id), { is_active: next });
      toast(next ? "Surveillance réactivée" : "Alerte mise en pause", { variant: "success" });
    } catch (error) {
      setAlerts((arr) => arr.map((a) => (a.id === alert.id ? { ...a, is_active: !next } : a)));
      toast(handleApiError(error, "Impossible de modifier l'alerte"), { variant: "error" });
    } finally {
      setPendingId(null);
    }
  };

  const confirmAck = async () => {
    if (!ackTarget) return;
    setPendingId(ackTarget.id);
    try {
      const res = await apiClient.acknowledgeAlert(String(ackTarget.id), ackNotes.trim());
      setAlerts((arr) =>
        arr.map((a) =>
          a.id === ackTarget.id ? { ...a, acknowledged_at: res.acknowledged_at } : a,
        ),
      );
      toast("Alerte acquittée", { variant: "success" });
      setAckTarget(null);
    } catch (error) {
      toast(handleApiError(error, "Impossible d'acquitter l'alerte"), { variant: "error" });
    } finally {
      setPendingId(null);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setPendingId(deleteTarget.id);
    try {
      await apiClient.deleteAlert(String(deleteTarget.id));
      setAlerts((arr) => arr.filter((a) => a.id !== deleteTarget.id));
      setTotalCount((n) => Math.max(0, n - 1));
      toast("Alerte supprimée", { variant: "success" });
      setDeleteTarget(null);
    } catch (error) {
      toast(handleApiError(error, "Erreur lors de la suppression"), { variant: "error" });
    } finally {
      setPendingId(null);
    }
  };

  const noKpi = !loading && !kpisError && kpis.length === 0;

  return (
    <div>
      <PageHeader
        title="Alertes KPI"
        subtitle="Soyez prévenu dès qu'un indicateur franchit un seuil ou varie brutalement."
        actions={
          <>
            <Button variant="outline" onClick={() => void loadData()} disabled={loading}>
              <RefreshCw className={cn(loading && "animate-spin")} />
              Rafraîchir
            </Button>
            {canWrite && (
              <Button onClick={openCreate} disabled={loading || kpis.length === 0}>
                <Plus /> Nouvelle alerte
              </Button>
            )}
          </>
        }
      />

      <PageBody>
        <InfoDisclosure title="Comment fonctionnent les alertes ?">
          <p>
            Chaque alerte surveille un indicateur (KPI). Elle est évaluée{" "}
            <strong className="text-foreground">à chaque nouveau calcul du KPI</strong> : si la
            condition est remplie (supérieur, inférieur ou égal à un seuil, ou variation d'au moins
            X % par rapport à la période précédente), l'alerte passe à l'état « Déclenchée » et une
            notification part par e-mail et/ou webhook.
          </p>
          <p>
            Le <strong className="text-foreground">délai de répit</strong> évite les notifications
            en rafale : tant qu'il n'est pas écoulé depuis le dernier déclenchement, l'alerte reste
            silencieuse. Acquittez une alerte déclenchée pour indiquer qu'elle a été prise en
            compte, avec une note facultative.
          </p>
        </InfoDisclosure>

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard
            label="Alertes configurées"
            value={totalCount}
            icon={BellRing}
            tone="brand"
            loading={loading}
            onClick={() => setFilter("all")}
            active={filter === "all"}
          />
          <StatCard
            label="À acquitter"
            value={counts.to_ack}
            hint="Déclenchées, non prises en compte"
            icon={Zap}
            tone={counts.to_ack > 0 ? "danger" : "neutral"}
            loading={loading}
            onClick={() => setFilter("to_ack")}
            active={filter === "to_ack"}
          />
          <StatCard
            label="Sous surveillance"
            value={counts.active}
            icon={Gauge}
            tone="success"
            loading={loading}
            onClick={() => setFilter("active")}
            active={filter === "active"}
          />
          <StatCard
            label="En pause"
            value={counts.paused}
            icon={BellOff}
            loading={loading}
            onClick={() => setFilter("paused")}
            active={filter === "paused"}
          />
        </div>

        <Panel
          title="Règles d'alerte"
          description={
            totalCount > alerts.length
              ? `${alerts.length} premières alertes affichées sur ${totalCount}`
              : "Indicateur surveillé, condition de déclenchement et état"
          }
          actions={
            <>
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Rechercher une alerte ou un KPI"
                  aria-label="Rechercher une alerte ou un KPI"
                  className={cn(fieldClass, "w-60 pl-8")}
                />
              </div>
              <Segmented
                label="Filtrer les alertes"
                value={filter}
                onChange={setFilter}
                options={[
                  { value: "all", label: "Toutes", count: counts.all },
                  { value: "to_ack", label: "À acquitter", count: counts.to_ack },
                  { value: "active", label: "Actives", count: counts.active },
                  { value: "paused", label: "En pause", count: counts.paused },
                ]}
              />
            </>
          }
          bodyClassName="p-0"
        >
          {loading ? (
            <LoadingState label="Chargement des alertes…" rows={4} className="p-5" />
          ) : loadError ? (
            <ErrorState message={loadError} onRetry={() => void loadData()} className="m-5" />
          ) : alerts.length === 0 ? (
            <EmptyState
              icon={BellRing}
              title="Aucune alerte configurée"
              description={
                noKpi
                  ? "Les alertes se rattachent à un indicateur KPI enregistré. Aucun KPI n'est encore disponible pour votre compte."
                  : canWrite
                    ? "Définissez un seuil sur un KPI pour être prévenu automatiquement lorsqu'il est franchi."
                    : "Aucune règle de surveillance n'a encore été définie par votre équipe."
              }
              action={
                canWrite && !noKpi ? (
                  <Button onClick={openCreate}>
                    <Plus /> Créer une alerte
                  </Button>
                ) : undefined
              }
              className="m-5"
            />
          ) : visible.length === 0 ? (
            <EmptyState
              icon={Search}
              title="Aucune alerte ne correspond"
              description="Modifiez la recherche ou le filtre pour afficher d'autres alertes."
              action={
                <Button
                  variant="outline"
                  onClick={() => {
                    setFilter("all");
                    setQuery("");
                  }}
                >
                  Réinitialiser
                </Button>
              }
              className="m-5"
            />
          ) : (
            <ul className="divide-y divide-border">
              {visible.map((alert) => {
                const state = alertState(alert);
                const pending = pendingId === alert.id;
                const lastTriggered = formatDate(alert.last_triggered_at);
                const acked = formatDate(alert.acknowledged_at);
                return (
                  <li
                    key={alert.id}
                    className={cn(
                      "flex flex-col gap-3 px-5 py-4 transition-colors hover:bg-secondary/40 md:flex-row md:items-center",
                      !alert.is_active && "opacity-75",
                    )}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate font-medium text-foreground">{alert.alert_name}</p>
                        <StatusBadge tone={state.tone} dot>
                          {state.label}
                        </StatusBadge>
                      </div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
                        <span className="inline-flex items-center gap-1.5">
                          <Gauge className="h-3.5 w-3.5" />
                          {alert.kpi_name || "KPI"}
                          {alert.kpi_code && (
                            <code className="rounded bg-secondary px-1.5 py-0.5 text-[11px]">
                              {alert.kpi_code}
                            </code>
                          )}
                        </span>
                        <span
                          className="rounded-md border border-border bg-card px-2 py-0.5 font-mono text-xs text-foreground"
                          title={CONDITION_LABELS[alert.condition_type]}
                        >
                          {conditionText(alert)}
                        </span>
                        <span className="text-xs">{ALERT_TYPE_LABELS[alert.alert_type]}</span>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {alert.trigger_count > 0
                          ? `Déclenchée ${alert.trigger_count} fois${lastTriggered ? ` · dernière le ${lastTriggered}` : ""}`
                          : "Jamais déclenchée"}
                        {acked && ` · acquittée le ${acked}`}
                      </p>
                    </div>

                    {canWrite && (
                      <div className="flex shrink-0 items-center gap-1">
                        {needsAck(alert) && alert.is_active && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setAckNotes("");
                              setAckTarget(alert);
                            }}
                            disabled={pending}
                          >
                            <CheckCheck /> Acquitter
                          </Button>
                        )}
                        <label className="ml-1 flex items-center gap-2 px-2 text-xs text-muted-foreground">
                          <Switch
                            checked={alert.is_active}
                            onCheckedChange={(v) => void toggleActive(alert, v)}
                            disabled={pending}
                            aria-label={
                              alert.is_active
                                ? `Mettre en pause « ${alert.alert_name} »`
                                : `Réactiver « ${alert.alert_name} »`
                            }
                          />
                          <span className="hidden sm:inline">
                            {alert.is_active ? "Active" : "Pause"}
                          </span>
                        </label>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => void openEdit(alert)}
                          aria-label={`Modifier « ${alert.alert_name} »`}
                          title="Modifier"
                        >
                          <Edit3 />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="hover:bg-destructive/10 hover:text-destructive"
                          onClick={() => setDeleteTarget(alert)}
                          aria-label={`Supprimer « ${alert.alert_name} »`}
                          title="Supprimer"
                        >
                          <Trash2 />
                        </Button>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>
      </PageBody>

      {/* Création / édition */}
      <Dialog open={formOpen} onOpenChange={(open) => !saving && setFormOpen(open)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{editingId ? "Modifier l'alerte" : "Nouvelle alerte"}</DialogTitle>
            <DialogDescription>
              Choisissez l'indicateur, la condition de déclenchement et la façon d'être prévenu.
            </DialogDescription>
          </DialogHeader>

          {formLoading ? (
            <LoadingState label="Chargement de la configuration…" rows={4} />
          ) : (
            <form id="alert-form" onSubmit={handleSubmit} className="space-y-5" noValidate>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Nom de l'alerte" htmlFor="alert-name" error={formErrors.alert_name}>
                  <input
                    id="alert-name"
                    value={form.alert_name}
                    onChange={(e) => setForm({ ...form, alert_name: e.target.value })}
                    placeholder="Ex. : CA mensuel sous l'objectif"
                    className={fieldClass}
                  />
                </Field>
                <Field label="Indicateur surveillé" htmlFor="alert-kpi" error={formErrors.kpi}>
                  <select
                    id="alert-kpi"
                    value={form.kpi || ""}
                    onChange={(e) => setForm({ ...form, kpi: Number(e.target.value) })}
                    className={fieldClass}
                  >
                    <option value="" disabled>
                      Sélectionner un KPI
                    </option>
                    {kpis.map((kpi) => (
                      <option key={kpi.id} value={kpi.id}>
                        {kpi.name} ({kpi.code})
                      </option>
                    ))}
                  </select>
                </Field>
              </div>

              <fieldset className="rounded-lg border border-border p-4">
                <legend className="px-1 text-[13px] font-medium text-foreground">
                  Condition de déclenchement
                </legend>
                <div className="grid gap-4 sm:grid-cols-3">
                  <Field label="Type" htmlFor="alert-type">
                    <select
                      id="alert-type"
                      value={form.alert_type}
                      onChange={(e) =>
                        setForm({ ...form, alert_type: e.target.value as KPIAlertType })
                      }
                      className={fieldClass}
                    >
                      {Object.entries(ALERT_TYPE_LABELS).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Condition" htmlFor="alert-condition">
                    <select
                      id="alert-condition"
                      value={form.condition_type}
                      onChange={(e) =>
                        setForm({ ...form, condition_type: e.target.value as KPIAlertCondition })
                      }
                      className={fieldClass}
                    >
                      {Object.entries(CONDITION_LABELS).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field
                    label={form.condition_type === "changed_by" ? "Variation (%)" : "Seuil"}
                    htmlFor="alert-threshold"
                    error={formErrors.threshold}
                  >
                    <input
                      id="alert-threshold"
                      inputMode="decimal"
                      value={form.threshold}
                      onChange={(e) => setForm({ ...form, threshold: e.target.value })}
                      placeholder={
                        form.condition_type === "changed_by" ? "Ex. : 15" : "Ex. : 50000"
                      }
                      className={fieldClass}
                    />
                  </Field>
                </div>
              </fieldset>

              <fieldset className="space-y-4 rounded-lg border border-border p-4">
                <legend className="px-1 text-[13px] font-medium text-foreground">
                  Notification
                </legend>
                <div className="flex flex-wrap gap-2" role="group" aria-label="Canaux">
                  {(["email", "webhook"] as KPIAlertChannel[]).map((channel) => {
                    const on = form.channels.includes(channel);
                    return (
                      <button
                        key={channel}
                        type="button"
                        aria-pressed={on}
                        onClick={() => toggleChannel(channel)}
                        className={cn(
                          "rounded-lg border px-3 py-1.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                          on
                            ? "border-primary bg-primary/10 text-primary-strong"
                            : "border-border text-muted-foreground hover:bg-secondary",
                        )}
                      >
                        {channel === "email" ? "E-mail" : "Webhook"}
                      </button>
                    );
                  })}
                </div>
                {form.channels.length === 0 && (
                  <p className="text-xs text-muted-foreground">
                    Sans canal, l'alerte change d'état sans envoyer de notification.
                  </p>
                )}
                {form.channels.includes("email") && (
                  <Field
                    label="Destinataires"
                    htmlFor="alert-recipients"
                    error={formErrors.recipients}
                    hint="Séparez les adresses par une virgule."
                  >
                    <input
                      id="alert-recipients"
                      value={form.recipients}
                      onChange={(e) => setForm({ ...form, recipients: e.target.value })}
                      placeholder="direction@pme.fr, compta@pme.fr"
                      className={fieldClass}
                    />
                  </Field>
                )}
                {form.channels.includes("webhook") && (
                  <Field
                    label="URL du webhook"
                    htmlFor="alert-webhook"
                    error={formErrors.webhook_url}
                  >
                    <input
                      id="alert-webhook"
                      type="url"
                      value={form.webhook_url}
                      onChange={(e) => setForm({ ...form, webhook_url: e.target.value })}
                      placeholder="https://…"
                      className={fieldClass}
                    />
                  </Field>
                )}
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field
                    label="Délai de répit (minutes)"
                    htmlFor="alert-cooldown"
                    error={formErrors.cooldown_minutes}
                  >
                    <input
                      id="alert-cooldown"
                      type="number"
                      min={0}
                      step={1}
                      value={form.cooldown_minutes}
                      onChange={(e) => setForm({ ...form, cooldown_minutes: e.target.value })}
                      className={fieldClass}
                    />
                  </Field>
                  <div className="flex items-end">
                    <label className="flex h-9 items-center gap-2.5 text-sm text-foreground">
                      <Switch
                        checked={form.is_active}
                        onCheckedChange={(v) => setForm({ ...form, is_active: v })}
                      />
                      Surveillance active
                    </label>
                  </div>
                </div>
                <Field label="Message personnalisé (facultatif)" htmlFor="alert-message">
                  <textarea
                    id="alert-message"
                    rows={2}
                    value={form.message_template}
                    onChange={(e) => setForm({ ...form, message_template: e.target.value })}
                    className={cn(fieldClass, "h-auto py-2")}
                  />
                </Field>
              </fieldset>
            </form>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setFormOpen(false)} disabled={saving}>
              Annuler
            </Button>
            <Button type="submit" form="alert-form" disabled={saving || formLoading}>
              {saving && <Loader2 className="animate-spin" />}
              {editingId ? "Enregistrer" : "Créer l'alerte"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Acquittement */}
      <Dialog
        open={ackTarget !== null}
        onOpenChange={(open) => !open && pendingId === null && setAckTarget(null)}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Acquitter l'alerte</DialogTitle>
            <DialogDescription>
              « {ackTarget?.alert_name} » sera marquée comme prise en compte. Elle redeviendra
              active au prochain déclenchement.
            </DialogDescription>
          </DialogHeader>
          <div>
            <label htmlFor="ack-notes" className={labelClass}>
              Note (facultatif)
            </label>
            <textarea
              id="ack-notes"
              rows={3}
              value={ackNotes}
              onChange={(e) => setAckNotes(e.target.value)}
              placeholder="Ex. : baisse liée à la fermeture estivale"
              className={cn(fieldClass, "h-auto py-2")}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setAckTarget(null)}
              disabled={pendingId !== null}
            >
              Annuler
            </Button>
            <Button onClick={() => void confirmAck()} disabled={pendingId !== null}>
              {pendingId !== null && <Loader2 className="animate-spin" />}
              Acquitter
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Supprimer cette alerte ?"
        description={`« ${deleteTarget?.alert_name ?? ""} » ne surveillera plus son indicateur. Cette action est irréversible.`}
        confirmLabel="Supprimer"
        destructive
        pending={pendingId !== null && pendingId === deleteTarget?.id}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
