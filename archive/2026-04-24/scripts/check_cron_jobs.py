import json
with open(r'C:\Users\vitamnb\.openclaw\cron\jobs.json') as f:
    jobs = json.load(f)
print('Type:', type(jobs))
if isinstance(jobs, list):
    print('Jobs list length:', len(jobs))
    for i, j in enumerate(jobs):
        print(f"Job {i}: type={type(j)}, keys={list(j.keys()) if isinstance(j, dict) else 'N/A'}")
        if isinstance(j, dict):
            print(f"  name/id: {j.get('name', j.get('id', '?'))}")
            if isinstance(j.get('payload'), dict):
                print(f"  payload text: {j['payload'].get('text', '')[:60]}")
        if i >= 2:
            break
elif isinstance(jobs, dict):
    print('Jobs dict keys:', list(jobs.keys())[:10])
