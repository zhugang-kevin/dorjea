import re
with open('self_defence/injection_detector.py', encoding='utf-8') as f:
    lines = f.readlines()
lines[80] = "    cleaned = re.sub(r'[<>]', '', text)
"
with open('self_defence/injection_detector.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('fixed')
