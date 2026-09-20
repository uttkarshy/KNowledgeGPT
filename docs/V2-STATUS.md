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
