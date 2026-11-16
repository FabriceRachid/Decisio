import { useEffect, useState } from "react";
import { getCurrentUserProfile, type CurrentUserProfile } from "@/lib/rbac";

export function useCurrentUser() {
  const [user, setUser] = useState<CurrentUserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;

    const load = async () => {
      try {
        const profile = await getCurrentUserProfile();
        if (!alive) return;
        setUser(profile);
      } catch {
        if (!alive) return;
        setUser(null);
      } finally {
        if (alive) {
          setLoading(false);
        }
      }
    };

    void load();

    return () => {
      alive = false;
    };
  }, []);

  return { user, loading };
}
