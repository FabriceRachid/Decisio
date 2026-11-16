import { useCallback, useEffect, useRef, useState } from "react";
import { Bell } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { apiClient } from "@/lib/api";
import { type Activity, ActivityItem } from "@/components/app/activity";

interface OnlineUser {
  user_id: number;
  username: string;
  email: string;
  role: string;
  page: string;
  last_seen: string;
}

export function NotificationBell() {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [onlineUsers, setOnlineUsers] = useState<OnlineUser[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);
  const lastSeenRef = useRef<string>("");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchActivities = useCallback(async () => {
    try {
      const [acts, online] = await Promise.all([
        apiClient.getActivityFeed(30),
        apiClient.getOnlineUsers(),
      ]);
      setActivities(acts);
      setOnlineUsers(online);

      if (!open && lastSeenRef.current) {
        const newUnread = acts.filter((a: Activity) => a.created_at > lastSeenRef.current).length;
        if (newUnread > 0) setUnreadCount((prev) => prev + newUnread);
      }

      if (acts.length > 0) {
        lastSeenRef.current = acts[0].created_at;
      }
    } catch {
      // silent
    }
  }, [open]);

  useEffect(() => {
    fetchActivities();
    intervalRef.current = setInterval(fetchActivities, 60000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchActivities]);

  const handleOpenChange = useCallback(
    (isOpen: boolean) => {
      setOpen(isOpen);
      if (isOpen) {
        setUnreadCount(0);
        fetchActivities();
      }
    },
    [fetchActivities],
  );

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <button
          className="relative grid h-9 w-9 place-items-center rounded-lg text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
          aria-label="Activité"
        >
          <Bell className="h-4 w-4" />
          {unreadCount > 0 && (
            <Badge
              variant="destructive"
              className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center px-1 text-[10px]"
            >
              {unreadCount > 99 ? "99+" : unreadCount}
            </Badge>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between px-4 py-3">
          <h4 className="text-sm font-semibold">Activité</h4>
          {unreadCount > 0 && (
            <button
              onClick={() => setUnreadCount(0)}
              className="text-xs text-primary-strong hover:underline"
            >
              Tout lu
            </button>
          )}
        </div>

        <Separator />

        {onlineUsers.length > 0 && (
          <>
            <div className="px-4 py-2">
              <p className="mb-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                En ligne
              </p>
              <div className="flex flex-wrap gap-2">
                {onlineUsers.map((u) => (
                  <div
                    key={u.user_id}
                    className="flex items-center gap-1.5 rounded-full bg-muted px-2 py-0.5 text-xs"
                  >
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    <span className="font-medium">{u.username}</span>
                  </div>
                ))}
              </div>
            </div>
            <Separator />
          </>
        )}

        <ScrollArea className="h-[320px]">
          {activities.length === 0 ? (
            <div className="flex h-full items-center justify-center py-12 text-sm text-muted-foreground">
              Aucune activité récente
            </div>
          ) : (
            <div className="py-1">
              {activities.map((activity) => (
                <ActivityItem
                  key={activity.id}
                  activity={activity}
                  className="transition-colors hover:bg-muted/50"
                />
              ))}
            </div>
          )}
        </ScrollArea>
      </PopoverContent>
    </Popover>
  );
}
