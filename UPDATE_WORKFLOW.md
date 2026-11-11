# ClaimsFlow workflow update

Three sections: Claims Inbox, Performance & Business Value, Administration.

- Inbox retains independent human-only and AI-assisted review actions for every claim. A completed review does not prevent the other method from being tested. Search by claim ID/title; see separate completion counts and latest human-approved route.
- Claim review explains the five route definitions.
- Performance page shows a prominent Run AI Evaluation button with test details alongside. Detailed evaluation shows expected test benchmark route, Gemini route, and match status separately.
- Administration offers single claim upload, ZIP bulk import (1-100 fictional claims), and demo reset. Specialist referral remains a routing outcome, not a separate worklist.

## Bulk ZIP format

One folder per claim, with 1-8 text-based PDF documents per folder. Optional root-level `manifest.csv` has headers `folder,title`, with one row per claim folder. ZIP must be <=100 MB compressed, <=150 MB uncompressed. PDF max 8 MB each. Only synthetic evidence.

## Paired testing and interpretation

Complete a human-only review and an AI-assisted review for each test claim. For a controlled comparison, complete the manual review before viewing Gemini's suggestions, or use separate blinded reviewers; repeated exposure can bias timing and decisions. The Performance page separates measured human review attempts from automated Gemini benchmark results. Reference scoring is only available for the six bundled claims; newly imported claims need independent reference answers to measure accuracy.

## Running

From root: `npm install && npm run dev`. From backend: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python -m uvicorn app:app --reload --port 8000`. Configure `backend/.env` locally with `GEMINI_API_KEY=...`. Never commit or share that file.
