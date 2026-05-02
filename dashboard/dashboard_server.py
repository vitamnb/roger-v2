#!/usr/bin/env python3
"""
Roger Command Center - Dashboard Server
Polls 6 freqtrade bots + market data, serves HTML dashboard
"""

import http.server
import socketserver
import threading
import json
import time
import os
from datetime import datetime
from pathlib import Path

class NumpyJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

# Add freqtrade to path
import sys
sys.path.insert(0, r"C:\Users\vitamnb\.openclaw\freqtrade")

import requests
import pandas as pd
import numpy as np
import ccxt

# Bot configs
BOTS = [
    {"name": "v3 Sniper", "port": 8083, "strategy": "RogerHybrid_v3", "desc": "Engulfing + Vol 1.5x"},
    {"name": "v2 Quality", "port": 8084, "strategy": "RogerHybrid_v2", "desc": "Engulfing + Vol 1.2x"},
    {"name": "v4 Vol2x", "port": 8085, "strategy": "RogerHybrid_v4", "desc": "Volume 2.0x"},
    {"name": "v5 Frequency", "port": 8086, "strategy": "RogerHybrid_v5", "desc": "RSI 40 entry"},
    {"name": "v6 Workhorse", "port": 8087, "strategy": "RogerHybrid_v6", "desc": "Fresh blocks (age 30)"},
    {"name": "v7 Conservative", "port": 8088, "strategy": "RogerHybrid_v7", "desc": "RR 1.5 target"},
]

API_USER = "roger"
API_PASS = "RogerDryRun2026!"

PAIRS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "ATOM/USDT",
         "ADA/USDT", "LINK/USDT", "AVAX/USDT", "BNB/USDT"]

DASHBOARD_DIR = Path(r"C:\Users\vitamnb\.openclaw\freqtrade\dashboard\static")
DATA_FILE = DASHBOARD_DIR / "data.json"

class DashboardData:
    def __init__(self):
        self.data = {
            "bots": [],
            "open_trades": [],
            "market_health": {},
            "trigger_proximity": [],
            "performance": {},
            "last_update": None
        }
        self.exchange = None
        self._init_exchange()
    
    def _init_exchange(self):
        try:
            self.exchange = ccxt.kucoin({
                'apiKey': '69eb1129b70d0a0001c8f3c2',
                'secret': '395076b9-8b19-42be-bf66-2413bd401fc0',
                'password': '2dvPGf!RY3h&xh0A4pSH',
                'enableRateLimit': True,
            })
        except Exception as e:
            print(f"Exchange init failed: {e}")
    
    def fetch_bot_data(self, bot):
        """Fetch status, balance, profit, trades from a single bot"""
        base = f"http://127.0.0.1:{bot['port']}"
        auth = (API_USER, API_PASS)
        result = {
            "name": bot["name"],
            "port": bot["port"],
            "strategy": bot["strategy"],
            "desc": bot["desc"],
            "status": "unknown",
            "running": False,
            "balance": 0,
            "equity": 0,
            "open_trades": 0,
            "total_trades": 0,
            "win_rate": 0,
            "profit_factor": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "total_profit": 0,
            "error": None
        }
        
        try:
            # Health check - returns dict with last_process timestamp
            r = requests.get(f"{base}/api/v1/health", auth=auth, timeout=5)
            if r.status_code == 200:
                health = r.json()
                # Bot is running if last_process is within 60 seconds
                import time
                last_process = health.get("last_process_ts", 0)
                if time.time() - last_process < 60:
                    result["status"] = "running"
                    result["running"] = True
        except Exception as e:
            result["error"] = str(e)
            return result
        
        try:
            # Balance
            r = requests.get(f"{base}/api/v1/balance", auth=auth, timeout=5)
            if r.status_code == 200:
                bal = r.json()
                result["balance"] = bal.get("total", 0)
                result["equity"] = bal.get("value", 0)
        except:
            pass
        
        try:
            # Profit
            r = requests.get(f"{base}/api/v1/profit", auth=auth, timeout=5)
            if r.status_code == 200:
                p = r.json()
                result["total_trades"] = p.get("trade_count", 0)
                result["win_rate"] = p.get("winrate", 0)
                result["profit_factor"] = p.get("profit_factor", 0)
                result["avg_win"] = p.get("avg_win", 0)
                result["avg_loss"] = p.get("avg_loss", 0)
                result["total_profit"] = p.get("profit_closed_coin", 0)
        except:
            pass
        
        try:
            # Open trades
            r = requests.get(f"{base}/api/v1/trades?limit=100", auth=auth, timeout=5)
            if r.status_code == 200:
                data = r.json()
                trades = data.get("trades", [])
                open_trades = [t for t in trades if t.get("is_open", False)]
                result["open_trades"] = len(open_trades)
                result["trades_detail"] = open_trades
        except:
            pass
        
        return result
    
    def fetch_market_data(self):
        """Fetch live market data for all pairs"""
        market_data = {}
        if not self.exchange:
            return market_data
        
        for pair in PAIRS:
            try:
                # Fetch OHLCV (1h)
                ohlcv = self.exchange.fetch_ohlcv(pair, timeframe='1h', limit=50)
                if ohlcv and len(ohlcv) > 20:
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    
                    # Calculate RSI
                    delta = df['close'].diff()
                    gain = delta.where(delta > 0, 0)
                    loss = -delta.where(delta < 0, 0)
                    avg_gain = gain.rolling(14).mean()
                    avg_loss = loss.rolling(14).mean()
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                    current_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
                    
                    # Volume
                    vol_avg = df['volume'].rolling(20).mean().iloc[-1]
                    current_vol = df['volume'].iloc[-1]
                    vol_ratio = current_vol / vol_avg if vol_avg > 0 else 1
                    
                    # EMA20
                    ema20 = df['close'].ewm(span=20).mean().iloc[-1]
                    price = df['close'].iloc[-1]
                    above_ema = price > ema20
                    
                    market_data[pair] = {
                        "price": price,
                        "rsi": round(current_rsi, 1),
                        "volume_ratio": round(vol_ratio, 2),
                        "above_ema20": above_ema,
                        "ema20": round(ema20, 2)
                    }
            except Exception as e:
                print(f"Error fetching {pair}: {e}")
                continue
        
        return market_data
    
    def calculate_trigger_proximity(self, market_data):
        """Calculate how close each pair is to triggering entry"""
        triggers = []
        
        for pair, data in market_data.items():
            rsi = data["rsi"]
            vol = data["volume_ratio"]
            
            # Proximity to RSI 35 (main entry threshold)
            # RSI below 35 = 100% triggered
            # RSI 35-50 = decreasing proximity
            # RSI above 50 = 0%
            if rsi <= 35:
                rsi_prox = 100
            elif rsi >= 55:
                rsi_prox = 0
            else:
                rsi_prox = max(0, (55 - rsi) / 20 * 100)
            
            # Volume proximity to 1.2x threshold
            vol_prox = min(100, vol / 1.2 * 100)
            
            # Combined (weighted: RSI 60%, volume 40%)
            combined = rsi_prox * 0.6 + vol_prox * 0.4
            
            status = "oversold" if rsi <= 35 else "warming" if rsi <= 45 else "neutral"
            
            triggers.append({
                "pair": pair,
                "price": data["price"],
                "rsi": rsi,
                "volume_ratio": vol,
                "rsi_proximity": round(rsi_prox, 1),
                "vol_proximity": round(vol_prox, 1),
                "combined": round(combined, 1),
                "status": status,
                "above_ema": data["above_ema20"]
            })
        
        # Sort by combined proximity (highest = closest to trigger)
        triggers.sort(key=lambda x: x["combined"], reverse=True)
        return triggers
    
    def calculate_market_health(self, market_data):
        """Calculate overall market health metrics"""
        if not market_data:
            return {}
        
        rsis = [d["rsi"] for d in market_data.values()]
        vols = [d["volume_ratio"] for d in market_data.values()]
        above_emas = sum(1 for d in market_data.values() if d["above_ema20"])
        
        avg_rsi = np.mean(rsis)
        avg_vol = np.mean(vols)
        pct_above_ema = above_emas / len(market_data) * 100
        
        # Oversold count (RSI 30-40) - our hunting zone
        oversold = sum(1 for r in rsis if 30 <= r <= 40)
        very_oversold = sum(1 for r in rsis if r < 30)
        
        # Market regime
        btc_data = market_data.get("BTC/USDT", {})
        btc_price = btc_data.get("price", 0)
        btc_ema = btc_data.get("ema20", 0)
        
        if btc_price > btc_ema * 1.05:
            regime = "bull"
            regime_color = "green"
        elif btc_price < btc_ema * 0.95:
            regime = "bear"
            regime_color = "red"
        else:
            regime = "neutral"
            regime_color = "yellow"
        
        # Fear/greed proxy (0 = fear, 100 = greed)
        # Low RSI = fear, high = greed
        fear_greed = min(100, max(0, (avg_rsi - 20) / 60 * 100))
        
        return {
            "avg_rsi": round(avg_rsi, 1),
            "avg_volume_ratio": round(avg_vol, 2),
            "pct_above_ema20": round(pct_above_ema, 1),
            "oversold_count": oversold,
            "very_oversold_count": very_oversold,
            "regime": regime,
            "regime_color": regime_color,
            "fear_greed": round(fear_greed, 1),
            "btc_price": btc_price,
            "btc_above_ema": btc_data.get("above_ema20", False)
        }
    
    def update(self):
        """Full data refresh cycle"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Updating dashboard data...")
        
        # Fetch all bot data
        bots = [self.fetch_bot_data(bot) for bot in BOTS]
        
        # Collect open trades
        all_open = []
        for bot in bots:
            for trade in bot.get("trades_detail", []):
                all_open.append({
                    "bot": bot["name"],
                    "pair": trade.get("pair", "?"),
                    "amount": trade.get("amount", 0),
                    "open_rate": trade.get("open_rate", 0),
                    "current_rate": trade.get("current_rate", 0),
                    "profit_pct": trade.get("profit_ratio", 0) * 100,
                    "profit_abs": trade.get("profit_abs", 0),
                    "open_date": trade.get("open_date", ""),
                    "duration": trade.get("open_date", "")
                })
        
        # Market data
        market = self.fetch_market_data()
        triggers = self.calculate_trigger_proximity(market)
        health = self.calculate_market_health(market)
        
        # Portfolio summary
        total_profit = sum(b.get("total_profit", 0) for b in bots)
        total_trades = sum(b.get("total_trades", 0) for b in bots)
        open_positions = sum(b.get("open_trades", 0) for b in bots)
        running = sum(1 for b in bots if b.get("running"))
        
        self.data = {
            "bots": bots,
            "open_trades": all_open,
            "trigger_proximity": triggers,
            "market_health": health,
            "portfolio": {
                "total_profit": round(total_profit, 2),
                "total_trades": total_trades,
                "open_positions": open_positions,
                "bots_running": running,
                "bots_total": len(BOTS)
            },
            "last_update": datetime.now().isoformat()
        }
        
        # Write to file
        with open(DATA_FILE, 'w') as f:
            json.dump(self.data, f, indent=2, cls=NumpyJSONEncoder)
        
        print(f"  Bots: {running}/{len(BOTS)} running, {open_positions} open trades")
        print(f"  Market: {health.get('regime', '?')}, avg RSI {health.get('avg_rsi', '?')}")
        print(f"  Data written to {DATA_FILE}")


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)
    
    def log_message(self, format, *args):
        # Suppress request logs
        pass
    
    def _json_response(self, data, status=200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, cls=NumpyJSONEncoder).encode())
    
    def _read_data(self):
        """Read cached dashboard data"""
        try:
            if DATA_FILE.exists():
                with open(DATA_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error reading data: {e}")
        return {}
    
    def do_GET(self):
        """Handle GET requests - serve API or static files"""
        path = self.path.split("?")[0]  # Strip query params
        
        # API endpoints
        if path == "/api/status" or path == "/api/v1/status" or path == "/api/health":
            data = self._read_data()
            self._json_response({
                "status": "ok",
                "last_update": data.get("last_update"),
                "bots_running": data.get("portfolio", {}).get("bots_running", 0),
                "bots_total": data.get("portfolio", {}).get("bots_total", 0),
                "open_positions": data.get("portfolio", {}).get("open_positions", 0),
                "total_profit": data.get("portfolio", {}).get("total_profit", 0),
            })
            return
        
        elif path == "/api/bots":
            data = self._read_data()
            bots = data.get("bots", [])
            self._json_response({
                "bots": [{k: v for k, v in b.items() if k not in ["closed_trades"]} for b in bots],
                "count": len(bots),
            })
            return
        
        elif path == "/api/trades":
            data = self._read_data()
            self._json_response({
                "open_trades": data.get("open_trades", []),
                "open_count": len(data.get("open_trades", [])),
            })
            return
        
        elif path == "/api/market":
            data = self._read_data()
            self._json_response({
                "market_health": data.get("market_health", {}),
                "trigger_proximity": data.get("trigger_proximity", [])[:5],  # Top 5
            })
            return
        
        elif path == "/api/events":
            """Serve last 50 lines of health log"""
            events = []
            log_file = Path.home() / ".openclaw" / "workspace" / "health_log.jsonl"
            if log_file.exists():
                with open(log_file, "r") as f:
                    lines = f.readlines()[-50:]
                    for line in lines:
                        line = line.strip()
                        if line:
                            try:
                                events.append(json.loads(line))
                            except:
                                pass
            self._json_response({
                "events": events,
                "count": len(events),
            })
            return
        
        # Default: serve static files
        super().do_GET()


def start_server(port=8090):
    """Start HTTP server for dashboard"""
    with socketserver.TCPServer(("", port), DashboardHandler) as httpd:
        print(f"Dashboard server running at http://localhost:{port}")
        httpd.serve_forever()


def main():
    # Ensure data file exists
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create initial data
    data = DashboardData()
    data.update()
    
    # Start background updater
    def updater():
        while True:
            time.sleep(15)  # Update every 15 seconds
            try:
                data.update()
            except Exception as e:
                print(f"Updater error: {e}")
    
    updater_thread = threading.Thread(target=updater, daemon=True)
    updater_thread.start()
    
    # Start server
    start_server(8090)


if __name__ == "__main__":
    main()
