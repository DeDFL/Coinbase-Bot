#!/bin/zsh
# Runs /briefing headless. Called daily by launchd (~/Library/LaunchAgents/com.cbbot.briefing.plist).
set -u
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# Prefer a claude on PATH; otherwise the newest binary bundled with the VS Code extension.
CLAUDE="$(command -v claude || true)"
if [[ -z "$CLAUDE" ]]; then
  CLAUDE="$(ls -d "$HOME"/.vscode/extensions/anthropic.claude-code-*/resources/native-binary/claude 2>/dev/null | sort -V | tail -1)"
fi
if [[ -z "$CLAUDE" ]]; then
  echo "$(date) claude CLI not found" >> logs/briefing.log; exit 1
fi

# Skip if today's briefing already exists (launchd may also fire on wake after a missed run).
[[ -f "briefings/$(date +%F).md" && "${1:-}" != "--force" ]] && exit 0

echo "=== $(date) starting briefing ===" >> logs/briefing.log
"$CLAUDE" -p "/briefing" \
  --allowedTools "mcp__coinbase__get_market_snapshot,mcp__coinbase__get_signal_history,mcp__coinbase__log_signal,mcp__coinbase__save_briefing,WebSearch,WebFetch" \
  >> logs/briefing.log 2>&1
echo "=== $(date) finished (exit $?) ===" >> logs/briefing.log
