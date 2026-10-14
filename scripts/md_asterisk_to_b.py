# -*- coding: utf-8 -*-
"""把 MD 正文中的 **加粗** 统一转为 <b>加粗</b>（跳过围栏代码块与行内代码）。

用法: python -X utf8 scripts/md_asterisk_to_b.py "复习资料/外科学教学计划版/外科学（二）_主复习资料.md" [更多文件...]
先自动备份为 <原名>.bak，再转换。
"""
import os, re, sys, io, shutil
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 粗体配对：**xxx**，xxx 不含 **（内容里允许有 * 斜体标记，但不处理嵌套 **）
PAIR = re.compile(r'\*\*([^*]+?)\*\*')


def convert_line(ln, in_code):
    """返回 (转换后行, 是否处于代码块)。"""
    if ln.strip().startswith('```'):
        return ln, not in_code
    if in_code:
        return ln, True
    # 按反引号切分：奇数段为行内代码，不转换
    segs = ln.split('`')
    out = []
    for j, seg in enumerate(segs):
        if j % 2 == 1:
            out.append(seg)          # 行内代码原样保留
        else:
            out.append(PAIR.sub(r'<b>\1</b>', seg))
    return '`'.join(out), False


def main():
    for p in sys.argv[1:]:
        if not os.path.exists(p):
            print(f'不存在: {p}')
            continue
        bak = p + '.bak'
        if not os.path.exists(bak):
            shutil.copy2(p, bak)
        lines = open(p, encoding='utf-8').read().split('\n')
        in_code = False
        new_lines, converted = [], 0
        for ln in lines:
            nl, in_code = convert_line(ln, in_code)
            new_lines.append(nl)
            if nl != ln:
                converted += 1
        open(p, 'w', encoding='utf-8', newline='').write('\n'.join(new_lines))
        # 验证
        t = open(p, encoding='utf-8').read()
        print(f'{p}')
        print(f'  改动行数: {converted}, 剩余 **: {t.count(chr(42)*2)}, 新增 <b>: {t.count("<b>")}')


if __name__ == '__main__':
    main()
