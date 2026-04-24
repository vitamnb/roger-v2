# Launch 6 Paper Trading Bots
# Run from freqtrade root directory

$bots = @(
    @{Name="Roger_v3_Sniper"; Strategy="RogerHybrid_v3"; Port=8083},
    @{Name="Roger_v2_Quality"; Strategy="RogerHybrid_v2"; Port=8084},
    @{Name="Roger_v4_Vol2x"; Strategy="RogerHybrid_v4"; Port=8085},
    @{Name="Roger_v5_Frequency"; Strategy="RogerHybrid_v5"; Port=8086},
    @{Name="Roger_v6_Workhorse"; Strategy="RogerHybrid_v6"; Port=8087},
    @{Name="Roger_v7_Conservative"; Strategy="RogerHybrid_v7"; Port=8088}
)

Write-Host "=== Launching 6 Paper Trading Bots ===" -ForegroundColor Green
Write-Host "Capital: $900 (leaving $100 reserve)"
Write-Host "Pairs: BTC, ETH, SOL, XRP, ATOM, ADA, LINK, AVAX, BNB"
Write-Host "Timeframe: 1h"
Write-Host ""

foreach ($bot in $bots) {
    Write-Host "Starting $($bot.Name) on port $($bot.Port)..." -ForegroundColor Cyan
    $job = Start-Job -ScriptBlock {
        param($name, $strategy, $port)
        $env:PYTHONPATH = "C:\Users\vitamnb\AppData\Local\Programs\Python\Python311\python.exe"
        Set-Location "C:\Users\vitamnb\.openclaw\freqtrade"
        & python -m freqtrade trade `
            --config user_data\config_paper.json `
            --strategy $strategy `
            --db-url sqlite:///user_data/$name.sqlite `
            --logfile user_data\logs\$name.log `
            --api-port $port
    } -ArgumentList $bot.Name, $bot.Strategy, $bot.Port
    Write-Host "  PID: $($job.Id)" -ForegroundColor Gray
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "All bots launched!" -ForegroundColor Green
Write-Host ""
Write-Host "Dashboard URLs:"
foreach ($bot in $bots) {
    Write-Host "  $($bot.Name): http://127.0.0.1:$($bot.Port)"
}
Write-Host ""
Write-Host "To check status: Get-Job | Format-Table"
Write-Host "To stop all: Get-Job | Stop-Job"
