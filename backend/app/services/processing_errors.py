"""User-safe failure types; provider payloads never enter UI messages."""

from __future__ import annotations

import random


class ProcessingFailure(Exception):
    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def retry_delay(attempt: int, base: int, provider_delay: float | None = None) -> float:
    return max(min(900, base * 2 ** min(attempt, 10)) + random.uniform(0, base), provider_delay or 0)


def classify(exc: Exception, stage: str) -> ProcessingFailure:
    from billiard.exceptions import SoftTimeLimitExceeded

    from app.services.extraction.schemas import ExtractionError, UnsupportedFormatError
    from app.services.llm.base import LLMInvalidRequestError, LLMProviderError, LLMRateLimitError
    from app.services.upload.validation import FileValidationError

    if isinstance(exc, ProcessingFailure):
        return exc
    if isinstance(exc, LLMRateLimitError):
        return ProcessingFailure(
            "provider_rate_limited",
            "Processing is temporarily unavailable due to AI provider limits. Retry processing later.",
            retryable=True,
        )
    if isinstance(exc, LLMInvalidRequestError):
        return ProcessingFailure(
            "embedding_failure", "AI provider rejected the processing configuration. Contact support."
        )
    if isinstance(exc, LLMProviderError):
        return ProcessingFailure(
            "provider_unavailable", "AI processing is temporarily unavailable. Retry processing later.", retryable=True
        )
    if isinstance(exc, SoftTimeLimitExceeded):
        return ProcessingFailure(
            "processing_timeout",
            "Processing exceeded the time budget. Retry Processing to resume saved progress.",
            retryable=True,
        )
    if isinstance(exc, UnsupportedFormatError):
        return ProcessingFailure("unsupported_format", "This format is not supported. Upload a supported document.")
    if isinstance(exc, ExtractionError):
        return ProcessingFailure(
            "extraction_failure", "Document extraction failed. Upload a clearer or different file."
        )
    if isinstance(exc, FileValidationError):
        return ProcessingFailure(
            getattr(exc, "code", "invalid_file"),
            "File validation failed. Check file size and format; upload a different file.",
        )
    return ProcessingFailure(
        "internal_processing_failure",
        f"Unexpected internal processing failure during {stage}. Retry Processing or contact support.",
        retryable=True,
    )
