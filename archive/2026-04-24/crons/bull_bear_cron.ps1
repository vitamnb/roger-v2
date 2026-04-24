# bull_bear_cron.ps1 -- Run bull/bear researcher for top pairs
# Schedule: Every 6 hours

$ErrorActionPreference = "Continue"
Set-Location "C:\Users\vitamnb\.openclaw\freqtrade"

python run_bull_bear_batch.py 2>&1 | Out-File -FilePath "bull_bear_cron.log" -Encoding utf8

Write-Output "[OK] Bull/Bear batch complete"
