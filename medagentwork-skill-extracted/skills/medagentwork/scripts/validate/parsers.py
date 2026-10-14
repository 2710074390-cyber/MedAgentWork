"""
parsers.py — JSON 和 Markdown 解析器
从 validate_options.py 拆分而来
"""
import json
import re
from pathlib import Path


def parse_json_file(filepath):
    """解析 JSON 格式的题库文件，返回题目列表
    支持两种格式:
      - batch004 风格: {"question": "...", "options": ["A. text", ...]}
      - batch006 风格: {"stem": "...", "options": [{"label": "A", "text": "..."}]}
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list):
        return []

    questions = []
    for item in data:
        if not isinstance(item, dict):
            continue
        stem = item.get('question') or item.get('stem') or item.get('question_text') or item.get('题干', '')
        if not stem:
            continue
        q = {
            'id': item.get('question_id', item.get('id', '?')),
            'type': item.get('type') or item.get('question_type', 'A1'),
            'question': stem,
            'options_raw': item.get('options', []),
            'answer': item.get('answer') or item.get('correct_answer', ''),
            'analysis': item.get('analysis', '') or item.get('explanation', '') or item.get('解析', ''),
            'module': item.get('module', ''),
            'bloom': item.get('bloom') or item.get('bloom_level', ''),
            'difficulty': item.get('difficulty', ''),
        }
        opts = {}
        raw = q['options_raw']
        if isinstance(raw, dict):
            # 契约格式: {A: text, B: text, ...}
            for label, text in raw.items():
                if str(label).strip() and str(text).strip():
                    opts[str(label).strip()] = str(text).strip()
            q['options'] = opts
            questions.append(q)
            continue
        for opt in raw:
            if isinstance(opt, dict):
                label = opt.get('label', '')
                text = opt.get('text', '')
                if label and text:
                    opts[label] = text.strip()
            elif isinstance(opt, str):
                m = re.match(r'^([A-E])\.\s*(.+)', opt)
                if m:
                    opts[m.group(1)] = m.group(2).strip()
                else:
                    opts[str(len(opts))] = opt.strip()
        q['options'] = opts
        questions.append(q)
    return questions


def parse_md_file(filepath):
    """解析 Markdown 格式的题库文件，返回题目列表"""
    if isinstance(filepath, str):
        filepath = Path(filepath)
    text = filepath.read_text(encoding='utf-8')
    lines = text.split('\n')

    questions = []
    b1_groups = {}
    current_b1_group = None

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        header_match = re.match(r'\*\*(N\d+-\d+)\*?\s*\[(\w+)型\](?:\s*\[([正反]?选)\])?', line)
        if not header_match:
            i += 1
            continue

        qid = header_match.group(1)
        qtype = header_match.group(2)
        polarity = header_match.group(3) or '正选'

        if qtype != 'B1':
            current_b1_group = None

        q = {
            'id': qid,
            'type': qtype,
            'polarity': polarity,
            'question': '',
            'options': {},
            'answer': '',
            'analysis': '',
            'module': '',
            'b1_group': None,
            'b1_shared_options': None,
        }

        i += 1

        if qtype == 'B1' and i < len(lines):
            shared_match = re.match(r'[（(](\d+)-(\d+)共用选项[）)]', lines[i].strip())
            if shared_match:
                group_start = shared_match.group(1)
                group_end = shared_match.group(2)
                q['b1_group'] = f"{group_start}-{group_end}"
                current_b1_group = q['b1_group']
                i += 1
                if i < len(lines):
                    shared_line = lines[i].strip()
                    shared_opts = {}
                    for opt_m in re.finditer(r'([A-E])\.\s*(\S+(?:\s+\S+)*?)(?=\s+[A-E]\.|$)', shared_line):
                        shared_opts[opt_m.group(1)] = opt_m.group(2).strip()
                    if not shared_opts:
                        for opt_m in re.finditer(r'([A-E])\.\s*(.+?)(?=\s+-\s+[A-E]\.|$)', shared_line):
                            shared_opts[opt_m.group(1)] = opt_m.group(2).strip()
                    q['b1_shared_options'] = shared_opts
                    b1_groups[q['b1_group']] = shared_opts
                    i += 1
            else:
                if current_b1_group:
                    q['b1_group'] = current_b1_group

        stem_lines = []
        while i < len(lines):
            line_i = lines[i].strip()

            sub_q_match = re.match(r'(N\d+-\d+)[：:]\s*(.+)', line_i)
            if sub_q_match and qtype == 'B1':
                q['question'] = sub_q_match.group(2).strip()
                i += 1
                continue

            opt_match = re.match(r'^-\s*([A-E])\.\s*(.+)', line_i)
            if opt_match:
                q['options'][opt_match.group(1)] = opt_match.group(2).strip()
                i += 1
                continue

            ans_match = re.match(r'^答案[：:]\s*([A-E]+)', line_i)
            if ans_match:
                q['answer'] = ans_match.group(1)
                i += 1
                continue

            ana_match = re.match(r'^解析[：:]\s*(.+)', line_i)
            if ana_match:
                q['analysis'] = ana_match.group(1)
                i += 1
                break

            if line_i == '---':
                i += 1
                break

            if line_i and not line_i.startswith('**') and not line_i.startswith('#'):
                stem_lines.append(line_i)
            elif line_i.startswith('**'):
                break

            i += 1

        if stem_lines:
            q['question'] = ' '.join(stem_lines)

        if qtype == 'B1' and not q['options']:
            if q['b1_shared_options']:
                q['options'] = q['b1_shared_options']
            elif q.get('b1_group') and q['b1_group'] in b1_groups:
                q['options'] = b1_groups[q['b1_group']]
            elif current_b1_group and current_b1_group in b1_groups:
                q['options'] = b1_groups[current_b1_group]

        if not q['question'] and not q['options']:
            continue

        questions.append(q)

    return questions
