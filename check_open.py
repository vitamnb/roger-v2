import requests, json
r = requests.get('http://127.0.0.1:8080/api/v1/status', auth=('roger', 'RogerDryRun2026!'))
for t in r.json():
    print(f"{t['pair']}: entry={t['open_rate']} cur={t['current_rate']} pnl={t['profit_pct']}% sl_dist={t.get('stoploss_current_dist_pct','?')}")
