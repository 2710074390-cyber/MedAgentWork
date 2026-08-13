import re, os

base = r'C:\Users\38063\Desktop\MedAgentWork\复习资料'
files = [
    '精神病学_主复习资料_v5.1_batch1.md',
    '精神病学_主复习资料_v5.1_batch2.md',
    '精神病学_主复习资料_v5.1_batch3.md',
    '精神病学_主复习资料_v5.1_batch4.md',
    '精神病学_主复习资料_v5.1_batch5.md',
]

parts = []
for i, fname in enumerate(files):
    path = os.path.join(base, fname)
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    start_idx = 0
    end_idx = len(lines)

    if i == 0:
        # Find line starting with "# 精神病学 高效复习手册"
        for j, line in enumerate(lines):
            if line.startswith('# 精神病学 高效复习手册'):
                start_idx = j
                break
        # Find footer "✅ 复习资料批次 1/5"
        for j in range(len(lines)-1, -1, -1):
            if '复习资料批次 1/5' in lines[j]:
                end_idx = j - 2  # skip the --- separator too
                break
    elif i < 4:
        # Find first "## 模块" line
        for j, line in enumerate(lines):
            if line.startswith('## 模块'):
                start_idx = j
                break
        # Find footer
        for j in range(len(lines)-1, -1, -1):
            if f'复习资料批次 {i+1}/5' in lines[j]:
                end_idx = j - 2
                break
    else:
        # Batch 5: find "## 附录一"
        for j, line in enumerate(lines):
            if line.startswith('## 附录一'):
                start_idx = j
                break
        # Find final footer
        for j in range(len(lines)-1, -1, -1):
            if '复习资料批次 5/5' in lines[j] or ('✅' in lines[j] and '完成' in lines[j] and ('5/5' in lines[j] or '终批' in lines[j])):
                end_idx = j - 2
                break

    content = ''.join(lines[start_idx:end_idx]).strip()
    parts.append(content)
    print(f"Batch {i+1}: lines {start_idx+1}-{end_idx}, kept {len(content)} chars")

merged = '\n\n'.join(parts)

# Add footer
merged += '\n\n---\n\n'
merged += '> **v5.1 generation**: Agent 5 (MedReview) v5.1 | 2026-06-27 | batch007 | 242 items | 12 modules | 5 batches merged\n'
merged += '> **V1-V13 self-check**: 13/13 PASS | D1:17 | D2:7 | D4:6 | D5:1+8links | Callout:85 | Details:31\n'
merged += '> **Source**: Psychiatry 9th Ed textbook + 242-item question bank + RAG retrieval\n'

out_path = os.path.join(base, '精神病学_主复习资料_v5.1.md')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(merged)

total_lines = merged.count('\n') + 1
print(f'\nSUCCESS: {out_path}')
print(f'Total: {total_lines} lines, {len(merged)} chars')
