with open('C:/Users/vitamnb/.openclaw/freqtrade/scanner.py', 'rb') as f:
    content = f.read()

old_row = (
    b'vol_s = str(s["vol_ratio"]) + "x"\r\n'
    b'        print(f"  {s[\'symbol\']:<12} {s[\'regime\']:<14} {s[\'direction\']:<6} {s[\'score\']:>6}  "\r\n'
    b'              f"{s[\'entry\']:>12.6f}  {sup:>12} {res:>12}  "\r\n'
    b'              f"{vol_s:>5} {s[\'confirmations\'][:25]}")'
)

new_row = (
    b'vol_s = str(s["vol_ratio"]) + "x"\r\n'
    b'        whale_s = str(s.get(\'whale_score\', 50)) + "/100"\r\n'
    b'        boost_delta = round(s.get(\'boosted_score\', s[\'score\']) - s[\'score\'], 1)\r\n'
    b'        boost_s = ("+" + str(boost_delta)) if boost_delta > 0 else "-"\r\n'
    b'        print(f"  {s[\'symbol\']:<12} {s[\'regime\']:<14} {s[\'direction\']:<6} {s[\'score\']:>6} {boost_s:>7} {whale_s:>6}  "\r\n'
    b'              f"{s[\'entry\']:>12.6f}  {sup:>12} {res:>12}  "\r\n'
    b'              f"{vol_s:>5} {s[\'confirmations\'][:25]}")'
)

if old_row in content:
    content = content.replace(old_row, new_row, 1)
    print('Replaced row')
else:
    print('Row not found')

with open('C:/Users/vitamnb/.openclaw/freqtrade/scanner.py', 'wb') as f:
    f.write(content)
print('Done')
