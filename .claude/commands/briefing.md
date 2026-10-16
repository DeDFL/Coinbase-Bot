---
description: Advisory buy/sell briefing from Coinbase technicals + recent news
allowed-tools: mcp__coinbase__get_market_snapshot, mcp__coinbase__get_signal_history, mcp__coinbase__log_signal, mcp__coinbase__save_briefing, WebSearch, WebFetch
---

Produce today's crypto signal briefing. Coins: $ARGUMENTS (if empty, use the watchlist from the snapshot).

These signals are ADVISORY ONLY. Never call place_order or run_strategy from this command.

## Steps

1. **Technicals:** call `get_market_snapshot` (pass the coins above if any were given).
2. **Track record:** call `get_signal_history` with days=14 so you can mention how recent calls played out.
3. **News and research:** for each coin, run web searches limited to the last 72 hours. Cover:
   - coin-specific news (upgrades, ETF flows, large holder or treasury moves, exchange listings or delistings, hacks)
   - regulation and legal actions
   - macro events that move crypto (Fed, CPI and jobs data, the dollar, equity risk-off moves) and anything scheduled in the next 7 days
   Prefer primary or reputable sources (Reuters, Bloomberg, CoinDesk, The Block, official project or agency posts). Ignore price-prediction spam. If a result has no clear date or is older than 72 hours, leave it out or say it's older.
4. **Make the call** for each coin: BUY, SELL or HOLD, with confidence low, medium or high.
   - Weigh the daily signals more heavily than the hourly ones. Hourly signals only help with timing.
   - Mark a call **STRONG** only when the technicals and the news point the same way. If they conflict, cap confidence at low or medium and explain the conflict.
   - Default to HOLD when the evidence is mixed or thin. Don't invent conviction.
5. **Log** each call with `log_signal` (product, action, confidence, one-line summary).
6. **Save** the full briefing with `save_briefing`, then print it.

## Briefing format

```
# Crypto Briefing — <date, time, timezone>

## Summary
| Coin | Call | Confidence | Price | 24h | 7d | One-line why |

## <COIN>
**Call:** BUY/SELL/HOLD (confidence) [STRONG if applicable]
**Technicals:** daily trend + RSI, hourly trend + RSI, volume vs average, position in 30-day range
**News & catalysts:**
- <headline> — <why it matters> ([source](url), <date>)
**Risks / what would change this call:** ...

## Upcoming events (next 7 days)
## Recent signal track record
## Disclaimer
Automated research summary, not financial advice. Signals are advisory; no trades were placed.
```
