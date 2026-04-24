import requests
import ccxt

# Get AUD rate
try:
    r = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=aud', timeout=10)
    aud_rate = float(r.json()['tether']['aud'])
    print(f"AUD/USD rate: {aud_rate:.4f}")
except Exception as e:
    aud_rate = 1.56  # fallback estimate
    print(f"Could not fetch AUD rate: {e}, using fallback {aud_rate}")

usd_to_aud = aud_rate
aud_to_usd = 1 / aud_rate

usd_capital = 1000
aud_capital = usd_capital * usd_to_aud

print(f"Starting capital: ${usd_capital:,.2f} USD = ${aud_capital:,.2f} AUD")
print()

# Run freqtrade backtest
import subprocess
import os

os.chdir(r"C:\Users\vitamnb\.openclaw\freqtrade")

print("Running Freqtrade backtest (strategy v5, 90 days)...")
result = subprocess.run([
    'freqtrade', 'backtest',
    '--config', 'user_data/config.json',
    '--strategy', 'RogerStrategy',
    '--timerange', '20260122-20260422',
    '--stake-amount', '20',
    '--initial-balance', '1000',
    '--trading-mode', 'spot',
    '--export', ' trades',
    '--export-filename', 'backtest_results.json'
], capture_output=True, text=True, timeout=300)

print("STDOUT:", result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout)
print("STDERR:", result.stderr[-1000:] if result.stderr else "")
print("Return code:", result.returncode)