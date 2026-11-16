import { redirect } from "@tanstack/react-router";
import { apiClient } from "@/lib/api";

export type Role = "admin" | "analyst" | "viewer";

export interface CurrentUserProfile {
  id: number;
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
  date_joined?: string;
  last_login?: string;
  profile?: {
    role?: Role;
    department?: string;
    phone_number?: string;
    avatar_url?: string;
    timezone?: string;
    language?: string;
  };
}

export type Capability =
  | "read:dashboard"
  | "read:kpi"
  | "read:conflicts"
  | "read:alerts"
  | "use:chatbot"
  | "write:data"
  | "manage:kpi"
  | "manage:users";

const ROLE_CAPABILITIES: Record<Role, Capability[]> = {
  admin: [
    "read:dashboard",
    "read:kpi",
    "read:conflicts",
    "read:alerts",
    "use:chatbot",
    "write:data",
    "manage:kpi",
    "manage:users",
  ],
  analyst: [
    "read:dashboard",
    "read:kpi",
    "read:conflicts",
    "read:alerts",
    "use:chatbot",
    "write:data",
    "manage:kpi",
  ],
  viewer: ["read:dashboard", "read:kpi", "read:conflicts", "read:alerts", "use:chatbot"],
};

let cachedProfile: CurrentUserProfile | null = null;
let inflightProfilePromise: Promise<CurrentUserProfile> | null = null;

export function normalizeRole(role?: string | null): Role {
  if (role === "admin" || role === "analyst" || role === "viewer") {
    return role;
  }
  return "viewer";
}

export function getRoleLabel(role?: string | null): string {
  const normalized = normalizeRole(role);
  if (normalized === "admin") return "Admin";
  if (normalized === "analyst") return "Analyste";
  return "Lecture";
}

export function can(role: string | null | undefined, capability: Capability): boolean {
  return ROLE_CAPABILITIES[normalizeRole(role)].includes(capability);
}

export function clearCurrentUserProfileCache() {
  cachedProfile = null;
  inflightProfilePromise = null;
}

export async function getCurrentUserProfile(force = false): Promise<CurrentUserProfile> {
  if (!force && cachedProfile) {
    return cachedProfile;
  }

  if (!force && inflightProfilePromise) {
    return inflightProfilePromise;
  }

  inflightProfilePromise = apiClient.getProfile().then((profile) => {
    cachedProfile = profile;
    inflightProfilePromise = null;
    return profile;
  });

  return inflightProfilePromise;
}

export async function requireRoleAccess(capability: Capability) {
  if (!apiClient.getAuthToken()) {
    throw redirect({ to: "/login" });
  }

  const profile = await getCurrentUserProfile();
  if (!can(profile.profile?.role, capability)) {
    throw redirect({ to: "/app/dashboard" });
  }

  return profile;
}
