# sentiment_scraper.py -- Browser-based sentiment collection
# Uses agent-browser to scrape social sentiment without API costs
# Version 2 - improved Reddit parsing, more sources

import subprocess, json, re, os, time
from datetime import datetime

SENTIMENT_FILE = os.path.join(os.path.dirname(__file__), "sentiment_data.json")

def run_browser_command(cmd, timeout=30):
    """Run agent-browser command and capture output."""
    full_cmd = f"agent-browser --auto-connect {cmd}"
    try:
        result = subprocess.run(
            full_cmd, capture_output=True, text=True, timeout=timeout,
            shell=True, cwd=os.path.dirname(__file__),
            encoding='utf-8', errors='replace'
        )
        return result.stdout or "", result.stderr or "", result.returncode
    except Exception as e:
        return "", str(e), 1

def parse_text_from_snapshot(stdout):
    """Extract readable text from agent-browser snapshot output."""
    texts = []
    if not stdout:
        return texts
    for line in stdout.split('\n'):
        # Look for link text (most page content is in links)
        if 'link' in line or 'heading' in line or 'generic' in line:
            # Extract text after the type and before [ref=]
            match = re.search(r'(?:link|heading|generic)\s+"([^"]+)"', line)
            if match:
                text = match.group(1).strip()
                if len(text) > 5 and not text.startswith('http'):
                    texts.append(text)
        # Also grab generic text blocks
        elif 'generic' in line and '"' in line:
            match = re.search(r'"([^"]{10,200})"', line)
            if match:
                texts.append(match.group(1).strip())
    return texts

def scrape_reddit_crypto():
    """Scrape r/CryptoCurrency hot posts using Reddit JSON API."""
    import requests
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        resp = requests.get(
            'https://www.reddit.com/r/CryptoCurrency/hot.json?limit=25',
            headers=headers, timeout=30
        )
        
        if resp.status_code != 200:
            return {"error": f"Reddit API returned {resp.status_code}"}
        
        data = resp.json()
        posts = []
        
        for child in data['data']['children']:
            post = child['data']
            title = post.get('title', '')
            
            if any(word in title.lower() for word in [
                'btc', 'eth', 'bitcoin', 'ethereum', 'crypto', 'altcoin',
                'bull', 'bear', 'pump', 'dump', 'moon', 'crash',
                'hodl', 'defi', 'nft', 'blockchain', 'mining',
                'binance', 'coinbase', 'kucoin', 'trading', 'market',
                'price', 'rally', 'surge', 'drop', 'analysis'
            ]):
                posts.append(title)
        
        return {
            "source": "reddit_r_cryptocurrency",
            "posts_sampled": len(posts),
            "posts": posts[:15],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        return {"error": f"Reddit API error: {str(e)[:200]}"}

def scrape_cryptopanic():
    """Scrape CryptoPanic for news sentiment."""
    stdout, stderr, rc = run_browser_command(
        'batch "open https://cryptopanic.com/news/" "wait 5000" "snapshot -i"',
        timeout=60
    )
    if rc != 0:
        return {"error": f"Browser failed: {stderr[:200]}"}
    
    texts = parse_text_from_snapshot(stdout)
    
    headlines = []
    for t in texts:
        if len(t) > 20 and len(t) < 200:
            if any(word in t.lower() for word in [
                'bitcoin', 'ethereum', 'crypto', 'btc', 'eth',
                'blockchain', 'defi', 'nft', 'altcoin', 'trading'
            ]):
                headlines.append(t)
    
    seen = set()
    unique_headlines = []
    for h in headlines:
        if h not in seen:
            seen.add(h)
            unique_headlines.append(h)
    
    return {
        "source": "cryptopanic",
        "headlines_sampled": len(unique_headlines),
        "headlines": unique_headlines[:15],
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

def scrape_cointelegraph():
    """Scrape CoinTelegraph for news sentiment."""
    stdout, stderr, rc = run_browser_command(
        'batch "open https://cointelegraph.com/" "wait 5000" "snapshot -i"',
        timeout=60
    )
    if rc != 0:
        return {"error": f"Browser failed: {stderr[:200]}"}
    
    texts = parse_text_from_snapshot(stdout)
    
    headlines = []
    for t in texts:
        if len(t) > 20 and len(t) < 200:
            if any(word in t.lower() for word in [
                'bitcoin', 'ethereum', 'crypto', 'btc', 'eth',
                'blockchain', 'defi', 'nft', 'altcoin', 'market',
                'price', 'rally', 'crash', 'surge', 'drop'
            ]):
                headlines.append(t)
    
    seen = set()
    unique_headlines = []
    for h in headlines:
        if h not in seen:
            seen.add(h)
            unique_headlines.append(h)
    
    return {
        "source": "cointelegraph",
        "headlines_sampled": len(unique_headlines),
        "headlines": unique_headlines[:15],
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

def scrape_coindesk():
    """Scrape CoinDesk for news sentiment."""
    stdout, stderr, rc = run_browser_command(
        'batch "open https://www.coindesk.com/" "wait 5000" "snapshot -i"',
        timeout=60
    )
    if rc != 0:
        return {"error": f"Browser failed: {stderr[:200]}"}
    
    texts = parse_text_from_snapshot(stdout)
    
    headlines = []
    for t in texts:
        if len(t) > 20 and len(t) < 200:
            if any(word in t.lower() for word in [
                'bitcoin', 'ethereum', 'crypto', 'btc', 'eth',
                'blockchain', 'defi', 'nft', 'altcoin', 'market',
                'price', 'rally', 'crash', 'surge', 'drop'
            ]):
                headlines.append(t)
    
    seen = set()
    unique_headlines = []
    for h in headlines:
        if h not in seen:
            seen.add(h)
            unique_headlines.append(h)
    
    return {
        "source": "coindesk",
        "headlines_sampled": len(unique_headlines),
        "headlines": unique_headlines[:15],
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

def analyze_sentiment(texts):
    """Simple keyword-based sentiment analysis."""
    bullish_words = ['bull', 'bullish', 'moon', 'pump', 'rally', 'breakout',
                     'surge', 'gain', 'up', 'green', ' ath', 'all time high',
                     ' ATH', 'soar', 'rocket', 'explode', 'boom', 'rallying']
    bearish_words = ['bear', 'bearish', 'dump', 'crash', 'fall', 'drop', 'down',
                       'red', 'correction', 'sell', 'panic', 'rug', 'plunge',
                       'collapse', 'tank', 'bleed', 'crash']
    
    bullish_count = 0
    bearish_count = 0
    
    for text in texts:
        text_lower = text.lower()
        for word in bullish_words:
            if word in text_lower:
                bullish_count += 1
        for word in bearish_words:
            if word in text_lower:
                bearish_count += 1
    
    total = bullish_count + bearish_count
    if total == 0:
        return {"score": 0, "confidence": 0.3, "details": "No sentiment keywords found"}
    
    score = ((bullish_count - bearish_count) / total) * 100
    confidence = min(0.9, 0.3 + (total / 30) * 0.15)
    
    return {
        "score": round(score, 1),
        "confidence": round(confidence, 2),
        "bullish_mentions": bullish_count,
        "bearish_mentions": bearish_count,
        "details": f"{bullish_count} bullish, {bearish_count} bearish keywords"
    }

def collect_all_sentiment():
    """Collect sentiment from all free sources."""
    print("=== Collecting Market Sentiment (Free Sources) ===")
    print(f"Started: {datetime.utcnow().isoformat()}Z")
    print()
    
    sources_data = {}
    all_texts = []
    
    # 1. Reddit
    print("[1/4] Scraping Reddit r/CryptoCurrency...")
    reddit_data = scrape_reddit_crypto()
    if "error" not in reddit_data:
        sources_data["reddit"] = reddit_data
        all_texts.extend(reddit_data.get("posts", []))
        reddit_sentiment = analyze_sentiment(reddit_data.get("posts", []))
        print(f"      OK: {reddit_sentiment['score']:+.1f} (conf: {reddit_sentiment['confidence']})")
        print(f"      Posts: {reddit_data['posts_sampled']}")
        for p in reddit_data.get("posts", [])[:3]:
            print(f"      - {p[:70]}")
    else:
        reddit_sentiment = {"score": 0, "confidence": 0, "details": reddit_data["error"]}
        print(f"      WARN: {reddit_data['error']}")
    
    # 2. CryptoPanic
    print("\n[2/4] Scraping CryptoPanic...")
    panic_data = scrape_cryptopanic()
    if "error" not in panic_data:
        sources_data["cryptopanic"] = panic_data
        all_texts.extend(panic_data.get("headlines", []))
        panic_sentiment = analyze_sentiment(panic_data.get("headlines", []))
        print(f"      OK: {panic_sentiment['score']:+.1f} (conf: {panic_sentiment['confidence']})")
        print(f"      Headlines: {panic_data['headlines_sampled']}")
        for h in panic_data.get("headlines", [])[:3]:
            print(f"      - {h[:70]}")
    else:
        panic_sentiment = {"score": 0, "confidence": 0, "details": panic_data["error"]}
        print(f"      WARN: {panic_data['error']}")
    
    # 3. CoinTelegraph
    print("\n[3/4] Scraping CoinTelegraph...")
    ct_data = scrape_cointelegraph()
    if "error" not in ct_data:
        sources_data["cointelegraph"] = ct_data
        all_texts.extend(ct_data.get("headlines", []))
        ct_sentiment = analyze_sentiment(ct_data.get("headlines", []))
        print(f"      OK: {ct_sentiment['score']:+.1f} (conf: {ct_sentiment['confidence']})")
        print(f"      Headlines: {ct_data['headlines_sampled']}")
        for h in ct_data.get("headlines", [])[:3]:
            print(f"      - {h[:70]}")
    else:
        ct_sentiment = {"score": 0, "confidence": 0, "details": ct_data["error"]}
        print(f"      WARN: {ct_data['error']}")
    
    # 4. CoinDesk
    print("\n[4/4] Scraping CoinDesk...")
    cd_data = scrape_coindesk()
    if "error" not in cd_data:
        sources_data["coindesk"] = cd_data
        all_texts.extend(cd_data.get("headlines", []))
        cd_sentiment = analyze_sentiment(cd_data.get("headlines", []))
        print(f"      OK: {cd_sentiment['score']:+.1f} (conf: {cd_sentiment['confidence']})")
        print(f"      Headlines: {cd_data['headlines_sampled']}")
        for h in cd_data.get("headlines", [])[:3]:
            print(f"      - {h[:70]}")
    else:
        cd_sentiment = {"score": 0, "confidence": 0, "details": cd_data["error"]}
        print(f"      WARN: {cd_data['error']}")
    
    # Calculate combined
    all_sentiment = analyze_sentiment(all_texts)
    active_sources = [k for k, v in sources_data.items() if "error" not in v]
    
    result = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "sources": {
            "reddit": reddit_sentiment,
            "cryptopanic": panic_sentiment,
            "cointelegraph": ct_sentiment,
            "coindesk": cd_sentiment
        },
        "combined": {
            "score": all_sentiment["score"],
            "confidence": all_sentiment["confidence"],
            "sources_used": active_sources,
            "total_texts_analyzed": len(all_texts)
        },
        "raw_data": sources_data
    }
    
    with open(SENTIMENT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n{'='*50}")
    print(f"COMBINED SENTIMENT: {result['combined']['score']:+.1f}")
    print(f"Confidence: {result['combined']['confidence']}")
    print(f"Sources: {', '.join(active_sources)}")
    print(f"Total texts: {len(all_texts)}")
    print(f"Saved: {SENTIMENT_FILE}")
    print(f"{'='*50}")
    
    return result

if __name__ == "__main__":
    collect_all_sentiment()
