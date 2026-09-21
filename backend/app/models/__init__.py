"""
Import every model here so:
  1. `Base.metadata` has the full schema (required for Alembic autogenerate).
  2. Application code can `from app.models import User, Document, ...`.
"""

from app.models.billing import CreditPurchase
from app.models.chat import ChatCitation, ChatMessage, ChatSession
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.knowledge_base import KnowledgeBase
from app.models.usage import ApiUsageLog, AuditLog
from app.models.user import RefreshToken, User

__all__ = [
    "User",
    "RefreshToken",
    "KnowledgeBase",
    "Document",
    "DocumentChunk",
    "ChatSession",
    "ChatMessage",
    "ChatCitation",
    "ApiUsageLog",
    "AuditLog",
    "CreditPurchase",
]
