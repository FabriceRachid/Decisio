import type { LucideIcon } from "lucide-react";
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Inbox,
  Loader2,
  RefreshCw,
} from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/* ─────────────────────────── Mise en page ─────────────────────────── */

/** Conteneur standard du contenu d'une page, sous le PageHeader. */
export function PageBody({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn("mx-auto w-full max-w-[1440px] space-y-6 px-4 py-6 md:px-8", className)}>
      {children}
    </div>
  );
}

/** Carte structurée avec en-tête optionnel (titre, description, icône, actions). */
export function Panel({
  title,
  description,
  icon: Icon,
  actions,
  className,
  bodyClassName,
  children,
}: {
  title?: ReactNode;
  description?: ReactNode;
  icon?: LucideIcon;
  actions?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children?: ReactNode;
}) {
  const hasHeader = title || description || actions;
  return (
    <section className={cn("rounded-xl border border-border bg-card shadow-card", className)}>
      {hasHeader && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-5 py-4">
          <div className="flex min-w-0 items-start gap-3">
            {Icon && (
              <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-secondary text-secondary-foreground">
                <Icon className="h-4 w-4" />
              </span>
            )}
            <div className="min-w-0">
              {title && (
                <h2 className="font-display text-[15px] font-semibold leading-6 text-foreground">
                  {title}
                </h2>
              )}
              {description && <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>}
            </div>
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      {children !== undefined && <div className={cn("p-5", bodyClassName)}>{children}</div>}
    </section>
  );
}

/* ─────────────────────────── Indicateurs ─────────────────────────── */

export type Tone = "neutral" | "brand" | "info" | "success" | "warning" | "danger";

const toneIcon: Record<Tone, string> = {
  neutral: "bg-secondary text-secondary-foreground",
  brand: "bg-primary/15 text-primary-strong",
  info: "bg-blue-50 text-blue-700",
  success: "bg-emerald-50 text-emerald-700",
  warning: "bg-amber-50 text-amber-800",
  danger: "bg-red-50 text-red-700",
};

/** Carte de statistique compacte : libellé, valeur, contexte. */
export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "neutral",
  loading,
  onClick,
  active,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: LucideIcon;
  tone?: Tone;
  loading?: boolean;
  onClick?: () => void;
  active?: boolean;
}) {
  const content = (
    <>
      <div className="flex items-start justify-between gap-3">
        <p className="text-[13px] font-medium text-muted-foreground">{label}</p>
        {Icon && (
          <span
            className={cn("grid h-8 w-8 shrink-0 place-items-center rounded-lg", toneIcon[tone])}
          >
            <Icon className="h-4 w-4" />
          </span>
        )}
      </div>
      {loading ? (
        <Skeleton className="mt-2 h-8 w-20" />
      ) : (
        <p className="mt-1 font-display text-2xl font-bold tracking-tight text-foreground tabular-nums">
          {value}
        </p>
      )}
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </>
  );
  const base = "rounded-xl border bg-card p-4 text-left shadow-card transition";
  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        aria-pressed={active}
        className={cn(
          base,
          "hover:border-input hover:shadow-widget-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          active ? "border-primary ring-1 ring-primary" : "border-border",
        )}
      >
        {content}
      </button>
    );
  }
  return <div className={cn(base, "border-border")}>{content}</div>;
}

const badgeTone: Record<Tone, string> = {
  neutral: "border-border bg-secondary text-secondary-foreground",
  brand: "border-primary/30 bg-primary/10 text-primary-strong",
  info: "border-blue-200 bg-blue-50 text-blue-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",
  warning: "border-amber-200 bg-amber-50 text-amber-800",
  danger: "border-red-200 bg-red-50 text-red-700",
};

/** Pastille de statut (gravité, état, rôle…). */
export function StatusBadge({
  tone = "neutral",
  dot,
  className,
  children,
}: {
  tone?: Tone;
  dot?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium",
        badgeTone[tone],
        className,
      )}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />}
      {children}
    </span>
  );
}

/** Libellés français des niveaux de gravité renvoyés par l'API. */
export const SEVERITY_LABELS: Record<string, string> = {
  critical: "Critique",
  high: "Élevée",
  medium: "Moyenne",
  low: "Faible",
};

/** Correspondance gravité → ton, partagée par conflits, anomalies et alertes. */
export function severityTone(severity?: string | null): Tone {
  switch ((severity || "").toLowerCase()) {
    case "critical":
    case "critique":
    case "high":
    case "haute":
    case "élevée":
      return "danger";
    case "medium":
    case "moyen":
    case "moyenne":
    case "warning":
      return "warning";
    case "low":
    case "faible":
    case "info":
      return "info";
    default:
      return "neutral";
  }
}

/* ─────────────────────────── États ─────────────────────────── */

/** État vide : explique pourquoi c'est vide et propose l'action suivante. */
export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className,
}: {
  icon?: LucideIcon;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-dashed border-input bg-card/60 px-6 py-12 text-center",
        className,
      )}
    >
      <span className="grid h-12 w-12 place-items-center rounded-xl bg-secondary text-secondary-foreground">
        <Icon className="h-5 w-5" />
      </span>
      <h3 className="mt-4 font-display text-base font-semibold text-foreground">{title}</h3>
      {description && (
        <p className="mt-1.5 max-w-md text-sm leading-relaxed text-muted-foreground">
          {description}
        </p>
      )}
      {action && <div className="mt-5 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  );
}

/** État d'erreur avec relance. */
export function ErrorState({
  title = "Impossible de charger ces données",
  message,
  onRetry,
  className,
}: {
  title?: string;
  message?: ReactNode;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 sm:flex-row sm:items-center",
        className,
      )}
    >
      <AlertCircle className="h-5 w-5 shrink-0 text-red-600" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-red-800">{title}</p>
        {message && <p className="mt-0.5 text-sm text-red-700">{message}</p>}
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw /> Réessayer
        </Button>
      )}
    </div>
  );
}

/** Bandeau de succès / information positive. */
export function SuccessNotice({
  title,
  message,
  action,
  className,
}: {
  title: string;
  message?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      role="status"
      className={cn(
        "flex flex-col items-start gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 sm:flex-row sm:items-center",
        className,
      )}
    >
      <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-emerald-900">{title}</p>
        {message && <p className="mt-0.5 text-sm text-emerald-800">{message}</p>}
      </div>
      {action}
    </div>
  );
}

/** Chargement d'un bloc : libellé explicite + squelette optionnel. */
export function LoadingState({
  label = "Chargement…",
  rows = 0,
  className,
}: {
  label?: string;
  rows?: number;
  className?: string;
}) {
  return (
    <div className={cn("space-y-3", className)} aria-busy="true" aria-live="polite">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> {label}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}

/** Grille de cartes squelettes pour les vues en cartes. */
export function SkeletonCards({ count = 4, className }: { count?: number; className?: string }) {
  return (
    <div className={cn("grid gap-4 sm:grid-cols-2 xl:grid-cols-4", className)} aria-hidden>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-xl border border-border bg-card p-4">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="mt-3 h-8 w-16" />
          <Skeleton className="mt-2 h-3 w-32" />
        </div>
      ))}
    </div>
  );
}

/* ─────────────────────────── Contrôles ─────────────────────────── */

/** Bloc pédagogique repliable (définitions, références, exemples). */
export function InfoDisclosure({
  icon: Icon = BookOpen,
  title,
  children,
  className,
}: {
  icon?: LucideIcon;
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <details className={cn("group rounded-xl border border-border bg-card shadow-card", className)}>
      <summary className="flex cursor-pointer list-none items-center gap-3 rounded-xl px-5 py-4 text-sm font-medium text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-blue-50 text-blue-700">
          <Icon className="h-4 w-4" />
        </span>
        <span className="flex-1">{title}</span>
        <ChevronRight className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-90" />
      </summary>
      <div className="space-y-3 border-t border-border px-5 py-4 text-sm leading-relaxed text-muted-foreground">
        {children}
      </div>
    </details>
  );
}

/** Groupe de boutons exclusifs (filtres, onglets compacts). */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
  className,
}: {
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: ReactNode; count?: number }[];
  label: string;
  className?: string;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cn(
        "inline-flex flex-wrap items-center gap-1 rounded-lg border border-border bg-card p-1",
        className,
      )}
    >
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(o.value)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active
                ? "bg-foreground text-background shadow-sm"
                : "text-muted-foreground hover:bg-secondary hover:text-foreground",
            )}
          >
            {o.label}
            {o.count !== undefined && (
              <span
                className={cn(
                  "rounded-full px-1.5 text-[10px] tabular-nums",
                  active ? "bg-background/20" : "bg-secondary",
                )}
              >
                {o.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/** Classes partagées pour les champs natifs (select, input) hors shadcn. */
export const fieldClass =
  "h-9 w-full rounded-lg border border-input bg-card px-3 text-sm text-foreground shadow-sm transition placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30 disabled:opacity-50";

export const labelClass = "mb-1.5 block text-[13px] font-medium text-foreground";

/** Champ de formulaire : libellé associé, contrôle, message d'erreur ou d'aide. */
export function FormField({
  label,
  htmlFor,
  error,
  hint,
  className,
  children,
}: {
  label: ReactNode;
  htmlFor: string;
  error?: string;
  hint?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className={labelClass}>
        {label}
      </label>
      {children}
      {error ? (
        <p className="mt-1 text-xs text-destructive" role="alert">
          {error}
        </p>
      ) : (
        hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  );
}
