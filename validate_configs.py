import json, sys

bots = [
    "Roger_v3_Sniper", "Roger_v2_Quality", "Roger_v4_Vol2x",
    "Roger_v5_Frequency", "Roger_v6_Workhorse", "Roger_v7_Conservative"
]

all_ok = True
for bot in bots:
    path = f"C:/Users/vitamnb/.openclaw/freqtrade/user_data/config_{bot}.json"
    try:
        with open(path) as f:
            config = json.load(f)
        
        # Check required fields
        checks = {
            "pairlists": "pairlists" in config,
            "StaticPairList": any(pl.get("method") == "StaticPairList" for pl in config.get("pairlists", [])),
            "pair_whitelist_in_pairlist": any("pair_whitelist" in pl for pl in config.get("pairlists", [])),
            "api_server": "api_server" in config,
            "port": config.get("api_server", {}).get("listen_port", 0) != 8080,
            "dry_run": config.get("dry_run", False) == True,
        }
        
        failed = [k for k, v in checks.items() if not v]
        if failed:
            print(f"FAIL {bot}: missing {failed}")
            all_ok = False
        else:
            print(f"OK {bot}: port={config['api_server']['listen_port']}, pairs={len([pl for pl in config['pairlists'] if pl.get('method') == 'StaticPairList'][0].get('pair_whitelist', []))}")
    except Exception as e:
        print(f"ERROR {bot}: {e}")
        all_ok = False

if all_ok:
    print("\nAll configs valid!")
    sys.exit(0)
else:
    print("\nSome configs have issues!")
    sys.exit(1)
