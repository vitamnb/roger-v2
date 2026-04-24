# signal_agents.py -- Signal Generation Layer for Roger Trading System (Branch A)
# Collects signals from multiple agents, outputs structured scores

import ccxt, json, os
from datetime import datetime
import pandas as pd
import numpy as np

API_KEY = '69e068a7c9bace0001a89666'
BASE_DIR = os.path.dirname(__file__)
WHALE_FILE = os.path.join(BASE_DIR, "..", "..", "whale_watchlist.txt")
SENTIMENT_FILE = os.path.join(BASE_DIR, "sentiment_data.json")

def get_kucoin():
    return ccxt.kucoin({
        'apiKey': API_KEY,
        'secret': '',
        'password': '',
        'enableRateLimit': True,
        'options': {'defaultType': 'spot', 'rateLimit': 50},
    })

def load_whale_scores():
    """Load whale watch scores from file."""
    if not os.path.exists(WHALE_FILE):
        return {}
    scores = {}
    try:
        with open(WHALE_FILE) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('|')
                if len(parts) >= 3:
                    pair = parts[0].strip()
                    try:
                        score = int(parts[1].strip())
                        bias = parts[2].strip()
                        scores[pair] = {'score': score, 'bias': bias}
                    except ValueError:
                        pass
    except Exception:
        pass
    return scores

def load_sentiment():
    """Load pre-computed sentiment data."""
    if not os.path.exists(SENTIMENT_FILE):
        return {'combined': {'score': 0, 'confidence': 0}}
    try:
        with open(SENTIMENT_FILE) as f:
            return json.load(f)
    except:
        return {'combined': {'score': 0, 'confidence': 0}}

def technical_agent(symbol, exchange):
    """Score based on RSI/EMA conditions (same logic as scanner)."""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=50)
        if not ohlcv or len(ohlcv) < 30:
            return {'score': 0, 'confidence': 0, 'details': 'No data'}
        
        df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
        df['ema12'] = df['close'].ewm(span=12).mean()
        df['ema26'] = df['close'].ewm(span=26).mean()
        
        delta = df['close'].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + gain / loss.replace(0, 1)))
        df['rsi_prev'] = df['rsi'].shift(1)
        df['green_prev'] = (df['close'] > df['open']).shift(1)
        df['ema12_dist_pct'] = (df['close'] - df['ema12']) / df['ema12'] * 100
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        score = 0
        details = []
        
        if -1.5 <= latest['ema12_dist_pct'] <= 1.5:
            score += 30
            details.append("EMA pullback zone")
        elif latest['ema12_dist_pct'] > 1.5:
            score -= 10
            details.append("Price stretched above EMA")
        
        if latest['rsi'] >= 40 and prev['rsi'] < 50 and latest['rsi'] <= 75:
            score += 40
            details.append("RSI cross up through 40")
        elif latest['rsi'] > 75:
            score -= 20
            details.append("RSI overbought")
        elif latest['rsi'] < 35:
            score += 10
            details.append("RSI oversold (potential recovery)")
        
        if prev['green_prev']:
            score += 20
            details.append("Prev candle green")
        
        if latest['ema12'] > latest['ema26']:
            score += 10
            details.append("EMA bullish")
        
        confidence = min(0.9, 0.5 + len(details) * 0.1)
        
        return {
            'score': max(-100, min(100, score)),
            'confidence': round(confidence, 2),
            'details': '; '.join(details) if details else 'No signals'
        }
    except Exception as e:
        return {'score': 0, 'confidence': 0, 'details': f'Error: {e}'}

def whale_agent(symbol, whale_scores):
    """Score based on whale watch accumulation/distribution."""
    pair = symbol.replace('/USDT', '') + '/USDT'
    data = whale_scores.get(pair, whale_scores.get(symbol, {}))
    
    if not data:
        return {'score': 0, 'confidence': 0.3, 'details': 'No whale data'}
    
    score = data['score']
    bias = data.get('bias', 'NEUTRAL')
    normalized = (score - 50) * 2
    
    return {
        'score': max(-100, min(100, normalized)),
        'confidence': 0.6 if bias in ['ACCUMULATION', 'DISTRIBUTION'] else 0.4,
        'details': f"Whale score {score}/100, bias: {bias}"
    }

def sentiment_agent():
    """Score based on social/news sentiment."""
    sentiment = load_sentiment()
    combined = sentiment.get('combined', {})
    score = combined.get('score', 0)
    confidence = combined.get('confidence', 0)
    sources = combined.get('sources_used', [])
    
    return {
        'score': score,
        'confidence': confidence,
        'details': f"Sentiment from {', '.join(sources)}: {score:+.1f}"
    }

def macro_agent():
    """Score based on macro events (placeholder)."""
    return {'score': 0, 'confidence': 0.3, 'details': 'Macro agent not implemented'}

def on_chain_agent():
    """Score based on on-chain data (placeholder)."""
    return {'score': 0, 'confidence': 0.0, 'details': 'On-chain agent not implemented'}

# Bull/Bear researcher cache
BB_FILE = os.path.join(BASE_DIR, "bull_bear_results.json")

def load_bull_bear_results():
    """Load cached bull/bear debate results."""
    if not os.path.exists(BB_FILE):
        return {}
    try:
        with open(BB_FILE) as f:
            data = json.load(f)
            return data.get('results', {})
    except:
        return {}

def bull_bear_agent(symbol):
    """Score from multi-agent bull/bear debate."""
    results = load_bull_bear_results()
    pair_key = symbol.replace('/', '_')
    data = results.get(pair_key, {})
    
    if not data or 'verdict' not in data:
        return {'score': 0, 'confidence': 0, 'details': 'No bull/bear data'}
    
    verdict = data['verdict']
    score = verdict.get('score', 0)
    confidence = verdict.get('confidence', 0.5)
    winner = verdict.get('winner', 'neutral')
    
    return {
        'score': score,
        'confidence': confidence,
        'details': f"Bull/Bear: {winner} wins (score {score:+d}, conf {confidence:.2f})"
    }

# Update weights to include bull_bear agent
DEFAULT_WEIGHTS = {
    'technical': 0.45,
    'whale': 0.15,
    'sentiment': 0.15,
    'bull_bear': 0.15,
    'macro': 0.05,
    'on_chain': 0.05
}

def combine_signals(signals, weights=None):
    """Weighted combination of all signals."""
    if weights is None:
        weights = DEFAULT_WEIGHTS
    
    total_weight = 0
    weighted_sum = 0
    confidence_sum = 0
    
    for agent_name, signal in signals.items():
        w = weights.get(agent_name, 0)
        if w > 0 and signal['confidence'] > 0:
            weighted_sum += signal['score'] * w * signal['confidence']
            total_weight += w * signal['confidence']
            confidence_sum += signal['confidence']
    
    if total_weight == 0:
        return {'score': 0, 'confidence': 0}
    
    return {
        'score': round(weighted_sum / total_weight, 1),
        'confidence': round(min(confidence_sum / len([s for s in signals.values() if s['confidence'] > 0]), 1.0), 2)
    }

def generate_signals(symbol, exchange=None):
    """Generate complete signal report for a symbol."""
    if exchange is None:
        exchange = get_kucoin()
    
    whale_scores = load_whale_scores()
    
    signals = {
        'technical': technical_agent(symbol, exchange),
        'whale': whale_agent(symbol, whale_scores),
        'sentiment': sentiment_agent(),
        'bull_bear': bull_bear_agent(symbol),
        'macro': macro_agent(),
        'on_chain': on_chain_agent()
    }
    
    combined = combine_signals(signals)
    
    return {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'symbol': symbol,
        'signals': signals,
        'combined': combined
    }

def generate_signals_batch(symbols, exchange=None):
    """Generate signals for multiple symbols."""
    if exchange is None:
        exchange = get_kucoin()
    
    results = []
    for symbol in symbols:
        try:
            result = generate_signals(symbol, exchange)
            results.append(result)
        except Exception as e:
            results.append({
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'symbol': symbol,
                'error': str(e)
            })
    return results

if __name__ == "__main__":
    test_symbols = ["BTC/USDT", "ETH/USDT", "ENJ/USDT"]
    print("=== Signal Agent Test (Branch A) ===")
    for sig in generate_signals_batch(test_symbols):
        print(f"\n{sig['symbol']}:")
        if 'error' in sig:
            print(f"  ERROR: {sig['error']}")
            continue
        print(f"  Combined: {sig['combined']['score']:+.1f} (conf: {sig['combined']['confidence']})")
        for agent, data in sig['signals'].items():
            print(f"    {agent:12s}: {data['score']:+.1f} (conf: {data['confidence']}) - {data['details']}")
