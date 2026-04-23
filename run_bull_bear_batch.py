# run_bull_bear_batch.py -- Batch run bull/bear researcher for watchlist pairs
import subprocess, sys, json, os
from datetime import datetime

WATCHLIST = r'C:\Users\vitamnb\.openclaw\freqtrade\daily_watchlist.txt'
OUTPUT = r'C:\Users\vitamnb\.openclaw\freqtrade\branches\signal_test\bull_bear_results.json'
BB_SCRIPT = r'C:\Users\vitamnb\.openclaw\freqtrade\bull_bear_researcher.py'

def load_watchlist():
    pairs = []
    with open(WATCHLIST) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            pair = line.split()[0]  # Extract pair symbol
            pairs.append(pair)
    return pairs

def run_debate(symbol):
    """Run bull/bear researcher for one symbol."""
    try:
        result = subprocess.run(
            [sys.executable, BB_SCRIPT, symbol],
            capture_output=True, text=True, timeout=300
        )
        # Parse output for score
        for line in result.stdout.split('\n'):
            if 'Score' in line and symbol in line:
                # Extract score from line like "BTC/USDT: Score +65 (bull, conf 0.75)"
                parts = line.split('Score')
                if len(parts) >= 2:
                    score_part = parts[1].split('(')[0].strip()
                    try:
                        score = int(score_part)
                        conf = float(line.split('conf')[1].split(')')[0].strip())
                        winner = line.split('(')[1].split(',')[0].strip()
                        return {
                            'score': score,
                            'confidence': conf,
                            'winner': winner,
                            'timestamp': datetime.utcnow().isoformat() + 'Z'
                        }
                    except:
                        pass
    except subprocess.TimeoutExpired:
        return {'error': 'timeout'}
    except Exception as e:
        return {'error': str(e)}
    return {'error': 'parse failed'}

def main():
    pairs = load_watchlist()
    print(f"Running bull/bear debates for {len(pairs)} pairs...")
    
    # Load existing results
    results = {}
    if os.path.exists(OUTPUT):
        try:
            with open(OUTPUT) as f:
                data = json.load(f)
                results = data.get('results', {})
        except:
            pass
    
    # Run for top 10 pairs (limit due to time)
    for pair in pairs[:10]:
        pair_key = pair.replace('/', '_')
        if pair_key in results:
            print(f"  [{pair}] Skipping (cached)")
            continue
        
        print(f"  [{pair}] Running debate...")
        verdict = run_debate(pair)
        if 'error' in verdict:
            print(f"    ERROR: {verdict['error']}")
        else:
            results[pair_key] = {
                'verdict': verdict,
                'timestamp': verdict['timestamp']
            }
            print(f"    Score: {verdict['score']:+d} ({verdict['winner']})")
    
    # Save results
    with open(OUTPUT, 'w') as f:
        json.dump({'results': results}, f, indent=2)
    
    print(f"\nSaved to {OUTPUT}")
    print(f"Total cached: {len(results)} pairs")

if __name__ == "__main__":
    main()
