# API Reference

Auto-generated from the live OpenAPI schema (`docs/openapi.json`) — this file is a formatted index of the same source of truth FastAPI serves at `/docs` (Swagger UI) and `/openapi.json` on the running API. If this ever looks stale, trust the running server's `/docs`, not this file.


## Authentication

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Register |
| `POST` | `/api/auth/login` | Login |
| `POST` | `/api/auth/refresh` | Refresh |
| `POST` | `/api/auth/logout` | Logout |
| `GET` | `/api/auth/me` | Me |
| `POST` | `/api/auth/verify-email` | Verify Email |
| `POST` | `/api/auth/forgot-password` | Forgot Password |
| `POST` | `/api/auth/reset-password` | Reset Password |
| `GET` | `/api/auth/google/login` | Google Login |
| `POST` | `/api/auth/google/callback` | Google Callback |

## Knowledge Bases

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/knowledge-bases` | Create Knowledge Base |
| `GET` | `/api/knowledge-bases` | List Knowledge Bases |
| `GET` | `/api/knowledge-bases/{kb_id}` | Get Knowledge Base |
| `PATCH` | `/api/knowledge-bases/{kb_id}` | Update Knowledge Base |
| `DELETE` | `/api/knowledge-bases/{kb_id}` | Delete Knowledge Base |
| `POST` | `/api/knowledge-bases/{kb_id}/archive` | Archive Knowledge Base |
| `POST` | `/api/knowledge-bases/{kb_id}/duplicate` | Duplicate Knowledge Base |
| `GET` | `/api/knowledge-bases/{kb_id}/stats` | Get Knowledge Base Stats |

## Documents

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/documents/upload-url` | Create Upload Url |
| `POST` | `/api/documents/confirm` | Confirm Upload |
| `GET` | `/api/documents/{document_id}/status` | Get Document Status |
| `GET` | `/api/documents` | List Documents |
| `DELETE` | `/api/documents/{document_id}` | Delete Document |

## Chat

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/chat/sessions` | Create Session |
| `GET` | `/api/chat/sessions` | List Sessions |
| `GET` | `/api/chat/sessions/{session_id}/messages` | Get Messages |
| `POST` | `/api/chat/sessions/{session_id}/ask` | Ask Question |

## Admin

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/admin/users` | List Users |
| `GET` | `/api/admin/users/{user_id}` | Get User Detail |
| `DELETE` | `/api/admin/users/{user_id}` | Delete User |
| `POST` | `/api/admin/users/{user_id}/suspend` | Suspend User |
| `POST` | `/api/admin/users/{user_id}/unsuspend` | Unsuspend User |
| `GET` | `/api/admin/analytics` | Get Analytics |
| `GET` | `/api/admin/logs/api-usage` | Get Api Usage Logs |
| `GET` | `/api/admin/logs/errors` | Get Error Logs |
| `GET` | `/api/admin/logs/audit` | Get Audit Logs |

## System

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health Check |
| `GET` | `/health/deep` | Deep Health Check |
