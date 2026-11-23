# Service deployment and deletion operations

This branch contains additive FastAPI endpoints and public Next.js pages. Production showed features from the recovery line. Identify the running image revision, Alembic head and provider configuration using the operator’s existing deployment records before promoting any changes. Build and review a merge against that verified revision in staging. Deploying the older main backend could discard newer capabilities or conflict with its schema.

## Configuration and staged verification

1. Set SUPPORT_INBOX to an existing monitored UtkarshLabs mailbox in the secret manager. Reuse the service’s SMTP host, port, TLS, sender and authentication settings. The endpoint returns 503 on absent configuration or rejection. A 202 acknowledges delivery to the mail system.
2. Verify a disposable account can send a support request, report one of its assistant messages and submit deletion from both the app and the public web form. Check that the mailbox actually received each reference. Keep reviewer accounts and private documents out of screenshots.
3. Confirm GET /privacy, /terms and /delete-account work publicly via HTTPS on the final host. Configure the existing web client’s API origin to that host at build time. Reconcile the public warning about retention with the operator’s actual retention schedule.
4. Rehearse the full upload, estimate, consent, worker, retrieval, refund/error and history lifecycle against the deployed revision. Log counts and outcomes, never bearer tokens, signed upload URLs, email links or document content.
5. Reviewing a report requires verifying its answer identifier in the owning tenant. Record the moderation decision, resolve dangerous content and communicate with the reporter using the account’s verified address when needed.

## Fulfill an account deletion request

The intake endpoint deliberately requires operator verification. Anyone can enter an address on the public page. Receiving the request is insufficient evidence of mailbox control.

1. Send a single-use verification challenge to the address already associated with the account. Avoid revealing whether another person has an account. Confirm the request and ownership before any destructive action.
2. Suspend further use, revoke refresh sessions and stop outstanding ingestion jobs for this account. Allow already-issued upload signatures to expire before the final storage sweep.
3. Enumerate only the verified owner’s temporary objects, staged uploads and any versions retained by the actual storage provider. Purge them. Verify completion with storage metadata. Record and retry failed removals.
4. Apply the service’s authenticated administrator deletion operation. Verify that owned bases, documents, chunks/embeddings, chats, messages, citations and refresh tokens are gone. Check related usage/credit records against the actual deployed migrations. Certain audit logs use SET NULL rather than CASCADE.
5. Check support mail, backups and required security/financial records. Minimize identifying information and document any specific lawful retention and expiry. Communicate the result and applicable retention periods. Operator must approve the retention notice before release.

Deleting one document can leave contributions in previously generated answer text. Include history in account erasure. Local logout and uninstall remove access on a device and have separate effects from an operator-confirmed account deletion.
