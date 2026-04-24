import subprocess, time, requests, os, signal, sys

# Find freqtrade process on port 9073
print("Finding BranchA process on port 9073...")

# Use netstat to find PID
result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, shell=False)
for line in result.stdout.split('\n'):
    if ':9073' in line and 'LISTENING' in line:
        parts = line.strip().split()
        if len(parts) >= 2:
            pid = parts[-1]
            print(f"Found PID {pid} listening on port 9073")
            
            # Verify it's freqtrade
            try:
                proc_info = subprocess.run(['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV'], 
                                          capture_output=True, text=True, shell=False)
                print(f"Process info: {proc_info.stdout[:200]}")
                
                # Kill it
                print(f"Killing PID {pid}...")
                os.kill(int(pid), signal.SIGTERM)
                print(f"Sent SIGTERM to PID {pid}")
                
                # Wait for process to die
                time.sleep(3)
                
                # Check if it's dead
                check = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], 
                                    capture_output=True, text=True, shell=False)
                if 'No tasks' in check.stdout or str(pid) not in check.stdout:
                    print(f"PID {pid} is dead")
                else:
                    print(f"PID {pid} still running, trying SIGKILL...")
                    os.kill(int(pid), signal.SIGKILL)
                    
            except Exception as e:
                print(f"Error: {e}")
            break

# Wait a bit for the process to fully die
time.sleep(2)

# Now run the watchdog to test restart
print("\nRunning watchdog...")
subprocess.run([sys.executable, '-c', """
import subprocess, sys
os.chdir(r'C:\\Users\\vitamnb\\.openclaw\\freqtrade')
result = subprocess.run(['powershell', '-ExecutionPolicy', 'Bypass', '-File', 'uptime_watchdog.ps1'], 
                       capture_output=True, text=True, timeout=30)
print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)
"""], capture_output=True, text=True, timeout=30)

# Check if BranchA came back
print("\nChecking if BranchA restarted...")
time.sleep(5)
try:
    r = requests.get('http://127.0.0.1:9073/api/v1/status', auth=('roger','RogerDryRun2026!'), timeout=5)
    print(f"BranchA port 9073: HTTP {r.status_code}")
    if r.status_code == 200:
        print("SUCCESS: BranchA was restarted by watchdog!")
except Exception as e:
    print(f"BranchA still down: {e}")
