import json, os, re, sys

def fix_inner_quotes(content):
    """Replace ASCII double quotes inside Chinese text with corner brackets."""
    # Pattern: Chinese char + " + text + " + Chinese char
    # CJK range: \u4e00-\u9fff, also include Chinese punctuation

    # Simple approach: find " surrounded by CJK context
    cjk = r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\u2000-\u206f]'

    L = '\u300c'  # 「
    R = '\u300d'  # 」

    # Handle paired quotes: 遵循"先救命后治伤"原则
    pattern1 = f'({cjk})"([^"]{{1,50}})"({cjk})'
    while re.search(pattern1, content):
        content = re.sub(pattern1, f'\\1{L}\\2{R}\\3', content)

    # Handle single quotes in Chinese context: 两个"i"
    pattern2 = f'({cjk})"([^"])"({cjk})'
    while re.search(pattern2, content):
        content = re.sub(pattern2, f'\\1{L}\\2{R}\\3', content)

    # Handle quote at end of Chinese text: ...原则"。
    pattern3 = f'({cjk})"([。，、；：！？）\\)])'
    content = re.sub(pattern3, f'\\1{R}\\2', content)

    # Handle opening quote after Chinese punctuation
    pattern4 = f'([（\\(])"({cjk})'
    content = re.sub(pattern4, f'\\1{L}\\2', content)

    return content

base = os.path.dirname(os.path.abspath(__file__))

for pf in ['ALL_questions_batch017.json', 'part2_第二篇.json', 'part3_第三篇.json', 'part4_第四篇.json']:
    path = os.path.join(base, pf)
    if not os.path.exists(path):
        continue

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Count problematic quotes
    # Find " inside Chinese text contexts
    cjk_pat = re.compile(r'[\u4e00-\u9fff]"[\u4e00-\u9fff]')
    issues = len(cjk_pat.findall(content))
    print(f'{pf}: {issues} Chinese-quote issues found')

    if issues > 0:
        fixed = fix_inner_quotes(content)

        # Verify
        try:
            data = json.loads(fixed)
            print(f'  Fixed! {len(data)} questions valid JSON')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(fixed)
        except json.JSONDecodeError as e:
            print(f'  Still broken at pos {e.pos}:')
            start = max(0, e.pos - 80)
            end = min(len(fixed), e.pos + 80)
            snippet = fixed[start:end]
            print(f'  ...{repr(snippet)}...')

            # Check remaining ASCII quotes in CJK context
            remaining = len(cjk_pat.findall(fixed))
            print(f'  Remaining issues: {remaining}')

            # Try more aggressive fix
            L = '\u300c'
            R = '\u300d'
            fixed2 = re.sub(r'([\u4e00-\u9fff])"', f'\\1{L}', fixed)
            fixed2 = re.sub(r'"([\u3000-\u303f\uff00-\uffef\u2000-\u206f])', f'{R}\\1', fixed2)
            fixed2 = re.sub(r'"([\u4e00-\u9fff])', f'{L}\\1', fixed2)
            try:
                data = json.loads(fixed2)
                print(f'  Aggressive fix succeeded! {len(data)} questions')
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(fixed2)
            except json.JSONDecodeError as e2:
                print(f'  Still broken: {e2}')
                # Show context
                p = e2.pos
                print(f'  Context: {repr(fixed2[max(0,p-40):p+40])}')
    else:
        try:
            data = json.loads(content)
            print(f'  Already valid ({len(data)} questions)')
        except:
            print(f'  Invalid but no obvious CJK quote issues')

    print('---')
