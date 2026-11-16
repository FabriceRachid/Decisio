import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, MailCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { apiClient, handleApiError } from "@/lib/api";
import { toast } from "@/lib/toast";
import {
  AuthError,
  AuthField,
  AuthLayout,
  authInputClass,
  authSecondaryClass,
  authSubmitClass,
} from "@/components/public/AuthLayout";

export const Route = createFileRoute("/forgot-password")({
  component: ForgotPasswordPage,
  head: () => ({ meta: [{ title: "Mot de passe oublié — DécisioBI" }] }),
});

function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      setErrorMessage(null);
      await apiClient.requestPasswordReset(email.trim());
      setSent(true);
      toast("E-mail de réinitialisation envoyé", { variant: "success" });
    } catch (error) {
      const message = handleApiError(error, "Impossible d'envoyer l'e-mail de réinitialisation");
      setErrorMessage(message);
      toast(message, { variant: "error" });
    } finally {
      setLoading(false);
    }
  };

  if (sent) {
    return (
      <AuthLayout
        title="Vérifiez votre boîte e-mail"
        back={{ to: "/login", label: "Retour à la connexion" }}
      >
        <div className="rounded-2xl border border-night-line bg-night-elevated p-6 text-center">
          <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-emerald-400/15 text-emerald-400">
            <MailCheck className="h-7 w-7" />
          </span>
          <p className="mt-5 text-sm leading-relaxed text-ink-muted">
            Si un compte est associé à <span className="font-semibold text-ink">{email}</span>, vous
            recevrez un lien de réinitialisation dans quelques instants. Pensez à vérifier vos
            courriers indésirables.
          </p>
          <Link to="/login" className={`${authSecondaryClass} mt-6`}>
            Retour à la connexion
          </Link>
          <button onClick={() => setSent(false)} className="mt-4 text-sm text-data hover:underline">
            Utiliser une autre adresse
          </button>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Mot de passe oublié"
      subtitle="Indiquez votre adresse e-mail : nous vous enverrons un lien pour choisir un nouveau mot de passe."
      back={{ to: "/login", label: "Retour à la connexion" }}
    >
      {errorMessage && <AuthError title="Envoi impossible" message={errorMessage} />}
      <form onSubmit={submit} className="space-y-5">
        <AuthField id="forgot-email" label="Adresse e-mail">
          <input
            id="forgot-email"
            required
            type="email"
            autoComplete="email"
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="vous@entreprise.bf"
            className={authInputClass}
          />
        </AuthField>
        <button type="submit" disabled={loading} className={authSubmitClass}>
          {loading ? "Envoi en cours…" : "Envoyer le lien"} <ArrowRight className="h-4 w-4" />
        </button>
        <p className="text-center text-xs text-ink-subtle">
          Pour votre sécurité, le lien est personnel et ne peut servir qu'une fois.
        </p>
      </form>
    </AuthLayout>
  );
}
