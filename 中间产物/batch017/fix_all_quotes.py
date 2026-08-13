import json, re, os

def fix_all_inner_quotes(filepath):
    """Replace ALL ASCII double quotes that appear inside JSON string values with corner brackets."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Strategy: process line by line, fixing quotes within string values
    lines = content.split('\n')
    fixed_lines = []

    for line in lines:
        # If this line contains a JSON string value with extra quotes
        # We need to identify: the key (like "explanation": ), then the value string

        # Pattern: key + ": " + "value"
        # We need to protect the outer quotes while replacing inner ones

        # Simpler: find patterns where a quote is preceded/followed by Chinese text
        # This won't match JSON delimiter quotes because they're surrounded by :  , whitespace [] {} etc

        # Match patterns like: 两个"i"  or  氟烷-肾上腺素心律失常"
        # The context around the inner quote is NOT JSON syntax characters

        # Find all quotes that are between CJK characters (with possible ASCII in between)
        # Pattern: CJK_or_punct + " + (any 1-20 chars) + " + CJK_or_punct
        cjk_wide = r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\u2000-\u206f\u2018-\u201f\u2100-\u214f]'

        # Paired inner quotes: 中文"text"中文
        pattern = f'({cjk_wide})"([^"]{{0,30}})"({cjk_wide})'
        while re.search(pattern, line):
            line = re.sub(pattern, f'\\1\u300c\\2\u300d\\3', line)

        # Single inner quote preceded by CJK (opening): 中文"text
        pattern2 = f'({cjk_wide})"([{cjk_wide}])'
        while re.search(pattern2, line):
            line = re.sub(pattern2, f'\\1\u300c\\2', line)

        # Quote at end of Chinese context: text"中文
        pattern3 = f'([{cjk_wide}])"({cjk_wide})'
        while re.search(pattern3, line):
            line = re.sub(pattern3, f'\\1\u300d\\2', line)

        fixed_lines.append(line)

    fixed = '\n'.join(fixed_lines)

    try:
        data = json.loads(fixed)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fixed)
        return len(data)
    except json.JSONDecodeError as e:
        print(f'  Still broken at line {fixed[:e.pos].count(chr(10))+1}: {e}')
        # Show context
        line_num = fixed[:e.pos].count('\n')
        if line_num < len(fixed_lines):
            print(f'  Line: {fixed_lines[line_num][:120]}')
        return None

base = r'C:\Users\38063\Desktop\MedAgentWork\中间产物\batch017'
for pf in ['part2_第二篇.json', 'part4_第四篇.json']:
    path = os.path.join(base, pf)
    if os.path.exists(path):
        print(f'Fixing {pf}...')
        result = fix_all_inner_quotes(path)
        if result:
            print(f'  Success: {result} questions')
        print('---')
