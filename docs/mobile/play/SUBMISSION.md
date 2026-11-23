# KnowledgeGPT Google Play submission draft

Prepared 23 November 2026. Use the existing UtkarshLabs developer account. This package is for owner review. The release is on hold.

## English store listing

**App title** — KnowledgeGPT  
**Developer** — UtkarshLabs  
**Suggested category** — Productivity  
**Short description** — Ask questions about your documents and follow citations back to the source.

**Full description**

Build a knowledge base from your own documents and ask questions about what they contain. KnowledgeGPT connects to your KnowledgeGPT account so you can pick up a saved conversation on Android.

Choose a PDF, Word document or text file, follow its processing status, then open a chat in the same knowledge base. When the service returns citations, expand them to read the supporting passages and check the answer against the source. Copy an answer or reopen the conversation later.

Organize your documents by knowledge base and remove files you no longer need. Account settings include theme controls, support and account deletion requests. Document limits, processing estimates and available credits depend on your account and service configuration. AI responses can contain mistakes. Review the cited text before relying on an answer.

**Website** — https://knowledgegpt.utkarshlabs.com  
**Support email** — Owner must supply and verify the monitored public address before entering it into Play Console.  
**Privacy policy** — https://knowledgegpt.utkarshlabs.com/privacy  
**Terms** — https://knowledgegpt.utkarshlabs.com/terms  
**Public deletion request** — https://knowledgegpt.utkarshlabs.com/delete-account

All three legal/deletion URLs returned 404 in the production check. Their candidate implementations are on this branch. Publish only after the owner approves the production-matched changes and the URLs work without login.

## Listing assets

| Asset | File |
|---|---|
| Store icon, 512 × 512 PNG | [Icon](../../../mobile/play/icon-512.png) |
| Feature graphic, 1024 × 500 PNG | [Feature graphic](../../../mobile/play/feature-1024x500.png) |
| Real 1080 × 2340 phone screenshots | [Welcome](screenshots/01-welcome.png), [Sign in](screenshots/02-sign-in.png), [Registration](screenshots/03-registration.png) |

The current screenshots show the public screens. Supplement them with a real knowledge base and a cited answer from a synthetic reviewer document once staged. Keep private files and personal account details out of store media.

## Data Safety worksheet

This is a draft for the app as shipped, its backend and integrated service providers. Verify operator configurations and provider terms before selecting final Console answers. Mark transmitted, persisted data as collected. An optional feature still counts as collection when used.

| Play data type to evaluate | Behavior / purpose | Required or optional |
|---|---|---|
| Email address, user IDs | Account, authentication, security, support and erasure. IDs link documents and conversations to their owner. | Required for authenticated workspace |
| Name | User can provide a profile name during registration. | Optional |
| Files and docs; other user-generated content | Selected files, extracted text/chunks, embeddings, questions, generated replies, source excerpts and references are processed and stored for document chat. | Optional, required for that feature |
| Other in-app messages / support | Reports, support reasons, message identifiers, deletion requests and replies go to the operator via SMTP. Assess all applicable Console message categories. | Optional |
| App interactions / diagnostics | Service source records API usage, security and audit events. Check IP, agent, infrastructure logs, linkage, retention and downstream telemetry in the deployed stack. | As configured |
| Purchase history | Recovery tracks credit ledger and consumption. No checkout in this Android client. Verify whether synced purchase history is processed for app users and whether digital credits require Play Billing in the chosen markets. | Operator review |

Identify every processor, including hosting, storage, configured embedding/chat providers and mail. Confirm processor-only use, retention, whether model inputs may be used for independent purposes and applicable Play exceptions before selecting “shared”. Confirm HTTPS across all production data transfers and the behavior of any additional SDK. No advertising SDK, ad identifier request, camera, microphone, contacts, location or broad media-storage permission was identified in the Android source. Record the actual support address, retention periods, deletion treatment and any lawful exceptions in the public policy. Complete the Console encryption and deletion answers after operator verification.

## App access and review

Provide a dedicated, pre-verified, reusable password account in the private App access section of Play Console. Set a funded or otherwise authorized reviewer allocation, ensure it stays valid throughout review, and provide credentials there only. The owner must supply the real credentials and test the account externally. Avoid time-dependent OTPs and personal data. Include a synthetic indexed PDF and a saved conversation with a page citation.

**Reviewer instructions to paste after staging:** Open KnowledgeGPT and select Sign in. Use the email and password provided in the private fields. Open the prepared review knowledge base, select its saved conversation, then expand a source below the answer to inspect its citation. Open the document details to see its processing status. In an answer, select Report answer to see the report form. Open Account and settings for the privacy policy and Request account deletion. Use a separate disposable account for an erasure test to preserve the shared reviewer login.

Run the steps with the actual names of the staged base, sample PDF and question, and insert those names before submission. Confirm access from outside the developer network.

## Ratings, permissions and distribution

- Complete IARC for a productivity app with AI-generated text, account sign-in, private uploads and private document chat. Answer content, user interaction, purchases and access questions from the actual release behavior and intended audience. IARC assigns the rating. The owner must select countries and intended age groups. A children-directed distribution requires a separate Families assessment.
- Select the appropriate AI-content declaration. Validate prevention of restricted output and the in-app Report answer action with a real monitored inbox and moderation process. Review any new listing-asset disclosure shown in Console.
- The inspected preview manifest includes INTERNET, ACCESS_NETWORK_STATE, VIBRATE, USE_BIOMETRIC, USE_FINGERPRINT and a package-scoped receiver permission. SecureStore contributes biometric declarations; app code does not ask for fingerprint or face enrollment. Upload uses Android’s picker. Compare against the production bundle and complete only applicable permissions declarations.
- The preview targets Android 16 API 36. Confirm version code availability, signing certificate, Play App Signing enrollment, package registration status and 16 KB native compatibility for the AAB and generated splits.
- If the existing personal developer account falls under the closed-testing requirement, arrange at least 12 continuously opted-in testers for 14 days before applying for production access. Check this app’s Console status for eligibility. No track upload or submission has been made.
- Resolve open issues in the [test results](../testing.md), [security audit](../SECURITY.md) and [operator guide](../operator.md). The release owner must approve the merge, deployment and release independently.

## Google references

[Store listing assets](https://support.google.com/googleplay/android-developer/answer/9866151) · [Data Safety](https://support.google.com/googleplay/android-developer/answer/10787469) · [Account deletion](https://support.google.com/googleplay/android-developer/answer/13327111) · [App access](https://support.google.com/googleplay/android-developer/answer/9859455) · [Generative AI](https://support.google.com/googleplay/android-developer/answer/13985936) · [Target API](https://support.google.com/googleplay/android-developer/answer/11926878) · [16 KB guidance](https://developer.android.com/guide/practices/page-sizes) · [Closed testing](https://support.google.com/googleplay/android-developer/answer/14151465)
