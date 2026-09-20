export interface KnowledgeBase {
  id: string;
  parent_folder_id: string | null;
  name: string;
  description: string | null;
  color: string | null;
  icon: string | null;
  tags: string[] | null;
  is_folder: boolean;
  document_count: number;
  total_chunk_count: number;
  storage_bytes_used: number;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface DocumentSummary {
  id: string;
  knowledge_base_id: string;
  name: string;
  file_type: string;
  status:
    | "pending"
    | "virus_scanning"
    | "extracting"
    | "ocr_processing"
    | "chunking"
    | "embedding"
    | "completed"
    | "failed";
  status_detail: string | null;
  error_code?: string | null;
  retryable?: boolean;
  next_retry_at?: string | null;
  processing_progress_pct: number;
  page_count: number | null;
  chunk_count: number;
  original_size_bytes: number;
  created_at: string;
}

export interface Citation {
  chunk_id: string;
  document_id: string;
  document_name: string;
  page_number: number | null;
  section: string | null;
  similarity_score: number;
  excerpt: string;
}

export interface ChatMessage {
  id: string;
  role: "system" | "user" | "assistant";
  content: string;
  model_used: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  latency_ms: number | null;
  confidence_score: number | null;
  citations: Citation[];
  created_at: string;
}

export interface ChatSession {
  id: string;
  knowledge_base_id: string;
  title: string;
  is_pinned: boolean;
  is_archived: boolean;
  is_bookmarked: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserPublic {
  id: string;
  email: string;
  full_name: string | null;
  role: "admin" | "user" | "ai";
  is_verified: boolean;
}

export interface AdminUser {
  id: string;
  email: string;
  full_name: string | null;
  role: "admin" | "user" | "ai";
  is_active: boolean;
  is_verified: boolean;
  is_suspended: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface AnalyticsSummary {
  total_users: number;
  total_knowledge_bases: number;
  total_documents: number;
  total_chunks: number;
  total_chat_sessions: number;
  total_storage_bytes: number;
  api_calls_last_24h: number;
  api_errors_last_24h: number;
  documents_by_status: Record<string, number>;
  recent_signups_7d: number;
  questions_7d: number;
  embedding_429_count: number;
  recent_processing_errors: Record<string, number>;
}

export interface ApiUsageLogEntry {
  id: string;
  user_id: string;
  endpoint: string;
  model: string | null;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number | null;
  status_code: number;
  created_at: string;
}
