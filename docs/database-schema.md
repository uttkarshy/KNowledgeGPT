# Database Schema

Generated from the real SQLAlchemy models (`app/models/`) — if this ever drifts from the actual schema, trust the models and the Alembic migration history over this file.


## `api_usage_logs`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `user_id` | `UUID` | no | FK → `users.id`, indexed |
| `endpoint` | `VARCHAR(255)` | no | indexed |
| `model` | `VARCHAR(128)` | yes |  |
| `input_tokens` | `INTEGER` | no |  |
| `output_tokens` | `INTEGER` | no |  |
| `latency_ms` | `INTEGER` | yes |  |
| `estimated_cost_usd` | `FLOAT` | yes |  |
| `status_code` | `INTEGER` | no |  |
| `error_message` | `VARCHAR(1024)` | yes |  |
| `id` | `UUID` | no | PK |
| `created_at` | `DATETIME` | no |  |
| `updated_at` | `DATETIME` | no |  |

## `audit_logs`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `user_id` | `UUID` | yes | FK → `users.id`, indexed |
| `action` | `VARCHAR(21)` | no | indexed |
| `resource_type` | `VARCHAR(64)` | yes |  |
| `resource_id` | `VARCHAR(255)` | yes |  |
| `ip_address` | `INET` | yes |  |
| `user_agent` | `VARCHAR(500)` | yes |  |
| `metadata_json` | `JSONB` | yes |  |
| `id` | `UUID` | no | PK |
| `created_at` | `DATETIME` | no |  |
| `updated_at` | `DATETIME` | no |  |

## `chat_citations`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `message_id` | `UUID` | no | FK → `chat_messages.id`, indexed |
| `document_id` | `UUID` | no | FK → `documents.id` |
| `chunk_id` | `UUID` | no | FK → `document_chunks.id` |
| `document_name` | `VARCHAR(512)` | no |  |
| `page_number` | `INTEGER` | yes |  |
| `section` | `VARCHAR(512)` | yes |  |
| `similarity_score` | `FLOAT` | no |  |
| `excerpt` | `TEXT` | no |  |
| `id` | `UUID` | no | PK |
| `created_at` | `DATETIME` | no |  |
| `updated_at` | `DATETIME` | no |  |

## `chat_messages`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `session_id` | `UUID` | no | FK → `chat_sessions.id`, indexed |
| `parent_message_id` | `UUID` | yes | FK → `chat_messages.id` |
| `role` | `VARCHAR(9)` | no |  |
| `content` | `TEXT` | no |  |
| `model_used` | `VARCHAR(128)` | yes |  |
| `input_tokens` | `INTEGER` | yes |  |
| `output_tokens` | `INTEGER` | yes |  |
| `latency_ms` | `INTEGER` | yes |  |
| `confidence_score` | `FLOAT` | yes |  |
| `is_active_branch` | `BOOLEAN` | no |  |
| `id` | `UUID` | no | PK |
| `created_at` | `DATETIME` | no |  |
| `updated_at` | `DATETIME` | no |  |

## `chat_sessions`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `owner_id` | `UUID` | no | FK → `users.id`, indexed |
| `knowledge_base_id` | `UUID` | no | FK → `knowledge_bases.id`, indexed |
| `title` | `VARCHAR(512)` | no |  |
| `is_pinned` | `BOOLEAN` | no |  |
| `is_archived` | `BOOLEAN` | no |  |
| `is_bookmarked` | `BOOLEAN` | no |  |
| `share_token` | `VARCHAR(64)` | yes | unique |
| `id` | `UUID` | no | PK |
| `created_at` | `DATETIME` | no |  |
| `updated_at` | `DATETIME` | no |  |

## `document_chunks`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `document_id` | `UUID` | no | FK → `documents.id`, indexed |
| `knowledge_base_id` | `UUID` | no | FK → `knowledge_bases.id`, indexed |
| `owner_id` | `UUID` | no | FK → `users.id`, indexed |
| `chunk_index` | `INTEGER` | no |  |
| `page_number` | `INTEGER` | yes |  |
| `section` | `VARCHAR(512)` | yes |  |
| `content` | `TEXT` | no |  |
| `token_count` | `INTEGER` | no |  |
| `embedding` | `VECTOR(3072)` | no |  |
| `embedding_model` | `VARCHAR(128)` | no |  |
| `checksum` | `VARCHAR(64)` | no |  |
| `id` | `UUID` | no | PK |
| `created_at` | `DATETIME` | no |  |
| `updated_at` | `DATETIME` | no |  |

## `documents`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `knowledge_base_id` | `UUID` | no | FK → `knowledge_bases.id`, indexed |
| `owner_id` | `UUID` | no | FK → `users.id`, indexed |
| `name` | `VARCHAR(512)` | no |  |
| `file_type` | `VARCHAR(8)` | no |  |
| `language` | `VARCHAR(16)` | yes |  |
| `status` | `VARCHAR(14)` | no | indexed |
| `status_detail` | `TEXT` | yes |  |
| `processing_progress_pct` | `INTEGER` | no |  |
| `checksum` | `VARCHAR(64)` | no | indexed |
| `version` | `INTEGER` | no |  |
| `original_size_bytes` | `BIGINT` | no |  |
| `page_count` | `INTEGER` | yes |  |
| `chunk_count` | `INTEGER` | no |  |
| `embedding_model` | `VARCHAR(128)` | yes |  |
| `temp_storage_key` | `VARCHAR(1024)` | yes |  |
| `extra_metadata` | `JSONB` | yes |  |
| `id` | `UUID` | no | PK |
| `created_at` | `DATETIME` | no |  |
| `updated_at` | `DATETIME` | no |  |

## `knowledge_bases`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `owner_id` | `UUID` | no | FK → `users.id`, indexed |
| `parent_folder_id` | `UUID` | yes | FK → `knowledge_bases.id` |
| `name` | `VARCHAR(255)` | no |  |
| `description` | `TEXT` | yes |  |
| `color` | `VARCHAR(32)` | yes |  |
| `icon` | `VARCHAR(64)` | yes |  |
| `tags` | `ARRAY` | yes |  |
| `is_archived` | `BOOLEAN` | no |  |
| `is_folder` | `BOOLEAN` | no |  |
| `document_count` | `INTEGER` | no |  |
| `total_chunk_count` | `INTEGER` | no |  |
| `storage_bytes_used` | `INTEGER` | no |  |
| `id` | `UUID` | no | PK |
| `created_at` | `DATETIME` | no |  |
| `updated_at` | `DATETIME` | no |  |

## `refresh_tokens`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `user_id` | `UUID` | no | FK → `users.id`, indexed |
| `token_hash` | `VARCHAR(255)` | no | unique |
| `expires_at` | `DATETIME` | no |  |
| `revoked` | `BOOLEAN` | no |  |
| `replaced_by_token_hash` | `VARCHAR(255)` | yes |  |
| `user_agent` | `VARCHAR(500)` | yes |  |
| `ip_address` | `VARCHAR(64)` | yes |  |
| `id` | `UUID` | no | PK |
| `created_at` | `DATETIME` | no |  |
| `updated_at` | `DATETIME` | no |  |

## `users`

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `email` | `VARCHAR(320)` | no | unique, indexed |
| `hashed_password` | `VARCHAR(255)` | yes |  |
| `full_name` | `VARCHAR(255)` | yes |  |
| `role` | `VARCHAR(5)` | no |  |
| `auth_provider` | `VARCHAR(8)` | no |  |
| `google_id` | `VARCHAR(255)` | yes | unique |
| `is_active` | `BOOLEAN` | no |  |
| `is_verified` | `BOOLEAN` | no |  |
| `is_suspended` | `BOOLEAN` | no |  |
| `email_verification_token` | `VARCHAR(255)` | yes |  |
| `password_reset_token` | `VARCHAR(255)` | yes |  |
| `password_reset_expires_at` | `DATETIME` | yes |  |
| `last_login_at` | `DATETIME` | yes |  |
| `id` | `UUID` | no | PK |
| `created_at` | `DATETIME` | no |  |
| `updated_at` | `DATETIME` | no |  |
