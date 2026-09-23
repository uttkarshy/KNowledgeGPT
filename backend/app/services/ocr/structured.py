"""Selective bounded CPU OCR; conservative ruled tables and spatial line fallback."""

from __future__ import annotations

from functools import lru_cache
import re
import subprocess

import cv2
import numpy as np
import pytesseract
from PIL import Image

from app.services.extraction.schemas import ExtractedBlock, ExtractedPage, SectionKind
from app.services.extraction.table_rows import row_block
from app.services.processing_errors import ProcessingFailure


_TESSERACT_DISCOVERY_TIMEOUT_SECONDS = 10


@lru_cache(maxsize=1)
def _installed_languages() -> tuple[str, ...]:
    """List Tesseract languages without pytesseract's unbounded subprocess."""
    try:
        result = subprocess.run(
            [pytesseract.pytesseract.tesseract_cmd, "--list-langs"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=_TESSERACT_DISCOVERY_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("OCR language discovery failed") from exc
    if result.returncode not in (0, 1):
        raise RuntimeError("OCR language discovery failed")
    return tuple(
        line.strip()
        for line in result.stdout.decode("utf-8", errors="replace").splitlines()
        if re.fullmatch(r"[a-z0-9_]+", line.strip())
    )


def normalize(image):
    rotation, confidence = 0, 0
    try:
        osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT, timeout=10)
        rotation, confidence = int(osd.get("rotate", 0)), float(osd.get("orientation_conf", 0))
    except (RuntimeError, pytesseract.TesseractError):
        pass
    if confidence < 4:
        sample = image.copy()
        sample.thumbnail((1400, 1400))
        best = -1
        for angle in (0, 90, 180, 270):
            try:
                data = pytesseract.image_to_data(
                    sample.rotate(-angle, expand=True, fillcolor="white"),
                    lang="eng",
                    config="--psm 11",
                    output_type=pytesseract.Output.DICT,
                    timeout=10,
                )
                score = sum(
                    float(c) * min(len(t), 12)
                    for t, c in zip(data["text"], data["conf"], strict=True)
                    if float(c) >= 65 and len(t) >= 3 and re.search("[A-Za-z]", t)
                )
                if score > best:
                    best, rotation = score, angle
            except (RuntimeError, pytesseract.TesseractError):
                continue
    normalized = image.rotate(-rotation, expand=True, fillcolor="white") if rotation else image
    gray = np.array(normalized.convert("L"))
    lines = cv2.HoughLinesP(
        cv2.Canny(gray, 60, 180), 1, np.pi / 1800, 100, minLineLength=gray.shape[1] // 3, maxLineGap=20
    )
    angles = []
    if lines is not None:
        for x1, y1, x2, y2 in lines[:, 0]:
            angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if abs(angle) < 5:
                angles.append(angle)
    if len(angles) >= 3 and abs(float(np.median(angles))) > 0.1:
        normalized = normalized.rotate(float(np.median(angles)), expand=True, fillcolor="white")
    return normalized, rotation


def _centres(indices):
    groups = []
    for i in indices:
        if groups and i <= groups[-1][-1] + 3:
            groups[-1].append(int(i))
        else:
            groups.append([int(i)])
    return [round(sum(group) / len(group)) for group in groups]


def _grids(gray):
    h, w = gray.shape
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15)
    horizontal = cv2.morphologyEx(
        binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, w // 5), 1))
    )
    vertical = cv2.morphologyEx(
        binary, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(25, h // 5)))
    )
    mask = cv2.bitwise_or(horizontal, vertical)
    contours, _ = cv2.findContours(
        cv2.dilate(mask, np.ones((3, 3), np.uint8)), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    grids = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if width < w * 0.3 or height < h * 0.1:
            continue
        xs = [
            x + i
            for i in _centres(np.where((vertical[y : y + height, x : x + width] > 0).sum(axis=0) > height * 0.3)[0])
        ]
        ys = [
            y + i
            for i in _centres(np.where((horizontal[y : y + height, x : x + width] > 0).sum(axis=1) > width * 0.25)[0])
        ]
        if 3 <= len(xs) <= 35 and 3 <= len(ys) <= 200:
            grids.append((xs, ys))
    clean = gray.copy()
    # Do not erase aligned glyph strokes on ordinary text pages.
    if grids:
        clean[mask > 0] = 255
    return grids[:5], clean


def scanned_page(image: Image.Image, page_number: int) -> ExtractedPage:
    if image.width * image.height > 12_000_000:
        raise ProcessingFailure("ocr_failure", "Scanned page exceeds safe OCR resolution. Upload a smaller scan.")
    try:
        image, rotation = normalize(image)
        gray = np.array(image.convert("L"))
        grids, clean = _grids(gray)
        installed = _installed_languages()
        languages = "+".join(code for code in ("eng", "hin") if code in installed)
        if not languages:
            raise RuntimeError("OCR languages missing")
        data = pytesseract.image_to_data(
            clean, lang=languages, config="--psm 6", output_type=pytesseract.Output.DICT, timeout=40
        )
        words = [
            (
                text.strip(),
                float(data["conf"][i]),
                data["left"][i] + data["width"][i] / 2,
                data["top"][i] + data["height"][i] / 2,
            )
            for i, text in enumerate(data["text"])
            if text.strip() and float(data["conf"][i]) >= 0
        ]
        blocks, used = [], set()
        for table_id, (xs, ys) in enumerate(grids):
            rows = []
            for row in range(len(ys) - 1):
                values, confidence = [], []
                for col in range(len(xs) - 1):
                    found = [
                        word for word in words if xs[col] < word[2] < xs[col + 1] and ys[row] < word[3] < ys[row + 1]
                    ]
                    found.sort(key=lambda word: (round(word[3] / 8), word[2]))
                    score = min((word[1] for word in found), default=0)
                    values.append(" ".join(word[0] for word in found) if score >= 70 else "")
                    confidence.append(score)
                rows.append((values, confidence))
            headers = rows[0][0]
            # Short header cells are often missed by sparse whole-page OCR.
            for col, header in enumerate(headers):
                if not header:
                    crop = gray[ys[0] + 3 : ys[1] - 3, xs[col] + 3 : xs[col + 1] - 3]
                    if crop.size:
                        raw = pytesseract.image_to_string(crop, lang=languages, config="--psm 7", timeout=5).strip()
                        if re.fullmatch(r"[A-Za-z .:/()0-9_-]{2,40}", raw):
                            headers[col] = raw
            recognized = sum(
                bool(
                    re.search(
                        r"\b(name|account|ifsc|payable|date|debit|credit|description|rank|appno|phone|state|total|amount)\b",
                        h,
                        re.I,
                    )
                )
                for h in headers
            )
            if recognized < 2:
                continue  # not a trustworthy header; do not relabel a data row
            used.update(i for i, word in enumerate(words) if xs[0] < word[2] < xs[-1] and ys[0] < word[3] < ys[-1])
            for row, (values, confidence) in enumerate(rows[1:], 1):
                for i, header in enumerate(headers):
                    if (
                        "ifsc" in header.lower()
                        and values[i]
                        and not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", values[i].replace(" ", ""))
                    ):
                        values[i] = ""
                    if (
                        "account" in header.lower()
                        and values[i]
                        and not re.fullmatch(r"\d{6,24}", values[i].replace(" ", ""))
                    ):
                        values[i] = ""
                if any(values):
                    blocks.append(
                        row_block(
                            headers,
                            values,
                            page_number=page_number,
                            table_id=table_id,
                            row_index=row,
                            confidence=confidence,
                            rotation=rotation,
                        )
                    )
        # Spatial lines keep adjacent cells together even when table structure is
        # uncertain. They are NOT eligible for deterministic named-cell answers.
        lines = []
        for i, word in sorted(enumerate(words), key=lambda item: (item[1][3], item[1][2])):
            if i in used or word[1] < 50:
                continue
            if lines and abs(word[3] - lines[-1][0]) <= 8:
                lines[-1][1].append(word)
            else:
                lines.append((word[3], [word]))
        for index, (_, line) in enumerate(lines):
            text = " ".join(word[0] for word in sorted(line, key=lambda word: word[2]))
            blocks.append(
                ExtractedBlock(
                    SectionKind.PARAGRAPH,
                    text,
                    page_number=page_number,
                    structure={
                        "kind": "ocr_line",
                        "row_index": index,
                        "rotation": rotation,
                        "uncertain_structure": True,
                    },
                )
            )
        blocks = pack_ocr_lines(blocks)
        if not blocks:
            raise ProcessingFailure("ocr_failure", "Scanned-document extraction failed. Upload a clearer upright scan.")
        return ExtractedPage(
            page_number=page_number,
            blocks=blocks,
            was_ocr=True,
            ocr_confidence=sum(w[1] for w in words) / len(words) if words else 0,
        )
    except ProcessingFailure:
        raise
    except (RuntimeError, pytesseract.TesseractError, cv2.error, OSError) as exc:
        raise ProcessingFailure(
            "ocr_failure", "Scanned-document extraction failed. Upload a clearer scan or try later."
        ) from exc


def pack_ocr_lines(blocks: list[ExtractedBlock], max_bytes: int = 900) -> list[ExtractedBlock]:
    """Pack uncertain spatial lines, preserving boundaries and provenance.

    These groups remain ineligible for deterministic cell/arithmetic answers.
    Trusted rows are never joined. Oversized individual lines retain the existing
    hard-limit failure rather than silently dropping or splitting cells.
    """
    packed = []
    for block in blocks:
        meta = block.structure or {}
        if meta.get("kind") == "ocr_line":
            previous = packed[-1] if packed else None
            if (
                previous is not None
                and (previous.structure or {}).get("kind") == "ocr_line"
                and previous.page_number == block.page_number
                and len((previous.text + "\n" + block.text).encode("utf-8")) <= max_bytes
            ):
                previous.text += "\n" + block.text
                previous.structure["last_line_index"] = meta["row_index"]
                continue
            block.structure = {**meta, "last_line_index": meta["row_index"]}
        packed.append(block)
    return packed
