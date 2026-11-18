# ClaimsFlow v12.1

ClaimsFlow compares human-only and AI-assisted handling of synthetic insurance claims. It records the reviewer’s final routing decision and gives administrators a way to run batch evaluations using the Gemini API.

This repository includes the v12.1 Mac app and the hosted guest app in [public-demo](public-demo/README.md). The hosted app uses the same source as its published build. It keeps guest records in the browser and supports live Gemini for the supplied synthetic claims.

## Install or upgrade on the Mac mini

1. Connect the host Mac to ZeroTier. Install Python 3.11 or later and Node.js 22 LTS with npm if needed. The installer needs internet access to download dependencies.
2. Clone this repository or unzip the v12.1 installer. In that folder, open `INSTALL_ClaimsFlow_v12.1.command` to install for local use. For ZeroTier access, run `bash INSTALL_ClaimsFlow_v12.1.command --host YOUR_PRIVATE_IPV4`. The installer prints the address and creates an **Open ClaimsFlow** shortcut.
3. The installer builds and tests v12.1, stops the previous ClaimsFlow service, and copies data and accounts from the latest earlier installation. Keep the previous release in place for rollback. To select a different source, pass `--previous "/path/to/the/previous/release"`.
4. When the health check passes, the installer opens ClaimsFlow. Sign in with your existing account. For a fresh install, open **Applications → ClaimsFlow v12.1 → Recover Admin Password.command** on the host Mac to create the first administrator. The same Applications folder contains the installed shortcut for opening the app.

The service runs while the installing macOS user is logged in. Keep the Mac awake and connected to ZeroTier for remote access. The installer can be run without sudo.

## Review claims

1. Open **Claims Inbox** and choose a synthetic claim. **Start human-only review** opens a blank form for manual entry. **Start AI-assisted review** opens the same evidence and lets you run Gemini to suggest details and a route.
2. Open the evidence PDFs. In AI-assisted mode, select **Run Gemini analysis** and check the highlighted form values against the evidence. When you edit an extracted field, its original Gemini value stays visible below it, including when you reopen the saved review. Fill any gaps directly from the PDFs. The review timer starts when you open the claim. Pause it if you need to step away.
3. Choose the final queue and submit the decision. Add a rationale when you override a suggested route. ClaimsFlow returns you to the inbox. Open **History** to see saved reviews, corrections and downloadable PDF reports.
4. To compare methods, use similar claims and vary which method you try first. You can also review a claim both ways. Familiarity with the evidence may affect the time you record.

Administrators and analysts can add synthetic claims in **Administration**. Upload 1–8 text-based PDFs per claim, up to 8 MB per PDF, or use a ZIP with one folder per claim. Bulk import accepts up to 100 claims and 100 MB compressed. An optional `manifest.csv` can specify `folder,title`.

## Gemini API and evaluation

Under **Administration → Gemini API connection**, an administrator can save a Google Gemini API key in the host Mac’s login Keychain and select **Test Gemini Connection**. The server uses that key to authenticate requests for AI-assisted reviews and batch evaluations. Both send synthetic claim details and any available attached PDFs to Google Gemini for extraction and routing. Use synthetic data only.

Open **AI Prototype Testing**, select claims, and choose **Run Gemini evaluation**. Results show how many claims received a Gemini response and how many used local rules. A missing key or failed Gemini request produces a clearly labelled local rules fallback. These results are excluded from the successful Gemini totals.

The human simulation is a local, assumption-based estimate. Measured human-only results come from saved reviews. The AI estimate combines measured API time with assumed verification time and uses the configured cost allowance. Blank accuracy figures indicate that the evaluation did not calculate those measurements.

## Remote access

For browser access, authorise the remote device on ZeroTier and share the host’s private ClaimsFlow URL. In **Administration → Account settings**, create an **Analyst** account for the remote user or reset an existing account password. The analyst can review claims and run evaluations. Account administration, saving the Gemini key and demo reset require an administrator.

For remote development, create a separate standard macOS account and a working copy under that account’s home directory. In **System Settings → General → Sharing → Remote Login**, allow only the intended macOS users. Use the remote user’s own credentials with VS Code Remote SSH over ZeroTier and confirm the SSH host fingerprint with the host administrator. Keep SSH and ClaimsFlow on the private network.

Build and test in the separate working copy:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-lock.txt
npm ci
npm run build
cd backend
CLAIMSFLOW_DATA_DIR="$(mktemp -d)" .venv/bin/python -m pytest -q
```

To run an isolated development instance from `backend`, prepare a dedicated data directory and accounts database. Local recovery opens on the host Mac. After creating an account, start the app and forward port 8877 through VS Code.

```bash
export CLAIMSFLOW_DATA_DIR="$HOME/Library/Application Support/ClaimsFlow-Dev/data"
export CLAIMSFLOW_ACCOUNTS_DB="$HOME/Library/Application Support/ClaimsFlow-Dev/accounts.sqlite3"
mkdir -p "$CLAIMSFLOW_DATA_DIR"
.venv/bin/python local_recovery.py
CLAIMSFLOW_AUTH_MODE=sessions .venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8877 --no-proxy-headers
```

Keep the development and installed data directories separate. Promote tested changes through a versioned installer.

## Verify, back up and recover

- After upgrading, confirm **Version 12.1** appears in Claims Inbox and `/ready` reports version `12.1` with a nonempty instance value. Verify existing accounts, claims, PDFs and reviews from the host and a remote device. Test Gemini with a synthetic claim.
- The release directory is `~/Library/Application Support/ClaimsFlow-v12.1`. It contains `data`, `accounts.sqlite3`, `server.log` and `server-error.log`. Make a private backup of `data` and `accounts.sqlite3` while the service is stopped, or use a consistent SQLite snapshot for a running database. Backup files do not include the Keychain key. The installer does not schedule backups.
- A failed upgrade is retained as `ClaimsFlow-v12.1.failed-<id>`. Check its logs. The installer attempts to restart the previous service if startup fails. Rerunning the installer opens a healthy v12.1 installation. An existing unhealthy v12.1 folder is retained for diagnosis.
- To roll back a successful upgrade to v12.0, unload the v12.1 service and disable its launch file before enabling the v12.0 service. Use the actual previous version if it differs. Reviews saved in v12.1 remain in its data directory.

```bash
agents="$HOME/Library/LaunchAgents"
domain="gui/$(id -u)"
launchctl bootout "$domain" "$agents/uk.claimsflow.v12.1.plist"
mv "$agents/uk.claimsflow.v12.1.plist" "$agents/uk.claimsflow.v12.1.plist.disabled"
mv "$agents/uk.claimsflow.v12.0.plist.disabled" "$agents/uk.claimsflow.v12.0.plist"
launchctl bootstrap "$domain" "$agents/uk.claimsflow.v12.0.plist"
```
