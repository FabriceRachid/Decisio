import { Link } from "@tanstack/react-router";
import { AlertTriangle } from "lucide-react";
import type { ReactNode } from "react";
import { PublicFooter, PublicHeader } from "@/components/public/PublicShell";
import {
  LEGAL_LAST_UPDATED,
  LEGAL_LINKS,
  LEGAL_PUBLISHER,
  SUBPROCESSORS,
  isLegalPlaceholder,
} from "@/lib/legal";

const hasPendingLegalInfo =
  isLegalPlaceholder(LEGAL_LAST_UPDATED) ||
  Object.values(LEGAL_PUBLISHER).some(isLegalPlaceholder) ||
  SUBPROCESSORS.some((s) => isLegalPlaceholder(s.location));

type LegalLayoutProps = {
  eyebrow: string;
  title: string;
  intro: ReactNode;
  sections: { id: string; title: string }[];
  children: ReactNode;
};

export function LegalLayout({ eyebrow, title, intro, sections, children }: LegalLayoutProps) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="bg-public-hero text-ink">
        <PublicHeader />
        <div className="mx-auto max-w-6xl px-6 pb-14 pt-6">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cta">{eyebrow}</p>
          <h1 className="mt-3 font-brand text-4xl font-bold tracking-tight md:text-5xl">{title}</h1>
          <div className="mt-4 max-w-2xl text-sm leading-relaxed text-ink-muted md:text-base">
            {intro}
          </div>
          <p className="mt-6 text-xs text-ink-subtle">
            Dernière mise à jour : <LegalValue value={LEGAL_LAST_UPDATED} />
          </p>
        </div>
      </div>

      <div className="mx-auto grid max-w-6xl gap-10 px-6 py-12 lg:grid-cols-[220px_1fr]">
        <nav aria-label="Sommaire" className="hidden lg:block">
          <div className="sticky top-8">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Sommaire
            </p>
            <ol className="mt-4 space-y-2 border-l border-border text-sm">
              {sections.map((s) => (
                <li key={s.id}>
                  <a
                    href={`#${s.id}`}
                    className="-ml-px block border-l border-transparent pl-4 text-muted-foreground transition hover:border-primary hover:text-foreground"
                  >
                    {s.title}
                  </a>
                </li>
              ))}
            </ol>
          </div>
        </nav>

        <article className="min-w-0 max-w-3xl">
          {hasPendingLegalInfo && (
            <div
              role="note"
              className="mb-10 flex gap-3 rounded-xl border border-warning/40 bg-warning/10 p-4 text-sm text-warning-foreground"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <p>
                Document en cours de finalisation : certaines informations sur l'éditeur ou
                l'hébergement sont encore à compléter. Elles apparaissent surlignées ci-dessous.
              </p>
            </div>
          )}
          <div className="space-y-12">{children}</div>
        </article>
      </div>

      <PublicFooter />
    </div>
  );
}

export function LegalSection({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-8">
      <h2 className="font-brand text-2xl font-bold tracking-tight text-foreground">{title}</h2>
      <div className="mt-4 space-y-4 text-[15px] leading-relaxed text-foreground/80">
        {children}
      </div>
    </section>
  );
}

export function LegalList({ items }: { items: ReactNode[] }) {
  return (
    <ul className="list-disc space-y-2 pl-5 marker:text-primary-strong">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

/** Affiche une valeur légale, surlignée si elle reste à compléter. */
export function LegalValue({ value }: { value: string }) {
  if (!isLegalPlaceholder(value)) return <>{value}</>;
  return (
    <mark className="rounded bg-warning/25 px-1 py-0.5 text-inherit">{value.slice(1, -1)}</mark>
  );
}

export function LegalLinks({ className = "" }: { className?: string }) {
  return (
    <nav aria-label="Informations légales" className="flex flex-wrap gap-x-5 gap-y-2">
      {LEGAL_LINKS.map((l) => (
        <Link key={l.to} to={l.to} className={`transition ${className}`}>
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
