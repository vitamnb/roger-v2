"""Check BTC.D and current market cycle phase."""
import requests, json

# BTC Dominance via CoinGecko
r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
if r.status_code == 200:
    data = r.json().get("data", {})
    btc_d = data.get("market_cap_percentage", {}).get("btc", None)
    total_mcap = data.get("total_market_cap", {}).get("usd", None)
    active_alts = data.get("active_cryptocurrencies", 0)
    print(f"BTC Dominance: {btc_d:.1f}%")
    print(f"Total market cap: ${total_mcap/1e12:.2f}T")
    print(f"Active coins: {active_alts}")
else:
    print(f"CoinGecko error: {r.status_code}")

# BTC price now
r2 = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true", timeout=10)
if r2.status_code == 200:
    btc = r2.json().get("bitcoin", {})
    print(f"\nBTC price: ${btc.get('usd', 'N/A'):,}")
    print(f"BTC 24h change: {btc.get('usd_24h_change', 0):+.2f}%")
