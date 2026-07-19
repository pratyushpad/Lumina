import { motion } from "framer-motion";
import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";
import { ChatArea } from "@/components/chat/ChatArea";
import { DocumentPanel } from "@/components/chat/DocumentPanel";
import { useDocumentStatusPolling } from "@/hooks/useDocumentStatus";
import { api } from "@/lib/api";
import { useDocumentStore } from "@/stores/documentStore";
import { useSessionStore } from "@/stores/sessionStore";

const DEMO_SESSION_ID = "demo";

const DEMO_SUGGESTIONS = [
  {
    label: "Why is dot-product attention scaled by 1/√dk?",
    query: "Why does the Transformer scale dot-product attention by 1 over the square root of d_k?",
  },
  {
    label: "How do residual connections help train very deep networks?",
    query: "According to the ResNet paper, how do residual connections help train very deep networks?",
  },
  {
    label: "What BLEU score did the Transformer get on WMT14 En→De?",
    query: "What BLEU score did the Transformer achieve on the WMT 2014 English-to-German translation task?",
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
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    api.listSessions().then((r) => {
      setSessions(r.sessions);
      const requested = searchParams.get("session");
      if (requested && r.sessions.some((s) => s.id === requested)) {
        setActiveSession(requested);
        setSearchParams({}, { replace: true });
      }
    });
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
        {!activeSessionId ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-1 items-center justify-center px-6"
          >
            <div className="text-center max-w-md">
              <div className="text-[10px] uppercase tracking-tight2 text-textMuted font-mono">
                01 / Begin
              </div>
              <h2 className="mt-3 font-display text-4xl font-bold tracking-tight3">
                Select or create<br />a session.
              </h2>
              <p className="mt-4 text-sm text-textSecondary">
                {sessions.length === 0
                  ? "Hit New session in the sidebar to start."
                  : "Pick one from the sidebar, or create a new one."}
              </p>
              <div className="mt-8 inline-flex items-center gap-2 hairline bg-card px-3 py-1.5 text-[10px] uppercase tracking-tight2 text-textMuted font-mono">
                <span className="h-1.5 w-1.5 bg-accent" />
                Ready
              </div>
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
