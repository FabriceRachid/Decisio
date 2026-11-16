import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { Activity as ActivityIcon, ArrowRight, Database, GitMerge, ScanSearch } from "lucide-react";
import { apiClient, handleApiError } from "@/lib/api";
import { can } from "@/lib/rbac";
import { type Activity, ActivityItem, formatTimeAgo } from "@/components/app/activity";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  Panel,
  SEVERITY_LABELS,
  StatCard,
  StatusBadge,
  severityTone,
} from "@/components/app/kit";

const OPEN_CONFLICT_STATUSES = ["detected", "investigating", "resolving"];

function useConflictStats(enabled: boolean) {
  return useQuery({
    queryKey: ["dashboard-insights", "conflicts"],
    queryFn: () => apiClient.getConflictDashboardStats(),
    enabled,
    staleTime: 30 * 1000,
  });
}

function useAnomalies(enabled: boolean) {
  return useQuery({
    queryKey: ["dashboard-insights", "anomalies"],
    queryFn: async () => {
      const [all, critical] = await Promise.all([
        apiClient.listAnomalies(1),
        apiClient.listAnomalies(1, "critical"),
      ]);
      return { count: all.count, critical: critical.count, latest: all.results.slice(0, 5) };
    },
    enabled,
    staleTime: 30 * 1000,
  });
}

/**
 * Bandeau de santé des données : sources validées, conflits à traiter, anomalies, qualité.
 * Chaque carte mène à l'écran qui permet d'agir.
 */
export function DashboardHealth({
  role,
  sourceCount,
  sourcesLoading,
  averageQuality,
  onNavigate,
}: {
  role: string | null | undefined;
  sourceCount: number;
  sourcesLoading?: boolean;
  averageQuality?: number;
  onNavigate: (to: "/app/import" | "/app/conflicts" | "/app/anomalies") => void;
}) {
  const canConflicts = can(role, "read:conflicts");
  const canAnomalies = can(role, "read:dashboard");
  const conflicts = useConflictStats(canConflicts);
  const anomalies = useAnomalies(canAnomalies);

  const byStatus = (conflicts.data?.by_status ?? {}) as Record<string, number>;
  const openConflicts = OPEN_CONFLICT_STATUSES.reduce((sum, s) => sum + (byStatus[s] || 0), 0);
  const resolutionRate = conflicts.data?.resolution_rate_percent as number | undefined;

  return (
    <section aria-label="Santé des données" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard
        label="Sources validées"
        value={sourceCount}
        hint={sourceCount ? "Prêtes pour l'analyse" : "Importez et validez une source"}
        icon={Database}
        tone="brand"
        loading={sourcesLoading}
        onClick={can(role, "write:data") ? () => onNavigate("/app/import") : undefined}
      />
      {canConflicts && (
        <StatCard
          label="Conflits à traiter"
          value={conflicts.isError ? "—" : openConflicts}
          hint={
            conflicts.isError
              ? "Statistiques indisponibles"
              : typeof resolutionRate === "number"
                ? `${Math.round(resolutionRate)} % résolus`
                : undefined
          }
          icon={GitMerge}
          tone={openConflicts > 0 ? "warning" : "success"}
          loading={conflicts.isLoading}
          onClick={() => onNavigate("/app/conflicts")}
        />
      )}
      {canAnomalies && (
        <StatCard
          label="Anomalies détectées"
          value={anomalies.isError ? "—" : (anomalies.data?.count ?? 0)}
          hint={
            anomalies.isError
              ? "Détection indisponible"
              : anomalies.data?.critical
                ? `dont ${anomalies.data.critical} critique${anomalies.data.critical > 1 ? "s" : ""}`
                : "Aucune anomalie critique"
          }
          icon={ScanSearch}
          tone={anomalies.data?.critical ? "danger" : "info"}
          loading={anomalies.isLoading}
          onClick={() => onNavigate("/app/anomalies")}
        />
      )}
      <StatCard
        label="Qualité moyenne"
        value={typeof averageQuality === "number" ? `${averageQuality} %` : "—"}
        hint={
          typeof averageQuality === "number"
            ? "Score des indicateurs affichés"
            : "Disponible avec un tableau de bord"
        }
        icon={ActivityIcon}
        tone={
          typeof averageQuality !== "number"
            ? "neutral"
            : averageQuality >= 80
              ? "success"
              : averageQuality >= 60
                ? "warning"
                : "danger"
        }
      />
    </section>
  );
}

/** Dernières anomalies et activité récente de l'espace de travail. */
export function DashboardSignals({ role }: { role: string | null | undefined }) {
  const canAnomalies = can(role, "read:dashboard");
  const anomalies = useAnomalies(canAnomalies);
  const activity = useQuery({
    queryKey: ["dashboard-insights", "activity"],
    queryFn: () => apiClient.getActivityFeed(8) as Promise<Activity[]>,
    staleTime: 30 * 1000,
  });

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {canAnomalies && (
        <Panel
          title="Dernières anomalies"
          description="Valeurs atypiques repérées par Isolation Forest"
          icon={ScanSearch}
          bodyClassName="p-0"
          actions={
            <Link
              to="/app/anomalies"
              className="inline-flex items-center gap-1 text-sm font-medium text-primary-strong hover:underline"
            >
              Tout voir <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          }
        >
          {anomalies.isLoading ? (
            <LoadingState className="p-5" rows={3} />
          ) : anomalies.isError ? (
            <ErrorState
              className="m-5"
              message={handleApiError(anomalies.error, "Les anomalies n'ont pas pu être chargées.")}
              onRetry={() => void anomalies.refetch()}
            />
          ) : !anomalies.data?.latest.length ? (
            <EmptyState
              className="m-5 py-8"
              icon={ScanSearch}
              title="Aucune anomalie"
              description="Lancez une détection depuis l'écran Anomalies pour surveiller vos données."
            />
          ) : (
            <ul className="divide-y divide-border">
              {anomalies.data.latest.map((a) => (
                <li key={a.id} className="flex items-center gap-3 px-5 py-3">
                  <StatusBadge tone={severityTone(a.severity)} dot>
                    {SEVERITY_LABELS[a.severity] || a.severity}
                  </StatusBadge>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">
                      {a.data_source_name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {a.outlier_count} valeur{a.outlier_count > 1 ? "s" : ""} atypique
                      {a.outlier_count > 1 ? "s" : ""} · {formatTimeAgo(a.detected_at)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      )}

      <Panel
        title="Activité récente"
        description="Dernières actions dans votre espace de travail"
        icon={ActivityIcon}
        bodyClassName="p-2"
        className={canAnomalies ? undefined : "lg:col-span-2"}
      >
        {activity.isLoading ? (
          <LoadingState className="p-3" rows={3} />
        ) : activity.isError ? (
          <ErrorState
            className="m-3"
            message={handleApiError(activity.error, "L'activité n'a pas pu être chargée.")}
            onRetry={() => void activity.refetch()}
          />
        ) : !activity.data?.length ? (
          <EmptyState
            className="m-3 py-8"
            icon={ActivityIcon}
            title="Aucune activité récente"
            description="Les imports, modifications et exports de votre équipe apparaîtront ici."
          />
        ) : (
          <div>
            {activity.data.map((item) => (
              <ActivityItem key={item.id} activity={item} className="rounded-lg" />
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
