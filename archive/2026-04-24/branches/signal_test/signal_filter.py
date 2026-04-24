# signal_filter.py -- Pre-filter pairs using signal layer before Freqtrade trading
# Run this before starting Branch A to update the pairlist

import json, os, sys
import ccxt

API_KEY = '69e068a7c9bace0001a89666'
SIGNAL_FILE = os.path.join(os.path.dirname(__file__), "signals.json")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
MIN_SCORE = 40
MIN_CONFIDENCE = 0.5

def get_kucoin():
    return ccxt.kucoin({
        'apiKey': API_KEY,
        'secret': '',
        'password': '',
        'enableRateLimit': True,
        'options': {'defaultType': 'spot', 'rateLimit': 50},
    })

def generate_signals_for_watchlist():
    """Run signal_agents.py for the watchlist."""
    import subprocess
    result = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "signal_agents.py")],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("signal_agents.py failed:", result.stderr)
        return None
    
    # Parse the test output to get JSON
    # For now, we'll just generate signals manually
    from signal_agents import generate_signals_batch
    
    # Load watchlist
    watchlist_file = os.path.join(os.path.dirname(__file__), "daily_watchlist.txt")
    pairs = []
    try:
        with open(watchlist_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    pairs.append(line.split()[0])
    except:
        # Fallback to default pairs
        pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT",
                 "ADA/USDT", "AVAX/USDT", "ARB/USDT", "OP/USDT", "NEAR/USDT"]
    
    exchange = get_kucoin()
    signals = generate_signals_batch(pairs, exchange)
    
    return {
        'timestamp': signals[0]['timestamp'] if signals else '',
        'signals': signals
    }

def filter_pairs_by_signal(signals_data):
    """Filter to pairs meeting threshold."""
    filtered = []
    for sig in signals_data.get('signals', []):
        if 'error' in sig:
            continue
        combined = sig.get('combined', {})
        score = combined.get('score', 0)
        confidence = combined.get('confidence', 0)
        
        if score >= MIN_SCORE and confidence >= MIN_CONFIDENCE:
            filtered.append({
                'symbol': sig['symbol'],
                'score': score,
                'confidence': confidence
            })
    
    return sorted(filtered, key=lambda x: x['score'], reverse=True)

def update_config_pairlist(filtered_pairs):
    """Update Branch A config with filtered pairlist."""
    with open(CONFIG_FILE) as f:
        config = json.load(f)
    
    # Replace pairlist with signal-filtered pairs
    pairlist = [p['symbol'] for p in filtered_pairs]
    
    # Find existing pairlist config or add it
    config['pairlist'] = {
        'method': 'StaticPairList',
        'pairs': pairlist
    }
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    return pairlist

def main():
    print("=== Signal Filter for Branch A ===")
    
    # Generate signals
    signals = generate_signals_for_watchlist()
    if not signals:
        print("[FAIL] Could not generate signals")
        sys.exit(1)
    
    # Save signals
    with open(SIGNAL_FILE, 'w') as f:
        json.dump(signals, f, indent=2)
    print(f"[OK] Signals saved to {SIGNAL_FILE}")
    
    # Filter
    filtered = filter_pairs_by_signal(signals)
    print(f"[OK] {len(filtered)} pairs pass filter (score>={MIN_SCORE}, conf>={MIN_CONFIDENCE})")
    
    for p in filtered[:10]:
        print(f"  {p['symbol']:15s} score={p['score']:+.1f} conf={p['confidence']}")
    
    # Update config
    pairlist = update_config_pairlist(filtered)
    print(f"[OK] Branch config updated with {len(pairlist)} pairs")
    print(f"     Config: {CONFIG_FILE}")
    print()
    print("Ready to start Branch A:")
    print(f"  freqtrade trade --config {CONFIG_FILE} --strategy RogerStrategy")

if __name__ == "__main__":
    main()
