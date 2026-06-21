#!/usr/bin/env bash
#
# team-down — tear down an ephemeral team spun up by team-up.sh. Kills the scoped
# server and WIPES its config + scoped data (config/<name>/ + ~/.protoagent/<name>/).
# The managed repo and any PRs it opened are NOT touched.
#
#   scripts/team-down.sh <name>
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"

NAME="${1:?usage: team-down <name>}"
[[ "$NAME" =~ ^[a-z0-9-]+$ ]] || { echo "bad name" >&2; exit 1; }
# Never nuke the standing instances.
case "$NAME" in
  coding|dev) echo "refusing to tear down protected instance '$NAME'" >&2; exit 1 ;;
esac

STATE="$HOME/.protoagent/$NAME/.team"

# 1. stop the server — prefer the recorded pid+port, fall back to a port scan.
if [ -f "$STATE" ]; then
  PID=$(sed -n 's/^pid=//p' "$STATE"); PORT=$(sed -n 's/^port=//p' "$STATE")
  [ -n "${PID:-}" ] && kill "$PID" 2>/dev/null || true
  [ -n "${PORT:-}" ] && pkill -f "server --port $PORT" 2>/dev/null || true
else
  echo "  (no state file; trying a best-effort kill by config dir)"
  pkill -f "config/$NAME" 2>/dev/null || true
fi
sleep 1

# 2. wipe scoped state (config + data + the editable-plugin symlinks). Repo untouched.
rm -rf "$ROOT/config/$NAME" "$HOME/.protoagent/$NAME"
rm -f "/tmp/protoagent-$NAME.log"
echo "✓ torn down '$NAME' — config + scoped data wiped; the repo and its PRs are untouched."
