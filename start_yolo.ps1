# start_yolo.ps1
# Start Roger YOLO Freqtrade instance on port 8081
param(
    [string]$FreqtradeExe = "C:\Users\vitamnb\AppData\Local\Programs\Python\Python311\Scripts\freqtrade.exe",
    [string]$ConfigFile = "C:\Users\vitamnb\.openclaw\freqtrade\user_data\config_yolo.json",
    [string]$Strategy = "RogerYOLOStrategy",
    [string]$WorkDir = "C:\Users\vitamnb\.openclaw\freqtrade"
)

$env:PYTHONIOENCODING = "utf-8"
$proc = Start-Process -FilePath $FreqtradeExe `
    -ArgumentList "trade","--config","$ConfigFile","--strategy","$Strategy" `
    -PassThru `
    -WorkingDirectory $WorkDir `
    -RedirectStandardOutput "$WorkDir\yolo_stdout.log" `
    -RedirectStandardError "$WorkDir\yolo_stderr.log"

Write-Output "YOLO instance started. PID: $($proc.Id)"
