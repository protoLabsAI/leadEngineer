#!/usr/bin/env bash
#
# team-up — spin up an EPHEMERAL, repo-scoped Lead Engineer team. One command, no
# hand-editing. The instance is scoped by PROTOAGENT_INSTANCE (ADR 0004): its own
# config/<name>/ + ~/.protoagent/<name>/. Tear it down with `scripts/team-down.sh <name>`.
#
#   scripts/team-up.sh <name> <repo-path> [--opus] [--port N] [--gate "<cmd>"]
#
#   <name>       instance/team name (a-z0-9-), also the A2A card name + beads prefix
#   <repo-path>  the repo the board manages (coders branch worktrees off it)
#   --opus       run the brain on Claude Code / Opus (ACP, ADR 0033). Default: gateway model.
#   --port N     bind port (default: first free from 7873).
#   --gate CMD   pre-PR gate command. Default: auto-detected from the repo.
#
# Seeds the team's config from config/langgraph-config.example.yaml (the shipped Lead
# Engineer config), fills in the repo, symlinks the editable plugins, copies the model
# secret + gateway api_base, `br init`s the repo, and launches headless.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"

[ $# -ge 2 ] || { echo "usage: team-up <name> <repo-path> [--opus] [--port N] [--gate \"<cmd>\"]" >&2; exit 1; }
NAME="$1"; REPO="$2"; shift 2
OPUS=0; PORT=""; GATE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --opus) OPUS=1 ;;
    --port) PORT="${2:?--port needs a value}"; shift ;;
    --gate) GATE="${2:?--gate needs a value}"; shift ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac; shift
done

[[ "$NAME" =~ ^[a-z0-9-]+$ ]] || { echo "name must be [a-z0-9-]" >&2; exit 1; }
REPO="$(cd "$REPO" 2>/dev/null && pwd)" || { echo "repo not found: $REPO" >&2; exit 1; }
[ -d "$REPO/.git" ] || { echo "repo has no .git: $REPO" >&2; exit 1; }
BR="${BR_BIN:-$HOME/.cargo/bin/br}"
PY="${PYTHON:-$ROOT/.venv/bin/python}"; [ -x "$PY" ] || PY="python3"

# Pick a free port from 7873 if not given.
if [ -z "$PORT" ]; then
  for p in $(seq 7873 7899); do lsof -iTCP:"$p" -sTCP:LISTEN -n >/dev/null 2>&1 || { PORT="$p"; break; }; done
fi
[ -n "$PORT" ] || { echo "no free port in 7873-7899" >&2; exit 1; }

# Auto-detect the pre-PR gate from the repo if not passed.
if [ -z "$GATE" ]; then
  if [ -f "$REPO/pyproject.toml" ] || [ -f "$REPO/requirements-dev.txt" ]; then
    GATE="ruff check . && ruff format --check ."
  elif grep -q '"vitepress"' "$REPO/package.json" 2>/dev/null; then
    GATE="npm ci && npm run docs:build"
  elif [ -f "$REPO/package.json" ]; then
    GATE="npm ci && npm test"
  fi
fi

CFG="$ROOT/config/$NAME"
APP="$HOME/Library/Application Support/studio.protolabs.protoagent"
echo "▶ team '$NAME' → $REPO  (port $PORT, brain: $([ $OPUS = 1 ] && echo Opus/ACP || echo gateway), gate: ${GATE:-<none>})"

# 1. config dir + editable plugin symlinks (project_board carries onboard-project etc.)
mkdir -p "$CFG/plugins" "$HOME/.protoagent/$NAME"
ln -sfn "$HOME/dev/projectBoard-plugin"  "$CFG/plugins/project_board"
ln -sfn "$HOME/dev/agent-browser-plugin" "$CFG/plugins/agent_browser"

# 2. seed config from the shipped Lead Engineer template, fill placeholders (preserve comments)
cp "$ROOT/config/langgraph-config.example.yaml" "$CFG/langgraph-config.yaml"
OPUS="$OPUS" "$PY" - "$CFG/langgraph-config.yaml" "$REPO" "$NAME" "$GATE" "$CFG/plugins" <<'PY'
import os, sys
path, repo, name, gate, plugdir = sys.argv[1:6]
t = open(path).read()
t = t.replace("~/dev/REPLACE_ME", repo)
t = t.replace("name: REPLACE_ME", f"name: {name}")           # filesystem project name
t = t.replace("name: engineering-team", f"name: {name}")     # identity
t = t.replace("loop_enabled: false", "loop_enabled: true")
t = t.replace('local_gate_cmd: ""', f'local_gate_cmd: "{gate}"')
t = t.replace("enabled: [delegates, project_board, agent_browser]",
              f"enabled: [delegates, project_board, agent_browser]\n  dir: {plugdir}")
if os.environ.get("OPUS") != "1":
    t = t.replace("agent_runtime: acp:claude", "agent_runtime: native")   # gateway brain
open(path, "w").write(t)
PY

# 3. model secret + gateway api_base (from the desktop app / an existing instance)
for src in "$APP/secrets.yaml" "$ROOT/config/coding/secrets.yaml"; do
  [ -f "$src" ] && { cp "$src" "$CFG/secrets.yaml"; break; }
done
for src in "$HOME/.protoagent/coding/host-config.yaml" "$HOME/.protoagent/dev/host-config.yaml"; do
  [ -f "$src" ] && { cp "$src" "$HOME/.protoagent/$NAME/host-config.yaml"; break; }
done

# 4. beads workspace in the repo (so the board pins here, not a parent dir)
[ -d "$REPO/.beads" ] || (cd "$REPO" && "$BR" init >/dev/null 2>&1 && echo "  br init $REPO")

# 5. launch headless (strip Claude-Code nesting markers; pin Opus when --opus)
ENVARGS=(env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_CODE_EXECPATH \
  -u CLAUDE_CODE_SESSION_ID -u CLAUDE_CODE_CHILD_SESSION -u CLAUDE_EFFORT)
[ "$OPUS" = 1 ] && ENVARGS+=(ANTHROPIC_MODEL=opus)
LOG="/tmp/protoagent-$NAME.log"
"${ENVARGS[@]}" PROTOAGENT_INSTANCE="$NAME" PORT="$PORT" \
  nohup "$ROOT/scripts/dev.sh" --ui none --host 127.0.0.1 > "$LOG" 2>&1 &
# dev.sh execs `python -m server`, so $! is the server pid. Record it for team-down.
printf 'pid=%s\nport=%s\nrepo=%s\n' "$!" "$PORT" "$REPO" > "$HOME/.protoagent/$NAME/.team"

# 6. wait for ready
for _ in $(seq 1 50); do
  curl -s -m 2 "localhost:$PORT/healthz" 2>/dev/null | grep -q '"ok":true' && break
  grep -qiE 'cannot complete|Traceback' "$LOG" 2>/dev/null && { echo "  ✗ boot failed — see $LOG"; tail -5 "$LOG"; exit 1; }
  sleep 1
done
if curl -s -m 3 "localhost:$PORT/healthz" 2>/dev/null | grep -q '"ok":true'; then
  echo "  ✓ up: http://localhost:$PORT   (log: $LOG)"
  echo "    teardown: scripts/team-down.sh $NAME"
else
  echo "  ✗ did not become healthy — see $LOG"; exit 1
fi
