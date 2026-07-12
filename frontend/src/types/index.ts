export interface Session {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  document_count: number;
  message_count: number;
}

export interface SessionListResponse {
  sessions: Session[];
  total: number;
}

export interface Document {
  id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  num_chunks: number;
  status: "processing" | "ready" | "error";
  uploaded_at: string;
  error_message?: string | null;
}

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  status: string;
  num_chunks: number;
  num_pages?: number | null;
  has_images: boolean;
  message: string;
}

export interface DocumentStatusResponse {
  document_id: string;
  status: string;
  num_chunks: number;
  error_message?: string | null;
}

export interface Citation {
  chunk_id: string;
  document_id: string;
  filename: string;
  page_num?: number | null;
  chunk_text: string;
  relevance_score: number;
  has_image: boolean;
  image_path?: string | null;
}

export interface TraceStage {
  seq: number;
  stage: string;
  latency_ms: number;
  payload: {
    count?: number;
    top?: { chunk_id: string; score: number }[];
    query?: string;
    queries?: string[];
    kind?: string;
    provider?: string;
    model?: string;
    completion_tokens?: number;
    tokens_per_sec?: number;
    [k: string]: unknown;
  } | null;
}

export interface Trace {
  trace_id: string;
  message_id: string | null;
  session_id: string | null;
  query: string;
  total_ms: number;
  provider: string | null;
  model: string | null;
  tokens_per_sec: number | null;
  created_at: string;
  stages: TraceStage[];
}

export interface StreamMeta {
  provider: string;
  model: string;
  tokens_per_sec: number;
  completion_tokens: number;
  tokens_estimated: boolean;
  generation_time_ms: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[] | null;
  model_used?: string | null;
  meta?: StreamMeta | null;
  created_at: string;
}
