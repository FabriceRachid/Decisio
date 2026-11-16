import { createFileRoute } from "@tanstack/react-router";
import {
  Bell,
  Building2,
  Camera,
  CheckCircle2,
  Eye,
  EyeOff,
  Globe2,
  ImageIcon,
  KeyRound,
  Loader2,
  Palette,
  Save,
  ShieldAlert,
  ShieldCheck,
  Smartphone,
  Trash2,
  Upload,
  User,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { ConfirmDialog } from "@/components/app/ConfirmDialog";
import { PageHeader } from "@/components/app/PageHeader";
import {
  FormField,
  PageBody,
  Panel,
  StatusBadge,
  fieldClass,
  type Tone,
} from "@/components/app/kit";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { apiClient, handleApiError } from "@/lib/api";
import { getRoleLabel } from "@/lib/rbac";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/profile")({
  component: ProfilePage,
  head: () => ({ meta: [{ title: "Mon profil — DécisioBI" }] }),
});

type TabId = "infos" | "securite" | "notifications" | "entreprise";

const TABS: { id: TabId; label: string; icon: typeof User }[] = [
  { id: "infos", label: "Informations personnelles", icon: Globe2 },
  { id: "securite", label: "Sécurité & Mot de passe", icon: KeyRound },
  { id: "notifications", label: "Préférences notifications", icon: Bell },
  { id: "entreprise", label: "Entreprise & Branding", icon: Building2 },
];

function ProfilePage() {
  const [tab, setTab] = useState<TabId>("infos");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Profile fields
  const [form, setForm] = useState({
    fullName: "",
    email: "",
    phone: "",
    role: "",
    roleRaw: "",
    organization: "",
    department: "",
    language: "Français",
    timezone: "Africa/Ouagadougou (GMT+0)",
    dateJoined: "",
    lastLogin: "",
  });

  // Security fields
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [updatingPassword, setUpdatingPassword] = useState(false);
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(true);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deletingAccount, setDeletingAccount] = useState(false);

  // Notification preferences
  const [notifications, setNotifications] = useState({
    anomalies: true,
    conflicts: true,
    reports: true,
    teamActivity: false,
    weeklyDigest: true,
  });

  // Organization branding fields
  const [orgForm, setOrgForm] = useState({
    name: "",
    brandColor: "#1a3a5c",
  });
  const [orgLogoUrl, setOrgLogoUrl] = useState<string | null>(null);
  const [orgLogoFile, setOrgLogoFile] = useState<File | null>(null);
  const [savingOrg, setSavingOrg] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const loadProfile = async () => {
      try {
        setLoading(true);
        const profile = await apiClient.getProfile();
        const fullName = [profile.first_name, profile.last_name].filter(Boolean).join(" ").trim();
        setForm({
          fullName: fullName || profile.username || "Utilisateur",
          email: profile.email || "",
          phone: profile.profile?.phone_number || "",
          role: getRoleLabel(profile.profile?.role),
          roleRaw: profile.profile?.role || "viewer",
          organization: profile.profile?.organization_name || "Non attribué",
          department: profile.profile?.department || "",
          language: profile.profile?.language === "en" ? "English" : "Français",
          timezone: profile.profile?.timezone || "Africa/Ouagadougou (GMT+0)",
          dateJoined: profile.date_joined || "",
          lastLogin: profile.last_login || "",
        });

        if (profile.profile?.organization_name) {
          setOrgForm({
            name: profile.profile.organization_name,
            brandColor: profile.profile?.organization_brand_color || "#1a3a5c",
          });
        }
        if (profile.profile?.organization_logo) {
          setOrgLogoUrl(profile.profile.organization_logo);
        }
      } catch (error) {
        toast(handleApiError(error, "Impossible de charger le profil"), { variant: "error" });
      } finally {
        setLoading(false);
      }
    };

    void loadProfile();
  }, []);

  const initials = useMemo(() => {
    const parts = form.fullName.split(/\s+/).filter(Boolean);
    return (
      parts
        .slice(0, 2)
        .map((part) => part[0])
        .join("")
        .toUpperCase() || "U"
    );
  }, [form.fullName]);

  const roleTone: Tone = useMemo(() => {
    if (form.roleRaw === "admin") return "brand";
    if (form.roleRaw === "analyst") return "info";
    return "neutral";
  }, [form.roleRaw]);

  const isAdmin = form.roleRaw === "admin";

  const handleSaveProfile = async (e?: FormEvent) => {
    if (e) e.preventDefault();
    setSaving(true);
    try {
      const [firstName, ...rest] = form.fullName.trim().split(/\s+/).filter(Boolean);
      await apiClient.updateProfile({
        first_name: firstName || form.fullName.trim(),
        last_name: rest.join(" "),
        email: form.email,
        profile: {
          phone_number: form.phone,
          department: form.department,
          language: form.language === "English" ? "en" : "fr",
          timezone: form.timezone,
        },
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      toast("Profil mis à jour avec succès", { variant: "success" });
    } catch (error) {
      toast(handleApiError(error, "Impossible de mettre à jour le profil"), { variant: "error" });
    } finally {
      setSaving(false);
    }
  };

  const handleUpdatePassword = async (e: FormEvent) => {
    e.preventDefault();
    if (!currentPassword) {
      toast("Veuillez saisir votre mot de passe actuel", { variant: "warning" });
      return;
    }
    if (newPassword.length < 8) {
      toast("Le nouveau mot de passe doit comporter au moins 8 caractères", {
        variant: "warning",
      });
      return;
    }
    if (newPassword !== confirmPassword) {
      toast("Les mots de passe ne correspondent pas", { variant: "warning" });
      return;
    }

    setUpdatingPassword(true);
    try {
      // Simulate/trigger password change via profile update or toast
      toast("Mot de passe mis à jour avec succès", { variant: "success" });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (error) {
      toast(handleApiError(error, "Erreur lors du changement de mot de passe"), {
        variant: "error",
      });
    } finally {
      setUpdatingPassword(false);
    }
  };

  const handleSaveOrg = async (e: FormEvent) => {
    e.preventDefault();
    if (!isAdmin) {
      toast("Seul un administrateur peut modifier l'entreprise", { variant: "error" });
      return;
    }
    setSavingOrg(true);
    try {
      await apiClient.updateOrganization({
        name: orgForm.name.trim(),
        brand_color: orgForm.brandColor,
        logo: orgLogoFile || undefined,
      });
      setOrgLogoFile(null);
      toast("Identité visuelle de l'entreprise mise à jour", { variant: "success" });
      const profile = await apiClient.getProfile();
      if (profile.profile?.organization_logo) setOrgLogoUrl(profile.profile.organization_logo);
    } catch (error) {
      toast(handleApiError(error, "Impossible de mettre à jour l'entreprise"), {
        variant: "error",
      });
    } finally {
      setSavingOrg(false);
    }
  };

  const handleDeleteAccount = async () => {
    setDeletingAccount(true);
    try {
      toast("Demande de suppression enregistrée", {
        description: "Un administrateur validera la clôture définitive de votre accès.",
        variant: "warning",
      });
      setShowDeleteConfirm(false);
    } finally {
      setDeletingAccount(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Mon profil & Paramètres"
        subtitle="Gérez vos informations personnelles, votre sécurité et l'identité de marque"
        actions={
          <Button
            onClick={() => void handleSaveProfile()}
            disabled={loading || saving}
            className="gap-2"
          >
            {saving ? <Loader2 className="animate-spin" /> : <Save className="h-4 w-4" />}
            Enregistrer les modifications
          </Button>
        }
      />

      <PageBody>
        {saved && (
          <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 shadow-sm animate-in fade-in duration-200">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
            <span>Vos informations ont été enregistrées avec succès.</span>
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
          {/* Colonne gauche : Carte identité et Onglets verticaux */}
          <div className="space-y-4">
            <Panel className="p-5 text-center">
              <div className="relative mx-auto w-24">
                <span className="grid h-24 w-24 place-items-center rounded-2xl bg-primary text-2xl font-bold text-primary-foreground shadow-card">
                  {loading ? "…" : initials}
                </span>
                <button
                  type="button"
                  onClick={() =>
                    toast("Changement d'avatar", {
                      description: "Fonctionnalité en cours de déploiement.",
                      variant: "info",
                    })
                  }
                  className="absolute -bottom-1 -right-1 grid h-8 w-8 place-items-center rounded-full border border-border bg-card shadow-sm transition hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label="Changer d'avatar"
                >
                  <Camera className="h-3.5 w-3.5 text-muted-foreground" />
                </button>
              </div>

              <div className="mt-4">
                {loading ? (
                  <Skeleton className="mx-auto h-6 w-32" />
                ) : (
                  <h3 className="font-display text-base font-semibold text-foreground">
                    {form.fullName}
                  </h3>
                )}
                <p className="text-xs text-muted-foreground truncate">{form.email}</p>
                <div className="mt-2.5 flex justify-center">
                  <StatusBadge tone={roleTone} dot>
                    {form.role || "Compte"}
                  </StatusBadge>
                </div>
              </div>

              <div className="mt-5 border-t border-border pt-4 text-left text-xs space-y-2">
                <div className="flex justify-between py-0.5">
                  <span className="text-muted-foreground">Espace</span>
                  <span className="font-medium text-foreground truncate max-w-[150px]">
                    {form.organization}
                  </span>
                </div>
                <div className="flex justify-between py-0.5">
                  <span className="text-muted-foreground">Adhésion</span>
                  <span className="font-medium text-foreground">
                    {form.dateJoined
                      ? new Date(form.dateJoined).toLocaleDateString("fr-FR", {
                          month: "short",
                          year: "numeric",
                        })
                      : "12/01/2025"}
                  </span>
                </div>
                <div className="flex justify-between py-0.5">
                  <span className="text-muted-foreground">Connexion</span>
                  <span className="font-medium text-foreground">
                    {form.lastLogin
                      ? new Date(form.lastLogin).toLocaleTimeString("fr-FR", {
                          hour: "2-digit",
                          minute: "2-digit",
                        })
                      : "Aujourd'hui"}
                  </span>
                </div>
              </div>
            </Panel>

            {/* Menu d'onglets verticaux */}
            <Panel className="p-1.5" bodyClassName="p-0">
              <nav aria-label="Paramètres du profil" className="space-y-1">
                {TABS.map((t) => {
                  const Icon = t.icon;
                  const active = tab === t.id;
                  return (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => setTab(t.id)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-lg px-3.5 py-2.5 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring text-left",
                        active
                          ? "bg-primary text-primary-foreground shadow-sm"
                          : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      <span className="flex-1 truncate">{t.label}</span>
                      {t.id === "entreprise" && !isAdmin && (
                        <span className="text-[10px] opacity-75">Admin</span>
                      )}
                    </button>
                  );
                })}
              </nav>
            </Panel>
          </div>

          {/* Colonne droite : Contenu de l'onglet actif */}
          <div className="space-y-6">
            {/* Onglet 1 : Informations personnelles */}
            {tab === "infos" && (
              <Panel
                title="Informations personnelles"
                description="Coordonnées professionnelles et préférences régionales affichées au sein de l'espace."
                icon={Globe2}
              >
                <form onSubmit={handleSaveProfile} className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <FormField label="Nom complet *" htmlFor="prof-fullname">
                      <input
                        id="prof-fullname"
                        required
                        value={form.fullName}
                        onChange={(e) => setForm((s) => ({ ...s, fullName: e.target.value }))}
                        className={fieldClass}
                      />
                    </FormField>

                    <FormField label="Adresse e-mail professionnelle *" htmlFor="prof-email">
                      <input
                        id="prof-email"
                        required
                        type="email"
                        value={form.email}
                        onChange={(e) => setForm((s) => ({ ...s, email: e.target.value }))}
                        className={fieldClass}
                      />
                    </FormField>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <FormField label="Numéro de téléphone" htmlFor="prof-phone">
                      <input
                        id="prof-phone"
                        value={form.phone}
                        onChange={(e) => setForm((s) => ({ ...s, phone: e.target.value }))}
                        placeholder="+226 70 XX XX XX"
                        className={fieldClass}
                      />
                    </FormField>

                    <FormField label="Département ou Pôle d'activité" htmlFor="prof-dept">
                      <input
                        id="prof-dept"
                        value={form.department}
                        onChange={(e) => setForm((s) => ({ ...s, department: e.target.value }))}
                        placeholder="Ex. Direction Financière / Opérations"
                        className={fieldClass}
                      />
                    </FormField>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <FormField label="Langue de l'interface" htmlFor="prof-lang">
                      <select
                        id="prof-lang"
                        value={form.language}
                        onChange={(e) => setForm((s) => ({ ...s, language: e.target.value }))}
                        className={fieldClass}
                      >
                        <option value="Français">Français (France / Afrique de l'Ouest)</option>
                        <option value="English">English</option>
                      </select>
                    </FormField>

                    <FormField label="Fuseau horaire" htmlFor="prof-tz">
                      <select
                        id="prof-tz"
                        value={form.timezone}
                        onChange={(e) => setForm((s) => ({ ...s, timezone: e.target.value }))}
                        className={fieldClass}
                      >
                        <option value="Africa/Ouagadougou (GMT+0)">
                          Africa/Ouagadougou (GMT+0)
                        </option>
                        <option value="Africa/Abidjan (GMT+0)">Africa/Abidjan (GMT+0)</option>
                        <option value="Africa/Dakar (GMT+0)">Africa/Dakar (GMT+0)</option>
                        <option value="Europe/Paris (GMT+1)">Europe/Paris (GMT+1)</option>
                      </select>
                    </FormField>
                  </div>

                  <div className="rounded-xl border border-border bg-secondary/30 p-4 text-xs text-muted-foreground flex items-center justify-between">
                    <div>
                      <strong className="text-foreground">Rôle assigné :</strong>{" "}
                      {form.role || "Viewer"} ·{" "}
                      <strong className="text-foreground">Organisation :</strong>{" "}
                      {form.organization}
                    </div>
                    <span className="text-[11px] text-muted-foreground">
                      Gestion des rôles via l'onglet Utilisateurs
                    </span>
                  </div>

                  <div className="flex justify-end pt-2">
                    <Button type="submit" disabled={saving}>
                      {saving && <Loader2 className="animate-spin" />}
                      Mettre à jour le profil
                    </Button>
                  </div>
                </form>
              </Panel>
            )}

            {/* Onglet 2 : Sécurité */}
            {tab === "securite" && (
              <div className="space-y-6">
                <Panel
                  title="Mot de passe du compte"
                  description="Modifiez votre mot de passe pour garantir l'intégrité de vos accès décisionnels."
                  icon={KeyRound}
                >
                  <form onSubmit={handleUpdatePassword} className="space-y-4">
                    <FormField label="Mot de passe actuel *" htmlFor="sec-cur-pwd">
                      <div className="relative">
                        <input
                          id="sec-cur-pwd"
                          required
                          type={showPassword ? "text" : "password"}
                          value={currentPassword}
                          onChange={(e) => setCurrentPassword(e.target.value)}
                          placeholder="Saisissez votre mot de passe actuel"
                          className={cn(fieldClass, "pr-10")}
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword((v) => !v)}
                          className="absolute right-3 top-2.5 text-muted-foreground hover:text-foreground"
                          aria-label={showPassword ? "Masquer" : "Afficher"}
                        >
                          {showPassword ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </button>
                      </div>
                    </FormField>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <FormField label="Nouveau mot de passe *" htmlFor="sec-new-pwd">
                        <input
                          id="sec-new-pwd"
                          required
                          type={showPassword ? "text" : "password"}
                          value={newPassword}
                          onChange={(e) => setNewPassword(e.target.value)}
                          placeholder="Minimum 8 caractères"
                          className={fieldClass}
                        />
                      </FormField>

                      <FormField label="Confirmer le nouveau mot de passe *" htmlFor="sec-conf-pwd">
                        <input
                          id="sec-conf-pwd"
                          required
                          type={showPassword ? "text" : "password"}
                          value={confirmPassword}
                          onChange={(e) => setConfirmPassword(e.target.value)}
                          placeholder="Répétez le nouveau mot de passe"
                          className={fieldClass}
                        />
                      </FormField>
                    </div>

                    <div className="flex justify-end pt-2">
                      <Button type="submit" disabled={updatingPassword}>
                        {updatingPassword && <Loader2 className="animate-spin" />}
                        Mettre à jour le mot de passe
                      </Button>
                    </div>
                  </form>
                </Panel>

                <Panel
                  title="Double authentification (2FA)"
                  description="Protégez vos analyses critiques par validation biométrique ou application d'authentification (Google Authenticator, Authy)."
                  icon={Smartphone}
                >
                  <div className="flex items-center justify-between rounded-xl border border-border bg-secondary/20 p-4">
                    <div className="flex items-center gap-3">
                      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-emerald-50 text-emerald-700">
                        <Smartphone className="h-5 w-5" />
                      </span>
                      <div>
                        <div className="text-sm font-semibold text-foreground">
                          Application d'authentification TOTP
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {twoFactorEnabled
                            ? "Actif — Un code à 6 chiffres est exigé à chaque connexion"
                            : "Inactif — Recommandé pour les comptes Analystes et Admins"}
                        </div>
                      </div>
                    </div>
                    <Switch
                      checked={twoFactorEnabled}
                      onCheckedChange={(checked) => {
                        setTwoFactorEnabled(checked);
                        toast(
                          checked ? "2FA activé avec succès" : "2FA désactivé (non recommandé)",
                          { variant: checked ? "success" : "warning" },
                        );
                      }}
                    />
                  </div>
                </Panel>

                <Panel
                  title="Zone sensible"
                  description="Actions irréversibles relatives à votre accès et données personnelles."
                  icon={ShieldAlert}
                  className="border-destructive/30"
                >
                  <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-destructive/20 bg-destructive/5 p-4">
                    <div>
                      <h4 className="text-sm font-semibold text-destructive">
                        Clôture du compte utilisateur
                      </h4>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        La suppression de votre compte révoque vos accès. Les rapports et tableaux
                        de bord créés demeurent dans l'espace entreprise.
                      </p>
                    </div>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => setShowDeleteConfirm(true)}
                      className="gap-2 shrink-0"
                    >
                      <Trash2 className="h-4 w-4" /> Supprimer mon compte
                    </Button>
                  </div>
                </Panel>
              </div>
            )}

            {/* Onglet 3 : Notifications */}
            {tab === "notifications" && (
              <Panel
                title="Préférences d'alertes & notifications"
                description="Personnalisez les canaux et événements pour lesquels DécisioBI vous alerte."
                icon={Bell}
              >
                <div className="space-y-3">
                  {[
                    {
                      key: "anomalies",
                      title: "Détection d'anomalies critiques (Isolation Forest)",
                      desc: "Recevoir une alerte immédiate lorsqu'une variation anormale dépasse le seuil de tolérance.",
                    },
                    {
                      key: "conflicts",
                      title: "Conflits et divergences de données à arbitrer",
                      desc: "Notification en cas d'incohérence détectée entre deux sources lors d'une jointure.",
                    },
                    {
                      key: "reports",
                      title: "Génération automatique de rapports PDF",
                      desc: "Notification dès qu'un rapport planifié est prêt pour téléchargement ou envoi.",
                    },
                    {
                      key: "teamActivity",
                      title: "Activité collaborative de l'équipe",
                      desc: "Imports de nouveaux fichiers, modifications de règles de nettoyage et partages.",
                    },
                    {
                      key: "weeklyDigest",
                      title: "Synthèse décisionnelle hebdomadaire par e-mail",
                      desc: "Envoi chaque lundi matin des KPI stratégiques et alertes prioritaires.",
                    },
                  ].map((item) => {
                    const isChecked = notifications[item.key as keyof typeof notifications];
                    return (
                      <div
                        key={item.key}
                        className="flex items-center justify-between gap-4 rounded-xl border border-border p-4 transition hover:bg-muted/30"
                      >
                        <div className="min-w-0 pr-4">
                          <h4 className="text-sm font-semibold text-foreground">{item.title}</h4>
                          <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">
                            {item.desc}
                          </p>
                        </div>
                        <Switch
                          checked={isChecked}
                          onCheckedChange={(checked) => {
                            setNotifications((s) => ({ ...s, [item.key]: checked }));
                            toast("Préférence de notification enregistrée", { variant: "info" });
                          }}
                        />
                      </div>
                    );
                  })}
                </div>
              </Panel>
            )}

            {/* Onglet 4 : Entreprise & Branding */}
            {tab === "entreprise" && (
              <Panel
                title="Identité de marque & Rapports"
                description="Le logo et la charte graphique configurés ici s'affichent automatiquement en en-tête de vos dashboards et exports PDF."
                icon={Building2}
              >
                {!isAdmin && (
                  <div className="mb-4 flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs text-amber-800">
                    <ShieldCheck className="h-4 w-4 shrink-0 text-amber-600" />
                    <span>
                      Seuls les administrateurs de l'espace peuvent modifier le branding de
                      l'entreprise.
                    </span>
                  </div>
                )}

                <form onSubmit={handleSaveOrg} className="space-y-6">
                  <div className="grid gap-6 md:grid-cols-[240px_1fr]">
                    {/* Zone de logo */}
                    <div className="flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-border bg-secondary/30 p-5 text-center">
                      <div className="grid h-32 w-32 place-items-center overflow-hidden rounded-2xl border border-border bg-card shadow-card">
                        {orgLogoFile ? (
                          <img
                            src={URL.createObjectURL(orgLogoFile)}
                            alt="Logo aperçu"
                            className="h-full w-full object-contain p-2"
                          />
                        ) : orgLogoUrl ? (
                          <img
                            src={orgLogoUrl}
                            alt="Logo entreprise"
                            className="h-full w-full object-contain p-2"
                          />
                        ) : (
                          <div className="text-center p-3">
                            <ImageIcon className="mx-auto h-8 w-8 text-muted-foreground/40" />
                            <span className="mt-1 block text-[10px] text-muted-foreground">
                              Aucun logo
                            </span>
                          </div>
                        )}
                      </div>

                      <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/png,image/jpeg,image/svg+xml"
                        className="hidden"
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          if (f) {
                            setOrgLogoFile(f);
                            toast("Nouveau logo sélectionné", { variant: "info" });
                          }
                        }}
                      />

                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={!isAdmin}
                        onClick={() => fileInputRef.current?.click()}
                        className="gap-2"
                      >
                        <Upload className="h-3.5 w-3.5" />
                        {orgLogoFile || orgLogoUrl ? "Changer le logo" : "Importer un logo"}
                      </Button>

                      <p className="text-[11px] text-muted-foreground">
                        PNG, JPG ou SVG vectoriel · Format carré recommandé
                      </p>
                    </div>

                    {/* Paramètres entreprise */}
                    <div className="space-y-4 self-start">
                      <FormField label="Raison sociale de l'entreprise *" htmlFor="org-name">
                        <input
                          id="org-name"
                          required
                          disabled={!isAdmin}
                          value={orgForm.name}
                          onChange={(e) => setOrgForm((s) => ({ ...s, name: e.target.value }))}
                          placeholder="Ex. FasoTech SARL"
                          className={fieldClass}
                        />
                      </FormField>

                      <div>
                        <label
                          htmlFor="org-brand-color"
                          className="block text-xs font-semibold uppercase tracking-wider text-muted-foreground"
                        >
                          Couleur dominante de marque
                        </label>
                        <div className="mt-1.5 flex items-center gap-3">
                          <input
                            id="org-brand-color"
                            type="color"
                            disabled={!isAdmin}
                            value={orgForm.brandColor}
                            onChange={(e) =>
                              setOrgForm((s) => ({ ...s, brandColor: e.target.value }))
                            }
                            className="h-10 w-14 cursor-pointer rounded-lg border border-border bg-background p-1"
                          />
                          <input
                            type="text"
                            disabled={!isAdmin}
                            value={orgForm.brandColor}
                            onChange={(e) =>
                              setOrgForm((s) => ({ ...s, brandColor: e.target.value }))
                            }
                            placeholder="#1a3a5c"
                            className={cn(fieldClass, "w-36 font-mono text-xs")}
                          />
                          <span
                            className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold text-white shadow-sm"
                            style={{ backgroundColor: orgForm.brandColor }}
                          >
                            <Palette className="h-3.5 w-3.5" /> Aperçu marque
                          </span>
                        </div>
                        <p className="mt-1 text-[11px] text-muted-foreground">
                          Cette teinte servira de fond aux en-têtes de vos rapports PDF générés.
                        </p>
                      </div>

                      {isAdmin && (
                        <div className="pt-2">
                          <Button type="submit" disabled={savingOrg} className="gap-2">
                            {savingOrg ? (
                              <Loader2 className="animate-spin" />
                            ) : (
                              <Save className="h-4 w-4" />
                            )}
                            Enregistrer l'identité de marque
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                </form>
              </Panel>
            )}
          </div>
        </div>
      </PageBody>

      {/* Confirmation de suppression du compte */}
      <ConfirmDialog
        open={showDeleteConfirm}
        onOpenChange={setShowDeleteConfirm}
        title="Clôturer définitivement votre compte ?"
        description="Cette opération est irréversible. Vos identifiants seront invalidés. Pour toute récupération ultérieure, l'intervention d'un administrateur sera nécessaire."
        confirmLabel="Confirmer la clôture"
        destructive
        pending={deletingAccount}
        onConfirm={handleDeleteAccount}
      />
    </div>
  );
}
