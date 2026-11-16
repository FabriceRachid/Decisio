import { Link, useLocation, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, LogOut, Menu, UserCircle } from "lucide-react";
import type { ReactNode } from "react";
import { toast } from "@/lib/toast";
import { apiClient, handleApiError } from "@/lib/api";
import { Logo } from "@/components/Logo";
import { useIsMobile } from "@/hooks/use-mobile";
import { can, getCurrentUserProfile, getRoleLabel } from "@/lib/rbac";
import { NotificationBell } from "@/components/NotificationBell";
import { NAV_GROUPS, findNavItem } from "@/components/app/nav";
import { cn } from "@/lib/utils";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

export { PageHeader } from "@/components/app/PageHeader";

type ShellProfile = {
  name: string;
  email: string;
  rawRole: string | null;
  initials: string;
  loaded: boolean;
};

const INITIAL_PROFILE: ShellProfile = {
  name: "Chargement…",
  email: "",
  rawRole: null,
  initials: "…",
  loaded: false,
};

function useShellProfile() {
  const [profile, setProfile] = useState<ShellProfile>(INITIAL_PROFILE);

  useEffect(() => {
    let alive = true;
    const loadProfile = async () => {
      try {
        const user = await getCurrentUserProfile();
        const fullName = [user.first_name, user.last_name].filter(Boolean).join(" ").trim();
        const name = fullName || user.username || "Utilisateur";
        const initials = name
          .split(/\s+/)
          .filter(Boolean)
          .slice(0, 2)
          .map((part: string) => part[0])
          .join("")
          .toUpperCase();
        if (!alive) return;
        setProfile({
          name,
          email: user.email || "",
          rawRole: user.profile?.role ?? null,
          initials: initials || "U",
          loaded: true,
        });
      } catch (error) {
        if (!alive) return;
        console.error(handleApiError(error, "Impossible de charger le profil"));
        setProfile({ name: "Utilisateur", email: "", rawRole: null, initials: "U", loaded: true });
      }
    };
    loadProfile();
    return () => {
      alive = false;
    };
  }, []);

  return profile;
}

function useConflictBadge(pathname: string) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const stats = await apiClient.getConflictDashboardStats();
        if (!alive) return;
        const pending =
          Number(stats?.by_status?.detected || 0) +
          Number(stats?.by_status?.investigating || 0) +
          Number(stats?.by_status?.resolving || 0);
        setCount(Number.isFinite(pending) ? pending : 0);
      } catch (error) {
        if (!alive) return;
        console.error(handleApiError(error, "Impossible de charger le compteur de conflits"));
        setCount(0);
      }
    };
    load();
    const onChange = () => void load();
    if (typeof window !== "undefined") {
      window.addEventListener("focus", onChange);
      window.addEventListener("decisiobi:conflicts-changed", onChange);
    }
    return () => {
      alive = false;
      if (typeof window !== "undefined") {
        window.removeEventListener("focus", onChange);
        window.removeEventListener("decisiobi:conflicts-changed", onChange);
      }
    };
  }, [pathname]);

  return count;
}

function Avatar({ initials, className }: { initials: string; className?: string }) {
  return (
    <span
      className={cn(
        "grid h-8 w-8 shrink-0 place-items-center rounded-full bg-primary text-xs font-bold text-primary-foreground",
        className,
      )}
      aria-hidden
    >
      {initials}
    </span>
  );
}

function SidebarNav({
  role,
  conflictBadge,
  onNavigate,
}: {
  role: string | null;
  conflictBadge: number;
  onNavigate?: () => void;
}) {
  const location = useLocation();
  const groups = useMemo(
    () =>
      NAV_GROUPS.map((group) => ({
        ...group,
        items: group.items.filter((item) => can(role, item.cap)),
      })).filter((group) => group.items.length > 0),
    [role],
  );

  return (
    <nav aria-label="Navigation de l'application" className="flex-1 overflow-y-auto px-3 py-4">
      {groups.map((group) => (
        <div key={group.section} className="mb-5 last:mb-0">
          <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-subtle">
            {group.section}
          </p>
          <ul className="space-y-0.5">
            {group.items.map((item) => {
              const active =
                location.pathname === item.to || location.pathname.startsWith(`${item.to}/`);
              const Icon = item.icon;
              const badge = item.to === "/app/conflicts" && conflictBadge > 0 ? conflictBadge : 0;
              return (
                <li key={item.to}>
                  <Link
                    to={item.to}
                    onClick={onNavigate}
                    title={item.hint}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring",
                      active
                        ? "bg-sidebar-accent text-sidebar-accent-foreground"
                        : "text-sidebar-foreground hover:bg-white/5 hover:text-sidebar-accent-foreground",
                    )}
                  >
                    {active && (
                      <span
                        className="absolute inset-y-1.5 left-0 w-[3px] rounded-r-full bg-sidebar-primary"
                        aria-hidden
                      />
                    )}
                    <Icon
                      className={cn(
                        "h-4 w-4 shrink-0 transition",
                        active ? "text-sidebar-primary" : "text-ink-subtle group-hover:text-ink",
                      )}
                    />
                    <span className="flex-1 truncate">{item.label}</span>
                    {badge > 0 && (
                      <span
                        className="grid h-5 min-w-5 place-items-center rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white tabular-nums"
                        aria-label={`${badge} conflit(s) en attente`}
                      >
                        {badge > 99 ? "99+" : badge}
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function SidebarPanel({
  profile,
  conflictBadge,
  onNavigate,
  onLogout,
}: {
  profile: ShellProfile;
  conflictBadge: number;
  onNavigate?: () => void;
  onLogout: () => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <Link
        to="/app/dashboard"
        onClick={onNavigate}
        className="flex h-16 shrink-0 items-center px-5 text-ink focus-visible:outline-none"
        aria-label="DécisioBI — tableau de bord"
      >
        <Logo size="sm" />
      </Link>

      <SidebarNav role={profile.rawRole} conflictBadge={conflictBadge} onNavigate={onNavigate} />

      <div className="border-t border-sidebar-border p-3">
        <div className="flex items-center gap-3 rounded-lg px-2 py-2">
          <Avatar initials={profile.initials} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-ink">{profile.name}</p>
            <p className="truncate text-xs text-ink-subtle">
              {profile.loaded ? getRoleLabel(profile.rawRole) : "…"}
            </p>
          </div>
          <button
            type="button"
            onClick={onLogout}
            aria-label="Se déconnecter"
            title="Se déconnecter"
            className="grid h-8 w-8 place-items-center rounded-lg text-ink-subtle transition hover:bg-white/5 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

/** Conservé pour compatibilité : barre latérale bureau + tiroir mobile. */
export function Sidebar({
  mobileOpen,
  onMobileClose,
}: {
  mobileOpen: boolean;
  onMobileClose: () => void;
}) {
  const location = useLocation();
  const profile = useShellProfile();
  const conflictBadge = useConflictBadge(location.pathname);
  const [confirmLogout, setConfirmLogout] = useState(false);

  return (
    <>
      <aside className="sticky top-0 hidden h-screen w-[256px] shrink-0 border-r border-sidebar-border bg-sidebar lg:block">
        <SidebarPanel
          profile={profile}
          conflictBadge={conflictBadge}
          onLogout={() => setConfirmLogout(true)}
        />
      </aside>
      <Sheet open={mobileOpen} onOpenChange={(open) => !open && onMobileClose()}>
        <SheetContent
          side="left"
          className="w-[280px] border-sidebar-border bg-sidebar p-0 text-ink sm:max-w-[280px]"
        >
          <SheetTitle className="sr-only">Menu</SheetTitle>
          <SidebarPanel
            profile={profile}
            conflictBadge={conflictBadge}
            onNavigate={onMobileClose}
            onLogout={() => setConfirmLogout(true)}
          />
        </SheetContent>
      </Sheet>
      <LogoutDialog open={confirmLogout} onOpenChange={setConfirmLogout} />
    </>
  );
}

function LogoutDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const navigate = useNavigate();
  const handleLogout = () => {
    apiClient.logout();
    onOpenChange(false);
    toast("Déconnexion réussie", { variant: "success" });
    setTimeout(() => navigate({ to: "/" }), 400);
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Se déconnecter ?</AlertDialogTitle>
          <AlertDialogDescription>
            Votre session sera fermée sur cet appareil. Vos données et tableaux de bord restent
            enregistrés.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Annuler</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleLogout}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            Se déconnecter
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function Topbar({ onOpenMenu }: { onOpenMenu: () => void }) {
  const location = useLocation();
  const profile = useShellProfile();
  const match = findNavItem(location.pathname);
  const [confirmLogout, setConfirmLogout] = useState(false);

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-card/85 backdrop-blur-md">
      <div className="flex h-14 items-center gap-3 px-4 md:px-8">
        <button
          type="button"
          onClick={onOpenMenu}
          className="grid h-9 w-9 place-items-center rounded-lg text-foreground hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:hidden"
          aria-label="Ouvrir le menu"
        >
          <Menu className="h-5 w-5" />
        </button>
        <Link to="/app/dashboard" className="lg:hidden" aria-label="DécisioBI — tableau de bord">
          <Logo size="sm" showText={false} />
        </Link>

        <nav
          aria-label="Fil d'Ariane"
          className="hidden min-w-0 items-center gap-1.5 text-sm sm:flex"
        >
          <Link to="/app/dashboard" className="text-muted-foreground hover:text-foreground">
            DécisioBI
          </Link>
          {match && (
            <>
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
              <span className="text-muted-foreground">{match.group.section}</span>
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
              <span className="truncate font-medium text-foreground" aria-current="page">
                {match.item.label}
              </span>
            </>
          )}
        </nav>

        <div className="ml-auto flex items-center gap-1.5">
          <NotificationBell />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="flex items-center gap-2 rounded-full py-1 pl-1 pr-2 transition hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label="Menu du compte"
              >
                <Avatar initials={profile.initials} />
                <span className="hidden max-w-[140px] truncate text-sm font-medium text-foreground md:inline">
                  {profile.name}
                </span>
                <ChevronDown className="hidden h-4 w-4 text-muted-foreground md:block" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-60">
              <DropdownMenuLabel className="font-normal">
                <p className="truncate text-sm font-semibold">{profile.name}</p>
                {profile.email && (
                  <p className="truncate text-xs text-muted-foreground">{profile.email}</p>
                )}
                {profile.loaded && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Rôle : {getRoleLabel(profile.rawRole)}
                  </p>
                )}
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link to="/app/profile">
                  <UserCircle className="h-4 w-4" /> Mon profil
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem
                onSelect={() => setConfirmLogout(true)}
                className="text-destructive focus:text-destructive"
              >
                <LogOut className="h-4 w-4" /> Se déconnecter
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      <LogoutDialog open={confirmLogout} onOpenChange={setConfirmLogout} />
    </header>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const isMobile = useIsMobile();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    if (isMobile) setSidebarOpen(false);
  }, [location.pathname, isMobile]);

  // Presence heartbeat - send every 60s
  useEffect(() => {
    const page = location.pathname;
    apiClient.sendPresenceHeartbeat(page).catch(() => {});
    const interval = setInterval(() => {
      apiClient.sendPresenceHeartbeat(page).catch(() => {});
    }, 60000);
    return () => clearInterval(interval);
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen w-full bg-background">
      <a
        href="#app-main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[200] focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-primary-foreground"
      >
        Aller au contenu
      </a>
      <Sidebar mobileOpen={sidebarOpen} onMobileClose={() => setSidebarOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onOpenMenu={() => setSidebarOpen(true)} />
        <main id="app-main" className="flex-1">
          {children}
        </main>
      </div>
    </div>
  );
}

/** Carte de base de l'application (compatibilité) — préférer `Panel` pour les nouvelles vues. */
export function Card({ className = "", children }: { className?: string; children: ReactNode }) {
  return (
    <div className={`rounded-xl border border-border bg-card shadow-card ${className}`}>
      {children}
    </div>
  );
}
