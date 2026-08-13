#!/usr/bin/env python3
"""
跨工作区 CONTEXT.md 工具路径表同步脚本
将所有工作区的工具路径表统一为 MedAgentWork 的基准版本。
"""
import re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(r'C:\Users\38063\Desktop')

# 基准来源
SOURCE = BASE / 'MedAgentWork' / 'CONTEXT.md'

# 目标工作区
TARGETS = ['Web-AI', 'web-med', 'agent-ppt', '黑曜石', '测试']

# 工具路径段可能使用的标题（不同工作区用了不同措辞）
SECTION_HEADERS = [
    '## 工具路径',
    '## 工具基础',
    '## 工具环境',
    '## 工具基础 / 路径',
    '## 工具基础/路径',
]

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'  ✅ 已写入 {path.name}')

def extract_baseline_section():
    """从 MedAgentWork 提取完整工具路径段"""
    content = read_file(SOURCE)
    start = content.find('## 工具路径')
    if start == -1:
        raise RuntimeError('MedAgentWork CONTEXT.md 缺少 ## 工具路径 段落')

    # 找到下一个 ## 级标题作为结束标记
    rest = content[start+1:]
    next_h2 = re.search(r'\n## ', rest)
    if next_h2:
        end = start + 1 + next_h2.start()
    else:
        end = len(content)

    return content[start:end].rstrip()

def find_section_bounds(content):
    """在给定内容中找到工具路径段落的起止位置"""
    for header in SECTION_HEADERS:
        pos = content.find(header)
        if pos != -1:
            # 找到下一个 ## 级标题
            rest = content[pos+1:]
            next_h2 = re.search(r'\n## ', rest)
            if next_h2:
                end = pos + 1 + next_h2.start()
            else:
                end = len(content)
            return pos, end, header
    return None, None, None

def find_insert_point(content):
    """找不到工具路径段时，找到应该插入的位置"""
    # 在第一个 ## 工具相关的标题之后插入
    # 或者在中国工程师约束段之后
    markers = [
        '## 工具选型层级',
        '### 工具选型层级',
        '## 中国工程师约束',
        '## 网络环境约束',
    ]
    for marker in markers:
        pos = content.find(marker)
        if pos != -1:
            # 找到这个section的结束（下一个 ##）
            rest = content[pos+1:]
            next_h2 = re.search(r'\n## ', rest)
            if next_h2:
                return pos + 1 + next_h2.start()
    return None

def sync_workspace(ws_name):
    """同步单个工作区"""
    ws_file = BASE / ws_name / 'CONTEXT.md'
    if not ws_file.exists():
        print(f'  ⚠️ {ws_name}/CONTEXT.md 不存在，跳过')
        return 'skip'

    content = read_file(ws_file)
    baseline = extract_baseline_section()

    start, end, header = find_section_bounds(content)

    if start is not None:
        # 替换已有段落
        old_section = content[start:end]
        new_content = content[:start] + baseline + content[end:]
        write_file(ws_file, new_content)
        return 'replaced'
    else:
        # 找不到段落，尝试插入
        insert_at = find_insert_point(content)
        if insert_at is not None:
            new_content = content[:insert_at] + '\n' + baseline + '\n' + content[insert_at:]
            write_file(ws_file, new_content)
            return 'inserted'
        else:
            # 追加到文件末尾
            new_content = content.rstrip() + '\n\n' + baseline + '\n'
            write_file(ws_file, new_content)
            return 'appended'

# ─── 执行 ───────────────────────────────────────

print(f'\n基准: {SOURCE.name}')
print(f'工具路径段: {len(extract_baseline_section())} 字符\n')

results = {}
for ws in TARGETS:
    print(f'[{ws}]', end=' ')
    result = sync_workspace(ws)
    results[ws] = result

print(f'\n{"─"*50}')
print('同步结果:')
for ws, result in results.items():
    icon = {'replaced': '🔧', 'inserted': '📥', 'appended': '📎', 'skip': '⚠️'}.get(result, '❓')
    print(f'  {icon} {ws}: {result}')
