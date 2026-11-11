# ClaimsFlow v4: business-language evaluation page

The former Impact & evaluation page is now Performance & business value. It separates automated Gemini results from completed human-review measurements, moves case-level and fairness diagnostics into expandable details, and labels financial calculations as illustrative assumptions. No backend evaluation rules or existing records were changed.

To use: install dependencies with `npm install` and `pip install -r backend/requirements.txt`, configure `backend/.env` locally, start backend with `python -m uvicorn app:app --reload --port 8000` from `backend`, and frontend with `npm run dev` from the project root. Do not commit API keys.
