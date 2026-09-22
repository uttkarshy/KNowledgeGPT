"""Synthetic generic-key PDF tables; no production statement data."""

import uuid
from copy import deepcopy
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.services.extraction.table_rows import row_block
from app.services.rag.exact_date import DateEvidenceLimit
from app.services.rag.exhaustive import calculate, transactions
from app.services.rag.query_router import route
from app.services.rag.retrieval import RetrievedChunk
from app.services.rag.structured_financial import _schema, _semantic

QUESTION = "What were my 3 largest expenses in July 2026? Give the date, description and amount for each."
PHYSICAL = ["Statement Transactions", None, None, None, None, None, None]
HEADER = ["#", "Date", "Description", "Chq/Ref. No.", "Withdrawal (Dr.)", "Deposit (Cr.)", "Balance"]


@pytest.mark.parametrize(
    "label",
    ["Amount", "Amount (INR)", "Amount INR", "Amount (USD)", "Amount USD",
     "Amount (EUR)", "Amount EUR", "Amount (GBP)", "Amount GBP",
     "Amount (₹)", "₹ Amount", "Amount ₹", " amount (inr) "],
)
@pytest.mark.parametrize("propagated", [False, True])
def test_supported_currency_amount_headers(label, propagated):
    assert _semantic(label) == "amount"
    assert _schema({"d": "Date", "t": "Type", "a": label}, propagated=propagated) == {
        "d": "date", "t": "direction", "a": "amount",
    }


@pytest.mark.parametrize("label", ["Amount Foo", "Amount Balance", "Amount Reference", "Amount INR Foo"])
@pytest.mark.parametrize("propagated", [False, True])
def test_unknown_amount_suffixes_fail_closed(label, propagated):
    assert _semantic(label) is None
    with pytest.raises(DateEvidenceLimit):
        _schema({"d": "Date", "t": "Type", "a": label}, propagated=propagated)


@pytest.mark.parametrize("labels", [
    {"d": "Date", "a": "Amount (INR)"},
    {"d": "Date", "t": "Type", "a": "Amount (INR)", "b": "Amount USD"},
    {"d": "Date", "t": "Type", "a": "Amount (INR)", "b": "Debit"},
])
def test_currency_amount_preserves_schema_ambiguity_checks(labels):
    with pytest.raises(DateEvidenceLimit):
        _schema(labels)


@pytest.mark.parametrize("direct_keys", [True, False])
def test_currency_header_production_top_three_debit_expenses(direct_keys):
    header = ["Date", "Description", "Type", "Amount (INR)"]
    values = [
        ["2026-07-02", "UPI - GREEN MART", "Debit", "842.50"],
        ["2026-07-03", "SALARY - NOVA SYSTEMS", "Credit", "62,500.00"],
        ["2026-07-05", "RENT - ARYA RESIDENCY", "Debit", "14,500.00"],
        ["2026-07-07", "METRO CARD RECHARGE", "Debit", "600.00"],
        ["2026-07-10", "ELECTRICITY BILL", "Debit", "2,384.75"],
        ["2026-07-12", "BOOKSTORE", "Debit", "1,299.00"],
        ["2026-07-15", "MEDICAL STORE", "Debit", "735.20"],
        ["2026-07-18", "FLIGHT BOOKING", "Debit", "6,890.00"],
        ["2026-07-21", "RESTAURANT - BLUE PLATE", "Debit", "1,845.60"],
        ["2026-07-25", "INTERNET BILL", "Debit", "999.00"],
        ["2026-07-29", "ELECTRONICS - TECH HUB", "Debit", "12,499.00"],
        ["2026-07-31", "GROCERY - DAILY BASKET", "Debit", "2,140.35"],
        ["2026-07-31", "CAB - CITY RIDE", "Debit", "486.00"],
    ]
    chunks = table(values if direct_keys else [header, *values])
    if direct_keys:
        for chunk, cells in zip(chunks, values, strict=True):
            chunk.structure["cells"] = dict(zip(header, cells, strict=True))
    answer, sources = calculate(chunks, route(QUESTION), QUESTION)
    assert "Analyzed 12 complete debit rows" in answer
    assert [line.split(" | ")[:3] for line in answer.splitlines() if line.startswith("| 2026")] == [
        ["| 2026-07-05", "RENT - ARYA RESIDENCY", "₹14,500.00"],
        ["| 2026-07-29", "ELECTRONICS - TECH HUB", "₹12,499.00"],
        ["| 2026-07-18", "FLIGHT BOOKING", "₹6,890.00"],
    ]
    offset = 0 if direct_keys else 1
    assert sources == [chunks[i + offset] for i in (2, 10, 7)]
    assert "SALARY" not in answer and "62,500.00" not in answer


def table(values=None, *, document_id=None, table_id=0, page=1):
    document_id = document_id or uuid.uuid4()
    values = (
        values
        if values is not None
        else [
            HEADER,
            ["1", "18 Jul 2026", "Synthetic supplies", "TEST001", "240.00", "", "99,760.00"],
            ["2", "19 Jul 2026", "Synthetic refund", "TEST002", "", "5000.00", "104,760.00"],
            ["3", "20 Jul 2026", "Synthetic course", "TEST003", "820.00", "", "103,940.00"],
            ["4", "21 Jul 2026", "Synthetic travel", "TEST004", "460.00", "", "103,480.00"],
            ["5", "22 Jul 2026", "Synthetic stationery", "TEST005", "75.00", "", "103,405.00"],
            ["6", "01 Aug 2026", "Synthetic rent", "TEST006", "9000.00", "", "94,405.00"],
        ]
    )
    result = []
    for index, cells in enumerate(values):
        block = row_block(PHYSICAL, cells, page_number=page, table_id=table_id, row_index=index + 1)
        result.append(
            RetrievedChunk(
                uuid.uuid4(),
                document_id,
                "synthetic.pdf",
                block.text,
                page,
                None,
                1.0,
                structure=block.structure,
                chunk_index=index,
            )
        )
    return result


def test_header_values_and_empty_cells_map_without_mutating_stored_rows():
    chunks = table()
    original = deepcopy(chunks)
    rows = transactions(chunks)
    assert len(rows) == 6  # schema is not data
    assert rows[0][:4] == (date(2026, 7, 18), "Synthetic supplies", Decimal("240.00"), "debit")
    assert rows[1][:4] == (date(2026, 7, 19), "Synthetic refund", Decimal("5000.00"), "credit")
    assert rows[0][4] is chunks[1]
    assert chunks == original
    assert all(row[2] < Decimal("94000") for row in rows)  # balance is never amount


def test_exact_question_top_three_excludes_credit_balance_and_august():
    chunks = table()
    answer, sources = calculate(chunks, route(QUESTION), QUESTION)
    assert "Analyzed 4 complete debit rows" in answer
    assert [line.split(" | ")[1:3] for line in answer.splitlines() if line.startswith("| 2026")] == [
        ["Synthetic course", "₹820.00"],
        ["Synthetic travel", "₹460.00"],
        ["Synthetic supplies", "₹240.00"],
    ]
    assert sources == [chunks[3], chunks[4], chunks[1]]
    assert all(token not in answer for token in ("5,000.00", "9,000.00", "103,940.00"))


@pytest.mark.parametrize("page", [1, 2])
def test_repeated_equivalent_header_reaffirms_schema(page):
    chunks = table()[:2]
    repeated = table(
        [HEADER, ["2", "20 Jul 2026", "Synthetic second", "TEST009", "20.00", "", "100.00"]],
        document_id=chunks[0].document_id,
        page=page,
    )
    repeated[0].structure["cells"].update({"Column 3": "Narration", "Column 5": "Debit", "Column 6": "Credit"})
    if page == 1:
        for c in repeated:
            c.structure["row_index"] += 10
    assert len(transactions(chunks + repeated)) == 2


@pytest.mark.parametrize("page", [1, 2])
def test_conflicting_repeated_header_fails_even_after_valid_transactions(page):
    chunks = table()[:2]
    conflicting = table([HEADER], document_id=chunks[0].document_id, page=page)[0]
    conflicting.structure["row_index"] = 20
    conflicting.structure["cells"].update({"Column 5": "Credit", "Column 6": "Debit"})
    with pytest.raises(DateEvidenceLimit):
        transactions(chunks + [conflicting])


@pytest.mark.parametrize("scope", ["document", "table", "page", "call"])
def test_no_header_mapping_leaks(scope):
    chunks = table()[:2]
    orphan = deepcopy(chunks[1])
    orphan.chunk_id = uuid.uuid4()
    orphan.structure["row_index"] = 20
    if scope == "document":
        orphan.document_id = uuid.uuid4()
    elif scope == "table":
        orphan.structure["table_id"] = 1
    elif scope == "page":
        orphan.page_number = 2
    else:
        transactions(chunks)
        chunks = []
    with pytest.raises(DateEvidenceLimit):
        transactions(chunks + [orphan])


@pytest.mark.parametrize(
    "updates",
    [
        {"Column 2": "Unknown"},
        {"Column 5": "Amount", "Column 6": "Unknown"},
        {"Column 5": "Balance"},
        {"Column 6": "Debit"},
        {"Column 4": "Transaction Date"},
        {"Column 3": "Particulars", "Column 4": "Narration"},
        {"Column 5": "Withdrawal (Cr.)"},
    ],
)
def test_missing_ambiguous_and_duplicate_semantic_columns_fail(updates):
    chunks = table()
    chunks[0].structure["cells"].update(updates)
    with pytest.raises(DateEvidenceLimit):
        calculate(chunks, route(QUESTION), QUESTION)


@pytest.mark.parametrize(
    "updates",
    [
        {"Column 5": "", "Column 6": ""},  # populated balance cannot rescue amount
        {"Column 5": "20.00", "Column 6": "30.00"},
        {"Column 2": "uncertain"},
        {"Column 5": "2O.00"},
    ],
)
def test_uncertain_data_refuses_all_arithmetic(updates):
    chunks = table()
    chunks[-1].structure["cells"].update(updates)  # even an out-of-period row must be sound
    with pytest.raises(DateEvidenceLimit):
        calculate(chunks, route(QUESTION), QUESTION)


@pytest.mark.parametrize("change", ["missing", "extra", "renamed", "semantic_switch"])
def test_physical_schema_change_fails(change):
    chunks = table()
    cells = chunks[-1].structure["cells"]
    if change == "missing":
        del cells["Column 6"]
    elif change == "extra":
        cells["Column 8"] = ""
    elif change == "renamed":
        cells["Other"] = cells.pop("Column 6")
    else:
        chunks[-1].structure["cells"] = dict(zip(HEADER, cells.values(), strict=True))
    with pytest.raises(DateEvidenceLimit):
        transactions(chunks)


@pytest.mark.parametrize("index", [0, 1])
def test_duplicate_provenance_including_header_refuses(index):
    chunks = table()
    duplicate = deepcopy(chunks[index])
    duplicate.chunk_id = uuid.uuid4()
    with pytest.raises(DateEvidenceLimit):
        transactions(chunks + [duplicate])


def test_data_before_header_is_not_backfilled():
    chunks = table()
    with pytest.raises(DateEvidenceLimit):
        transactions([chunks[1], chunks[0], *chunks[2:]])


def test_semantic_key_rows_keep_working_and_normalize_parenthesized_aliases():
    chunks = table()[1:]
    for c in chunks:
        c.structure["cells"] = dict(zip(HEADER, c.structure["cells"].values(), strict=True))
    assert len(transactions(chunks)) == 6


def test_unrelated_table_is_not_used_as_a_financial_schema():
    chunks = table([["Name", "Subject", "Level"], ["Example Person", "Computing", "Introductory"]])
    assert transactions(chunks) == []


@pytest.mark.parametrize(
    "day,amounts,total",
    [
        (30, ["14", "1540", "35", "180", "15", "60"], "1,844.00"),
        (31, ["1000", "406.89", "309"], "1,715.89"),
    ],
)
def test_mapped_exact_date_totals(day, amounts, total):
    chunks = table(
        [HEADER]
        + [
            [str(i), f"{day} Jul 2026", "Synthetic purchase", f"TEST{i:03}", a, "", "9000.00"]
            for i, a in enumerate(amounts, 1)
        ]
    )
    plan = replace(route("total expenses in July 2026"), periods=((date(2026, 7, day), date(2026, 7, day)),))
    assert f"₹{total}" in calculate(chunks, plan, "expenses")[0]


@pytest.mark.parametrize("column", ["Column 5", "Column 6"])
def test_one_missing_direction_header_refuses_even_if_rows_only_use_other_column(column):
    chunks = table()[:2]
    chunks[0].structure["cells"][column] = "Unknown"
    with pytest.raises(DateEvidenceLimit):
        transactions(chunks)


def test_unsupported_preamble_in_same_physical_table_is_not_silently_discarded():
    chunks = table()
    preamble = table(
        [["1", "unknown", "Synthetic uncertain transaction", "TEST008", "90.00", "", "1000.00"]],
        document_id=chunks[0].document_id,
    )[0]
    preamble.structure["row_index"] = 0
    with pytest.raises(DateEvidenceLimit):
        transactions([preamble] + chunks)


@pytest.mark.parametrize("scope", ["document", "table"])
def test_independent_scopes_can_have_different_schemas(scope):
    chunks = table()[:2]
    other = table()[:2]
    if scope == "table":
        for c in other:
            c.document_id = chunks[0].document_id
            c.structure["table_id"] = 1
    for c in other:
        cells = c.structure["cells"]
        cells["Column 5"], cells["Column 6"] = cells["Column 6"], cells["Column 5"]
    assert [r[2:4] for r in transactions(chunks + other)] == [(Decimal("240"), "debit")] * 2


@pytest.mark.parametrize("row_index", [0, 1])
def test_uncertain_ocr_header_or_amount_column_refuses(row_index):
    chunks = table()[:2]
    chunks[row_index].structure["confidence"] = [95, 95, 95, 95, 95, 20, 95]
    with pytest.raises(DateEvidenceLimit):
        transactions(chunks)


def test_semantic_only_schema_change_and_duplicate_aliases_refuse():
    chunks = table()[1:3]
    for c in chunks:
        c.structure["cells"] = dict(zip(HEADER, c.structure["cells"].values(), strict=True))
    chunks[1].structure["cells"]["Debit"] = "99.00"
    with pytest.raises(DateEvidenceLimit):
        transactions(chunks)


def test_amount_plus_explicit_direction_header_uses_existing_transaction_semantics():
    chunks = table(
        [
            ["#", "Date", "Particulars", "Reference", "Amount", "Dr/Cr", "Balance"],
            ["1", "20 Jul 2026", "Synthetic purchase", "TEST010", "55.00", "Dr", "999.00"],
        ]
    )
    assert transactions(chunks)[0][2:4] == (Decimal("55"), "debit")


@pytest.mark.parametrize("ambiguous", [False, True])
async def test_analytical_engine_uses_stored_header_rows_without_llm(monkeypatch, ambiguous):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.core.config import Settings
    from app.models.chat import ChatSession
    from app.services.rag import engine

    chunks = table()
    if ambiguous:
        chunks[-1].structure["cells"]["Column 6"] = "5.00"
    db = AsyncMock()
    db.add = lambda obj: None
    db.execute.side_effect = [
        SimpleNamespace(one=lambda: (len(chunks), sum(len(c.content) for c in chunks))),
        SimpleNamespace(
            all=lambda: [
                (
                    SimpleNamespace(
                        id=c.chunk_id,
                        document_id=c.document_id,
                        content=c.content,
                        page_number=c.page_number,
                        section=c.section,
                        structure=c.structure,
                        chunk_index=c.chunk_index,
                    ),
                    c.document_name,
                )
                for c in chunks
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
    assert events[-1].type == ("no_answer" if ambiguous else "done")
    text = "".join(e.delta or "" for e in events)
    if ambiguous:
        assert "No partial calculation" in text
        assert "820.00" not in text
    else:
        assert text.index("820.00") < text.index("460.00") < text.index("240.00")
    provider.embed.assert_not_called()
    provider.stream.assert_not_called()


def test_jsonb_key_order_does_not_change_mapping_or_hide_ocr_uncertainty():
    chunks = table()[:2]
    for c in chunks:
        c.structure["cells"] = dict(reversed(list(c.structure["cells"].items())))
    assert transactions(chunks)[0][2:4] == (Decimal("240.00"), "debit")
    chunks[0].structure["confidence"] = [95, 95, 95, 95, 95, 0, 95]
    with pytest.raises(DateEvidenceLimit):
        transactions(chunks)


def test_placeholder_row_after_header_is_skipped_but_transactions_are_kept():
    chunks = table(
        [
            HEADER,
            ["-", "-", "Opening placeholder", "-", "-", "-", "0.00"],
            ["1", "20 Jul 2026", "Synthetic purchase", "TEST101", "820.00", "", "100.00"],
            ["2", "21 Jul 2026", "Synthetic refund", "TEST102", "", "50.00", "150.00"],
        ]
    )
    rows = transactions(chunks)
    assert [(r[0], r[2], r[3]) for r in rows] == [
        (date(2026, 7, 20), Decimal("820.00"), "debit"),
        (date(2026, 7, 21), Decimal("50.00"), "credit"),
    ]


def test_dated_row_with_blank_debit_and_credit_still_fails_closed():
    chunks = table(
        [
            HEADER,
            ["1", "20 Jul 2026", "Synthetic ambiguous", "TEST103", "", "", "100.00"],
        ]
    )
    with pytest.raises(DateEvidenceLimit):
        transactions(chunks)


def test_undated_row_with_directional_amount_still_fails_closed():
    chunks = table(
        [
            HEADER,
            ["1", "-", "Synthetic ambiguous", "TEST104", "25.00", "", "75.00"],
        ]
    )
    with pytest.raises(DateEvidenceLimit):
        transactions(chunks)



def test_unstructured_companion_text_on_structured_page_is_not_reparsed_as_legacy():
    chunks = table(
        [
            HEADER,
            ["1", "20 Jul 2026", "Synthetic purchase", "TEST201", "820.00", "", "100.00"],
        ]
    )
    companion = RetrievedChunk(
        uuid.uuid4(),
        chunks[0].document_id,
        "synthetic.pdf",
        "Account Statement 01 Jul 2026 - 31 Jul 2026\n\n"
        "1\n\n"
        "20 Jul 2026\n\n"
        "Synthetic purchase\n\n"
        "TEST201\n\n"
        "820.00\n\n"
        "100.00\n\n"
        "Page 1 of 1",
        1,
        None,
        1.0,
        structure=None,
        chunk_index=2,
    )

    rows = transactions(chunks + [companion])

    assert [(r[0], r[1], r[2], r[3]) for r in rows] == [
        (date(2026, 7, 20), "Synthetic purchase", Decimal("820.00"), "debit")
    ]


def test_unrelated_later_page_with_reused_table_id_is_not_schema_propagated():
    chunks = table()[:2]
    legend = table(
        [["Legend", "UPI - Synthetic payment code", "", "", "", "", ""]],
        document_id=chunks[0].document_id,
        page=6,
    )[0]
    assert len(transactions(chunks + [legend])) == 1


def test_dated_later_page_without_local_header_still_fails_closed():
    chunks = table()[:2]
    orphan = table(
        [["1", "22 Jul 2026", "Synthetic orphan", "TEST105", "30.00", "", "70.00"]],
        document_id=chunks[0].document_id,
        page=2,
    )[0]
    with pytest.raises(DateEvidenceLimit):
        transactions(chunks + [orphan])
