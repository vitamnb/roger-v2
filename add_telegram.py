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
        "buy": "on",
        "sell": "on",
        "buy_fill": "on",
        "sell_fill": "on",
        "buy_cancel": "off",
        "sell_cancel": "off",
        "warning": "on",
        "startup": "off",
        "entry": "on",
        "entry_fill": "on",
        "entry_cancel": "off",
        "exit": "on",
        "exit_fill": "on",
        "exit_cancel": "off",
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
    
    config["telegram"] = telegram_config
    
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"Added Telegram alerts to {bot}")

print("\nAll configs updated!")
print("Next: Restart bots for changes to take effect.")
