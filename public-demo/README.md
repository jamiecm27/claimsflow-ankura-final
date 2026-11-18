# ClaimsFlow public demo

Open the sign-in page and choose **Guest entry**. The guest session uses the Analyst workspace with Claims Inbox, AI Prototype Testing and Administration tools for synthetic claims and simulation settings.

Hosted live Gemini sends the six supplied synthetic claims to Google and measures API request time. Uploaded PDFs remain available for manual review in the browser. Sample mode is labelled and uses illustrative timings when the hosted connection is unavailable. Reviews and uploaded synthetic PDFs are stored in the visitor’s browser for the session. The demo runs independently of the installed ClaimsFlow service.

## Run the source locally

```bash
npm ci
npm run dev
```

Open the URL printed by Vite. `npm run build` builds the site and the deployment Worker in `dist/`.

## Hosted Gemini

In ChatGPT Sites settings, add `GEMINI_API_KEY` as a secret and publish the saved version to apply it. `GEMINI_MODEL` can select a Gemini model. The default is `gemini-3.8-flash`. The `GEMINI_DAILY_LIMIT` environment variable sets the maximum number of provider calls per UTC day, with a default of 48. Apply the D1 migration in `drizzle/` as part of deployment.
