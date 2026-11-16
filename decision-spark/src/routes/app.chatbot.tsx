import { createFileRoute, useSearch } from "@tanstack/react-router";
import {
  AlertTriangle,
  ArrowUp,
  BarChart3,
  Bot,
  Check,
  Copy,
  Database,
  Download,
  FileText,
  Lightbulb,
  Loader2,
  MessagesSquare,
  Package,
  Plus,
  RotateCcw,
  Sparkles,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { PageHeader } from "@/components/AppShell";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { ConfirmDialog } from "@/components/app/ConfirmDialog";
import { EmptyState, ErrorState, fieldClass } from "@/components/app/kit";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
  apiClient,
  handleApiError,
  type ChatMessage as ChatMessageType,
  type ChatSession,
  type DataSourceDetail,
} from "@/lib/api";
import { getCurrentUserProfile } from "@/lib/rbac";
import { toast } from "@/lib/toast";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/chatbot")({
  beforeLoad: async () => {
    const { requireRoleAccess } = await import("@/lib/rbac");
    await requireRoleAccess("use:chatbot");
  },
  component: ChatPage,
  head: () => ({ meta: [{ title: "Assistant IA — DécisioBI" }] }),
  validateSearch: (search: Record<string, unknown>) => ({
    context: (search.context as string) || "",
    sourceId: (search.sourceId as string) || "",
  }),
});

const CHAT_SUGGESTIONS: { l: string; icon: LucideIcon }[] = [
  { l: "Qu'est-ce que contiennent mes données ?", icon: Database },
  { l: "Quels KPI nécessitent une attention ?", icon: BarChart3 },
  { l: "Analyse les tendances récentes", icon: FileText },
  { l: "Compare les performances par région", icon: Package },
  { l: "Y a-t-il des anomalies ?", icon: AlertTriangle },
  { l: "Conseille-moi des actions prioritaires", icon: Sparkles },
  { l: "Explique-moi la colonne principale", icon: BarChart3 },
];

/** Marqueur local des réponses d'erreur réseau (non renvoyé par l'API). */
const LOCAL_ERROR = "error";

function formatSessionDate(iso: string) {
  const date = new Date(iso);
  const today = new Date();
  if (date.toDateString() === today.toDateString()) {
    return date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

/* ─────────────────────────── Messages ─────────────────────────── */

function Bubble({
  side,
  children,
  time,
  avatar,
  footer,
  tone = "default",
}: {
  side: "user" | "bot";
  children: ReactNode;
  time: string;
  avatar: string;
  footer?: ReactNode;
  tone?: "default" | "error";
}) {
  const isUser = side === "user";
  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <span
        aria-hidden
        className={cn(
          "grid h-8 w-8 shrink-0 place-items-center rounded-full text-xs font-bold",
          isUser ? "bg-primary text-primary-foreground" : "bg-night text-primary",
        )}
      >
        {isUser ? avatar : <Bot className="h-4 w-4" />}
      </span>
      <div
        className={cn(
          "flex min-w-0 max-w-[85%] flex-col gap-1 sm:max-w-[75%]",
          isUser ? "items-end" : "items-start",
        )}
      >
        <span className="sr-only">{isUser ? "Vous" : "Assistant"} :</span>
        <div
          className={cn(
            "min-w-0 max-w-full rounded-2xl px-4 py-3 text-sm leading-relaxed",
            isUser
              ? "rounded-tr-sm bg-primary/15 text-foreground"
              : tone === "error"
                ? "rounded-tl-sm border border-red-200 bg-red-50 text-red-800"
                : "rounded-tl-sm border border-border bg-card text-foreground shadow-card",
          )}
        >
          {children}
        </div>
        <div
          className={cn(
            "flex flex-wrap items-center gap-2 px-1",
            isUser ? "justify-end" : "justify-start",
          )}
        >
          <time className="text-[11px] text-muted-foreground">{time}</time>
          {footer}
        </div>
      </div>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          toast("Copie impossible dans ce navigateur", { variant: "error" });
        }
      }}
      className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] text-muted-foreground transition hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      aria-label="Copier la réponse"
    >
      {copied ? <Check className="h-3 w-3 text-emerald-600" /> : <Copy className="h-3 w-3" />}
      {copied ? "Copié" : "Copier"}
    </button>
  );
}

function ThinkingBubble() {
  return (
    <div className="flex gap-3" role="status" aria-live="polite">
      <span
        aria-hidden
        className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-night text-primary"
      >
        <Bot className="h-4 w-4" />
      </span>
      <div className="rounded-2xl rounded-tl-sm border border-border bg-card px-4 py-3 shadow-card">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="flex gap-1" aria-hidden>
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.15s]" />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" />
          </span>
          L'assistant analyse vos données…
        </div>
      </div>
    </div>
  );
}

function MessagesSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Chargement des messages">
      {[0, 1, 2].map((i) => (
        <div key={i} className={cn("flex gap-3", i % 2 === 0 && "flex-row-reverse")}>
          <Skeleton className="h-8 w-8 rounded-full" />
          <Skeleton className={cn("h-16 rounded-2xl", i % 2 === 0 ? "w-1/2" : "w-2/3")} />
        </div>
      ))}
    </div>
  );
}

function SuggestionGrid({
  onPick,
  disabled,
}: {
  onPick: (text: string) => void;
  disabled?: boolean;
}) {
  return (
    <ul className="grid w-full max-w-2xl grid-cols-1 gap-2 sm:grid-cols-2">
      {CHAT_SUGGESTIONS.map((s) => (
        <li key={s.l}>
          <button
            type="button"
            onClick={() => onPick(s.l)}
            disabled={disabled}
            className="flex h-full w-full items-start gap-3 rounded-xl border border-border bg-card p-3 text-left text-sm text-foreground transition hover:border-primary/40 hover:shadow-widget-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
          >
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-primary/15 text-primary-strong">
              <s.icon className="h-3.5 w-3.5" />
            </span>
            <span className="pt-1">{s.l}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

/* ─────────────────────────── Conversations ─────────────────────────── */

function SessionList({
  sessions,
  activeId,
  loading,
  error,
  onRetry,
  onSelect,
  onDelete,
  touch = false,
}: {
  sessions: ChatSession[];
  activeId: number | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
  touch?: boolean;
}) {
  if (loading) {
    return (
      <div className="space-y-2" aria-busy="true">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-14 w-full rounded-lg" />
        ))}
      </div>
    );
  }
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (sessions.length === 0) {
    return (
      <p className="px-2 py-6 text-center text-sm text-muted-foreground">
        Aucune conversation pour l'instant.
      </p>
    );
  }
  return (
    <ul className="space-y-1">
      {sessions.map((s) => {
        const active = s.id === activeId;
        return (
          <li key={s.id} className="group relative">
            <button
              type="button"
              onClick={() => onSelect(s.id)}
              aria-current={active ? "true" : undefined}
              className={cn(
                "w-full rounded-lg px-3 py-2.5 pr-10 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active ? "bg-primary/15" : "hover:bg-secondary",
              )}
            >
              <span
                className={cn(
                  "block truncate text-sm",
                  active ? "font-semibold text-foreground" : "font-medium text-foreground/90",
                )}
              >
                {s.session_name || `Conversation #${s.id}`}
              </span>
              <span className="mt-0.5 block text-xs text-muted-foreground">
                {s.message_count} message{s.message_count > 1 ? "s" : ""} ·{" "}
                {formatSessionDate(s.last_activity_at)}
              </span>
            </button>
            <button
              type="button"
              onClick={() => onDelete(s.id)}
              aria-label={`Supprimer « ${s.session_name || `Conversation #${s.id}`} »`}
              title="Supprimer"
              className={cn(
                "absolute right-1.5 top-1/2 grid h-7 w-7 -translate-y-1/2 place-items-center rounded-md text-muted-foreground transition hover:bg-red-50 hover:text-red-700 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                !touch && "opacity-0 group-hover:opacity-100",
              )}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </li>
        );
      })}
    </ul>
  );
}

/* ─────────────────────────── Page ─────────────────────────── */

function ChatPage() {
  const searchParams = useSearch({ from: Route.fullPath });
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [messagesError, setMessagesError] = useState<string | null>(null);
  const [creatingSession, setCreatingSession] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [showIdeas, setShowIdeas] = useState(false);
  const [initials, setInitials] = useState("Moi");
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const [sources, setSources] = useState<DataSourceDetail[]>([]);
  const [selectedSource, setSelectedSource] = useState<DataSourceDetail | null>(null);
  const [selectedWidgetIds, setSelectedWidgetIds] = useState<Set<number>>(new Set());
  const [loadingSources, setLoadingSources] = useState(true);
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const autoSentRef = useRef(false);

  useEffect(() => {
    loadSessions();
    loadSources();
    getCurrentUserProfile()
      .then((user) => {
        const name =
          [user.first_name, user.last_name].filter(Boolean).join(" ").trim() || user.username;
        const value = (name || "")
          .split(/\s+/)
          .filter(Boolean)
          .slice(0, 2)
          .map((part) => part[0])
          .join("")
          .toUpperCase();
        if (value) setInitials(value);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, thinking]);

  // Ajuste la hauteur du champ de saisie à son contenu.
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [chatInput]);

  // Envoi automatique de l'analyse d'un widget lorsque le contexte vient du tableau de bord
  useEffect(() => {
    if (!searchParams.context || autoSentRef.current || thinking) return;
    if (sources.length === 0) return;

    const source = sources.find((s) => s.id === Number(searchParams.sourceId));
    if (searchParams.sourceId && source) setSelectedSource(source);

    const widgetImage = sessionStorage.getItem("widgetAnalysisImage");
    const widgetTitle = sessionStorage.getItem("widgetAnalysisTitle");
    if (widgetImage) {
      sessionStorage.removeItem("widgetAnalysisImage");
      sessionStorage.removeItem("widgetAnalysisTitle");
    }

    autoSentRef.current = true;

    const run = async () => {
      let sid = activeSessionId;
      if (!sid) {
        try {
          const session = await apiClient.createChatSession({ bot_personality: "professional" });
          setSessions((prev) => [session, ...prev]);
          setActiveSessionId(session.id);
          sid = session.id;
        } catch (e) {
          console.error("Auto-create session failed:", e);
          return;
        }
      }

      sendChat(
        "Analyse ce widget en détail.",
        searchParams.context,
        widgetImage || undefined,
        widgetTitle || undefined,
        sid,
      );
    };
    run();
  }, [searchParams.context, searchParams.sourceId, activeSessionId, sources, thinking]);

  const loadSessions = async () => {
    try {
      setLoadingSessions(true);
      setSessionsError(null);
      const data = await apiClient.listChatSessions();
      setSessions(data);
      if (data.length > 0 && !activeSessionId) {
        setActiveSessionId(data[0].id);
        loadMessages(data[0].id);
      }
    } catch (error) {
      setSessionsError(handleApiError(error, "Impossible de charger les conversations"));
    } finally {
      setLoadingSessions(false);
    }
  };

  const loadMessages = async (sessionId: number) => {
    try {
      setLoadingMessages(true);
      setMessagesError(null);
      const data = await apiClient.getChatMessages(sessionId);
      setMessages(data);
    } catch (error) {
      setMessagesError(handleApiError(error, "Impossible de charger les messages"));
    } finally {
      setLoadingMessages(false);
    }
  };

  const createSession = async () => {
    setCreatingSession(true);
    try {
      const session = await apiClient.createChatSession({ bot_personality: "professional" });
      setSessions((prev) => [session, ...prev]);
      setActiveSessionId(session.id);
      setMessages([]);
      setMessagesError(null);
      setHistoryOpen(false);
      return session.id;
    } catch (error) {
      toast(handleApiError(error, "Erreur lors de la création"), { variant: "error" });
      return null;
    } finally {
      setCreatingSession(false);
    }
  };

  const createNewSession = async () => {
    const sid = await createSession();
    if (sid) {
      toast("Nouvelle conversation créée", { variant: "success" });
      inputRef.current?.focus();
    }
  };

  /** Démarre une conversation directement à partir d'une suggestion. */
  const startWith = async (text: string) => {
    const sid = activeSessionId ?? (await createSession());
    if (sid) void sendChat(text, undefined, undefined, undefined, sid);
  };

  const switchSession = (id: number) => {
    setActiveSessionId(id);
    setHistoryOpen(false);
    loadMessages(id);
  };

  const doDeleteSession = async () => {
    if (deleteConfirmId === null) return;
    const id = deleteConfirmId;
    setDeleting(true);
    try {
      await apiClient.deleteChatSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (activeSessionId === id) {
        const remaining = sessions.filter((s) => s.id !== id);
        if (remaining.length > 0) {
          setActiveSessionId(remaining[0].id);
          loadMessages(remaining[0].id);
        } else {
          setActiveSessionId(null);
          setMessages([]);
        }
      }
      toast("Conversation supprimée", { variant: "success" });
    } catch (error) {
      toast(handleApiError(error, "Erreur lors de la suppression"), { variant: "error" });
    } finally {
      setDeleting(false);
      setDeleteConfirmId(null);
    }
  };

  const sendChat = async (
    text: string,
    widgetContext?: string,
    widgetImage?: string,
    widgetTitle?: string,
    sessionId?: number,
  ) => {
    const sid = sessionId || activeSessionId;
    if (!text.trim() || !sid) return;

    const attachedData: Record<string, unknown> = {};
    if (widgetImage) {
      attachedData.widget_image = widgetImage;
      attachedData.widget_title = widgetTitle;
    }

    const userMsg: ChatMessageType = {
      id: Date.now(),
      message_type: "user",
      content_type: "question",
      content: text,
      intent: "",
      sentiment: "neutral",
      confidence: 0,
      attached_data: Object.keys(attachedData).length > 0 ? attachedData : null,
      suggested_questions: null,
      response_time_ms: null,
      model_used: null,
      fallback_used: false,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setChatInput("");
    setShowIdeas(false);
    setThinking(true);

    const context: Record<string, unknown> = {};
    if (selectedSource) {
      context.source_id = selectedSource.id;
      if (selectedWidgetIds.size > 0) {
        context.widget_ids = Array.from(selectedWidgetIds);
      }
    }
    if (widgetContext) {
      context.widget_context = widgetContext;
    }

    try {
      const result = await apiClient.sendChatMessage(sid, text, { context });
      setMessages((prev) => [...prev.slice(0, -1), userMsg, result.bot_message]);

      setSessions((prev) =>
        prev.map((s) =>
          s.id === sid
            ? {
                ...s,
                session_name: result.session?.session_name || s.session_name,
                message_count: s.message_count + 2,
                last_activity_at: new Date().toISOString(),
              }
            : s,
        ),
      );
    } catch (error) {
      const errorMsg: ChatMessageType = {
        id: Date.now() + 2,
        message_type: "bot",
        content_type: LOCAL_ERROR,
        content: handleApiError(
          error,
          "Une erreur est survenue lors de l'analyse. Veuillez réessayer.",
        ),
        intent: "",
        sentiment: "neutral",
        confidence: 0,
        attached_data: null,
        suggested_questions: null,
        response_time_ms: null,
        model_used: null,
        fallback_used: true,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev.slice(0, -1), userMsg, errorMsg]);
    } finally {
      setThinking(false);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    sendChat(chatInput);
  };

  const exportConversation = () => {
    if (messages.length === 0) {
      toast("Aucun message à exporter", { variant: "info" });
      return;
    }
    const lines = messages.map((m) => {
      const role = m.message_type === "user" ? "Utilisateur" : "Assistant";
      const time = new Date(m.created_at).toLocaleString("fr-FR");
      return `[${time}] ${role}:\n${m.content}\n`;
    });
    const blob = new Blob([lines.join("\n---\n\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `chat-export-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    toast("Export téléchargé", { variant: "success" });
  };

  const loadSources = async () => {
    try {
      setLoadingSources(true);
      const data = await apiClient.listDataSources({ status: "completed" });
      setSources(data);
      if (data.length > 0 && !selectedSource && !searchParams.sourceId) {
        setSelectedSource(data[0]);
      }
    } catch (error) {
      console.error("Failed to load sources:", error);
    } finally {
      setLoadingSources(false);
    }
  };

  const handleSelectSource = (source: DataSourceDetail) => {
    setSelectedSource(source);
    setSelectedWidgetIds(new Set());
  };

  const deleteSessionName = deleteConfirmId
    ? sessions.find((s) => s.id === deleteConfirmId)?.session_name
    : "";
  const activeSession = sessions.find((s) => s.id === activeSessionId) || null;
  const lastMessage = messages[messages.length - 1];
  const followUps =
    !thinking &&
    lastMessage?.message_type === "bot" &&
    lastMessage.content_type !== LOCAL_ERROR &&
    lastMessage.suggested_questions?.length
      ? lastMessage.suggested_questions.slice(0, 4)
      : [];
  const lastUserText = [...messages].reverse().find((m) => m.message_type === "user")?.content;

  const sessionList = (touch: boolean) => (
    <SessionList
      sessions={sessions}
      activeId={activeSessionId}
      loading={loadingSessions}
      error={sessionsError}
      onRetry={() => void loadSessions()}
      onSelect={switchSession}
      onDelete={setDeleteConfirmId}
      touch={touch}
    />
  );

  return (
    <div className="flex h-[calc(100dvh-3.5rem-1px)] flex-col">
      <ConfirmDialog
        open={deleteConfirmId !== null}
        onOpenChange={(open) => !open && setDeleteConfirmId(null)}
        title="Supprimer la conversation ?"
        description={
          <>
            « {deleteSessionName || "Conversation"} » et tous ses messages seront définitivement
            supprimés.
          </>
        }
        confirmLabel="Supprimer"
        destructive
        pending={deleting}
        onConfirm={doDeleteSession}
      />

      <PageHeader
        title="Assistant IA"
        subtitle="Posez vos questions en français : l'assistant répond à partir de vos données importées."
        actions={
          <>
            <Button variant="outline" className="lg:hidden" onClick={() => setHistoryOpen(true)}>
              <MessagesSquare /> Conversations
            </Button>
            <Button
              variant="outline"
              onClick={exportConversation}
              disabled={messages.length === 0}
              aria-label="Exporter la conversation (.txt)"
              title="Exporter la conversation (.txt)"
            >
              <Download />
              <span className="hidden sm:inline">Exporter</span>
            </Button>
            <Button onClick={() => void createNewSession()} disabled={creatingSession}>
              {creatingSession ? <Loader2 className="animate-spin" /> : <Plus />}
              Nouvelle conversation
            </Button>
          </>
        }
      />

      <div className="grid min-h-0 flex-1 lg:grid-cols-[280px_minmax(0,1fr)]">
        {/* Historique des conversations (bureau) */}
        <aside
          aria-label="Conversations"
          className="hidden min-h-0 flex-col border-r border-border bg-card lg:flex"
        >
          <div className="flex items-center justify-between px-4 pb-2 pt-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Conversations
            </p>
            <span className="text-xs tabular-nums text-muted-foreground">{sessions.length}</span>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">{sessionList(false)}</div>
        </aside>

        {/* Fil de discussion */}
        <section className="flex min-h-0 flex-col" aria-label="Discussion">
          {activeSessionId === null && !loadingSessions ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-6 overflow-y-auto px-4 py-10">
              <span className="grid h-14 w-14 place-items-center rounded-2xl bg-night text-primary shadow-card">
                <Sparkles className="h-7 w-7" />
              </span>
              <div className="max-w-md text-center">
                <h2 className="font-display text-xl font-semibold text-foreground">
                  Votre analyste, disponible à tout moment
                </h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  Interrogez vos données en langage naturel : tendances, KPI, anomalies, actions
                  prioritaires. Choisissez une suggestion pour démarrer.
                </p>
              </div>
              <SuggestionGrid onPick={(t) => void startWith(t)} disabled={creatingSession} />
              {sessionsError && (
                <ErrorState
                  className="w-full max-w-2xl"
                  message={sessionsError}
                  onRetry={() => void loadSessions()}
                />
              )}
            </div>
          ) : (
            <>
              <div className="min-h-0 flex-1 overflow-y-auto">
                <div
                  className="mx-auto w-full max-w-3xl space-y-6 px-4 py-6 md:px-6"
                  aria-live="polite"
                >
                  {activeSession && (
                    <p className="text-center text-xs text-muted-foreground">
                      {activeSession.session_name || `Conversation #${activeSession.id}`} · démarrée
                      le{" "}
                      {new Date(activeSession.started_at).toLocaleDateString("fr-FR", {
                        day: "numeric",
                        month: "long",
                      })}
                    </p>
                  )}

                  {loadingMessages || loadingSessions ? (
                    <MessagesSkeleton />
                  ) : messagesError ? (
                    <ErrorState
                      message={messagesError}
                      onRetry={() => activeSessionId && void loadMessages(activeSessionId)}
                    />
                  ) : messages.length === 0 && !thinking ? (
                    <div className="flex flex-col items-center gap-5 py-10 text-center">
                      <EmptyState
                        icon={MessagesSquare}
                        title="Comment puis-je vous aider ?"
                        description="Posez une question sur vos données ou choisissez une suggestion."
                        className="border-none bg-transparent p-0 shadow-none"
                      />
                      <SuggestionGrid onPick={(t) => void sendChat(t)} disabled={thinking} />
                    </div>
                  ) : (
                    messages.map((m) => {
                      const isUser = m.message_type === "user";
                      const isError = m.content_type === LOCAL_ERROR;
                      const time = new Date(m.created_at).toLocaleTimeString("fr-FR", {
                        hour: "2-digit",
                        minute: "2-digit",
                      });
                      const attached = m.attached_data as {
                        widget_image?: string;
                        widget_title?: string;
                      } | null;
                      return (
                        <Bubble
                          key={m.id}
                          side={isUser ? "user" : "bot"}
                          time={time}
                          avatar={initials}
                          tone={isError ? "error" : "default"}
                          footer={
                            !isUser &&
                            (isError ? (
                              m.id === lastMessage?.id &&
                              lastUserText && (
                                <button
                                  type="button"
                                  onClick={() => void sendChat(lastUserText)}
                                  disabled={thinking}
                                  className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium text-red-700 transition hover:bg-red-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                >
                                  <RotateCcw className="h-3 w-3" /> Réessayer
                                </button>
                              )
                            ) : (
                              <>
                                <CopyButton text={m.content} />
                                {m.response_time_ms != null && (
                                  <span className="text-[11px] text-muted-foreground">
                                    {(m.response_time_ms / 1000).toFixed(1)} s
                                  </span>
                                )}
                              </>
                            ))
                          }
                        >
                          {isUser ? (
                            <div className="space-y-2">
                              {attached?.widget_image && (
                                <figure className="overflow-hidden rounded-lg border border-border bg-card">
                                  <img
                                    src={attached.widget_image}
                                    alt={attached.widget_title || "Widget analysé"}
                                    className="w-full max-w-xs object-contain"
                                  />
                                  {attached.widget_title && (
                                    <figcaption className="border-t border-border px-2 py-1 text-[11px] font-medium text-muted-foreground">
                                      {attached.widget_title}
                                    </figcaption>
                                  )}
                                </figure>
                              )}
                              <p className="whitespace-pre-wrap break-words">{m.content}</p>
                            </div>
                          ) : isError ? (
                            <p>{m.content}</p>
                          ) : (
                            <MarkdownRenderer content={m.content} />
                          )}
                        </Bubble>
                      );
                    })
                  )}

                  {thinking && <ThinkingBubble />}

                  {followUps.length > 0 && (
                    <div className="pl-11">
                      <p className="mb-2 text-xs font-medium text-muted-foreground">
                        Pour aller plus loin
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {followUps.map((q) => (
                          <button
                            key={q}
                            type="button"
                            onClick={() => void sendChat(q)}
                            className="rounded-full border border-border bg-card px-3 py-1.5 text-left text-xs font-medium text-foreground transition hover:border-primary/40 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  <div ref={endRef} />
                </div>
              </div>

              {/* Zone de saisie */}
              <div className="border-t border-border bg-card/80 backdrop-blur">
                <form
                  onSubmit={handleSubmit}
                  className="mx-auto w-full max-w-3xl space-y-2 px-4 py-3 md:px-6"
                >
                  {showIdeas && (
                    <div className="flex flex-wrap gap-1.5" aria-label="Idées de questions">
                      {CHAT_SUGGESTIONS.map((s) => (
                        <button
                          type="button"
                          key={s.l}
                          onClick={() => sendChat(s.l)}
                          disabled={thinking || !activeSessionId}
                          className="inline-flex items-center gap-1 rounded-full border border-border bg-secondary/60 px-2.5 py-1 text-xs font-medium text-foreground/90 transition hover:border-input hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                        >
                          <s.icon className="h-3 w-3 text-primary-strong" /> {s.l}
                        </button>
                      ))}
                    </div>
                  )}

                  <div className="rounded-xl border border-input bg-card shadow-sm transition focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/30">
                    <label htmlFor="chat-input" className="sr-only">
                      Votre question
                    </label>
                    <textarea
                      id="chat-input"
                      ref={inputRef}
                      rows={1}
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          sendChat(chatInput);
                        }
                      }}
                      placeholder={
                        selectedSource
                          ? `Question sur « ${selectedSource.name} »…`
                          : "Posez une question…"
                      }
                      disabled={thinking || !activeSessionId}
                      className="block max-h-40 w-full resize-none bg-transparent px-4 pt-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-50"
                    />
                    <div className="flex flex-wrap items-center gap-2 px-2 pb-2 pt-1">
                      <div className="flex min-w-0 items-center gap-1.5">
                        <Database
                          className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
                          aria-hidden
                        />
                        <label htmlFor="chat-source" className="sr-only">
                          Source de données analysée
                        </label>
                        <select
                          id="chat-source"
                          value={selectedSource?.id ?? ""}
                          onChange={(e) => {
                            const s = sources.find((x) => x.id === Number(e.target.value));
                            if (s) handleSelectSource(s);
                          }}
                          disabled={loadingSources || sources.length === 0}
                          className={cn(
                            fieldClass,
                            "h-7 w-auto max-w-[200px] truncate border-transparent bg-secondary/60 px-2 text-xs shadow-none",
                          )}
                        >
                          {loadingSources && <option value="">Chargement…</option>}
                          {!loadingSources && sources.length === 0 && (
                            <option value="">Aucune source</option>
                          )}
                          {!selectedSource && sources.length > 0 && (
                            <option value="">Choisir une source</option>
                          )}
                          {sources.map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <button
                        type="button"
                        onClick={() => setShowIdeas((v) => !v)}
                        aria-pressed={showIdeas}
                        className={cn(
                          "inline-flex h-7 items-center gap-1 rounded-md px-2 text-xs font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                          showIdeas
                            ? "bg-primary/15 text-foreground"
                            : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                        )}
                      >
                        <Lightbulb className="h-3.5 w-3.5" /> Idées
                      </button>
                      <Button
                        type="submit"
                        size="icon"
                        className="ml-auto h-8 w-8"
                        disabled={thinking || !activeSessionId || !chatInput.trim()}
                        aria-label="Envoyer"
                      >
                        {thinking ? <Loader2 className="animate-spin" /> : <ArrowUp />}
                      </Button>
                    </div>
                  </div>
                  <p className="text-center text-[11px] text-muted-foreground">
                    Réponses générées par IA : vérifiez les chiffres clés avant toute décision.
                    Entrée pour envoyer, Maj + Entrée pour aller à la ligne.
                  </p>
                </form>
              </div>
            </>
          )}
        </section>
      </div>

      {/* Historique des conversations (mobile) */}
      <Sheet open={historyOpen} onOpenChange={setHistoryOpen}>
        <SheetContent side="left" className="w-full overflow-y-auto sm:max-w-sm">
          <SheetHeader>
            <SheetTitle>Conversations</SheetTitle>
            <SheetDescription>
              Reprenez une conversation ou démarrez-en une nouvelle.
            </SheetDescription>
          </SheetHeader>
          <div className="mt-4 space-y-4">
            <Button
              className="w-full"
              onClick={() => void createNewSession()}
              disabled={creatingSession}
            >
              <Plus /> Nouvelle conversation
            </Button>
            {sessionList(true)}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
