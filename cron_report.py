import sys
sys.path.insert(0, r"C:\Users\vitamnb\.openclaw\freqtrade")
import scanner as s
import numpy as np

exchange = s.get_kucoin()
watchlist = s.load_daily_watchlist(top_n=50)
pairs = [s[0] for s in watchlist] if watchlist else s.get_top_pairs(exchange, limit=50)

regimes = []
for sym in pairs:
    df = s.fetch_ohlcv(exchange, sym, '1h')
    if df.empty:
        continue
    df = s.add_indicators(df)
    r = s.detect_regime(df)
    if r is None:
        continue
    score, conf = s.score_signal(df, r)
    regimes.append((sym, r, score or 0, conf, df))
    if len(regimes) >= 42:
        break

# Majors bias
print("=" * 50)
print("[MAJORS BIAS] 1h timeframe")
for sym in s.MAJORS:
    df = s.fetch_ohlcv(exchange, sym, '1h')
    if df.empty:
        continue
    df = s.add_indicators(df)
    r = s.detect_regime(df)
    if r is None:
        continue
    chain = s.CHAIN_TAGS.get(sym, "Unknown")
    sig = "++" if r["regime"] == "STRONG_TREND" and r["direction"] == "LONG" else \
          "+" if r["regime"] == "TRENDING" and r["direction"] == "LONG" else \
          "--" if r["regime"] == "STRONG_TREND" and r["direction"] == "SHORT" else \
          "-" if r["regime"] == "TRENDING" and r["direction"] == "SHORT" else "~"
    print(f"  {sym:<12} {r['regime']:<16} {r['direction']:<6} ADX={r['adx']:>5.1f} RSI={r['rsi']:>5.1f} [{sig}]")

# Regime overview top 10 by ADX
print()
print("=" * 50)
print("[REGIME OVERVIEW] Top 10 by ADX")
print(f"{'Pair':<14} {'Regime':<16} {'Dir':<6} {'ADX':>5} {'RSI':>5} {'Trend%':>7} {'Chop%':>6} {'Score':>6}")
for sym, r, sc, _, _ in sorted(regimes, key=lambda x: -x[1]["adx"])[:10]:
    print(f"{sym:<14} {r['regime']:<16} {r['direction']:<6} {r['adx']:>5.1f} {r['rsi']:>5.1f} {r['trend_pct']:>6.1f}% {r['chop_pct']:>5.1f}% {sc:>6}")

# Signals
signals = [(sym, r, sc, conf, df) for sym, r, sc, conf, df in regimes if sc and sc >= 40]
signals.sort(key=lambda x: -x[2])

print()
print("=" * 50)
if signals:
    print("[SIGNALS]")
    for sym, r, sc, conf, df in signals[:10]:
        entry = float(df.iloc[-1]["close"])
        sl = round(entry * 0.98, 8)
        tp = round(entry * 1.07, 8)
        confs = ", ".join(list(conf.keys())[:6])
        print(f"  {sym}")
        print(f"    Regime: {r['regime']} | Dir: {r['direction']} | Score: {sc}")
        print(f"    Entry:  ${entry:.6f}")
        print(f"    Stop:   ${sl:.6f}  (-2.0%)")
        print(f"    TP:     ${tp:.6f}  (+7.0%)")
        print(f"    Conf:   {confs}")
else:
    print("[!] No signals found (min score: 40)")
    print()
    print("[APPROACHING -- highest scores below threshold]")
    near = [(sym, r, sc, df) for sym, r, sc, _, df in regimes if 0 < sc < 40]
    near.sort(key=lambda x: -x[2])
    for sym, r, sc, df in near[:3]:
        entry = float(df.iloc[-1]["close"])
        sl = round(entry * 0.98, 8)
        tp = round(entry * 1.07, 8)
        print(f"  {sym:<14} score={sc:<4} {r['regime']:<16} {r['direction']:<6} RSI={r['rsi']:>5.1f}")
        print(f"    Entry: ${entry:.6f}  SL: ${sl:.6f}  TP: ${tp:.6f}")
