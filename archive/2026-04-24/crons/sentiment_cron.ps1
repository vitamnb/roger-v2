# sentiment_cron.ps1 -- Run sentiment scraper every 6 hours
# Schedule: cron 0 */6 * * * @ Australia/Sydney

$ErrorActionPreference = "Continue"

$BASE_DIR = "C:\Users\vitamnb\.openclaw\freqtrade"
Set-Location $BASE_DIR

# Run sentiment scraper
python sentiment_scraper.py 2>&1 | Out-File -FilePath "sentiment_cron.log" -Encoding utf8

# Check if output was created
if (Test-Path "sentiment_data.json") {
    Write-Output "[OK] Sentiment data updated"
    
    # Read the result for Telegram notification
    $result = ""
    try {
        $result = Get-Content "sentiment_data.json" -Raw | ConvertFrom-Json -ErrorAction Stop
    } catch {}
    
    $combinedScore = if ($result.combined) { $result.combined.score } else { "N/A" }
    $combinedConf = if ($result.combined) { $result.combined.confidence } else { "N/A" }
    $sourceCount = if ($result.sources) { $result.sources.Count } else { 0 }
    
    # Copy to branch if it exists
    if (Test-Path "branches\signal_test\signal_agents.py") {
        Copy-Item "sentiment_data.json" "branches\signal_test\sentiment_data.json" -Force
        Write-Output "[OK] Copied to signal_test branch"
    }
    
    # Send Telegram notification
    $token = "8755560208:AAFwdeFgfn4arxDV_eBnZZSA6UVuI5fhjcU"
    $chat = "404572949"
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm"
    
    # Determine sentiment label
    $label = if ($combinedScore -ge 20) { "BULLISH" } elseif ($combinedScore -le -20) { "BEARISH" } else { "NEUTRAL" }
    
    $msg = "Sentiment Update ($ts): $label ($combinedScore, conf: $combinedConf)`nSources: $sourceCount | Data saved to sentiment_data.json"
    
    try {
        $body = @{chat_id=$chat; text=$msg} | ConvertTo-Json
        $headers = @{"Content-Type"="application/json"}
        Invoke-RestMethod -Uri "https://api.telegram.org/bot$token/sendMessage" -Method POST -Body $body -Headers $headers -TimeoutSec 30 | Out-Null
        Write-Output "[OK] Telegram notification sent"
    } catch {
        Write-Output "[WARN] Telegram send failed: $_"
    }
} else {
    Write-Output "[FAIL] Sentiment data not created"
    
    # Send failure alert
    $token = "8755560208:AAFwdeFgfn4arxDV_eBnZZSA6UVuI5fhjcU"
    $chat = "404572949"
    $msg = "[ALERT] Sentiment scraper failed at $(Get-Date -Format 'yyyy-MM-dd HH:mm'). Check sentiment_cron.log"
    try {
        $body = @{chat_id=$chat; text=$msg} | ConvertTo-Json
        Invoke-RestMethod -Uri "https://api.telegram.org/bot$token/sendMessage" -Method POST -Body $body -TimeoutSec 30 | Out-Null
    } catch {}
    
    exit 1
}
