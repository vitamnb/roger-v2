import ccxt
import numpy as np

ex = ccxt.kucoin({'options':{'defaultType':'spot'},'enableRateLimit':True})
ex.load_markets()

sym = 'ENJ/USDT'
book = ex.fetch_order_book(sym, 20)
ticker = ex.fetch_ticker(sym)
price = ticker['last']

THRESHOLD = 50000
DEPTH = 20
entry = 0.05838
tp_partial = entry * 1.035
tp_full = entry * 1.07
stop = entry * 0.97

print('=== ENJ/USDT -- Order Book Analysis ===')
print('Current price:  $%.6f' % price)
print('Our entry:      $%.6f' % entry)
print('Partial TP:    $%.6f  (+3.5%%)' % tp_partial)
print('Full TP:       $%.6f  (+7.0%%)' % tp_full)
print('Hard stop:     $%.6f  (-3.0%%)' % stop)
print()

bids = book['bids']
asks = book['asks']
total_bid = sum(p*s for p,s in bids[:DEPTH])
total_ask = sum(p*s for p,s in asks[:DEPTH])
imbalance = (total_bid - total_ask) / (total_bid + total_ask)

print('ORDER BOOK SUMMARY')
print('Total bid vol (top %d levels):  $%.0f' % (DEPTH, total_bid))
print('Total ask vol (top %d levels):  $%.0f' % (DEPTH, total_ask))
print('Bid/Ask imbalance:              %+.2f%%  (%s)' % (imbalance*100, 'BUY PRESSURE' if imbalance>0 else 'SELL PRESSURE'))
print()

buy_walls = []
sell_walls = []
for p,s in bids[:DEPTH]:
    u = p*s
    if u >= THRESHOLD:
        buy_walls.append({'price':p,'size':s,'usd':u})
for p,s in asks[:DEPTH]:
    u = p*s
    if u >= THRESHOLD:
        sell_walls.append({'price':p,'size':s,'usd':u})

print('LARGE BUY WALLS (>$50K):')
if not buy_walls:
    print('  None')
for w in buy_walls:
    dist = (price - w['price'])/price*100
    print('  $%10.0f  @ $%.6f  (%.2f%% below)' % (w['usd'], w['price'], dist))

print()
print('LARGE SELL WALLS (>$50K):')
if not sell_walls:
    print('  None')
for w in sell_walls:
    dist = (w['price'] - price)/price*100
    print('  $%10.0f  @ $%.6f  (%.2f%% above)' % (w['usd'], w['price'], dist))

print()
print('NEARBY WALLS vs OUR TRADE LEVELS:')
for label, lvl in [('Partial TP (+3.5%%)', tp_partial), ('Full TP (+7.0%%)', tp_full)]:
    nearby_sells = [w for w in sell_walls if 0 < (w['price']-lvl)/lvl*100 < 2.0]
    print('  %s @ $%.6f:' % (label, lvl))
    if nearby_sells:
        for w in nearby_sells:
            print('    SELL wall $%.0f (%.2f%% above TP)' % (w['usd'], (w['price']-lvl)/lvl*100))
    else:
        print('    Clear -- no resistance walls nearby')

nearby_stops = [w for w in buy_walls if 0 < (price-w['price'])/price*100 < 3.0]
print()
print('  Stop level @ $%.6f:' % stop)
if nearby_stops:
    for w in nearby_stops:
        print('    BUY wall $%.0f at $%.6f -- potential stop hunt' % (w['usd'], w['price']))
else:
    print('    Clean -- no buy walls nearby, stop is in open air')

# Whale score
near_buy = sum(w['usd'] for w in buy_walls if 0 < (price-w['price'])/price*100 <= 2.0)
near_sell = sum(w['usd'] for w in sell_walls if 0 < (w['price']-price)/price*100 <= 2.0)
score = 50
if near_buy > near_sell * 2:
    sig = 'ACCUMULATION'
    score += min(int(np.log1p(near_buy/1000)*10)*0.5, 30)
elif near_sell > near_buy * 2:
    sig = 'DISTRIBUTION'
    score -= min(int(np.log1p(near_sell/1000)*10)*0.5, 30)
else:
    sig = 'NEUTRAL'

print()
print('WHALE SIGNAL: %s  |  Score: %d/100' % (sig, score))
print()
print('VERDICT:')
if sig == 'ACCUMULATION':
    print('  + Whale accumulation nearby -- entry is supported')
elif sig == 'DISTRIBUTION':
    print('  - Distribution bias -- headwind at entry level')
else:
    print('  ~ Quiet book -- no strong whale signal either way')
