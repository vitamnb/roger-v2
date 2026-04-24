# Roger v3.0 — Clean Slate

**Status:** Infrastructure rebuilt, strategies archived, ready for new build.
**Date:** 2026-04-24

---

## What's Here

| File | Purpose |
|------|---------|
| `generate_config.py` | Generate `config.json` from `.env` (no plaintext keys) |
| `mtf_research.py` | Multi-timeframe backtester (the only validated research tool) |
| `coin_quality_full.py` | Pair quality grading (keep for reference) |
| `market_pulse.py` | Market regime detection (keep for reference) |
| `user_data/config.json` | Generated from `.env` — populate pair_whitelist before use |

## What's Archived

Everything else is in `archive/2026-04-24/`:
- All old strategies (Entry A-E variants)
- All scanners and signal agents
- Old configs, cron jobs, one-off scripts
- Research results from previous runs
- Logs and trade journals

## Next Steps

1. **Research a new strategy approach** — RSI mean reversion is dead
2. **Validate it through `mtf_research.py`** — before any live code
3. **Build a minimal freqtrade strategy** — only after validation
4. **Paper trade one pair** — prove edge before scaling

## Security

API keys live in `~/.openclaw/workspace/.env` only. Never in configs. Run `python generate_config.py` after updating `.env`.

## Notes

- Dry run mode only until proven profitable
- Start with 1 pair, 1 trade at a time
- Validate everything before trusting it
