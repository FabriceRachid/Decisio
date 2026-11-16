import { createFileRoute } from "@tanstack/react-router";
import {
  Activity,
  Clock,
  Edit3,
  Filter,
  KeyRound,
  Loader2,
  Mail,
  Plus,
  Search,
  ShieldCheck,
  Trash2,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { ConfirmDialog } from "@/components/app/ConfirmDialog";
import { PageHeader } from "@/components/app/PageHeader";
import {
  EmptyState,
  FormField,
  PageBody,
  Panel,
  SkeletonCards,
  StatCard,
  StatusBadge,
  fieldClass,
  type Tone,
} from "@/components/app/kit";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { apiClient, handleApiError, type AdminUser } from "@/lib/api";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/users")({
  beforeLoad: async () => {
    const { requireRoleAccess } = await import("@/lib/rbac");
    await requireRoleAccess("manage:users");
  },
  component: UsersPage,
  head: () => ({ meta: [{ title: "Utilisateurs — DécisioBI" }] }),
});

type Role = "admin" | "analyst" | "viewer";

interface ActivityItem {
  id: number;
  user?: { username?: string };
  action_type: string;
  resource_type: string;
  resource_name?: string;
  created_at: string;
}

const ROLE_CONFIG: Record<Role, { label: string; tone: Tone; desc: string }> = {
  admin: {
    label: "Admin",
    tone: "brand",
    desc: "Contrôle total : utilisateurs, configuration, imports, alertes et rapports.",
  },
  analyst: {
    label: "Analyste",
    tone: "info",
    desc: "Importation, nettoyage, analyse avancée, modélisation KPI et génération de rapports.",
  },
  viewer: {
    label: "Viewer",
    tone: "neutral",
    desc: "Consultation des dashboards, visualisation des analyses et lecture des rapports.",
  },
};

function formatTimeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = Math.floor((now - then) / 1000);
  if (diff < 60) return "à l'instant";
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)} h`;
  return `il y a ${Math.floor(diff / 86400)} j`;
}

function getInitials(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join("")
      .toUpperCase() || "U"
  );
}

function UsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<"Tous" | Role>("Tous");
  const [savingId, setSavingId] = useState<number | null>(null);

  // Dialogs state
  const [showInvite, setShowInvite] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [userToDelete, setUserToDelete] = useState<AdminUser | null>(null);
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);

  const [inviteForm, setInviteForm] = useState({
    username: "",
    name: "",
    email: "",
    password: "",
    role: "viewer" as Role,
  });

  const [editForm, setEditForm] = useState({
    first_name: "",
    last_name: "",
    username: "",
    email: "",
    role: "viewer" as Role,
    is_active: true,
    department: "",
    phone_number: "",
  });

  const [onlineUsers, setOnlineUsers] = useState<
    { user_id: number; username: string; page: string }[]
  >([]);
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [activityOpen, setActivityOpen] = useState(false);

  const onlineIds = useMemo(() => new Set(onlineUsers.map((u) => u.user_id)), [onlineUsers]);

  const loadUsers = useCallback(async () => {
    try {
      setLoading(true);
      const result = await apiClient.getAdminUsers();
      setUsers(result);
    } catch (error) {
      toast(handleApiError(error, "Impossible de charger les utilisateurs"), { variant: "error" });
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchPresence = useCallback(async () => {
    try {
      const [online, acts] = await Promise.all([
        apiClient.getOnlineUsers(),
        apiClient.getActivityFeed(20),
      ]);
      setOnlineUsers(online);
      setActivities(acts as ActivityItem[]);
    } catch {
      // silencieux pour le polling
    }
  }, []);

  useEffect(() => {
    void loadUsers();
    void fetchPresence();
    const interval = setInterval(fetchPresence, 10000);
    return () => clearInterval(interval);
  }, [loadUsers, fetchPresence]);

  const filtered = useMemo(() => {
    return users.filter((user) => {
      const fullName = `${user.first_name || ""} ${user.last_name || ""}`.trim();
      const role = (user.profile?.role || "viewer") as Role;
      const q = query.toLowerCase().trim();
      const matchQuery =
        !q ||
        user.username.toLowerCase().includes(q) ||
        user.email.toLowerCase().includes(q) ||
        fullName.toLowerCase().includes(q);
      const matchRole = roleFilter === "Tous" || role === roleFilter;
      return matchQuery && matchRole;
    });
  }, [users, query, roleFilter]);

  const activeSelected = useMemo(() => {
    if (selectedUser && users.some((u) => u.id === selectedUser.id)) {
      return users.find((u) => u.id === selectedUser.id) || null;
    }
    return filtered[0] || users[0] || null;
  }, [selectedUser, users, filtered]);

  const createUser = async (e: FormEvent) => {
    e.preventDefault();
    if (!inviteForm.username.trim() || !inviteForm.email.trim() || !inviteForm.password.trim()) {
      toast("Veuillez renseigner tous les champs obligatoires", { variant: "warning" });
      return;
    }

    try {
      setSavingId(-1);
      const [firstName, ...rest] = inviteForm.name.trim().split(/\s+/).filter(Boolean);
      await apiClient.createAdminUser({
        username: inviteForm.username.trim(),
        email: inviteForm.email.trim(),
        password: inviteForm.password,
        first_name: firstName || inviteForm.name.trim(),
        last_name: rest.join(" "),
        role: inviteForm.role,
      });
      toast("Utilisateur créé avec succès", { variant: "success" });
      setShowInvite(false);
      setInviteForm({ username: "", name: "", email: "", password: "", role: "viewer" });
      await loadUsers();
    } catch (error) {
      toast(handleApiError(error, "Impossible de créer l'utilisateur"), { variant: "error" });
    } finally {
      setSavingId(null);
    }
  };

  const openEdit = (user: AdminUser) => {
    setEditingUser(user);
    setEditForm({
      first_name: user.first_name || "",
      last_name: user.last_name || "",
      username: user.username,
      email: user.email,
      role: (user.profile?.role || "viewer") as Role,
      is_active: user.is_active,
      department: user.profile?.department || "",
      phone_number: user.profile?.phone_number || "",
    });
  };

  const saveEdit = async (e: FormEvent) => {
    e.preventDefault();
    if (!editingUser) return;

    try {
      setSavingId(editingUser.id);
      await apiClient.updateAdminUser(editingUser.id, {
        username: editForm.username,
        email: editForm.email,
        first_name: editForm.first_name,
        last_name: editForm.last_name,
        is_active: editForm.is_active,
        profile: {
          role: editForm.role,
          department: editForm.department || undefined,
          phone_number: editForm.phone_number || undefined,
        },
      });
      toast("Utilisateur mis à jour avec succès", { variant: "success" });
      setEditingUser(null);
      await loadUsers();
    } catch (error) {
      toast(handleApiError(error, "Impossible de modifier l'utilisateur"), { variant: "error" });
    } finally {
      setSavingId(null);
    }
  };

  const handleDeleteUser = async () => {
    if (!userToDelete) return;
    try {
      setSavingId(userToDelete.id);
      await apiClient.deleteAdminUser(userToDelete.id);
      toast("Utilisateur supprimé", { variant: "success" });
      setUserToDelete(null);
      await loadUsers();
    } catch (error) {
      toast(handleApiError(error, "Impossible de supprimer l'utilisateur"), { variant: "error" });
    } finally {
      setSavingId(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Gestion des utilisateurs"
        subtitle="Rôles, permissions et accès des membres de votre espace"
        actions={
          <Button onClick={() => setShowInvite(true)} className="gap-2">
            <Plus className="h-4 w-4" /> Nouvel utilisateur
          </Button>
        }
      />

      <PageBody>
        {/* Cartes statistiques */}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Utilisateurs totaux"
            value={users.length}
            icon={Users}
            tone="brand"
            loading={loading}
          />
          <StatCard
            label="En ligne maintenant"
            value={onlineUsers.length}
            icon={Activity}
            tone="success"
            hint="Présence active en direct"
            loading={loading}
          />
          <StatCard
            label="Rôles attribués"
            value={new Set(users.map((u) => u.profile?.role || "viewer")).size}
            icon={KeyRound}
            tone="info"
            hint="Admin, Analyste, Viewer"
            loading={loading}
          />
          <StatCard
            label="Administrateurs"
            value={users.filter((u) => u.profile?.role === "admin").length}
            icon={ShieldCheck}
            tone="warning"
            hint="Accès complet"
            loading={loading}
          />
        </div>

        {/* Barre de recherche et filtres */}
        <Panel className="p-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-1 items-center gap-2 rounded-lg border border-border bg-background px-3 py-1.5 focus-within:border-primary">
              <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Rechercher par nom, nom d'utilisateur ou e-mail…"
                className="w-full bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery("")}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  Effacer
                </button>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-1.5">
              <Filter className="h-4 w-4 text-muted-foreground" />
              {(["Tous", "admin", "analyst", "viewer"] as const).map((r) => {
                const active = roleFilter === r;
                return (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setRoleFilter(r)}
                    className={cn(
                      "rounded-lg px-3 py-1.5 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      active
                        ? "bg-primary text-primary-foreground shadow-sm"
                        : "bg-secondary/60 text-muted-foreground hover:bg-secondary hover:text-foreground",
                    )}
                  >
                    {r === "Tous" ? "Tous les rôles" : ROLE_CONFIG[r].label}
                  </button>
                );
              })}

              <Popover open={activityOpen} onOpenChange={setActivityOpen}>
                <PopoverTrigger asChild>
                  <Button variant="outline" size="sm" className="gap-2">
                    <Activity className="h-4 w-4" /> Activité récente
                  </Button>
                </PopoverTrigger>
                <PopoverContent align="end" className="w-80 p-0 shadow-lg">
                  <div className="flex items-center justify-between px-4 py-3">
                    <h4 className="text-sm font-semibold">Flux d'activité récent</h4>
                    <span className="text-xs text-muted-foreground">
                      {activities.length} actions
                    </span>
                  </div>
                  <Separator />
                  <ScrollArea className="h-[280px]">
                    {activities.length === 0 ? (
                      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-muted-foreground">
                        Aucune activité récente enregistrée
                      </div>
                    ) : (
                      <div className="divide-y divide-border/50 py-1">
                        {activities.map((a) => (
                          <div
                            key={a.id}
                            className="flex gap-3 px-4 py-2.5 hover:bg-muted/40 transition"
                          >
                            <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[10px] font-bold text-primary-strong">
                              {a.user?.username?.[0]?.toUpperCase() || "?"}
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="text-xs leading-snug">
                                <span className="font-semibold text-foreground">
                                  {a.user?.username || "Système"}
                                </span>{" "}
                                <span className="text-muted-foreground">
                                  {a.action_type === "create"
                                    ? "a créé"
                                    : a.action_type === "update"
                                      ? "a modifié"
                                      : a.action_type === "delete"
                                        ? "a supprimé"
                                        : a.action_type === "login"
                                          ? "s'est connecté"
                                          : a.action_type}
                                </span>{" "}
                                <span className="font-medium text-foreground">
                                  {a.resource_type}
                                </span>
                                {a.resource_name && (
                                  <span className="text-muted-foreground">
                                    {" "}
                                    «
                                    {a.resource_name.length > 25
                                      ? a.resource_name.slice(0, 25) + "…"
                                      : a.resource_name}
                                    »
                                  </span>
                                )}
                              </p>
                              <p className="mt-0.5 flex items-center gap-1 text-[10px] text-muted-foreground">
                                <Clock className="h-2.5 w-2.5" />
                                {formatTimeAgo(a.created_at)}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </ScrollArea>
                </PopoverContent>
              </Popover>
            </div>
          </div>
        </Panel>

        {/* Vue principale : Table + Panneau latéral détail */}
        <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
          {/* Table des utilisateurs */}
          <Panel
            title={
              <span className="flex items-center gap-2">
                <Users className="h-4 w-4 text-primary" />
                Membres de l'équipe ({filtered.length})
              </span>
            }
            bodyClassName="p-0"
          >
            {loading ? (
              <div className="p-6">
                <SkeletonCards count={4} />
              </div>
            ) : filtered.length === 0 ? (
              <EmptyState
                icon={Users}
                title="Aucun utilisateur trouvé"
                description={
                  query
                    ? "Aucun membre ne correspond à votre recherche."
                    : "Aucun utilisateur n'est configuré dans cet espace."
                }
                action={
                  query ? (
                    <Button variant="outline" size="sm" onClick={() => setQuery("")}>
                      Réinitialiser la recherche
                    </Button>
                  ) : undefined
                }
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-border bg-muted/40 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    <tr>
                      <th className="px-4 py-3">Utilisateur</th>
                      <th className="px-4 py-3">Rôle</th>
                      <th className="px-4 py-3">Statut</th>
                      <th className="px-4 py-3">Dernière connexion</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {filtered.map((user) => {
                      const role = (user.profile?.role || "viewer") as Role;
                      const roleConf = ROLE_CONFIG[role] || ROLE_CONFIG.viewer;
                      const fullName =
                        `${user.first_name || ""} ${user.last_name || ""}`.trim() || user.username;
                      const isOnline = onlineIds.has(user.id);
                      const isSelected = activeSelected?.id === user.id;

                      return (
                        <tr
                          key={user.id}
                          onClick={() => setSelectedUser(user)}
                          className={cn(
                            "cursor-pointer transition hover:bg-muted/30",
                            isSelected && "bg-primary/5",
                          )}
                        >
                          <td className="px-4 py-3.5">
                            <div className="flex items-center gap-3">
                              <div className="relative shrink-0">
                                <span className="grid h-9 w-9 place-items-center rounded-lg bg-primary text-xs font-bold text-primary-foreground shadow-sm">
                                  {getInitials(fullName)}
                                </span>
                                {isOnline && (
                                  <span
                                    className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-background bg-emerald-500"
                                    title="En ligne"
                                  />
                                )}
                              </div>
                              <div className="min-w-0">
                                <div className="flex items-center gap-2">
                                  <span className="font-semibold text-foreground truncate">
                                    {fullName}
                                  </span>
                                  {isOnline && (
                                    <span className="rounded-full bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
                                      En ligne
                                    </span>
                                  )}
                                </div>
                                <div className="text-xs text-muted-foreground truncate">
                                  {user.email}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-3.5">
                            <StatusBadge tone={roleConf.tone}>{roleConf.label}</StatusBadge>
                          </td>
                          <td className="px-4 py-3.5">
                            {user.is_active ? (
                              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-700">
                                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                                Actif
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                                <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground" />
                                Inactif
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3.5 text-xs text-muted-foreground">
                            {user.last_login
                              ? new Date(user.last_login).toLocaleDateString("fr-FR", {
                                  day: "numeric",
                                  month: "short",
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })
                              : "Jamais connecté"}
                          </td>
                          <td className="px-4 py-3.5 text-right">
                            <div
                              className="flex items-center justify-end gap-1"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => openEdit(user)}
                                disabled={savingId === user.id}
                                aria-label="Modifier l'utilisateur"
                                className="h-8 w-8 text-muted-foreground hover:text-foreground"
                              >
                                <Edit3 className="h-3.5 w-3.5" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => setUserToDelete(user)}
                                disabled={savingId === user.id}
                                aria-label="Supprimer l'utilisateur"
                                className="h-8 w-8 text-muted-foreground hover:text-destructive"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          {/* Panneau latéral détails et RBAC */}
          <div className="space-y-4">
            <Panel title="Détail du membre" icon={Users} className="sticky top-6">
              {activeSelected ? (
                <div className="space-y-5">
                  <div className="flex items-center gap-3">
                    <span className="grid h-12 w-12 place-items-center rounded-xl bg-primary text-base font-bold text-primary-foreground shadow-sm">
                      {getInitials(
                        `${activeSelected.first_name || ""} ${activeSelected.last_name || ""}`.trim() ||
                          activeSelected.username,
                      )}
                    </span>
                    <div className="min-w-0 flex-1">
                      <h3 className="font-semibold text-foreground truncate">
                        {`${activeSelected.first_name || ""} ${activeSelected.last_name || ""}`.trim() ||
                          activeSelected.username}
                      </h3>
                      <p className="text-xs text-muted-foreground truncate">
                        {activeSelected.email}
                      </p>
                      <div className="mt-1">
                        <StatusBadge
                          tone={
                            ROLE_CONFIG[(activeSelected.profile?.role || "viewer") as Role]?.tone ||
                            "neutral"
                          }
                        >
                          {ROLE_CONFIG[(activeSelected.profile?.role || "viewer") as Role]?.label ||
                            "Viewer"}
                        </StatusBadge>
                      </div>
                    </div>
                  </div>

                  <Separator />

                  <dl className="space-y-2.5 text-xs">
                    <div className="flex justify-between py-1">
                      <dt className="text-muted-foreground">ID utilisateur</dt>
                      <dd className="font-mono font-medium text-foreground">
                        #{activeSelected.id}
                      </dd>
                    </div>
                    <div className="flex justify-between py-1">
                      <dt className="text-muted-foreground">Nom d'utilisateur</dt>
                      <dd className="font-medium text-foreground">@{activeSelected.username}</dd>
                    </div>
                    <div className="flex justify-between py-1">
                      <dt className="text-muted-foreground">Statut</dt>
                      <dd className="font-medium">
                        {onlineIds.has(activeSelected.id) ? (
                          <span className="text-emerald-700 font-semibold">En ligne</span>
                        ) : activeSelected.is_active ? (
                          <span className="text-foreground">Actif</span>
                        ) : (
                          <span className="text-muted-foreground">Désactivé</span>
                        )}
                      </dd>
                    </div>
                    <div className="flex justify-between py-1">
                      <dt className="text-muted-foreground">Département</dt>
                      <dd className="font-medium text-foreground">
                        {activeSelected.profile?.department || "—"}
                      </dd>
                    </div>
                    <div className="flex justify-between py-1">
                      <dt className="text-muted-foreground">Téléphone</dt>
                      <dd className="font-medium text-foreground">
                        {activeSelected.profile?.phone_number || "—"}
                      </dd>
                    </div>
                    <div className="flex justify-between py-1">
                      <dt className="text-muted-foreground">Membre depuis</dt>
                      <dd className="font-medium text-foreground">
                        {activeSelected.date_joined
                          ? new Date(activeSelected.date_joined).toLocaleDateString("fr-FR", {
                              day: "numeric",
                              month: "short",
                              year: "numeric",
                            })
                          : "—"}
                      </dd>
                    </div>
                    <div className="flex justify-between py-1">
                      <dt className="text-muted-foreground">Dernière activité</dt>
                      <dd className="font-medium text-foreground">
                        {activeSelected.last_login
                          ? formatTimeAgo(activeSelected.last_login)
                          : "Jamais connecté"}
                      </dd>
                    </div>
                  </dl>

                  <div className="rounded-xl border border-border bg-secondary/30 p-3.5">
                    <h4 className="text-xs font-semibold text-foreground">
                      Description du rôle (
                      {ROLE_CONFIG[(activeSelected.profile?.role || "viewer") as Role]?.label})
                    </h4>
                    <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                      {ROLE_CONFIG[(activeSelected.profile?.role || "viewer") as Role]?.desc}
                    </p>
                  </div>

                  <div className="flex justify-end gap-2 pt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openEdit(activeSelected)}
                      className="gap-1.5"
                    >
                      <Edit3 className="h-3.5 w-3.5" /> Modifier
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Sélectionnez un utilisateur dans le tableau pour afficher son détail.
                </p>
              )}
            </Panel>

            <Panel title="Contrôle d'accès RBAC" icon={KeyRound}>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Les politiques de sécurité et les restrictions de routes sont validées côté backend
                via JWT et permissions Django REST Framework. Seuls les administrateurs peuvent
                inviter ou modifier les rôles.
              </p>
            </Panel>
          </div>
        </div>
      </PageBody>

      {/* Modal Inviter un membre */}
      <Dialog open={showInvite} onOpenChange={setShowInvite}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Inviter un nouveau membre</DialogTitle>
            <DialogDescription>
              Créez un compte pour un collaborateur et définissez son rôle d'accès.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={createUser} className="space-y-4">
            <FormField label="Nom complet *" htmlFor="invite-name">
              <input
                id="invite-name"
                required
                value={inviteForm.name}
                onChange={(e) => setInviteForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Ex. Aminata Ouedraogo"
                className={fieldClass}
              />
            </FormField>

            <FormField label="Nom d'utilisateur *" htmlFor="invite-username">
              <input
                id="invite-username"
                required
                value={inviteForm.username}
                onChange={(e) => setInviteForm((f) => ({ ...f, username: e.target.value }))}
                placeholder="aminata.ouedraogo"
                className={fieldClass}
              />
            </FormField>

            <FormField label="Adresse e-mail *" htmlFor="invite-email">
              <div className="relative">
                <Mail className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <input
                  id="invite-email"
                  required
                  type="email"
                  value={inviteForm.email}
                  onChange={(e) => setInviteForm((f) => ({ ...f, email: e.target.value }))}
                  placeholder="collaborateur@entreprise.bf"
                  className={cn(fieldClass, "pl-9")}
                />
              </div>
            </FormField>

            <FormField label="Mot de passe temporaire *" htmlFor="invite-password">
              <input
                id="invite-password"
                required
                type="password"
                value={inviteForm.password}
                onChange={(e) => setInviteForm((f) => ({ ...f, password: e.target.value }))}
                placeholder="Minimum 8 caractères"
                className={fieldClass}
              />
            </FormField>

            <FormField label="Rôle RBAC *" htmlFor="invite-role">
              <select
                id="invite-role"
                value={inviteForm.role}
                onChange={(e) => setInviteForm((f) => ({ ...f, role: e.target.value as Role }))}
                className={fieldClass}
              >
                <option value="viewer">Viewer — Lecture seule des tableaux et rapports</option>
                <option value="analyst">Analyste — Importation, nettoyage et modélisation</option>
                <option value="admin">Administrateur — Gestion complète de l'espace</option>
              </select>
            </FormField>

            <DialogFooter className="pt-2">
              <Button type="button" variant="outline" onClick={() => setShowInvite(false)}>
                Annuler
              </Button>
              <Button type="submit" disabled={savingId === -1}>
                {savingId === -1 ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <Plus className="h-4 w-4" />
                )}
                Créer le membre
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Modal Modifier l'utilisateur */}
      <Dialog open={!!editingUser} onOpenChange={(open) => !open && setEditingUser(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Modifier le collaborateur</DialogTitle>
            <DialogDescription>
              Mise à jour des coordonnées, rôle et état du compte.
            </DialogDescription>
          </DialogHeader>

          {editingUser && (
            <form onSubmit={saveEdit} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <FormField label="Prénom" htmlFor="edit-first-name">
                  <input
                    id="edit-first-name"
                    value={editForm.first_name}
                    onChange={(e) => setEditForm((f) => ({ ...f, first_name: e.target.value }))}
                    placeholder="Prénom"
                    className={fieldClass}
                  />
                </FormField>
                <FormField label="Nom" htmlFor="edit-last-name">
                  <input
                    id="edit-last-name"
                    value={editForm.last_name}
                    onChange={(e) => setEditForm((f) => ({ ...f, last_name: e.target.value }))}
                    placeholder="Nom"
                    className={fieldClass}
                  />
                </FormField>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <FormField label="Nom d'utilisateur *" htmlFor="edit-username">
                  <input
                    id="edit-username"
                    required
                    value={editForm.username}
                    onChange={(e) => setEditForm((f) => ({ ...f, username: e.target.value }))}
                    className={fieldClass}
                  />
                </FormField>
                <FormField label="E-mail *" htmlFor="edit-email">
                  <input
                    id="edit-email"
                    required
                    type="email"
                    value={editForm.email}
                    onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))}
                    className={fieldClass}
                  />
                </FormField>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <FormField label="Rôle *" htmlFor="edit-role">
                  <select
                    id="edit-role"
                    value={editForm.role}
                    onChange={(e) => setEditForm((f) => ({ ...f, role: e.target.value as Role }))}
                    className={fieldClass}
                  >
                    <option value="viewer">Viewer</option>
                    <option value="analyst">Analyste</option>
                    <option value="admin">Admin</option>
                  </select>
                </FormField>

                <FormField label="Département" htmlFor="edit-dept">
                  <input
                    id="edit-dept"
                    value={editForm.department}
                    onChange={(e) => setEditForm((f) => ({ ...f, department: e.target.value }))}
                    placeholder="Ex. Finance"
                    className={fieldClass}
                  />
                </FormField>
              </div>

              <FormField label="Téléphone" htmlFor="edit-phone">
                <input
                  id="edit-phone"
                  value={editForm.phone_number}
                  onChange={(e) => setEditForm((f) => ({ ...f, phone_number: e.target.value }))}
                  placeholder="+226 XX XX XX XX"
                  className={fieldClass}
                />
              </FormField>

              <div className="flex items-center justify-between rounded-xl border border-border p-3">
                <div>
                  <div className="text-sm font-semibold text-foreground">Statut du compte</div>
                  <div className="text-xs text-muted-foreground">
                    Autoriser la connexion à la plateforme DécisioBI
                  </div>
                </div>
                <Switch
                  checked={editForm.is_active}
                  onCheckedChange={(checked) => setEditForm((f) => ({ ...f, is_active: checked }))}
                />
              </div>

              <DialogFooter className="pt-2">
                <Button type="button" variant="outline" onClick={() => setEditingUser(null)}>
                  Annuler
                </Button>
                <Button type="submit" disabled={savingId === editingUser.id}>
                  {savingId === editingUser.id ? (
                    <Loader2 className="animate-spin" />
                  ) : (
                    "Enregistrer"
                  )}
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>

      {/* Confirmation de suppression */}
      <ConfirmDialog
        open={!!userToDelete}
        onOpenChange={(open) => !open && setUserToDelete(null)}
        title="Supprimer ce collaborateur ?"
        description={`Êtes-vous sûr de vouloir supprimer définitivement l'utilisateur ${userToDelete?.username} ? Cette action révoquera immédiatement tous ses accès.`}
        confirmLabel="Supprimer définitivement"
        destructive
        pending={savingId === userToDelete?.id}
        onConfirm={handleDeleteUser}
      />
    </div>
  );
}
