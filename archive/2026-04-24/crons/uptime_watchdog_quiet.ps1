# uptime_watchdog_quiet.ps1 -- Silent health monitor, only alerts on failure
# Run every 5 minutes via cron, but only output when something is wrong

$ErrorActionPreference = "Continue"

$INSTANCES = @(
    @{
        Name = "Main"
        Port = 8080
        AuthUser = "roger"
        AuthPass = "RogerDryRun2026!"
        PidFile = "freqtrade_main.pid"
    },
    @{
        Name = "YOLO"
        Port = 8081
        AuthUser = "roger"
        AuthPass = "RogerYOLO2026!"
        PidFile = "freqtrade_yolo.pid"
    },
    @{
        Name = "BranchA"
        Port = 9073
        AuthUser = "roger"
        AuthPass = "RogerDryRun2026!"
        PidFile = "freqtrade_brancha.pid"
    }
)

$BASE_DIR = "C:\Users\vitamnb\.openclaw\freqtrade"
$LOG_FILE = "$BASE_DIR\uptime_watchdog.log"
$MAX_RESTARTS = 3
$RESTART_WINDOW = 3600
$TELEGRAM_TOKEN = "8755560208:AAFwdeFgfn4arxDV_eBnZZSA6UVuI5fhjcU"
$TELEGRAM_CHAT = "404572949"

function Send-Telegram($Message) {
    try {
        $body = @{chat_id=$TELEGRAM_CHAT; text=$Message} | ConvertTo-Json
        $headers = @{"Content-Type"="application/json"}
        Invoke-RestMethod -Uri "https://api.telegram.org/bot$TELEGRAM_TOKEN/sendMessage" -Method POST -Body $body -Headers $headers -TimeoutSec 30 | Out-Null
    } catch {}
}

function Write-Log($Message) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $Message"
    Add-Content -Path $LOG_FILE -Value $line -Encoding UTF8 -ErrorAction SilentlyContinue
}

function Check-ApiHealth($Port, $User, $Pass) {
    try {
        $url = "http://127.0.0.1:$Port/api/v1/status"
        $secpass = ConvertTo-SecureString $Pass -AsPlainText -Force
        $cred = New-Object System.Management.Automation.PSCredential($User, $secpass)
        $resp = Invoke-RestMethod -Uri $url -Method GET -Credential $cred -TimeoutSec 10 -ErrorAction Stop
        return $true
    } catch [System.Net.WebException] {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode -eq 401) {
            return $true  # Server up, wrong auth
        }
        return $false
    } catch {
        return $false
    }
}

function Get-InstanceProcessId($PidFile) {
    $path = Join-Path $BASE_DIR $PidFile
    if (Test-Path $path) {
        try {
            $pidStr = Get-Content $path -Raw
            return [int]$pidStr.Trim()
        } catch {
            return $null
        }
    }
    return $null
}

function Find-FreqtradeProcess($ProcId) {
    try {
        $proc = Get-Process -Id $ProcId -ErrorAction Stop
        if ($proc.ProcessName -match "freqtrade|python") {
            return $proc
        }
    } catch {}
    return $null
}

function Start-Instance($Instance) {
    $configMap = @{
        "Main" = "user_data\config.json"
        "YOLO" = "user_data\config_yolo.json"
        "BranchA" = "branches\signal_test\config.json"
    }
    $strategyMap = @{
        "Main" = "RogerStrategy"
        "YOLO" = "RogerYOLOStrategy"
        "BranchA" = "RogerStrategy"
    }
    
    $configPath = Join-Path $BASE_DIR $configMap[$Instance.Name]
    
    if (-not (Test-Path $configPath)) {
        Write-Log ("[FAIL] {0}: Config not found" -f $Instance.Name)
        return $false
    }
    
    try {
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = "freqtrade"
        $startInfo.Arguments = "trade --config `"$configPath`" --strategy $($strategyMap[$Instance.Name])"
        $startInfo.WorkingDirectory = $BASE_DIR
        $startInfo.UseShellExecute = $false
        $startInfo.RedirectStandardOutput = $false
        $startInfo.RedirectStandardError = $false
        $startInfo.CreateNoWindow = $true
        
        $proc = [System.Diagnostics.Process]::Start($startInfo)
        
        if ($proc) {
            $pidFile = Join-Path $BASE_DIR $Instance.PidFile
            $proc.Id | Out-File -FilePath $pidFile -Encoding UTF8 -Force
            return $true
        }
    } catch {
        Write-Log ("[FAIL] {0}: Error starting: {1}" -f $Instance.Name, $_.Exception.Message)
    }
    
    return $false
}

function Restart-Instance($Instance) {
    $restartLog = Join-Path $BASE_DIR ("restart_log_{0}.json" -f $Instance.Name.ToLower())
    $restarts = @()
    
    if (Test-Path $restartLog) {
        try {
            $restarts = Get-Content $restartLog -Raw | ConvertFrom-Json
        } catch {}
    }
    
    $cutoff = (Get-Date).AddSeconds(-$RESTART_WINDOW)
    $restarts = @($restarts | Where-Object { $_ -gt $cutoff })
    
    if ($restarts.Count -ge $MAX_RESTARTS) {
        $msg = "[ALERT] $($Instance.Name): Max restarts ($MAX_RESTARTS) reached in last hour. NOT restarting."
        Write-Log $msg
        Send-Telegram $msg
        return $false
    }
    
    $restarts += (Get-Date)
    $restarts | ConvertTo-Json | Out-File $restartLog -Encoding UTF8
    
    # Kill existing
    $oldProcId = Get-InstanceProcessId $Instance.PidFile
    if ($oldProcId) {
        $oldProc = Find-FreqtradeProcess $oldProcId
        if ($oldProc) {
            try {
                $oldProc.Kill()
                Start-Sleep -Seconds 3
            } catch {}
        }
    }
    
    return Start-Instance $Instance
}

# === MAIN CHECK ===
$alerts = @()

foreach ($inst in $INSTANCES) {
    $apiOk = Check-ApiHealth $inst.Port $inst.AuthUser $inst.AuthPass
    
    if (-not $apiOk) {
        # Check if process exists
        $oldProcId = Get-InstanceProcessId $inst.PidFile
        $proc = $null
        if ($oldProcId) {
            $proc = Find-FreqtradeProcess $oldProcId
        }
        
        if ($proc) {
            $alerts += "[WARN] $($inst.Name): Process alive but API unresponsive on port $($inst.Port)"
        } else {
            $alerts += "[DOWN] $($inst.Name): Dead on port $($inst.Port). Restarting..."
            $success = Restart-Instance $inst
            if ($success) {
                $alerts += "[RECOVERED] $($inst.Name): Restarted successfully"
            } else {
                $alerts += "[FAIL] $($inst.Name): Restart failed"
            }
        }
    }
}

# Only alert if there are issues
if ($alerts.Count -gt 0) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm"
    $alertText = "Freqtrade Alert ($ts):`n" + ($alerts -join "`n")
    Write-Log $alertText
    Send-Telegram $alertText
}
