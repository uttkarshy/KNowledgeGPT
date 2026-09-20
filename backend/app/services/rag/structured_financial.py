"""Deterministic, call-local schemas for stored financial table rows.

PDF table IDs restart on every page. A header must therefore be present on the
same page before propagation; a later header for the same document/table ID may
only reaffirm the mapping. No positional, balance or language-model inference.
"""

import re

from app.services.rag.exact_date import DateEvidenceLimit

_ALIASES = {
    "date": {"date", "transactiondate", "txndate", "valuedate"},
    "description": {"description", "narration", "particulars"},
    "reference": {"reference", "referenceno", "refno", "chqrefno", "chequereferenceno"},
    "debit": {"debit", "withdrawal", "withdrawals", "withdrawalamount", "debitamount", "withdrawaldr", "debitdr"},
    "credit": {"credit", "deposit", "deposits", "creditamount", "depositamount", "depositcr", "creditcr"},
    "balance": {"balance", "runningbalance"},
    "amount": {"amount"},
    "direction": {"type", "direction", "drcr"},
}
_SEMANTICS = {alias: field for field, aliases in _ALIASES.items() for alias in aliases}
_FINANCIAL = {"debit", "credit", "balance", "amount", "direction"}
_DATE_VALUE = re.compile(r"^(?:\d{1,2}[ /.-]+(?:[A-Za-z]{3,9}|\d{1,2})[ /.,-]+\d{2,4}|\d{4}-\d{1,2}-\d{1,2})\b")


def _semantic(value):
    return _SEMANTICS.get(re.sub(r"[^a-z]", "", str(value).lower()))


def _fail():
    raise DateEvidenceLimit(
        "Transaction table headers or cells are incomplete or ambiguous. No partial calculation was made."
    )


def _schema(labels, *, propagated=False):
    mapping = {physical: _semantic(label) for physical, label in labels.items()}
    fields = [field for field in mapping.values() if field]
    if len(fields) != len(set(fields)) or "date" not in fields:
        _fail()
    directional = {"debit", "credit"} & set(fields)
    explicit_amount = {"amount", "direction"} <= set(fields)
    if propagated and directional and directional != {"debit", "credit"}:
        _fail()
    if not directional and not explicit_amount:
        _fail()
    # Competing direction/amount layouts are never silently preferred.
    if directional and ({"amount", "direction"} & set(fields)):
        _fail()
    return mapping


class FinancialTableHeaders:
    def __init__(self):
        self.schemas = {}
        self.pages = set()
        self.seen = set()
        self.unsupported = set()

    def cells(self, chunk):
        structure = chunk.structure
        cells = structure.get("cells")
        if not isinstance(cells, dict) or not cells:
            _fail()
        table = (chunk.document_id, structure.get("table_id"))
        page = (*table, chunk.page_number)
        old = self.schemas.get(table)
        values = {_semantic(v) for v in cells.values()} - {None}
        keys = {_semantic(k) for k in cells} - {None}
        # Date plus another recognized field, or multiple financial labels,
        # identifies a candidate schema. Invalid candidates must refuse.
        header = len(values) >= 2 and ("date" in values or bool(values & _FINANCIAL))
        financial = bool(keys & ({"date"} | _FINANCIAL))
        dated = any(_DATE_VALUE.match(str(v).strip()) for v in cells.values())
        if not (header or financial or dated or old):
            self.unsupported.add(page)
            return None
        if structure.get("uncertain_structure"):
            _fail()
        if chunk.document_id is None or structure.get("table_id") is None or structure.get("row_index") is None:
            _fail()
        identity = (*page, structure["row_index"])
        if identity in self.seen:
            raise DateEvidenceLimit("Duplicate row provenance prevents a reliable calculation.")
        self.seen.add(identity)

        if header:
            if page in self.unsupported:
                _fail()
            mapping = _schema(cells, propagated=True)
            self._confidence(structure, mapping)
            if old is not None and old != mapping:
                _fail()
            self.schemas[table] = mapping
            self.pages.add(page)
            return None  # A header is evidence of schema, never a transaction.
        direct = _schema({key: key for key in cells}) if financial else None
        if direct is not None:
            if old is not None and old != direct:
                _fail()
            self.schemas[table] = old = direct
            self.pages.add(page)
        if old is not None:
            if page not in self.pages or set(cells) != set(old):
                _fail()
            mapping = old
        else:
            _fail()  # A dated generic row cannot be silently dropped.
        self._confidence(structure, mapping)
        # Keep empty strings exactly: blank debit and populated credit is credit.
        return {field: cells[physical] for physical, field in mapping.items() if field}

    @staticmethod
    def _confidence(structure, mapping):
        confidence = structure.get("confidence")
        if confidence is None:
            return  # Native extraction has no OCR scores.
        if not isinstance(confidence, list) or len(confidence) != len(mapping):
            _fail()
        # JSONB may reorder cell keys independently of the positional OCR
        # scores. Require every score to be reliable; never guess the pairing.
        if any(not isinstance(score, (int, float)) or not 70 <= score <= 100 for score in confidence):
            _fail()
