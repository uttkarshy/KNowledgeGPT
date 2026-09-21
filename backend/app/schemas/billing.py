from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class CreditSummary(BaseModel):
    balance: int
    plan_code: str
    starter_allowance: int
    chat_credits: int
    document_credits_per_page: int
    payments_enabled: bool


class CreditUsagePublic(BaseModel):
    id: uuid.UUID
    operation: str | None
    credits_delta: int
    input_tokens: int
    output_tokens: int
    model: str | None
    created_at: datetime
    usage_metadata: dict | None = None

    model_config = {"from_attributes": True}
