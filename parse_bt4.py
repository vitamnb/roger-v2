import json
from pathlib import Path

results_dir = Path(r"C:\Users\vitamnb\.openclaw\freqtrade\user_data\backtest_results\unzipped_1751")
with open(results_dir / "backtest-result-2026-04-22_17-51-23.json", encoding="utf-8") as f:
    data = json.load(f)

s = data["strategy"]["RogerStrategy"]

print("=== BACKTEST RESULTS ===")
print(f"Total trades:    {s['total_trades']}")
print(f"Win rate:         {s['winrate']*100:.1f}%")
print(f"Profit total:     {s['profit_total']:.3f} ({s['profit_total_abs']:.3f} USDT)")
print(f"Final balance:    {s['final_balance']:.3f} USDT")
print(f"Starting balance: {s['starting_balance']:.3f} USDT")
print(f"Return:          {s['profit_total']*100:.1f}%")
print()

print("=== PER-PAIR ===")
pair_results = s.get("results_per_pair", [])
if isinstance(pair_results, dict):
    # Sort by profit
    sorted_pairs = sorted(pair_results.items(), key=lambda x: x[1].get("profit_abs", 0), reverse=True)
    print(f"{'Pair':<20} {'Trades':>6} {'WR%':>6} {'Profit%':>8} {'ProfitAbs':>10}")
    print("-" * 60)
    for pair, info in sorted_pairs[:15]:
        trades = info.get("trade_count", 0)
        profit_pct = info.get("profit_mean", 0) * 100
        profit_abs = info.get("profit_abs", 0)
        wr = info.get("winrate", 0) * 100
        print(f"{pair:<20} {trades:>6} {wr:>6.1f} {profit_pct:>+8.2f} {profit_abs:>+10.3f}")
    print()
    print("Bottom 5:")
    for pair, info in sorted_pairs[-5:]:
        trades = info.get("trade_count", 0)
        profit_pct = info.get("profit_mean", 0) * 100
        profit_abs = info.get("profit_abs", 0)
        wr = info.get("winrate", 0) * 100
        print(f"{pair:<20} {trades:>6} {wr:>6.1f} {profit_pct:>+8.2f} {profit_abs:>+10.3f}")

print()
print("=== EXIT REASONS ===")
for reason, count in s.get("exit_reason_summary", {}).items():
    print(f"  {reason}: {count}")

print()
print("=== ENTRY TAGS ===")
for tag, count in s.get("results_per_enter_tag", {}).items():
    print(f"  {tag}: {count}")

print()
print("=== REJECTED SIGNALS ===")
print(f"  {s.get('rejected_signals', 0)}")
print(f"  Timed out entries: {s.get('timedout_entry_orders', 0)}")
print()

# SQN score
print("=== METRICS ===")
print(f"  SQN:             {s.get('sqn', 'N/A')}")
print(f"  Profit factor:   {s.get('profit_factor', 'N/A')}")
print(f"  Sharpe:          {s.get('sharpe', 'N/A')}")
print(f"  Sortino:         {s.get('sortino', 'N/A')}")
print(f"  CAGR:            {s.get('cagr', 'N/A')}")
print(f"  Expectancy:      {s.get('expectancy', 'N/A')}")
print(f"  Max drawdown:    {s.get('max_drawdown_abs', 'N/A')} ({s.get('max_relative_drawdown', 'N/A')})")
print(f"  Calmar:           {s.get('calmar', 'N/A')}")
print()
print(f"  Trading mode:    {s.get('trading_mode', 'N/A')}")
print(f"  Margin mode:     {s.get('margin_mode', 'N/A')}")
