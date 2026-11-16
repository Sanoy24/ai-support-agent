import { ArrowUp, BookOpen, MessageCircle, SquarePen, UserRound, X } from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";

import { ChatError, sendChatMessage, uniqueSourceLabels, type Source } from "@/lib/chat";
import { cn } from "@/lib/utils";

export interface WidgetConfig {
  apiBase: string;
  title: string;
  greeting: string;
  suggestions: string[];
}

interface ChatEntry {
  id: number;
  role: "user" | "assistant" | "notice";
  text: string;
  sources?: Source[];
}

interface StoredState {
  conversationId: string | null;
  entries: ChatEntry[];
  handedOff: boolean;
}

const STORAGE_KEY = "ai-support-agent:chat";

function loadState(): StoredState {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as StoredState;
  } catch {
    // Storage can be blocked by the browser; start fresh.
  }
  return { conversationId: null, entries: [], handedOff: false };
}

function saveState(state: StoredState): void {
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Ignore: the chat still works for this page view.
  }
}

export function ChatWidget({ config }: { config: WidgetConfig }) {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<StoredState>(loadState);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const nextId = useRef(state.entries.reduce((max, e) => Math.max(max, e.id), 0) + 1);

  useEffect(() => saveState(state), [state]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [state.entries, pending, open]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const append = useCallback((entry: Omit<ChatEntry, "id">) => {
    const id = nextId.current++;
    setState((s) => ({ ...s, entries: [...s.entries, { ...entry, id }] }));
  }, []);

  const send = useCallback(
    async (text: string) => {
      const message = text.trim();
      if (!message || pending) return;
      setDraft("");
      append({ role: "user", text: message });
      setPending(true);
      try {
        const reply = await sendChatMessage(config.apiBase, message, state.conversationId);
        append({ role: "assistant", text: reply.reply, sources: reply.sources });
        setState((s) => ({ ...s, conversationId: reply.conversation_id }));
        if (reply.handed_off && !state.handedOff) {
          append({ role: "notice", text: "A member of our team will follow up on this chat." });
          setState((s) => ({ ...s, handedOff: true }));
        }
      } catch (error) {
        if (error instanceof ChatError && error.status === 404) {
          setState({ conversationId: null, entries: [], handedOff: false });
          append({ role: "notice", text: "Your previous chat expired. Please ask again." });
        } else {
          append({
            role: "notice",
            text:
              error instanceof ChatError ? error.message : "Can't reach support. Please try again.",
          });
        }
      } finally {
        setPending(false);
        inputRef.current?.focus();
      }
    },
    [append, config.apiBase, pending, state.conversationId, state.handedOff],
  );

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void send(draft);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send(draft);
    }
  };

  const startNewConversation = () => {
    setState({ conversationId: null, entries: [], handedOff: false });
    setDraft("");
    inputRef.current?.focus();
  };

  const showSuggestions = state.entries.length === 0 && !pending;

  return (
    <div className="fixed right-5 bottom-5 z-[2147483000] flex flex-col items-end gap-3 text-sm text-zinc-900">
      {open && (
        <section
          role="dialog"
          aria-label={config.title}
          className="asa-pop flex h-[min(600px,calc(100dvh-104px))] max-h-[calc(100dvh-104px)] min-h-[320px] w-[min(380px,calc(100vw-40px))] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl ring-1 ring-zinc-900/10"
        >
          <header className="flex items-center gap-3 border-b border-zinc-100 px-4 py-3">
            <div className="flex size-9 items-center justify-center rounded-full bg-brand-600 text-white">
              <MessageCircle className="size-4.5" aria-hidden />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold">{config.title}</p>
              <p className="truncate text-xs text-zinc-500">
                AI assistant · a person can take over anytime
              </p>
            </div>
            {state.entries.length > 0 && (
              <button
                type="button"
                onClick={startNewConversation}
                disabled={pending}
                title="Start a new conversation"
                aria-label="Start a new conversation"
                className="rounded-md p-1.5 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 disabled:opacity-40"
              >
                <SquarePen className="size-4" />
              </button>
            )}
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-md p-1.5 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900"
              aria-label="Close chat"
            >
              <X className="size-4" />
            </button>
          </header>

          <div
            ref={logRef}
            className="flex-1 space-y-3 overflow-y-auto px-4 py-4"
            aria-live="polite"
          >
            <Bubble role="assistant" text={config.greeting} />
            {state.entries.map((entry) =>
              entry.role === "notice" ? (
                <Notice key={entry.id} text={entry.text} />
              ) : (
                <Bubble
                  key={entry.id}
                  role={entry.role}
                  text={entry.text}
                  sources={entry.sources}
                />
              ),
            )}
            {pending && <TypingIndicator />}
            {showSuggestions && (
              <div className="flex flex-wrap gap-2 pt-1">
                {config.suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => void send(suggestion)}
                    className="rounded-full border border-zinc-200 px-3 py-1.5 text-[13px] text-zinc-700 transition hover:border-brand-600 hover:text-brand-700"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            )}
          </div>

          <form onSubmit={onSubmit} className="border-t border-zinc-100 p-3">
            <div className="flex items-end gap-2 rounded-xl border border-zinc-200 px-3 py-2 focus-within:border-brand-600 focus-within:ring-2 focus-within:ring-brand-600/15">
              <textarea
                ref={inputRef}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={onKeyDown}
                rows={1}
                maxLength={2000}
                placeholder="Ask about an order, shipping or returns"
                aria-label="Message"
                className="max-h-28 min-h-6 flex-1 resize-none bg-transparent leading-6 outline-none placeholder:text-zinc-400"
              />
              <button
                type="submit"
                disabled={!draft.trim() || pending}
                aria-label="Send message"
                className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white transition hover:bg-brand-700 disabled:bg-zinc-200 disabled:text-zinc-400"
              >
                <ArrowUp className="size-4" />
              </button>
            </div>
          </form>
        </section>
      )}

      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? "Close chat" : `Open ${config.title}`}
        aria-expanded={open}
        className="flex size-14 items-center justify-center rounded-full bg-brand-600 text-white shadow-lg ring-1 ring-black/5 transition hover:scale-105 hover:bg-brand-700"
      >
        {open ? <X className="size-6" /> : <MessageCircle className="size-6" />}
      </button>
    </div>
  );
}

function Bubble({
  role,
  text,
  sources,
}: {
  role: "user" | "assistant";
  text: string;
  sources?: Source[];
}) {
  const labels = sources ? uniqueSourceLabels(sources) : [];
  return (
    <div className={cn("flex", role === "user" ? "justify-end" : "justify-start")}>
      <div className="max-w-[85%]">
        <div
          className={cn(
            "rounded-2xl px-3.5 py-2.5 leading-relaxed break-words whitespace-pre-wrap",
            role === "user"
              ? "rounded-br-md bg-brand-600 text-white"
              : "rounded-bl-md bg-zinc-100 text-zinc-900",
          )}
        >
          {text}
        </div>
        {labels.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {labels.map((label) => (
              <span
                key={label}
                className="inline-flex items-center gap-1 rounded-md bg-zinc-50 px-1.5 py-0.5 text-[11px] text-zinc-500 ring-1 ring-zinc-200"
              >
                <BookOpen className="size-3" aria-hidden />
                {label}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Notice({ text }: { text: string }) {
  return (
    <div className="flex items-center justify-center gap-1.5 py-1 text-xs text-zinc-500">
      <UserRound className="size-3.5" aria-hidden />
      {text}
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start" aria-label="Assistant is typing">
      <div className="flex gap-1 rounded-2xl rounded-bl-md bg-zinc-100 px-3.5 py-3">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="asa-dot size-1.5 rounded-full bg-zinc-500"
            style={{ animationDelay: `${i * 150}ms` }}
          />
        ))}
      </div>
    </div>
  );
}
