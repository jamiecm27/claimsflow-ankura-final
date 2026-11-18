#!/bin/bash
set -euo pipefail
RECOVERY="$HOME/Library/Application Support/ClaimsFlow-v12.1/RECOVER_ADMIN_PASSWORD.command"
if [ ! -f "$RECOVERY" ]; then
  osascript -e 'display alert "ClaimsFlow v12.1 is not installed" message "Install ClaimsFlow v12.1 on this Mac mini first."' || true
  exit 1
fi
exec /bin/bash "$RECOVERY"
