# scan_cron.py -- Scanner cron wrapper with signal detection
# Called by cron job. Writes results to JSON and prints signal summary.
import subprocess, json, sys
from pathlib import Path

OUT_FILE = Path(__file__).parent / "latest_scan.json"
SCRIPT_DIR = Path(__file__).parent

def main():
    tf = sys.argv[1] if len(sys.argv) > 1 else "1h"

    result = subprocess.run(
        ["python", str(SCRIPT_DIR / "scanner.py"),
         "--timeframe", tf, "--top", "10", "--capital", "58", "--risk", "2", "--rr", "3.5"],
        capture_output=True, text=True,
        cwd=str(SCRIPT_DIR)
    )

    output = result.stdout + result.stderr

    # Parse for signals block
    signals = []
    in_signals = False
    for line in output.splitlines():
        if "[SIGNALS]" in line:
            in_signals = True
        elif in_signals and line.startswith("  [!]"):
            in_signals = False
        elif in_signals and line.strip().startswith("  "):
            parts = line.strip().split()
            if len(parts) >= 4 and parts[0] not in ("Symbol", "---", "[LEGEND]"):
                try:
                    signals.append({
                        "symbol": parts[0],
                        "regime": parts[1],
                        "direction": parts[2],
                        "score": int(parts[3]),
                        "raw": line.strip()
                    })
                except:
                    pass

    # Save JSON
    with open(OUT_FILE, "w") as f:
        json.dump({
            "time": str(subprocess.run(
                ["powershell", "-Command",
                 "(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"],
                capture_output=True, text=True
            ).stdout.strip()),
            "timeframe": tf,
            "signal_count": len(signals),
            "signals": signals,
            "full_output": output[-3000:]  # last 3000 chars
        }, f, indent=2)

    # Print short summary for cron delivery
    print(f"[SCANNER] Timeframe: {tf} | Signals found: {len(signals)}")
    for s in signals:
        print(f"  {s['symbol']} | {s['regime']} | {s['direction']} | Score {s['score']}")
    if not signals:
        print("  No signals this cycle. Market regime: see full output.")

    if len(output) > 3000:
        print(f"\n  [Full output saved to {OUT_FILE}]")

if __name__ == "__main__":
    main()
