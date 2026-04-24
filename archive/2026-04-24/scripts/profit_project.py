"""EMA strategy profit projection — $1,000 starting capital."""
import math

# === ENTRY E: EMA pullback + green candle ===
# 168 trades over 90 days, WR 39.9%, Exp 0.940% per trade
# Win: 5%, Loss: ~2% (TP 5%, stop 2%)

e_trades = 168
e_wr = 0.399
e_tp = 0.05
e_stop = 0.02
starting_cap = 1000
risk_pct = 0.02  # 2% risk per trade

e_wins = int(e_trades * e_wr)
e_losses = e_trades - e_wins

print("=" * 65)
print("ENTRY E — EMA Pullback + Green Candle")
print("=" * 65)
print(f"Trades: {e_trades} over 90 days")
print(f"Win rate: {e_wr*100:.1f}%  ({e_wins} wins / {e_losses} losses)")
print(f"Win: +5%  |  Loss: -2%")
print()

cap = starting_cap
for i in range(e_trades):
    risk_amt = cap * risk_pct
    if i < e_wins:
        # Winner: +5%
        cap += risk_amt * (e_tp / e_stop)
    else:
        # Loser: -2%
        cap -= risk_amt

print(f"Starting capital: ${starting_cap:,.2f}")
print(f"After {e_trades} trades: ${cap:,.2f}")
print(f"Net return: {(cap/starting_cap-1)*100:+.1f}%")
print(f"Expectancy per trade: {((cap/starting_cap-1)/e_trades)*100:+.2f}%")
print()

# === ENTRY F: Multi-timeframe EMA pullback ===
f_trades = 120
f_wr = 0.408
f_tp = 0.05
f_stop = 0.02

f_wins = int(f_trades * f_wr)
f_losses = f_trades - f_wins

print("=" * 65)
print("ENTRY F — Multi-Timeframe EMA Pullback + Green Candle")
print("=" * 65)
print(f"Trades: {f_trades} over 90 days")
print(f"Win rate: {f_wr*100:.1f}%  ({f_wins} wins / {f_losses} losses)")
print(f"Win: +5%  |  Loss: -2%")
print()

cap2 = starting_cap
for i in range(f_trades):
    risk_amt = cap2 * risk_pct
    if i < f_wins:
        cap2 += risk_amt * (f_tp / f_stop)
    else:
        cap2 -= risk_amt

print(f"Starting capital: ${starting_cap:,.2f}")
print(f"After {f_trades} trades: ${cap2:,.2f}")
print(f"Net return: {(cap2/starting_cap-1)*100:+.1f}%")
print(f"Expectancy per trade: {((cap2/starting_cap-1)/f_trades)*100:+.2f}%")
print()

# === Compare with our current Entry B ===
print("=" * 65)
print("COMPARISON: Entry B (RSI cross, no EMA filter)")
print("=" * 65)
b_trades = 300
b_wr = 0.220
b_tp = 0.05
b_stop = 0.02  # ATR-based (avg ~1.5%)
b_wins = int(b_trades * b_wr)
b_losses = b_trades - b_wins

cap3 = starting_cap
for i in range(b_trades):
    risk_amt = cap3 * risk_pct
    if i < b_wins:
        cap3 += risk_amt * (b_tp / b_stop)
    else:
        cap3 -= risk_amt

print(f"Trades: {b_trades} over 90 days")
print(f"Win rate: {b_wr*100:.1f}%  ({b_wins} wins / {b_losses} losses)")
print(f"Starting capital: ${starting_cap:,.2f}")
print(f"After {b_trades} trades: ${cap3:,.2f}")
print(f"Net return: {(cap3/starting_cap-1)*100:+.1f}%")
print()

# === What if we compound faster — risk 5% per trade? ===
print("=" * 65)
print("SENSITIVITY: Risk % per trade")
print("=" * 65)
print(f"{'Risk%':>6} | {'Entry E Final':>15} | {'Entry F Final':>15} | {'Entry B Final':>15}")
print("-" * 55)
for risk in [0.01, 0.02, 0.03, 0.05, 0.10]:
    for label, trades, wr, tp, stop in [
        ("E", e_trades, e_wr, e_tp, e_stop),
        ("F", f_trades, f_wr, f_tp, f_stop),
        ("B", b_trades, b_wr, b_tp, b_stop),
    ]:
        cap_ = starting_cap
        wins = int(trades * wr)
        for i in range(trades):
            r = cap_ * risk
            if i < wins:
                cap_ += r * (tp / stop)
            else:
                cap_ -= r
    print(f"  {risk*100:.0f}%  |  {cap_:>15,.0f}")