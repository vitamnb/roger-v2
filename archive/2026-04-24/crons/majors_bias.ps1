# Majors Bias Check — daily at 9am Sydney
$ErrorActionPreference = 'SilentlyContinue'
$log = "$env:USERPROFILE\.openclaw\freqtrade\majors_log.txt"
$out = & "$env:USERPROFILE\.openclaw\freqtrade\.venv\Scripts\python.exe" `
    "$env:USERPROFILE\.openclaw\freqtrade\scanner.py" `
    --majors 2>&1
$ts = Get-Date -Format "yyyy-MM-dd HH:mm"
"$ts AEST | Majors Bias Check" | Out-File -FilePath $log -Append
$out | Out-File -FilePath $log -Append
Write-Host "Majors bias check done. See $log"
