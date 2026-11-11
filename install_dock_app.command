#!/bin/bash
set -e
cd "$(dirname "$0")"
APP="$HOME/Applications/ClaimsFlow.app"
mkdir -p "$HOME/Applications"
LAUNCHER="$PWD/start_claimsflow.command"
# AppleScript app launches the real start script in Terminal.
export CLAIMSFLOW_LAUNCHER="$LAUNCHER"
SCRIPT=$(mktemp /tmp/claimsflow_dock.XXXXXX.applescript)
cat > "$SCRIPT" <<'APPLESCRIPT'
on run
    set launcherPath to system attribute "CLAIMSFLOW_LAUNCHER"
    tell application "Terminal"
        activate
        do script "bash " & quoted form of launcherPath
    end tell
end run
APPLESCRIPT
# Embed an absolute path; environment variables are not inherited by the dock app.
python3 - "$SCRIPT" "$LAUNCHER" <<'PYAPP'
import sys
from pathlib import Path
f=Path(sys.argv[1]); p=sys.argv[2].replace(chr(92), chr(92)*2).replace(chr(34), chr(92)+chr(34))
s=f.read_text().replace('system attribute "CLAIMSFLOW_LAUNCHER"', '"'+p+'"')
f.write_text(s)
PYAPP
rm -rf "$APP"
osacompile -o "$APP" "$SCRIPT"
rm -f "$SCRIPT"
echo "Created $APP"
open -R "$APP"
echo "Drag ClaimsFlow.app from Finder into your Dock."
read -r -p "Press Return to close..." _
