import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Trace, TraceStage } from "@/types";

const STAGE_HINTS: Record<string, string> = {
  query_transform: "LLM query rewriting",
  dense: "pgvector cosine ANN",
  sparse_bm25: "Okapi BM25 (in-process)",
  sparse_fts: "Postgres ts_rank_cd",
  fusion: "Reciprocal Rank Fusion",
  hybrid_sql: "dense + FTS + RRF in one SQL",
  rerank: "cross-encoder rerank",
  vision_enrich: "image description (Gemini)",
  generation: "answer generation",
};

function StageRow({ stage, maxMs }: { stage: TraceStage; maxMs: number }) {
  const [open, setOpen] = useState(false);
  const p = stage.payload || {};
  const widthPct = maxMs > 0 ? Math.max(2, (stage.latency_ms / maxMs) * 100) : 2;
  return (
    <div className="hairline bg-card">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-3 py-2 text-left"
      >
        <span className="w-28 shrink-0 font-mono text-[11px] uppercase tracking-tight2">
          {stage.stage}
        </span>
        <span className="relative h-2 flex-1 bg-background">
          <span
            className="absolute inset-y-0 left-0 bg-accent"
            style={{ width: `${widthPct}%` }}
          />
        </span>
        <span className="w-16 shrink-0 text-right font-mono text-[11px] text-textMuted">
          {stage.latency_ms} ms
        </span>
      </button>
      {open && (
        <div className="border-t border-line px-3 py-2 text-[11px] text-textMuted">
          <div className="mb-1 font-mono uppercase tracking-tight2">
            {STAGE_HINTS[stage.stage] || stage.stage}
            {typeof p.count === "number" && <span> · {p.count} candidates</span>}
          </div>
          {p.kind === "multi_query" && Array.isArray(p.queries) && (
            <ul className="mb-2 list-disc pl-4">
              {p.queries.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ul>
          )}
          {stage.stage === "generation" && (
            <div className="font-mono">
              {String(p.provider)}:{String(p.model)} · {String(p.completion_tokens)} tok ·{" "}
              {String(p.tokens_per_sec)} tok/s
            </div>
          )}
          {Array.isArray(p.top) && p.top.length > 0 && (
            <table className="w-full font-mono">
              <tbody>
                {p.top.slice(0, 10).map((c) => (
                  <tr key={c.chunk_id} className="border-t border-line/50">
                    <td className="truncate py-0.5 pr-2 max-w-[220px]">{c.chunk_id}</td>
                    <td className="py-0.5 text-right">{c.score.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

export function TraceInspector({
  messageId,
  onClose,
}: {
  messageId: string;
  onClose: () => void;
}) {
  const [trace, setTrace] = useState<Trace | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getTrace(messageId)
      .then(setTrace)
      .catch(() => setError("No trace recorded for this message."));
  }, [messageId]);

  const maxMs = trace ? Math.max(...trace.stages.map((s) => s.latency_ms), 1) : 1;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 bg-black/60"
        onClick={onClose}
      >
        <motion.aside
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "tween", duration: 0.22 }}
          onClick={(e) => e.stopPropagation()}
          className="absolute right-0 top-0 h-full w-full max-w-md overflow-y-auto border-l border-line bg-surface p-5"
        >
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-display text-sm uppercase tracking-tight2">
              Query trace
            </h2>
            <button onClick={onClose} className="hairline bg-card p-1.5">
              <X size={14} />
            </button>
          </div>
          {error && <p className="text-sm text-textMuted">{error}</p>}
          {trace && (
            <>
              <p className="mb-1 text-sm">{trace.query}</p>
              <p className="mb-4 font-mono text-[11px] uppercase tracking-tight2 text-textMuted">
                {trace.total_ms} ms total
                {trace.provider && (
                  <>
                    {" "}
                    · {trace.provider}:{trace.model}
                    {trace.tokens_per_sec ? ` · ${trace.tokens_per_sec.toFixed(1)} tok/s` : ""}
                  </>
                )}
              </p>
              <div className="flex flex-col gap-1.5">
                {trace.stages.map((s) => (
                  <StageRow key={s.seq} stage={s} maxMs={maxMs} />
                ))}
              </div>
            </>
          )}
        </motion.aside>
      </motion.div>
    </AnimatePresence>
  );
}
