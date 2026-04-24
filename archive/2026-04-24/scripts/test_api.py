import requests, json
r = requests.get("https://api.kucoin.com/api/v1/market/candles?symbol=OFC-USDT&type=1hour&limit=3")
print(r.status_code)
print(r.json())
