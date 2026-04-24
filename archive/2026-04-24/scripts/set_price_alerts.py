#!/usr/bin/env python
"""
set_price_alerts.py
Sets KuCoin stop-loss and take-profit trigger alerts for an open Freqtrade trade.

Usage:
  python set_price_alerts.py           Set/replace SL + TP for open trade
  python set_price_alerts.py cancel    Cancel all stop orders for open pair
  python set_price_alerts.py show      Show current stop orders for open pair
  python set_price_alerts.py status     Test KuCoin API auth

Trigger order behaviour:
  - stop=loss: fires when price FALLS to or below stopPrice (good for SL)
  - stop=entry: fires when price RISES to or above stopPrice (good for TP)
  Both fire a MARKET sell of the full position size.

Key insight: KuCoin server time comes from HTTP Date header, NOT JSON body.
Nonce = parsed server ms + 2000ms buffer. Cancel uses DELETE with clientOid in query string.
"""
import requests
import time
import hmac
import base64
import hashlib
import json
import sys
import uuid
import subprocess
from email.utils import parsedate_tz, mktime_tz

API_KEY = "69e068a7c9bace0001a89666"
API_SECRET = "f541ca8a-44d0-41e2-8475-db060c1cfc24"
API_PASS = "BuvG0tUM%mpq3gBXjZ6^"
BASE = "https://api.kucoin.com"


def get_server_ms():
    """Get KuCoin server time from HTTP Date header (RFC 2822)."""
    try:
        r = requests.get(
            BASE + "/api/v1/market/orderbook/level1?symbol=JUP-USDT",
            timeout=5, allow_redirects=True
        )
        ts = mktime_tz(parsedate_tz(r.headers["Date"]))
        return int(ts * 1000)
    except Exception:
        return int(time.time() * 1000)


def get_signed_headers(path, method="GET", body=""):
    nonce = str(get_server_ms() + 2000)
    message = nonce + method + path + body
    sig = base64.b64encode(
        hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256).digest()
    ).decode()
    passphrase_enc = base64.b64encode(
        hmac.new(API_SECRET.encode(), API_PASS.encode(), hashlib.sha256).digest()
    ).decode()
    return {
        "KC-API-TIMESTAMP": nonce,
        "KC-API-KEY": API_KEY,
        "KC-API-SIGN": sig,
        "KC-API-PASSPHRASE": passphrase_enc,
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json",
    }


def api(method, path, body=""):
    hdrs = get_signed_headers(path, method, body)
    url = BASE + path
    if method == "GET":
        r = requests.get(url, headers=hdrs, timeout=5)
    elif method == "DELETE":
        r = requests.delete(url, headers=hdrs, timeout=5)
    else:
        r = requests.post(url, headers=hdrs, data=body, timeout=5)
    return r.json()


def get_open_trade():
    cmd = [
        "curl", "-s", "-X", "GET",
        "http://127.0.0.1:8080/api/v1/status",
        "-u", "roger:RogerDryRun2026!"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        trades = json.loads(result.stdout)
        return next((t for t in trades if t.get("is_open")), None)
    except json.JSONDecodeError:
        return None


def set_trigger(pair, side, trigger_price, size, stop_type):
    """Place a KuCoin stop-order (fires MARKET sell when price crosses trigger)."""
    body = json.dumps({
        "symbol": pair.replace("/", "-"),
        "type": "market",
        "side": side,
        "size": str(size),
        "stop": stop_type,
        "stopPrice": str(trigger_price),
        "clientOid": str(uuid.uuid4()),
    })
    result = api("POST", "/api/v1/stop-order", body)
    if result.get("code") == "200000":
        oid = result["data"].get("orderId", "N/A")
        print(
            f"  [{side.upper()} {stop_type.upper()}] "
            f"${float(trigger_price):.4f} — ID: {oid}"
        )
        return True
    print(f"  Error: {result}")
    return False


def cancel_triggers(pair):
    """Cancel all open stop orders for a pair (uses DELETE with clientOid in query)."""
    sym = pair.replace("/", "-")
    result = api("GET", f"/api/v1/stop-order?symbol={sym}&status=open")
    data = result.get("data", {})
    items = data if isinstance(data, list) else data.get("items", [])
    if not items:
        print("  No open stop orders found.")
        return
    print(f"  Cancelling {len(items)} stop order(s)...")
    for o in items:
        client_oid = o["clientOid"]
        path = f"/api/v1/stop-order/cancelOrderByClientOid?symbol={sym}&clientOid={client_oid}"
        r = api("DELETE", path)
        status = r.get("code", "???")
        print(f"  Cancelled {client_oid[:8]}... : {status}")


def show_triggers(pair):
    """Show current stop orders for a pair."""
    sym = pair.replace("/", "-")
    result = api("GET", f"/api/v1/stop-order?symbol={sym}&status=open")
    data = result.get("data", {})
    items = data if isinstance(data, list) else data.get("items", [])
    if not items:
        print(f"  No open stop orders for {pair}.")
        return
    print(f"  Open stop orders for {pair}:")
    for o in items:
        price = float(o["stopPrice"])
        size = float(o["size"])
        print(
            f"  {o['stop'].upper():6} | {o['side'].upper()} | "
            f"${price:.4f} | size={size:.4f}"
        )


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "set"

    if mode == "status":
        result = api("GET", "/api/v1/accounts")
        if "data" in result:
            print("KuCoin auth: OK")
            for a in result["data"]:
                print(f"  {a['currency']} {a['type']}: {a['balance']}")
        else:
            print(f"KuCoin auth FAILED: {result}")
        return

    trade = get_open_trade()

    if mode == "show":
        pair = (
            sys.argv[2] if len(sys.argv) > 2
            else (trade["pair"] if trade else None)
        )
        if not pair:
            print("No pair specified and no open trade found.")
            return
        show_triggers(pair)
        return

    if mode == "cancel":
        pair = (
            sys.argv[2] if len(sys.argv) > 2
            else (trade["pair"] if trade else None)
        )
        if not pair:
            print("No pair specified and no open trade found.")
            return
        print(f"Cancelling stop orders for {pair}...")
        cancel_triggers(pair)
        return

    if not trade:
        print("No open trade found.")
        return

    pair = trade["pair"]
    entry = float(trade["open_rate"])
    amount = float(trade["amount"])
    stop = float(trade["stop_loss_abs"])
    tp = round(entry * 1.07, 4)

    print(f"Trade: {pair}")
    print(f"  Entry:  ${entry:.4f}")
    print(f"  Stop:   ${stop:.4f}  (-2%)")
    print(f"  TP:     ${tp:.4f}  (+7%)")
    print()

    print("Cancelling existing stop orders...")
    cancel_triggers(pair)
    print()

    print("Setting SL trigger (stop=loss)...")
    set_trigger(pair, "sell", stop, amount, "loss")

    print("Setting TP trigger (stop=entry)...")
    set_trigger(pair, "sell", tp, amount, "entry")

    print()
    show_triggers(pair)


if __name__ == "__main__":
    main()
