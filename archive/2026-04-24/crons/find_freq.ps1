Get-Process -Name 'python' -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*freqtrade*' } | ForEach-Object {
    Write-Output "PID: $($_.Id)"
    Write-Output "Command: $($_.CommandLine)"
}
