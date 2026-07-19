import { motion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";
import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { api } from "@/lib/api";
import { useDocumentStore } from "@/stores/documentStore";
import { toast } from "@/stores/toastStore";

export function DocumentDropzone({ sessionId }: { sessionId: string }) {
  const addDocument = useDocumentStore((s) => s.addDocument);

  const onDrop = useCallback(
    async (files: File[]) => {
      for (const file of files) {
        try {
          const resp = await api.uploadDocument(sessionId, file);
          addDocument(sessionId, {
            id: resp.document_id,
            filename: resp.filename,
            file_type: file.name.split(".").pop() || "unknown",
            file_size_bytes: file.size,
            num_chunks: 0,
            status: "processing",
            uploaded_at: new Date().toISOString(),
          });
          toast.info(`Processing ${file.name}`, "We'll let you know when it's ready.");
        } catch (e) {
          const msg = e instanceof Error ? e.message : "Upload failed";
          toast.error(`Couldn't upload ${file.name}`, msg);
        }
      }
    },
    [sessionId, addDocument]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "text/plain": [".txt"],
      "text/markdown": [".md"],
      "image/png": [".png"],
      "image/jpeg": [".jpg", ".jpeg"],
    },
  });

  return (
    <motion.div
      {...(getRootProps() as any)}
      whileHover={{ y: -1 }}
      className={`group flex cursor-pointer items-center gap-3 px-4 py-3 transition-colors ${
        isDragActive
          ? "bg-accentDim hairline-strong"
          : "hairline bg-card hover:border-textPrimary/30"
      }`}
    >
      <input {...getInputProps()} />
      <ArrowUpRight
        className="text-textPrimary transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
        size={18}
      />
      <div className="text-sm leading-tight">
        <div className="font-medium text-textPrimary tracking-tight2">Upload document</div>
        <div className="text-[11px] uppercase tracking-tight2 text-textMuted mt-0.5">
          PDF · TXT · MD · PNG · JPG
        </div>
      </div>
    </motion.div>
  );
}
