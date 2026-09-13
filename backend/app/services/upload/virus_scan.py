"""
Virus scanning via a ClamAV daemon (clamd), using its INSTREAM protocol
directly over a socket — no extra SDK dependency beyond the stdlib.

This is functional, not a no-op stub: if VIRUS_SCAN_ENABLED=true and a
clamd instance is reachable at CLAMAV_HOST:CLAMAV_PORT, files are actually
scanned. It defaults to disabled because most local/dev/CI environments
won't have a ClamAV daemon running, and the rest of the upload pipeline
should still be exercisable without one — see docker-compose (added in the
Docker increment) for a ready-to-run clamd service.
"""

from __future__ import annotations

import logging
import socket

from app.core.config import Settings

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 1024 * 1024  # 1MB, matches clamd's expected INSTREAM chunking
_SOCKET_TIMEOUT_SECONDS = 30


class VirusFoundError(Exception):
    def __init__(self, signature: str):
        self.signature = signature
        super().__init__(f"Malware detected: {signature}")


class VirusScanUnavailableError(Exception):
    """Raised when scanning is enabled but clamd can't be reached. Callers
    decide policy — the document service treats this as a hard failure
    (reject the upload) rather than silently skipping the scan."""


def scan_file(*, file_path: str, settings: Settings) -> None:
    """Scans a local file via clamd's INSTREAM command.

    Raises VirusFoundError if malware is detected, VirusScanUnavailableError
    if clamd can't be reached, or returns silently if the file is clean.
    Does nothing if VIRUS_SCAN_ENABLED is False.
    """
    if not settings.VIRUS_SCAN_ENABLED:
        logger.debug("Virus scanning disabled — skipping scan for %s", file_path)
        return

    try:
        with socket.create_connection(
            (settings.CLAMAV_HOST, settings.CLAMAV_PORT), timeout=_SOCKET_TIMEOUT_SECONDS
        ) as sock:
            sock.sendall(b"zINSTREAM\0")
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(_CHUNK_SIZE)
                    size_header = len(chunk).to_bytes(4, byteorder="big")
                    sock.sendall(size_header + chunk)
                    if not chunk:
                        break
            received = bytearray()
            while b"\0" not in received and len(received) < 4096:
                data = sock.recv(4096 - len(received))
                if not data:
                    break
                received.extend(data)
            response = bytes(received).decode("utf-8", errors="replace").rstrip("\0").strip()
    except OSError as e:
        raise VirusScanUnavailableError(
            f"Could not reach ClamAV daemon at {settings.CLAMAV_HOST}:{settings.CLAMAV_PORT}: {e}"
        ) from e

    # clamd responses look like "stream: OK" or "stream: Eicar-Test-Signature FOUND"
    if response.endswith("FOUND"):
        signature = response.replace("stream:", "").replace("FOUND", "").strip()
        raise VirusFoundError(signature)
    if not response.endswith("OK"):
        raise VirusScanUnavailableError(f"Unexpected ClamAV response: {response}")
