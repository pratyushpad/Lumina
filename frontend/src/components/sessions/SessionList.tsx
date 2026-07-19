import { motion } from "framer-motion";
import { Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { useSessionStore } from "@/stores/sessionStore";
import type { Session } from "@/types";

export function SessionList() {
  const sessions = useSessionStore((s) => s.sessions);
  const activeId = useSessionStore((s) => s.activeSessionId);
  const setActive = useSessionStore((s) => s.setActiveSession);
  const remove = useSessionStore((s) => s.removeSession);

  const handleDelete = async (e: React.MouseEvent, s: Session) => {
    e.stopPropagation();
    if (!confirm(`Delete session "${s.name}"?`)) return;
    await api.deleteSession(s.id);
    remove(s.id);
  };

  if (sessions.length === 0) {
    return (
      <div className="text-[11px] uppercase tracking-tight2 text-textMuted px-1 py-2">
        No sessions yet
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      {sessions.map((s) => {
        const active = s.id === activeId;
        return (
          <motion.div
            key={s.id}
            whileHover={{ x: 1 }}
            onClick={() => setActive(s.id)}
            className={`group relative cursor-pointer px-3 py-2.5 text-sm transition-colors ${
              active
                ? "bg-card text-textPrimary accent-bar"
                : "text-textSecondary hover:bg-card/60 hover:text-textPrimary"
            }`}
          >
            <div className="flex items-center gap-2">
              <span className={`h-1.5 w-1.5 ${active ? "bg-accent" : "bg-textMuted"}`} />
              <span className="truncate font-medium tracking-tight2">{s.name}</span>
              <button
                onClick={(e) => handleDelete(e, s)}
                className="ml-auto opacity-0 group-hover:opacity-100 text-textMuted hover:text-textPrimary transition-opacity"
              >
                <Trash2 size={13} />
              </button>
            </div>
            <div className="mt-1 text-[10px] uppercase tracking-tight2 text-textMuted font-mono">
              {s.document_count} docs · {s.message_count} msgs
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
