import {
  FileText,
  GitMerge,
  LayoutDashboard,
  type LucideIcon,
  MessageSquare,
  ScanSearch,
  Upload,
  UserCircle,
  Users,
} from "lucide-react";
import type { Capability } from "@/lib/rbac";

export type AppRoute =
  | "/app/dashboard"
  | "/app/import"
  | "/app/conflicts"
  | "/app/anomalies"
  | "/app/alerts"
  | "/app/analyse"
  | "/app/chatbot"
  | "/app/reports"
  | "/app/users"
  | "/app/profile";

export type NavItem = {
  to: AppRoute;
  label: string;
  icon: LucideIcon;
  cap: Capability;
  /** Courte description affichée en info-bulle et dans l'en-tête de page. */
  hint: string;
};

export type NavGroup = { section: string; items: NavItem[] };

/** Navigation de l'application, organisée selon le parcours décisionnel. */
export const NAV_GROUPS: NavGroup[] = [
  {
    section: "Pilotage",
    items: [
      {
        to: "/app/dashboard",
        label: "Tableau de bord",
        icon: LayoutDashboard,
        cap: "read:dashboard",
        hint: "Vue d'ensemble de vos indicateurs",
      },
    ],
  },
  {
    section: "Données",
    items: [
      {
        to: "/app/import",
        label: "Importer & préparer",
        icon: Upload,
        cap: "write:data",
        hint: "Import, aperçu, relations, nettoyage et validation",
      },
    ],
  },
  {
    section: "Contrôle",
    items: [
      {
        to: "/app/conflicts",
        label: "Conflits",
        icon: GitMerge,
        cap: "read:conflicts",
        hint: "Incohérences entre sources et arbitrage",
      },
      {
        to: "/app/anomalies",
        label: "Anomalies",
        icon: ScanSearch,
        cap: "read:dashboard",
        hint: "Valeurs atypiques détectées par Isolation Forest",
      },
    ],
  },
  {
    section: "Analyse",
    items: [
      {
        to: "/app/chatbot",
        label: "Assistant IA",
        icon: MessageSquare,
        cap: "use:chatbot",
        hint: "Questions sur vos données importées, en français",
      },
    ],
  },
  {
    section: "Reporting",
    items: [
      {
        to: "/app/reports",
        label: "Rapports",
        icon: FileText,
        cap: "read:dashboard",
        hint: "Rapports PDF et envois planifiés",
      },
    ],
  },
  {
    section: "Administration",
    items: [
      {
        to: "/app/users",
        label: "Utilisateurs",
        icon: Users,
        cap: "manage:users",
        hint: "Comptes, rôles et accès",
      },
      {
        to: "/app/profile",
        label: "Mon profil",
        icon: UserCircle,
        cap: "read:dashboard",
        hint: "Informations, sécurité et préférences",
      },
    ],
  },
];

export function findNavItem(pathname: string) {
  for (const group of NAV_GROUPS) {
    const item = group.items.find((i) => pathname === i.to || pathname.startsWith(`${i.to}/`));
    if (item) return { group, item };
  }
  return null;
}

export type JourneyStep = {
  key: string;
  label: string;
  to: AppRoute;
  cap: Capability;
};

/** Parcours Importer → Décider ; chaque étape pointe vers l'écran qui la réalise. */
export const JOURNEY: JourneyStep[] = [
  { key: "import", label: "Importer", to: "/app/import", cap: "write:data" },
  { key: "prepare", label: "Préparer", to: "/app/import", cap: "write:data" },
  { key: "validate", label: "Valider", to: "/app/import", cap: "write:data" },
  { key: "control", label: "Contrôler", to: "/app/conflicts", cap: "read:conflicts" },
  { key: "analyse", label: "Analyser", to: "/app/chatbot", cap: "use:chatbot" },
  { key: "visualise", label: "Visualiser", to: "/app/dashboard", cap: "read:dashboard" },
  { key: "report", label: "Reporter", to: "/app/reports", cap: "read:dashboard" },
  { key: "decide", label: "Décider", to: "/app/chatbot", cap: "use:chatbot" },
];
