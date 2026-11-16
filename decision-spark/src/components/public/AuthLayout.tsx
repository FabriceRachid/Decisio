import { Link } from "@tanstack/react-router";
import { ArrowLeft, Check, Eye, EyeOff, ShieldCheck } from "lucide-react";
import { useState, type InputHTMLAttributes, type ReactNode } from "react";
import { Logo } from "@/components/Logo";

/** Champ de saisie sur fond nuit : contraste AA, focus visible en ambre. */
export const authInputClass =
  "w-full rounded-xl border border-white/15 bg-night px-3.5 py-3 text-sm text-ink placeholder:text-ink-subtle transition focus:border-cta focus:outline-none focus:ring-2 focus:ring-cta/30";

export const authSubmitClass =
  "inline-flex w-full items-center justify-center gap-2 rounded-xl bg-cta py-3 text-sm font-semibold text-cta-foreground shadow-cta transition hover:bg-cta-hover focus-ring-cta disabled:cursor-not-allowed disabled:opacity-60";

export const authSecondaryClass =
  "inline-flex w-full items-center justify-center gap-2 rounded-xl border border-white/20 py-3 text-sm font-semibold text-ink transition hover:bg-white/5 focus-ring-cta";

const reassurances = [
  "Vos fichiers Excel et CSV nettoyés automatiquement",
  "Vos indicateurs clés dans un tableau de bord clair",
  "Un assistant qui répond en français sur vos données",
];

export function AuthLayout({
  title,
  subtitle,
  back = { to: "/", label: "Accueil" },
  wide = false,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  back?: { to: "/" | "/login"; label: string };
  wide?: boolean;
  children: ReactNode;
}) {
  return (
    <main className="grid min-h-screen bg-night text-ink lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-public-hero p-12 lg:flex">
        <Link to="/" aria-label="Accueil DécisioBI" className="w-fit rounded-lg focus-ring-cta">
          <Logo />
        </Link>
        <div>
          <h2 className="font-brand text-3xl font-extrabold leading-tight tracking-tight text-ink xl:text-4xl">
            Transformez vos données dispersées en{" "}
            <span className="text-cta">décisions claires.</span>
          </h2>
          <ul className="mt-8 space-y-4">
            {reassurances.map((r) => (
              <li key={r} className="flex items-start gap-3 text-ink-muted">
                <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-emerald-400/15">
                  <Check className="h-3 w-3 text-emerald-400" />
                </span>
                {r}
              </li>
            ))}
          </ul>
        </div>
        <Link
          to="/securite"
          className="inline-flex w-fit items-center gap-2 text-sm text-ink-muted transition hover:text-ink"
        >
          <ShieldCheck className="h-4 w-4 text-emerald-400" /> Comment nous protégeons vos données
        </Link>
      </aside>

      <div className="flex min-h-screen flex-col px-6 py-6 sm:px-10">
        <div className="flex items-center justify-between">
          <Link
            to={back.to}
            className="inline-flex items-center gap-2 rounded-lg text-sm text-ink-muted transition hover:text-ink focus-ring-cta"
          >
            <ArrowLeft className="h-4 w-4" /> {back.label}
          </Link>
          <Link to="/" aria-label="Accueil DécisioBI" className="lg:hidden">
            <Logo size="sm" />
          </Link>
        </div>

        <div className="flex flex-1 items-center justify-center py-10">
          <div className={`w-full ${wide ? "max-w-xl" : "max-w-md"}`}>
            <h1 className="font-brand text-3xl font-bold tracking-tight text-ink">{title}</h1>
            {subtitle && (
              <div className="mt-2 text-sm leading-relaxed text-ink-muted">{subtitle}</div>
            )}
            <div className="mt-8">{children}</div>
          </div>
        </div>
      </div>
    </main>
  );
}

export function AuthField({
  id,
  label,
  hint,
  children,
}: {
  id: string;
  label: string;
  hint?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-ink">
        {label}
      </label>
      <div className="relative mt-2">{children}</div>
      {hint && <p className="mt-1.5 text-xs text-ink-subtle">{hint}</p>}
    </div>
  );
}

export function PasswordInput(props: Omit<InputHTMLAttributes<HTMLInputElement>, "type">) {
  const [visible, setVisible] = useState(false);
  return (
    <>
      <input
        {...props}
        type={visible ? "text" : "password"}
        className={`${authInputClass} pr-11`}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Masquer le mot de passe" : "Afficher le mot de passe"}
        className="absolute inset-y-0 right-0 grid w-11 place-items-center rounded-r-xl text-ink-subtle transition hover:text-ink focus-ring-cta"
      >
        {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </>
  );
}

export function AuthError({ title, message }: { title: string; message: string }) {
  return (
    <div
      role="alert"
      className="mb-6 rounded-xl border border-red-400/40 bg-red-500/10 px-4 py-3 text-sm"
    >
      <p className="font-semibold text-red-200">{title}</p>
      <p className="mt-1 text-red-100">{message}</p>
    </div>
  );
}
