"""Fail-closed reader for native PDF cells serialized vertically before V2.

Only a complete numbered, chronological ledger with a recognized schema is
accepted. Empty PDF cells are often omitted: a two-money-cell row therefore
needs an independently established preceding balance. No language-model or
description-based direction inference is used. Unresolved overlap is refused.
"""

from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal

from app.services.rag.exact_date import DateEvidenceLimit, explicit_date

_ALIASES = (
    {"#", "no", "srno", "sno"},
    {"date", "transactiondate", "txndate"},
    {"description", "narration", "particulars"},
    {"reference", "referenceno", "refno", "chqrefno", "chequereferenceno"},
    {"debit", "withdrawal", "withdrawals", "withdrawaldr", "debitdr"},
    {"credit", "deposit", "deposits", "depositcr", "creditcr"},
    {"balance", "runningbalance"},
)
_DATE = re.compile(r"(?:\d{1,2}[ /.-]+(?:[A-Za-z]{3,9}|\d{1,2})[ /.,-]+\d{4}|\d{4}-\d{2}-\d{2})$")
_DATE_START = re.compile(_DATE.pattern.removesuffix("$") + r"(?=\s|$)")
_MONEY = re.compile(r"(?:₹\s*|INR\s*|Rs\.?\s*)?(?:\d+|\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3})\.\d{2}$", re.I)
_REFERENCE = re.compile(r"(?=[A-Za-z0-9/-]*[A-Za-z])(?=[A-Za-z0-9/-]*\d)[A-Za-z0-9/-]+$")


def _fail():
    raise DateEvidenceLimit(
        "Legacy transaction cells, sequence or balances are incomplete or ambiguous. "
        "No partial calculation was made; select a complete structured statement."
    )


def _key(value):
    return re.sub(r"[^a-z#]", "", value.lower())


def _header(lines, pos):
    values = [_key(line) for line, _ in lines[pos : pos + 7]]
    if len(values) != 7 or not all(values[i] in _ALIASES[i] for i in (0, 1, 2, 3, 6)):
        return None
    if values[4] in _ALIASES[4] and values[5] in _ALIASES[5]:
        return ("debit", "credit")
    if values[4] in _ALIASES[5] and values[5] in _ALIASES[4]:
        return ("credit", "debit")
    return None


def _money(value):
    if value in ("-", "—"):
        return None
    if not _MONEY.fullmatch(value):
        _fail()
    return Decimal(re.sub(r"₹|INR|Rs\.?|,|\s", "", value, flags=re.I))


def _sources(lines):
    return list({chunk.chunk_id: chunk for _, chunk in lines}.values())


def _lines(chunks):
    lines = []
    for chunk in chunks:
        if chunk.structure:
            continue
        incoming = [(line.strip(), chunk) for line in chunk.content.splitlines() if line.strip()]
        # The legacy chunker flattens its overlap tail into one line. Accept
        # only an exact suffix copied from the immediately preceding chunk,
        # containing a whole numbered row (date, text, reference and amounts).
        # Short/reformatted/partial-cell overlaps remain ambiguous and refuse.
        if lines and incoming:
            prefix = incoming[0][0]
            previous = lines[-1][1]
            normalized = " ".join(previous.content.split())
            numbered_row = re.search(
                r"(?:^| )\d+ \d{1,2} [A-Za-z]{3,9} \d{4} .+ \S+ \d[\d,]*\.\d{2} \d[\d,]*\.\d{2}$",
                prefix,
            )
            if (
                numbered_row
                and previous.chunk_index is not None
                and chunk.chunk_index == previous.chunk_index + 1
                and (normalized == prefix or normalized.endswith(" " + prefix))
            ):
                if len(incoming) == 1:
                    _fail()
                incoming = incoming[1:]
        lines.extend(incoming)
    return lines


def _read_document(chunks, lines, start, schema):
    # Evidence() loads all authorized chunks in index order. Do not join a
    # filtered, reordered or incomplete stream, or infer adjacency from pages.
    if len(chunks) > 1 and [c.chunk_index for c in chunks] != list(range(len(chunks))):
        _fail()
    if len(chunks) == 1 and chunks[0].chunk_index not in (None, 0):
        _fail()
    if len({c.chunk_id for c in chunks}) != len(chunks):
        _fail()
    if any(c.structure for c in chunks):
        # Mixed representations cannot safely be reconciled without row identity.
        _fail()
    if any(_DATE_START.match(line) for line, _ in lines[:start]):
        _fail()

    pos, expected, previous_day = start + 7, 1, None
    previous_balance, balance_sources = None, []
    schema_sources = _sources(lines[start : start + 7])
    result = []
    if pos < len(lines) and _key(lines[pos][0]) == "openingbalance":
        if pos + 1 >= len(lines):
            _fail()
        previous_balance = _money(lines[pos + 1][0])
        if previous_balance is None:
            _fail()
        balance_sources = _sources(lines[pos : pos + 2])
        pos += 2

    while pos < len(lines):
        repeated = _header(lines, pos)
        if repeated:
            if repeated != schema:
                _fail()
            pos += 7
            if pos == len(lines):
                _fail()
            continue
        if _key(lines[pos][0]) == "closingbalance":
            if pos + 2 != len(lines) or _money(lines[pos + 1][0]) != previous_balance:
                _fail()
            pos += 2
            break
        begin = pos
        if lines[pos][0] != str(expected) or pos + 1 >= len(lines) or not _DATE.fullmatch(lines[pos + 1][0]):
            _fail()
        day = explicit_date(lines[pos + 1][0])
        if day is None or (previous_day is not None and day < previous_day):
            _fail()
        pos += 2
        # A non-numeric description and reference are mandatory. Wrapped
        # descriptions are retained; the final text cell is the reference.
        text_cells = []
        while pos < len(lines) and not (_MONEY.fullmatch(lines[pos][0]) or lines[pos][0] in ("-", "—")):
            value = lines[pos][0]
            if not re.search(r"[A-Za-z]", value) or _DATE.fullmatch(value) or _header(lines, pos):
                _fail()
            text_cells.append(value)
            pos += 1
        if len(text_cells) < 2 or not _REFERENCE.fullmatch(text_cells[-1]):
            _fail()
        amounts = []
        while pos < len(lines) and (_MONEY.fullmatch(lines[pos][0]) or lines[pos][0] in ("-", "—")):
            amounts.append(_money(lines[pos][0]))
            pos += 1
        # Balance is the final schema column, and exact row width is enforced.
        # It is never eligible as a transaction amount.
        if len(amounts) not in (2, 3) or amounts[-1] is None:
            _fail()
        balance = amounts[-1]
        dependencies = []
        if len(amounts) == 3:
            active = [(kind, amount) for kind, amount in zip(schema, amounts[:2], strict=True) if amount]
            if len(active) != 1:
                _fail()
            direction, amount = active[0]
        else:
            amount = amounts[0]
            if not amount or previous_balance is None or abs(balance - previous_balance) != amount:
                _fail()
            direction = "credit" if balance > previous_balance else "debit"
            dependencies = balance_sources
        if previous_balance is not None and balance != previous_balance + (
            amount if direction == "credit" else -amount
        ):
            _fail()
        # Retain actual source chunks, including the preceding balance and
        # header needed to audit direction. Never fabricate a merged chunk ID.
        row_sources = _sources(lines[begin:pos])
        sources = list({c.chunk_id: c for c in row_sources + dependencies + schema_sources}.values())
        result.append((day, " ".join(text_cells[:-1]), amount, direction, *sources))
        previous_balance, previous_day = balance, day
        balance_sources = [lines[pos - 1][1]]
        expected += 1
    if not result:
        _fail()
    return result


def vertical_transactions(chunks):
    """Return rows and consumed chunk IDs; leave established formats untouched.

    Group only by document identity, never filename/page. OCR and structured
    chunks cannot supply a legacy schema or continuation. Blank lines are
    paragraph separators, NOT evidence of an empty debit/credit column.
    """
    documents = defaultdict(list)
    for chunk in chunks:
        documents[chunk.document_id].append(chunk)
    rows, consumed = [], set()
    for document_chunks in documents.values():
        lines = _lines(document_chunks)
        for pos in range(len(lines)):
            schema = _header(lines, pos)
            if schema:
                rows.extend(_read_document(document_chunks, lines, pos, schema))
                consumed.update(c.chunk_id for c in document_chunks)
                break
    return rows, consumed
