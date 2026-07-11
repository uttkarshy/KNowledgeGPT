# System-level dependencies (beyond `pip install -r requirements.txt`)

These are OS packages, not Python packages. They need to be baked into the
Docker image (see the upcoming Docker increment) or installed manually in
any environment running the Celery workers.

## Required now (OCR)

```bash
apt-get install -y tesseract-ocr tesseract-ocr-hin
```

- `tesseract-ocr` — English OCR (and the core engine)
- `tesseract-ocr-hin` — Hindi language data, for the Hindi/mixed-language
  OCR support required by the spec

Verified working in this increment: English OCR tested end-to-end against
a real generated image (94%+ confidence). Hindi OCR language data installs
correctly but could not be verified end-to-end in the sandbox this was
built in — no Devanagari-script font was available to render a real test
image. Recommend a quick verification pass with a real Hindi document/image
before relying on it in production.

## Not required by anything implemented so far, but will be needed if/when
## the deferred formats are wired up:

- `libreoffice` (headless) — for legacy `.doc` extraction (convert to
  `.docx` first, then reuse the existing DOCX extractor)
- ClamAV (`clamav-daemon`) — already required for the Upload Service's
  virus scanning; see the Docker increment for a ready-to-run service
  definition once that's built
