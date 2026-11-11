# Claims Operations Workbench — first working redesign

This prototype reuses the original FNOL FastAPI and Gemini extraction/routing. It adds a separate workbench API and a new React frontend. Existing `/process-fnol`, `/claims`, and `/llm-status` endpoints remain intact.

## On your Mac

1. Back up your original project. Unzip this archive into a new folder; do not overwrite your original without a backup.
2. Copy your existing `backend/.env` into the new project's `backend/` directory. **Do not share the .env file.**
3. Backend terminal: `cd backend && source .venv/bin/activate && python -m uvicorn app:app --reload`. If the new folder has no `.venv`, create one with `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
4. Frontend terminal, from project root: `npm install && npm run dev`.
5. Open http://localhost:5173.

## What's implemented

- Six synthetic incoming claims backed by included PDF files.
- Manual FNOL data entry with a pause/resume timer and final human routing decision; **manual mode never invokes Gemini**.
- AI-assisted mode with an explicit **Process with Gemini API** button, editable extracted fields, routing suggestion, fallback visibility and mandatory human approval.
- Persisted timing attempts, API-processing duration, AI overrides, field correction counts and specialist referrals.
- Dashboard of observed manual and AI-assisted timings. Reset button clears workbench attempts, not legacy claims.
- Existing Gemini integration and rules fallback preserved.

## Limitations / next phase

- Each sample case currently contains one PDF; the backend case schema and evidence aggregation support multiple PDFs per case, but the inbox does not yet include a document upload/grouping UI.
- Accuracy and fairness **are not measured yet**; this requires labelled reference answers and controlled tests.
- Timer is a browser active-session timer and can be paused; do not treat it as tamper-proof operational telemetry.
- Results are descriptive, not a controlled experiment; repeat handling can introduce familiarity bias.
- No login, production privacy controls, real specialist assignment or claims settlement decisions. **Synthetic data only.**
- AI processing time includes extraction and routing plus local PDF processing. Total AI-assisted time includes API processing and handler review.
- The project remains a prototype; review Gemini outputs and confirm the model is available in your account.
