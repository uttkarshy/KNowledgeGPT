# V2 reconstruction checkpoints

Starting source: 7221a41aa16e8721ae24e538635f45507b1c98e7.
Production is not changed by this work.

## Stage A

Deterministic semantic/exact-date/analytical/quoted lexical/row routing.
Analytical evidence is owner + KB scoped on both documents and chunks,
Ready-only, capped at 2,000 chunks / 2 million characters / 6,000 prompt
 tokens. Deterministic financial calculations accept explicit debit/credit
rows only and use Decimal. Ambiguous legacy layouts and overlap refuse.
Ranked results support up to 20 rows; evidence citations are capped at 32.
No similarity threshold or provider/model changes.
Structured row routing currently refuses until the extraction contract is added.

Validation: backend 82 passed, 4 PostgreSQL tests skipped (no local server).
Exact-date regressions and synthetic totals 1844.00 / 1715.89 pass.
Monthly top-three uses the complete bounded evidence, not semantic top-K.

## Stage B

Successful embedding batches commit independently and are reused only when
index/checksum/model match. Failed documents remain excluded from retrieval.
Worker advisory locking and the new unique document/chunk index protect retries.
Original objects remain available until the final durable success commit.
429 failures preserve Retry-After/RetryInfo and use capped exponential jitter.
Automatic retries stop at the configured Celery retry count; provider advice over
one hour requires manual retry later. Embedding SDK retries are disabled to avoid
multiplying budgets. Stalled jobs are marked retryable only after checking that
no worker owns the advisory lock. Manual retry checks owner, confirmed upload and
storage size, and commits the queued state before dispatch.

Migration 0004 adds retry/error metadata and a unique chunk constraint; duplicate
legacy indices stop migration for review rather than deleting data.
Validation: 85 backend tests passed, 4 DB tests skipped. Ruff passed. Upgrade SQL
from 0003 to 0004 generated successfully; actual PostgreSQL upgrade not yet run.

## Stage C

Selective CPU Tesseract OCR now corrects orientation (OSD plus bounded four-way
fallback) and slight ruled-page skew. Native-text PDFs keep the fast path.
Recognizable table rows carry page/table/row/cell provenance; uncertain cells
stay empty, and spatial OCR lines are packed into bounded 900-byte groups with
line ranges. Named-cell answers reject uncertain spatial text; prompts retain
its uncertainty. No account/IFSC digit substitutions or guessed cells.
Migration 0005 adds nullable JSONB row provenance; existing vectors stay valid.

Actual supplied fixture evaluation (English OCR installed locally):
- Payroll scan: 11/11 pages extracted, 92 chunks, 94 seconds. Neither requested
  person's full named row was verified. PARTIALLY IMPROVED, NOT FIXED.
- Sideways TGT merit list: 22/22 pages extracted, 62 chunks, 227 seconds;
  orientation corrected, no dependable table rows. PARTIALLY IMPROVED, NOT FIXED.
- Both fit the unchanged 1,000-chunk ceiling. This is extraction/chunking evidence,
  not live Gemini/pgvector ingestion or independently verified cell accuracy.
- `scripts/evaluate_scans.py` repeats local evaluation and prints aggregates only.
  Private fixtures and extracted private text are excluded from the repository.

Validation: 94 backend tests passed, 4 local PostgreSQL tests skipped; Ruff passed.
Offline upgrade SQL from production revision 0003 through 0005 passed. Actual DB
validation uses CI. Fixed the existing DB exact-date test's missing non-null test
embedding, preserving its assertions. Stage B CI had passed Docker clean boot
and migrations; frontend test runtime mismatch remains for final validation.
