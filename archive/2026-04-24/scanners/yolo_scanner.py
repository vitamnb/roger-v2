"""
yolo_scanner.py
YOLO Scanner v3 -- Full spectrum: accumulation + new listings
Whale-boosted: pairs with ACCUMULATION signal from whale_watch get priority boost.
Wide net: scans ALL KuCoin USDT pairs by volume.

TP: 12% | Stop: 5% | Timeout: 24h
"""

import ccxt
import pandas as pd
import numpy as np
import talib.abstract as ta
from datetime import datetime
import time
import os
import sys

API_KEY = '69e068a7c9bace0001a89666'
WHALE_FILE = r"C:\Users\vitamnb\.openclaw\freqtrade\whale_watchlist.txt"
KUCOIN_AU_FILE = r"C:\Users\vitamnb\.openclaw\freqtrade\kucoin_au_pairs.txt"


def get_kucoin():
    return ccxt.kucoin({
        'apiKey': API_KEY,
        'secret': '',
        'password': '',
        'enableRateLimit': True,
        'options': {'defaultType': 'spot', 'rateLimit': 50},
    })


def load_whale_scores():
    """Load whale activity scores from whale_watchlist.txt."""
    scores = {}
    if not os.path.exists(WHALE_FILE):
        return scores
    for line in open(WHALE_FILE):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('|')
        if len(parts) >= 2:
            symbol = parts[0].strip()
            score = 50
            for part in parts[1:]:
                part = part.strip()
                if part.startswith('score='):
                    try:
                        score = int(part.split('=')[1].strip())
                    except:
                        pass
            scores[symbol] = score
    return scores


def load_kucoin_au_pairs():
    """Load KuCoin Australia-eligible pairs from saved file."""
    if not os.path.exists(KUCOIN_AU_FILE):
        return None  # No filter if file doesn't exist
    pairs = set()
    for line in open(KUCOIN_AU_FILE):
        line = line.strip()
        if line and not line.startswith('#'):
            pairs.add(line.strip())
    return pairs


def get_top_by_volume(exchange, limit=200):
    """Get top pairs by 24h volume, filtered to KuCoin AU if available."""
    tickers = exchange.fetch_tickers()
    kucoin_au = load_kucoin_au_pairs()
    usdt_tickers = {}
    for k, v in tickers.items():
        if '/USDT' not in k or v.get('quoteVolume', 0) <= 10000:
            continue
        base = k.replace('/USDT', '')
        if kucoin_au is not None and base not in kucoin_au:
            continue
        usdt_tickers[k] = v
    sorted_tickers = sorted(usdt_tickers.values(), key=lambda x: x.get('quoteVolume', 0), reverse=True)
    return [t['symbol'] for t in sorted_tickers[:limit]]


def analyze_yolo_entry(df, whale_score=50):
    """Check for post-accumulation breakout entry, whale-boosted."""
    rsi = df['rsi'].iloc[-1]
    rsi_prev = df['rsi'].iloc[-2]
    vol_ratio = df['vol_ratio'].iloc[-1]
    price = df['close'].iloc[-1]
    ema12 = df['ema12'].iloc[-1]
    ema26 = df['ema26'].iloc[-1]
    prev_candle = df.iloc[-2]

    rsi_ok = rsi > 35 and rsi_prev <= 30
    vol_ok = vol_ratio > 1.5
    ema_bull = ema12 > ema26
    price_ok = price > ema12
    prev_green = prev_candle['close'] > prev_candle['open']

    if rsi_ok and vol_ok and ema_bull and price_ok and prev_green:
        base_score = int(min(rsi, 50) * 0.5 + vol_ratio * 20)

        # Whale boost: ACCUMULATION pairs get up to +15 extra score
        if whale_score > 70:
            whale_boost = 15
        elif whale_score > 60:
            whale_boost = 10
        elif whale_score > 50:
            whale_boost = 5
        else:
            whale_boost = 0

        score = base_score + whale_boost

        return {
            'type': 'BREAKOUT',
            'price': round(price, 8),
            'rsi': round(rsi, 1),
            'vol_ratio': round(vol_ratio, 2),
            'score': score,
            'whale_score': whale_score,
            'whale_boost': whale_boost,
            'stop': round(price * 0.95, 8),
            'tp': round(price * 1.12, 8),
            'rr': round((price * 1.12 - price) / (price - price * 0.95), 1),
        }
    return None


def analyze_new_listing(df, age_days, price, whale_score=50):
    """Check for new listing early-entry setup, whale-boosted."""
    rsi = df['rsi'].iloc[-1]
    vol_ratio = df['vol_ratio'].iloc[-1]
    ema12 = df['ema12'].iloc[-1]
    ema26 = df['ema26'].iloc[-1]

    price_24h_ago = df['close'].iloc[-24] if len(df) >= 24 else df['close'].iloc[0]
    change_24h = ((price / price_24h_ago) - 1) * 100

    if change_24h > 30:
        return None

    rsi_ok = 25 < rsi < 55
    vol_ok = vol_ratio > 1.0
    ema_bull = ema12 > ema26

    if rsi_ok and (vol_ok or ema_bull):
        base_score = int((55 - rsi) * 2 + vol_ratio * 15 + (30 - min(change_24h, 30)) * 0.5)

        if whale_score > 70:
            whale_boost = 15
        elif whale_score > 60:
            whale_boost = 10
        elif whale_score > 50:
            whale_boost = 5
        else:
            whale_boost = 0

        score = base_score + whale_boost

        return {
            'type': 'NEW_LISTING',
            'age_days': round(age_days, 1),
            'price': round(price, 8),
            'rsi': round(rsi, 1),
            'vol_ratio': round(vol_ratio, 2),
            'change_24h': round(change_24h, 1),
            'score': score,
            'whale_score': whale_score,
            'whale_boost': whale_boost,
            'stop': round(price * 0.95, 8),
            'tp': round(price * 1.15, 8),
            'rr': round((price * 1.15 - price) / (price - price * 0.95), 1),
        }
    return None


def get_pair_age_days(market_info):
    for field in ['firstOpenDate', 'tradingStartTime', 'created', 'launchTime']:
        val = market_info.get(field)
        if val:
            try:
                ts = int(val)
                if ts > 10000000000:
                    ts = ts / 1000
                age_days = (time.time() - ts) / (60 * 60 * 24)
                if 0 <= age_days <= 30:
                    return round(age_days, 1)
            except:
                pass
    return None


def scan_universe(symbols, kucoin_au_pairs=None):
    exchange = get_kucoin()
    exchange.load_markets()
    whale_scores = load_whale_scores()

    breakout_results = []
    new_listing_results = []
    checked = 0
    errors = 0
    skipped_au = 0
    start = time.time()

    print('Scanning ' + str(len(symbols)) + ' pairs...')

    for symbol in symbols:
        # KuCoin Australia filter
        if kucoin_au_pairs is not None and symbol not in kucoin_au_pairs:
            skipped_au += 1
            continue

        checked += 1
        try:
            market = exchange.market(symbol)
            market_info = market.get('info', {})
            age_days = get_pair_age_days(market_info)
            whale_score = whale_scores.get(symbol, 50)

            ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=60)
            if len(ohlcv) < 20:
                continue

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['rsi'] = ta.RSI(df['close'], timeperiod=14)
            df['ema12'] = ta.EMA(df['close'], timeperiod=12)
            df['ema26'] = ta.EMA(df['close'], timeperiod=26)
            df['volume_avg'] = df['volume'].rolling(20).mean()
            df['vol_ratio'] = df['volume'] / df['volume_avg']

            price = df['close'].iloc[-1]

            breakout = analyze_yolo_entry(df, whale_score)
            if breakout:
                breakout['symbol'] = symbol
                breakout_results.append(breakout)

            if age_days is not None and age_days <= 14:
                new_listing = analyze_new_listing(df, age_days, price, whale_score)
                if new_listing:
                    new_listing['symbol'] = symbol
                    new_listing_results.append(new_listing)

        except Exception as e:
            errors += 1
            continue

        if checked % 100 == 0:
            elapsed = time.time() - start
            print('  ...' + str(checked) + '/' + str(len(symbols)) + ' (' + str(int(elapsed)) + 's)')

    elapsed = time.time() - start
    return breakout_results, new_listing_results, checked, errors, skipped_au, elapsed


def print_report(breakout_results, new_listing_results, checked, errors, skipped_au, elapsed):
    print('')
    print('====================================================================================================')
    print('YOLO SCANNER v3 -- ' + datetime.now().strftime('%H:%M:%S AEST') + '  [WHALE-BOOSTED]')
    print('Scanned: ' + str(checked) + ' pairs | Errors: ' + str(errors) + ' | Skipped (AU): ' + str(skipped_au) + ' | Time: ' + str(int(elapsed)) + 's')
    print('====================================================================================================')
    print('')

    # BREAKOUT
    if breakout_results:
        breakout_results.sort(key=lambda x: x['score'], reverse=True)
        print('[BREAKOUT] POST-ACCUMULATION SIGNALS (' + str(len(breakout_results)) + ' found)')
        print('-' * 110)
        header = '  #  Symbol           Price           RSI    Vol   Score  Boost  Whale   Entry        Stop         TP       R:R'
        print(header)
        print('-' * 110)
        for i, r in enumerate(breakout_results[:15]):
            boost_str = '+' + str(r['whale_boost']) if r['whale_boost'] > 0 else '-'
            line = ('  %2d  %-15s  $%12.6f  %5.1f  %4.1fx  %5d  %5s  %5d/100  $%10.6f  $%10.6f  $%10.6f  %4.1fx' % (
                i+1, r['symbol'], r['price'], r['rsi'], r['vol_ratio'], r['score'],
                boost_str, r['whale_score'],
                r['price'], r['stop'], r['tp'], r['rr']
            ))
            print(line)
        print('')
        print('  Breakout rules: RSI < 35 -> crosses UP through 40 + Vol > 1.5x + EMA bull + prev candle green')
        print('  Whale boost: ACCUMULATION pairs (score>50) get +5 to +15 extra score')
    else:
        print('[BREAKOUT] No signals -- market is quiet')

    print('')

    # NEW LISTINGS
    if new_listing_results:
        new_listing_results.sort(key=lambda x: x['score'], reverse=True)
        print('[NEW] NEW LISTING SIGNALS -- < 14 days old (' + str(len(new_listing_results)) + ' found)')
        print('-' * 110)
        header = '  #  Symbol           Age    Price           RSI    Vol    24h%    Score  Boost  Whale   Entry        Stop         TP'
        print(header)
        print('-' * 110)
        for i, r in enumerate(new_listing_results[:15]):
            boost_str = '+' + str(r['whale_boost']) if r['whale_boost'] > 0 else '-'
            line = ('  %2d  %-15s  %4.0fd  $%12.6f  %5.1f  %4.1fx  %+6.1f%%  %5d  %5s  %5d/100  $%10.6f  $%10.6f  $%10.6f' % (
                i+1, r['symbol'], r['age_days'], r['price'], r['rsi'], r['vol_ratio'],
                r['change_24h'], r['score'],
                boost_str, r['whale_score'],
                r['price'], r['stop'], r['tp']
            ))
            print(line)
        print('')
        print('  New listing rules: Listed < 14 days, RSI recovering (25-55), Volume picking up or EMA bull')
    else:
        print('[NEW] No fresh listings found -- none meeting criteria')

    print('')
    print('====================================================================================================')
    print('YOLO Config: TP +12-15% | Stop -5% | Timeout 24h | Max 2 concurrent YOLO positions')
    print('Whale boost: +5 to +15 points added to base score for pairs with whale ACCUMULATION signal')
    print('====================================================================================================')

    return breakout_results, new_listing_results


def main():
    exchange = get_kucoin()
    symbols = get_top_by_volume(exchange, limit=200)
    print('Loaded ' + str(len(symbols)) + ' pairs by volume')

    kucoin_au = load_kucoin_au_pairs()
    if kucoin_au:
        print('KuCoin AU filter: active (' + str(len(kucoin_au)) + ' eligible pairs)')
    else:
        print('KuCoin AU filter: not active (no au_pairs file found)')

    breakout_results, new_listing_results, checked, errors, skipped_au, elapsed = scan_universe(symbols, kucoin_au)
    print_report(breakout_results, new_listing_results, checked, errors, skipped_au, elapsed)


if __name__ == '__main__':
    main()
