#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_obsidian.py —— Obsidian 渲染 / PDF 导出兼容性门禁

与 scripts/check_visual.py 同风格：FAIL 为结构性缺陷（在 Obsidian 中必然出错），
WARN 为体验 / 导出风险。--strict 让 WARN 也计入退出码。

为什么需要它：
    Obsidian 不是 CommonMark 的宽松实现，它对若干结构有硬性要求
    （HTML 块内不解析 markdown、链接解析依赖 vault 索引、details 默认折叠）。
    这些缺陷在纯文本编辑器里看不出来，只在 Obsidian 渲染 / 导出 PDF 时暴露。
    本脚本把「渲染期才暴露的缺陷」提前到「提交前可检出」。

用法:
    python scripts/check_obsidian.py --all
    python scripts/check_obsidian.py 大三下/复习资料/中医学_主复习资料.md
    python scripts/check_obsidian.py --all --json reports/obsidian_check.json
    python scripts/check_obsidian.py --all --strict
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 阈值（集中管理，便于调参；--strict 不改变阈值，只改变退出码语义）
# ---------------------------------------------------------------------------

# 单 md 超过此体积，Obsidian 阅读视图渲染与 PDF 导出会明显卡顿甚至超时
MAX_FILE_BYTES = 512 * 1024
# 单文件引用图片总量（PDF 会把图片内联，决定产物体积与导出耗时）
MAX_IMAGE_BYTES = 60 * 1024 * 1024
# 连续空行上限（Obsidian 阅读视图会渲染成大片留白）
MAX_CONSEC_BLANK = 2
# 标题层级允许的最大跳跃（h1 -> h3 会打断 outline 树）
MAX_HEADING_JUMP = 1

# 默认检查目标：三类 md 产物
# 默认检查目标：Obsidian 导出用产物。
# 只覆盖 Obsidian产物/ —— 本门禁的职责是「确保导出 PDF 的 md 合规」，
# 题库（最终产物/）与导航（_MOC/）不用于 PDF 导出，不在范围内。
# [!_]* 排除 _source/ 等归档目录（原始整册文件保留在那里供回溯）。
DEFAULT_GLOBS = [
    "Obsidian产物/*.md",
    "Obsidian产物/[!_]*/*.md",
    "_MOC/*.md",          # 导航笔记含大量 wikilink，是歧义检查的重点对象
]

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", ".bmp", ".avif"}

# ---------------------------------------------------------------------------
# 正则
# ---------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(\s*<?([^)>\s]+)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)")
WIKI_IMAGE_RE = re.compile(r"!\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
HTML_IMG_RE = re.compile(r"<img\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(\S.*?)[ \t]*#*[ \t]*$", re.M)
DETAILS_RE = re.compile(r"<details\b([^>]*)>(.*?)</details>", re.S | re.I)
TABLE_HTML_RE = re.compile(r"<table\b", re.I)
BR_RE = re.compile(r"<br\s*/?>", re.I)
MERMAID_RE = re.compile(r"^```mermaid[ \t]*\r?\n(.*?)^```", re.S | re.M)
# mermaid 内联样式指令：语法随版本变动，易导致整图渲染失败
MERMAID_STYLE_RE = re.compile(r"^\s*(?:linkStyle|style|classDef|class)\b", re.M)
# HTML 块内的 markdown 语法（Obsidian 不解析）
MD_BOLD_RE = re.compile(r"\*\*[^*\n]+\*\*|__[^_\n]+__")
MD_LIST_RE = re.compile(r"^[ \t]*(?:[-*+]|\d+\.)[ \t]+\S", re.M)
MD_TABLE_ROW_RE = re.compile(r"^[ \t]*\|.*\|[ \t]*$", re.M)
MD_MATH_RE = re.compile(r"(?<!\\)\$[^$\n]+\$")
CONSEC_BLANK_RE = re.compile(r"\n(?:[ \t]*\n){%d,}" % (MAX_CONSEC_BLANK + 1))
# Obsidian 内部链接（wikilink）—— 用于检查同名文件导致的解析歧义
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
# 折叠标记：Obsidian 的 callout（原生特性，替代 <details> 的正解）
CALLOUT_RE = re.compile(r"^>[ \t]*\[![a-zA-Z]+\]", re.M)

# --- <details> 的 HTML block 边界 ---
# CommonMark 规范：details 属于 HTML block 类型 6，从标签行开始，**到第一个空行结束**。
# 因此「标签行 ~ 首个空行」区间内的 markdown 不解析；空行之后的内容恢复正常解析。
# 这是本脚本最容易写错的地方：不能用「整个 details 块」判定，
# 必须按空行切出 HTML 区间，否则会把正常渲染的内容误报为缺陷。
DETAILS_BLANK_RE = re.compile(r"\n[ \t]*\n")
# --- 被压成单行的判定 ---
# 背景：MinerU 会把「表格源码」「mermaid 源码」压成一行，用「 ／ 」代替换行。
# 这类内容在 Obsidian 里语法不成立（表格要三行、代码块要围栏独占行），不会渲染。

def _is_flattened_table_line(line: str) -> bool:
    """判断某行是否是把「表头 + 分隔 + 数据」压成一行的表格。

    必须排除正常的表格分隔行 |---|---|：它本身就是「管道符 + 连字符」。
    判据：管道符 >= 4 个、含分隔线、且去掉分隔符后仍有内容（表头文字或数据）。
    正常分隔行去掉 | - : 空格后为空串，因此不会命中。
    """
    if line.count("|") < 4:
        return False
    if "---" not in line and ":-:" not in line:
        return False
    residue = line.replace("|", "").replace("-", "").replace(":", "")
    residue = residue.replace(" ", "").replace("\t", "").replace("／", "")
    return len(residue) > 0


def _is_flattened_fence_line(line: str) -> bool:
    """判断某行是否是把整个代码块压成一行的产物。

    特征：以 ``` 开头、以 ``` 结尾、且中间有内容（长度 > 20）。
    正常围栏行只有一个 ``` 且很短，不会命中。
    """
    s = line.strip()
    return len(s) > 20 and s.startswith("```") and s.endswith("```")


def analyze_details(body: str, masked: str | None = None) -> dict:
    """按 CommonMark HTML block 边界分析 <details> 块。

    参数:
        body    原始正文 —— 用于 flattened 检测（需要看到被压平的内容，
                因为压平的代码块在 masked 里已被屏蔽，看 masked 会漏报）
        masked  屏蔽代码区域后的正文 —— 用于结构判定；与 body 等长，位置可直接映射

    返回:
        total       details 块总数
        no_open     未加 open 属性的数量（PDF 导出为折叠态）
        md_in_html  「标签行 ~ 首个空行」区间内含 markdown 的位置（不解析）
        flattened   details 内表格/代码块被压成单行的位置（语法不成立）
    """
    src = masked if masked is not None else body
    res: dict = {"total": 0, "no_open": 0, "md_in_html": [], "flattened": []}
    for d in DETAILS_RE.finditer(src):
        res["total"] += 1
        line_no = src.count("\n", 0, d.start()) + 1
        if "open" not in d.group(1).lower():
            res["no_open"] += 1

        inner = d.group(2)
        sep = DETAILS_BLANK_RE.search(inner)
        head = inner[:sep.start()] if sep else inner   # HTML block 内，markdown 不解析

        hits = []
        if MD_BOLD_RE.search(head):
            hits.append("粗体")
        if MD_LIST_RE.search(head):
            hits.append("列表")
        if MD_TABLE_ROW_RE.search(head):
            hits.append("表格行")
        if MD_MATH_RE.search(head):
            hits.append("数学")
        if hits:
            res["md_in_html"].append(f"L{line_no}({'+'.join(hits)})")

        # flattened 用未屏蔽的原文取同一区间（masked 与 body 等长，位置一一对应）
        off = sep.end() if sep else 0
        rest_raw = body[d.start(2) + off: d.end(2)]
        if any(_is_flattened_table_line(ln) for ln in rest_raw.split("\n")):
            res["flattened"].append(f"L{line_no}(表格)")
        elif any(_is_flattened_fence_line(ln) for ln in rest_raw.split("\n")):
            res["flattened"].append(f"L{line_no}(代码块)")
    return res


# --- 代码区域屏蔽 ---
# 结构检查必须跳过代码块与行内代码，否则「文档里写的示例文本」会被当成真结构。
# 反例：文档里写「用 `![](路径)` 表示相对路径」时，那个 `![](路径)` 不是图片引用；
#       写「`<details>` 有三个坑」时，那个 `<details>` 不是折叠块。
# 屏蔽采用等长替换（保留换行位置），因此行号与原文完全一致，报错定位不受影响。
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def mask_code(text: str) -> str:
    """把围栏代码块与行内代码替换为等长空白，保留换行位置。"""
    out: list[str] = []
    fence_char: str | None = None
    for ln in text.split("\n"):
        m = re.match(r"^[ \t]*(`{3,}|~{3,})", ln)
        if fence_char is None:
            if m:
                out.append("." * len(ln))
                # 同一行内出现第二个围栏标记 = 单行自闭（MinerU 把代码块压成一行的产物）。
                # 此时整行按代码屏蔽，但绝不能进入围栏态，
                # 否则该行之后的所有内容都会被误屏蔽，导致后续缺陷全部漏报。
                if not re.search(r"`{3,}|~{3,}", ln[m.end():]):
                    fence_char = m.group(1)[0]
            else:
                out.append(INLINE_CODE_RE.sub(lambda x: "." * len(x.group(0)), ln))
        else:
            out.append("." * len(ln))
            if m and m.group(1)[0] == fence_char:
                fence_char = None
    return "\n".join(out)


# ---------------------------------------------------------------------------
# vault 定位与索引
# ---------------------------------------------------------------------------

def find_vault_root(start: Path) -> Path | None:
    """从 start 向上查找含 .obsidian 的目录。"""
    try:
        p = start.resolve()
    except OSError:
        return None
    for cand in [p if p.is_dir() else p.parent, *p.parents]:
        if (cand / ".obsidian").is_dir():
            return cand
    return None


def build_image_index(vault: Path) -> dict[str, list[str]]:
    """建立「文件名 -> [vault 相对路径, ...]」索引，用于模拟 Obsidian 链接解析。"""
    idx: dict[str, list[str]] = {}
    for p in vault.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in IMAGE_EXTS:
            continue
        # 跳过 Obsidian 自身的配置与回收站
        rel_parts = p.relative_to(vault).parts
        if any(part.startswith(".") for part in rel_parts):
            continue
        idx.setdefault(p.name, []).append("/".join(rel_parts))
    return idx


def build_md_index(vault: Path) -> dict[str, list[str]]:
    """建立「md 文件名 -> [vault 相对路径, ...]」索引，用于 wikilink 歧义检查。

    Obsidian 解析 [[名字]] 时，若 vault 内存在多个同名 md，会任选其一 ——
    这会让链接静默指向错误的文件，比断链更难发现。
    """
    idx: dict[str, list[str]] = {}
    for p in vault.rglob("*.md"):
        parts = p.relative_to(vault).parts
        if any(x.startswith(".") for x in parts):
            continue
        idx.setdefault(p.name, []).append("/".join(parts))
    return idx


def load_ignore_filters(vault: Path) -> list[str]:
    """读取 vault 的 userIgnoreFilters（被排除的文件在 Obsidian 中不可见）。"""
    app_json = vault / ".obsidian" / "app.json"
    if not app_json.is_file():
        return []
    try:
        data = json.loads(app_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    filters = data.get("userIgnoreFilters") or []
    return [str(x) for x in filters]


def is_ignored(rel_path: str, filters: list[str]) -> str | None:
    """判断 vault 相对路径是否命中排除规则，命中则返回命中的规则。"""
    norm = "/" + rel_path.replace("\\", "/").lstrip("/")
    for f in filters:
        rule = f.strip()
        if not rule:
            continue
        rule_norm = rule if rule.startswith("/") else "/" + rule
        if norm == rule_norm or norm.startswith(rule_norm.rstrip("/") + "/"):
            return rule
        # 规则也可能指向具体文件
        if norm.endswith(rule_norm):
            return rule
    return None


def resolve_image(raw: str, md_rel: str, vault: Path,
                  idx: dict[str, list[str]]) -> tuple[str, str]:
    """模拟 Obsidian 的链接解析，返回 (状态, 说明)。

    状态取值:
        remote      —— 远程 URL，交给网络（导出 PDF 时可能破图）
        ok-vault    —— vault 根相对路径命中
        ok-mdrel    —— md 文件所在目录相对路径命中
        ok-byname   —— 按文件名全局唯一命中（Obsidian 的兜底解析）
        ambiguous   —— 多个同名文件，解析不确定
        broken      —— 解析失败
    """
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw) or raw.startswith("data:"):
        return "remote", raw

    clean = raw.split("#", 1)[0].strip()
    if not clean:
        return "broken", "(空路径)"

    if clean.startswith("/"):  # vault 绝对路径
        rel = clean.lstrip("/")
        return ("ok-vault", rel) if (vault / rel).is_file() else ("broken", rel)

    # 1) vault 根相对
    if (vault / clean).is_file():
        return "ok-vault", clean

    # 2) md 文件所在目录相对
    md_dir = (vault / md_rel).parent
    cand = md_dir / clean
    if cand.is_file():
        return "ok-mdrel", str(cand.relative_to(vault)).replace("\\", "/")

    # 3) 按文件名全局匹配（Obsidian 的兜底行为）
    name = Path(clean).name
    hits = idx.get(name, [])
    if len(hits) == 1:
        return "ok-byname", hits[0]
    if len(hits) > 1:
        return "ambiguous", "; ".join(hits[:4])
    return "broken", clean


# ---------------------------------------------------------------------------
# 检查
# ---------------------------------------------------------------------------

class Finding:
    __slots__ = ("level", "code", "msg")

    def __init__(self, level: str, code: str, msg: str):
        self.level = level
        self.code = code
        self.msg = msg


def check_file(md_path: Path, vault: Path, idx: dict[str, list[str]],
               filters: list[str], raw: str,
               md_idx: dict[str, list[str]] | None = None) -> tuple[list[Finding], dict]:
    findings: list[Finding] = []
    stats: dict = {"bytes": len(raw.encode("utf-8")), "images": 0, "image_bytes": 0}

    try:
        md_rel = str(md_path.resolve().relative_to(vault)).replace("\\", "/")
    except ValueError:
        md_rel = md_path.name

    # --- F5 文件是否被 vault 排除 ---
    hit = is_ignored(md_rel, filters)
    if hit:
        findings.append(Finding(
            "FAIL", "F5",
            f"被 vault 排除规则命中（{hit}）—— 在 Obsidian 中不可见，无法导出"))

    # --- frontmatter ---
    m = FRONTMATTER_RE.match(raw)
    body = raw[m.end():] if m else raw
    fm_text = m.group(1) if m else ""
    # 结构检查一律跑在 mask_code 之后的文本上，避免文档里写的示例代码被当成真结构。
    # mask 为等长替换，故行号与原文一致。
    masked = mask_code(body)
    if not m:
        findings.append(Finding(
            "WARN", "W1",
            "无 frontmatter —— 无法用 cssclasses 指定样式，PDF 元数据（标题/作者）为空"))
    else:
        if not re.search(r"^\s*title\s*:", fm_text, re.M):
            findings.append(Finding("WARN", "W1", "frontmatter 缺 title —— PDF 元数据标题为空"))

    # --- 图片链接 ---
    imgs: list[tuple[int, str]] = []
    for mm in MD_IMAGE_RE.finditer(masked):
        imgs.append((masked.count("\n", 0, mm.start()) + 1, mm.group(2)))
    for mm in WIKI_IMAGE_RE.finditer(masked):
        imgs.append((masked.count("\n", 0, mm.start()) + 1, mm.group(1)))
    for mm in HTML_IMG_RE.finditer(masked):
        imgs.append((masked.count("\n", 0, mm.start()) + 1, mm.group(1)))

    broken: list[str] = []
    ambiguous: list[str] = []
    remote: list[str] = []
    byname: list[str] = []
    for line_no, raw_link in imgs:
        status, detail = resolve_image(raw_link, md_rel, vault, idx)
        if status == "broken":
            broken.append(f"L{line_no}: {detail}")
        elif status == "ambiguous":
            ambiguous.append(f"L{line_no}: {detail}")
        elif status == "remote":
            remote.append(f"L{line_no}: {detail[:60]}")
        elif status == "ok-byname":
            byname.append(f"L{line_no}: {raw_link} -> {detail}")
        # 所有成功解析的分支都要计入字节数（ok-vault / ok-mdrel / ok-byname）
        if status.startswith("ok-"):
            fp = vault / detail
            if fp.is_file():
                stats["image_bytes"] += fp.stat().st_size

    stats["images"] = len(imgs)

    if broken:
        findings.append(Finding(
            "FAIL", "F1",
            f"图片断链 {len(broken)} 处（导出 PDF 为破图）例：{broken[0]}"))
    if ambiguous:
        findings.append(Finding(
            "FAIL", "F2",
            f"图片链接歧义 {len(ambiguous)} 处（同名多文件，解析不确定）例：{ambiguous[0]}"))
    if remote:
        findings.append(Finding(
            "WARN", "W10",
            f"远程图片 {len(remote)} 处（离线导出会破图）例：{remote[0]}"))
    if byname:
        findings.append(Finding(
            "WARN", "W11",
            f"依赖文件名兜底解析 {len(byname)} 处（重命名即断链，建议改 vault 相对路径）"))

    # --- wikilink 解析歧义 ---
    # Obsidian 遇到多个同名 md 会任选其一，链接静默指向错误文件，比断链更难发现。
    if md_idx:
        amb_links: list[str] = []
        for mm in WIKILINK_RE.finditer(masked):
            target = mm.group(1).strip()
            if not target:
                continue
            cand = vault / (target if target.endswith(".md") else target + ".md")
            if cand.is_file():
                continue          # vault 相对路径命中，无歧义
            hits = md_idx.get(Path(target).name + ".md", [])
            if len(hits) > 1:
                ln = masked.count(chr(10), 0, mm.start()) + 1
                amb_links.append(f"L{ln}: [[{target}]] -> {len(hits)} 个同名")
        if amb_links:
            findings.append(Finding(
                "FAIL", "F6",
                f"wikilink 解析歧义 {len(amb_links)} 处（同名 md 多个，会静默指向错误文件）"
                f"例：{amb_links[0]}"))

    # --- 标题层级 ---
    levels = [len(mm.group(1)) for mm in HEADING_RE.finditer(masked)]
    h1_count = levels.count(1)
    if h1_count == 0:
        findings.append(Finding("WARN", "W7", "无 H1 —— Obsidian 大纲树缺根节点"))
    elif h1_count > 1:
        findings.append(Finding(
            "WARN", "W7", f"H1 有 {h1_count} 个 —— 一篇文档应只有一个 H1（其余降级为 H2）"))

    jumps = []
    for prev, cur in zip(levels, levels[1:]):
        if cur - prev > MAX_HEADING_JUMP:
            jumps.append(f"H{prev}->H{cur}")
    if jumps:
        findings.append(Finding(
            "FAIL", "F3",
            f"标题层级跳跃 {len(jumps)} 处（outline 断裂）例：{', '.join(jumps[:3])}"))

    # --- details 块（按 HTML block 边界判定） ---
    dstat = analyze_details(body, masked)
    if dstat["total"]:
        if dstat["no_open"]:
            findings.append(Finding(
                "WARN", "W5",
                f"details 块 {dstat['no_open']}/{dstat['total']} 个未加 open —— "
                f"PDF 导出为折叠态，内容不可见（修法：标签写 <details open>）"))
        if dstat["md_in_html"]:
            findings.append(Finding(
                "FAIL", "F4",
                f"details 标签行与首个空行之间含 markdown {len(dstat['md_in_html'])} 处"
                f"（该区间属 HTML block，markdown 不解析，会原样显示符号）"
                f"例：{dstat['md_in_html'][0]}"))
        if dstat["flattened"]:
            findings.append(Finding(
                "WARN", "W13",
                f"details 内表格/代码块被压成单行 {len(dstat['flattened'])} 处"
                f"（三行语法压成一行即失效，不会渲染）例：{dstat['flattened'][0]}"))
        if not CALLOUT_RE.search(masked):
            findings.append(Finding(
                "WARN", "W9",
                "未使用 callout —— Obsidian 原生 `> [!note]- 标题` 折叠块可替代 <details> "
                "且导出正常"))

    # --- HTML 表格 ---
    n_html_table = len(TABLE_HTML_RE.findall(masked))
    if n_html_table:
        findings.append(Finding(
            "WARN", "W4",
            f"HTML 表格 {n_html_table} 处（能渲染，但打印样式难控制，建议转 md 表格）"))

    # --- <br> ---
    n_br = len(BR_RE.findall(masked))
    if n_br:
        findings.append(Finding(
            "WARN", "W6", f"<br> 硬换行 {n_br} 处（建议用空行分段或行尾双空格）"))

    # --- mermaid ---
    # mermaid 必须用未屏蔽的 body：需检查代码块内的 style 指令原文
    mermaid_blocks = MERMAID_RE.findall(body)
    if mermaid_blocks:
        bad = sum(1 for blk in mermaid_blocks if MERMAID_STYLE_RE.search(blk))
        if bad:
            findings.append(Finding(
                "WARN", "W8",
                f"mermaid 含内联样式指令 {bad}/{len(mermaid_blocks)} 处"
                f"（linkStyle/style/classDef，易致整图渲染失败）"))

    # --- 连续空行 ---
    n_blank = len(CONSEC_BLANK_RE.findall(masked))
    if n_blank:
        findings.append(Finding(
            "WARN", "W12", f"连续空行（>{MAX_CONSEC_BLANK} 行）{n_blank} 处 —— 阅读视图大片留白"))

    # --- 体积 ---
    if stats["bytes"] > MAX_FILE_BYTES:
        findings.append(Finding(
            "WARN", "W2",
            f"文件 {stats['bytes'] / 1024:.0f} KB 超过 {MAX_FILE_BYTES // 1024} KB —— "
            f"阅读视图与 PDF 导出会卡顿，建议按章拆分"))
    if stats["image_bytes"] > MAX_IMAGE_BYTES:
        findings.append(Finding(
            "WARN", "W3",
            f"引用图片 {stats['image_bytes'] / 1048576:.1f} MB 超过 "
            f"{MAX_IMAGE_BYTES // 1048576} MB —— PDF 体积与导出耗时风险"))

    stats["headings"] = {f"H{i}": levels.count(i) for i in range(1, 7)}
    stats["details"] = dstat["total"]
    stats["mermaid"] = len(mermaid_blocks)
    stats["html_table"] = n_html_table
    stats["rel_path"] = md_rel
    return findings, stats


# ---------------------------------------------------------------------------
# 目标发现与主流程
# ---------------------------------------------------------------------------

def discover_targets(root: Path) -> list[Path]:
    seen: list[Path] = []
    for pattern in DEFAULT_GLOBS:
        for p in sorted(root.glob(pattern)):
            if p.is_file() and p not in seen:
                seen.append(p)
    return seen


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Obsidian 渲染 / PDF 导出兼容性门禁")
    ap.add_argument("files", nargs="*", help="待检查的 md 文件")
    ap.add_argument("--all", action="store_true", help="检查默认目标集合")
    ap.add_argument("--root", default=".", help="项目根目录（默认当前目录）")
    ap.add_argument("--vault", default=None, help="vault 根目录（默认自动向上查找 .obsidian）")
    ap.add_argument("--json", default=None, help="把结果写入 JSON 文件")
    ap.add_argument("--strict", action="store_true", help="WARN 也计入退出码")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()

    if args.all:
        targets = discover_targets(root)
    elif args.files:
        targets = [Path(f) for f in args.files]
    else:
        ap.print_help()
        return 2

    if not targets:
        print("没有找到任何目标文件。")
        return 2

    vault = Path(args.vault).resolve() if args.vault else find_vault_root(targets[0].resolve())
    if vault is None:
        print("✘ 未找到 vault 根（向上查找 .obsidian 失败）。用 --vault 显式指定。")
        return 2

    print(f"vault: {vault}")
    filters = load_ignore_filters(vault)
    print(f"vault 排除规则: {len(filters)} 条")
    idx = build_image_index(vault)
    print(f"图片索引: {sum(len(v) for v in idx.values())} 个文件 / {len(idx)} 个唯一名")
    md_idx = build_md_index(vault)
    dup_md = {k: v for k, v in md_idx.items() if len(v) > 1}
    print(f"md 索引: {sum(len(v) for v in md_idx.values())} 个文件 / {len(dup_md)} 组同名")
    print()

    n_fail = n_warn = 0
    report: list[dict] = []
    for t in targets:
        try:
            raw = t.read_text(encoding="utf-8")
        except OSError as e:
            print(f"▸ {t}\n    ✘ FAIL  读取失败: {e}")
            n_fail += 1
            continue

        findings, stats = check_file(t, vault, idx, filters, raw, md_idx)
        print(f"▸ {stats.get('rel_path', t.name)}")
        print(f"    · {stats['bytes'] / 1024:.0f} KB | 图片 {stats['images']} 张 "
              f"({stats['image_bytes'] / 1048576:.1f} MB) | details {stats['details']} | "
              f"mermaid {stats['mermaid']} | HTML表格 {stats['html_table']}")
        print(f"    · 标题 {stats['headings']}")
        if not findings:
            print("    ✓ 无问题")
        for f in findings:
            mark = "✘ FAIL" if f.level == "FAIL" else "⚠ WARN"
            print(f"    {mark}  [{f.code}] {f.msg}")
            if f.level == "FAIL":
                n_fail += 1
            else:
                n_warn += 1
        print()
        report.append({
            "file": stats.get("rel_path", str(t)),
            "stats": stats,
            "findings": [{"level": f.level, "code": f.code, "msg": f.msg} for f in findings],
        })

    print(f"FAIL={n_fail}  WARN={n_warn}  文件={len(targets)}")

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"vault": str(vault), "results": report},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"报告已写入 {out}")

    ok = (n_fail == 0) and (not args.strict or n_warn == 0)
    print("✅ Obsidian 门禁通过" if ok else "❌ Obsidian 门禁未通过")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
