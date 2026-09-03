# -*- coding: utf-8 -*-
"""模拟 CommonMark 围栏解析，找出未配对/嵌套异常位置"""
import re
import sys

path = sys.argv[1]
lines = open(path, encoding='utf-8').read().split('\n')

FENCE = re.compile(r'^\s{0,3}(`{3,}|~{3,})(.*)$')

stack = []  # (line_no, info)
open_line = None
problems = []

for i, line in enumerate(lines, 1):
    m = FENCE.match(line)
    if not m:
        continue
    fence = m.group(1)
    rest = m.group(2).strip()
    info = rest if rest else ''
    if not info:
        # 无信息串：闭合匹配的围栏，或开启新围栏
        if open_line is not None:
            open_line = None
        else:
            open_line = (i, fence, line.strip())
    else:
        # 带信息串：只能是开启；若当前已开启 → 嵌套错误
        if open_line is not None:
            problems.append((i, '嵌套开启(带信息串)时已有未闭合围栏', open_line))
            open_line = (i, fence, line.strip())
        else:
            open_line = (i, fence, line.strip())

if open_line is not None:
    problems.append((open_line[0], '未闭合围栏(到文件末尾仍开启)', None))

if not problems:
    print('OK: 无多组围栏问题')
else:
    for p in problems:
        print(f'L{p[0]}: {p[1]}  {p[2] if p[2] else p[0]}')
        if p[2]:
            print(f'   -> 关联配对开启行 L{p[2][0]} 内容: {p[2][2]!r}')
