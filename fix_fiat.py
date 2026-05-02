import json
import os

configs = [
    "user_data/config_Roger_v3_Sniper.json",
    "user_data/config_Roger_v2_Quality.json",
    "user_data/config_Roger_v4_Vol2x.json",
    "user_data/config_Roger_v5_Frequency.json",
    "user_data/config_Roger_v6_Workhorse.json",
    "user_data/config_Roger_v7_Conservative.json"
]

base = r"C:\Users\vitamnb\.openclaw\freqtrade"

for cfg in configs:
    path = os.path.join(base, cfg)
    with open(path) as f:
        data = json.load(f)
    data["fiat_display_currency"] = ""  # Disable fiat conversion
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    print("Fixed: " + cfg)

print("\nAll configs updated. Restart bots for changes to take effect.")
