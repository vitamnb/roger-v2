import json
with open(r'C:\Users\vitamnb\.openclaw\openclaw.json') as f:
    d = json.load(f)
print('=== Crons ===')
for c in d.get('crons', []):
    print(f"{c.get('id','?')} | {c.get('name','unnamed')} | {c.get('schedule',{})}")
print('\n=== Reminders ===')
for r in d.get('reminders', []):
    print(f"{r.get('id','?')} | {r.get('text','')[:50]}")
