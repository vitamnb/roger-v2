# Fix ALL non-ASCII in audit_layer1.py
import re

path = r'C:\Users\vitamnb\.openclaw\freqtrade\audit_layer1.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace ALL non-ASCII chars with simple ASCII equivalents
replacements = {
    '\u23f0': '[CLOCK]',
    '\U0001f50d': '[AUDIT]',
    '\U0001f4c8': '[UP]',
    '\U0001f4c9': '[DOWN]',
    '\u2705': '[OK]',
    '\u274c': '[FAIL]',
    '\u26a0': '[WARN]',
    '\U0001f534': '[ALERT]',
    '\U0001f50a': '[LOUD]',
    '\U0001f4ca': '[CHART]',
    '\u2b50': '[STAR]',
    '\u2757': '[!]',
    '\u2753': '[?]',
}

old = content
for char, rep in replacements.items():
    content = content.replace(char, rep)

# Catch any remaining non-ASCII
content = re.sub(r'[^\x00-\x7f]', '[X]', content)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print(f'Fixed {len(old)-len(content)} chars')
