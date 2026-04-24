with open('C:/Users/vitamnb/.openclaw/freqtrade/scanner.py', 'rb') as f:
    content = f.read()

target = b'vol_s = str(s["vol_ratio"]) + "x"\r\n        print(f"  {s[\'symbol\']:<12} {s[\'regime\']:<14} {s[\'direction\']:<6} {s[\'score\']:>6}  "'
if target in content:
    print('Found row pattern!')
    idx = content.find(b'vol_s = str')
    print(repr(content[idx:idx+250]))
else:
    print('Not found')
    idx = content.find(b'vol_s =')
    print(repr(content[idx:idx+200]))
