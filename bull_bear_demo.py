# bull_bear_demo.py -- Shows how per-trade conviction works
import json

# Simulated scanner signal
signal = {
    "pair": "BTC/USDT",
    "entry": 77400,
    "rsi": 42,
    "ema_dist": 0.8,
    "vol_ratio": 1.8,
    "regime": "STRONG_TREND",
    "reason": "RSI crosses 40 from below, EMA12 support, green candle"
}

print("=== Per-Trade Bull/Bear Conviction ===\n")
print(f"Signal: {signal['pair']} @ ${signal['entry']}")
print(f"  RSI: {signal['rsi']} | EMA dist: {signal['ema_dist']}% | Vol: {signal['vol_ratio']}x")
print(f"  Setup: {signal['reason']}\n")

print("Running bull/bear analysis...")
print("  [Bull Analyst] Checking: RSI momentum, EMA support, volume confirmation")
print("  [Bear Analyst] Checking: Trend exhaustion, resistance levels, macro risk")
print("  [Judge] Scoring...\n")

# Simulated result (would come from LLM)
result = {
    "score": +45,
    "confidence": 0.72,
    "winner": "bull",
    "recommendation": "enter",
    "bull_conf": 78,
    "bear_conf": 42,
    "position_size": 25,
    "position_label": "half",
    "reasoning": "Bull case stronger on momentum but bear warns of trend exhaustion. Moderate conviction."
}

print(f"RESULT:")
print(f"  Score: {result['score']:+d} (conf: {result['confidence']:.2f})")
print(f"  Bull: {result['bull_conf']}/100 | Bear: {result['bear_conf']}/100")
print(f"  Verdict: {result['winner'].upper()} wins → {result['recommendation'].upper()}")
print(f"  Position: ${result['position_size']} ({result['position_label']} stake)")
print(f"  Reasoning: {result['reasoning']}")

print("\n=== Position Sizing Rules ===")
print("  Score >= 50 + conf >= 0.6 → $50 (full)")
print("  Score >= 30 + conf >= 0.5 → $25 (half)")
print("  Score > 0 + conf >= 0.4 → $15 (quarter)")
print("  Score <= 0 or conf < 0.4 → SKIP")

print("\n=== How it fits the pipeline ===")
print("1. Scanner finds Entry E signal")
print("2. Bull/bear runs on THAT signal (60s LLM call)")
print("3. Score feeds into position sizing")
print("4. Branch A strategy adjusts stake accordingly")
