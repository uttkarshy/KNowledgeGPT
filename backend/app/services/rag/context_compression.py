"""
Context compression — the step between "similarity search returned chunks"
and "text that actually goes in the prompt".

Two real, functional operations (not just token-truncation):
  1. Dedupe: if the same underlying content was chunked and embedded twice
     (e.g. a re-uploaded revision, or an identical paragraph appearing in
     two documents) don't spend context budget on it twice.
  2. Token-budget capping: keep the highest-similarity chunks first, drop
     from the bottom once the running total would exceed the budget —
     never silently truncate a chunk's text mid-sentence.
"""

from __future__ import annotations

from app.services.chunking.token_estimate import estimate_tokens
from app.services.rag.retrieval import RetrievedChunk


def compress_context(
    chunks: list[RetrievedChunk], *, max_context_tokens: int = 3000
) -> list[RetrievedChunk]:
    """Input is assumed already sorted by similarity descending (as
    similarity_search returns it). Returns the subset to actually include
    in the prompt."""
    seen_content_hashes: set[int] = set()
    deduped: list[RetrievedChunk] = []
    for chunk in chunks:
        content_key = hash(chunk.content.strip().lower())
        if content_key in seen_content_hashes:
            continue
        seen_content_hashes.add(content_key)
        deduped.append(chunk)

    kept: list[RetrievedChunk] = []
    running_tokens = 0
    for chunk in deduped:
        chunk_tokens = estimate_tokens(chunk.content)
        if running_tokens + chunk_tokens > max_context_tokens and kept:
            break
        kept.append(chunk)
        running_tokens += chunk_tokens

    return kept
