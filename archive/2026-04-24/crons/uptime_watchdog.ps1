# uptime_watchdog.ps1 -- Freqtrade Instance Health Monitor
# Monitors all Freqtrade bots and auto-restarts crashed instances

param(
    [switch]$InstallCron,
    [switch]$Status,
    [switch]$StopAll
)

$ErrorActionPreference = "Continue"

# Configuration
$INSTANCES = @(
    @{
        Name = "Main"
        Port = 8080
        Config = "user_data\config.json"
        Strategy = "RogerStrategy"
        AuthUser = "roger"
        AuthPass = "RogerDryRun2026!"
        PidFile = "freqtrade_main.pid"
    },
    @{
        Name = "YOLO"
        Port = 8081
        Config = "user_data\config_yolo.json"
        Strategy = "RogerYOLOStrategy"
        AuthUser = "roger"
        AuthPass = "RogerYOLO2026!"
        PidFile = "freqtrade_yolo.pid"
    },
    @{
        Name = "BranchA"
        Port = 9073
        Config = "branches\signal_test\config.json"
        Strategy = "RogerStrategy"
        AuthUser = "roger"
        AuthPass = "RogerDryRun2026!"
        PidFile = "freqtrade_brancha.pid"
    }
)

$BASE_DIR = "C:\Users\vitamnb\.openclaw\freqtrade"
$LOG_FILE = "$BASE_DIR\uptime_watchdog.log"
$MAX_RESTARTS = 3
$RESTART_WINDOW = 3600

function Write-Log($Message) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $Message"
    Write-Output $line
    try {
        Add-Content -Path $LOG_FILE -Value $line -Encoding UTF8 -ErrorAction SilentlyContinue
    } catch {}
}

function Check-ApiHealth($Port, $User, $Pass) {
    try {
        $url = "http://127.0.0.1:$Port/api/v1/status"
        $secpass = ConvertTo-SecureString $Pass -AsPlainText -Force
        $cred = New-Object System.Management.Automation.PSCredential($User, $secpass)
        $resp = Invoke-RestMethod -Uri $url -Method GET -Credential $cred -TimeoutSec 10 -ErrorAction Stop
        return $true
    } catch [System.Net.WebException] {
        # Check if it's auth failure (401 = wrong password) vs actual down
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode -eq 401) {
            return $true  # Server is up, auth is just wrong
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

function Set-InstanceProcessId($PidFile, $ProcId) {
    $path = Join-Path $BASE_DIR $PidFile
    $ProcId | Out-File -FilePath $path -Encoding UTF8 -Force
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
    $configPath = Join-Path $BASE_DIR $Instance.Config
    
    if (-not (Test-Path $configPath)) {
        Write-Log ("[FAIL] {0}: Config not found: {1}" -f $Instance.Name, $configPath)
        return $false
    }
    
    Write-Log ("[START] {0}: Starting freqtrade on port {1}" -f $Instance.Name, $Instance.Port)
    
    try {
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = "freqtrade"
        $startInfo.Arguments = "trade --config `"$configPath`" --strategy $($Instance.Strategy)"
        $startInfo.WorkingDirectory = $BASE_DIR
        $startInfo.UseShellExecute = $false
        $startInfo.RedirectStandardOutput = $false
        $startInfo.RedirectStandardError = $false
        $startInfo.CreateNoWindow = $true
        
        $proc = [System.Diagnostics.Process]::Start($startInfo)
        
        if ($proc) {
            Set-InstanceProcessId $Instance.PidFile $proc.Id
            Write-Log ("[OK] {0}: Started PID {1} on port {2}" -f $Instance.Name, $proc.Id, $Instance.Port)
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
        Write-Log ("[ALERT] {0}: Max restarts ({1}) reached in last hour. NOT restarting." -f $Instance.Name, $MAX_RESTARTS)
        return $false
    }
    
    $restarts += (Get-Date)
    $restarts | ConvertTo-Json | Out-File $restartLog -Encoding UTF8
    
    # Kill existing process
    $oldProcId = Get-InstanceProcessId $Instance.PidFile
    if ($oldProcId) {
        $oldProc = Find-FreqtradeProcess $oldProcId
        if ($oldProc) {
            try {
                $oldProc.Kill()
                Write-Log ("[KILL] {0}: Killed old process PID {1}" -f $Instance.Name, $oldProcId)
                Start-Sleep -Seconds 3
            } catch {}
        }
    }
    
    return Start-Instance $Instance
}

function Check-Instance($Instance) {
    $apiOk = Check-ApiHealth $Instance.Port $Instance.AuthUser $Instance.AuthPass
    
    if ($apiOk) {
        return @{ Status = "HEALTHY"; Action = "None" }
    }
    
    $oldProcId = Get-InstanceProcessId $Instance.PidFile
    $proc = $null
    if ($oldProcId) {
        $proc = Find-FreqtradeProcess $oldProcId
    }
    
    if ($proc) {
        return @{ Status = "DEGRADED"; Action = "Monitor" }
    }
    
    return @{ Status = "DOWN"; Action = "Restart" }
}

function Main() {
    if ($Status) {
        Write-Output "=== Freqtrade Health Status ==="
        foreach ($inst in $INSTANCES) {
            $result = Check-Instance $inst
            Write-Output ("{0,-10} | Port {1,-6} | {2,-10} | Action: {3}" -f $inst.Name, $inst.Port, $result.Status, $result.Action)
        }
        return
    }
    
    if ($StopAll) {
        Write-Log "=== STOPPING ALL INSTANCES ==="
        foreach ($inst in $INSTANCES) {
            $oldProcId = Get-InstanceProcessId $inst.PidFile
            if ($oldProcId) {
                $oldProc = Find-FreqtradeProcess $oldProcId
                if ($oldProc) {
                    try {
                        $oldProc.Kill()
                        Write-Log ("[STOP] {0}: Killed PID {1}" -f $inst.Name, $oldProcId)
                    } catch {
                        Write-Log ("[FAIL] {0}: Could not kill PID {1}: {2}" -f $inst.Name, $oldProcId, $_.Exception.Message)
                    }
                }
            }
        }
        return
    }
    
    if ($InstallCron) {
        Write-Log "Cron installation not yet implemented. Run manually or schedule via Task Scheduler."
        return
    }
    
    Write-Log "=== UPTIME WATCHDOG CHECK ==="
    
    foreach ($inst in $INSTANCES) {
        $result = Check-Instance $inst
        
        if ($result.Action -eq "None") {
            Write-Log ("[OK] {0}: Healthy on port {1}" -f $inst.Name, $inst.Port)
        } elseif ($result.Action -eq "Monitor") {
            Write-Log ("[WARN] {0}: Degraded on port {1} - process exists but API unresponsive" -f $inst.Name, $inst.Port)
        } elseif ($result.Action -eq "Restart") {
            Write-Log ("[DOWN] {0}: Not responding on port {1} - restarting..." -f $inst.Name, $inst.Port)
            $success = Restart-Instance $inst
            if (-not $success) {
                Write-Log ("[FAIL] {0}: Restart failed" -f $inst.Name)
            }
        }
    }
    
    Write-Log "=== CHECK COMPLETE ==="
}

Main
