# bull_bear_integration.py -- Integrates pre-computed bull/bear into scanner
import json, os

BB_FILE = r'C:\Users\vitamnb\.openclaw\freqtrade\branches\signal_test\bull_bear_results.json'

def load_bull_bear():
    """Load pre-computed bull/bear results."""
    if not os.path.exists(BB_FILE):
        return {}
    try:
        with open(BB_FILE) as f:
            data = json.load(f)
            return data.get('results', {})
    except:
        return {}

def get_trade_conviction(pair):
    """Get bull/bear conviction for a pair (pre-computed)."""
    results = load_bull_bear()
    pair_key = pair.replace('/', '_')
    data = results.get(pair_key, {})
    
    if not data or 'verdict' not in data:
        return None
    
    verdict = data['verdict']
    return {
        'score': verdict.get('score', 0),
        'confidence': verdict.get('confidence', 0.5),
        'winner': verdict.get('winner', 'neutral'),
        'recommendation': 'enter' if verdict.get('score', 0) >= 50 else ('reduce' if verdict.get('score', 0) > 0 else 'skip')
    }

def format_conviction(conviction):
    """Format conviction for display."""
    if not conviction:
        return "N/A"
    s = conviction['score']
    w = conviction['winner']
    c = conviction['confidence']
    if s >= 50:
        return f"STRONG BUY ({s:+d}, {w}, conf {c:.2f})"
    elif s > 0:
        return f"WEAK BUY ({s:+d}, {w}, conf {c:.2f})"
    elif s == 0:
        return f"NEUTRAL ({s:+d})"
    else:
        return f"AVOID ({s:+d}, {w}, conf {c:.2f})"
