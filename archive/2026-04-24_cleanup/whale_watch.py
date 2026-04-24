"""
whale_watch.py
KuCoin order book scanner — whale activity detection.
Flags pairs with large buy/sell walls, accumulation/distribution imbalance.

Run: python whale_watch.py [top_n]
Output: ranked pairs with whale signals
"""

import sys
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime


API_KEY = '69e068a7c9bace0001a89666'
TOP_N = 60
DEPTH_LEVEL = 20   # KuCoin requires 20 or 100
THRESHOLD_BS = 50000  # USDT minimum for a "large" wall


def get_kucoin():
    return ccxt.kucoin({
        'apiKey': API_KEY,
        'secret': '',
        'password': '',
        'enableRateLimit': True,
        'options': {'defaultType': 'spot', 'rateLimit': 50},
    })


def get_top_pairs(exchange, n=200):
    tickers = exchange.fetch_tickers()
    usdt = {k: v for k, v in tickers.items()
            if '/USDT' in k and v.get('quoteVolume', 0) > 50000}
    sorted_usdt = sorted(usdt.values(), key=lambda x: x.get('quoteVolume', 0), reverse=True)
    return [t['symbol'] for t in sorted_usdt[:n]]


def analyze_order_book(book, price):
    """
    Analyze a single pair's order book.
    Returns dict with whale metrics.
    """
    bids = book.get('bids', [])
    asks = book.get('asks', [])

    if not bids or not asks:
        return None

    buy_walls = []
    sell_walls = []
    total_bid_vol = 0.0
    total_ask_vol = 0.0

    for price_level, size in bids[:DEPTH_LEVEL]:
        usd_val = price_level * size
        total_bid_vol += usd_val
        if usd_val >= THRESHOLD_BS:
            buy_walls.append({'price': price_level, 'size': size, 'usd': usd_val})

    for price_level, size in asks[:DEPTH_LEVEL]:
        usd_val = price_level * size
        total_ask_vol += usd_val
        if usd_val >= THRESHOLD_BS:
            sell_walls.append({'price': price_level, 'size': size, 'usd': usd_val})

    # Imbalance: positive = more buy pressure
    imbalance = (total_bid_vol - total_ask_vol) / (total_bid_vol + total_ask_vol + 1e-9)

    # Distance to nearest large wall
    nearest_buy_dist_pct = None
    nearest_sell_dist_pct = None

    if buy_walls:
        below = [w for w in buy_walls if w['price'] < price]
        if below:
            dists = [(price - w['price']) / price * 100 for w in below]
            nearest_buy_dist_pct = min(dists)

    if sell_walls:
        above = [w for w in sell_walls if w['price'] > price]
        if above:
            dists = [(w['price'] - price) / price * 100 for w in above]
            nearest_sell_dist_pct = min(dists)

    # Whale accumulation/distribution signal
    near_buy = sum(w['usd'] for w in buy_walls
                  if 0 < (price - w['price']) / price * 100 <= 2.0)
    near_sell = sum(w['usd'] for w in sell_walls
                   if 0 < (w['price'] - price) / price * 100 <= 2.0)

    whale_score = 0
    whale_signal = "NEUTRAL"

    if near_buy > near_sell * 2:
        whale_score = min(int(np.log1p(near_buy / 1000) * 10), 100)
        whale_signal = "ACCUMULATION"
    elif near_sell > near_buy * 2:
        whale_score = -min(int(np.log1p(near_sell / 1000) * 10), 100)
        whale_signal = "DISTRIBUTION"

    # Support/resistance strength
    support_strength = "WEAK"
    if nearest_buy_dist_pct is not None and nearest_buy_dist_pct < 1.0:
        support_strength = "STRONG"
    elif nearest_buy_dist_pct is not None and nearest_buy_dist_pct < 2.0:
        support_strength = "MODERATE"

    resistance_strength = "WEAK"
    if nearest_sell_dist_pct is not None and nearest_sell_dist_pct < 1.0:
        resistance_strength = "STRONG"
    elif nearest_sell_dist_pct is not None and nearest_sell_dist_pct < 2.0:
        resistance_strength = "MODERATE"

    return {
        'total_bid_vol': total_bid_vol,
        'total_ask_vol': total_ask_vol,
        'imbalance': imbalance,
        'buy_wall_count': len(buy_walls),
        'sell_wall_count': len(sell_walls),
        'nearest_buy_dist_pct': nearest_buy_dist_pct,
        'nearest_sell_dist_pct': nearest_sell_dist_pct,
        'whale_signal': whale_signal,
        'whale_score': whale_score,
        'support_strength': support_strength,
        'resistance_strength': resistance_strength,
        'buy_walls': buy_walls,
        'sell_walls': sell_walls,
    }


def trade_score(wa):
    """Composite score 0-100 for how favorable the order book is for a LONG."""
    if wa is None:
        return 0

    score = 50

    if wa['whale_signal'] == 'ACCUMULATION':
        score += min(wa['whale_score'] * 0.5, 30)
    elif wa['whale_signal'] == 'DISTRIBUTION':
        score -= min(abs(wa['whale_score']) * 0.5, 30)

    if wa['support_strength'] == 'STRONG':
        score += 15
    elif wa['support_strength'] == 'MODERATE':
        score += 7

    if wa['resistance_strength'] == 'STRONG':
        score -= 10
    elif wa['resistance_strength'] == 'MODERATE':
        score -= 5

    return max(0, min(100, round(score)))


def print_report(results):
    print("")
    print("==================================================================================================")
    print(f"WHALE WATCH  |  KuCoin USDT  |  {datetime.now().strftime('%H:%M AEST')}")
    print(f"Pairs checked: {len(results)}  |  Wall threshold: ${THRESHOLD_BS:,} USDT")
    print("==================================================================================================")
    print("")

    actionable = [r for r in results if r['trade_score'] > 50 or r['wa']['support_strength'] != 'WEAK']
    actionable.sort(key=lambda x: x['trade_score'], reverse=True)

    if not actionable:
        print("No strong whale activity detected. Market is quiet.")
        print("")
        return

    print(f"PAIRS WITH WHALE SIGNALS ({len(actionable)} found)")
    print("-" * 110)
    print("  Symbol           Price           BuyWalls  SellWalls  Imbal%    Support  Resist   Score  Signal")
    print("-" * 110)

    for r in actionable[:20]:
        wa = r['wa']
        price = r['price']
        imbalance_pct = wa['imbalance'] * 100
        print(
            "  %-15s  $%10.5f  %5d       %5d       %+6.2f%%  %-8s  %-8s  %5d   %s"
            % (
                r['symbol'],
                price,
                wa['buy_wall_count'],
                wa['sell_wall_count'],
                imbalance_pct,
                wa['support_strength'],
                wa['resistance_strength'],
                r['trade_score'],
                wa['whale_signal'],
            )
        )

        # Show nearby large buy walls
        for w in wa['buy_walls'][:3]:
            dist = (r['price'] - w['price']) / r['price'] * 100
            if dist < 3:
                print("    [BUY]  $%-12.0f  @ $%.5f  (%.2f%% below)" % (w['usd'], w['price'], dist))

        # Show nearby large sell walls
        for w in wa['sell_walls'][:3]:
            dist = (w['price'] - r['price']) / r['price'] * 100
            if dist < 3:
                print("    [SELL] $%-12.0f  @ $%.5f  (%.2f%% above)" % (w['usd'], w['price'], dist))

        print()

    print("HOW TO READ:")
    print("  Score 70+  = high-conviction whale-supported long entry")
    print("  Score 50-69 = neutral whale activity, use with other signals")
    print("  Score < 50 = no strong whale interest, proceed with caution")
    print("  ACCUMULATION = large buy walls nearby, bullish pressure")
    print("  DISTRIBUTION = large sell walls nearby, bearish pressure")
    print("  STRONG support = buy wall < 1%% below current price")
    print("  STRONG resist = sell wall < 1%% above current price")
    print("")
    print("==================================================================================================")


def main():
    top_n = int(sys.argv[1]) if len(sys.argv) > 1 else TOP_N

    print("Connecting to KuCoin...")
    ex = get_kucoin()
    ex.load_markets()
    pairs = get_top_pairs(ex, n=top_n)
    print("Loaded %d pairs by volume" % len(pairs))

    results = []
    checked = 0
    errors = 0

    for symbol in pairs:
        checked += 1
        try:
            book = ex.fetch_order_book(symbol, DEPTH_LEVEL)
            ticker = ex.fetch_ticker(symbol)
            price = ticker['last']
            wa = analyze_order_book(book, price)
            if wa is None:
                continue
            ts = trade_score(wa)
            results.append({
                'symbol': symbol,
                'price': price,
                'wa': wa,
                'trade_score': ts,
            })
        except Exception as e:
            errors += 1
            continue

        if checked % 20 == 0:
            print("  ... %d/%d pairs checked" % (checked, len(pairs)))

    results.sort(key=lambda x: x['trade_score'], reverse=True)
    print("Done. %d checked, %d errors." % (checked, errors))
    print_report(results)

    # Save top pairs to file
    out_path = "C:\\Users\\vitamnb\\.openclaw\\freqtrade\\whale_watchlist.txt"
    with open(out_path, 'w') as f:
        f.write("# Whale Watch List  |  %s\n" % datetime.now().strftime('%Y-%m-%d %H:%M'))
        f.write("# Top pairs by whale activity score\n\n")
        for r in results[:30]:
            wa = r['wa']
            f.write("%s | score=%d | %s | support=%s | resist=%s\n"
                    % (r['symbol'], r['trade_score'], wa['whale_signal'],
                       wa['support_strength'], wa['resistance_strength']))
    print("Saved to: " + out_path)


if __name__ == '__main__':
    main()
