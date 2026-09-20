"""Bounded, exhaustive date evidence; never silently compress matching rows."""
from __future__ import annotations

import re
import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.chunking.token_estimate import estimate_tokens
from app.services.rag.retrieval import RetrievalFilters, RetrievedChunk

MAX_SCAN_CHUNKS = 2000
MAX_SCAN_CHARS = 2_000_000
MAX_CONTEXT_TOKENS = 6000
LIMIT_MESSAGE = "I cannot safely include all evidence for that date. Please select a smaller document set or upload the relevant statement pages before asking for a total."


class DateEvidenceLimit(ValueError):
    pass


_MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
_NAMED = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_SEP = r"[\s/.,-]+"
_DAY_FIRST = re.compile(r"(?<!\w)(\d{1,2})(?:st|nd|rd|th)?" + _SEP + _NAMED + _SEP + r"(\d{4})(?!\d)", re.I)
_MONTH_FIRST = re.compile(r"(?<!\w)" + _NAMED + _SEP + r"(\d{1,2})(?:st|nd|rd|th)?" + _SEP + r"(\d{4})(?!\d)", re.I)
_ISO = re.compile(r"(?<!\d)(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?!\d)")
_NUMERIC = re.compile(r"(?<![\d/-])(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?!\d)")


def explicit_date(question: str) -> date | None:
    found = set()
    try:
        for day, month, year in _DAY_FIRST.findall(question):
            found.add(date(int(year), _MONTHS.index(month[:3].lower()) + 1, int(day)))
        for month, day, year in _MONTH_FIRST.findall(question):
            found.add(date(int(year), _MONTHS.index(month[:3].lower()) + 1, int(day)))
        for year, month, day in _ISO.findall(question):
            found.add(date(int(year), int(month), int(day)))
        for first, second, year in _NUMERIC.findall(question):
            a, b = int(first), int(second)
            if a <= 12 and b <= 12 and a != b:
                raise DateEvidenceLimit("Please spell out the month or use YYYY-MM-DD so the date is unambiguous.")
            found.add(date(int(year), b if a > 12 else a, a if a > 12 else b))
    except ValueError as exc:
        if isinstance(exc, DateEvidenceLimit):
            raise
        raise DateEvidenceLimit("Please provide a valid date with a four-digit year.") from exc
    if len(found) > 1:
        raise DateEvidenceLimit("Please ask about one exact date at a time and select the relevant documents.")
    if not found and (
        re.search(r"(?<!\w)\d{1,2}(?:st|nd|rd|th)?" + _SEP + _NAMED, question, re.I)
        or re.search(_NAMED + _SEP + r"\d{1,2}(?!\d)", question, re.I)
        or re.search(r"\b(?:on|date)\s+\d{1,2}[/-]\d{1,2}\b", question, re.I)
    ):
        raise DateEvidenceLimit("Please specify the exact date with a four-digit year and spell out the month.")
    return next(iter(found), None)


def date_pattern(target: date) -> re.Pattern:
    month = _NAMED[1:-1].split("|")[target.month - 1]
    day = f"0?{target.day}" if target.day < 10 else str(target.day)
    number = f"0?{target.month}" if target.month < 10 else str(target.month)
    year = f"(?:{target.year}|{target.year % 100:02})"
    alternatives = [
        day + _SEP + month + _SEP + year,
        month + _SEP + day + _SEP + year,
        day + _SEP + number + _SEP + year,
        number + _SEP + day + _SEP + year,
        str(target.year) + _SEP + number + _SEP + day,
    ]
    return re.compile(r"(?<!\w)(?:" + "|".join(alternatives) + r")(?!\w)", re.I)


async def exact_date_evidence(
    db: AsyncSession, *, target: date, owner_id: uuid.UUID,
    knowledge_base_id: uuid.UUID, filters: RetrievalFilters | None = None,
) -> list[RetrievedChunk]:
    # No embedding-model filter: text evidence must not disappear merely
    # because its vector missed top-K (or was embedded by an older model).
    conditions = [DocumentChunk.owner_id == owner_id, Document.owner_id == owner_id,
                  DocumentChunk.knowledge_base_id == knowledge_base_id,
                  Document.knowledge_base_id == knowledge_base_id,
                  Document.status == DocumentStatus.COMPLETED]
    if filters:
        if filters.document_ids is not None:
            conditions.append(DocumentChunk.document_id.in_(filters.document_ids))
        if filters.language:
            conditions.append(Document.language == filters.language)
        if filters.uploaded_after:
            conditions.append(Document.created_at >= filters.uploaded_after)
        if filters.uploaded_before:
            conditions.append(Document.created_at <= filters.uploaded_before)
    scope = select(DocumentChunk.id).join(Document, Document.id == DocumentChunk.document_id).where(*conditions)
    count, chars = (await db.execute(scope.with_only_columns(
        func.count(DocumentChunk.id), func.coalesce(func.sum(func.length(DocumentChunk.content)), 0)
    ))).one()
    if count > MAX_SCAN_CHUNKS or chars > MAX_SCAN_CHARS:
        raise DateEvidenceLimit(LIMIT_MESSAGE)
    # LIMIT + substring also bound memory if documents change between queries.
    rows = (await db.execute(scope.with_only_columns(
        DocumentChunk.id, DocumentChunk.document_id, DocumentChunk.chunk_index,
        func.substr(DocumentChunk.content, 1, MAX_SCAN_CHARS + 1).label("content"),
        DocumentChunk.page_number, DocumentChunk.section, DocumentChunk.structure, Document.name.label("document_name")
    ).order_by(DocumentChunk.document_id, DocumentChunk.chunk_index).limit(MAX_SCAN_CHUNKS + 1))).all()
    if len(rows) > MAX_SCAN_CHUNKS or sum(len(r.content) for r in rows) > MAX_SCAN_CHARS:
        raise DateEvidenceLimit(LIMIT_MESSAGE)
    pattern = date_pattern(target)
    matched = {(r.document_id, r.chunk_index) for r in rows if pattern.search(r.content)}
    selected = [r for r in rows if any((r.document_id, r.chunk_index + offset) in matched for offset in (-1, 0, 1))]
    evidence = [RetrievedChunk(r.id, r.document_id, r.document_name, r.content, r.page_number, r.section, 1.0, structure=getattr(r, "structure", None)) for r in selected]
    if context_cost(evidence) > MAX_CONTEXT_TOKENS:
        raise DateEvidenceLimit(LIMIT_MESSAGE)
    return evidence


def context_cost(chunks: list[RetrievedChunk]) -> int:
    return sum(estimate_tokens(c.content + c.document_name + (c.section or "")) + 40 for c in chunks)


def augment_date_context(evidence: list[RetrievedChunk], semantic: list[RetrievedChunk]) -> list[RetrievedChunk]:
    # Identity dedupe only: identical-looking rows on different pages can be
    # separate transactions. Never apply content deduplication to date evidence.
    result = list(evidence)
    seen = {c.chunk_id for c in result}
    for chunk in semantic:
        if chunk.chunk_id not in seen and context_cost(result + [chunk]) <= MAX_CONTEXT_TOKENS:
            result.append(chunk)
            seen.add(chunk.chunk_id)
    return result
