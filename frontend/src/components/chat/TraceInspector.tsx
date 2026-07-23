import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { NumberTicker } from "@/components/ui/NumberTicker";
import { api } from "@/lib/api";
import { duration, ease, waterfallStep } from "@/lib/motion";
import { STAGE_HINTS } from "@/lib/pipelineStages";
import type { Trace, TraceStage } from "@/types";

function StageRow({ stage, maxMs, index }: { stage: TraceStage; maxMs: number; index: number }) {
  const [open, setOpen] = useState(false);
  const reduceMotion = useReducedMotion();
  const p = stage.payload || {};
  // Real proportion of the slowest stage — set once as a static width. Only
  // the *reveal* of that bar (scaleX 0→1) is animated, never the width itself.
  const widthPct = maxMs > 0 ? Math.max(2, (stage.latency_ms / maxMs) * 100) : 2;
  const revealDelay = reduceMotion ? 0 : index * waterfallStep;
  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: duration.base, ease, delay: revealDelay }}
      className="hairline bg-card"
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-3 py-2 text-left"
      >
        <span className="w-28 shrink-0 font-mono text-[11px] uppercase tracking-tight2">
          {stage.stage}
        </span>
        <span className="relative h-2 flex-1 overflow-hidden bg-background">
          <motion.span
            className="absolute inset-y-0 left-0 bg-accent"
            style={{ width: `${widthPct}%`, transformOrigin: "left" }}
            initial={reduceMotion ? false : { scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{
              duration: duration.slow,
              ease,
              delay: revealDelay + (reduceMotion ? 0 : 0.08),
            }}
          />
        </span>
        <span className="w-16 shrink-0 text-right font-mono text-[11px] text-textMuted">
          <NumberTicker value={stage.latency_ms} decimals={0} suffix=" ms" />
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
    </motion.div>
  );
}

export function TraceInspector({ messageId, onClose }: { messageId: string; onClose: () => void }) {
  const [trace, setTrace] = useState<Trace | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    api
      .getTrace(messageId)
      .then(setTrace)
      .catch(() => setError("No trace recorded for this message."));
  }, [messageId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const maxMs = trace ? Math.max(...trace.stages.map((s) => s.latency_ms), 1) : 1;

  // Rendered into document.body: this panel is `position: fixed`, but it is
  // mounted inside a message bubble that Framer animates with a transform, and
  // a transformed ancestor becomes the containing block for fixed descendants —
  // which would pin the overlay to the bubble instead of the viewport.
  return createPortal(
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 bg-textPrimary/35"
        onClick={onClose}
      >
        <motion.aside
          initial={reduceMotion ? { opacity: 0 } : { x: "100%" }}
          animate={reduceMotion ? { opacity: 1 } : { x: 0 }}
          exit={reduceMotion ? { opacity: 0 } : { x: "100%" }}
          transition={{ duration: duration.slow, ease }}
          onClick={(e) => e.stopPropagation()}
          className="absolute right-0 top-0 h-full w-full max-w-md overflow-y-auto border-l border-line bg-surface p-5"
        >
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-display text-sm uppercase tracking-tight2">Query trace</h2>
            <button onClick={onClose} className="hairline bg-card p-1.5">
              <X size={14} />
            </button>
          </div>
          {error && <p className="text-sm text-textMuted">{error}</p>}
          {trace && (
            <>
              <p className="mb-1 text-sm">{trace.query}</p>
              <p className="mb-4 font-mono text-[11px] uppercase tracking-tight2 text-textMuted">
                <NumberTicker value={trace.total_ms} decimals={0} suffix=" ms total" />
                {trace.provider && (
                  <>
                    {" "}
                    · {trace.provider}:{trace.model}
                    {trace.tokens_per_sec ? ` · ${trace.tokens_per_sec.toFixed(1)} tok/s` : ""}
                  </>
                )}
              </p>
              <div className="flex flex-col gap-1.5">
                {trace.stages.map((s, i) => (
                  <StageRow key={s.seq} stage={s} maxMs={maxMs} index={i} />
                ))}
              </div>
            </>
          )}
        </motion.aside>
      </motion.div>
    </AnimatePresence>,
    document.body,
  );
}
