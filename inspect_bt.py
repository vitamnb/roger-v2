import json
from pathlib import Path

results_dir = Path(r"C:\Users\vitamnb\.openclaw\freqtrade\user_data\backtest_results\unzipped_1751")
with open(results_dir / "backtest-result-2026-04-22_17-51-23.json", encoding="utf-8") as f:
    data = json.load(f)

print("Top-level keys:", list(data.keys()))
for k in data.keys():
    v = data[k]
    if isinstance(v, list):
        print(f"  {k}: list with {len(v)} items")
    elif isinstance(v, dict):
        print(f"  {k}: dict with keys {list(v.keys())[:10]}")
    else:
        print(f"  {k}: {type(v).__name__} = {str(v)[:100]}")
