"""Deliver support requests to the configured operator without logging private content."""
import uuid
from email.message import EmailMessage
from typing import Literal

import aiosmtplib
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.enums import MessageRole
from app.models.user import User

router = APIRouter(prefix="/api/support", tags=["support"])


class HelpRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1500)


class AnswerReport(HelpRequest):
    message_id: uuid.UUID


class DeletionRequest(BaseModel):
    email: EmailStr
    confirmation: Literal["DELETE"]


async def deliver(settings: Settings, kind: str, body: str):
    if not settings.SUPPORT_INBOX or not settings.SMTP_HOST:
        raise HTTPException(503, "Support delivery is unavailable. Please try again later.")
    receipt = str(uuid.uuid4())
    message = EmailMessage()
    message["From"] = settings.EMAIL_FROM
    message["To"] = settings.SUPPORT_INBOX
    message["Subject"] = f"KnowledgeGPT {kind} [{receipt}]"
    message.set_content(body)
    try:
        refused, _ = await aiosmtplib.send(
            message, hostname=settings.SMTP_HOST, port=settings.SMTP_PORT,
            username=settings.SMTP_USER, password=settings.SMTP_PASSWORD,
            start_tls=settings.SMTP_USE_TLS, timeout=12,
        )
        if refused:
            raise aiosmtplib.SMTPException("Recipient unavailable")
    except (aiosmtplib.SMTPException, OSError, TimeoutError):
        raise HTTPException(503, "Support delivery is unavailable. Please try again later.") from None
    return {"reference": receipt}


@router.post("/contact", status_code=202, dependencies=[Depends(rate_limit(key_prefix="support", max_requests=3))])
async def contact(body: HelpRequest, user: User = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    return await deliver(settings, "support", f"Account: {user.id}\nReply to: {user.email}\n\n{body.reason}")


@router.post("/report-answer", status_code=202, dependencies=[Depends(rate_limit(key_prefix="report", max_requests=5))])
async def report_answer(body: AnswerReport, user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    message = await db.scalar(select(ChatMessage.id).join(ChatSession).where(
        ChatMessage.id == body.message_id, ChatSession.owner_id == user.id,
        ChatMessage.role == MessageRole.ASSISTANT,
    ))
    if message is None:
        raise HTTPException(404, "Answer unavailable")
    return await deliver(settings, "answer report", f"Account: {user.id}\nAnswer: {message}\nReason: {body.reason}")


@router.post("/deletion-request", status_code=202, dependencies=[Depends(rate_limit(key_prefix="erase", max_requests=3))])
async def request_deletion(body: DeletionRequest, settings: Settings = Depends(get_settings)):
    # No lookup or automatic erasure. The operator verifies mailbox control before fulfillment.
    return await deliver(settings, "deletion request",
                         f"Verify control of {body.email} before deleting any data. Follow docs/mobile/operator.md.")
