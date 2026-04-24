# Migration Checklist: PC → Cloud VPS

**Purpose:** Move OpenClaw + Freqtrade from Benny's Windows PC to a cloud VPS.
**Trigger:** When live trading begins, or PC can't stay on 24/7.
**Estimated time:** 1–2 hours.

---

## Phase 1: Choose Your Cloud Provider

### Option A — Oracle Cloud (RECOMMENDED — free forever)
- Sign up at cloud.oracle.com
- Use "Always Free" tier: 1GB RAM, 1 AMD processor, 200GB block volume
- Create a Ubuntu 22.04 instance
- Download SSH private key (.pem)
- Open ports: 22 (SSH), 8080 (Freqtrade WebUI — bind to 0.0.0.0), 443 (optional)

### Option B — DigitalOcean ($4–6/month)
- Sign up at digitalocean.com
- Create Debian/Ubuntu droplet, 1GB RAM
- Get root password or SSH key
- Open firewall port 8080

### Option C — AWS EC2 (free 12 months, then ~$10/mo)
- aws.amazon.com → Free tier EC2
- t3.micro (2 vCPU, 1GB RAM)
- Ubuntu 22.04 LTS
- Elastic IP (free while instance running)

---

## Phase 2: Set Up the Server

### 2.1 — Connect via SSH
```bash
ssh -i /path/to/key.pem ubuntu@YOUR_SERVER_IP
```

### 2.2 — Install dependencies
```bash
# Update
sudo apt update && sudo apt upgrade -y

# Python 3.11+
sudo apt install -y python3 python3-pip python3-venv git curl wget

# Node.js 18+ (for OpenClaw)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# PM2 (keeps processes alive)
sudo npm install -g pm2

# Verify
python3 --version   # should be 3.11+
node --version      # should be 18+
pm2 --version
```

### 2.3 — Install Freqtrade
```bash
# Clone or upload freqtrade
cd /opt
# Option A — clone from GitHub (if repo is public)
git clone https://github.com/vitamnb/roger-v2.git

# Option B — rsync from local PC
# Run on LOCAL PC:
rsync -avz --exclude '*.sqlite-shm' --exclude '*.sqlite-wal' \
  C:\Users\vitamnb\.openclaw\freqtrade/ \
  ubuntu@YOUR_SERVER_IP:/opt/freqtrade/
```

---

## Phase 3: Configure Freqtrade

### 3.1 — Create virtual environment
```bash
cd /opt/freqtrade
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install freqtrade
```

### 3.2 — Fix config paths (Windows → Linux)
Edit `user_data/config.json`:
- `"config_files"` paths: Linux format if hardcoded
- `"user_data"` should be `/opt/freqtrade/user_data`
- Database path: `/opt/freqtrade/tradesv3.dryrun.sqlite`

### 3.3 — Update KuCoin config
```bash
# Verify exchange is set to kucoin
# API keys can be re-entered or copied from:
# C:\Users\vitamnb\.openclaw\freqtrade\user_data\config.json
```

### 3.4 — Update scanner paths
Edit any scripts that have hardcoded `C:\Users\...` paths — change to `/opt/freqtrade/`.

Key files to audit:
- `scanner.py` — check API paths
- `price_check.py` — check DB path
- `journal.py` — check DB path
- `scan_cron.ps1` → rewrite as `scan_cron.sh` (PowerShell → bash)
- `clawstreet_heartbeat.py` — paths OK, check credentials file path
- `run_scan.ps1` → `run_scan.sh`

### 3.5 — Start Freqtrade manually to test
```bash
cd /opt/freqtrade
source venv/bin/activate
freqtrade trade --strategy RogerStrategy --dry-run 2>&1 &
```

Check WebUI: `http://YOUR_SERVER_IP:8080`

---

## Phase 4: Install OpenClaw

### 4.1 — Install OpenClaw
```bash
npm install -g openclaw
```

### 4.2 — Copy OpenClaw config
```bash
# Copy from local PC to server
rsync -avz C:\Users\vitamnb\.openclaw\openclaw.json \
  ubuntu@YOUR_SERVER_IP:~/.openclaw/openclaw.json
```

### 4.3 — Copy cron jobs
Cron jobs are stored at:
`C:\Users\vitamnb\.openclaw\.openclaw\cron\jobs.json`

Copy this file to the new machine. OpenClaw will pick up the jobs on restart.

### 4.4 — Test OpenClaw
```bash
openclaw gateway start
openclaw status
```

---

## Phase 5: Set Up Process Manager (PM2)

### 5.1 — Freqtrade as PM2 service
```bash
cd /opt/freqtrade
pm2 start freqtrade --name "freqtrade" -- \
  trade --strategy RogerStrategy --dry-run \
  --userdir /opt/freqtrade/user_data \
  --config /opt/freqtrade/user_data/config.json

pm2 save           # save startup list
pm2 startup        # auto-restart on reboot
```

### 5.2 — OpenClaw as PM2 service
```bash
pm2 start openclaw --name "openclaw" -- gateway start
pm2 save
```

### 5.3 — Useful PM2 commands
```bash
pm2 list            # show all processes
pm2 logs freqtrade  # view freqtrade logs
pm2 restart all     # restart everything
pm2 monit           # visual monitor
```

---

## Phase 6: DNS + Security (Optional but Recommended)

### 6.1 — Domain name
- Buy a domain (e.g. `roger.example.com`) from Namecheap/Cloudflare
- Point A record to your server IP
- Add subdomain: `freqtrade.roger.example.com → YOUR_IP:8080`

### 6.2 — Firewall
```bash
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS (if using reverse proxy)
sudo ufw enable
```

### 6.3 — Reverse proxy (nginx) — optional
```bash
sudo apt install -y nginx
# Proxy port 8080 → port 80 for WebUI access
```

---

## Phase 7: Verify Everything Works

### Checklist
- [ ] Freqtrade WebUI accessible at `http://SERVER_IP:8080`
- [ ] OpenClaw WebUI accessible
- [ ] Telegram bot responding
- [ ] Scanner cron firing and reporting
- [ ] Trade monitor cron firing
- [ ] ClawStreet heartbeat firing
- [ ] Database reading/writing correctly
- [ ] Strategy placing trades
- [ ] Stops and TPs set correctly

### Smoke test commands
```bash
# Freqtrade API
curl -s http://localhost:8080/api/v1/balance -u roger:RogerDryRun2026!

# Check crons
openclaw crons list

# Paper trade check
curl -s http://localhost:8080/api/v1/status -u roger:RogerDryRun2026!
```

---

## What Changes When Going LIVE (not paper)

When migrating from paper to real:
1. Change `--dry-run` flag to live trading
2. Update API keys — paper vs live KuCoin keys are DIFFERENT
3. Change `tradesv3.dryrun.sqlite` → new live DB
4. Test with $10 first before committing real capital
5. Update `force_entry_enable` and `max_open_trades` for live risk
6. Remove `dry_run` from config.json

---

## Quick Reference: Local PC → Server File Map

| Local | Server |
|-------|--------|
| `C:\Users\vitamnb\.openclaw\freqtrade\` | `/opt/freqtrade/` |
| `C:\Users\vitamnb\.openclaw\freqtrade\user_data\` | `/opt/freqtrade/user_data/` |
| `C:\Users\vitamnb\.openclaw\openclaw.json` | `~/.openclaw/openclaw.json` |
| `C:\Users\vitamnb\.openclaw\.openclaw\cron\jobs.json` | `~/.openclaw/cron/jobs.json` |
| `C:\Users\vitamnb\.openclaw\freqtrade\tradesv3.dryrun.sqlite` | `/opt/freqtrade/tradesv3.dryrun.sqlite` |

---

_Last updated: 2026-04-20 — Roger v3.0_
