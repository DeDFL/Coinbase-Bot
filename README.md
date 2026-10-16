# cbbot: Coinbase trading + signals for Claude Code

A local MCP server. Claude Code uses it to read Coinbase market data, compute rule-based signals, write daily news-plus-technicals briefings, and place orders. **Paper mode is the default.**

## Setup

1. **Create an API key:** go to <https://portal.cdp.coinbase.com>, then API Keys, then Create API key.
   - Permissions: **View** and **Trade** only. Never enable Transfer.
   - Add an IP allowlist if you can.
   - Download the JSON key file and move it somewhere private, e.g. `~/coinbase-bot/cdp_api_key.json` (it's gitignored).
2. `cp .env.example .env` and set `COINBASE_KEY_FILE=~/coinbase-bot/cdp_api_key.json`
3. Restart Claude Code, or run `/mcp` to reconnect `coinbase`. Prices and signals work **without** a key. The key is only needed for real balances and live orders.

The server is already registered at user scope:
`claude mcp add -s user coinbase -- ~/.local/bin/uv --directory ~/coinbase-bot run cbbot`

## Using it

Just ask Claude Code:
- "What's my status?" / "Show my balances"
- "Evaluate the MA crossover on BTC daily"
- "Paper buy $10 of ETH" / "Place a limit buy for $20 of BTC at 78000"
- "Any signals today?" (reads the latest briefing)
- `/briefing` in this folder (fresh briefing now; optional coins: `/briefing SOL-USD`)
- "How did last week's signals do?"

## Safety

| Guard | Where |
|---|---|
| Paper mode unless `TRADING_MODE=live` in `.env` | `.env` |
| Live orders also need `confirm=true` per order | `risk.py` |
| Max $ per order, rolling 24h cap, allowed coins | `config.yaml` → `risk.py` |
| Every attempt logged, including rejections | `state/cbbot.sqlite` |
| Briefings never place trades | `.claude/commands/briefing.md` |

**Going live:** set `TRADING_MODE=live`, restart Claude Code, and start with a $1–5 order.
To add a coin, add it to both `watchlist` and `limits.allowed_products` in `config.yaml`.

## Daily briefing

`launchd` runs `scripts/run_briefing.sh` at 8:00 AM, and if the Mac was asleep at 8:00, it runs on wake. It skips the run if today's briefing already exists. Output goes to `briefings/YYYY-MM-DD.md` and the log to `logs/briefing.log`.

- Run now: `launchctl kickstart gui/$(id -u)/com.cbbot.briefing` (or `scripts/run_briefing.sh --force`)
- Change the time: edit `Hour`/`Minute` in `~/Library/LaunchAgents/com.cbbot.briefing.plist`, then
  `launchctl bootout gui/$(id -u)/com.cbbot.briefing && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.cbbot.briefing.plist`
- Disable: `launchctl bootout gui/$(id -u)/com.cbbot.briefing`

## Development

`~/.local/bin/uv run pytest`. Strategies live in `src/cbbot/strategies.py`. Add one to `STRATEGIES` and it shows up in `evaluate_signal` and the snapshot automatically.

Not financial advice. Simple technical rules plus news summaries can be wrong.
