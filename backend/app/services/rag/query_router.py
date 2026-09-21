"""Deterministic routing; retain the existing exact-date and semantic paths."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date

from app.services.rag.exact_date import DateEvidenceLimit, explicit_date

MONTH = r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"


@dataclass(frozen=True)
class QueryPlan:
    strategy: str = "semantic"
    target: date | None = None
    periods: tuple[tuple[date, date], ...] = ()
    operation: str = "all"
    count: int = 3
    financial: bool = False
    names: tuple[str, ...] = ()
    filename: str | None = None


def route(question: str) -> QueryPlan:
    filename = re.search(r'\b(?:in|from)\s+["\']?([^?\n]+?\.(?:pdf|csv|xlsx|txt))["\']?(?:\s|[?.]|$)', question, re.I)
    filename = filename.group(1).strip() if filename else None
    if re.search(r"\b(ifsc|net payable|account (?:no\.?|number))\b", question, re.I):
        match = re.search(r"\bfor\s+(.+?)(?:\s+(?:in|from)\s+|[?.]|$)", question, re.I)
        names = tuple(n.strip(" ,\"'") for n in re.split(r"\s+and\s+|,", match.group(1), flags=re.I)) if match else ()
        if not names or len(names) > 5 or any(not 3 <= len(n) <= 80 for n in names):
            raise DateEvidenceLimit("Give up to five full names and select the document for a row lookup.")
        return QueryPlan(strategy="row", names=names, filename=filename)
    financial = bool(
        re.search(
            r"\b(expenses?|spent|spend|withdrawals?|debits?|payments?|transactions?|credits?|deposits?)\b",
            question,
            re.I,
        )
    )
    analytical = bool(
        re.search(
            r"\b(largest|highest|lowest|smallest|top\s+\d+|total|sum|count|average|compare|all|every|entire|whole|how many)\b",
            question,
            re.I,
        )
    )
    if re.search(r"\b(highest|top)\s+(?:educational\s+)?(qualification|degree|education)\b", question, re.I):
        analytical = False
    periods = []
    for month, year in re.findall(MONTH + r"\s+(20\d{2})\b", question, re.I):
        m = [v.lower() for v in calendar.month_abbr].index(month[:3].lower())
        periods.append((date(int(year), m, 1), date(int(year), m, calendar.monthrange(int(year), m)[1])))
    # Unambiguous explicit ranges only. Other multi-date phrases fail closed.
    range_match = re.search(
        r"\b(?:from|between)\s+(\d{4}-\d{2}-\d{2})\s+(?:to|and|through)\s+(\d{4}-\d{2}-\d{2})\b", question, re.I
    )
    if range_match:
        try:
            start, end = map(date.fromisoformat, range_match.groups())
            if start > end:
                raise ValueError()
        except ValueError as exc:
            raise DateEvidenceLimit("Please provide a valid chronological date range.") from exc
        periods = [(start, end)]
        analytical = True
        target = None
    else:
        target = explicit_date(question)
    if target:
        return QueryPlan(strategy="exact_date", target=target, filename=filename)
    if analytical or (financial and periods):
        if re.search(MONTH, question, re.I) and not periods:
            raise DateEvidenceLimit("Include a four-digit year with the month.")
        operation = "all"
        for pattern, value in [
            (r"largest|highest|\btop\b", "top"),
            (r"lowest|smallest", "bottom"),
            (r"average", "average"),
            (r"count|how many", "count"),
            (r"compare", "compare"),
            (r"total|sum|how much", "sum"),
        ]:
            if re.search(pattern, question, re.I):
                operation = value
                break
        match = re.search(r"\btop\s+(\d+)|\b(\d+)\s+(?:largest|highest|lowest|smallest)", question, re.I)
        count = int(next(g for g in match.groups() if g)) if match else 3
        if not 1 <= count <= 20:
            raise DateEvidenceLimit("Request between 1 and 20 ranked rows.")
        return QueryPlan(
            "analytical",
            periods=tuple(periods),
            operation=operation,
            count=count,
            financial=financial,
            filename=filename,
        )
    if re.search(r'"[^"\n]{3,80}"', question):
        return QueryPlan(strategy="lexical", filename=filename)
    return QueryPlan(filename=filename)
