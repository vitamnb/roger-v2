# Launch 6 Paper Trading Bots
# Uses Start-Process for proper working directory control

$FreqtradeDir = "C:\Users\vitamnb\.openclaw\freqtrade"
$PythonPath = "C:\Users\vitamnb\AppData\Local\Programs\Python\Python311\python.exe"

$bots = @(
    @{Name="Roger_v3_Sniper"; Strategy="RogerHybrid_v3"; Port=8083},
    @{Name="Roger_v2_Quality"; Strategy="RogerHybrid_v2"; Port=8084},
    @{Name="Roger_v4_Vol2x"; Strategy="RogerHybrid_v4"; Port=8085},
    @{Name="Roger_v5_Frequency"; Strategy="RogerHybrid_v5"; Port=8086},
    @{Name="Roger_v6_Workhorse"; Strategy="RogerHybrid_v6"; Port=8087},
    @{Name="Roger_v7_Conservative"; Strategy="RogerHybrid_v7"; Port=8088}
)

Write-Host "=== Launching 6 Paper Trading Bots ===" -ForegroundColor Green
Write-Host ""

foreach ($bot in $bots) {
    $configPath = Join-Path $FreqtradeDir "user_data\config_$($bot.Name).json"
    $dbPath = Join-Path $FreqtradeDir "user_data\$($bot.Name).sqlite"
    $logPath = Join-Path $FreqtradeDir "user_data\logs\$($bot.Name).log"
    
    Write-Host "Starting $($bot.Name) on port $($bot.Port)..." -ForegroundColor Cyan
    
    $proc = Start-Process -FilePath $PythonPath -ArgumentList @(
        "-m", "freqtrade", "trade",
        "--config", $configPath,
        "--strategy", $bot.Strategy,
        "--db-url", "sqlite:///$dbPath",
        "--logfile", $logPath
    ) -WorkingDirectory $FreqtradeDir -WindowStyle Hidden -PassThru
    
    Write-Host "  PID: $($proc.Id)" -ForegroundColor Gray
    Start-Sleep -Seconds 3
}

Write-Host ""
Write-Host "All bots launched!" -ForegroundColor Green
Write-Host ""
Write-Host "Dashboard URLs:"
foreach ($bot in $bots) {
    Write-Host "  $($bot.Name): http://127.0.0.1:$($bot.Port)"
}
Write-Host ""
Write-Host "Note: First trade may take 1-4 hours (waiting for 1h candle close)"
