import { motion, useReducedMotion } from "framer-motion";
import { MessagesSquare } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { SessionListResponse } from "@/types";
import { Sidebar } from "@/components/layout/Sidebar";
import { ChatArea } from "@/components/chat/ChatArea";
import { DocumentPanel } from "@/components/chat/DocumentPanel";
import { useDocumentStatusPolling } from "@/hooks/useDocumentStatus";
import { api, pingHealth } from "@/lib/api";
import { DEMO_SESSION_ID } from "@/lib/constants";
import { duration, ease, fadeRise, staggerStep } from "@/lib/motion";
import { useAuthStore } from "@/stores/authStore";
import { useDocumentStore } from "@/stores/documentStore";
import { useSessionStore } from "@/stores/sessionStore";
import { toast } from "@/stores/toastStore";

const EMPTY_STATE_FEATURES = ["Hybrid retrieval", "Cited answers", "Query trace"];

const DEMO_SUGGESTIONS = [
  {
    label: "Why is dot-product attention scaled by 1/√dk?",
    query: "Why does the Transformer scale dot-product attention by 1 over the square root of d_k?",
  },
  {
    label: "How do residual connections help train very deep networks?",
    query:
      "According to the ResNet paper, how do residual connections help train very deep networks?",
  },
  {
    label: "What BLEU score did the Transformer get on WMT14 En→De?",
    query:
      "What BLEU score did the Transformer achieve on the WMT 2014 English-to-German translation task?",
  },
  {
    label: "What's the capital of France? (off-topic — watch it refuse)",
    query: "What is the capital of France?",
    guardrail: true,
  },
];

export default function AppPage() {
  const sessions = useSessionStore((s) => s.sessions);
  const setSessions = useSessionStore((s) => s.setSessions);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const setActiveSession = useSessionStore((s) => s.setActiveSession);
  const setDocuments = useDocumentStore((s) => s.setDocuments);
  const hydrateAuth = useAuthStore((s) => s.hydrate);
  const [searchParams, setSearchParams] = useSearchParams();
  const reduceMotion = useReducedMotion();
  // True while the free-tier API is cold-starting (30–60 s on the HF Space).
  const [apiWaking, setApiWaking] = useState(false);

  // Turn a stored session token into a signed-in user (or drop it if stale).
  useEffect(() => {
    hydrateAuth();
  }, [hydrateAuth]);

  useEffect(() => {
    let cancelled = false;
    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

    const applySessions = (r: SessionListResponse) => {
      setSessions(r.sessions);
      const requested = searchParams.get("session");
      if (!requested) return;
      if (r.sessions.some((s) => s.id === requested)) {
        setActiveSession(requested);
      } else {
        // Landing links straight to ?session=demo; if seeding has not run the
        // user would otherwise get a blank pane with no explanation.
        toast.error(
          "That session isn't available",
          requested === "demo"
            ? "The demo is still being prepared on the server. Try again shortly, or upload your own document."
            : "It may have been deleted.",
        );
      }
      setSearchParams({}, { replace: true });
    };

    (async () => {
      // First attempt gets a hard timeout: a cold HF Space can leave the
      // request hanging for the whole 30–60 s wake, which would otherwise
      // look like a dead app with no feedback.
      try {
        const r = await api.listSessions({ signal: AbortSignal.timeout(10_000) });
        if (!cancelled) applySessions(r);
        return;
      } catch {
        if (cancelled) return;
      }

      // Timeout or failure on first contact — almost always the free-tier
      // Space cold-starting. Show the waking state and poll /health with
      // backoff instead of surfacing an error toast.
      setApiWaking(true);
      const delays = [3_000, 5_000, 8_000, 10_000, 10_000, 10_000, 10_000, 10_000];
      for (const ms of delays) {
        await sleep(ms);
        if (cancelled) return;
        if (!(await pingHealth())) continue;
        try {
          const r = await api.listSessions();
          if (!cancelled) {
            setApiWaking(false);
            applySessions(r);
          }
          return;
        } catch {
          // Health said up but the call still failed — keep polling.
          if (cancelled) return;
        }
      }
      if (!cancelled) {
        setApiWaking(false);
        toast.error(
          "Could not reach the server",
          "The free-tier API did not wake up in time. Give it a minute and refresh.",
        );
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setSessions]);

  useEffect(() => {
    if (activeSessionId) {
      api.listDocuments(activeSessionId).then((d) => setDocuments(activeSessionId, d));
    }
  }, [activeSessionId, setDocuments]);

  useDocumentStatusPolling(activeSessionId);

  return (
    <div className="flex h-screen bg-background text-textPrimary">
      <Sidebar />
      <main className="flex flex-1 flex-col overflow-hidden">
        {!activeSessionId && apiWaking ? (
          <motion.div
            initial={reduceMotion ? "visible" : "hidden"}
            animate="visible"
            variants={{
              hidden: {},
              visible: { transition: { staggerChildren: staggerStep, delayChildren: 0.05 } },
            }}
            className="flex flex-1 items-center justify-center px-6"
          >
            <div
              role="status"
              aria-live="polite"
              className="max-w-md hairline-strong bg-surface px-8 py-10 text-center"
            >
              <motion.div
                variants={fadeRise}
                transition={{ duration: duration.base, ease }}
                className="font-mono text-[10px] uppercase tracking-tight2 text-textMuted"
              >
                Free-tier cold start
              </motion.div>
              <motion.h2
                variants={fadeRise}
                transition={{ duration: duration.base, ease }}
                className="mt-3 font-display text-4xl font-bold tracking-tight3"
              >
                Waking
                <br />
                the API.
              </motion.h2>
              <motion.p
                variants={fadeRise}
                transition={{ duration: duration.base, ease }}
                className="mt-4 text-sm text-textSecondary"
              >
                The backend sleeps when idle to keep hosting free. A cold start usually takes about
                30 seconds — it retries automatically, no refresh needed.
              </motion.p>
              <motion.div
                variants={fadeRise}
                transition={{ duration: duration.base, ease }}
                className="mt-8 inline-flex items-center gap-2 hairline bg-card px-3 py-1.5 text-[10px] uppercase tracking-tight2 text-textMuted font-mono"
              >
                <span className="h-1.5 w-1.5 bg-accent motion-safe:animate-pulse" />
                Connecting
              </motion.div>
            </div>
          </motion.div>
        ) : !activeSessionId ? (
          <motion.div
            initial={reduceMotion ? "visible" : "hidden"}
            animate="visible"
            variants={{
              hidden: {},
              visible: { transition: { staggerChildren: staggerStep, delayChildren: 0.05 } },
            }}
            className="flex flex-1 items-center justify-center px-6"
          >
            <div className="max-w-md hairline-strong bg-surface px-8 py-10 text-center">
              <motion.div
                variants={fadeRise}
                transition={{ duration: duration.base, ease }}
                className="mx-auto mb-6 flex h-12 w-12 items-center justify-center hairline bg-card"
              >
                <MessagesSquare size={20} className="text-accent" strokeWidth={1.75} />
              </motion.div>
              <motion.div
                variants={fadeRise}
                transition={{ duration: duration.base, ease }}
                className="font-mono text-[10px] uppercase tracking-tight2 text-textMuted"
              >
                Workbench idle
              </motion.div>
              <motion.h2
                variants={fadeRise}
                transition={{ duration: duration.base, ease }}
                className="mt-3 font-display text-4xl font-bold tracking-tight3"
              >
                Select or create
                <br />a session.
              </motion.h2>
              <motion.p
                variants={fadeRise}
                transition={{ duration: duration.base, ease }}
                className="mt-4 text-sm text-textSecondary"
              >
                {sessions.length === 0
                  ? "Hit New session in the sidebar to start."
                  : "Pick one from the sidebar, or create a new one."}
              </motion.p>
              <motion.div
                variants={fadeRise}
                transition={{ duration: duration.base, ease }}
                className="mt-8 flex flex-wrap items-center justify-center gap-2 border-t border-line pt-6"
              >
                {EMPTY_STATE_FEATURES.map((f) => (
                  <span
                    key={f}
                    className="hairline bg-card px-2.5 py-1 text-[10px] font-mono uppercase tracking-tight2 text-textMuted"
                  >
                    {f}
                  </span>
                ))}
              </motion.div>
              <motion.div
                variants={fadeRise}
                transition={{ duration: duration.base, ease }}
                className="mt-6 inline-flex items-center gap-2 hairline bg-card px-3 py-1.5 text-[10px] uppercase tracking-tight2 text-textMuted font-mono"
              >
                <span className="h-1.5 w-1.5 bg-accent" />
                Ready
              </motion.div>
            </div>
          </motion.div>
        ) : (
          <>
            <DocumentPanel sessionId={activeSessionId} />
            <ChatArea
              sessionId={activeSessionId}
              suggestions={activeSessionId === DEMO_SESSION_ID ? DEMO_SUGGESTIONS : undefined}
            />
          </>
        )}
      </main>
    </div>
  );
}
