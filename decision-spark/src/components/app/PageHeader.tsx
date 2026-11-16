import { Link, useLocation } from "@tanstack/react-router";
import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { can } from "@/lib/rbac";
import { findNavItem, JOURNEY } from "./nav";
import { StatusBadge } from "./kit";

/**
 * En-tête de page de l'application : section du parcours, titre, description et actions.
 * `roleLabel` reste accepté pour compatibilité et s'affiche en pastille s'il est fourni.
 */
export function PageHeader({
  title,
  subtitle,
  actions,
  roleLabel,
  eyebrow,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  roleLabel?: string;
  /** @deprecated la navigation latérale et le fil d'Ariane remplacent le bouton retour. */
  backLabel?: string;
  eyebrow?: string;
}) {
  const location = useLocation();
  const match = findNavItem(location.pathname);
  const section = eyebrow ?? match?.group.section;

  return (
    <div className="border-b border-border bg-card">
      <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 py-5 md:flex-row md:items-end md:justify-between md:px-8 md:py-6">
        <div className="min-w-0">
          {section && (
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary-strong">
              {section}
            </p>
          )}
          <div className="mt-1 flex flex-wrap items-center gap-3">
            <h1 className="font-display text-2xl font-bold tracking-tight text-foreground md:text-[28px]">
              {title}
            </h1>
            {roleLabel && <StatusBadge>{roleLabel}</StatusBadge>}
          </div>
          {subtitle && (
            <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-muted-foreground">
              {subtitle}
            </p>
          )}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}

/**
 * Parcours décisionnel Importer → Décider. Chaque étape mène à l'écran correspondant ;
 * les étapes inaccessibles au rôle courant sont affichées sans lien.
 */
export function JourneySteps({
  role,
  current,
  className,
}: {
  role: string | null | undefined;
  current?: string;
  className?: string;
}) {
  return (
    <nav aria-label="Parcours décisionnel" className={cn("overflow-x-auto", className)}>
      <ol className="flex min-w-max items-center gap-1">
        {JOURNEY.map((step, i) => {
          const allowed = can(role, step.cap);
          const isCurrent = step.key === current;
          const inner = (
            <>
              <span
                className={cn(
                  "grid h-6 w-6 place-items-center rounded-full text-[11px] font-bold tabular-nums",
                  isCurrent
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-secondary-foreground",
                )}
              >
                {i + 1}
              </span>
              <span>{step.label}</span>
            </>
          );
          return (
            <li key={step.key} className="flex items-center gap-1">
              {allowed ? (
                <Link
                  to={step.to}
                  aria-current={isCurrent ? "step" : undefined}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-full px-2.5 py-1.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    isCurrent
                      ? "text-foreground"
                      : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                  )}
                >
                  {inner}
                </Link>
              ) : (
                <span
                  className="inline-flex items-center gap-2 px-2.5 py-1.5 text-sm text-muted-foreground/70"
                  title="Non disponible pour votre rôle"
                >
                  {inner}
                </span>
              )}
              {i < JOURNEY.length - 1 && (
                <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/60" aria-hidden />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
