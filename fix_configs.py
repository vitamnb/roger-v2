import json

bots = [
    "Roger_v3_Sniper", "Roger_v2_Quality", "Roger_v4_Vol2x",
    "Roger_v5_Frequency", "Roger_v6_Workhorse", "Roger_v7_Conservative"
]

whitelist = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT",
    "XRP/USDT", "ATOM/USDT", "ADA/USDT",
    "LINK/USDT", "AVAX/USDT", "BNB/USDT"
]

for bot in bots:
    path = f"C:/Users/vitamnb/.openclaw/freqtrade/user_data/config_{bot}.json"
    with open(path) as f:
        config = json.load(f)
    
    # freqtrade 2026.3 needs BOTH:
    # 1. pairlists with StaticPairList
    # 2. pair_whitelist inside exchange block
    exchange = config.get("exchange", {})
    exchange["pair_whitelist"] = whitelist
    config["exchange"] = exchange
    
    # Add pairlists
    config["pairlists"] = [
        {"method": "StaticPairList"}
    ]
    
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"Fixed {bot} — exchange.pair_whitelist + pairlists both set")

print("\nAll configs fixed!")
