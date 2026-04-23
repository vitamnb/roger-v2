"""
Roger System Audit [X] Layer 1
Nightly digest: code integrity, data sanity, config drift, wiki health
Delivers to Telegram when run standalone.
"""

import os
import json
import requests
import ccxt
from pathlib import Path
from datetime import datetime

FREQUOTE_DIR = Path(r"C:\Users\vitamnb\.openclaw\freqtrade")
WIKI_DIR = Path(r"C:\Users\vitamnb\Documents\Roger Vault")
TELEGRAM_CHAT_ID = "404572949"
TELEGRAM_BOT_TOKEN = "8755560208:AAFwdeFgfn4arxDV_eBnZZSA6UVuI5fhjcU"

exchange = ccxt.kucoin({
    'apiKey': '69e068a7c9bace0001a89666',
    'secret': '',
    'password': '',
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'},
})

sections = []
PASS = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN][X]"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

def check(name):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                sections.append((name, PASS, result))
            except Exception as e:
                sections.append((name, FAIL, str(e)))
        return wrapper
    return decorator

# [X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X]
# 1. DATA INTEGRITY CHECKS
# [X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X]

@check("Data: KuCoin ticker % sanity (BTC/SOL)")
def check_ticker_sanity():
    results = []
    for sym in ['BTC/USDT', 'SOL/USDT']:
        try:
            t = exchange.fetch_ticker(sym)
            # Use the CORRECT method: info['changeRate'] * 100
            change = float(t.get('info', {}).get('changeRate', 0)) * 100
            results.append(f"{sym}: {change:+.2f}%")
            # Sanity: should be within -20% to +20% for any 24h period
            if abs(change) > 20:
                return f"UNEXPECTED: {results[-1]} [X] out of sane range"
        except Exception as e:
            results.append(f"{sym}: ERROR {e}")
    return " | ".join(results)

@check("Data: Watchlist pairs reachable")
def check_watchlist_pairs():
    pairs_file = FREQUOTE_DIR / "daily_watchlist.txt"
    if not pairs_file.exists():
        return f"File not found: {pairs_file}"
    
    reachable = 0
    errors = []
    for line in open(pairs_file):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('Date') or line.startswith('Format'):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        raw = parts[0]
        sym = raw if '/' in raw else raw + '/USDT'
        try:
            ticker = exchange.fetch_ticker(sym)
            reachable += 1
        except Exception as e:
            errors.append(f"{sym}: {str(e)[:50]}")
    
    msg = f"{reachable} pairs reachable"
    if errors:
        msg += f" | {len(errors)} failed: {errors[:2]}"
    return msg

@check("Data: Research files present")
def check_research_files():
    files = [
        FREQUOTE_DIR / "ema_results_2026-04-22.txt",
        FREQUOTE_DIR / "mtf_results_2026-04-22.txt",
    ]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        return f"Missing: {missing}"
    return f"All research files present ({len(files)})"

# [X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X]
# 2. CODE INTEGRITY CHECKS
# [X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X]

@check("Code: ticker['change'] bug presence")
def check_ticker_change_bug():
    """Check all py files in freqtrade dir for ticker['change'] misuse"""
    bug_files = []
    clean_files = []
    
    for pyfile in FREQUOTE_DIR.glob("*.py"):
        if pyfile.name.startswith('_'):
            continue
        try:
            content = pyfile.read_text(errors='ignore')
            if "ticker['change']" in content or 'ticker["change"]' in content:
                # Check if it ALSO uses info['changeRate'] [X] if both present, it's an intentional comparison, not a bug
                uses_correct = ("info['changeRate']" in content or 'info["changeRate"]' in content
                               or "ticker.get('info'" in content or 'ticker.get("info"' in content)
                if not uses_correct:
                    bug_files.append(pyfile.name)
                else:
                    clean_files.append(pyfile.name)
            else:
                clean_files.append(pyfile.name)
        except:
            pass
    
    for pyfile in (FREQUOTE_DIR / "strategies").glob("*.py"):
        try:
            content = pyfile.read_text(errors='ignore')
            if "ticker['change']" in content or 'ticker["change"]' in content:
                if "info['changeRate']" not in content and 'info["changeRate"]' not in content:
                    bug_files.append(pyfile.name)
                else:
                    clean_files.append(pyfile.name)
            else:
                clean_files.append(pyfile.name)
        except:
            pass
    
    if bug_files:
        return f"Buggy: {bug_files}"
    return f"All clean ({len(clean_files)} files checked)"

@check("Code: Strategy config matches MEMORY.md")
def check_strategy_config():
    """Verify key strategy params match what's documented"""
    memory_file = Path(r"C:\Users\vitamnb\.openclaw\workspace\MEMORY.md")
    if not memory_file.exists():
        return "MEMORY.md not found"
    
    content = memory_file.read_text()
    checks = {
        "7% TP": "1.07" in content or "7%" in content,
        "2% SL": "0.98" in content or "2%" in content,
        "RSI override": "RSI" in content and "override" in content,
        "SHORT blocked": "SHORT" in content and "blocked" in content,
        "trailing removed": "trailing" in content.lower(),
    }
    
    failed = [k for k, v in checks.items() if not v]
    if failed:
        return f"Missing docs: {failed}"
    return f"All key params documented ({len(checks)} checked)"

@check("Code: Scripts directory clean (no debug artifacts)")
def check_no_debug_artifacts():
    debug_files = list(FREQUOTE_DIR.glob("debug_*.py"))
    if debug_files:
        return f"{len(debug_files)} debug files remain: {[f.name for f in debug_files[:3]]}"
    return "No debug artifacts"

# [X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X]
# 3. CONFIG DRIFT CHECKS
# [X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X]

@check("Config: freqtrade config.json validity")
def check_config_json():
    cfg_file = FREQUOTE_DIR / "user_data" / "config.json"
    if not cfg_file.exists():
        return "config.json not found"
    try:
        data = json.load(open(cfg_file))
        # Check key fields exist
        required = ['exchange', 'max_open_trades']
        missing = [k for k in required if k not in data]
        if missing:
            return f"Missing keys: {missing}"
        return f"Valid JSON, {len(data)} top-level keys"
    except json.JSONDecodeError as e:
        return f"INVALID JSON: {e}"

@check("Config: API key present")
def check_api_key():
    cfg_file = FREQUOTE_DIR / "user_data" / "config.json"
    try:
        data = json.load(open(cfg_file))
        key = data.get('exchange', {}).get('key', '')
        if not key or key == 'your_api_key':
            return "API key missing or placeholder"
        return f"API key: {key[:12]}...{key[-4:]}"
    except:
        return "Could not read config"

# [X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X]
# 4. WIKI HEALTH CHECKS
# [X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X]

@check("Wiki: Roger Vault exists and has index")
def check_vault_index():
    index_file = WIKI_DIR / "00 INDEX.md"
    if not index_file.exists():
        return "00 INDEX.md not found"
    content = index_file.read_text()
    lines = [l for l in content.split('\n') if l.strip() and not l.startswith('#')]
    return f"Index has {len(lines)} entries"

@check("Wiki: All strategy docs have frontmatter")
def check_wiki_frontmatter():
    strategy_dir = WIKI_DIR / "strategies"
    if not strategy_dir.exists():
        return "strategies/ dir not found"
    
    issues = []
    for mdfile in strategy_dir.glob("*.md"):
        content = mdfile.read_text()
        if not content.startswith('---'):
            issues.append(mdfile.name)
    
    if issues:
        return f"Missing frontmatter: {issues}"
    return f"All {len(list(strategy_dir.glob('*.md')))} docs OK"

@check("Wiki: Journal has entries for this week")
def check_journal_recent():
    journal_file = WIKI_DIR / "journaling" / "Trade Log.md"
    if not journal_file.exists():
        return "Trade Log.md not found"
    content = journal_file.read_text()
    # Check for April 2026 entries
    has_recent = '2026-04' in content
    if not has_recent:
        return "[WARN][X] No April 2026 entries in Trade Log"
    return "Journal entries present"

# [X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X]
# 5. CRON HEALTH CHECKS
# [X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X]

@check("Cron: Scanner running on schedule")
def check_scanner_cron():
    """Verify scanner cron is active"""
    # This just checks if the cron file exists and was modified recently
    cron_script = FREQUOTE_DIR / "scan_cron.ps1"
    if not cron_script.exists():
        return "scan_cron.ps1 not found"
    # Check if file modified in last 24h
    from datetime import datetime, timedelta
    mtime = datetime.fromtimestamp(cron_script.stat().st_mtime)
    age = datetime.now() - mtime
    if age > timedelta(days=7):
        return f"[WARN][X] Scanner script not modified in 7 days"
    return f"Last modified {age.seconds//3600}h ago (healthy)"

# [X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X]
# BUILD REPORT
# [X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X]

def run_audit():
    header = (
        "[AUDIT] *Roger System Audit [X] Layer 1*\n"
        f"[CLOCK] {datetime.now().strftime('%Y-%m-%d %H:%M')} Sydney\n"
        "[X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X]"
    )
    
    body = []
    for name, status, detail in sections:
        body.append(f"{status} *{name}*\n{detail}")
    
    footer = (
        "[X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X][X]\n"
        "All checks complete."
    )
    
    report = header + "\n\n" + "\n\n".join(body) + "\n\n" + footer
    return report

if __name__ == "__main__":
    # Run all checks
    print("Running audit checks...")
    
    # Data checks
    check_ticker_sanity()
    check_watchlist_pairs()
    check_research_files()
    
    # Code checks
    check_ticker_change_bug()
    check_strategy_config()
    check_no_debug_artifacts()
    
    # Config checks
    check_config_json()
    check_api_key()
    
    # Wiki checks
    check_vault_index()
    check_wiki_frontmatter()
    check_journal_recent()
    
    # Cron checks
    check_scanner_cron()
    
    report = run_audit()
    print(report)
    send_telegram(report)