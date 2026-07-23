import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Activity } from "lucide-react";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CitationChip } from "./CitationChip";
import { TraceInspector } from "./TraceInspector";
import { NumberTicker } from "@/components/ui/NumberTicker";
import { duration, ease } from "@/lib/motion";
import { STAGE_HINTS } from "@/lib/pipelineStages";
import type { Citation, StreamMeta } from "@/types";

interface Props {
  content: string;
  citations?: Citation[];
  streaming?: boolean;
  meta?: StreamMeta | null;
  modelUsed?: string | null;
  messageId?: string | null;
  stopped?: boolean;
}

/**
 * Qualitative retrieval pipeline choreography — reuses the exact stage
 * vocabulary from `TraceInspector`'s `STAGE_HINTS` (the real-trace inspector),
 * collapsed to one representative key per backend phase. This is a loading
 * *choreography*, not measured telemetry: no millisecond figures are shown
 * here. Real per-stage latency only ever appears in the TraceInspector,
 * sourced from an actual trace.
 */
const PIPELINE_KEYS = [
  "query_transform",
  "dense",
  "sparse_bm25",
  "fusion",
  "rerank",
  "generation",
] as const;
const PIPELINE_STAGES = PIPELINE_KEYS.map((key) => ({ key, label: STAGE_HINTS[key] }));

/**
 * Plays while an answer is awaited/streaming and no tokens have arrived yet.
 * The stage cascade before `retrievalDone` is an indicative timer — it does
 * not claim to measure anything. Once citations actually arrive over SSE
 * (`retrievalDone`), that is a real signal that retrieval has finished, so
 * the indicator jumps straight to "Generating" rather than keep guessing.
 */
function PipelineIndicator({ retrievalDone }: { retrievalDone: boolean }) {
  const reduceMotion = useReducedMotion();
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (reduceMotion || retrievalDone) return;
    const id = setInterval(() => {
      setTick((t) => Math.min(t + 1, PIPELINE_STAGES.length - 2));
    }, 420);
    return () => clearInterval(id);
  }, [reduceMotion, retrievalDone]);

  if (reduceMotion) {
    return (
      <div
        role="status"
        className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-tight2 text-textMuted"
      >
        <span className="h-1.5 w-1.5 bg-accent" />
        Working — retrieving context and generating an answer…
      </div>
    );
  }

  const activeIdx = retrievalDone ? PIPELINE_STAGES.length - 1 : tick;

  return (
    <div className="flex flex-col gap-4">
      <span className="sr-only" role="status" aria-live="polite">
        {PIPELINE_STAGES[activeIdx].label}…
      </span>
      <div
        aria-hidden
        className="flex flex-wrap items-center gap-y-2 font-mono text-[10px] uppercase tracking-tight2"
      >
        {PIPELINE_STAGES.map((stage, i) => {
          const state = i < activeIdx ? "done" : i === activeIdx ? "active" : "pending";
          return (
            <div key={stage.key} className="flex items-center">
              <motion.span
                animate={
                  state === "active"
                    ? { opacity: [0.55, 1, 0.55] }
                    : { opacity: state === "done" ? 1 : 0.35 }
                }
                transition={
                  state === "active"
                    ? { duration: 1.1, repeat: Infinity, ease: "easeInOut" }
                    : { duration: duration.base, ease }
                }
                className={`px-2 py-1 hairline ${
                  state === "pending" ? "text-textMuted" : "bg-card text-textPrimary"
                }`}
              >
                {stage.label}
              </motion.span>
              {i < PIPELINE_STAGES.length - 1 && <span className="mx-1 h-px w-3 bg-line" />}
            </div>
          );
        })}
      </div>
      <div className="flex flex-col gap-2">
        <div className="shimmer relative h-3 w-full overflow-hidden bg-card" />
        <div className="shimmer relative h-3 w-4/5 overflow-hidden bg-card" />
        <div className="shimmer relative h-3 w-3/5 overflow-hidden bg-card" />
      </div>
    </div>
  );
}

/** Blinking caret — a genuine on/off blink rather than a sinusoidal pulse. */
function StreamingCursor() {
  const reduceMotion = useReducedMotion();
  return (
    <motion.span
      aria-hidden
      className="ml-0.5 inline-block h-[1.1em] w-[3px] translate-y-[0.15em] bg-accent align-middle"
      animate={reduceMotion ? { opacity: 0.6 } : { opacity: [1, 1, 0, 0] }}
      transition={
        reduceMotion
          ? { duration: 0 }
          : { duration: 1, repeat: Infinity, ease: "linear", times: [0, 0.5, 0.5, 1] }
      }
    />
  );
}

function ProviderBadge({
  meta,
  modelUsed,
}: {
  meta?: StreamMeta | null;
  modelUsed?: string | null;
}) {
  // A cached demo answer stores the ORIGINAL provider:model in `model`, so show
  // that with a "cached" marker rather than "cache:local:…".
  if (meta?.cached) {
    return (
      <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-tight2 text-textMuted">
        <span className="h-1.5 w-1.5 bg-textMuted" />
        cached{meta.model ? ` · ${meta.model}` : ""}
      </span>
    );
  }
  const label = meta ? `${meta.provider}:${meta.model}` : modelUsed;
  if (!label) return null;
  const local = label.startsWith("local:");
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-tight2 text-textMuted">
      <span className={`h-1.5 w-1.5 ${local ? "bg-local" : "bg-accent"}`} />
      {label}
      {meta && meta.tokens_per_sec > 0 && (
        <span>
          {" "}
          ·{" "}
          <NumberTicker
            value={meta.tokens_per_sec}
            decimals={1}
            suffix={meta.tokens_estimated ? "~" : ""}
          />{" "}
          tok/s
        </span>
      )}
    </span>
  );
}

export function StreamingMessage({
  content,
  citations,
  streaming,
  meta,
  modelUsed,
  messageId,
  stopped,
}: Props) {
  const [showTrace, setShowTrace] = useState(false);
  const reduceMotion = useReducedMotion();
  // Only DB-persisted messages (uuid ids) have traces — not the tmp-/err-/
  // stopped- placeholders the client creates locally.
  const traceable = !!messageId && !/^(tmp|err|stopped)-/.test(messageId);
  const showPipeline = !!streaming && content.length === 0;

  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: duration.slow, ease }}
      className="hairline bg-surface p-5 max-w-[85%]"
    >
      <AnimatePresence mode="wait" initial={false}>
        {showPipeline ? (
          <motion.div
            key="pipeline"
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: duration.fast, ease }}
          >
            <PipelineIndicator retrievalDone={(citations?.length ?? 0) > 0} />
          </motion.div>
        ) : (
          <motion.div
            key="content"
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: duration.fast, ease }}
            className="prose prose-sm max-w-none font-serif prose-p:font-serif prose-p:text-[0.95rem] prose-p:leading-relaxed prose-headings:font-display prose-headings:tracking-tight2 prose-p:my-2 prose-code:bg-card prose-code:px-1 prose-code:py-0.5 prose-code:before:content-[''] prose-code:after:content-['']"
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            {streaming && <StreamingCursor />}
          </motion.div>
        )}
      </AnimatePresence>
      {stopped && (
        <p className="mt-2 font-mono text-[10px] uppercase tracking-tight2 text-textMuted">
          Stopped · not saved
        </p>
      )}
      {citations && citations.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2 border-t border-line pt-4">
          {citations.map((c) => (
            <CitationChip key={c.chunk_id} citation={c} />
          ))}
        </div>
      )}
      {!streaming && (meta || modelUsed || traceable) && (
        <div className="mt-3 flex items-center justify-end gap-3">
          <ProviderBadge meta={meta} modelUsed={modelUsed} />
          {traceable && (
            <button
              onClick={() => setShowTrace(true)}
              title="Inspect retrieval pipeline"
              className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-tight2 text-textMuted hover:text-textPrimary transition-colors"
            >
              <Activity size={11} />
              trace
            </button>
          )}
        </div>
      )}
      {showTrace && messageId && (
        <TraceInspector messageId={messageId} onClose={() => setShowTrace(false)} />
      )}
    </motion.div>
  );
}
