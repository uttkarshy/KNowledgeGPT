"""Enum types shared across ORM models and Pydantic schemas."""

from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"
    AI = "ai"  # service-account role for internal/automated agents


class AuthProvider(str, enum.Enum):
    PASSWORD = "password"
    GOOGLE = "google"


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    VIRUS_SCANNING = "virus_scanning"
    EXTRACTING = "extracting"
    OCR_PROCESSING = "ocr_processing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    COMPLETED = "completed"
    FAILED = "failed"


class FileType(str, enum.Enum):
    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    TXT = "txt"
    CSV = "csv"
    XLSX = "xlsx"
    XLS = "xls"
    PPTX = "pptx"
    MARKDOWN = "markdown"
    HTML = "html"
    XML = "xml"
    JSON = "json"
    RTF = "rtf"
    IMAGE = "image"
    ZIP = "zip"


class MessageRole(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class AuditAction(str, enum.Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    UPLOAD_DOCUMENT = "upload_document"
    DELETE_DOCUMENT = "delete_document"
    CREATE_KNOWLEDGE_BASE = "create_knowledge_base"
    DELETE_KNOWLEDGE_BASE = "delete_knowledge_base"
    CHAT_MESSAGE = "chat_message"
    SUSPEND_USER = "suspend_user"
    DELETE_USER = "delete_user"
    UPDATE_SETTINGS = "update_settings"
