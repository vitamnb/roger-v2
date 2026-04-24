$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue
$procs | Where-Object { $_.CommandLine -like '*freqtrade*' } | ForEach-Object {
    Write-Output "PID: $($_.ProcessId)"
    Write-Output "Command: $($_.CommandLine)"
}
if ($procs.Count -eq 0) {
    Write-Output "No python.exe processes found"
}
