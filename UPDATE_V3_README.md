# ClaimsFlow v3 - saved claim details and version history

## New workflow
1. Process a claim in Manual or AI-Assisted mode and submit the human routing decision.
2. In Claims Inbox, select **View claim** on a completed claim. The same review form opens with **the exact fields submitted** and links to supporting PDFs. It is read-only by default.
3. Select **Edit claim** to unlock fields and the routing decision. Explain the correction in the rationale field and select **Save new version**.
4. Use **Version history** to open any previous submission. Earlier versions are not overwritten.
5. Edits are recorded as revisions, and are **excluded from manual-versus-AI processing time averages**.

Saved records are stored locally in `backend/data/workbench.json`; uploaded evidence is in `backend/uploads/`. Keep both folders if migrating data from an earlier install. The `.env` API key is not included.

## Run on Mac
Backend (Terminal 1):
```
cd ~/Desktop/ClaimsFlow_Workbench/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
set -a; source .env; set +a
python -m uvicorn app:app --reload
```
Frontend (Terminal 2):
```
cd ~/Desktop/ClaimsFlow_Workbench
npm install
npm run dev
```

## Important when upgrading from v2
Stop both servers, unzip v3 to a **new folder**, then copy `backend/.env` from v2. To preserve prior submitted claims and uploaded evidence, also copy `backend/data/workbench.json` (if present) and `backend/uploads/` (if present) into the v3 backend. Do not overwrite the v3 `backend/data/reference_answers.json`.

## Verification
Backend tests: 26 passing, including a test confirming revisions retain prior snapshots. Frontend JSX/browser build not verified in this environment; run `npm install && npm run build` locally. No production authentication or privacy protections are implemented; use synthetic data only.
