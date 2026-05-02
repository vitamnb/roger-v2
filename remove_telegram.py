import json

bots = [
    "Roger_v3_Sniper", "Roger_v2_Quality", "Roger_v4_Vol2x",
    "Roger_v5_Frequency", "Roger_v6_Workhorse", "Roger_v7_Conservative"
]

for bot in bots:
    path = f"C:/Users/vitamnb/.openclaw/freqtrade/user_data/config_{bot}.json"
    with open(path) as f:
        config = json.load(f)
    
    # Remove telegram to avoid conflict with OpenClaw's bot
    if "telegram" in config:
        del config["telegram"]
    
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"Removed Telegram from {bot}")

print("\nAll configs cleaned.")
print("Will set up trade watcher via OpenClaw cron instead.")
