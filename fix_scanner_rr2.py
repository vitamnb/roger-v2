content = open(r'C:\Users\vitamnb\.openclaw\freqtrade\scanner.py', 'r', encoding='utf-8').read()

# Fix the def calc_levels line - add rr parameter
content = content.replace(
    'def calc_levels(df, entry_price, regime_info,\n    risk_pct=DEFAULT_RISK_PCT):',
    'def calc_levels(df, entry_price, regime_info,\n    risk_pct=DEFAULT_RISK_PCT, rr=DEFAULT_RR):'
)

open(r'C:\Users\vitamnb\.openclaw\freqtrade\scanner.py', 'w', encoding='utf-8').write(content)
print('Done')
