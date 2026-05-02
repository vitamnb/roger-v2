# Launch Cascade-Fade Futures Bot
# Paper trading on KuCoin margin/futures

$FreqtradeDir = "C:\Users\vitamnb\.openclaw\freqtrade"
$PythonPath = "C:\Users\vitamnb\AppData\Local\Programs\Python\Python311\python.exe"

Write-Host "=== Launching Cascade-Fade Futures Bot ===" -ForegroundColor Green
Write-Host "Mode: Paper trade (dry_run) on KuCoin margin"
Write-Host ""

$configPath = Join-Path $FreqtradeDir "user_data\config_CascadeFade_Futures.json"
$dbPath = Join-Path $FreqtradeDir "user_data\CascadeFade_Futures.sqlite"
$logPath = Join-Path $FreqtradeDir "user_data\logs\CascadeFade_Futures.log"

Write-Host "Starting CascadeFade_Futures on port 8091..." -ForegroundColor Cyan

$proc = Start-Process -FilePath $PythonPath -ArgumentList @(
    "-m", "freqtrade", "trade",
    "--config", $configPath,
    "--strategy", "CascadeFadeFutures",
    "--db-url", "sqlite:///$dbPath",
    "--logfile", $logPath
) -WorkingDirectory $FreqtradeDir -WindowStyle Hidden -PassThru

Write-Host "  PID: $($proc.Id)" -ForegroundColor Gray
Write-Host ""
Write-Host "Dashboard: http://127.0.0.1:8091" -ForegroundColor Green
Write-Host "Login: roger / RogerDryRun2026!"
