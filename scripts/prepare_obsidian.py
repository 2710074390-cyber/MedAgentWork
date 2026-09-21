#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prepare_obsidian.py —— 把 md 产物适配 Obsidian 渲染与 PDF 导出

落实 4 条输出约定：
  1. 每篇必有 frontmatter（title / author / cssclasses / tags）
  2. 单一 H1 + 不跳级（层级只允许 ±1）
  3. <details> → callout（默认展开，且内部 markdown 完全可用）
  4. 图片与 md 同级（不改变相对路径）

附加能力：按指定标题级别拆分 + 生成 toc:true 目录笔记。

为什么 details 要转 callout（而不是只加 open）：
  <details> 属 CommonMark HTML block 类型 6，标签行到首个空行之间的 markdown 不解析；
  callout 是 Obsidian 原生语法，内部表格/列表/粗体全部可用，且 `[!note]+` 默认展开。

用法:
  # 单文件转换（不拆分）
  python scripts/prepare_obsidian.py --src a.md --out-dir out --title "书名"

  # 拆分：按 H2 拆，每章一个文件 + 生成目录笔记
  python scripts/prepare_obsidian.py --src a.md --out-dir out --title "讲义上册" --split-level 2

  # 批量：五册一起处理
  python scripts/prepare_obsidian.py --all
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 复用门禁里的代码区域屏蔽（同目录裸导入；scripts/ 不是 Python 包）
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_obsidian import mask_code  # noqa: E402

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

DEFAULT_AUTHOR = "MedAgentWork"

DETAILS_RE = re.compile(r"<details\b([^>]*)>(.*?)</details>", re.S | re.I)
SUMMARY_RE = re.compile(r"<summary[^>]*>(.*?)</summary>", re.S | re.I)
HEADING_LINE_RE = re.compile(r"^(#{1,6})[ \t]+(\S.*?)[ \t]*#*[ \t]*$")
FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)

# callout 类型按 summary 文字选择，让图标语义化
CALLOUT_TYPE_HINTS = [
    (re.compile(r"答案|解析|answer", re.I), "success"),
    (re.compile(r"陷阱|易错|注意|warning", re.I), "warning"),
    (re.compile(r"口诀|技巧|tip|记忆", re.I), "tip"),
    (re.compile(r"图内文字|流程图|折线图|图注|数据", re.I), "info"),
]


def yaml_str(s: str) -> str:
    """把字符串安全地写成 YAML 双引号标量。"""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def parse_frontmatter(text: str) -> tuple[dict | None, str]:
    """返回 (frontmatter 文本或 None, 去掉 frontmatter 的正文)。"""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    return m.group(1), text[m.end():]


def compact_blank_lines(text: str, *, max_blank: int = 1) -> str:
    """把连续空行压到最多 max_blank 个（阅读视图会渲染成大片留白）。

    借 mask_code 判定代码区域：代码块内的空行属于内容，必须原样保留。
    mask 用非空白占位符，所以「mask 后为空」等价于「原文就是空行」。
    """
    out: list[str] = []
    blank = 0
    for ln, ml in zip(text.split("\n"), mask_code(text).split("\n")):
        if ml.strip():
            blank = 0
            out.append(ln)
        else:
            blank += 1
            if blank <= max_blank:
                out.append(ln)
    return "\n".join(out)


def iter_headings(masked: str) -> list[tuple[int, int, str]]:
    """返回 [(行号, 级别, 标题文字), ...]，已跳过代码区域。"""
    out = []
    for i, ln in enumerate(masked.split("\n")):
        m = HEADING_LINE_RE.match(ln)
        if m:
            out.append((i, len(m.group(1)), m.group(2).strip()))
    return out


def build_frontmatter(title: str, *, author: str = DEFAULT_AUTHOR,
                      cssclass: str = "mgw-book", tags: list[str] | None = None,
                      series: str | None = None) -> str:
    lines = ["---", f"title: {yaml_str(title)}", f"author: {yaml_str(author)}",
             f"cssclasses: [{cssclass}]"]
    if series:
        lines.append(f"series: {yaml_str(series)}")
    if tags:
        lines.append("tags: [" + ", ".join(tags) + "]")
    lines.append("---")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 约定 2：单一 H1 + 不跳级
# ---------------------------------------------------------------------------

def normalize_headings(body: str, *, root_title: str | None = None) -> tuple[str, dict]:
    """把标题层级整理成「单一 H1 + 不跳级」。

    步骤：
      a. 若有多个 H1，保留第一个（或 root_title），其余降为 H2
      b. 逐条 clamp：级别不得比前一个深超过 1
    返回 (新正文, 统计)。
    """
    lines = body.split("\n")
    masked_lines = mask_code(body).split("\n")
    heads = iter_headings(mask_code(body))
    if not heads:
        return body, {"h1_before": 0, "demoted": 0, "clamped": 0}

    # a. H1 归一：保留第一个 H1，其余降为 H2
    # 判据必须是「是否已是第一个 H1」，不能写成 heads 的索引 k > 0 ——
    # 若文档以 H2/H3 开头（外科学就是这样），真正的第一个 H1 的 k 会 > 0，
    # 会被误降级，最终变成「无 H1」。
    demoted = 0
    h1_idx = [h for h in heads if h[1] == 1]
    first_h1_done = False
    for k, (ln_no, lv, txt) in enumerate(heads):
        if lv != 1:
            continue
        if not first_h1_done:
            first_h1_done = True
            continue
        lines[ln_no] = "## " + txt
        heads[k] = (ln_no, 2, txt)
        demoted += 1

    # b. 不跳级
    clamped = 0
    prev = 0
    for k, (ln_no, lv, txt) in enumerate(heads):
        want = lv if prev == 0 else min(lv, prev + 1)
        want = max(1, min(6, want))
        if want != lv:
            lines[ln_no] = "#" * want + " " + txt
            heads[k] = (ln_no, want, txt)
            clamped += 1
        prev = want

    return "\n".join(lines), {"h1_before": len(h1_idx), "demoted": demoted, "clamped": clamped}


# ---------------------------------------------------------------------------
# 约定 3：details → callout
# ---------------------------------------------------------------------------

def pick_callout_type(title: str) -> str:
    for pat, t in CALLOUT_TYPE_HINTS:
        if pat.search(title):
            return t
    return "note"


def details_to_callout(body: str, *, default_open: bool = True) -> tuple[str, int]:
    """把 <details> 转成 Obsidian callout。marker '+' = 默认展开，'-' = 默认折叠。"""
    marker = "+" if default_open else "-"
    count = 0

    def repl(m: re.Match) -> str:
        nonlocal count
        inner = m.group(2)
        sm = SUMMARY_RE.search(inner)
        title = re.sub(r"\s+", " ", sm.group(1)).strip() if sm else "展开"
        # 去掉原 details 的交互提示语 —— callout 默认展开后「点击展开」会自相矛盾
        # 括号内可能还夹着字数说明，如「流程图文字（324 字，点击展开）」
        title = re.sub(r"[（(][^（()）]*(?:展开|查看|显示|折叠)[）)]", "", title).strip()
        title = re.sub(r"[（(]\s*[）)]", "", title).strip()
        content = inner[sm.end():] if sm else inner
        content = content.strip("\n")

        ctype = pick_callout_type(title)
        # 标题后补一个空行（`>`），让后续块级内容（表格/代码块/列表）边界清晰。
        # 实测加不加都能渲染，但加空行更贴近 Obsidian 社区惯例，也更稳。
        out = [f"> [!{ctype}]{marker} {title}", ">"]
        for ln in content.split("\n"):
            out.append("> " + ln if ln.strip() else ">")
        count += 1
        return "\n".join(out)

    return DETAILS_RE.sub(repl, body), count


# ---------------------------------------------------------------------------
# 按章拆分
# ---------------------------------------------------------------------------

# 这些标题不单独成文件（原文档自带的目录会被新生成的 toc 笔记取代）
SKIP_SPLIT_TITLES = re.compile(r"^(目\s*录|contents|前言|序\s*言)$", re.I)


def _norm_cmp(s: str) -> str:
    """归一化用于比较：去掉空白、标点、间隔号等（「贺银成真题·下册」↔「真题下册」）。"""
    return re.sub(r"[\s·・\-—–_（）()【】\[\]:：,，。.、!！?？]", "", s)


def _is_toc_only(chunk: str) -> bool:
    """判断 chunk 是否只含目录（去掉标题行后全是列表项）。

    用途：真题册的结构是「# 书名 → ## 目录 → # 各年试卷」，
    按 H1 拆分时书名会成为一个只含目录的 chunk，应当跳过。
    只在**首个 chunk** 上使用该判据，避免误伤「整章都是列表」的正常章节。
    """
    lines = [l.strip() for l in chunk.split("\n") if l.strip()]
    content = [l for l in lines
               if not l.startswith("#")
               and not re.match(r"^([-*_])\s*\1\s*\1", l)]   # 忽略水平分隔线 --- / *** / ___
    if len(content) < 3:
        return False
    return all(re.match(r"^[-*+]\s+\S", l) for l in content)


def split_by_level(body: str, level: int) -> list[tuple[str, str, str | None]]:
    """按指定级别标题拆分，返回 [(标题, 含标题行的正文, 所属上级标题), ...]。

    关键设计（踩过的坑）：
      · **必须在 H1 归一之前拆分**。若先把多余的 H1 降级，文档的「篇」会变成 H2，
        于是拆分点里混进「篇」，产出 `02-第一篇…` 与 `03-一、…` 这种同级错乱。
      · 上级标题（级别 < level，如「篇」）**不单独成文件**，而是记为 series 写进 frontmatter，
        并从正文里删掉该标题行，避免它挂在上一章末尾。
      · 拆分后章标题上移为 H1，内部标题整体上移 (level-1) 级。
    """
    lines = body.split("\n")
    masked_lines = mask_code(body).split("\n")
    heads = iter_headings(mask_code(body))
    cuts = [h for h in heads if h[1] == level]
    if not cuts:
        return []
    supers = [h for h in heads if h[1] < level]

    def series_for(line_no: int) -> str | None:
        cur = None
        for ln, _lv, txt in supers:
            if ln < line_no:
                cur = txt
            else:
                break
        return cur

    chunks: list[tuple[str, str, str | None]] = []
    for i, (ln_no, _lv, txt) in enumerate(cuts):
        if SKIP_SPLIT_TITLES.match(txt):
            continue
        start = ln_no
        end = cuts[i + 1][0] if i + 1 < len(cuts) else len(lines)
        # 首个 chunk 若只是书名页 + 目录，跳过（真题册的结构：书名 H1 后紧跟目录）
        if i == 0 and _is_toc_only("\n".join(lines[start:end])):
            continue
        fixed: list[str] = []
        for cl, ml in zip(lines[start:end], masked_lines[start:end]):
            m = HEADING_LINE_RE.match(ml)
            if m:
                lv = len(m.group(1))
                if lv < level:
                    continue  # 上级标题行（篇）丢弃，已记入 series
                new_lv = max(1, min(6, lv - level + 1))
                fixed.append("#" * new_lv + " " + cl.lstrip("#").strip())
            else:
                fixed.append(cl)
        chunks.append((txt, "\n".join(fixed).rstrip() + "\n", series_for(ln_no)))
    return chunks


def build_toc(title: str, entries: list[tuple[str, str, str | None]],
              *, author: str = DEFAULT_AUTHOR) -> str:
    """生成 Better Export PDF 用的目录笔记（toc: true + 内部链接列表）。"""
    fm = ["---", f"title: {yaml_str(title + ' · 目录')}", f"author: {yaml_str(author)}",
          "cssclasses: [mgw-toc]", "toc: true", "---"]
    lines = fm + ["", f"# {title}", "", "按顺序导出以下章节：", ""]
    last_series = None
    for i, (fname, _t, series) in enumerate(entries, 1):
        if series and series != last_series:
            lines.append(f"**{series}**")
            last_series = series
        lines.append(f"{i}. [[{Path(fname).stem}]]")
    return "\n".join(lines) + "\n"


def safe_filename(name: str, maxlen: int = 60) -> str:
    """把标题转成安全的文件名（去掉路径非法字符）。"""
    s = re.sub(r'[\\/:*?"<>|\r\n\t]', "", name)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s[:maxlen] or "untitled"


# ---------------------------------------------------------------------------
# 主转换
# ---------------------------------------------------------------------------

def convert(src: Path, out_dir: Path, *, title: str | None = None,
            split_level: int | None = None, author: str = DEFAULT_AUTHOR,
            cssclass: str = "mgw-book", tags: list[str] | None = None,
            default_open: bool = True, dry_run: bool = False) -> dict:
    """把一个 md 转成 Obsidian 友好形态；可选按章拆分。返回统计。

    顺序很重要：**先拆、后归一**。
    若先归一（把多余 H1 降为 H2），文档的「篇」会混进拆分点，产出 `02-第一篇…`
    与 `03-一、…` 这种同级错乱的文件名。
    """
    text = src.read_text(encoding="utf-8")
    _fm, body = parse_frontmatter(text)
    stats: dict = {"src": str(src), "out": [], "details_converted": 0,
                   "split": 0, "headings": {}, "bytes_out": 0}

    # 1) 折叠块转 callout（先做，避免 HTML 块干扰后续标题识别）
    body, n_cal = details_to_callout(body, default_open=default_open)
    stats["details_converted"] = n_cal

    # 1b) 压缩连续空行（阅读视图大片留白；代码块内的空行不受影响）
    body = compact_blank_lines(body)

    # 2) 推断书名：显式 title > 第一个 H1 > 文件名
    if not title:
        h1 = [h for h in iter_headings(mask_code(body)) if h[1] == 1]
        title = h1[0][2] if h1 else src.stem

    # dry-run 不得产生任何副作用（含创建目录）
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    if split_level:
        chunks = split_by_level(body, split_level)
        # 首个 chunk 若标题即书名（如「真题下册」），说明它是书名页，跳过。
        # 用归一化比较，因为书名参数（贺银成真题·下册）与文档内 H1（真题下册）写法不同。
        book_norm = _norm_cmp(title)
        if chunks and book_norm:
            head_norm = _norm_cmp(chunks[0][0])
            if head_norm and head_norm in book_norm:
                chunks = chunks[1:]
        if not chunks:
            stats["error"] = f"未找到 H{split_level} 标题，未拆分"
            return stats
        written: list[tuple[str, str, str | None]] = []
        demoted = clamped = 0
        for i, (ctitle, cbody, series) in enumerate(chunks, 1):
            # 分册内部再做一次「单一 H1 + 不跳级」（此时章标题已是 H1）
            cbody, h = normalize_headings(cbody)
            demoted += h.get("demoted", 0)
            clamped += h.get("clamped", 0)
            fname = f"{i:02d}-{safe_filename(ctitle)}.md"
            fm = build_frontmatter(ctitle, author=author, cssclass=cssclass,
                                   tags=tags, series=series)
            content = fm + "\n" + cbody
            written.append((fname, ctitle, series))
            stats["out"].append(str(out_dir / fname))
            stats["bytes_out"] += len(content.encode("utf-8"))
            if not dry_run:
                (out_dir / fname).write_text(content, encoding="utf-8")
        stats["headings"] = {"h1_before": len(chunks), "demoted": demoted, "clamped": clamped}
        toc_name = f"00-{safe_filename(title)}-目录.md"
        toc = build_toc(title, written, author=author)
        stats["out"].insert(0, str(out_dir / toc_name))
        stats["bytes_out"] += len(toc.encode("utf-8"))
        if not dry_run:
            (out_dir / toc_name).write_text(toc, encoding="utf-8")
        stats["split"] = len(written)
    else:
        # 不拆分：整篇做一次归一
        body, hstat = normalize_headings(body)
        stats["headings"] = hstat
        fname = safe_filename(title) + ".md"
        fm = build_frontmatter(title, author=author, cssclass=cssclass, tags=tags)
        content = fm + "\n" + body
        stats["out"].append(str(out_dir / fname))
        stats["bytes_out"] = len(content.encode("utf-8"))
        if not dry_run:
            (out_dir / fname).write_text(content, encoding="utf-8")

    return stats


# ---------------------------------------------------------------------------
# 批量配置
# ---------------------------------------------------------------------------

# (源 md 相对路径, 输出目录, 书名, 拆分级别, cssclass)
BATCH = [
    ("Obsidian产物/_source/讲义上册.md", "Obsidian产物/讲义上册", "贺银成讲义·上册", 2, "mgw-book"),
    ("Obsidian产物/_source/讲义中册.md", "Obsidian产物/讲义中册", "贺银成讲义·中册", 2, "mgw-book"),
    ("Obsidian产物/_source/讲义下册.md", "Obsidian产物/讲义下册", "贺银成讲义·下册", 2, "mgw-book"),
    ("Obsidian产物/_source/真题上册.md", "Obsidian产物/真题上册", "贺银成真题·上册", 1, "mgw-book"),
    ("Obsidian产物/_source/真题下册.md", "Obsidian产物/真题下册", "贺银成真题·下册", 1, "mgw-book"),
]

# 复习手册：不拆分，只落实约定（cssclass 用紧凑排版）
BATCH_HANDOUT = [
    (f"大三下/复习资料/{n}_主复习资料.md", f"Obsidian产物/复习手册/{n}.md",
     f"{n} 高效复习手册", "mgw-handout")
    for n in ["中医学", "中医心理学", "内科学", "医患沟通", "外科学", "神经病学", "精神病学"]
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="把 md 适配 Obsidian 渲染与 PDF 导出")
    ap.add_argument("--src")
    ap.add_argument("--out-dir")
    ap.add_argument("--title")
    ap.add_argument("--split-level", type=int, default=None)
    ap.add_argument("--author", default=DEFAULT_AUTHOR)
    ap.add_argument("--cssclass", default="mgw-book")
    ap.add_argument("--fold", action="store_true", help="callout 默认折叠（默认展开）")
    ap.add_argument("--all", action="store_true", help="批量处理五册 + 七本复习手册")
    ap.add_argument("--books", nargs="*", help="只处理指定册（匹配 --all 清单里的书名关键词）")
    ap.add_argument("--handouts", action="store_true", help="只处理复习手册")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    root = Path(".").resolve()
    jobs: list[tuple] = []
    if args.all or args.handouts:
        jobs += [(str(root / s), str(root / o), t, None, c) for s, o, t, c in BATCH_HANDOUT]
    if args.all or (not args.handouts and not args.src):
        jobs += [(str(root / s), str(root / o), t, lv, c) for s, o, t, lv, c in BATCH]

    if args.books:
        jobs = [j for j in jobs if any(b in j[2] for b in args.books)]

    if args.src:
        jobs = [(str(Path(args.src)), args.out_dir or "Obsidian产物/out",
                 args.title, args.split_level, args.cssclass)]

    if not jobs:
        ap.print_help()
        return 2

    all_stats = []
    total_details = total_split = 0
    for src_s, out_s, title, split_level, cssclass in jobs:
        src = Path(src_s)
        if not src.is_file():
            print(f"  ✘ 源文件不存在: {src}")
            continue
        # 复习手册：源文件本身就是单个文件，输出到目标文件
        if out_s.endswith(".md"):
            out_dir = Path(out_s).parent
            title = title
            st = convert(src, out_dir, title=title, split_level=None,
                         author=args.author, cssclass=cssclass,
                         default_open=not args.fold, dry_run=args.dry_run)
            # 重命名成目标文件名
            if st.get("out") and not args.dry_run:
                produced = Path(st["out"][0])
                want = Path(out_s)
                if produced != want:
                    want.parent.mkdir(parents=True, exist_ok=True)
                    produced.replace(want)
                    st["out"] = [str(want)]
        else:
            st = convert(src, Path(out_s), title=title, split_level=split_level,
                         author=args.author, cssclass=cssclass,
                         default_open=not args.fold, dry_run=args.dry_run)
        st["title"] = title
        all_stats.append(st)
        total_details += st.get("details_converted", 0)
        total_split += st.get("split", 0)
        tag = "（预演）" if args.dry_run else ""
        print(f"  ▸ {title}{tag}")
        print(f"      details→callout {st.get('details_converted', 0)} 处 | "
              f"拆分 {st.get('split', 0)} 个 | 输出 {len(st.get('out', []))} 文件 | "
              f"{st.get('bytes_out', 0) / 1024:.0f} KB")
        h = st.get("headings", {})
        if h:
            print(f"      标题归一：原 H1 {h.get('h1_before', 0)} 个 → 降级 {h.get('demoted', 0)} / "
                  f"修跳级 {h.get('clamped', 0)}")

    print()
    print(f"合计：details→callout {total_details} 处 | 拆分 {total_split} 个文件 | 任务 {len(all_stats)}")

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(all_stats, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        print(f"报告已写入 {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
