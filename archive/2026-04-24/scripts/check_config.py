import requests, json
r = requests.get('http://127.0.0.1:8080/api/v1/show_config', auth=('roger', 'RogerDryRun2026!'))
d = r.json()
print('max_open_trades:', d.get('max_open_trades'))
print('stake_amount:', d.get('stake_amount'))
print('minimal_roi:', d.get('minimal_roi'))
print('dry_run_wallet:', d.get('dry_run_wallet'))
print('state:', d.get('state'))
