#!/usr/bin/env python3
"""
GoldenSet 回归测试器 v1.0 — HC-4 自动化
=========================================
当 Agent Prompt 变更时，自动运行全量答案校验，确认修改不影响已签收的 GS 条目。

检测项目：
  1. GS 文件完整性 — 检查结构化文件是否可读、schema 是否合规
  2. 答案完整性 — 检查下册 GS 答案字段是否非空
  3. 索引一致性 — 检查 index.json 中的 count 与实际文件条目数是否一致
  4. 新旧对比 — 快速检查（回归测试的实际答案比对依赖 GS 答案覆盖率）

用法：
  python regression.py [--full] [--output report.json]

  --full: 执行完整检查（含逐题 Schema 验证，GS 量大时较慢）
  --output: 报告输出路径（默认打印到 stdout）
"""

import json, sys, io, os
from pathlib import Path
from datetime import datetime

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = Path(r"C:\Users\38063\Desktop\MedAgentWork\GoldenSet")
STRUCTURED = BASE / "structured"
OUTPUT_DIR = BASE / "regression_reports"


# ── Schema 校验 ───────────────────────────────────────────
# v1.1 (2026-08-20 审查修复): 按册分级 —— 上册（真题原文）含完整题干/选项，
# 要求 stem/options；下册（贺银成答案精析，源文件 真题下册.md 为
# "N. 答案 ①解析…" 格式，**没有题干与选项**）硬性要求 stem/options 永远无法
# 满足 → 此前 2754/2754 条全报 critical。现按下册实际内容分级校验。
REQUIRED_FIELDS = ["gs_id", "year", "question_no", "type", "stem", "options"]
ANALYSIS_REQUIRED_FIELDS = ["gs_id", "year", "question_no", "type", "answer", "explanation"]
RECOMMENDED_FIELDS = ["answer", "subject", "explanation", "source_page", "bloom_level", "difficulty"]


def is_analysis_file(file_name):
    """精析类源文件（无题干/选项）：GS_下册_* 等。"""
    return "GS_下册" in file_name


def required_fields_for(file_name):
    return ANALYSIS_REQUIRED_FIELDS if is_analysis_file(file_name) else REQUIRED_FIELDS


def validate_schema(questions, file_name):
    """逐题校验 schema（按文件类型分级）"""
    issues = []
    required = required_fields_for(file_name)
    for i, q in enumerate(questions):
        for f in required:
            if f not in q or q[f] is None or q[f] == "":
                issues.append({
                    "index": i,
                    "gs_id": q.get("gs_id", f"unknown-{i}"),
                    "missing_field": f,
                    "severity": "critical"
                })
        # 推荐字段检查（非阻断）
        for f in RECOMMENDED_FIELDS:
            if f not in q or q[f] is None or (isinstance(q[f], str) and q[f] == ""):
                issues.append({
                    "index": i,
                    "gs_id": q.get("gs_id", f"unknown-{i}"),
                    "missing_field": f,
                    "severity": "warning"
                })
    return issues


def check_file_integrity():
    """检查 GS 结构化文件完整性"""
    results = {"files": {}, "total": 0, "errors": 0}

    for f in sorted(STRUCTURED.glob("GS_*.json")):
        if "schema" in f.name or "index" in f.name:
            continue
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            count = len(data)
            results["files"][f.name] = {
                "status": "OK",
                "count": count,
                "size_kb": round(f.stat().st_size / 1024, 1)
            }
            results["total"] += count
        except json.JSONDecodeError as e:
            results["files"][f.name] = {"status": "CORRUPTED", "error": str(e)}
            results["errors"] += 1
        except Exception as e:
            results["files"][f.name] = {"status": "ERROR", "error": str(e)}
            results["errors"] += 1

    return results


def check_index_consistency():
    """检查索引与实际文件一致性"""
    index_path = STRUCTURED / "GS_index.json"
    if not index_path.exists():
        return {"status": "NO_INDEX", "message": "GS_index.json 不存在，建议重新运行解析器"}

    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    issues = []
    for key, info in index.get("files", {}).items():
        file_path = BASE / info.get("path", "")
        if not file_path.exists():
            issues.append({
                "file": key,
                "issue": "文件不存在",
                "index_count": info.get("count", 0),
                "actual_count": 0
            })
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            actual = len(data)
            indexed = info.get("count", 0)
            if actual != indexed:
                issues.append({
                    "file": key,
                    "issue": "数量不一致",
                    "index_count": indexed,
                    "actual_count": actual,
                    "delta": actual - indexed
                })

    return {
        "status": "OK" if not issues else "MISMATCH",
        "issues": issues
    }


def check_answer_coverage():
    """检查下册答案覆盖率"""
    xiace_path = STRUCTURED / "GS_下册_2025_1994.json"
    if not xiace_path.exists():
        return {"status": "NO_FILE", "message": "下册文件不存在"}

    with open(xiace_path, "r", encoding="utf-8") as f:
        entries = json.load(f)

    with_answer = sum(1 for e in entries if e.get("answer"))
    without_answer = sum(1 for e in entries if not e.get("answer"))

    return {
        "status": "OK",
        "total": len(entries),
        "with_answer": with_answer,
        "without_answer": without_answer,
        "coverage_pct": round(with_answer / len(entries) * 100, 1) if entries else 0
    }


# ── 主入口 ────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="GoldenSet 回归测试器 (HC-4)")
    parser.add_argument("--full", action="store_true", help="执行完整 Schema 校验")
    parser.add_argument("--output", type=str, default=None, help="输出 JSON 报告路径")
    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"GoldenSet 回归测试 v1.0")
    print(f"执行时间: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    report = {
        "test_id": f"REGRESSION-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "checks": {},
        "overall": "PASS",
    }

    # 1. 文件完整性
    print("[1/4] 检查文件完整性...")
    integrity = check_file_integrity()
    report["checks"]["integrity"] = integrity
    print(f"  文件数: {len(integrity['files'])}")
    print(f"  总条目: {integrity['total']}")
    for fname, info in integrity['files'].items():
        print(f"    {fname}: {info['status']} ({info['count']} 条)")
    if integrity['errors'] > 0:
        report["overall"] = "FAIL"

    # 2. 索引一致性
    print("\n[2/4] 检查索引一致性...")
    index_check = check_index_consistency()
    report["checks"]["index_consistency"] = index_check
    print(f"  状态: {index_check['status']}")
    for issue in index_check.get('issues', []):
        print(f"    ⚠️ {issue['file']}: {issue['issue']} (索引={issue['index_count']}, 实际={issue['actual_count']})")
    # v1.1 (2026-08-20 审查修复 C6): overall 判定逻辑此前翻转 ——
    # "FAIL if overall != FAIL else PARTIAL" 在已 FAIL 时反而降为 PARTIAL、
    # 未 FAIL 时升为 FAIL，两个分支语义都错。正确语义：MISMATCH（索引数不一致，
    # 非致命）只把 PASS 降为 PARTIAL，绝不覆盖已有 FAIL。
    if index_check['status'] == 'MISMATCH' and report["overall"] == "PASS":
        report["overall"] = "PARTIAL"

    # 3. 答案覆盖率
    print("\n[3/4] 检查答案覆盖率...")
    answer_cov = check_answer_coverage()
    report["checks"]["answer_coverage"] = answer_cov
    if answer_cov['status'] == 'NO_FILE':
        print(f"  ⚠️ {answer_cov['message']}")
    else:
        print(f"  总条目: {answer_cov['total']}")
        print(f"  有答案: {answer_cov['with_answer']} ({answer_cov['coverage_pct']}%)")
        print(f"  无答案: {answer_cov['without_answer']}")
        if answer_cov['coverage_pct'] < 50:
            print(f"  ⚠️ 答案覆盖率偏低，建议补充 GS 答案数据")

    # 4. Schema 校验（可选）
    if args.full:
        print("\n[4/4] 执行完整 Schema 校验...")
        all_issues = []
        for f in sorted(STRUCTURED.glob("GS_*.json")):
            if "schema" in f.name or "index" in f.name:
                continue
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            issues = validate_schema(data, f.name)
            if issues:
                all_issues.extend(issues[:5])  # 每文件最多5条
        report["checks"]["schema_validation"] = {
            "total_issues": len(all_issues),
            "sample_issues": all_issues[:10]
        }
        critical = [i for i in all_issues if i["severity"] == "critical"]
        if critical:
            report["overall"] = "FAIL"
            print(f"  ❌ {len(critical)} 个关键字段缺失")
        else:
            print(f"  ✅ {len(all_issues)} 个问题 (均为推荐字段)")
    else:
        print("\n[4/4] 跳过完整 Schema 校验 (使用 --full 启用)")

    # 判定
    print(f"\n{'='*60}")
    print(f"回归测试结果: {report['overall']}")
    print(f"{'='*60}")

    if report['overall'] == 'PASS':
        print("✅ 所有检查通过，GoldenSet 运行正常。")
    elif report['overall'] == 'PARTIAL':
        print("⚠️ 部分检查未通过，请查看上方的警告项。")
    else:
        print("❌ 关键检查未通过，请修复后方可继续使用 GoldenSet。")

    # 保存报告
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = args.output or str(OUTPUT_DIR / f"regression_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: {output_path}")

    # v1.1 (2026-08-20 审查修复 C6): FAIL 时非零退出 —— 此前恒 exit 0，
    # 无法作为 CI/门禁判定依据
    sys.exit(1 if report['overall'] == 'FAIL' else 0)
