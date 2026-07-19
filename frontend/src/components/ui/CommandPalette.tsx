import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Home, MessageSquare, Plus, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useSessionStore } from "@/stores/sessionStore";
import { toast } from "@/stores/toastStore";

type CommandKind = "action" | "session";

interface Command {
  id: string;
  kind: CommandKind;
  label: string;
  hint?: string;
  icon: typeof Search;
  onSelect: () => void;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const sessions = useSessionStore((s) => s.sessions);
  const setActive = useSessionStore((s) => s.setActiveSession);
  const addSession = useSessionStore((s) => s.addSession);

  // Open with ⌘K / Ctrl+K, close with Esc
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isMod = e.metaKey || e.ctrlKey;
      if (isMod && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    if (open) {
      setQuery("");
      setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [open]);

  const close = () => setOpen(false);

  const newSessionAction = async () => {
    close();
    try {
      const s = await api.createSession("New Session");
      addSession(s);
      setActive(s.id);
      navigate("/app");
    } catch {
      toast.error(
        "Could not create session",
        "The server may be waking up. Give it up to a minute and try again."
      );
    }
  };

  const all: Command[] = useMemo(() => {
    const actions: Command[] = [
      {
        id: "new",
        kind: "action",
        label: "New session",
        hint: "Create a fresh chat",
        icon: Plus,
        onSelect: newSessionAction,
      },
      {
        id: "app",
        kind: "action",
        label: "Open app",
        hint: "Go to workspace",
        icon: ArrowRight,
        onSelect: () => {
          navigate("/app");
          close();
        },
      },
      {
        id: "landing",
        kind: "action",
        label: "Landing page",
        hint: "Go home",
        icon: Home,
        onSelect: () => {
          navigate("/");
          close();
        },
      },
    ];
    const sessionCmds: Command[] = sessions.map((s) => ({
      id: `s:${s.id}`,
      kind: "session",
      label: s.name,
      hint: `${s.document_count} docs · ${s.message_count} msgs`,
      icon: MessageSquare,
      onSelect: () => {
        setActive(s.id);
        navigate("/app");
        close();
      },
    }));
    return [...actions, ...sessionCmds];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessions]);

  const filtered = useMemo(() => {
    if (!query.trim()) return all;
    const q = query.toLowerCase();
    return all.filter(
      (c) => c.label.toLowerCase().includes(q) || c.hint?.toLowerCase().includes(q)
    );
  }, [all, query]);

  const [cursor, setCursor] = useState(0);
  useEffect(() => setCursor(0), [query, open]);

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor((c) => Math.min(c + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((c) => Math.max(c - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      filtered[cursor]?.onSelect();
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.12 }}
          className="fixed inset-0 z-[90] flex items-start justify-center bg-textPrimary/40 backdrop-blur-sm pt-[18vh] px-4"
          onClick={close}
        >
          <motion.div
            initial={{ y: -8, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -8, opacity: 0 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-xl hairline-strong bg-surface shadow-2xl"
          >
            <div className="flex items-center gap-3 border-b border-line px-4 py-3">
              <Search size={16} className="text-textMuted" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKey}
                placeholder="Search sessions or run a command…"
                className="flex-1 bg-transparent text-sm text-textPrimary outline-none placeholder:text-textMuted"
              />
              <kbd className="hairline px-1.5 py-0.5 text-[10px] font-mono uppercase text-textMuted">
                Esc
              </kbd>
            </div>
            <div className="max-h-[50vh] overflow-y-auto">
              {filtered.length === 0 && (
                <div className="px-4 py-6 text-sm text-textMuted text-center">
                  No matches
                </div>
              )}
              {filtered.map((c, i) => {
                const Icon = c.icon;
                const active = i === cursor;
                return (
                  <button
                    key={c.id}
                    onMouseEnter={() => setCursor(i)}
                    onClick={c.onSelect}
                    className={`group flex w-full items-center gap-3 px-4 py-3 text-left text-sm transition-colors ${
                      active ? "bg-card text-textPrimary" : "text-textSecondary hover:bg-card/60"
                    }`}
                  >
                    <Icon size={14} className={active ? "text-accent" : "text-textMuted"} />
                    <span className="flex-1 truncate font-medium tracking-tight2">
                      {c.label}
                    </span>
                    {c.hint && (
                      <span className="text-[10px] font-mono uppercase tracking-tight2 text-textMuted">
                        {c.hint}
                      </span>
                    )}
                    {active && (
                      <span className="text-[10px] font-mono uppercase tracking-tight2 text-accent">
                        ↵
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
            <div className="flex items-center justify-between border-t border-line px-4 py-2.5 text-[10px] uppercase tracking-tight2 font-mono text-textMuted">
              <span className="inline-flex items-center gap-3">
                <span>↑↓ navigate</span>
                <span>↵ open</span>
              </span>
              <span>{filtered.length} result{filtered.length === 1 ? "" : "s"}</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
