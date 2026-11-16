import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { ArrowRight, KeyRound } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";
import { apiClient, handleApiError } from "@/lib/api";
import { toast } from "@/lib/toast";
import {
  AuthError,
  AuthField,
  AuthLayout,
  PasswordInput,
  authSubmitClass,
} from "@/components/public/AuthLayout";

export const Route = createFileRoute("/reset-password")({
  validateSearch: (search: Record<string, unknown>) => ({
    uid: typeof search.uid === "string" ? search.uid : "",
    token: typeof search.token === "string" ? search.token : "",
  }),
  component: ResetPasswordPage,
  head: () => ({ meta: [{ title: "Réinitialiser le mot de passe — DécisioBI" }] }),
});

function ResetPasswordPage() {
  const navigate = useNavigate();
  const { uid, token } = Route.useSearch();
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isLinkValid = useMemo(() => Boolean(uid && token), [uid, token]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();

    if (!isLinkValid) {
      setErrorMessage("Le lien de réinitialisation est incomplet ou invalide.");
      return;
    }

    if (password !== passwordConfirm) {
      setErrorMessage("Les deux mots de passe doivent être identiques.");
      return;
    }

    try {
      setLoading(true);
      setErrorMessage(null);
      await apiClient.confirmPasswordReset({
        uid,
        token,
        new_password: password,
        new_password_confirm: passwordConfirm,
      });
      setDone(true);
      toast("Mot de passe réinitialisé", { variant: "success" });
    } catch (error) {
      const message = handleApiError(error, "Impossible de réinitialiser le mot de passe");
      setErrorMessage(message);
      toast(message, { variant: "error" });
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <AuthLayout
        title="Mot de passe mis à jour"
        back={{ to: "/login", label: "Retour à la connexion" }}
      >
        <div className="rounded-2xl border border-night-line bg-night-elevated p-6 text-center">
          <span className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-emerald-400/15 text-emerald-400">
            <KeyRound className="h-7 w-7" />
          </span>
          <p className="mt-5 text-sm leading-relaxed text-ink-muted">
            Votre mot de passe a été réinitialisé. Vous pouvez maintenant vous connecter avec vos
            nouveaux identifiants.
          </p>
          <button onClick={() => navigate({ to: "/login" })} className={`${authSubmitClass} mt-6`}>
            Aller à la connexion <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Nouveau mot de passe"
      subtitle="Choisissez un mot de passe robuste, différent de vos anciens mots de passe."
      back={{ to: "/login", label: "Retour à la connexion" }}
    >
      {!isLinkValid && (
        <AuthError
          title="Lien invalide"
          message="Ce lien de réinitialisation est incomplet. Demandez un nouveau lien depuis la page « Mot de passe oublié »."
        />
      )}
      {errorMessage && <AuthError title="Réinitialisation impossible" message={errorMessage} />}
      <form onSubmit={submit} className="space-y-5">
        <AuthField id="reset-password" label="Nouveau mot de passe" hint="8 caractères minimum.">
          <PasswordInput
            id="reset-password"
            required
            minLength={8}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </AuthField>
        <AuthField id="reset-password-confirm" label="Confirmer le mot de passe">
          <PasswordInput
            id="reset-password-confirm"
            required
            minLength={8}
            autoComplete="new-password"
            value={passwordConfirm}
            onChange={(e) => setPasswordConfirm(e.target.value)}
          />
        </AuthField>
        <button type="submit" disabled={loading || !isLinkValid} className={authSubmitClass}>
          {loading ? "Réinitialisation…" : "Définir le nouveau mot de passe"}{" "}
          <ArrowRight className="h-4 w-4" />
        </button>
      </form>
    </AuthLayout>
  );
}
