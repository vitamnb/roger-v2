import json

bots = [
    "Roger_v3_Sniper", "Roger_v2_Quality", "Roger_v4_Vol2x",
    "Roger_v5_Frequency", "Roger_v6_Workhorse", "Roger_v7_Conservative"
]

TELEGRAM_TOKEN = "8755560208:AAFwdeFgfn4arxDV_eBnZZSA6UVuI5fhjcU"
TELEGRAM_CHAT_ID = "404572949"

telegram_config = {
    "enabled": True,
    "token": TELEGRAM_TOKEN,
    "chat_id": TELEGRAM_CHAT_ID,
    "notification_settings": {
        "roi": "off",
        "entry": "on",
        "entry_fill": "on",
        "entry_cancel": "off",
        "exit": "on",
        "exit_fill": "on",
        "exit_cancel": "off",
        "warning": "on",
        "startup": "off",
        "protection_trigger": "on",
        "protection_trigger_global": "on",
        "show_candle": "off",
        "strategy_msg": "off",
        "forcebuy": "on",
        "forcesell": "on"
    },
    "reload": True
}

for bot in bots:
    path = f"C:/Users/vitamnb/.openclaw/freqtrade/user_data/config_{bot}.json"
    with open(path) as f:
        config = json.load(f)
    
    # Remove old deprecated keys if present
    old_tg = config.get("telegram", {})
    if old_tg:
        old_tg.pop("buy", None)
        old_tg.pop("sell", None)
        old_tg.pop("buy_fill", None)
        old_tg.pop("sell_fill", None)
        old_tg.pop("buy_cancel", None)
        old_tg.pop("sell_cancel", None)
    
    config["telegram"] = telegram_config
    
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"Fixed Telegram config for {bot}")

print("\nAll configs fixed! Removing deprecated buy/sell keys.")
