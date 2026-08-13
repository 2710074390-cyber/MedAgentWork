import json, re

path = r'C:\Users\38063\Desktop\MedAgentWork\中间产物\batch017\part4_第四篇.json'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

L = '\u300c'  # 「
R = '\u300d'  # 」

# Fix inner opening quote at very start of string value
content = content.replace('"explanation": ""', '"explanation": "' + L)
content = content.replace('"question_text": ""', '"question_text": "' + L)

# Fix: CJK+"+CJK → CJK+」+CJK (closing inner quote)
pattern_close = re.compile(r'([\u4e00-\u9fff])"([\u4e00-\u9fff\u3000-\u303f])')
while pattern_close.search(content):
    content = pattern_close.sub(r'\1' + R + r'\2', content)

# Fix remaining CJK+"+text"+CJK paired quotes
pattern_paired = re.compile(r'([\u4e00-\u9fff])"([^"]{0,30})"([\u4e00-\u9fff])')
while pattern_paired.search(content):
    content = pattern_paired.sub(r'\1' + L + r'\2' + R + r'\3', content)

try:
    data = json.loads(content)
    print(f'Part 4 fixed: {len(data)} questions valid')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
except json.JSONDecodeError as e:
    print(f'Still broken at char {e.pos}: {e}')
    s = max(0, e.pos-50)
    e2 = min(len(content), e.pos+50)
    print(f'Context: {repr(content[s:e2])}')

    # Show line number
    line_num = content[:e.pos].count('\n') + 1
    lines = content.split('\n')
    if line_num <= len(lines):
        print(f'Line {line_num}: {lines[line_num-1][:150]}')
