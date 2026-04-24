import ccxt, pandas as pd, numpy as np
from datetime import datetime

exchange = ccxt.kucoin({'enableRateLimit': True})

pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'DOGE/USDT',
         'ADA/USDT', 'AVAX/USDT', 'LINK/USDT', 'DOT/USDT', 'NEAR/USDT']

results = []
for symbol in pairs:
    try:
        candles = exchange.fetch_ohlcv(symbol, '1h', limit=100)
        if not candles or len(candles) < 50:
            continue
        df = pd.DataFrame(candles, columns=['ts','open','high','low','close','volume'])
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['volume'] = df['volume'].astype(float)

        close = df['close']
        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

        # EMA
        ema12 = close.ewm(span=12).mean()

        # ATR
        tr1 = df['high'] - df['low']
        tr2 = (df['high'] - close.shift(1)).abs()
        tr3 = (df['low'] - close.shift(1)).abs()
        atr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()

        # ADX simplified
        plus_dm = df['high'].diff()
        minus_dm = -df['low'].diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_s = tr.rolling(14).mean()
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr_s)
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr_s)
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.rolling(14).mean()

        # Volume
        vol_sma = df['volume'].rolling(20).mean()
        vol_ratio = df['volume'].iloc[-1] / vol_sma.iloc[-1] if vol_sma.iloc[-1] > 0 else 1

        price = close.iloc[-1]
        rsi_val = rsi.iloc[-1]
        adx_val = adx.iloc[-1]
        ema_dist = (price - ema12.iloc[-1]) / ema12.iloc[-1] * 100

        # Simple regime
        ma20 = close.rolling(20).mean().iloc[-1]

        if adx_val >= 30 and price > ma20:
            regime = 'STRONG_TREND'
            direction = 'LONG'
        elif adx_val >= 20 and price > ma20:
            regime = 'TRENDING'
            direction = 'LONG'
        elif price > ma20 * 0.98 and price < ma20 * 1.02:
            regime = 'RANGE_BOUND'
            direction = 'NEUTRAL'
        else:
            regime = 'CHOPPY'
            direction = 'NEUTRAL'

        # Simple score
        score = 0
        if direction == 'LONG':
            if 35 <= rsi_val <= 55:
                score += 30
            elif rsi_val < 35:
                score += 20
            if vol_ratio >= 1.5:
                score += 25
            elif vol_ratio >= 1.0:
                score += 10
            if ema_dist > 0:
                score += 15
            if adx_val >= 25:
                score += 15

        results.append({
            'symbol': symbol, 'price': price, 'rsi': rsi_val, 'adx': adx_val,
            'regime': regime, 'direction': direction, 'score': score,
            'vol_ratio': vol_ratio, 'ema_dist': ema_dist
        })
    except Exception as e:
        print(f'{symbol}: {e}')

results.sort(key=lambda x: x['score'], reverse=True)

print(f'Pairs analyzed: {len(results)}')
print(f'Time: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}')
print()
print(f"{'Symbol':<12} {'Regime':<14} {'Dir':<6} {'Score':>6} {'RSI':>6} {'ADX':>5} {'Vol':>5}")
print('-' * 60)
for r in results:
    print(f"{r['symbol']:<12} {r['regime']:<14} {r['direction']:<6} {r['score']:>6.0f} {r['rsi']:>6.1f} {r['adx']:>5.1f} {r['vol_ratio']:>5.2f}x")

print()
signals = [r for r in results if r['score'] >= 40]
if signals:
    print(f'SIGNALS ({len(signals)}):')
    for s in signals:
        entry = s['price']
        stop = entry * 0.98
        tp = entry * 1.07
        print(f"  {s['symbol']}: {s['direction']} | Score {s['score']:.0f} | Entry ${entry:,.4f} | Stop ${stop:,.4f} | TP ${tp:,.4f}")
else:
    print('No signals this cycle (score >= 40)')
    print('Top 3 closest to triggering:')
    for r in results[:3]:
        entry = r['price']
        stop = entry * 0.98
        tp = entry * 1.07
        print(f"  {r['symbol']}: {r['direction']} | Score {r['score']:.0f} | Entry ${entry:,.4f} | Stop ${stop:,.4f} | TP ${tp:,.4f} | RSI={r['rsi']:.1f} Vol={r['vol_ratio']:.2f}x")
