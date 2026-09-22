import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.services.rag.exact_date import DateEvidenceLimit
from app.services.rag.exhaustive import calculate, evidence
from app.services.rag.query_router import route
from app.services.rag.retrieval import RetrievalFilters, RetrievedChunk


@pytest.mark.parametrize(
    "question,strategy",
    [
        ("What is my highest qualification?", "semantic"),
        ("What is my highest educational qualification, and where did I complete it?", "semantic"),
        ("How much did I spend on 30 July 2026?", "exact_date"),
        ("Total withdrawals on 31 July 2026", "exact_date"),
        ("What were my 3 largest expenses in July 2026?", "analytical"),
        ("Give account number and IFSC for Example Person in payroll.pdf", "row"),
        ('Find "exact reference ZX123"', "lexical"),
        ("Compare expenses in July 2026 and August 2026", "analytical"),
    ],
)
def test_route(question, strategy):
    assert route(question).strategy == strategy


def fixture():
    document = uuid.uuid4()
    values = (
        [("30 Jul 2026", a) for a in (14, 1540, 35, 180, 15, 60)]
        + [("31 Jul 2026", a) for a in (1000, 406.89, 309)]
        + [("01 Aug 2026", 9000)]
    )
    return [
        RetrievedChunk(
            uuid.uuid4(),
            document,
            "synthetic.pdf",
            f"{day} | Synthetic purchase {i} | Debit {amount:.2f}",
            i + 1,
            None,
            1.0,
        )
        for i, (day, amount) in enumerate(values)
    ]


@pytest.mark.parametrize("day,total", [(30, "1,844.00"), (31, "1,715.89")])
def test_complete_decimal_totals(day, total):
    plan = route(f"total expenses on {day} July 2026")
    assert plan.strategy == "exact_date" and plan.financial and plan.target == date(2026, 7, day)
    answer, sources = calculate(fixture(), plan, "expenses")
    assert total in answer and len(sources) == (6 if day == 30 else 3)


def test_monthly_top_three_full_enumeration():
    answer, sources = calculate(fixture(), route("3 largest expenses in July 2026"), "expenses")
    assert "1,540.00" in answer and "1,000.00" in answer and "406.89" in answer
    assert "9,000.00" not in answer and "Analyzed 9 complete debit rows" in answer
    assert len(sources) == 3 and {s.page_number for s in sources} == {2, 7, 8}
    assert all(f"[{i}]" in answer for i in (1, 2, 3))


def test_ambiguous_layout_and_overlap_refuse():
    rows = fixture()
    with pytest.raises(DateEvidenceLimit):
        calculate(rows + [rows[0]], route("total expenses in July 2026"), "expenses")
    rows[0].content = "30 Jul 2026 | unknown 999 1000"
    with pytest.raises(DateEvidenceLimit):
        calculate(rows, route("total expenses in July 2026"), "expenses")


async def test_exhaustive_and_lexical_queries_scope_both_owners_and_kbs():
    for lexical in (None, '"reference"'):
        db = AsyncMock()
        db.execute.side_effect = [SimpleNamespace(one=lambda: (0, 0)), SimpleNamespace(all=lambda: [])]
        await evidence(
            db, owner_id=uuid.uuid4(), kb_id=uuid.uuid4(), filters=RetrievalFilters(document_ids=[]), lexical=lexical
        )
        for call in db.execute.call_args_list:
            compiled = call.args[0].compile(dialect=postgresql.dialect())
            for name in (
                "documents.owner_id",
                "document_chunks.owner_id",
                "documents.knowledge_base_id",
                "document_chunks.knowledge_base_id",
                "documents.status",
            ):
                assert name in str(compiled)
            assert [] in compiled.params.values()


async def test_evidence_budget_checked_before_loading():
    db = AsyncMock()
    db.execute.return_value = SimpleNamespace(one=lambda: (2001, 100))
    with pytest.raises(DateEvidenceLimit):
        await evidence(db, owner_id=uuid.uuid4(), kb_id=uuid.uuid4())
    assert db.execute.await_count == 1
