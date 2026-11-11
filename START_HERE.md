# ClaimsFlow — Claims Operations Workbench (assessment build)

This is a standalone React + FastAPI prototype built on the original extraction/routing project. **All included claim data is synthetic.** Do not use real customer documents. The prototype is not a production claims management system.

## 1. Install and start (Mac)

Unzip this archive into a separate folder on your Desktop, e.g. `ClaimsFlow_Workbench`. Do **not** overwrite the original project. In Terminal 1:

```bash
cd ~/Desktop/ClaimsFlow_Workbench/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
nano .env
```

Enter your Gemini key in the new `.env` file (do not share it):

```
GEMINI_API_KEY=YOUR_KEY
```

Save with Control+O, Return, Control+X. Then:

```bash
set -a
source .env
set +a
python -m uvicorn app:app --reload
```

Terminal 2:

```bash
cd ~/Desktop/ClaimsFlow_Workbench
npm install
npm run dev
```

Open `http://localhost:5173`. API documentation: `http://127.0.0.1:8000/docs`.

## 2. Demonstrate

1. **Claims inbox:** Six synthetic claims are preloaded; each has an intake PDF plus a supporting evidence PDF. Alternatively, create a fictional claim using 1–8 text-based PDFs (max 8 MB each). You can attach more PDFs to an existing claim while reviewing.
2. **Manual review:** Open a claim in manual mode, read both PDFs, fill fields and select a final queue. The timer starts on opening; submit the human decision.
3. **AI-assisted review:** Open the same or a comparable claim in AI mode; press **Process with Gemini API**. Gemini receives extracted text from **all documents associated with that claim**. Check and correct every field, then approve or override the suggested route. An override reason is mandatory.
4. **Claim history:** Select **History** in the inbox to inspect previously submitted human decisions and timings. They persist in `backend/data/workbench.json` between server restarts.
5. **Impact & evaluation:** Compare recorded elapsed time, human-submitted field accuracy, routing agreement and illustrative labour/API cost. Change hourly cost, API cost and monthly volume assumptions.
6. **Specialist worklist:** A claim appears only when the handler's final decision is `Specialist Queue`.

## 3. What is measured and what is assumed

- **Time:** Wall-clock active timer from opening a claim to submitting a human decision; user may pause/resume. AI time includes waiting for the API and human verification. This is a small uncontrolled demonstration; repeated claims create familiarity bias.
- **Quality:** Six preloaded cases have **provisional synthetic reference answers** in `backend/data/reference_answers.json`. The system compares submitted fields using normalized exact text matches and checks whether the final route agrees with an expected synthetic queue. This scoring is strict (equivalent wording may score incorrectly), reference answers are partly derived from rule extraction, and it **does not measure raw AI extraction accuracy**. New user-uploaded claims remain **unscored** without a reference answer.
- **Cost:** Editable hourly labour rate and estimated API charge per AI claim. The model excludes integration, governance, setup, licensing, rework, infrastructure, and the economic effects of errors. Capacity released is not necessarily cash saved.
- **Reliability:** Gemini failures use the existing regex/rules fallback. The interface labels whether extraction used Gemini or fallback; a fallback result is not evidence of AI success.
- **Privacy/fairness:** The app is **synthetic-only** and has no login, access control, encryption-at-rest, retention automation, production privacy assurance, or comprehensive fairness testing. Uploaded PDF text is transmitted to Gemini when the button is clicked. Do not upload real personal data. One automated counterfactual test confirms that changing a fictional claimant name does not change the deterministic rules-based route. This does NOT establish Gemini fairness; that would need controlled counterfactual cases and expert review.
- **Specialist routing:** AI proposes; the human makes the final routing decision. No claim payment, fraud finding or coverage decision is automated.

## 4. Tests

Run from the project root:

```bash
python -m pytest -q backend/tests
```

Additional endpoint smoke tests can be run with FastAPI's TestClient. The sample evidence PDFs are generated from fictional supporting notes and are explicitly marked synthetic.

## 5. Files

- `src/App.jsx`, `src/App.css`: redesigned handler workflow and evaluation page.
- `backend/workbench.py`: multi-document case API, Gemini processing, persistent decisions, audit history, reference scoring.
- `backend/sample-docs`: six intake PDFs and six synthetic supporting evidence PDFs.
- `backend/data/reference_answers.json`: editable provisional reference answers.
- `backend/data/workbench.json`: created at runtime; local persistent synthetic claims and attempts.
- `backend/uploads`: created when new PDFs are uploaded. Keep this folder private and out of source control.

**Reset demo** clears the indexed claims and attempt log, but does not delete previously uploaded PDFs from disk. Delete `backend/uploads` manually to remove orphaned test files. This is a prototype limitation.
