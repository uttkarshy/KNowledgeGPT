"""Synthetic legacy native-PDF cells only; no production PII or references."""

import uuid
from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.models.chat import ChatSession
from app.services.chunking.semantic_chunker import chunk_document
from app.services.extraction.schemas import ExtractedBlock, ExtractedDocument, ExtractedPage, SectionKind
from app.services.rag import engine
from app.services.rag.exact_date import DateEvidenceLimit
from app.services.rag.exhaustive import calculate, transactions
from app.services.rag.query_router import route
from app.services.rag.retrieval import RetrievedChunk

QUESTION = "What were my 3 largest expenses in July 2026? Give the date, description and amount for each."
HEADER = "Savings Account Transactions\n#\nDate\nDescription\nChq/Ref. No.\nWithdrawal (Dr.)\nDeposit (Cr.)\nBalance\n"


def ledger():
    # An omitted empty column is represented by TWO cells, not a guessed blank.
    return (
        HEADER
        + "Opening Balance\n20,000.00\n"
        + "\n".join(
            [
                "1\n19 Jul 2026\nSynthetic program fee\nTEST-REF-A001\n499.00\n19,501.00",
                "2\n20 Jul 2026\nSynthetic cashback\nTEST-REF-B001\n250.00\n19,751.00",
                "3\n22 Jul 2026\nSynthetic purchase\nTEST-REF-C001\n88.00\n19,663.00",
                "4\n23 Jul 2026\nSynthetic rent\nTEST-REF-D001\n1,000.00\n18,663.00",
                "5\n24 Jul 2026\nSynthetic deposit\nTEST-REF-E001\n9,000.00\n27,663.00",
                "6\n25 Jul 2026\nSynthetic appliance\nTEST-REF-F001\n2,400.00\n25,263.00",
                "7\n01 Aug 2026\nSynthetic travel\nTEST-REF-G001\n8,000.00\n17,263.00",
            ]
        )
    )


def chunks(*texts, document=None):
    document = document or uuid.uuid4()
    return [
        RetrievedChunk(uuid.uuid4(), document, "synthetic-ledger.pdf", text, 1, None, 1.0, chunk_index=i)
        for i, text in enumerate(texts)
    ]


def test_exact_live_question_routes_unchanged_and_ranks_debits_only():
    plan = route(QUESTION)
    assert (plan.strategy, plan.operation, plan.count, plan.financial) == ("analytical", "top", 3, True)
    assert plan.periods == ((date(2026, 7, 1), date(2026, 7, 31)),)
    answer, sources = calculate(chunks(ledger()), plan, QUESTION)
    assert "Analyzed 4 complete debit rows" in answer
    assert answer.index("2,400.00") < answer.index("1,000.00") < answer.index("499.00")
    for value in ("9,000.00", "8,000.00", "25,263.00", "250.00", "cashback", "deposit"):
        assert value not in answer
    assert "2026-07-25 | Synthetic appliance" in answer
    assert "2026-07-23 | Synthetic rent" in answer
    assert "2026-07-19 | Synthetic program fee" in answer
    assert len(sources) == 1


def test_cashback_and_deposit_are_credits_and_description_is_not_direction():
    rows = transactions(chunks(ledger().replace("Synthetic cashback", "Synthetic expense refund")))
    assert rows[1][2:4] == (Decimal("250.00"), "credit")
    assert rows[4][2:4] == (Decimal("9000.00"), "credit")
    answer, _ = calculate(chunks(ledger()), route("total deposits in July 2026"), "deposits")
    assert "9,250.00" in answer and "2 credit transactions" in answer


@pytest.mark.parametrize("columns", [("100.00", "-", "debit"), ("-", "100.00", "credit"), ("100.00", "0.00", "debit")])
def test_explicit_slots_need_no_opening_balance(columns):
    debit, credit, direction = columns
    text = HEADER + f"1\n19 Jul 2026\nSynthetic item\nTEST-REF-A001\n{debit}\n{credit}\n500.00"
    assert transactions(chunks(text))[0][2:4] == (Decimal("100.00"), direction)


def test_equivalent_schema_and_reversed_direction_columns():
    text = HEADER.replace("Chq/Ref. No.", "Reference").replace("Withdrawal (Dr.)\nDeposit (Cr.)", "Credit\nDebit")
    text += "1\n19 Jul 2026\nSynthetic item\nTEST-REF-A001\n100.00\n-\n500.00"
    assert transactions(chunks(text))[0][3] == "credit"


@pytest.mark.parametrize(
    "transform",
    [
        lambda s: s.replace("Opening Balance\n20,000.00\n", ""),
        lambda s: s.replace("19,501.00", "19,500.00"),
        lambda s: s.replace("499.00\n19,501.00", "499.00\n12.00\n19,501.00"),
        lambda s: s.replace("499.00\n19,501.00", "-\n-\n19,501.00"),
        lambda s: s.replace("499.00\n19,501.00", "19,501.00"),
        lambda s: s.replace("TEST-REF-A001\n", ""),
        lambda s: s.replace("2\n20 Jul", "3\n20 Jul"),
        lambda s: s.replace("20 Jul 2026", "18 Jul 2026"),
        lambda s: s.replace("20 Jul 2026", "31 Feb 2026"),
        lambda s: s.replace("20 Jul 2026", "03/04/2026"),
        lambda s: s.replace("499.00", "4,99.00"),
        lambda s: s.replace("499.00", "0.00"),
        lambda s: s.replace("Deposit (Cr.)", "Unknown column"),
        lambda s: s + "\n8\n02 Aug 2026\nTruncated item",
        lambda s: s + "\nUnrecognized footer 123.00",
        lambda s: s + "\nClosing Balance\n1.00",
    ],
)
def test_ambiguous_inconsistent_or_incomplete_ledger_fails_whole_ranking(transform):
    with pytest.raises(DateEvidenceLimit):
        calculate(chunks(transform(ledger())), route(QUESTION), QUESTION)


def test_cross_chunk_row_and_header_reconstruction_retains_original_citations():
    text = ledger()
    cut = text.index("2,400.00")
    evidence = chunks(text[: cut + 3], text[cut + 3 :])
    # A split within a cell cannot be established from missing text boundaries.
    with pytest.raises(DateEvidenceLimit):
        calculate(evidence, route(QUESTION), QUESTION)
    cut_header = text.index("Description")
    evidence = chunks(text[:cut_header], text[cut_header:cut], text[cut:])
    answer, sources = calculate(evidence, route(QUESTION), QUESTION)
    assert "2,400.00" in answer
    assert {c.chunk_id for c in sources} == {c.chunk_id for c in evidence}
    assert all(c.content == evidence[c.chunk_index].content for c in sources)
    assert calculate(evidence, route(QUESTION), QUESTION) == (answer, sources)
    with pytest.raises(DateEvidenceLimit):
        calculate(evidence[:-1], route(QUESTION), QUESTION)


@pytest.mark.parametrize("kind", ["gap", "unknown", "reorder", "duplicate", "foreign"])
def test_adjacent_evidence_must_be_complete_and_same_document(kind):
    text = ledger()
    cut = text.index("2,400.00")
    evidence = chunks(text[:cut], text[cut:])
    if kind == "gap":
        evidence[1].chunk_index = 2
    elif kind == "unknown":
        evidence[1].chunk_index = None
    elif kind == "reorder":
        evidence.reverse()
    elif kind == "duplicate":
        evidence.append(evidence[0])
    else:
        evidence[1].document_id = uuid.uuid4()
    with pytest.raises(DateEvidenceLimit):
        calculate(evidence, route(QUESTION), QUESTION)


def test_flattened_exact_overlap_is_deduplicated_but_conflicts_refuse():
    text = ledger()
    cut = text.index("4\n23 Jul")
    overlap = " ".join(text[text.index("3\n22 Jul") : cut].split())
    evidence = chunks(text[:cut], overlap + "\n\n" + text[cut:])
    rows = transactions(evidence)
    assert len(rows) == 7 and sum(r[2] for r in rows if r[3] == "debit") == Decimal("11987.00")
    evidence[1].content = evidence[1].content.replace("88.00", "89.00")
    with pytest.raises(DateEvidenceLimit):
        transactions(evidence)
    with pytest.raises(DateEvidenceLimit):
        transactions(chunks(text + "\n" + text[text.index("3\n22 Jul") : cut]))


def test_no_silently_discarded_preamble_rows_or_missing_reference():
    for text in (
        "18 Jul 2026 | Synthetic previous purchase | Debit: 100.00\n" + ledger(),
        ledger().replace("TEST-REF-A001", "description continuation"),
    ):
        with pytest.raises(DateEvidenceLimit):
            transactions(chunks(text))
    evidence = chunks(ledger())
    evidence[0].chunk_index = 5
    with pytest.raises(DateEvidenceLimit):
        transactions(evidence)


def test_repeated_headers_closing_balance_and_monthly_comparison():
    text = ledger().replace("4\n23 Jul", HEADER.split("\n", 1)[1] + "4\n23 Jul")
    text += "\nClosing Balance\n17,263.00"
    assert len(transactions(chunks(text))) == 7
    plan = replace(route(QUESTION), operation="compare", periods=())
    answer, _ = calculate(chunks(text), plan, "expenses")
    assert "2026-07: ₹3,987.00" in answer and "2026-08: ₹8,000.00" in answer


def test_actual_chunker_overlap_either_reconstructs_or_refuses_never_partial():
    doc = ExtractedDocument(
        pages=[
            ExtractedPage(
                1, [ExtractedBlock(SectionKind.PARAGRAPH, line, page_number=1) for line in ledger().splitlines()]
            )
        ]
    )
    accepted_split = False
    for size in (50, 80, 120):
        produced = chunk_document(doc, chunk_size_tokens=size, overlap_tokens=30)
        evidence = chunks(*(c.text for c in produced))
        try:
            rows = transactions(evidence)
        except DateEvidenceLimit:
            continue  # Partial-cell/short overlap has insufficient identity.
        accepted_split |= len(produced) > 1
        assert [(r[0], r[2], r[3]) for r in rows] == [(r[0], r[2], r[3]) for r in transactions(chunks(ledger()))]

    assert accepted_split


def test_structured_and_labelled_formats_keep_priority_and_ocr_refuses():
    structured = chunks("untrusted text " + HEADER)[0]
    structured.structure = {
        "kind": "table_row",
        "table_id": 0,
        "row_index": 1,
        "cells": {"Date": "30 Jul 2026", "Description": "Synthetic", "Debit": "14.00", "Credit": ""},
    }
    assert transactions([structured])[0][2] == Decimal("14.00")
    with pytest.raises(DateEvidenceLimit):
        transactions([structured, structured])
    for text in (
        "30 Jul 2026 | Synthetic | Debit: 14.00",
        "Date | Description | Debit | Credit | Balance\n30 Jul 2026 | Synthetic | 14.00 | - | 99.00",
    ):
        assert transactions(chunks(text))[0][2] == Decimal("14.00")
    scan = chunks(ledger())[0]
    scan.structure = {"kind": "ocr_line", "uncertain_structure": True}
    with pytest.raises(DateEvidenceLimit):
        transactions([scan])
    with pytest.raises(DateEvidenceLimit):
        transactions(chunks(ledger(), "uncertain")[:-1] + [replace(scan, document_id=structured.document_id)])


@pytest.mark.parametrize("day,total", [(30, "1,844.00"), (31, "1,715.89")])
def test_vertical_exact_date_totals(day, total):
    text = HEADER + "Opening Balance\n10,000.00\n"
    balance = Decimal("10000")
    values = [
        (30, "14"),
        (30, "1540"),
        (30, "35"),
        (30, "180"),
        (30, "15"),
        (30, "60"),
        (31, "1000"),
        (31, "406.89"),
        (31, "309"),
    ]
    for index, (d, amount) in enumerate(values, 1):
        balance -= Decimal(amount)
        text += f"{index}\n{d} Jul 2026\nSynthetic purchase {index}\nTEST-REF-{index}\n{Decimal(amount):.2f}\n{balance:.2f}\n"
    plan = replace(route("total expenses in July 2026"), periods=((date(2026, 7, day), date(2026, 7, day)),))
    assert total in calculate(chunks(text), plan, "expenses")[0]


async def test_engine_analytical_legacy_path_never_calls_gemini(monkeypatch):
    evidence = chunks(ledger())
    db = AsyncMock()
    db.add = lambda obj: None
    db.execute.side_effect = [
        SimpleNamespace(one=lambda: (1, len(ledger()))),
        SimpleNamespace(
            all=lambda: [
                (
                    SimpleNamespace(
                        id=evidence[0].chunk_id,
                        document_id=evidence[0].document_id,
                        content=ledger(),
                        page_number=1,
                        section=None,
                        structure=None,
                        chunk_index=0,
                    ),
                    "synthetic-ledger.pdf",
                )
            ]
        ),
    ]
    monkeypatch.setattr(engine, "_fetch_recent_history", AsyncMock(return_value=[]))
    provider = AsyncMock()
    session = ChatSession(id=uuid.uuid4(), owner_id=uuid.uuid4(), knowledge_base_id=uuid.uuid4())
    events = [
        event
        async for event in engine.answer_question(
            db, settings=Settings(), provider=provider, session=session, question=QUESTION
        )
    ]
    assert events[-1].type == "done" and "2,400.00" in events[0].delta
    provider.embed.assert_not_called()
    provider.stream.assert_not_called()
