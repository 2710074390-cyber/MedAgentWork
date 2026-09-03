#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外科学（二）主复习资料整合脚本。

输入：
  - 99_前导与整合模板.md   （科目导航/使用指南/D3 谱系/模块速览地图 + 免责声明）
  - 97_D5跨模块概念地图.md   （D5 草稿）
  - 模块01~08_*.md           （8 个模块正文 + 「附录贡献」块）
输出：
  - 复习资料/外科学（二）_主复习资料.md

处理：每模块取「附录贡献」之前的正文；附录贡献块拆成
  页码索引→附录一 / 术语表→附录二 / 口诀→附录三；
  [!NOTE] 素材冲突与补充说明 → 附录四；模块信息速览仅用于日志统计。
页码范围校验：P 值必须落在该模块允许区间，否则报 "超出范围"。
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(BASE, "..", "..", "复习资料", "外科学（二）_主复习资料.md"))

MODULES = [
    ("01", "模块1：胸部损伤、肺疾病、食管疾病", (257, 288)),
    ("02", "模块2：腹外疝、急性化脓性腹膜炎、胃十二指肠疾病", (342, 387)),
    ("03", "模块3：小肠疾病、阑尾疾病、结直肠与肛管疾病", (389, 441)),
    ("04", "模块4：肝疾病、门静脉高压症、胆道疾病、胰腺疾病", (442, 497)),
    ("05", "模块5：周围血管与淋巴疾病", (320, 339)),
    ("06", "模块6：泌尿系统疾病（损伤、感染、结石、肿瘤、良性前列腺增生）", (512, 577)),
    ("07", "模块7：骨折、关节损伤、脊柱脊髓损伤、骨盆骨折", (613, 690)),
    ("08", "模块8：骨与关节化脓性感染、骨肿瘤", (730, 769)),
]
# 允许的额外页码区间（跨章节真实引用，均经 chunk 元数据核验）
EXTRA_RANGES = {
    "05": [(50, 52), (313, 319)],
    "03": [(363, 369), (503, 509)],   # 第37章腹膜炎 / 第47-48章消化道出血与急腹症诊断
    "07": [(691, 699)],               # 第66章周围神经损伤
}

FILES = {
    "99": os.path.join(BASE, "99_前导与整合模板.md"),
    "97": os.path.join(BASE, "97_D5跨模块概念地图.md"),
    "01": os.path.join(BASE, "模块01_胸部损伤肺疾病食管疾病.md"),
    "02": os.path.join(BASE, "模块02_腹外疝腹膜炎胃十二指肠疾病.md"),
    "03": os.path.join(BASE, "模块03_小肠阑尾结直肠肛管疾病.md"),
    "04": os.path.join(BASE, "模块04_肝胆胰疾病.md"),
    "05": os.path.join(BASE, "模块05_周围血管与淋巴疾病.md"),
    "06": os.path.join(BASE, "模块06_泌尿系统疾病.md"),
    "07": os.path.join(BASE, "模块07_骨折与关节损伤.md"),
    "08": os.path.join(BASE, "模块08_骨感染与骨肿瘤.md"),
}

# ---------- 工具 ----------

def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def split_contribution(text):
    """拆出「附录贡献」块之前的正文与之后的贡献内容。"""
    m = re.search(r"^## 「附录贡献」", text, re.M)
    if not m:
        return text.strip(), ""
    return text[: m.start()].strip(), text[m.start():]


def harvest(contrib, mod_title):
    """从贡献块中提取 页码/术语/口诀/速览/素材说明。"""
    out = {"pages": [], "terms": [], "mnemonics": [], "overview": [], "notes": []}
    # 子节切分
    sections = {}
    pos = None
    cur = None
    for line in contrib.splitlines():
        if line.startswith("### "):
            cur = line[4:].strip()
            sections.setdefault(cur, [])
            pos = cur
        elif cur:
            sections[cur].append(line)
    for name, lines in sections.items():
        if "页码" in name:
            for ln in lines:
                if ln.startswith("- ") and "P" in ln:
                    out["pages"].append(ln.strip())
        elif "术语" in name:
            for ln in lines:
                if ln.startswith("|") and "术语" not in ln and ln.strip("| ").replace("-", "").strip():
                    out["terms"].append(ln.strip())
        elif "口诀" in name:
            for ln in lines:
                if re.match(r"^\d+\.\s", ln.strip()):
                    out["mnemonics"].append(ln.strip())
                elif ln.strip() and not ln.startswith("|") and "```" not in ln:
                    # 口诀可能跨行：以数字开头者为准，其余作为承接行忽略（子代理均单行）
                    pass
        elif "速览" in name:
            for ln in lines:
                if ln.startswith("- "):
                    out["overview"].append(ln.strip())
        else:
            out["notes"].append(ln)
    # 素材冲突说明（可能在贡献块内，也可能在文件最末——由调用方补充）
    return out


def extract_notes(text):
    """提取 素材冲突/补充说明 类 [!NOTE] 块（跨行 >）。"""
    blocks = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if re.match(r"^>\s*\[!NOTE\]\s*(素材|来源|冲突|补充)", lines[i]):
            blk = [lines[i]]
            i += 1
            while i < len(lines) and lines[i].startswith(">"):
                blk.append(lines[i])
                i += 1
            blocks.append("\n".join(blk))
        else:
            i += 1
    return blocks


def page_ok(p, mod_key):
    lo, hi = dict((k, v) for k, _, v in MODULES)[mod_key]
    if lo <= p <= hi:
        return True
    for a, b in EXTRA_RANGES.get(mod_key, []):
        if a <= p <= b:
            return True
    return False


def find_page_of_module(contrib_text, mod_key):
    """收集页码索引中的 P 值以校验。"""
    vals = []
    for m in re.finditer(r"P(\d{2,3})(?:-(\d{2,3}))?", contrib_text):
        a = int(m.group(1))
        vals.append(a)
        if m.group(2):
            vals.append(int(m.group(2)))
    return vals


# ---------- 主流程 ----------

problems = []
summary = []

body_parts = []
for mod, title, rng in MODULES:
    text = read(FILES[mod])
    body, contrib = split_contribution(text)
    hn = harvest(contrib, title)
    # 页码范围校验（对整个文件正文+贡献的 P 值）
    for p in find_page_of_module(text, mod):
        if not page_ok(p, mod):
            problems.append(f"{mod} P{p} 超出允许区间 {rng}")
    # 模块信息速览 → 日志
    ov = "; ".join(hn["overview"])[:160]
    summary.append(f"{mod} | 页码索引 {len(hn['pages'])} | 术语 {len(hn['terms'])} | 口诀 {len(hn['mnemonics'])} | {ov}")
    body_parts.append((mod, title, body, hn))

# 正文拼接（去掉每段首尾多余 --- 分隔线，统一以 --- 连接）


def normalize_headings(body):
    """统一标题层级：模块标题 ## 模块N 保留；其余 ##→###；#####/######→####。"""
    lines = []
    for line in body.splitlines():
        m = re.match(r"^(#{2,6})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            content = m.group(2)
            if level == 2 and not re.match(r"^模块\d+[:：]", content):
                level = 3
            elif level >= 5:
                level = 4
            lines.append("#" * level + " " + content)
        else:
            lines.append(line)
    return "\n".join(lines)


joined = []
for mod, title, body, hn in body_parts:
    b = normalize_headings(body)
    b = re.sub(r"\n---\s*$", "", b.strip())
    b = re.sub(r"^(---\s*\n)+", "", b)
    joined.append(b.rstrip())
modules_md = "\n\n---\n\n".join(joined)

# D5
d5_raw = read(FILES["97"])
d5_lines = d5_raw.splitlines()
while d5_lines and not d5_lines[0].startswith("#"):
    d5_lines.pop(0)  # 去掉可能的前导空行
d5_body = "\n".join(d5_lines[1:]).strip()  # 去掉标题行
d5_md = "## 🗺️ 外科学跨模块概念地图（D5）\n\n" + d5_body

# 附录一：页码索引
app1 = ["## 附录一：教材知识点页码索引", ""]
for mod, title, body, hn in body_parts:
    app1.append(f"**{title.replace('模块', '模块', 1)}**")
    app1.extend(hn["pages"])
    app1.append("")
app1 = "\n".join(app1).rstrip()

# 附录二：术语对照（合并大表）
rows = []
for mod, title, body, hn in body_parts:
    rows.extend(hn["terms"])
app2_lines = ["## 附录二：术语同意异名对照表", "", "| 术语 | 同义/异名 | 备注 |", "|------|------|------|"]
app2_lines.extend(rows)
app2 = "\n".join(app2_lines)

# 附录三：口诀（全局重编号）
mn = []
for mod, title, body, hn in body_parts:
    mn.extend(hn["mnemonics"])
app3 = ["## 附录三：必背记忆口诀汇总", ""]
app3.extend(f"{i}. {re.sub(r'^\\d+\\.\\s*', '', m)}" for i, m in enumerate(mn, 1))
app3 = "\n".join(app3).rstrip()

# 附录四：素材冲突与补充说明（从各模块文件尾部抽取）
app4 = ["## 附录四：素材冲突与补充说明（供复核）", ""]
for mod, title, body, hn in body_parts:
    notes = extract_notes(read(FILES[mod]))
    if notes:
        app4.append(f"**{title.replace('模块', '模块', 1)}**")
        app4.append("")
        for n in notes:
            app4.append(n)
        app4.append("")
app4 = "\n".join(app4).rstrip()

# 组装
tpl = read(FILES["99"])
placeholder = "（模块 + D5 + 附录在整合时插入）"
if placeholder not in tpl:
    problems.append("99 模板中未找到占位行")
insert = "\n\n".join([modules_md, d5_md, app1, app2, app3, app4])
final = tpl.replace(placeholder, insert)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(final)

print(f"输出: {OUT}")
print(f"字符数: {len(final)} | 行数: {final.count(chr(10)) + 1}")
print("模块统计:")
for s in summary:
    print("  -", s)
print("页码越界问题:", problems if problems else "无")
