# Android release evidence

23 November 2026. Package `com.utkarshlabs.knowledgegpt`, version 1.0.0 (1).

| Check | Result | Boundary of the result |
|---|---|---|
| Mobile TypeScript and six Node tests | Passed | Type checking, SSE and client protocol coverage. |
| Main-based backend unit suite | 15 passed | In-process service code. |
| Recovery branch suite | 258 passed, 10 skipped | Separate recovery tree, not evidence that this older main-based backend can replace the production image. |
| Two-user FastAPI acceptance | Passed with isolated services | Real PostgreSQL/pgvector, Redis, PDF extraction, signed PUT against a Moto HTTP S3 server and stored citations. Queue delivery, external model, embeddings and SMTP substituted. |
| Production connectivity | Public GET/unauthenticated checks only | Website and auth pages responded. Protected routes required authentication. See SOURCE_AUDIT.md for public pages returning 404. |
| Android compilation | Debug and bundled release-mode preview built | ARM64 and x86_64. The disposable debug certificate is for installation tests. |
| Installed device test | Passed on Android 13 API 33 x86_64 emulator | Standalone preview started, displayed welcome, login and registration, accepted keyboard input, handled Back and cold restart. |
| Website production build | Passed | Next.js builds and typechecks the public policy and deletion pages locally. |
| Production-signed AAB and Play delivery | Pending | Requires an authenticated existing EAS project and the correct upload credential. |

## PDF, citation and login regression

The disposable acceptance harness creates two password accounts, signs in, creates a base, uploads a generated PDF, confirms and processes it, retrieves indexed text and streams an answer. It checks the citation page, persisted answer and tenant isolation. It exercises refresh, logout, revoked refresh rejection, login again and reopening history. Support and deletion request receipts use a captured mail delivery. The deletion receipt is an intake check. Operator verification and erasure require a separate rehearsal. Read the harness before running: it is for disposable test resources only.

[Acceptance harness](../../backend/tests/mobile_flow/run.py) · [Service tests](../../backend/tests)

## Install and CI evidence

| File | Bytes | SHA-256 |
|---|---:|---|
| KnowledgeGPT-preview.apk | 54,129,544 | `0ed6f8f12e28e11cd606f1d4f733fa2a36b665c9f00b5d959e5fb585fed5eea6` |
| KnowledgeGPT-debug.apk | 88,635,092 | `c5353cfa97cd79525258520bce0c56036f21ffe02e6468233cde1db6c8927484` |

The standalone preview includes its JS bundle. The debug APK uses Metro. The first CI job completed compilation, signature and alignment verification, then its UI driver selected the email label instead of the editable field. The second run downloaded the same APK and verified its UI after correcting the selector. The three screenshots are captures from this installed APK. CI downloads have a retention window.

[Build and checksums](https://github.com/uttkarshy/KNowledgeGPT/actions/runs/45145573270) · [Passing Android 13 rerun](https://github.com/uttkarshy/KNowledgeGPT/actions/runs/45147990267) · [Device screenshots](play/screenshots)

## Still to verify before release

- The full authenticated flow on an Android phone against a release-matched staging service, including the system file picker, provider-backed citations, reopened chat after process death, expired-session rotation, slow and offline uploads, and cancellation during generation. The installed emulator and backend tests cover different parts of this journey.
- Public policy and deletion URLs, actual email delivery, moderator response and erasure completion including storage, audit records and backups.
- Release-bundle manifest, upload certificate, 16 KB compatibility and a Play-delivered install. Run on a physical ARM64 phone and on a 16 KB page-size Android system.
- Confirm provider configurations, tenant policy, dependency remediation and billing behavior on the deployed backend before making the final Play declarations.
