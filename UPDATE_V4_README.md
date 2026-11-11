# v4 Automated Evaluation

Start backend and frontend using the same commands as v3. The Impact & evaluation tab now includes **Run evaluation**. It sends six seeded synthetic cases through Gemini and persists the result in `backend/data/workbench.json` under `evaluationRuns`. It does not change case status or create human-approved attempts. Name-sensitivity probes are optional and increase Gemini API calls.

The results separate successful Gemini extraction+route responses from regex/rules fallbacks. Raw field accuracy uses exact normalized text matching against provisional synthetic references, so formatting differences can count as wrong. Manual minutes, verification minutes, staff cost and API cost are illustrative assumptions, not measured savings. Name changes are narrow robustness probes, not proof of fairness. Gemini API calls require a valid key and may incur costs.

To preserve existing v3 data, copy `backend/data/workbench.json` and `backend/uploads/` from v3 into v4 before running. Copy your own `backend/.env` as well; no API key is included.
