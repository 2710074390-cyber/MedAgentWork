import json, os, sys

def fix_json_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    try:
        data = json.loads(content)
        print(f'{filepath}: Valid ({len(data)} questions)')
        return data
    except json.JSONDecodeError as e:
        print(f'{filepath}: Invalid - {e}')

    # Count and replace curly double quotes
    left_count = content.count('\u201c')
    right_count = content.count('\u201d')
    print(f'  Curly quotes: LEFT={left_count}, RIGHT={right_count}')

    content = content.replace('\u201c', '\u300c')
    content = content.replace('\u201d', '\u300d')

    try:
        data = json.loads(content)
        print(f'  Fixed! ({len(data)} questions)')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return data
    except json.JSONDecodeError as e:
        print(f'  Still broken: {e}')

        # More aggressive fix: the error might be regular ASCII quotes inside strings
        # Let's find the exact position
        pos = e.pos
        start = max(0, pos - 100)
        end = min(len(content), pos + 50)
        print(f'  Context around pos {pos}: ...{repr(content[start:end])}...')
        return None

base = os.path.dirname(os.path.abspath(__file__))

for pf in ['ALL_questions_batch017.json', 'part2_第二篇.json', 'part3_第三篇.json', 'part4_第四篇.json']:
    path = os.path.join(base, pf)
    if os.path.exists(path):
        fix_json_file(path)
        print('---')
