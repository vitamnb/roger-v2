# Scanner Infrastructure Status Report
# Generated: 2026-04-24
# Roger Trading System v2

## ACTIVE CRON JOBS (12 total)

### 1. KuCoin Scanner (1h) ✅ STILL SENDING SIGNALS
- **Schedule:** Every hour at :05 past
- **Script:** `scan_cron.ps1`
- **Status:** ARCHIVED (moved to archive/2026-04-24_cleanup/)
- **Impact:** Cron still fires but script path invalid — likely using cached/old version
- **Action:** DISABLE or migrate to new infra

### 2. Whale Watch (15m) 🟡 SILENT
- **Schedule:** Every 15 minutes
- **Script:** `whale_watch_cron.ps1`
- **Status:** ARCHIVED
- **Impact:** Runs silently (delivery: none), updates `whale_watchlist.txt`
- **Action:** DISABLE — no longer needed for 1h strategy

### 3. YOLO Scanner (6h) 🟡 BREAKOUT SIGNALS
- **Schedule:** Every 6 hours
- **Script:** `yolo_scanner.py`
- **Status:** ARCHIVED
- **Impact:** May still work if script at old path, but not aligned with 1h strategy
- **Action:** DISABLE or integrate into 4h strategy later

### 4. Quality Scan (8am/8pm) 🟡 PAIR RANKING
- **Schedule:** 8am and 8pm daily
- **Script:** `coin_quality_full.py`
- **Status:** ARCHIVED
- **Impact:** Updates `daily_watchlist.txt` but strategy uses fixed 9-pair whitelist
- **Action:** DISABLE — whitelist is now static

### 5. Market Intelligence Pulse (8am) 🟡 BTC.D/ETH.D
- **Schedule:** 8am daily
- **Script:** `market_pulse.py`
- **Status:** ARCHIVED
- **Impact:** Macro context, not needed for 1h execution
- **Action:** KEEP for regime context but redirect to new path

### 6. Majors Bias Check (9am) 🟡 REGIME SCAN
- **Schedule:** 9am daily
- **Script:** `scanner.py --majors`
- **Status:** ARCHIVED
- **Impact:** Regime classification — useful but separate from 1h strategy
- **Action:** KEEP but move to new infra

### 7. Trade Monitor (hourly) ✅ SL/TP ALERTS
- **Schedule:** Every hour at :35 past
- **Script:** `price_check.py`
- **Status:** ARCHIVED
- **Impact:** Monitors open trades for SL/TP hits
- **Action:** DISABLE — freqtrade handles this natively

### 8. Bull/Bear Researcher (6h) 🟡 MARKET ANALYSIS
- **Schedule:** Every 6 hours
- **Script:** `bull_bear_cron.ps1`
- **Status:** ARCHIVED
- **Impact:** LLM-based market analysis
- **Action:** DISABLE — not aligned with 1h strategy

### 9. ClawStreet Trading (4h) 🟡 STOCK/CRYPTO
- **Schedule:** Every 4 hours
- **Script:** `clawstreet_cron.ps1`
- **Status:** ARCHIVED
- **Impact:** Separate trading system (stocks + crypto)
- **Action:** DISABLE — different system, different capital

### 10. Research Progress Check (2h) 🔴 MTF RESEARCH
- **Schedule:** Every 2 hours
- **Script:** Checks for `mtf_results_2026-04-22.txt`
- **Status:** COMPLETED
- **Action:** DISABLE — research finished

### 11. Roger System Audit (6pm) 🟡 CODE INTEGRITY
- **Schedule:** 6pm daily
- **Script:** `audit_layer1.py`
- **Status:** ARCHIVED
- **Impact:** Checks code integrity, data sanity
- **Action:** DISABLE or rebuild for new infra

### 12. Quality Scan Morning (8am) 🟡 DUPLICATE
- **Schedule:** 8am daily
- **Script:** `coin_quality_full.py`
- **Status:** ARCHIVED (duplicate of #4)
- **Action:** DISABLE

---

## RECOMMENDATION: CLEAN SLATE

**Disable ALL old scanners.** The 6 paper trading bots will handle:
- Signal generation (each strategy)
- Trade execution (freqtrade native)
- SL/TP management (freqtrade native)
- Position tracking (freqtrade DB)

**What we lose:**
- Manual SL/TP alerts (freqtrade has them)
- Market regime overview (can rebuild if needed)
- Whale watch (not relevant to 1h strategy)
- YOLO breakout signals (4h strategy later)

**What we gain:**
- Clean execution
- No conflicting signals
- No false alerts from archived scripts
- Single source of truth (freqtrade DB)

---

## NEXT STEPS

1. **Disable all old crons** (except ClawStreet if still wanted)
2. **Launch 6 paper trading bots**
3. **Build new market health overlay** (optional)
4. **Monitor for 1-2 weeks**
5. **Re-enable scanners selectively** if needed

---

## MARKET HEALTH OVERLAY (Future)

If you want regime context integrated into the 1h strategy, I can build:
- **Daily regime check** (BTC/ETH/SOL/XRP/ATOM ADX + RSI)
- **Market health score** (0-100)
- **Chop filter** (ADX < 20 = no trades)
- **Bull/bear bias** (daily structure)

This would be a lightweight addition, not a separate scanner.
