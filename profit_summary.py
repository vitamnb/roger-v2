cap = 58.0

conservative = {
    'BTC':  +9.2,
    'ETH':  +17.4,
    'ARB':  +14.2,
    'NEAR': +8.3,
    'LINK': +10.5,
    'SOL':  -0.9,
    'XRP':  +1.2,
    'ADA':  -7.4,
    'AVAX': +37.9,
    'OP':   +7.8,
    'APT':  +11.5,
    'FIL':  +35.8,
    'DOT':  +3.3,
    'ATOM': -3.8,
}

aggressive = {
    'ETH':  +157.9,
    'ADA':  +117.8,
    'SOL':  +117.3,
    'LINK': +81.9,
    'ARB':  +72.8,
    'XRP':  +42.8,
    'AVAX': +29.5,
    'BTC':  +34.3,
    'NEAR': +6.3,
}

print('='*60)
print('CONSERVATIVE (4h candles | 90 days | $58 | 2% risk | 2:1 R:R)')
print('='*60)
print(f"  Starting capital: ${cap:.2f}")
print()
print(f"  {'Pair':<10} {'Return%':>9}  {'$':>8}  {'Final $':>10}")
print(f"  {'--'*5}  {'--'*4}  {'--'*4}  {'--'*5}")

for pair, ret in sorted(conservative.items(), key=lambda x: -x[1]):
    final = cap * (1 + ret/100)
    dollar = final - cap
    print(f"  {pair:<10} {ret:>+8.1f}%  {dollar:>+7.2f}  ${final:>9.2f}")

total_return = sum(conservative.values())
avg_ret = total_return / len(conservative)
avg_final = cap * (1 + avg_ret/100)
print(f"  {'--'*5}  {'--'*4}  {'--'*4}  {'--'*5}")
print(f"  {'AVERAGE':<10} {avg_ret:>+8.1f}%")
print()
all_final_c = sum(cap * (1+r/100) for r in conservative.values())
print(f"  All 14 pairs simultaneously (separate capital pools):")
print(f"  Combined final: ${all_final_c:.2f}  (started ${cap*14:.0f})")
print(f"  Best:  ETH  ${cap*1.174:.2f}")
print(f"  Worst: ADA  ${cap*0.926:.2f}")

print()
print('='*60)
print('AGGRESSIVE (1h candles | 30 days | $58 | 5% risk | 3:1 R:R)')
print('='*60)
print(f"  Starting capital: ${cap:.2f}")
print()
print(f"  {'Pair':<10} {'Return%':>9}  {'$':>8}  {'Final $':>10}")
print(f"  {'--'*5}  {'--'*4}  {'--'*4}  {'--'*5}")

for pair, ret in sorted(aggressive.items(), key=lambda x: -x[1]):
    final = cap * (1 + ret/100)
    dollar = final - cap
    print(f"  {pair:<10} {ret:>+8.1f}%  {dollar:>+7.2f}  ${final:>9.2f}")

total_ret_a = sum(aggressive.values())
avg_ret_a = total_ret_a / len(aggressive)
print(f"  {'--'*5}  {'--'*4}  {'--'*4}  {'--'*5}")
print(f"  {'AVERAGE':<10} {avg_ret_a:>+8.1f}%")
print()
all_final_a = sum(cap * (1+r/100) for r in aggressive.values())
print(f"  All 9 pairs simultaneously (separate capital pools):")
print(f"  Combined final: ${all_final_a:.2f}  (started ${cap*9:.0f})")
print(f"  Best:  ETH  ${cap*2.579:.2f}")
print(f"  Worst: NEAR ${cap*1.063:.2f}")

print()
print('='*60)
print('SINGLE $58 - BEST PAIR COMPARISON')
print('='*60)
print(f"  {'Strategy':<20} {'Pair':<8} {'Final':>10} {'$ Made':>10}")
print(f"  {'--'*10}  {'--'*4}  {'--'*5}  {'--'*5}")
best_c = max(conservative, key=conservative.get)
best_a = max(aggressive, key=aggressive.get)
print(f"  {'Conservative':<20} {best_c:<8} ${cap*(1+conservative[best_c]/100):>9.2f}  ${cap*conservative[best_c]/100:>+9.2f}")
print(f"  {'Aggressive':<20} {best_a:<8} ${cap*(1+aggressive[best_a]/100):>9.2f}  ${cap*aggressive[best_a]/100:>+9.2f}")
print()
print('  If you put $58 in ETH with the aggressive strategy:')
print(f"  $58 -> ${cap*(1+aggressive['ETH']/100):.2f} in 30 days")
print(f"  That's ${cap*aggressive['ETH']/100:.2f} profit in 1 month")
