import json
with open(r"C:\Users\vitamnb\.openclaw\freqtrade\user_data\config.json") as f:
    c = json.load(f)
print(json.dumps(c.get("stoploss", "NOT SET"), indent=2))
print(json.dumps(c.get("trailing", {}), indent=2))
print("exitReasons:", c.get("exit_reason_trade", "NOT SET"))
