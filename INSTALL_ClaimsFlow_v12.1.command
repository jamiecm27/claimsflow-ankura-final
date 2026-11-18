#!/bin/bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
ROOT="$(cd "$(dirname "$0")" && pwd)"
command -v python3 >/dev/null || { echo 'Install Python 3.11 or newer first.'; exit 1; }
python3 "$ROOT/mac/install.py" "$@"
