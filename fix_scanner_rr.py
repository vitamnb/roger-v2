content = open(r'C:\Users\vitamnb\.openclaw\freqtrade\scanner.py', 'r', encoding='utf-8').read()

# Fix: add DEFAULT_RR on its own line (split the merged line)
content = content.replace('DEFAULT_RISK_PCT = 2.0\nDEFAULT_RR = 3.5', 'DEFAULT_RISK_PCT = 2.0\nDEFAULT_RR = 3.5')

# Fix: add rr param to calc_levels signature
content = content.replace(
    'def calc_levels(df, entry_price, regime_info,\n    risk_pct=DEFAULT_RISK_PCT):',
    'def calc_levels(df, entry_price, regime_info,\n    risk_pct=DEFAULT_RISK_PCT, rr=DEFAULT_RR):'
)

# Fix: replace t = regime_info thresholds with hardcoded dict
content = content.replace('t = regime_info["thresholds"]', 't = {"stop_mult": 1.5, "tp_mult": rr}')

# Fix: add --rr argument after --risk
old = ('    parser.add_argument("--risk", type=float,\n'
       '                        default=DEFAULT_RISK_PCT)')
new = old + '\n    parser.add_argument("--rr", type=float, default=DEFAULT_RR)'
content = content.replace(old, new)

# Fix: call with args.rr
content = content.replace(
    'levels = calc_levels(df, entry, regime_info, args.risk)',
    'levels = calc_levels(df, entry, regime_info, args.risk, args.rr)'
)

open(r'C:\Users\vitamnb\.openclaw\freqtrade\scanner.py', 'w', encoding='utf-8').write(content)
print('Done - scanner.py updated')
