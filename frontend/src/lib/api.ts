import type {
  Citation,
  Document,
  DocumentStatusResponse,
  DocumentUploadResponse,
  Message,
  Session,
  SessionListResponse,
  StreamMeta,
  Trace,
} from "@/types";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // sessions
  createSession: (name?: string) =>
    http<Session>("/api/sessions/", { method: "POST", body: JSON.stringify({ name }) }),
  listSessions: () => http<SessionListResponse>("/api/sessions/"),
  getSession: (id: string) => http<Session>(`/api/sessions/${id}`),
  renameSession: (id: string, name: string) =>
    http<Session>(`/api/sessions/${id}`, { method: "PATCH", body: JSON.stringify({ name }) }),
  deleteSession: (id: string) => http<{ message: string }>(`/api/sessions/${id}`, { method: "DELETE" }),

  // documents
  uploadDocument: async (sessionId: string, file: File): Promise<DocumentUploadResponse> => {
    const fd = new FormData();
    fd.append("session_id", sessionId);
    fd.append("file", file);
    const res = await fetch(`${BASE_URL}/api/documents/upload`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  listDocuments: (sessionId: string) =>
    http<Document[]>(`/api/documents/session/${sessionId}`),
  getDocumentStatus: (documentId: string) =>
    http<DocumentStatusResponse>(`/api/documents/${documentId}/status`),
  deleteDocument: (documentId: string) =>
    http<{ chunks_deleted: number }>(`/api/documents/${documentId}`, { method: "DELETE" }),

  // chat history
  getHistory: (sessionId: string) => http<Message[]>(`/api/chat/${sessionId}/history`),

  // traces
  getTrace: (messageId: string) => http<Trace>(`/api/traces/${messageId}`),

  // config (model name, limits)
  getConfig: () =>
    http<{
      model: string;
      max_file_size_mb: number;
      allowed_extensions: string[];
      top_k_reranked: number;
    }>("/api/config"),
};

export interface StreamHandlers {
  onCitations: (c: Citation[]) => void;
  onToken: (t: string) => void;
  onMeta?: (m: StreamMeta) => void;
  onDone: (messageId?: string) => void;
  onError: (e: string) => void;
}

export function streamChat(sessionId: string, query: string, h: StreamHandlers): () => void {
  const url = `${BASE_URL}/api/chat/${sessionId}/stream?query=${encodeURIComponent(query)}`;
  const es = new EventSource(url);
  let finished = false;

  const finish = () => {
    finished = true;
    es.close();
  };

  es.onmessage = (e) => {
    try {
      const payload = JSON.parse(e.data);
      if (payload.type === "citations") h.onCitations(payload.data || []);
      else if (payload.type === "token") h.onToken(payload.data || "");
      else if (payload.type === "meta") h.onMeta?.(payload.data);
      else if (payload.type === "done") {
        h.onDone(payload.data?.message_id);
        finish();
      } else if (payload.type === "error") {
        h.onError(payload.data || "stream error");
        finish();
      }
    } catch (err) {
      if (!finished) h.onError(String(err));
      finish();
    }
  };
  es.onerror = () => {
    // Suppress error after a clean done — EventSource fires onerror when
    // the server closes the connection, even on a successful stream end.
    if (finished) return;
    h.onError("Connection error");
    finish();
  };
  return finish;
}
