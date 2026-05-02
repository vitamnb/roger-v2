import json

with open(r'C:\Users\vitamnb\.openclaw\freqtrade\dashboard\static\data.json') as f:
    d = json.load(f)

p = d['portfolio']
h = d['market_health']

print('=== ROGER COMMAND CENTER ===')
print('Updated:', d.get('last_update', 'N/A')[:19])
print()
print('--- Portfolio ---')
print('Bots:', str(p['bots_running']) + '/' + str(p['bots_total']), 'running')
print('Open positions:', p['open_positions'])
print('Total trades:', p['total_trades'])
print('Total P&L: $' + str(round(p['total_profit'], 2)))
print()
print('--- Market Health ---')
print('Regime:', str(h.get('regime', '?')).upper())
print('BTC: $' + str(round(h.get('btc_price', 0), 0)))
print('Avg RSI:', h.get('avg_rsi', 0))
print('Volume ratio:', h.get('avg_volume_ratio', 0), 'x')
print('Pairs above EMA20:', h.get('pct_above_ema20', 0), '%')
print('Oversold pairs:', h.get('oversold_count', 0) + h.get('very_oversold_count', 0))
print('Fear/Greed:', h.get('fear_greed', 0), '/100')
print()
print('--- Trigger Proximity ---')
for t in d.get('trigger_proximity', [])[:5]:
    status = t['status'].upper()
    print(t['pair'] + ': ' + str(t['combined']) + '% (' + status + ') RSI=' + str(t['rsi']) + ' Vol=' + str(t['volume_ratio']) + 'x')
print()
print('--- Bot Status ---')
for b in d.get('bots', []):
    status = 'RUNNING' if b['running'] else 'STOPPED'
    print(b['name'] + ': ' + status + ' | Trades: ' + str(b['total_trades']) + ' | P&L: $' + str(round(b['total_profit'], 2)))
