#!/bin/bash
set -euo pipefail

config="$HOME/Library/Application Support/ClaimsFlow-v12.1/install.json"
if [[ ! -f "$config" ]]; then
  echo 'Install ClaimsFlow v12.1 before opening it.' >&2
  exit 1
fi
host=$(/usr/bin/plutil -extract host raw -o - "$config")
port=$(/usr/bin/plutil -extract port raw -o - "$config")
open "http://$host:$port/"
