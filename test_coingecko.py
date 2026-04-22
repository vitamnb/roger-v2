import requests, json
from datetime import datetime

url = "https://api.coingecko.com/api/v3/global"
r = requests.get(url, timeout=10)
data = r.json().get("data", {})
mcp = data.get("market_cap_percentage", {})

print("Market cap percentages available:")
for k, v in mcp.items():
    print(f"  {k}: {v:.1f}%")
print()
print(f"Total market cap: ${data.get('total_market_cap',{}).get('usd',0)/1e12:.2f}T")
print(f"Stablecoins: {mcp.get('usdt',0) + mcp.get('usdc',0):.1f}% combined (usdt+usdc)")