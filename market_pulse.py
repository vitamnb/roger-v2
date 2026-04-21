"""Market Intelligence Pulse — daily macro context snapshot.
Captures BTC.D, ETH.D, SOL.D, total market cap, cycle phase, and rotation signals.
Runs: 8am Sydney daily (same time as quality scan).
Output: vault log + optional Telegram summary.
"""
import requests
import json
from datetime import datetime

COINGECKO_GLOBAL = "https://api.coingecko.com/api/v3/global"
COINGECKO_SIMPLE = "https://api.coingecko.com/api/v3/simple/price"
VAULT_PATH = r"C:\Users\vitamnb\Documents\Roger Vault\journaling"

def get_btc_dominance():
    r = requests.get(COINGECKO_GLOBAL, timeout=10)
    if r.status_code != 200:
        return None
    data = r.json().get("data", {})
    return {
        "btc_d": data.get("market_cap_percentage", {}).get("btc", 0),
        "eth_d": data.get("market_cap_percentage", {}).get("eth", 0),
        "total_mcap_trillions": data.get("total_market_cap", {}).get("usd", 0) / 1e12,
        "active_coins": data.get("active_cryptocurrencies", 0),
        "btc_24h_vol": data.get("market_cap_change_percentage_24h_usd", 0),
    }

def get_btc_price_and_change():
    r = requests.get(
        f"{COINGECKO_SIMPLE}?ids=bitcoin&vs_currencies=usd&include_24h_change=true",
        timeout=10
    )
    if r.status_code != 200:
        return {}
    btc = r.json().get("bitcoin", {})
    return {
        "btc_price": btc.get("usd", 0),
        "btc_24h_pct": btc.get("usd_24h_change", 0),
    }

def get_sol_dominance():
    r = requests.get(
        f"{COINGECKO_SIMPLE}?ids=solana&vs_currencies=usd&include_market_cap=true",
        timeout=10
    )
    if r.status_code != 200:
        return {}
    data = r.json()
    sol = data.get("solana", {})
    total = data.get("market_data", {}).get("total_market_cap", {}).get("usd", 1)
    # Fallback: use BTC from global to calc
    btc_mcap = 1e12  # placeholder
    return {
        "sol_price": sol.get("usd", 0),
        "sol_mcap": sol.get("market_cap", 0),
    }

def assess_cycle_phase(btc_d, eth_d, btc_24h_pct):
    """Return (phase_label, risk_mode, explanation)."""
    if btc_d > 62:
        phase = "BTC ABSORBING"
        risk = "RISK_OFF"
        note = "BTC dominant — alts lack structural support"
    elif btc_d > 55:
        phase = "TRANSITION"
        risk = "NEUTRAL"
        note = "Mid-phase rotation — ETH/SOL chains active"
    elif btc_d > 50:
        phase = "ROTATION ACTIVE"
        risk = "MODERATE_RISK_ON"
        note = "Capital rotating to alts — large caps moving"
    elif btc_d > 45:
        phase = "ALT SEASON BUILDING"
        risk = "RISK_ON"
        note = "Alt season underway — mid/small caps warming up"
    else:
        phase = "FULL ALT SEASON"
        risk = "FULL_RISK_ON"
        note = "Full risk-on — low-caps running, caution on blowoff"

    # ETH context
    if eth_d > 20:
        eth_note = "ETH heavy — ETH chain plays preferred"
    else:
        eth_note = "No single chain dominant"

    return phase, risk, note, eth_note

def assess_rotation_signal(btc_d, btc_24h_pct):
    """Flag if we might be entering a rotation phase."""
    signals = []
    if btc_d > 58 and btc_24h_pct < -1:
        signals.append("BTC weakness + high dominance — rotation possible")
    elif btc_24h_pct > 3:
        signals.append("BTC running hard — alt liquidity squeeze ON")
    if btc_d < 52:
        signals.append("BTC.D breaking down — alt season likely active")
    return signals

def main():
    print(f"\n{'='*60}")
    print(f"[MARKET INTELLIGENCE PULSE] {datetime.now().strftime('%Y-%m-%d %H:%M')} AEST")
    print(f"{'='*60}")

    dom = get_btc_dominance()
    btc_px = get_btc_price_and_change()
    sol_dat = get_sol_dominance()

    if not dom:
        print("Failed to fetch data from CoinGecko")
        return

    btc_d = dom["btc_d"]
    eth_d = dom["eth_d"]
    total_mcap = dom["total_mcap_trillions"]
    btc_24h_pct = btc_px.get("btc_24h_pct", 0)
    btc_price = btc_px.get("btc_price", 0)

    phase, risk, note, eth_note = assess_cycle_phase(btc_d, eth_d, btc_24h_pct)
    rot_signals = assess_rotation_signal(btc_d, btc_24h_pct)

    print(f"\n[MARKET CONTEXT]")
    print(f"  BTC Dominance:   {btc_d:.1f}%  (24h: {btc_24h_pct:+.2f}%)")
    print(f"  ETH Dominance:   {eth_d:.1f}%")
    print(f"  Total Market:   ${total_mcap:.2f}T")
    print(f"  BTC Price:      ${btc_price:,.0f}")
    if sol_dat.get("sol_price"):
        print(f"  SOL Price:      ${sol_dat['sol_price']:,.2f}")

    print(f"\n[CYCLE PHASE: {phase}]")
    print(f"  Risk mode: {risk}")
    print(f"  {note}")
    print(f"  {eth_note}")

    if rot_signals:
        print(f"\n[ROTATION SIGNALS]")
        for s in rot_signals:
            print(f"  >> {s}")

    # Log to vault
    today = datetime.now().strftime("%Y-%m-%d")
    log_line = f"- **{today}** | BTC.D: {btc_d:.1f}% | ETH.D: {eth_d:.1f}% | Phase: {phase} | Risk: {risk} | BTC 24h: {btc_24h_pct:+.2f}%"
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
