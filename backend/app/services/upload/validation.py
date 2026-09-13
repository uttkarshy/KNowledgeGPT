"""
File validation — runs BEFORE anything else touches an uploaded file.

Three layers, deliberately in this order (cheapest/least-trustworthy first):
  1. Extension allowlist         — rejects obviously wrong file types fast
  2. Server-side size check      — via S3 head_object, never trusts the client
  3. Magic-byte content sniffing — catches a renamed .exe pretending to be
     .pdf, which the extension check alone would miss
"""

from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from typing import Optional

import filetype

from app.core.config import Settings
from app.models.enums import FileType

# Maps our internal FileType enum to the set of magic-byte-detected
# extensions/mimes that are acceptable for it. Formats filetype.py can't
# sniff (plain text, csv, markdown, json, xml, rtf) are allowed through on
# extension alone — they have no reliable binary signature by design.
_SNIFFABLE_MATCHES: dict[FileType, set[str]] = {
    FileType.PDF: {"pdf"},
    FileType.DOCX: {"docx", "zip"},   # docx is a zip container
    FileType.PPTX: {"pptx", "zip"},
    FileType.XLSX: {"xlsx", "zip"},
    FileType.ZIP: {"zip"},
    FileType.IMAGE: {"png", "jpg", "jpeg", "tiff", "bmp", "gif", "webp"},
}

_EXTENSION_TO_FILE_TYPE: dict[str, FileType] = {
    "pdf": FileType.PDF,
    "docx": FileType.DOCX,
    "doc": FileType.DOC,
    "txt": FileType.TXT,
    "csv": FileType.CSV,
    "xlsx": FileType.XLSX,
    "xls": FileType.XLS,
    "pptx": FileType.PPTX,
    "md": FileType.MARKDOWN,
    "markdown": FileType.MARKDOWN,
    "html": FileType.HTML,
    "htm": FileType.HTML,
    "xml": FileType.XML,
    "json": FileType.JSON,
    "rtf": FileType.RTF,
    "png": FileType.IMAGE,
    "jpg": FileType.IMAGE,
    "jpeg": FileType.IMAGE,
    "tiff": FileType.IMAGE,
    "bmp": FileType.IMAGE,
    "zip": FileType.ZIP,
}


class FileValidationError(Exception):
    pass


@dataclass
class ValidationResult:
    file_type: FileType
    size_bytes: int
    checksum_sha256: str


def validate_extension(filename: str, settings: Settings) -> str:
    if "." not in filename:
        raise FileValidationError(f"File '{filename}' has no extension")
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in settings.ALLOWED_FILE_EXTENSIONS:
        raise FileValidationError(
            f"File extension '.{ext}' is not allowed. "
            f"Allowed: {', '.join(sorted(settings.ALLOWED_FILE_EXTENSIONS))}"
        )
    return ext


def validate_size(size_bytes: int, settings: Settings) -> None:
    if size_bytes <= 0:
        raise FileValidationError("File is empty")
    if size_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
        raise FileValidationError(
            f"File size {size_bytes} bytes exceeds the {settings.MAX_UPLOAD_SIZE_BYTES} byte limit"
        )


def validate_magic_bytes(file_path: str, declared_extension: str) -> Optional[str]:
    """Returns the sniffed extension, or None if the format isn't
    magic-byte-detectable (plain text formats). Raises if a sniffable
    format's actual bytes contradict the declared extension."""
    kind = filetype.guess(file_path)
    file_type = _EXTENSION_TO_FILE_TYPE.get(declared_extension)

    if kind is None:
        # Not detectable via magic bytes (txt/csv/md/json/xml/rtf/html) —
        # nothing to cross-check here.
        if file_type in _SNIFFABLE_MATCHES:
            raise FileValidationError("File signature does not match its declared format")
        return None

    expected = _SNIFFABLE_MATCHES.get(file_type)
    if expected is not None and kind.extension not in expected:
        raise FileValidationError(
            f"File content does not match its '.{declared_extension}' extension "
            f"(detected: {kind.mime})"
        )
    return kind.extension


def compute_checksum(file_path: str) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def validate_uploaded_file(
    *, file_path: str, filename: str, size_bytes: int, settings: Settings
) -> ValidationResult:
    """Full validation pipeline against a file already downloaded to local
    disk (i.e. run inside the Celery worker after pulling from S3)."""
    ext = validate_extension(filename, settings)
    validate_size(size_bytes, settings)
    validate_magic_bytes(file_path, ext)
    if ext in {"docx", "xlsx", "pptx"}:
        with zipfile.ZipFile(file_path) as archive:
            members = archive.infolist()
            if len(members) > 10000 or sum(x.file_size for x in members) > 100 * 1024 * 1024:
                raise FileValidationError("Office archive exceeds safe extraction limits")
            expected = {"docx": "word/document.xml", "xlsx": "xl/workbook.xml", "pptx": "ppt/presentation.xml"}[ext]
            if expected not in archive.namelist():
                raise FileValidationError("Invalid Office document structure")
    checksum = compute_checksum(file_path)

    return ValidationResult(
        file_type=_EXTENSION_TO_FILE_TYPE[ext],
        size_bytes=size_bytes,
        checksum_sha256=checksum,
    )
