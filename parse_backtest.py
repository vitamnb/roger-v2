import json
from pathlib import Path

results_dir = Path(r"C:\Users\vitamnb\.openclaw\freqtrade\user_data\backtest_results")
files = sorted(results_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
latest = files[0]
print(f"Reading: {latest.name}")
data = json.load(open(latest))

# Get the strategy results
results = data.get('results', [])
print(f"\nTotal trades: {len(results)}")

# Group by pair
from collections import defaultdict
pair_stats = defaultdict(lambda: {'trades': 0, 'wins': 0, 'profit': 0.0})
for r in results:
    pair = r.get('pair', 'UNKNOWN')
    profit = r.get('profit_abs', 0)
    exit_reason = r.get('exit_reason', '')
    is_win = profit > 0
    pair_stats[pair]['trades'] += 1
    pair_stats[pair]['wins'] += is_win
    pair_stats[pair]['profit'] += profit

print("\nTop 10 pairs by profit:")
sorted_pairs = sorted(pair_stats.items(), key=lambda x: x[1]['profit'], reverse=True)
print(f"{'Pair':<20} {'Trades':>6} {'Wins':>5} {'Win%':>6} {'Profit':>10}")
print("-" * 55)
for pair, stats in sorted_pairs[:10]:
    wr = stats['wins']/stats['trades']*100 if stats['trades'] > 0 else 0
    print(f"{pair:<20} {stats['trades']:>6} {stats['wins']:>5} {wr:>6.1f}% {stats['profit']:>+10.3f}")

print("\nBottom 5 pairs:")
for pair, stats in sorted_pairs[-5:]:
    wr = stats['wins']/stats['trades']*100 if stats['trades'] > 0 else 0
    print(f"{pair:<20} {stats['trades']:>6} {stats['wins']:>5} {wr:>6.1f}% {stats['profit']:>+10.3f}")

# Exit reasons
exit_reasons = defaultdict(int)
for r in results:
    exit_reasons[r.get('exit_reason', 'UNKNOWN')] += 1
print("\nExit reasons:")
for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
    print(f"  {reason}: {count}")

# Entry tags
entry_tags = defaultdict(int)
for r in results:
    entry_tag = r.get('enter_tag', 'none')
    entry_tags[entry_tag] += 1
print("\nEntry tags:")
for tag, count in sorted(entry_tags.items(), key=lambda x: x[1], reverse=True):
    print(f"  {tag}: {count}")
