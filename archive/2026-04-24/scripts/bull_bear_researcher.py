# bull_bear_researcher.py -- Multi-agent debate layer for signal confidence
# Simulates: bull analyst, bear analyst, literature judge
# Output: structured JSON with confidence score (-100 to +100)

import os, json, requests
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "kimi-k2.6:cloud"
TIMEOUT = 90  # seconds per call

def call_llm(prompt, temperature=0.7):
    """Call local Ollama LLM for reasoning."""
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature}
            },
            timeout=TIMEOUT
        )
        if resp.status_code == 200:
            return resp.json().get("response", "")
        else:
            return f"ERROR: HTTP {resp.status_code}"
    except requests.exceptions.Timeout:
        return "ERROR: LLM timeout"
    except Exception as e:
        return f"ERROR: {e}"

def get_market_context():
    """Get current market context from files."""
    ctx = "Market Context:\n"
    
    # Try to read sentiment data
    try:
        with open(r'C:\Users\vitamnb\.openclaw\freqtrade\sentiment_data.json') as f:
            sent = json.load(f)
            combined = sent.get('combined', {})
            ctx += f"- Sentiment: {combined.get('score', 0):+.1f} ({combined.get('sources_used', [])})\n"
    except:
        pass
    
    # Try to read whale watch
    try:
        with open(r'C:\Users\vitamnb\.openclaw\freqtrade\whale_watchlist.txt') as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
            if lines:
                top = lines[0].split('|')
                if len(top) >= 3:
                    ctx += f"- Whale bias: {top[2].strip()} (score {top[1].strip()})\n"
    except:
        pass
    
    return ctx

def bull_argument(symbol, context):
    """Generate bull case."""
    prompt = f"""You are a bullish crypto analyst. Find reasons why {symbol} could go UP.

{context}

Respond ONLY with JSON:
{{"confidence": 0-100, "factors": ["factor 1", "factor 2"], "summary": "one sentence"}}
"""
    return call_llm(prompt, temperature=0.8)

def bear_argument(symbol, context):
    """Generate bear case."""
    prompt = f"""You are a bearish crypto analyst. Find reasons why {symbol} could go DOWN.

{context}

Respond ONLY with JSON:
{{"confidence": 0-100, "factors": ["factor 1", "factor 2"], "summary": "one sentence"}}
"""
    return call_llm(prompt, temperature=0.8)

def judge(symbol, bull_raw, bear_raw):
    """Arbitrate between bull and bear."""
    prompt = f"""You judge bull vs bear cases for {symbol}.

BULL: {bull_raw}
BEAR: {bear_raw}

Score -100 (bearish) to +100 (bullish). Respond ONLY with JSON:
{{"score": -100 to 100, "winner": "bull|bear|neutral", "confidence": 0.0-1.0, "reasoning": "brief"}}
"""
    return call_llm(prompt, temperature=0.3)

def extract_json(text):
    """Extract JSON from LLM response."""
    try:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
    except:
        pass
    return {}

def debate(symbol):
    """Run full debate for one symbol."""
    context = get_market_context()
    
    print(f"[{symbol}] Bull analysis...")
    bull_raw = bull_argument(symbol, context)
    print(f"[{symbol}] Bear analysis...")
    bear_raw = bear_argument(symbol, context)
    print(f"[{symbol}] Judging...")
    judge_raw = judge(symbol, bull_raw, bear_raw)
    
    bull_data = extract_json(bull_raw)
    bear_data = extract_json(bear_raw)
    judge_data = extract_json(judge_raw)
    
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "symbol": symbol,
        "bull": {
            "confidence": bull_data.get('confidence', 0),
            "summary": bull_data.get('summary', ''),
            "factors": bull_data.get('factors', [])
        },
        "bear": {
            "confidence": bear_data.get('confidence', 0),
            "summary": bear_data.get('summary', ''),
            "factors": bear_data.get('key_factors', bear_data.get('factors', []))
        },
        "verdict": {
            "score": judge_data.get('score', 0),
            "winner": judge_data.get('winner', 'neutral'),
            "confidence": judge_data.get('confidence', 0.5),
            "reasoning": judge_data.get('reasoning', '')
        }
    }

if __name__ == "__main__":
    import sys
    symbols = sys.argv[1:] if len(sys.argv) > 1 else ["BTC/USDT"]
    print("=== Bull/Bear Researcher ===")
    for sym in symbols:
        result = debate(sym)
        v = result['verdict']
        print(f"\n{sym}: Score {v['score']:+d} ({v['winner']}, conf {v['confidence']:.2f})")
        print(f"  Bull: {result['bull']['confidence']}/100 - {result['bull']['summary']}")
        print(f"  Bear: {result['bear']['confidence']}/100 - {result['bear']['summary']}")
