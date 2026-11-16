import { Link } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import type { ReactNode } from "react";
import { Logo } from "@/components/Logo";
import { LEGAL_LINKS } from "@/lib/legal";

/** Bouton d'action principal du site public — seul élément en ambre. */
export const ctaClass =
  "group inline-flex items-center justify-center gap-2 rounded-full bg-cta font-semibold text-cta-foreground shadow-cta transition hover:bg-cta-hover focus-ring-cta";

/** Bouton secondaire : contour neutre, ne concurrence pas l'action principale. */
export const secondaryClass =
  "inline-flex items-center justify-center gap-2 rounded-full border border-white/20 font-medium text-ink transition hover:border-white/40 hover:bg-white/5 focus-ring-cta";

export function CtaArrow() {
  return <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />;
}

const navLinks = [
  { href: "/#fonctionnalites", label: "Fonctionnalités" },
  { href: "/#parcours", label: "Comment ça marche" },
  { href: "/securite", label: "Sécurité" },
  { href: "/#faq", label: "FAQ" },
];

export function PublicHeader() {
  return (
    <header className="relative z-20 mx-auto flex max-w-6xl items-center justify-between gap-6 px-6 py-5">
      <Link to="/" aria-label="Accueil DécisioBI" className="text-ink focus-ring-cta rounded-lg">
        <Logo />
      </Link>
      <nav
        aria-label="Navigation principale"
        className="hidden items-center gap-8 text-sm text-ink-muted lg:flex"
      >
        {navLinks.map((l) => (
          <a key={l.href} href={l.href} className="transition hover:text-ink">
            {l.label}
          </a>
        ))}
      </nav>
      <div className="flex items-center gap-2 sm:gap-3">
        <Link
          to="/login"
          className="rounded-full px-4 py-2 text-sm font-medium text-ink transition hover:bg-white/5 focus-ring-cta"
        >
          Connexion
        </Link>
        <Link to="/register" className={`${ctaClass} px-4 py-2 text-sm sm:px-5`}>
          Créer un espace
        </Link>
      </div>
    </header>
  );
}

function FooterColumn({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wider text-ink">{title}</p>
      <ul className="mt-4 space-y-3 text-sm text-ink-muted">{children}</ul>
    </div>
  );
}

export function PublicFooter() {
  return (
    <footer className="border-t border-night-line bg-night">
      <div className="mx-auto grid max-w-6xl gap-10 px-6 py-14 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
        <div>
          <Logo size="sm" className="text-ink" />
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-ink-muted">
            La plateforme qui transforme les fichiers Excel et CSV des PME en indicateurs clairs et
            en réponses en français.
          </p>
        </div>
        <FooterColumn title="Produit">
          <li>
            <a href="/#fonctionnalites" className="transition hover:text-ink">
              Fonctionnalités
            </a>
          </li>
          <li>
            <a href="/#parcours" className="transition hover:text-ink">
              Comment ça marche
            </a>
          </li>
          <li>
            <Link to="/securite" className="transition hover:text-ink">
              Sécurité
            </Link>
          </li>
        </FooterColumn>
        <FooterColumn title="Compte">
          <li>
            <Link to="/login" className="transition hover:text-ink">
              Connexion
            </Link>
          </li>
          <li>
            <Link to="/register" className="transition hover:text-ink">
              Créer un espace
            </Link>
          </li>
          <li>
            <Link to="/forgot-password" className="transition hover:text-ink">
              Mot de passe oublié
            </Link>
          </li>
        </FooterColumn>
        <FooterColumn title="Légal">
          {LEGAL_LINKS.map((l) => (
            <li key={l.to}>
              <Link to={l.to} className="transition hover:text-ink">
                {l.label}
              </Link>
            </li>
          ))}
        </FooterColumn>
      </div>
      <div className="border-t border-night-line">
        <p className="mx-auto max-w-6xl px-6 py-6 text-xs text-ink-subtle">
          © {new Date().getFullYear()} DécisioBI. Tous droits réservés.
        </p>
      </div>
    </footer>
  );
}
