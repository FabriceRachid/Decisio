import { cn } from "@/lib/utils";

/** Entrée du fil d'activité (GET /api/conflits/activity-feed/). */
export interface Activity {
  id: number;
  user: { id: number; username: string; email: string; role: string };
  action_type: string;
  resource_type: string;
  resource_id: number | null;
  resource_name: string;
  action_details: Record<string, unknown>;
  created_at: string;
}

const ACTION_LABELS: Record<string, string> = {
  create: "a créé",
  update: "a modifié",
  delete: "a supprimé",
  login: "s'est connecté",
  logout: "s'est déconnecté",
  import: "a importé",
  export: "a exporté",
  read: "a consulté",
};

const RESOURCE_LABELS: Record<string, string> = {
  Dashboard: "le tableau de bord",
  Widget: "le widget",
  DataSource: "la source de données",
  CleaningRule: "la règle de nettoyage",
  CleaningPipeline: "le pipeline",
  CleaningJob: "le job de nettoyage",
  KPI: "le KPI",
  KPIAlert: "l'alerte KPI",
  AnomalyModel: "le modèle d'anomalie",
  Anomaly: "l'anomalie",
  Report: "le rapport",
  User: "le compte",
  UserProfile: "le profil",
  ConflictDetection: "la détection de conflits",
  ConflictResolution: "la résolution de conflits",
};

export function formatTimeAgo(dateStr: string): string {
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diff < 60) return "à l'instant";
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)} h`;
  return `il y a ${Math.floor(diff / 86400)} j`;
}

export function ActivityItem({ activity, className }: { activity: Activity; className?: string }) {
  const verb = ACTION_LABELS[activity.action_type] || activity.action_type;
  const resource = RESOURCE_LABELS[activity.resource_type] || activity.resource_type;
  const name = activity.resource_name || "";

  return (
    <div className={cn("flex gap-3 px-3 py-2.5", className)}>
      <div className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-primary/15 text-xs font-bold text-primary-strong">
        {activity.user?.username?.[0]?.toUpperCase() || "?"}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm leading-snug">
          <span className="font-semibold">{activity.user?.username}</span>{" "}
          <span className="text-muted-foreground">{verb}</span>{" "}
          <span className="font-medium">{resource}</span>
          {name && (
            <span className="text-muted-foreground">
              {" "}
              «{name.length > 30 ? `${name.slice(0, 30)}…` : name}»
            </span>
          )}
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          <time dateTime={activity.created_at}>{formatTimeAgo(activity.created_at)}</time>
        </p>
      </div>
    </div>
  );
}
