# bull_bear_researcher_v2.py -- Per-trade conviction (RULE-BASED)
# Uses technical indicators to simulate bull/bear debate
# Fast (< 0.1s), deterministic, no LLM needed

import json, sys
from datetime import datetime

def analyze_trade(pair, price, rsi, ema_dist, vol_ratio, regime, reason):
    """
    Simulate bull/bear analysis using technical rules.
    Returns score -100 to +100.
    """
    bull_points = 0
    bear_points = 0
    reasons = []
    
    # RSI analysis
    if 35 <= rsi <= 45:
        bull_points += 30  # Sweet spot for momentum entry
        reasons.append("RSI in momentum zone (35-45)")
    elif rsi < 35:
        bull_points += 15  # Oversold, potential bounce
        reasons.append("RSI oversold (potential bounce)")
    elif rsi > 70:
        bear_points += 25  # Overbought
        reasons.append("RSI overbought")
    elif rsi > 55:
        bear_points += 10  # Getting stretched
        reasons.append("RSI elevated")
    
    # EMA distance
    if -1.5 <= ema_dist <= 1.5:
        bull_points += 20  # Price near EMA = good entry
        reasons.append("Price near EMA (pullback zone)")
    elif ema_dist > 3:
        bear_points += 15  # Price too far above EMA
        reasons.append("Price stretched above EMA")
    elif ema_dist < -3:
        bear_points += 20  # Price below EMA = breakdown
        reasons.append("Price below EMA (breakdown)")
    
    # Volume
    if vol_ratio >= 2.0:
        bull_points += 15  # Strong volume confirmation
        reasons.append("High volume confirmation")
    elif vol_ratio >= 1.5:
        bull_points += 10  # Above average volume
        reasons.append("Above average volume")
    elif vol_ratio < 1.0:
        bear_points += 10  # Low volume = weak move
        reasons.append("Low volume (weak move)")
    
    # Regime
    if "STRONG_TREND" in regime and "LONG" in str(reason).upper():
        bull_points += 15
        reasons.append("Strong uptrend")
    elif "STRONG_TREND" in regime and "SHORT" in str(reason).upper():
        bear_points += 15
        reasons.append("Strong downtrend")
    
    # Calculate final score
    total = bull_points + bear_points
    if total == 0:
        score = 0
    else:
        score = int(((bull_points - bear_points) / max(total, 1)) * 100)
    
    # Clamp to -100 to +100
    score = max(-100, min(100, score))
    
    # Determine recommendation
    if score >= 50:
        rec = "enter"
        size = 50
        label = "full"
    elif score >= 30:
        rec = "enter"
        size = 25
        label = "half"
    elif score > 0:
        rec = "reduce"
        size = 15
        label = "quarter"
    else:
        rec = "skip"
        size = 0
        label = "skip"
    
    return {
        "pair": pair,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "score": score,
        "bull_points": bull_points,
        "bear_points": bear_points,
        "recommendation": rec,
        "position_size": size,
        "position_label": label,
        "reasoning": "; ".join(reasons) if reasons else "No strong signals"
    }

def main():
    if len(sys.argv) < 6:
        print("Usage: python bull_bear_researcher_v2.py <pair> <price> <rsi> <ema_dist> <reason> [vol_ratio] [regime]")
        sys.exit(1)
    
    pair = sys.argv[1]
    price = float(sys.argv[2])
    rsi = float(sys.argv[3])
    ema_dist = float(sys.argv[4])
    reason = sys.argv[5]
    vol_ratio = float(sys.argv[6]) if len(sys.argv) > 6 else 1.5
    regime = sys.argv[7] if len(sys.argv) > 7 else "TRENDING"
    
    result = analyze_trade(pair, price, rsi, ema_dist, vol_ratio, regime, reason)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
