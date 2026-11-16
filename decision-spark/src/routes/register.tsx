import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ArrowRight, Check, Info } from "lucide-react";
import { useState, type FormEvent } from "react";
import { apiClient, handleApiError } from "@/lib/api";
import { toast } from "@/lib/toast";
import { clearCurrentUserProfileCache } from "@/lib/rbac";
import {
  AuthError,
  AuthField,
  AuthLayout,
  PasswordInput,
  authInputClass,
  authSubmitClass,
} from "@/components/public/AuthLayout";

export const Route = createFileRoute("/register")({
  component: RegisterPage,
  head: () => ({ meta: [{ title: "Créer un espace entreprise — DécisioBI" }] }),
});

const SECTORS = [
  "Commerce / Distribution",
  "Industrie / Production",
  "Services",
  "Agro-alimentaire",
  "Santé",
  "Logistique",
  "Autre",
];
const SIZES = ["1–10", "11–50", "51–200", "200+"];

function Stepper({ step }: { step: number }) {
  const labels = ["Entreprise", "Administrateur", "Validation"];
  return (
    <ol className="mb-8 flex items-center" aria-label={`Étape ${step} sur ${labels.length}`}>
      {labels.map((l, i) => {
        const idx = i + 1;
        const done = step > idx;
        const active = step === idx;
        return (
          <li
            key={l}
            className="flex flex-1 items-center gap-2 last:flex-none"
            aria-current={active ? "step" : undefined}
          >
            <span
              className={`grid h-8 w-8 shrink-0 place-items-center rounded-full text-sm font-semibold transition ${
                done
                  ? "bg-emerald-500 text-white"
                  : active
                    ? "bg-cta text-cta-foreground"
                    : "border border-white/20 text-ink-subtle"
              }`}
            >
              {done ? <Check className="h-4 w-4" /> : idx}
            </span>
            <span className={`text-sm ${active ? "font-semibold text-ink" : "text-ink-subtle"}`}>
              {l}
            </span>
            {i < labels.length - 1 && (
              <span className={`mx-3 h-px flex-1 ${done ? "bg-emerald-500/60" : "bg-white/15"}`} />
            )}
          </li>
        );
      })}
    </ol>
  );
}

function RegisterPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [form, setForm] = useState({
    username: "",
    company: "",
    sector: SECTORS[0],
    size: SIZES[1],
    country: "Burkina Faso",
    fullName: "",
    email: "",
    password: "",
    accept: false,
  });

  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) =>
    setForm((s) => ({ ...s, [k]: v }));

  const next = async (e: FormEvent) => {
    e.preventDefault();

    if (step < 3) {
      setStep(step + 1);
      return;
    }

    if (!form.accept) {
      toast("Vous devez accepter les conditions d'utilisation", { variant: "warning" });
      return;
    }

    if (!form.username.trim()) {
      toast("Le nom d'utilisateur est requis", { variant: "warning" });
      return;
    }

    try {
      setLoading(true);
      setErrorMessage(null);
      const [firstName, ...rest] = form.fullName.trim().split(/\s+/).filter(Boolean);
      const lastName = rest.join(" ");

      await apiClient.register({
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
        password_confirm: form.password,
        first_name: firstName || form.fullName.trim(),
        last_name: lastName,
        company_name: form.company.trim(),
        company_sector: form.sector,
        company_size: form.size,
        company_country: form.country.trim(),
      });

      clearCurrentUserProfileCache();
      if (typeof window !== "undefined") {
        window.dispatchEvent(new Event("decisio-profile-updated"));
      }
      toast("Compte créé avec succès", { variant: "success" });
      navigate({ to: "/app/dashboard" });
    } catch (error) {
      const message = handleApiError(error, "Création du compte impossible");
      setErrorMessage(message);
      toast(message, { variant: "error" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      wide
      title="Créez votre espace entreprise"
      subtitle={
        <>
          Le premier compte créé devient{" "}
          <span className="font-semibold text-ink">administrateur</span> de l'espace.
        </>
      }
    >
      <Stepper step={step} />

      {errorMessage && <AuthError title="L'inscription a échoué" message={errorMessage} />}

      <form onSubmit={next}>
        {step === 1 && (
          <div className="space-y-5">
            <AuthField id="reg-company" label="Nom de l'entreprise">
              <input
                id="reg-company"
                required
                autoComplete="organization"
                value={form.company}
                onChange={(e) => set("company", e.target.value)}
                placeholder="Ex. PME Sahel SARL"
                className={authInputClass}
              />
            </AuthField>

            <div className="grid gap-5 md:grid-cols-2">
              <SelectField
                id="reg-sector"
                label="Secteur d'activité"
                value={form.sector}
                onChange={(v) => set("sector", v)}
                options={SECTORS}
              />
              <SelectField
                id="reg-size"
                label="Nombre de collaborateurs"
                value={form.size}
                onChange={(v) => set("size", v)}
                options={SIZES}
              />
            </div>

            <AuthField id="reg-country" label="Pays / zone d'activité">
              <input
                id="reg-country"
                autoComplete="country-name"
                value={form.country}
                onChange={(e) => set("country", e.target.value)}
                className={authInputClass}
              />
            </AuthField>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-5">
            <div className="flex gap-3 rounded-xl border border-data/30 bg-data/10 px-4 py-3 text-sm text-ink-muted">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-data" />
              <p>
                Ce compte aura le rôle <strong className="text-ink">Administrateur</strong>. Il
                pourra ensuite inviter vos collaborateurs et choisir leurs droits.
              </p>
            </div>

            <div className="grid gap-5 md:grid-cols-2">
              <AuthField id="reg-fullname" label="Nom complet">
                <input
                  id="reg-fullname"
                  required
                  autoComplete="name"
                  value={form.fullName}
                  onChange={(e) => set("fullName", e.target.value)}
                  placeholder="Ex. Omar Konaté"
                  className={authInputClass}
                />
              </AuthField>

              <AuthField
                id="reg-username"
                label="Nom d'utilisateur"
                hint="Utilisé pour vous connecter."
              >
                <input
                  id="reg-username"
                  required
                  autoComplete="username"
                  value={form.username}
                  onChange={(e) => set("username", e.target.value)}
                  placeholder="Ex. omar.konate"
                  className={authInputClass}
                />
              </AuthField>
            </div>

            <AuthField id="reg-email" label="Adresse e-mail professionnelle">
              <input
                id="reg-email"
                required
                type="email"
                autoComplete="email"
                value={form.email}
                onChange={(e) => set("email", e.target.value)}
                placeholder="vous@entreprise.bf"
                className={authInputClass}
              />
            </AuthField>

            <AuthField id="reg-password" label="Mot de passe" hint="8 caractères minimum.">
              <PasswordInput
                id="reg-password"
                required
                minLength={8}
                autoComplete="new-password"
                value={form.password}
                onChange={(e) => set("password", e.target.value)}
              />
            </AuthField>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-5 text-sm">
            <div className="rounded-xl border border-night-line bg-night-elevated p-5">
              <p className="text-sm font-semibold text-ink">Récapitulatif</p>
              <dl className="mt-4 space-y-2.5">
                {[
                  ["Entreprise", form.company || "—"],
                  ["Secteur", form.sector],
                  ["Taille", `${form.size} collaborateurs`],
                  ["Pays", form.country],
                  ["Administrateur", form.fullName || "—"],
                  ["E-mail", form.email || "—"],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-4">
                    <dt className="text-ink-subtle">{k}</dt>
                    <dd className="text-right font-medium text-ink">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>

            <label htmlFor="reg-accept" className="flex items-start gap-3 text-ink-muted">
              <input
                id="reg-accept"
                type="checkbox"
                required
                checked={form.accept}
                onChange={(e) => set("accept", e.target.checked)}
                className="mt-0.5 h-4 w-4 shrink-0 accent-[#f5b02e]"
              />
              <span>
                J'accepte les{" "}
                <Link
                  to="/cgu"
                  target="_blank"
                  rel="noopener"
                  className="font-medium text-data hover:underline"
                >
                  conditions d'utilisation
                </Link>{" "}
                et la{" "}
                <Link
                  to="/confidentialite"
                  target="_blank"
                  rel="noopener"
                  className="font-medium text-data hover:underline"
                >
                  politique de confidentialité
                </Link>{" "}
                de DécisioBI.
              </span>
            </label>
          </div>
        )}

        <div className="mt-8 flex items-center gap-3">
          {step > 1 && (
            <button
              type="button"
              onClick={() => setStep((s) => Math.max(1, s - 1))}
              className="rounded-xl border border-white/20 px-5 py-3 text-sm font-medium text-ink transition hover:bg-white/5 focus-ring-cta"
            >
              Précédent
            </button>
          )}
          <button type="submit" disabled={loading} className={`${authSubmitClass} flex-1`}>
            {loading ? "Création…" : step < 3 ? "Continuer" : "Créer mon espace"}{" "}
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </form>

      <p className="mt-8 border-t border-night-line pt-6 text-center text-sm text-ink-muted">
        Déjà un espace ?{" "}
        <Link to="/login" className="font-semibold text-data hover:underline">
          Se connecter
        </Link>
      </p>
    </AuthLayout>
  );
}

function SelectField({
  id,
  label,
  value,
  onChange,
  options,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: readonly string[];
}) {
  return (
    <AuthField id={id} label={label}>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={authInputClass}
      >
        {options.map((o) => (
          <option key={o} value={o} className="bg-night text-ink">
            {o}
          </option>
        ))}
      </select>
    </AuthField>
  );
}
