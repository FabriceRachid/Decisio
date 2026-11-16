import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { apiClient, handleApiError } from "@/lib/api";
import { toast } from "@/lib/toast";
import { clearCurrentUserProfileCache } from "@/lib/rbac";
import {
  AuthField,
  AuthLayout,
  PasswordInput,
  authInputClass,
  authSubmitClass,
} from "@/components/public/AuthLayout";

export const Route = createFileRoute("/login")({
  component: LoginPage,
  head: () => ({ meta: [{ title: "Connexion — DécisioBI" }] }),
});

function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [pwd, setPwd] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    clearCurrentUserProfileCache();
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();

    try {
      setLoading(true);
      await apiClient.login(username.trim(), pwd);
      clearCurrentUserProfileCache();
      if (typeof window !== "undefined") {
        window.dispatchEvent(new Event("decisio-profile-updated"));
      }
      toast("Connexion réussie", { variant: "success" });
      navigate({ to: "/app/dashboard" });
    } catch (error) {
      toast(handleApiError(error, "Connexion impossible"), { variant: "error" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout title="Bon retour parmi nous" subtitle="Connectez-vous à votre espace DécisioBI.">
      <form onSubmit={submit} className="space-y-5">
        <AuthField id="login-username" label="Nom d'utilisateur">
          <input
            id="login-username"
            required
            autoComplete="username"
            autoFocus
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className={authInputClass}
            placeholder="Ex. omar.konate"
          />
        </AuthField>

        <div>
          <AuthField id="login-password" label="Mot de passe">
            <PasswordInput
              id="login-password"
              required
              autoComplete="current-password"
              value={pwd}
              onChange={(e) => setPwd(e.target.value)}
              placeholder="Votre mot de passe"
            />
          </AuthField>
          <div className="mt-2 text-right">
            <Link to="/forgot-password" className="text-sm text-data hover:underline">
              Mot de passe oublié ?
            </Link>
          </div>
        </div>

        <button type="submit" disabled={loading} className={authSubmitClass}>
          {loading ? "Connexion…" : "Se connecter"} <ArrowRight className="h-4 w-4" />
        </button>
      </form>

      <p className="mt-8 border-t border-night-line pt-6 text-center text-sm text-ink-muted">
        Pas encore d'espace entreprise ?{" "}
        <Link to="/register" className="font-semibold text-data hover:underline">
          Créer un espace
        </Link>
      </p>
    </AuthLayout>
  );
}
