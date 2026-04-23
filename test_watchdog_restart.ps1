# Test watchdog restart functionality
Write-Output "=== Testing Watchdog Restart ==="

# Step 1: Check current state
Write-Output "`nStep 1: Checking current BranchA state..."
$statusBefore = & powershell -ExecutionPolicy Bypass -File "$PSScriptRoot\uptime_watchdog.ps1" -Status 2>&1
Write-Output $statusBefore

# Step 2: Find and kill BranchA process
Write-Output "`nStep 2: Killing BranchA process..."
$portInfo = netstat -ano | findstr :9073 | findstr LISTENING
if ($portInfo) {
    $parts = $portInfo -split '\s+'
    $pidToKill = $parts[-1]
    Write-Output "Found PID $pidToKill on port 9073"
    
    try {
        Stop-Process -Id $pidToKill -Force -ErrorAction Stop
        Write-Output "Killed PID $pidToKill"
    } catch {
        Write-Output "Error killing process: $_"
    }
} else {
    Write-Output "No process found on port 9073"
}

# Wait for process to die
Start-Sleep -Seconds 3

# Step 3: Verify it's down
Write-Output "`nStep 3: Verifying BranchA is down..."
try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:9073/api/v1/status" -Method GET `
              -Credential (New-Object System.Management.Automation.PSCredential("roger", (ConvertTo-SecureString "RogerDryRun2026!" -AsPlainText -Force))) `
              -TimeoutSec 5 -ErrorAction Stop
    Write-Output "WARNING: BranchA still responding!"
} catch {
    Write-Output "Confirmed: BranchA is down"
}

# Step 4: Run watchdog to trigger restart
Write-Output "`nStep 4: Running watchdog restart..."
& "$PSScriptRoot\uptime_watchdog.ps1" 2>&1

# Wait for restart
Write-Output "`nWaiting 5 seconds for restart..."
Start-Sleep -Seconds 5

# Step 5: Verify restart
Write-Output "`nStep 5: Verifying BranchA restarted..."
try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:9073/api/v1/status" -Method GET `
              -Credential (New-Object System.Management.Automation.PSCredential("roger", (ConvertTo-SecureString "RogerDryRun2026!" -AsPlainText -Force))) `
              -TimeoutSec 10 -ErrorAction Stop
    Write-Output "SUCCESS: BranchA is back up on port 9073!"
} catch {
    Write-Output "FAIL: BranchA did not restart. Error: $_"
}

Write-Output "`n=== Test Complete ==="
