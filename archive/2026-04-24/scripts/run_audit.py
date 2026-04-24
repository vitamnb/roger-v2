import sys, subprocess
p = subprocess.run(
    [sys.executable, r'C:\Users\vitamnb\.openclaw\freqtrade\audit_layer1.py'],
    capture_output=True, text=True, encoding='utf-8', errors='replace'
)
print(p.stdout, end='')
if p.stderr:
    print(p.stderr, end='', file=sys.stderr)
sys.exit(p.returncode)
