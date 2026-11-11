# ClaimsFlow — consolidated comparison update

- Performance claim selection is now a one-row-per-claim list with search, multi-select, and Select All.
- Three compact scenarios: AI, Simulated Human, Manual Human.
- A common metrics table covers claim count, time, cost, field accuracy, routing agreement, and total processing cost.
- Two comparisons: AI vs Simulated Human and AI vs Manual Human. The latter only uses claim IDs with both a successful AI evaluation and a submitted manual review.
- Manual metrics remain blank until reviews have been submitted.
- Business value is projected from the same per-claim cost figures as the comparison, rather than an independent benefit calculation.
- AI labels replace Gemini in the user-facing workflow; backend still uses Gemini API.
- Administration has estimated AI checking time and API allowance alongside the human simulation assumptions.
- AI processing time is measured; checking time and cost are estimates. Simulated human results are modelled, not observed. Manual review time is recorded by the workbench timer.

## Launch

Copy the working `backend/.env` from the previous version. Set up backend and frontend as in START_HERE.md. No real claimant data should be used.

## Verification status

Frontend build could not be completed in the build environment because npm dependency installation timed out. Please run `npm install` and `npm run build` locally before relying on this release. Backend Gemini API has not been re-tested for this UI-only change.
