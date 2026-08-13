#!/usr/bin/env python3
"""
验证知识库索引页码 + 复习资料附录页码真实性。
用法:
  python verify_page_numbers.py --subject 中医学     # 检查知识库索引
  python verify_page_numbers.py --all                # 检查所有科目索引
  python verify_page_numbers.py --check-appendix 神经病学  # 检查附录占位符
  python verify_page_numbers.py --check-all-appendix # 检查所有附录
"""
import json, sys, argparse, re
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(__file__).parent
MANIFEST = BASE / "知识库素材" / "index_store" / "index_manifest.json"
REVIEW_DIR = BASE / "复习资料"

SUBJECT_TO_CODE = {
    "内科学": "internal-med", "儿科学": "pediatrics", "外科学": "surgery",
    "神经病学": "neurology", "精神病学": "psychiatry",
    "皮肤性病学": "dermatology", "中医学": "tcm", "医患沟通": "doctor-patient",
}


# ──────────────────────────────────────────
# Part 1: 知识库索引页码验证
# ──────────────────────────────────────────

def check(code):
    with open(MANIFEST, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    if code not in manifest:
        return {"code": code, "exists": False, "error": "未索引"}
    m = manifest[code]
    source = m.get("page_number_source", "unknown")
    if source == "n/a":
        return {"code": code, "status": "OK", "note": "无页码引用（贺银成/昭昭类素材）"}
    if m.get("printed_pages_available", False):
        return {"code": code, "status": "OK", "pages": "教材印刷页码"}
    if source == "pdf_raw":
        offset = m.get("estimated_offset")
        return {
            "code": code, "status": "WARN",
            "source": "PDF阅读器页码（旧索引）",
            "estimated_offset": offset,
            "fix": "python 知识库素材/embed_index.py --subject " + m.get("subject","")
        }
    return {"code": code, "status": "UNKNOWN"}


# ──────────────────────────────────────────
# Part 2: 附录页码占位符检测 (HC-10)
# ──────────────────────────────────────────

def find_appendix_table(text):
    """在复习资料中查找「教材知识点页码索引」附录表格，返回 (start_line, rows)"""
    lines = text.split('\n')
    # 查找附录标题
    appendix_start = None
    for i, line in enumerate(lines):
        if re.search(r'教材知识点页码索引|页码索引|附录.*页码', line):
            appendix_start = i
            break

    if appendix_start is None:
        return None, []

    # 提取表格行
    rows = []
    for i in range(appendix_start + 1, min(appendix_start + 50, len(lines))):
        line = lines[i].strip()
        if line.startswith('|') and '---' not in line and '模块' not in line and '核心知识点' not in line:
            cols = [c.strip() for c in line.split('|') if c.strip()]
            if len(cols) >= 3:
                rows.append(cols)

    return appendix_start, rows


def check_appendix_placeholder(subject):
    """检查指定科目的复习资料附录是否存在占位符页码"""
    # 查找文件
    patterns = [
        REVIEW_DIR / f"{subject}_备考复习资料.md",
        REVIEW_DIR / f"{subject}_主复习资料.md",
    ]

    results = []
    for filepath in patterns:
        if not filepath.exists():
            continue

        text = filepath.read_text(encoding='utf-8')
        start_line, rows = find_appendix_table(text)

        if not rows:
            results.append({
                "file": filepath.name,
                "status": "NO_APPENDIX",
                "note": "未找到教材知识点页码索引附录"
            })
            continue

        # 提取页码列（最后一列）
        pages = []
        for row in rows:
            page_col = row[-1] if row else ""
            # 提取数字页码
            m = re.search(r'P(\d+)', page_col, re.IGNORECASE)
            if m:
                pages.append(int(m.group(1)))
            elif re.search(r'[a-zA-Z\u4e00-\u9fff]', page_col):
                pages.append(None)  # 无页码（文字描述）
            else:
                pages.append(None)

        total = len(pages)
        valid_pages = [p for p in pages if p is not None]
        no_page_count = sum(1 for p in pages if p is None)

        if not valid_pages:
            results.append({
                "file": filepath.name,
                "status": "MISSING_ALL",
                "note": "所有模块均无具体页码",
                "total_modules": total,
            })
            continue

        # 统计页码频率
        counter = Counter(valid_pages)
        most_common_page, most_common_count = counter.most_common(1)[0]

        # 判定
        issues = []
        if most_common_count >= total * 0.5 and total >= 3:
            issues.append("PLACEHOLDER_DETECTED")

        if no_page_count > 0:
            issues.append("MISSING_PAGE")

        status = "FAIL" if issues else "OK"
        results.append({
            "file": filepath.name,
            "status": status,
            "issues": issues,
            "total_modules": total,
            "valid_pages": len(valid_pages),
            "no_page_count": no_page_count,
            "most_common": f"P{most_common_page} x{most_common_count}" if most_common_page else None,
            "page_distribution": dict(counter),
        })

    return results


# ──────────────────────────────────────────
# Part 3: 大纲来源页码检测 (HC-11)
# ──────────────────────────────────────────

def check_syllabus_pages(subject):
    """检查备考复习资料中「来源锚点」列是否只写大纲而无教材页码"""
    filepath = REVIEW_DIR / f"{subject}_备考复习资料.md"
    if not filepath.exists():
        return {"file": filepath.name, "status": "NOT_FOUND"}

    text = filepath.read_text(encoding='utf-8')
    lines = text.split('\n')

    missing_entries = []
    total_table_rows = 0

    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped.startswith('|'):
            continue
        if '---' in line_stripped:
            continue
        # 检查是否为考点速记表行（含来源/来源锚点列）
        cols = [c.strip() for c in line_stripped.split('|') if c.strip()]
        if len(cols) < 5:
            continue

        # 跳过表头
        if '知识点' in line_stripped or '序号' in line_stripped:
            continue

        # 取最后一列作为来源锚点
        source_col = cols[-1]
        total_table_rows += 1

        # 检测只写大纲/复习大纲而无页码的情况
        if re.match(r'^(复习大纲|大纲|考纲|考试大纲)$', source_col):
            missing_entries.append({
                "line": i + 1,
                "source": source_col,
                "knowledge_point": cols[1][:30] if len(cols) > 1 else "..."
            })

    if missing_entries:
        return {
            "file": filepath.name,
            "status": "FAIL",
            "issue": "MISSING_TEXTBOOK_PAGE",
            "total_rows": total_table_rows,
            "missing_count": len(missing_entries),
            "examples": missing_entries[:5],
        }
    return {
        "file": filepath.name,
        "status": "OK",
        "total_rows": total_table_rows,
        "note": "所有来源锚点均含教材页码",
    }


def main():
    parser = argparse.ArgumentParser(
        description="验证知识库索引页码 + 复习资料附录页码真实性 + 大纲来源页码检测"
    )
    parser.add_argument("--subject", "-s", help="科目名（检查索引）")
    parser.add_argument("--all", action="store_true", help="检查所有科目索引")
    parser.add_argument("--check-appendix", "-ca", metavar="SUBJECT",
                        help="检查指定科目复习资料的附录占位符页码")
    parser.add_argument("--check-all-appendix", action="store_true",
                        help="检查所有已生成复习资料的附录")
    parser.add_argument("--check-syllabus-pages", "-cs", metavar="SUBJECT",
                        help="检查指定科目备考复习资料中大纲来源是否缺少教材页码 (HC-11)")
    args = parser.parse_args()

    ran_something = False

    # ── 索引检查 ──
    if args.all:
        ran_something = True
        print("═══ 知识库索引页码验证 ═══")
        for name, code in SUBJECT_TO_CODE.items():
            r = check(code)
            status = r.get("status", "?")
            icon = "✓" if status == "OK" else ("⚠️" if status == "WARN" else "✗")
            print(f"  {icon} {name:8s} → {status} {r.get('source', r.get('note',''))}")

    elif args.subject:
        ran_something = True
        code = SUBJECT_TO_CODE.get(args.subject, args.subject)
        r = check(code)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        if r.get("status") == "WARN":
            print(f"\n⚠️ 该科目索引使用 PDF 阅读器页码，非教材印刷页码！")
            if r.get("estimated_offset"):
                print(f"   已知偏移量: {r['estimated_offset']}")
            print(f"   修复: {r['fix']}")

    # ── 附录占位符检查 (HC-10) ──
    if args.check_appendix:
        ran_something = True
        print(f"\n═══ 附录页码占位符检测 (HC-10): {args.check_appendix} ═══")
        results = check_appendix_placeholder(args.check_appendix)
        if not results:
            print(f"  未找到 {args.check_appendix} 的复习资料文件")
        for r in results:
            status = r["status"]
            icon = "✓" if status == "OK" else ("⚠️" if "NO_APPENDIX" in status else "✗")
            print(f"  {icon} {r['file']}: {status}")
            if "issues" in r:
                for issue in r["issues"]:
                    print(f"      → {issue}")
            if r.get("most_common"):
                print(f"      最高频: {r['most_common']} / {r['total_modules']}个模块")
            if r.get("no_page_count", 0) > 0:
                print(f"      无页码模块: {r['no_page_count']}个")
            if "note" in r:
                print(f"      {r['note']}")

    if args.check_all_appendix:
        ran_something = True
        print("\n═══ 全部附录页码占位符检测 (HC-10) ═══")
        for subject in SUBJECT_TO_CODE:
            results = check_appendix_placeholder(subject)
            if results:
                for r in results:
                    status = r["status"]
                    icon = "✓" if status == "OK" else ("⚠️" if "NO_APPENDIX" in status else "✗")
                    extra = ""
                    if r.get("most_common"):
                        extra = f" ({r['most_common']})"
                    print(f"  {icon} {subject:8s} {r['file']}: {status}{extra}")

    # ── 大纲来源页码检测 (HC-11) ──
    if args.check_syllabus_pages:
        ran_something = True
        print(f"\n═══ 大纲来源页码检测 (HC-11): {args.check_syllabus_pages} ═══")
        r = check_syllabus_pages(args.check_syllabus_pages)
        status = r["status"]
        icon = "✓" if status == "OK" else "✗"
        print(f"  {icon} {r['file']}: {status}")
        if status == "FAIL":
            print(f"      共{r['total_rows']}行，其中{r['missing_count']}行缺少教材页码")
            for ex in r.get("examples", []):
                print(f"      L{ex['line']}: 「{ex['source']}」 → {ex['knowledge_point']}")
        elif status == "OK":
            print(f"      {r.get('note', '')} ({r.get('total_rows', 0)}行)")
        elif status == "NOT_FOUND":
            print(f"      未找到文件")

    if not ran_something:
        parser.print_help()


if __name__ == "__main__":
    main()
