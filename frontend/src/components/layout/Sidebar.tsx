import { Command, Loader2, Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { GradientButton } from "@/components/ui/GradientButton";
import { SessionList } from "@/components/sessions/SessionList";
import { api } from "@/lib/api";
import { useSessionStore } from "@/stores/sessionStore";
import { toast } from "@/stores/toastStore";

export function Sidebar() {
  const addSession = useSessionStore((s) => s.addSession);
  const setActive = useSessionStore((s) => s.setActiveSession);
  const [creating, setCreating] = useState(false);

  const newSession = async () => {
    if (creating) return;
    setCreating(true);
    try {
      const s = await api.createSession("New Session");
      addSession(s);
      setActive(s.id);
    } catch {
      toast.error(
        "Could not create session",
        "The server may be waking up. Give it up to a minute and try again."
      );
    } finally {
      setCreating(false);
    }
  };

  return (
    <aside className="flex w-[280px] shrink-0 flex-col border-r border-line bg-background">
      <Link
        to="/"
        className="block border-b border-line px-5 py-5 transition-colors hover:bg-card"
      >
        <span className="font-display text-lg font-bold tracking-tight3">
          LUMINA<span className="text-accent">.</span>
        </span>
        <div className="mt-1 text-[10px] uppercase tracking-tight2 text-textMuted font-mono">
          Document intelligence
        </div>
      </Link>
      <div className="border-b border-line p-3">
        <GradientButton onClick={newSession} disabled={creating} className="w-full disabled:opacity-60">
          {creating ? (
            <>
              <Loader2 size={14} className="animate-spin" /> Creating
            </>
          ) : (
            <>
              <Plus size={14} /> New session
            </>
          )}
        </GradientButton>
      </div>
      <div className="flex-1 overflow-y-auto py-2">
        <SessionList />
      </div>
      <div className="border-t border-line px-4 py-3 text-[10px] uppercase tracking-tight2 font-mono text-textMuted flex items-center justify-between">
        <span>Quick switch</span>
        <kbd className="hairline bg-card px-1.5 py-0.5 inline-flex items-center gap-0.5">
          <Command size={9} /> K
        </kbd>
      </div>
    </aside>
  );
}
