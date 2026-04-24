import requests, time

for model in ['gemma4:e4b', 'kimi-k2.6:cloud']:
    start = time.time()
    try:
        r = requests.post('http://localhost:11434/api/generate', 
            json={'model':model,'prompt':'Say OK in 3 words','stream':False,'options':{'num_predict':10}},
            timeout=30)
        elapsed = time.time()-start
        resp = r.json().get('response','')
        print(f'{model}: HTTP {r.status_code} | {elapsed:.1f}s | "{resp[:30]}"')
    except Exception as e:
        print(f'{model}: ERROR after {time.time()-start:.1f}s: {e}')
