#!/usr/bin/env python3
"""
Generate config.json from environment variables.
Run this after updating .env in the workspace.
"""
import json
import os
from pathlib import Path

def load_env():
    """Load .env from workspace."""
    env_path = Path.home() / '.openclaw' / 'workspace' / '.env'
    if not env_path.exists():
        raise FileNotFoundError(f"No .env found at {env_path}")
    
    env = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            key, val = line.split('=', 1)
            env[key] = val
    return env

def generate_config():
    env = load_env()
    
    config = {
        "max_open_trades": 1,
        "stake_currency": "USDT",
        "stake_amount": 50.0,
        "tradable_balance_ratio": 0.90,
        "fiat_display_currency": "USD",
        "dry_run": True,
        "dry_run_wallet": 58,
        "minimal_roi": {"0": 0.07},
        "cancel_open_orders_on_exit": False,
        "unfilledtimeout": {
            "entry": 10,
            "exit": 10,
            "exit_timeout_count": 0,
            "unit": "minutes"
        },
        "entry_pricing": {
            "price_side": "same",
            "use_order_book": True,
            "order_book_top": 1,
            "price_last_balance": 0.0,
            "check_depth_of_market": {
                "enabled": False,
                "bids_to_ask_delta": 1
            }
        },
        "exit_pricing": {
            "price_side": "same",
            "use_order_book": True,
            "order_book_top": 1
        },
        "exchange": {
            "name": "kucoin",
            "key": env.get("KUCOIN_API_KEY", ""),
            "secret": env.get("KUCOIN_API_SECRET", ""),
            "password": env.get("KUCOIN_API_PASSPHRASE", ""),
            "ccxt_config": {"fetchMarkets": "fetch_markets"},
            "ccxt_async_config": {"fetchCurrencies": False}
        },
        "pair_whitelist": [],
        "pair_blacklist": [],
        "telegram": {
            "enabled": False,
            "token": "",
            "chat_id": ""
        },
        "api_server": {
            "enabled": True,
            "listen_ip_address": "127.0.0.1",
            "listen_port": 8080,
            "verbosity": "error",
            "enable_openapi": True,
            "jwt_secret_key": env.get("JWT_SECRET_KEY", "change_me"),
            "CORS_origins": [],
            "username": env.get("WEBUI_USERNAME", "roger"),
            "password": env.get("WEBUI_PASSWORD", "change_me")
        },
        "bot_name": "Roger_v2",
        "force_entry_enable": True,
        "initial_state": "running"
    }
    
    config_path = Path.home() / '.openclaw' / 'freqtrade' / 'user_data' / 'config.json'
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Config written to: {config_path}")
    print("Note: pair_whitelist is empty. Populate it before running.")

if __name__ == '__main__':
    generate_config()
