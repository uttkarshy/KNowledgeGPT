# User Guide

## Getting started

1. **Create an account** at `/register`. You'll get a verification email
   (check your inbox, or in a local dev setup without SMTP configured,
   check the backend logs, which print the verification link instead of
   emailing it).
2. **Sign in** at `/login`.
3. You'll land on the **Dashboard**.

## Knowledge bases

A knowledge base is a private collection of documents. Click "New
knowledge base", give it a name and (optionally) a description and
color, and create it.

From a knowledge base's card, click it to open the Documents panel:

- **Upload a document** — supports PDF, DOCX, PPTX, XLSX, CSV, TXT,
  Markdown, HTML, JSON, and images (scanned pages and photos are OCR'd
  automatically, including mixed English/Hindi text). Watch its status
  move through Queued, Scanning, Extracting, Chunking, Generating
  embeddings, Ready. If something goes wrong, the failure reason is
  shown directly.
- Once a document shows Ready, it's searchable in chat.

## Chatting with your documents

Click "Chat with this knowledge base" (or navigate to Chat with a
knowledge base selected). Ask a question in plain language.

- The assistant answers only from your uploaded documents — if it
  can't find the answer in what you've uploaded, it says so rather than
  guessing.
- Every answer includes numbered citations ([1], [2], ...). Click
  one to jump to the matching source card in the right-hand panel, which
  shows the document name, page/section, a relevance indicator, and the
  exact excerpt the answer drew from.
- Conversations are saved per knowledge base; use "New chat" to start a
  fresh thread.

## Admin (if your account has the Admin role)

Navigate to `/admin` to see:
- System-wide stats (users, knowledge bases, documents, storage, API activity)
- A searchable user list, with the ability to suspend, unsuspend, or permanently delete an account
- A recent-errors table for spotting problems quickly

## Tips

- If a document upload fails, the reason is shown in the Documents panel
  — common causes are an unsupported file type or the file failing a
  virus scan.
- If chat says it can't find something you're sure you uploaded, check
  the document actually reached Ready status — it isn't searchable
  until it has.
