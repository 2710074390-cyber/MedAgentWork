import os

base = r'C:\Users\38063\Desktop\MedAgentWork\Prompt版本'
out_dir = os.path.join(base, 'clean')
os.makedirs(out_dir, exist_ok=True)

agents = ['MedMaster', 'MedGen', 'MedQC', 'MedFix']
for agent in agents:
    src = os.path.join(base, f'{agent}_current_prompt.md')
    with open(src, 'r', encoding='utf-8') as f:
        content = f.read()

    # Opening marker
    start_marker = '```markdown\n'
    start_idx = content.find(start_marker)
    if start_idx == -1:
        print(f'{agent}: FAILED - no opening ```markdown')
        continue

    content_start = start_idx + len(start_marker)

    # Find </START> and work backwards to find closing ```
    end_marker = '</START>'
    end_marker_idx = content.rfind(end_marker)
    if end_marker_idx == -1:
        print(f'{agent}: FAILED - no </START>')
        continue

    # Find the last ``` before </START>
    tail = content[content_start:end_marker_idx]
    # Find ``` that is alone on a line near the end
    last_backtick = tail.rfind('\n```')
    if last_backtick != -1:
        clean = tail[:last_backtick]
    else:
        clean = tail

    dst = os.path.join(out_dir, f'{agent}_prompt.md')
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(clean)

    lines = clean.count('\n') + 1
    print(f'{agent}: {lines} lines, {len(clean)} chars')

print('Done')
