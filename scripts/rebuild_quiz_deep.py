# -*- coding: utf-8 -*-
"""重新生成五套押题卷：新模板（深海主题） + 各卷原有题目数据（零内容改动）

注意：模板头部注释内含有 <script id="quiz-data"> 字面量文本，
     必须取最后一次出现的位置（真实脚本标签），否则会吞掉 <style> 块。
"""
import pathlib, re, sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = pathlib.Path(__file__).resolve().parent.parent
TPL = ROOT / 'scripts' / 'quiz_template.html'
DIR = ROOT / '大三下' / '押题卷'

OPEN = '<script id="quiz-data">'
CLOSE = '</script>'

def extract_data(html):
    """取真实 quiz-data 块内容（最后一个 OPEN 位置）"""
    i = html.rfind(OPEN)
    if i < 0:
        return None
    j = html.find(CLOSE, i + len(OPEN))
    if j < 0:
        return None
    return html[i + len(OPEN):j]

template = TPL.read_text(encoding='utf-8')
print(f'模板: {TPL} · {len(template)} 字符 · deep CSS: {"深海·未来主义" in template} · topbar var: {"var(--topbar-bg)" in template}')
assert '<script id="quiz-data">' in template

files = sorted(DIR.glob('*.html'))
print(f'待重建 {len(files)} 卷')
for f in files:
    old = f.read_text(encoding='utf-8')
    data_block = extract_data(old)
    if data_block is None:
        print(f'✗ {f.name}: 未找到真实 quiz-data 块，跳过')
        continue
    if 'PAPER_META' not in data_block or 'QUESTIONS' not in data_block:
        print(f'✗ {f.name}: quiz-data 块不完整，跳过')
        continue
    mt = re.search(r'title"\s*:\s*"([^"]+)"', data_block)
    subject = mt.group(1).replace('押题卷', '').strip() if mt else f.stem
    tpl_data = extract_data(template)
    ti = template.rfind(OPEN)
    tj = template.find(CLOSE, ti + len(OPEN))
    new = template[:ti] + OPEN + data_block + CLOSE + template[tj + len(CLOSE):]
    new = new.replace('{科目}', subject)
    assert '深海·未来主义' in new, f'{f.name}: 新页缺少 deep CSS（模板切片异常）'
    f.write_text(new, encoding='utf-8')
    n_q = data_block.count('"qid"')
    print(f'✓ {f.name}: {len(old)} → {len(new)} 字节 · 题目 {n_q} 个 · 科目 {subject}')

print('完成。')
