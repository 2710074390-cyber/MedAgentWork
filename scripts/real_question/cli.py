# -*- coding: utf-8 -*-
"""cli.py — 真题检索子系统命令行入口。"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from .answer_recovery import recover_answer
from .check import print_report, run_check
from .planner import build_plan, write_plan
from .schema import dedupe_items, read_jsonl, write_jsonl
from .sources import GS_LOW, build_kaoyan_items, build_zhiyi_items, build_zhiyi_pdf_items

BASE = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUT = BASE / "question_bank" / "real_questions"


def cmd_build(args) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    all_items = []
    stats = {}
    if not args.zhiyi_only:
        kaoyan, ks = build_kaoyan_items()
        all_items.extend(kaoyan)
        stats["kaoyan"] = ks
    if not args.kaoyan_only:
        zhiyi, zs = build_zhiyi_items()
        all_items.extend(zhiyi)
        stats["zhiyi"] = zs
        if not getattr(args, "no_zhiyi_pdf", False):
            zpdf, ps = build_zhiyi_pdf_items()
            all_items.extend(zpdf)
            stats["zhiyi_pdf"] = ps

    kept, removed = dedupe_items(all_items)
    by_source = Counter(x.source for x in kept)
    by_subject = Counter(x.subject for x in kept)
    by_confidence = Counter(x.answer_confidence for x in kept)
    by_source_subject = Counter((x.source, x.subject) for x in kept)

    ky = [x for x in kept if x.source == "kaoyan"]
    zy = [x for x in kept if x.source == "zhiyi"]
    zp = [x for x in kept if x.source == "zhiyi_pdf"]
    n_ky = write_jsonl(out_dir / "kaoyan_items.jsonl", ky)
    n_zy = write_jsonl(out_dir / "zhiyi_items.jsonl", zy)
    n_zp = write_jsonl(out_dir / "zhiyi_pdf_items.jsonl", zp)

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "out_dir": str(out_dir),
        "counts": {"kaoyan": n_ky, "zhiyi": n_zy, "zhiyi_pdf": n_zp,
                   "total": len(kept), "dedup_removed": removed},
        "by_source": dict(by_source),
        "by_confidence": dict(by_confidence),
        "by_subject": dict(by_subject.most_common()),
        "by_source_subject": {f"{s}/{sub}": n for (s, sub), n in sorted(by_source_subject.items())},
        "build_stats": stats,
        "notes": [
            "考研答案仅保留可恢复 high/medium；low 不进入可选池",
            "CMExam test 答案 high；train 答案 medium；train 学科为关键词标注",
            "zhiyi_pdf = 执业医师历年真题扫描册 OCR（印刷答案 high；无答案不入库）",
            "license=public_noncommercial：用户声明仅非商业个人刷题使用",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ 题目索引已生成：{out_dir}")
    print(f"  考研 {n_ky}；执医历年真题 {n_zp}；CMExam {n_zy}；合计 {len(kept)}；去重移除 {removed}")
    print("  学科分布：")
    for subject, n in by_subject.most_common(20):
        print(f"    {subject}: {n}")
    return 0


def cmd_plan(args) -> int:
    plan = build_plan(
        subject=args.subject,
        target=args.target,
        index_dir=args.index_dir,
        keypoints_path=args.keypoints,
        blueprint_path=args.blueprint,
        quota_kaoyan=args.quota_kaoyan,
        quota_zhiyi=args.quota_zhiyi,
        batch=args.batch,
        top_k_per_keypoint=args.top_k,
    )
    out = write_plan(plan, args.out)
    print(f"✅ 选题计划已生成：{out}")
    c = plan["counts"]
    print(f"  目标 {plan['target']}；已选 {c['selected']}（考研 {c['kaoyan']} / 执医 {c['zhiyi']}"
          f" = 历年真题 {c.get('zhiyi_pdf', 0)} + CMExam {c.get('zhiyi_cmexam', 0)}）")
    for source, st in plan["quota_status"].items():
        print(f"  {source}: {st['selected']}/{st['requested']} [{st['status']}]，可用 {st['available']}，"
              f"有效配额 {st['effective_quota']}")
    kp = plan["keypoint_coverage"]
    if kp["total"]:
        print(f"  教师重点：{kp['covered_by_plan']}/{kp['total']}；未覆盖 {len(kp['uncovered'])}")
    return 0


def cmd_check(args) -> int:
    report = run_check(
        file_path=args.file,
        plan_path=args.plan,
        keypoints_path=args.keypoints,
        build=args.build,
        require_ratio=args.require_ratio,
        max_ratio=args.max_ratio,
    )
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"✅ 报告已写入：{out}")
    print_report(report)
    return 0 if report["pass"] else 1


def cmd_recover(args) -> int:
    lower = json.loads(GS_LOW.read_text(encoding="utf-8"))
    out = {}
    stats = Counter()
    for q in lower:
        result = recover_answer(q.get("explanation", ""), raw_answer=q.get("answer"))
        if result.answer:
            stats[result.confidence] += 1
            out[q["gs_id"]] = {
                "gs_id": q["gs_id"],
                "year": q.get("year"),
                "question_no": q.get("question_no"),
                "subject": q.get("subject"),
                "answer_recovered": result.answer,
                "answer_raw_prefix": q.get("answer"),
                "confidence": result.confidence,
                "evidence": result.evidence,
                "method": result.method,
                "explanation": q.get("explanation", ""),
            }
        else:
            stats["unrecovered"] += 1
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ 答案表已写出：{out_path}")
    print(f"  恢复 {len(out)}/{len(lower)}；high {stats['high']}；medium {stats['medium']}；未恢复 {stats['unrecovered']}")
    return 0


def cmd_stats(args) -> int:
    index_dir = Path(args.index_dir)
    items = []
    for name in ("kaoyan_items.jsonl", "zhiyi_pdf_items.jsonl", "zhiyi_items.jsonl"):
        p = index_dir / name
        if p.exists():
            items.extend(read_jsonl(p))
    print(f"题目总数：{len(items)}")
    for (source, subject), n in Counter((x.source, x.subject) for x in items).most_common():
        print(f"  {source:7s} {subject:16s} {n}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="真题检索与双族配额工具（考研 / 执业医师：历年真题 + CMExam）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="构建题目级索引（JSONL）")
    p_build.add_argument("--out-dir", default=str(DEFAULT_OUT))
    p_build.add_argument("--kaoyan-only", action="store_true")
    p_build.add_argument("--zhiyi-only", action="store_true")
    p_build.add_argument("--no-zhiyi-pdf", action="store_true", help="跳过执业医师历年真题索引")
    p_build.set_defaults(func=cmd_build)

    p_plan = sub.add_parser("plan", help="按教师重点/蓝图检索并选题")
    p_plan.add_argument("--subject", required=True)
    p_plan.add_argument("--target", type=int, required=True)
    p_plan.add_argument("--batch", default="")
    p_plan.add_argument("--index-dir", default=str(DEFAULT_OUT))
    p_plan.add_argument("--keypoints", default="")
    p_plan.add_argument("--blueprint", default="")
    p_plan.add_argument("--quota-kaoyan", type=float, default=0.20)
    p_plan.add_argument("--quota-zhiyi", type=float, default=0.20)
    p_plan.add_argument("--top-k", type=int, default=40)
    p_plan.add_argument("--out", required=True)
    p_plan.set_defaults(func=cmd_plan)

    p_check = sub.add_parser("check", help="终审门禁")
    p_check.add_argument("--file", required=True)
    p_check.add_argument("--plan", default="")
    p_check.add_argument("--keypoints", default="")
    p_check.add_argument("--build", default="public", choices=["public", "internal"])
    p_check.add_argument("--require-ratio", type=float, default=0.15)
    p_check.add_argument("--max-ratio", type=float, default=0.25)
    p_check.add_argument("--out", default="")
    p_check.set_defaults(func=cmd_check)

    p_rec = sub.add_parser("recover", help="用扩展规则重算考研答案表")
    p_rec.add_argument("--out", default=str(BASE / "question_bank" / "kaoyan_answers.json"))
    p_rec.set_defaults(func=cmd_recover)

    p_stats = sub.add_parser("stats", help="查看索引分布")
    p_stats.add_argument("--index-dir", default=str(DEFAULT_OUT))
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
