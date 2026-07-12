import { motion } from "framer-motion";
import { Activity } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CitationChip } from "./CitationChip";
import { TraceInspector } from "./TraceInspector";
import type { Citation, StreamMeta } from "@/types";

interface Props {
  content: string;
  citations?: Citation[];
  streaming?: boolean;
  meta?: StreamMeta | null;
  modelUsed?: string | null;
  messageId?: string | null;
}

function ProviderBadge({ meta, modelUsed }: { meta?: StreamMeta | null; modelUsed?: string | null }) {
  const label = meta ? `${meta.provider}:${meta.model}` : modelUsed;
  if (!label) return null;
  const local = label.startsWith("local:");
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-tight2 text-textMuted">
      <span className={`h-1.5 w-1.5 ${local ? "bg-emerald-400" : "bg-accent"}`} />
      {label}
      {meta && meta.tokens_per_sec > 0 && (
        <span>
          · {meta.tokens_per_sec}
          {meta.tokens_estimated ? "~" : ""} tok/s
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
}: Props) {
  const [showTrace, setShowTrace] = useState(false);
  // Only DB-persisted messages (uuid ids) have traces — not tmp-/err- placeholders
  const traceable = !!messageId && !/^(tmp|err)-/.test(messageId);
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="hairline bg-surface p-5 max-w-[85%]"
    >
      <div className="prose prose-invert prose-sm max-w-none prose-headings:font-display prose-headings:tracking-tight2 prose-p:my-2 prose-code:bg-card prose-code:px-1 prose-code:py-0.5 prose-code:before:content-[''] prose-code:after:content-['']">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        {streaming && (
          <span className="ml-0.5 inline-block h-3.5 w-2 bg-accent align-middle animate-pulse" />
        )}
      </div>
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
