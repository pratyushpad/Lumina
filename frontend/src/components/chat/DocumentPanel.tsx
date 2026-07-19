import { motion } from "framer-motion";
import { FileText, Image as ImageIcon, X } from "lucide-react";
import { DocumentDropzone } from "@/components/upload/DocumentDropzone";
import { api } from "@/lib/api";
import { useDocumentStore } from "@/stores/documentStore";
import type { Document } from "@/types";

function StatusBadge({ status }: { status: Document["status"] }) {
  const map = {
    processing: {
      cls: "text-amber-300 border-amber-300/40",
      label: "PROCESSING",
      dot: "bg-amber-300 animate-pulse",
    },
    ready: { cls: "text-textPrimary border-textPrimary/40", label: "READY", dot: "bg-accent" },
    error: { cls: "text-rose-300 border-rose-300/40", label: "ERROR", dot: "bg-rose-300" },
  } as const;
  const v = map[status];
  return (
    <span className={`inline-flex items-center gap-1.5 border px-2 py-0.5 text-[9px] font-mono uppercase tracking-tight2 ${v.cls}`}>
      <span className={`h-1.5 w-1.5 ${v.dot}`} />
      {v.label}
    </span>
  );
}

export function DocumentPanel({ sessionId }: { sessionId: string }) {
  const docs = useDocumentStore((s) => s.documents[sessionId] || []);
  const removeDocument = useDocumentStore((s) => s.removeDocument);

  const handleDelete = async (id: string) => {
    await api.deleteDocument(id);
    removeDocument(sessionId, id);
  };

  return (
    <div className="border-b border-line bg-background px-6 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <DocumentDropzone sessionId={sessionId} />
        {docs.map((d) => (
          <motion.div
            key={d.id}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            className="group flex items-center gap-2.5 hairline bg-card px-3 py-2 text-sm"
          >
            {d.file_type === "image" ? (
              <ImageIcon size={14} className="text-textSecondary" />
            ) : (
              <FileText size={14} className="text-textSecondary" />
            )}
            <span className="max-w-[180px] truncate font-medium">{d.filename}</span>
            <span className="text-[10px] font-mono uppercase tracking-tight2 text-textMuted">
              {d.num_chunks} chunks
            </span>
            <StatusBadge status={d.status} />
            <button
              onClick={() => handleDelete(d.id)}
              className="ml-1 opacity-0 group-hover:opacity-100 text-textMuted hover:text-textPrimary transition-opacity"
            >
              <X size={13} />
            </button>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
