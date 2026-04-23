# signal_agents.py -- Signal Generation Layer for Roger Trading System
# Collects signals from multiple agents, outputs structured scores
# Run before scanner or as part of scanner pipeline

import ccxt, json, os, sys
from datetime import datetime
import pandas as pd
import numpy as np

API_KEY = '69e068a7c9bace0001a89666'
BASE_DIR = os.path.dirname(__file__)
WHALE_FILE = os.path.join(BASE_DIR, "whale_watchlist.txt")

# Signal output structure:
# {
#   "timestamp": "2026-04-23T18:00:00Z",
#   "signals": {
#     "technical": {"score": 65, "confidence": 0.8, "details": "RSI cross, EMA support"},
#     "whale": {"score": -20, "confidence": 0.6, "details": "Distribution bias on BTC"},
#     "macro": {"score": 0, "confidence": 0.3, "details": "No events today"},
#     "news": {"score": 0, "confidence": 0.0, "details": "News agent not configured"},
#     "on_chain": {"score": 0, "confidence": 0.0, "details": "On-chain agent not configured"}
#   },
#   "combined": {"score": 45, "confidence": 0.55}
# }

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

def technical_agent(symbol, exchange):
    """Score based on RSI/EMA conditions (same logic as scanner)."""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=50)
        if not ohlcv or len(ohlcv) < 30:
            return {'score': 0, 'confidence': 0, 'details': 'No data'}
        
        df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
        df['ema12'] = df['close'].ewm(span=12).mean()
        df['ema26'] = df['ema26'] = df['close'].ewm(span=26).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + gain / loss.replace(0, 1)))
        df['rsi_prev'] = df['rsi'].shift(1)
        df['green_prev'] = (df['close'] > df['open']).shift(1)
        df['ema12_dist_pct'] = (df['close'] - df['ema12']) / df['ema12'] * 100
        
        # Check Entry E conditions
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        score = 0
        details = []
        
        # EMA distance (pullback zone)
        if -1.5 <= latest['ema12_dist_pct'] <= 1.5:
            score += 30
            details.append("EMA pullback zone")
        elif latest['ema12_dist_pct'] > 1.5:
            score -= 10
            details.append("Price stretched above EMA")
        
        # RSI cross
        if latest['rsi'] >= 40 and prev['rsi'] < 50 and latest['rsi'] <= 75:
            score += 40
            details.append("RSI cross up through 40")
        elif latest['rsi'] > 75:
            score -= 20
            details.append("RSI overbought")
        elif latest['rsi'] < 35:
            score += 10
            details.append("RSI oversold (potential recovery)")
        
        # Previous candle green
        if prev['green_prev']:
            score += 20
            details.append("Prev candle green")
        
        # EMA bull
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
    
    # Normalize to -100 to +100
    normalized = (score - 50) * 2  # 50->0, 100->+100, 0->-100
    
    details = f"Whale score {score}/100, bias: {bias}"
    confidence = 0.6 if bias in ['ACCUMULATION', 'DISTRIBUTION'] else 0.4
    
    return {
        'score': max(-100, min(100, normalized)),
        'confidence': round(confidence, 2),
        'details': details
    }

def macro_agent():
    """Score based on macro events (placeholder)."""
    # TODO: Read CPI/Fed calendar, earnings, etc.
    return {
        'score': 0,
        'confidence': 0.3,
        'details': 'Macro agent not implemented'
    }

def news_agent():
    """Score based on news sentiment (placeholder)."""
    # TODO: Read Twitter/Reddit/news feeds
    return {
        'score': 0,
        'confidence': 0.0,
        'details': 'News agent not implemented'
    }

def on_chain_agent():
    """Score based on on-chain data (placeholder)."""
    # TODO: Read wallet flows, exchange flows
    return {
        'score': 0,
        'confidence': 0.0,
        'details': 'On-chain agent not implemented'
    }

def combine_signals(signals, weights=None):
    """Weighted combination of all signals."""
    if weights is None:
        weights = {
            'technical': 0.50,
            'whale': 0.25,
            'macro': 0.10,
            'news': 0.10,
            'on_chain': 0.05
        }
    
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
    
    combined_score = weighted_sum / total_weight
    avg_confidence = confidence_sum / len([s for s in signals.values() if s['confidence'] > 0]) if any(s['confidence'] > 0 for s in signals.values()) else 0
    
    return {
        'score': round(combined_score, 1),
        'confidence': round(min(avg_confidence, 1.0), 2)
    }

def generate_signals(symbol, exchange=None):
    """Generate complete signal report for a symbol."""
    if exchange is None:
        exchange = get_kucoin()
    
    whale_scores = load_whale_scores()
    
    signals = {
        'technical': technical_agent(symbol, exchange),
        'whale': whale_agent(symbol, whale_scores),
        'macro': macro_agent(),
        'news': news_agent(),
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
    # Test with a few symbols
    test_symbols = ["BTC/USDT", "ETH/USDT", "ENJ/USDT"]
    print("=== Signal Agent Test ===")
    for sig in generate_signals_batch(test_symbols):
        print(f"\n{sig['symbol']}:")
        if 'error' in sig:
            print(f"  ERROR: {sig['error']}")
            continue
        print(f"  Combined: {sig['combined']['score']:+.1f} (conf: {sig['combined']['confidence']})")
        for agent, data in sig['signals'].items():
            print(f"    {agent:12s}: {data['score']:+.1f} (conf: {data['confidence']}) - {data['details']}")
