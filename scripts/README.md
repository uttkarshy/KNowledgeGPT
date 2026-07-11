# Scripts

## `smoke_test.py`

Real end-to-end deployment verification: registers a user, creates a
knowledge base, uploads a document, waits for it to finish processing,
asks a grounded question (expects a real cited answer), and asks an
ungrounded question (expects a refusal, not a hallucination).

```bash
pip install httpx
python scripts/smoke_test.py --base-url https://your-deployed-api.example.com
```

Requires a real, working `OPENAI_API_KEY` on the target environment —
this makes real embedding and chat completion calls. Creates a throwaway
test user/knowledge base/document on whatever environment you point it
at; don't run it against production without expecting that side effect.

Every request payload and response field this script reads was
cross-validated against the live OpenAPI schema (`docs/openapi.json`)
during development — see `docs/README.md` for what that means and what it
doesn't cover (it confirms the shapes match; it does not confirm the
pipeline actually runs, since no live server was available to run this
against while building it).
