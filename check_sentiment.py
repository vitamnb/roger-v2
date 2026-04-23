import json
with open(r'C:\Users\vitamnb\.openclaw\freqtrade\sentiment_data.json') as f:
    d = json.load(f)
print('Combined:', d['combined']['score'], 'confidence:', d['combined']['confidence'])
print('Sources:', d['combined']['sources_used'])
for s in d['sources']:
    print(f"  {s['source']}: {s['sentiment_score']} (conf: {s['confidence']})")
