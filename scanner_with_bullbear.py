# scanner_with_bullbear.py -- Wrapper that adds bull/bear conviction to scanner output
# Usage: python scanner_with_bullbear.py [same args as scanner.py]

import subprocess, sys, json, os
from datetime import datetime

def run_scanner(args):
    """Run scanner and capture output."""
    cmd = [sys.executable, r'C:\Users\vitamnb\.openclaw\freqtrade\scanner.py'] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return result.stdout, result.stderr

def run_bull_bear(pair, entry, rsi, ema_dist, reason):
    """Run bull/bear analysis for a signal."""
    try:
        cmd = [
            sys.executable,
            r'C:\Users\vitamnb\.openclaw\freqtrade\bull_bear_researcher_v2.py',
            pair, str(entry), str(rsi), str(ema_dist), reason
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line and line.startswith('{'):
                try:
                    return json.loads(line)
                except:
                    pass
    except:
        pass
    return None

def enhance_signals(signal_text):
    """Parse scanner output and add bull/bear conviction."""
    lines = signal_text.split('\n')
    output = []
    current_signal = None
    
    for line in lines:
        # Detect signal lines
        if line.strip().startswith('[') and 'SIGNAL' in line:
            output.append(line)
            continue
        
        # Try to extract signal details
        parts = line.strip().split()
        if len(parts) >= 5 and '/' in parts[0] and parts[0].endswith('/USDT'):
            # This looks like a signal row
            pair = parts[0]
            # Find entry price (after score columns)
            entry = None
            for i, p in enumerate(parts):
                if p.startswith('$'):
                    try:
                        entry = float(p.replace('$', ''))
                        break
                    except:
                        pass
            
            if entry:
                # Run bull/bear
                bb = run_bull_bear(pair, entry, 40, 0.5, "Scanner signal")
                if bb:
                    conv = bb.get('recommendation', 'skip')
                    score = bb.get('score', 0)
                    conf = bb.get('confidence', 0)
                    
                    # Add conviction to line
                    line += f"  |  BB: {conv} ({score:+d}, {conf:.1f})"
                else:
                    line += "  |  BB: timeout"
        
        output.append(line)
    
    return '\n'.join(output)

def main():
    # Run scanner
    print("[SCANNER + Bull/Bear] Running scanner...")
    stdout, stderr = run_scanner(sys.argv[1:])
    
    # Add bull/bear to output
    enhanced = enhance_signals(stdout)
    
    print(enhanced)
    if stderr:
        print(stderr, file=sys.stderr)

if __name__ == "__main__":
    main()
