# ClaimsFlow: independent evaluation and simulated human baseline

- Performance evaluates any selected claims, including bulk-imported claims; imported cases without a benchmark are not given accuracy scores.
- Optional simulated human-only baseline uses explicit configurable assumptions (base minutes, per-document minutes, assessment minutes, field error rate, routing error rate and hourly staff cost). It is deterministic, does not use Gemini, does not create human decisions and must not be described as observed staff performance.
- Gemini extraction and routing are measured through live API calls. A full comparison of human and AI end-to-end processing requires real human review measurements; the simulation is illustrative only.
- Removed name-based fairness probing and its additional API calls.
- The evaluation selector does not change operational claim status.
- Admin contains the human simulation settings.
- Keep backend/.env private and out of GitHub. Do not upload real claimant data.
