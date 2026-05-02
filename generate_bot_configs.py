import json
import os

base_config_path = "C:/Users/vitamnb/.openclaw/freqtrade/user_data/config_paper.json"
with open(base_config_path) as f:
    base = json.load(f)

bots = [
    {"name": "Roger_v3_Sniper", "strategy": "RogerHybrid_v3", "port": 8083},
    {"name": "Roger_v2_Quality", "strategy": "RogerHybrid_v2", "port": 8084},
    {"name": "Roger_v4_Vol2x", "strategy": "RogerHybrid_v4", "port": 8085},
    {"name": "Roger_v5_Frequency", "strategy": "RogerHybrid_v5", "port": 8086},
    {"name": "Roger_v6_Workhorse", "strategy": "RogerHybrid_v6", "port": 8087},
    {"name": "Roger_v7_Conservative", "strategy": "RogerHybrid_v7", "port": 8088},
]

for bot in bots:
    config = json.loads(json.dumps(base))  # Deep copy
    config["api_server"]["listen_port"] = bot["port"]
    config["bot_name"] = bot["name"]
    
    out_path = f"C:/Users/vitamnb/.openclaw/freqtrade/user_data/config_{bot['name']}.json"
    with open(out_path, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"Generated {out_path}")

print("\nAll configs generated!")
