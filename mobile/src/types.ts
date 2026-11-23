export interface Profile {id: string; email: string; full_name?: string; is_verified: boolean; credit_balance?: number}
export interface Base {id: string; name: string; description?: string; is_folder: boolean; document_count: number}
export interface Doc {id: string; knowledge_base_id: string; name: string; status: string; original_size_bytes: number; processing_progress_pct: number; chunk_count: number; page_count?: number; estimated_credits?: number | null; retryable?: boolean; status_detail?: string}
export interface Conversation {id: string; title: string; knowledge_base_id: string}
export interface Citation {document_id: string; document_name: string; page_number?: number; section?: string; excerpt: string}
export interface Message {id: string; role: 'user' | 'assistant' | 'system'; content: string; citations: Citation[]}
export interface Limits {max_size_bytes: number; allowed_extensions: string[]}
