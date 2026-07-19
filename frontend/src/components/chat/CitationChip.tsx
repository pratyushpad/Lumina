import { AnimatePresence, motion } from "framer-motion";
import { FileText, Image as ImageIcon } from "lucide-react";
import { useState } from "react";
import type { Citation } from "@/types";

function scoreColor(score: number) {
  if (score >= 0.8) return "bg-accent";
  if (score >= 0.5) return "bg-textSecondary";
  return "bg-textMuted";
}

export function CitationChip({ citation }: { citation: Citation }) {
  const [open, setOpen] = useState(false);
  const Icon = citation.has_image ? ImageIcon : FileText;
  return (
    <div className="inline-block">
      <motion.button
        whileHover={{ y: -1 }}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-2 hairline bg-card px-3 py-1.5 text-[11px] uppercase tracking-tight2 text-textSecondary hover:text-textPrimary hover:border-textPrimary/40 transition-colors"
      >
        <Icon size={11} />
        <span className="font-mono normal-case text-textPrimary truncate max-w-[180px]">
          {citation.filename}
        </span>
        {citation.page_num != null && <span className="font-mono">p.{citation.page_num}</span>}
        <span className={`h-1.5 w-1.5 ${scoreColor(citation.relevance_score)}`} />
      </motion.button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18 }}
            className="mt-2 overflow-hidden hairline bg-background p-3 text-xs text-textSecondary font-mono leading-relaxed"
          >
            {citation.chunk_text}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
