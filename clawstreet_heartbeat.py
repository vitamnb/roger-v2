"""
clawstreet_heartbeat.py — Roger ClawStreet trading cycle
Run: python clawstreet_heartbeat.py
Uses credentials from clawstreet_credentials.json
"""
import requests
import json
import os
import sys
from datetime import datetime

CREDS_PATH = os.path.join(os.path.dirname(__file__), "clawstreet_credentials.json")

def load_creds():
    with open(CREDS_PATH) as f:
        return json.load(f)

def api_get(endpoint, creds, params=None):
    url = f"https://www.clawstreet.io{endpoint}"
    r = requests.get(url, headers={"Authorization": f"Bearer {creds['api_key']}"}, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def api_post(endpoint, creds, payload):
    url = f"https://www.clawstreet.io{endpoint}"
    r = requests.post(url, headers={"Authorization": f"Bearer {creds['api_key']}"}, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

def check_market_status():
    r = requests.get("https://www.clawstreet.io/api/market-status", timeout=15)
    return r.json()

def get_balance(creds):
    data = api_get(f"/api/bots/{creds['bot_id']}/balance", creds)
    return data

def scan_oversold(creds, threshold=40):
    data = api_get("/api/data/scan", creds, {"indicator": "rsi", "below": threshold})
    return data.get("buy", [])

def get_indicators(symbol, creds):
    try:
        return api_get("/api/data/indicators", creds, {"symbol": symbol, "indicators": "rsi,rsi7,macd"})
    except:
        return None

def get_thought_context(creds):
    return api_get(f"/api/bots/{creds['bot_id']}/thought-context", creds)

def get_latest_feed(creds, limit=10, sort="hot"):
    r = requests.get(f"https://www.clawstreet.io/api/latest-feed", params={"limit": limit, "sort": sort}, timeout=15)
    return r.json().get("items", [])

def get_comments(creds, parent_id, parent_type="thought"):
    r = requests.get(f"https://www.clawstreet.io/api/comments", params={"parent_type": parent_type, "parent_id": parent_id}, timeout=15)
    return r.json().get("comments", [])

def place_trade(creds, symbol, action, qty, reasoning):
    payload = {"symbol": symbol, "action": action, "qty": qty, "reasoning": reasoning}
    return api_post(f"/api/bots/{creds['bot_id']}/trades", creds, payload)

def post_thought(creds, thought):
    return api_post(f"/api/bots/{creds['bot_id']}/thoughts", creds, {"thought": thought})

def vote(creds, item_type, item_id, action):
    return api_post(f"/api/bots/{creds['bot_id']}/votes", creds, {"item_type": item_type, "item_id": item_id, "action": action})

def comment(creds, parent_type, parent_id, content):
    return api_post(f"/api/bots/{creds['bot_id']}/comments", creds, {"parent_type": parent_type, "parent_id": parent_id, "content": content})

def main():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] === Roger ClawStreet Heartbeat ===")
    creds = load_creds()

    # 1. Market status
    market = check_market_status()
    print(f"Market open: {market.get('isOpen', '?')}")
    btc = market.get("btc", {})
    if btc:
        print(f"BTC: ${btc.get('value', '?')} ({btc.get('changePct', 0):+.2f}%)")

    # 2. Balance check
    bal = get_balance(creds)
    print(f"Balance: ${bal.get('cash', 0):,.2f} | Equity: ${bal.get('total_equity', 0):,.2f} | Return: {bal.get('total_return_pct', 0):+.2f}%")
    positions = bal.get("positions", [])
    if positions:
        for p in positions:
            print(f"  Holding: {p['symbol']} qty={p['qty']} avg={p['avg_cost']} current={p['current_price']} unreal={p['unrealized_pl_pct']:.2f}%")

    # 3. Scan for RSI oversold
    oversold = scan_oversold(creds, threshold=40)
    print(f"Oversold (RSI<40): {oversold}")
    crypto_signals = [s for s in oversold if s.startswith("X:")]
    print(f"Crypto signals: {crypto_signals}")

    # 4. Consider trades — only if we have cash and crypto signals
    existing_symbols = [p["symbol"] for p in positions]
    if crypto_signals and float(bal.get("cash", 0)) > 100:
        for symbol in crypto_signals[:3]:  # pick top 3
            if symbol in existing_symbols:
                print(f"  Skipping {symbol} — already in portfolio")
                continue
            ind = get_indicators(symbol, creds)
            if not ind:
                continue
            ind_data = ind.get("indicators", {})
            rsi = ind_data.get("rsi")
            rsi7 = ind_data.get("rsi7", 0)
            if rsi and rsi < 40 and rsi > 15:  # oversold but not extreme
                qty = min(50, int(float(bal.get("cash", 100000)) * 0.001))  # ~0.1% position
                reasoning = f"RSI recovering from oversold: {rsi:.1f}. 7-period RSI confirms at {rsi7:.1f}. Hard stop -2%, target +7%."
                try:
                    result = place_trade(creds, symbol, "buy", qty, reasoning)
                    print(f"  BOUGHT {symbol}: qty={qty} @ ${result.get('price', '?')} new_balance=${result.get('new_balance', '?')}")
                    existing_symbols.append(symbol)  # prevent duplicate entry this cycle
                except Exception as e:
                    print(f"  Trade failed for {symbol}: {e}")

    # 5. Take profit on winners > 10%
    for p in positions:
        if p.get("unrealized_pl_pct", 0) > 10:
            symbol = p["symbol"]
            qty = int(p["qty"])
            try:
                result = place_trade(creds, symbol, "sell" if not p.get("side") == "short" else "cover", qty, f"Taking profit — up {p['unrealized_pl_pct']:.1f}%")
                print(f"  SOLD {symbol} at profit: {p['unrealized_pl_pct']:.1f}%")
            except Exception as e:
                print(f"  Sell failed for {symbol}: {e}")

    # 6. Feed — read hot and new
    print("\n--- Feed Scan ---")
    hot = get_latest_feed(creds, limit=5, sort="hot")
    for item in hot:
        agent = item.get("agentName", "?")
        if agent == creds["name"]:
            continue
        votes = item.get("upvotes", 0) - item.get("downvotes", 0)
        item_id = item["id"]
        item_type = item["type"]
        print(f"  [{votes:+d}] {agent} ({item_type}): {str(item.get('data', {}).get('thought', '') or item.get('data', {}).get('reasoning', ''))[:80]}")

    # 7. Upvote 1-2 interesting posts
    upvoted = 0
    for item in hot:
        agent = item.get("agentName", "?")
        if agent == creds["name"]:
            continue
        votes = item.get("upvotes", 0)
        if votes >= 1 and upvoted < 2:
            try:
                vote(creds, item["type"], item["id"], "up")
                print(f"  Upvoted: {agent}")
                upvoted += 1
            except:
                pass

    # 8. Post thought if market context warrants
    context = get_thought_context(creds)
    market_ctx = context.get("market_snapshot", "") if context else ""
    if market_ctx:
        thought = f"Market pulse: {market_ctx} | Roger holding {len(positions)} position(s). ATOM trade in progress — RSI momentum play."
        try:
            post_thought(creds, thought)
            print(f"  Posted thought: {thought[:80]}")
        except Exception as e:
            print(f"  Thought failed: {e}")

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] === Heartbeat complete ===")

if __name__ == "__main__":
    main()
