"""
scripts.validate.__main__ — 支持 python -m scripts.validate 运行

用法:
  python -m scripts.validate --batch batch005
  python -m scripts.validate --file path/to/file.json
  python -m scripts.validate --batch batch004 --verbose
  python -m scripts.validate --file x.json --batch-mode          # X1/X2/X6 批次规则（advisory）
  python -m scripts.validate --file x.json --batch-mode --batch-enforce

P2-S3 变更（2026-11-02）：
  - 新增 --batch-mode：批次级 X1/X2/X6 + S-STRUCT 结构覆盖率；
  - --file 模式默认落 `reports/validate/<batch>_structural.json`（AC-P2-02 证据），
    可用 --no-report 关闭。
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from . import validate_file, validate_batch

BASE = Path(__file__).resolve().parent.parent.parent


def _report_stem(path: str) -> str:
    """从路径里取出批次名（如 batch046）；取不到就用文件名。"""
    m = re.search(r'(batch\d{3}[A-Za-z0-9_\-]*)', str(path))
    return m.group(1) if m else Path(path).stem


def _write(p: Path, text: str) -> str:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')
    return str(p)


def _run_batch_mode(path: str, enforce: bool, out_json: str = '', out_md: str = '') -> int:
    from .rules_batch import audit_batch, load_items, render_md

    items = load_items(path)
    rep = audit_batch(items, enforce=enforce)
    rep['path'] = str(path)

    stem = _report_stem(path)
    outdir = BASE / 'reports' / 'validate'
    jp = out_json or str(outdir / f'{stem}_batch_rules.json')
    mp = out_md or str(outdir / f'{stem}_batch_rules.md')
    _write(Path(jp), json.dumps(rep, ensure_ascii=False, indent=2))
    _write(Path(mp), render_md(rep, title=f'{stem} 批次规则回测（{rep["mode"]}）'))

    print(f'批次规则（{rep["mode"]}）: {rep["status"]}  {path}')
    for c in rep['checks']:
        v = c.get('value')
        vs = f'{v:.1%}' if isinstance(v, float) else ''
        print(f'  {c["rule"]:<9} {c["status"]:<9} {c["name"]}  {vs}')
    print(f'  证据: {jp} / {mp}')
    return 1 if rep['status'] == 'FAIL' else 0


def _run_structural(path: str, out: str = '') -> str:
    """结构字段覆盖率单跑并落证据（不参与退出码：历史批次是 SKIP）。"""
    from .rules_batch import check_structural_coverage, load_items

    rep = check_structural_coverage(load_items(path))
    rep['path'] = str(path)
    target = out or str(BASE / 'reports' / 'validate' / f'{_report_stem(path)}_structural.json')
    _write(Path(target), json.dumps(rep, ensure_ascii=False, indent=2))
    return target


def exit_code(summary: dict | None, strict_warn: bool = False) -> int:
    """WARN 不再产生非零退出码（2026-11-03）。

    历史问题：VALID=FAIL=0、仅 WARN 时也 exit 1，自动化脚本会把 WARN 误判成失败。
    需要旧口径时显式传 --strict-warn。
    """
    if not summary:
        return 0
    if int(summary.get('fail', 0) or 0) > 0:
        return 1
    if strict_warn and int(summary.get('warn', 0) or 0) > 0:
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="选项设计机械化校验器 — HC-7 子规则硬编码检测"
    )
    parser.add_argument("--batch", "-b", help="批次ID（如 batch005）")
    parser.add_argument("--file", "-f", help="单个文件路径")
    parser.add_argument("--mode", "-m", choices=['basic', 'full'], default='full',
                        help='校验模式: basic=R1-R9+B1（快速）, full=R1-R9+B1+R10-R13+JS1+S3（完整，默认）')
    parser.add_argument("--verbose", "-v", action="store_true", help="显示通过题目")
    parser.add_argument("--batch-mode", action="store_true",
                        help="额外跑批次级规则 X1/X2/X6 + 结构覆盖率（默认 advisory）")
    parser.add_argument("--batch-enforce", action="store_true",
                        help="批次规则违例即 FAIL（需先完成历史回测与误伤确认）")
    parser.add_argument("--no-report", action="store_true", help="不落 reports/validate 证据文件")
    parser.add_argument("--strict-warn", action="store_true",
                        help="旧口径：出现 WARN 也返回非 0（默认 WARN 不阻断）")
    args = parser.parse_args(argv)

    if not args.batch and not args.file:
        parser.print_help()
        sys.exit(2)

    if args.batch_mode and not args.file:
        print('[FAIL] --batch-mode 目前只支持 --file（需要确定单一产物文件）', file=sys.stderr)
        sys.exit(2)

    exit_status = 0

    if args.file:
        summary = validate_file(args.file, mode=args.mode, verbose=args.verbose)
        exit_status = max(exit_status, exit_code(summary, strict_warn=args.strict_warn))
        if not args.no_report:
            try:
                sp = _run_structural(args.file)
                print(f'  结构字段覆盖证据: {sp}')
            except Exception as exc:  # 证据落盘失败不应改变校验结论
                print(f'  ⚠️ 结构覆盖率证据落盘失败: {exc}', file=sys.stderr)
    elif args.batch:
        summary = validate_batch(args.batch, mode=args.mode, verbose=args.verbose)
        exit_status = max(exit_status, exit_code(summary, strict_warn=args.strict_warn))

    if args.batch_mode and args.file:
        if _run_batch_mode(args.file, enforce=args.batch_enforce) != 0:
            exit_status = 1

    sys.exit(exit_status)


if __name__ == '__main__':
    main()
