"""
Approximate token counting for chunk-sizing decisions.

Deliberately NOT using tiktoken here: tiktoken downloads its BPE encoding
file from a remote blob endpoint on first use in a given environment, which
is a fragile dependency for a production/air-gapped deployment (and isn't
reachable from networks that only allow package registries, as observed
while building this). Chunk-boundary decisions don't need exact token
counts — only a consistent, conservative estimate — so a character-based
heuristic is used instead. Exact token usage for billing/display still
comes from the LLM provider's real API response (see LLMUsage), never from
this estimate.

Heuristic: ~4 characters per token for English; CJK/Devanagari and other
non-Latin scripts run denser (closer to 1-2 chars/token), so those are
weighted accordingly based on a simple script detection.
"""

from __future__ import annotations

import re

_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")


def estimate_tokens(text: str) -> int:
    if not text:
        return 0

    devanagari_chars = len(_DEVANAGARI_RE.findall(text))
    cjk_chars = len(_CJK_RE.findall(text))
    total_chars = len(text)
    other_chars = total_chars - devanagari_chars - cjk_chars

    # Denser scripts: ~1.5 chars/token. Latin/English: ~4 chars/token.
    estimated = (other_chars / 4.0) + (devanagari_chars / 1.5) + (cjk_chars / 1.5)
    return max(1, int(estimated))
