"""Market Intelligence Pulse — daily macro context snapshot.
Captures BTC.D, ETH.D, USDT.D, USDC.D, stablecoin total, cycle phase, and rotation signals.
Runs: 8am Sydney daily.
Output: Telegram summary + vault log.
"""
import requests
from datetime import datetime

COINGECKO_GLOBAL = "https://api.coingecko.com/api/v3/global"
COINGECKO_SIMPLE = "https://api.coingecko.com/api/v3/simple/price"
VAULT_PATH = r"C:\Users\vitamnb\Documents\Roger Vault\journaling"

def get_global_data():
    r = requests.get(COINGECKO_GLOBAL, timeout=10)
    if r.status_code != 200:
        return None
    return r.json().get("data", {})

def get_btc_price():
    r = requests.get(f"{COINGECKO_SIMPLE}?ids=bitcoin&vs_currencies=usd&include_24h_change=true", timeout=10)
    if r.status_code != 200:
        return {}, 0, 0
    btc = r.json().get("bitcoin", {})
    return btc, btc.get("usd", 0), btc.get("usd_24h_change", 0)

def assess_cycle_phase(btc_d, eth_d, btc_24h_pct):
    if btc_d > 62:
        phase, risk, note = "BTC ABSORBING", "RISK_OFF", "BTC dominant — alts lack structural support"
    elif btc_d > 55:
        phase, risk, note = "TRANSITION", "NEUTRAL", "Mid-phase rotation — ETH/SOL chains active"
    elif btc_d > 50:
        phase, risk, note = "ROTATION ACTIVE", "MODERATE_RISK_ON", "Capital rotating to alts — large caps moving"
    elif btc_d > 45:
        phase, risk, note = "ALT SEASON BUILDING", "RISK_ON", "Alt season underway — mid/small caps warming up"
    else:
        phase, risk, note = "FULL ALT SEASON", "FULL_RISK_ON", "Full risk-on — low-caps running, caution on blowoff"
    return phase, risk, note

def assess_rotation_signals(btc_d, btc_24h_pct, stable_d, usdt_d):
    signals = []
    if btc_d > 58 and btc_24h_pct < -1:
        signals.append("BTC weakness + high dominance — rotation possible")
    elif btc_24h_pct > 3:
        signals.append("BTC running hard — alt liquidity squeeze ON")
    if btc_d < 52:
        signals.append("BTC.D breaking down — alt season likely active")
    # Stablecoin signals
    if stable_d > 12:
        signals.append("High stablecoin dominance (>12%) — caution, dry powder waiting")
    elif stable_d < 8:
        signals.append("Low stablecoin dominance (<8%) — risk-on, capital deployed")
    if usdt_d > 8:
        signals.append("USDT dominance elevated — market stress signal")
    return signals

def main():
    print(f"\n{'='*60}")
    print(f"[MARKET INTELLIGENCE PULSE] {datetime.now().strftime('%Y-%m-%d %H:%M')} AEST")
    print(f"{'='*60}")

    data = get_global_data()
    btc_px, btc_price, btc_24h_pct = get_btc_price()

    if not data:
        print("Failed to fetch from CoinGecko")
        return

    mcp = data.get("market_cap_percentage", {})
    btc_d = mcp.get("btc", 0)
    eth_d = mcp.get("eth", 0)
    usdt_d = mcp.get("usdt", 0)
    usdc_d = mcp.get("usdc", 0)
    stable_d = usdt_d + usdc_d
    total_mcap = data.get("total_market_cap", {}).get("usd", 0) / 1e12

    phase, risk, note = assess_cycle_phase(btc_d, eth_d, btc_24h_pct)
    rot_signals = assess_rotation_signals(btc_d, btc_24h_pct, stable_d, usdt_d)

    print(f"\n[MARKET CONTEXT]")
    print(f"  BTC Dominance:   {btc_d:.1f}%  (24h: {btc_24h_pct:+.2f}%)")
    print(f"  ETH Dominance:   {eth_d:.1f}%")
    print(f"  USDT Dominance:  {usdt_d:.1f}%")
    print(f"  USDC Dominance:  {usdc_d:.1f}%")
    print(f"  Stablecoins:     {stable_d:.1f}% combined (USDT+USDC)")
    print(f"  Total Market:   ${total_mcap:.2f}T")
    print(f"  BTC Price:      ${btc_price:,.0f}")

    print(f"\n[CYCLE PHASE: {phase}]")
    print(f"  Risk mode: {risk}")
    print(f"  {note}")

    if rot_signals:
        print(f"\n[ROTATION SIGNALS]")
        for s in rot_signals:
            print(f"  >> {s}")

    # Vault log
    today = datetime.now().strftime("%Y-%m-%d")
    log_line = f"- **{today}** | BTC.D: {btc_d:.1f}% | ETH.D: {eth_d:.1f}% | USDT: {usdt_d:.1f}% | USDC: {usdc_d:.1f}% | Stable: {stable_d:.1f}% | Phase: {phase} | BTC 24h: {btc_24h_pct:+.2f}%"
    vault_log = rf"{VAULT_PATH}\Market Pulse.md"
    try:
        with open(vault_log, "a") as f:
            f.write(log_line + "\n")
        print(f"\n[LOGGED] -> {vault_log}")
    except Exception as e:
        print(f"\n[LOG ERROR] {e}")

    print(f"\n{'='*60}")

if __name__ == "__main__":
    main()