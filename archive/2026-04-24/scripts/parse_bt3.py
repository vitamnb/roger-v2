import json
from pathlib import Path
from collections import defaultdict

results_dir = Path(r"C:\Users\vitamnb\.openclaw\freqtrade\user_data\backtest_results\unzipped_1751")
with open(results_dir / "backtest-result-2026-04-22_17-51-23.json", encoding="utf-8") as f:
    data = json.load(f)

strategy_data = data["strategy"]["RogerStrategy"]
print("Strategy keys:", list(strategy_data.keys()))

results = strategy_data.get("results", [])
print(f"\nTotal trades: {len(results)}")

pair_stats = defaultdict(lambda: {"trades": 0, "wins": 0, "profit": 0.0})
for r in results:
    pair = r.get("pair", "UNKNOWN")
    profit = r.get("profit_abs", 0)
    is_win = profit > 0
    pair_stats[pair]["trades"] += 1
    pair_stats[pair]["wins"] += is_win
    pair_stats[pair]["profit"] += profit

sorted_pairs = sorted(pair_stats.items(), key=lambda x: x[1]["profit"], reverse=True)
print(f"\n{'Pair':<20} {'Trades':>6} {'Wins':>5} {'Win%':>6} {'Profit':>10}")
print("-" * 55)
for pair, stats in sorted_pairs[:15]:
    wr = stats["wins"] / stats["trades"] * 100 if stats["trades"] > 0 else 0
    print(f"{pair:<20} {stats['trades']:>6} {stats['wins']:>5} {wr:>6.1f}% {stats['profit']:>+10.3f}")

print("\nBottom 5:")
for pair, stats in sorted_pairs[-5:]:
    wr = stats["wins"] / stats["trades"] * 100 if stats["trades"] > 0 else 0
    print(f"{pair:<20} {stats['trades']:>6} {stats['wins']:>5} {wr:>6.1f}% {stats['profit']:>+10.3f}")

exit_reasons = defaultdict(int)
for r in results:
    exit_reasons[r.get("exit_reason", "UNKNOWN")] += 1

print("\nExit reasons:")
for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
    print(f"  {reason}: {count}")

entry_tags = defaultdict(int)
for r in results:
    entry_tags[r.get("enter_tag", "none")] += 1

print("\nEntry tags:")
for tag, count in sorted(entry_tags.items(), key=lambda x: x[1], reverse=True):
    print(f"  {tag}: {count}")

total_profit = sum(r.get("profit_abs", 0) for r in results)
total_wins = sum(1 for r in results if r.get("profit_abs", 0) > 0)
total_losses = sum(1 for r in results if r.get("profit_abs", 0) < 0)
n = len(results)
print(f"\nTotal profit: {total_profit:+.3f} USDT")
print(f"Wins: {total_wins}, Losses: {total_losses}")
if n > 0:
    print(f"WR: {total_wins/n*100:.1f}%")
