with open(r'C:\Users\vitamnb\.openclaw\freqtrade\scanner.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '    parser.add_argument("--risk", type=float, default=DEFAULT_RISK_PCT)'
new = old + '\n    parser.add_argument("--rr", type=float, default=DEFAULT_RR)'

if old in content:
    content = content.replace(old, new)
    print('Added --rr argument')
else:
    print('Not found - checking what we have')
    idx = content.find('parser.add_argument("--risk"')
    print(repr(content[idx:idx+80]))

with open(r'C:\Users\vitamnb\.openclaw\freqtrade\scanner.py', 'w', encoding='utf-8') as f:
    f.write(content)
