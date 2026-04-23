import subprocess
import os

cmd = 'agent-browser --auto-connect batch "open https://old.reddit.com/r/CryptoCurrency/hot/" "wait 5000" "screenshot"'
result = subprocess.run(
    cmd, capture_output=True, text=True, shell=True, timeout=60,
    encoding='utf-8', errors='replace'
)

# Find the screenshot path from output
screenshot_path = None
for line in (result.stdout or '').split('\n'):
    if 'screenshot' in line.lower() and 'tmp' in line:
        parts = line.split()
        for part in parts:
            if 'screenshot' in part and part.endswith('.png'):
                screenshot_path = part
                break

# If not found in stdout, check tmp directory
if not screenshot_path:
    tmp_dir = r'C:\Users\vitamnb\.agent-browser\tmp\screenshots'
    if os.path.exists(tmp_dir):
        files = sorted([f for f in os.listdir(tmp_dir) if f.endswith('.png')])
        if files:
            screenshot_path = os.path.join(tmp_dir, files[-1])

if screenshot_path and os.path.exists(screenshot_path):
    print(f"Screenshot saved: {screenshot_path}")
else:
    print("No screenshot found")
    print("STDOUT:", result.stdout[:500] if result.stdout else 'empty')
