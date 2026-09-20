"""Authorized, bounded PostgreSQL evidence and conservative transaction arithmetic."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.enums import DocumentStatus
from app.services.rag.exact_date import MAX_SCAN_CHARS, MAX_SCAN_CHUNKS, DateEvidenceLimit, explicit_date
from app.services.rag.retrieval import RetrievalFilters, RetrievedChunk


def scope(owner_id, kb_id, filters):
    conditions = [
        Document.owner_id == owner_id,
        DocumentChunk.owner_id == owner_id,
        Document.knowledge_base_id == kb_id,
        DocumentChunk.knowledge_base_id == kb_id,
        Document.status == DocumentStatus.COMPLETED,
    ]
    if filters:
        if filters.document_ids is not None:
            conditions.append(Document.id.in_(filters.document_ids))
        for value, column, operator in [
            (filters.language, Document.language, "eq"),
            (filters.uploaded_after, Document.created_at, "ge"),
            (filters.uploaded_before, Document.created_at, "le"),
        ]:
            if value is not None:
                conditions.append(getattr(column, "__" + operator + "__")(value))
    return conditions


async def narrow(db, *, owner_id, kb_id, filters, filename):
    if not filename:
        return filters
    ids = list(
        (
            await db.scalars(
                select(Document.id).where(
                    Document.owner_id == owner_id,
                    Document.knowledge_base_id == kb_id,
                    func.lower(Document.name) == filename.lower(),
                )
            )
        ).all()
    )
    if filters and filters.document_ids is not None:
        ids = [i for i in ids if i in filters.document_ids]
    return replace(filters, document_ids=ids) if filters else RetrievalFilters(document_ids=ids)


async def evidence(db, *, owner_id, kb_id, filters=None, lexical=None):
    query = select(DocumentChunk).join(Document).where(*scope(owner_id, kb_id, filters))
    if lexical is not None:
        terms = " ".join('"' + t + '"' for t in re.findall(r'"([^"\n]{3,80})"', lexical))
        vector = func.to_tsvector("simple", DocumentChunk.content)
        match = func.websearch_to_tsquery("simple", terms or lexical)
        query = query.where(vector.op("@@")(match))
    count, chars = (
        await db.execute(
            query.with_only_columns(
                func.count(DocumentChunk.id), func.coalesce(func.sum(func.length(DocumentChunk.content)), 0)
            )
        )
    ).one()
    if count > MAX_SCAN_CHUNKS or chars > MAX_SCAN_CHARS:
        raise DateEvidenceLimit(
            "The selected evidence exceeds the safe analysis limit. Select fewer documents; no partial calculation was made."
        )
    rows = (
        await db.execute(
            query.with_only_columns(DocumentChunk, Document.name)
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
            .limit(MAX_SCAN_CHUNKS + 1)
        )
    ).all()
    if len(rows) > MAX_SCAN_CHUNKS or sum(len(c.content) for c, _ in rows) > MAX_SCAN_CHARS:
        raise DateEvidenceLimit("The evidence changed or exceeds the safe limit. Narrow the selection.")
    return [RetrievedChunk(c.id, c.document_id, name, c.content, c.page_number, c.section, 1.0) for c, name in rows]


def _date(value):
    match = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2}|\d{4})", value.strip())
    if match:
        d, m, y = map(int, match.groups())
        return date(y + 2000 if y < 100 else y, m, d)
    value = re.sub(r"(?<=[ /-])(\d{2})$", r"20\1", value.strip())
    result = explicit_date(value)
    if not result:
        raise ValueError("Missing date")
    return result


def _money(value):
    value = re.sub(r"₹|INR|Rs\.?|,", "", value, flags=re.I).strip()
    if value in ("", "-", "—"):
        return None
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", value):
        raise ValueError("Unreliable amount")
    return Decimal(value)


def _transaction(cells):
    cells = {re.sub("[^a-z]", "", k.lower()): str(v).strip() for k, v in cells.items()}

    def field(*keys):
        return next((cells[k] for k in keys if k in cells), "")

    day = _date(field("date", "transactiondate", "txndate", "valuedate"))
    debit = _money(field("debit", "withdrawal", "withdrawals", "withdrawalamount", "debitamount"))
    credit = _money(field("credit", "deposit", "deposits", "creditamount", "depositamount"))
    if debit and credit:
        raise ValueError("Ambiguous direction")
    if not debit and not credit:
        amount = _money(field("amount"))
        direction = field("type", "direction", "drcr").lower()
        if not amount or direction not in ("debit", "dr", "credit", "cr"):
            raise ValueError("Unknown direction")
        debit, credit = (amount, None) if direction in ("debit", "dr") else (None, amount)
    return (
        day,
        field("description", "narration", "particulars", "reference") or "Description unavailable",
        debit or credit,
        "debit" if debit else "credit",
    )


DATE_LINE = re.compile(r"^\s*(\d{1,2}[ /.-]+(?:[A-Za-z]{3,9}|\d{1,2})[ /.,-]+\d{2,4}|\d{4}-\d{1,2}-\d{1,2})\b")


def transactions(chunks):
    result, seen, headers = [], set(), {}
    for chunk in chunks:
        for line in chunk.content.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3 and any(re.fullmatch(r"(date|transaction date|txn date)", p, re.I) for p in parts):
                headers[chunk.document_id] = parts
                continue
            match = DATE_LINE.match(line)
            if not match:
                continue
            identity = (chunk.document_id, chunk.page_number, line.strip())
            if identity in seen:
                raise DateEvidenceLimit(
                    "Overlapping legacy rows cannot be counted reliably. Use a structured export or reprocess the document."
                )
            seen.add(identity)
            labelled = re.search(r"\b(Debit|Withdrawal|Credit|Deposit)\s*[:₹ ]\s*([\d,]+(?:\.\d{1,2})?)\b", line, re.I)
            header = headers.get(chunk.document_id)
            if labelled:
                cells = {
                    "Date": match.group(1),
                    "Description": line[match.end() : labelled.start()].strip(" |"),
                    labelled.group(1): labelled.group(2),
                }
            elif header and len(header) == len(parts):
                cells = dict(zip(header, parts, strict=True))
            else:
                raise DateEvidenceLimit(
                    "Transaction columns are incomplete or ambiguous. Upload a structured export; no partial total was calculated."
                )
            try:
                result.append((*_transaction(cells), chunk))
            except ValueError as exc:
                raise DateEvidenceLimit(
                    "A transaction date, amount or direction is unreliable. No partial calculation was made."
                ) from exc
    return result


def calculate(chunks, plan, question):
    direction = "credit" if re.search(r"\b(credits?|deposits?|income)\b", question, re.I) else "debit"
    rows = [
        r
        for r in transactions(chunks)
        if r[3] == direction and (not plan.periods or any(a <= r[0] <= b for a, b in plan.periods))
    ]
    if not rows:
        raise DateEvidenceLimit(
            "No complete transaction rows match this request. Select the statement or upload a structured export."
        )
    output = (
        sorted(rows, key=lambda r: (r[2], r[0]), reverse=plan.operation == "top")[: plan.count]
        if plan.operation in ("top", "bottom")
        else rows
    )
    sources = list({r[4].chunk_id: r[4] for r in output}.values())
    if len(sources) > 32 or (plan.operation == "all" and len(output) > 50):
        raise DateEvidenceLimit(
            "The complete answer exceeds the citation/output limit. Narrow the period or document selection."
        )
    indices = {c.chunk_id: i + 1 for i, c in enumerate(sources)}
    refs = " ".join(f"[{i + 1}]" for i in range(len(sources)))
    if plan.operation in ("top", "bottom", "all"):
        text = f"Analyzed {len(rows)} complete {direction} rows.\n\n| Date | Description | Amount | Source |\n|---|---|---:|---|\n"
        for day, description, amount, _, source in output:
            description = re.sub(r"[\n\r|`<>\[\]]", " ", description)
            text += f"| {day.isoformat()} | {description} | ₹{amount:,.2f} | [{indices[source.chunk_id]}] |\n"
    elif plan.operation == "count":
        text = f"Count: **{len(rows)} {direction} transactions**. {refs}"
    elif plan.operation == "compare":
        groups = {}
        for day, _, amount, _, _ in rows:
            key = day.strftime("%Y-%m")
            groups[key] = groups.get(key, Decimal(0)) + amount
        text = "Monthly totals:\n" + "\n".join(f"- {k}: ₹{v:,.2f}" for k, v in sorted(groups.items())) + "\n" + refs
    else:
        total = sum((r[2] for r in rows), Decimal(0))
        value = total / len(rows) if plan.operation == "average" else total
        text = f"{'Average' if plan.operation == 'average' else 'Total'}: **₹{value:,.2f}** across {len(rows)} {direction} transactions. {refs}"
    return text, sources
