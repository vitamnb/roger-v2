import subprocess, sys, os
os.chdir(r'C:\Users\vitamnb\.openclaw\freqtrade\branches\signal_test')
result = subprocess.run([sys.executable, 'signal_agents.py'], capture_output=True, text=True, timeout=60)
print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)
sys.exit(result.returncode)
