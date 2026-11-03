#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_rules.py — 规则注册表（rules/registry.yaml）的 lint 与渲染器。

为什么有这个脚本（P1-S1/P1-S2）：
    规则此前散落在 SOUL.md、Prompt版本/、validate_options.py、
    check_learning_value.py、gate_check.py、quality_policy.json、pipeline.yaml
    七处，同一条规则被多处改写、编号互相冲突（HC-6/HC-7/HC-18 各被定义 2-3 次），
    且没有任何机制能发现「注册表说有这条规则，代码里却找不到检测器」。

本脚本提供三件事：
    1. lint   —— 机械校验注册表自洽性：ID/别名唯一、hard 规则必须有检测器、
                 detector 指向的函数必须真实存在、同字段不得被反向约束、
                 config_keys 与 pipeline_config/pipeline.yaml 三处取值必须一致。
    2. render —— 把注册表渲染成 SOUL 规则表 / 提示词约束 / thresholds 片段，
                产物先落 reports/registry/rendered/，人工确认后才可写入正式文件。
    3. coverage —— 统计 hard 规则中有机械检测器的比例（AC-P1-03 ≥80%）。

用法::

    python scripts/render_rules.py --check
    python scripts/render_rules.py --check --json reports/registry/lint_20261102.json
    python scripts/render_rules.py --coverage
    python scripts/render_rules.py --write --out-dir reports/registry/rendered

退出码：
    0 = 无 error（warn 允许）
    1 = 存在 error
    2 = 注册表不可读 / 依赖缺失

本脚本只读注册表与代码，不修改任何规则或配置。
"""
from __future__ import annotations
# ── UTF-8 输出兜底（2026-11-03）：Windows 默认 GBK 控制台下 emoji 会抛 UnicodeEncodeError，
#    导致门禁命令“时绿时红”。仅在脚本直接运行时生效，pytest 捕获下跳过。
import sys as _sys
if "pytest" not in _sys.modules and "_pytest" not in _sys.modules:
    for _stream in (_sys.stdout, _sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

import argparse
import ast
import json
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = BASE / "rules" / "registry.yaml"
DEFAULT_OUT = BASE / "reports" / "registry" / "rendered"
EVIDENCE_DIR = BASE / "reports" / "registry"

MECHANICAL = {"python", "command"}
SEVERITIES = {"hard", "soft", "process"}
REQUIRED_RULE_KEYS = {"id", "title", "kind", "severity", "status"}

_ast_cache: dict[str, ast.Module | None] = {}
_text_cache: dict[str, str] = {}


# ── 基础工具 ────────────────────────────────────────────────

def load_registry(path: Path) -> dict:
    """读取注册表。PyYAML 缺失时直接失败，不静默降级。"""
    if not path.exists():
        raise FileNotFoundError(f"注册表不存在: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover - 本机已装 PyYAML
        raise RuntimeError(
            "render_rules.py 需要 PyYAML 读取 rules/registry.yaml"
            "（pip install pyyaml；本机默认环境已具备）"
        ) from exc
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"注册表顶层必须是映射: {path}")
    return data


def _module_ast(rel_path: str) -> ast.Module | None:
    if rel_path in _ast_cache:
        return _ast_cache[rel_path]
    p = BASE / rel_path
    mod = None
    if p.exists() and p.suffix == ".py":
        try:
            mod = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            mod = None
    _ast_cache[rel_path] = mod
    return mod


def _file_text(rel_path: str) -> str:
    if rel_path not in _text_cache:
        p = BASE / rel_path
        _text_cache[rel_path] = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    return _text_cache[rel_path]


def _defined_symbols(rel_path: str) -> set[str]:
    mod = _module_ast(rel_path)
    if mod is None:
        return set()
    return {n.name for n in ast.walk(mod) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def _dig(data, dotted: str):
    """按 a.b.0.c 取嵌套值；取不到返回哨兵 __MISSING__。"""
    cur = data
    for part in dotted.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return "__MISSING__"
        elif isinstance(cur, dict):
            if part not in cur:
                return "__MISSING__"
            cur = cur[part]
        else:
            return "__MISSING__"
    return cur


def _issue(level: str, code: str, rule_id: str, msg: str) -> dict:
    return {"level": level, "code": code, "rule_id": rule_id, "msg": msg}


# ── lint ───────────────────────────────────────────────────

def lint(reg: dict) -> tuple[list[dict], dict]:
    """返回 (issues, stats)。issues 里 level=error 即 lint 不一致项。"""
    issues: list[dict] = []
    rules = reg.get("rules") or []
    sources = reg.get("sources") or {}
    backlog = set(reg.get("semantic_backlog") or [])
    stats = {"rules": len(rules), "hard": 0, "hard_mechanical": 0, "soft": 0, "process": 0}

    # L0 结构完整性
    for i, r in enumerate(rules):
        if not isinstance(r, dict):
            issues.append(_issue("error", "L0_BAD_ENTRY", f"#{i}", "规则条目必须是映射"))
            continue
        missing = REQUIRED_RULE_KEYS - set(r)
        if missing:
            issues.append(_issue("error", "L0_MISSING_KEY", str(r.get("id", f"#{i}")),
                                 f"缺少必填字段: {sorted(missing)}"))
        if r.get("severity") not in SEVERITIES:
            issues.append(_issue("error", "L0_BAD_SEVERITY", str(r.get("id", f"#{i}")),
                                 f"severity 必须是 {sorted(SEVERITIES)}，实际 {r.get('severity')!r}"))

    # L1 ID 唯一
    seen: dict[str, str] = {}
    for r in rules:
        rid = str(r.get("id", ""))
        if not rid:
            continue
        if rid in seen:
            issues.append(_issue("error", "L1_DUP_ID", rid, "规则 ID 重复"))
        seen[rid] = rid

    # L2 别名唯一（含与其它规则 ID 撞名）
    alias_owner: dict[str, str] = {}
    for r in rules:
        rid = str(r.get("id", ""))
        for a in r.get("aliases") or []:
            a = str(a)
            if a in alias_owner and alias_owner[a] != rid:
                issues.append(_issue("error", "L2_DUP_ALIAS", rid,
                                     f"别名 {a!r} 已被 {alias_owner[a]} 占用"))
            alias_owner[a] = rid
            if a in seen and a != rid:
                issues.append(_issue("error", "L2_ALIAS_SHADOWS_ID", rid,
                                     f"别名 {a!r} 与规则 ID {a!r} 撞名"))

    # L3 hard 规则必须有机械检测器（或显式登记进 semantic_backlog）
    for r in rules:
        rid = str(r.get("id", ""))
        sev = r.get("severity")
        det = r.get("detector") or {}
        dtype = det.get("type")
        if sev == "hard":
            stats["hard"] += 1
            if dtype in MECHANICAL:
                stats["hard_mechanical"] += 1
            elif rid not in backlog:
                issues.append(_issue(
                    "error", "L3_HARD_NO_DETECTOR", rid,
                    f"hard 规则没有机械检测器（detector.type={dtype!r}），"
                    "且未登记进 semantic_backlog"))
            else:
                issues.append(_issue(
                    "warn", "L3_HARD_SEMANTIC_BACKLOG", rid,
                    "hard 规则只有语义/人工检测，计入覆盖率缺口"))
        elif sev == "soft":
            stats["soft"] += 1
        elif sev == "process":
            stats["process"] += 1

    # L4 同字段不得被反向约束（min 与 max 未声明配对）
    by_target: dict[str, list[dict]] = {}
    for r in rules:
        t = r.get("target")
        if t:
            by_target.setdefault(str(t), []).append(r)
    for target, group in by_target.items():
        dirs = {str(r.get("direction")) for r in group}
        if "min" in dirs and "max" in dirs:
            ids = [str(r.get("id")) for r in group]
            paired = all(
                any(str(o.get("id")) == str(r.get("range_with")) for o in group if o is not r)
                for r in group if r.get("direction") in {"min", "max"}
            )
            if not paired:
                issues.append(_issue("error", "L4_CONFLICT_DIRECTION", ",".join(ids),
                                     f"字段 {target} 同时被 min/max 约束，但未用 range_with 声明区间"))

    # L5 source_refs 必须可追溯
    for r in rules:
        rid = str(r.get("id", ""))
        for ref in r.get("source_refs") or []:
            ref = str(ref)
            head = ref.split(":")[0].split("#")[0].strip()
            if head in sources:
                continue
            if (BASE / head).exists():
                continue
            issues.append(_issue("error", "L5_UNKNOWN_SOURCE", rid, f"source_refs 无法追溯: {ref!r}"))

    # L6 detector 必须真实存在
    for r in rules:
        rid = str(r.get("id", ""))
        det = r.get("detector") or {}
        dtype = det.get("type")
        if dtype == "python":
            f = str(det.get("file", ""))
            sym = str(det.get("symbol", ""))
            if not (BASE / f).exists():
                issues.append(_issue("error", "L6_DETECTOR_FILE_MISSING", rid, f"检测器文件不存在: {f}"))
                continue
            if sym and sym not in _defined_symbols(f):
                issues.append(_issue("error", "L6_DETECTOR_SYMBOL_MISSING", rid,
                                     f"{f} 中找不到符号 {sym!r}"))
            tag = det.get("tag")
            if tag:
                text = _file_text(f)
                if f'"{tag}"' not in text and f"'{tag}'" not in text:
                    issues.append(_issue("error", "L6_DETECTOR_TAG_MISSING", rid,
                                         f"{f} 中找不到规则标签字面量 {tag!r}"))
        elif dtype == "command":
            cmd = str(det.get("cmd", ""))
            parts = [p for p in cmd.split() if p and not p.startswith("-")]
            script = next((p for p in parts[1:] if p.endswith((".py", ".mjs", ".js"))), None)
            if script and not (BASE / script).exists():
                issues.append(_issue("error", "L6_DETECTOR_CMD_MISSING", rid,
                                     f"command 检测器引用的脚本不存在: {script}"))
        elif dtype == "semantic":
            if not det.get("reviewer"):
                issues.append(_issue("error", "L6_SEMANTIC_NO_REVIEWER", rid,
                                     "semantic 检测器必须声明 reviewer（谁来做人工判定）"))
        elif dtype is not None:
            issues.append(_issue("error", "L6_BAD_DETECTOR_TYPE", rid, f"未知 detector.type: {dtype!r}"))

    # L7 / L8 配置三处一致：registry.config_keys ↔ pipeline_config.DEFAULTS ↔ pipeline.yaml
    cfg_keys = reg.get("config_keys") or []
    defaults, yaml_doc = _load_config_sources(issues)
    if defaults is not None:
        for item in cfg_keys:
            key = str(item.get("key", ""))
            want = item.get("default")
            got = defaults.get(key, "__MISSING__")
            if got == "__MISSING__":
                issues.append(_issue("error", "L7_KEY_NOT_LOADED", key,
                                     "config_keys 声明的键不在 pipeline_config.DEFAULTS 中"))
            elif not _same(want, got):
                issues.append(_issue("error", "L7_CONFIG_DRIFT", key,
                                     f"注册表 default={want!r} 与 pipeline_config.DEFAULTS={got!r} 不一致"))
    if isinstance(yaml_doc, dict):
        declared = {str(i.get("key")): i for i in cfg_keys}
        for key, item in declared.items():
            probe = item.get("yaml_probe")
            want = item.get("default")
            if probe:
                got = _dig(yaml_doc, str(probe))
                if got == "__MISSING__":
                    issues.append(_issue("error", "L8_PROBE_MISSING", key,
                                         f"yaml_probe 路径不存在: {probe}"))
                elif not _same(want, got) and not item.get("allow_mismatch"):
                    issues.append(_issue("error", "L8_PROBE_MISMATCH", key,
                                         f"注册表 default={want!r} 与 pipeline.yaml[{probe}]={got!r} 不一致"))
            in_yaml = _dig(yaml_doc, f"thresholds.{key}")
            if in_yaml != "__MISSING__" and not _same(want, in_yaml):
                issues.append(_issue("error", "L8_YAML_MISMATCH", key,
                                     f"注册表 default={want!r} 与 pipeline.yaml thresholds.{key}={in_yaml!r} 不一致"))

    # L9 policy_bindings 引用必须可解析
    bindings = reg.get("policy_bindings") or {}
    cmds = bindings.get("check_commands") or {}
    rule_ids = seen
    for name, spec in cmds.items():
        if not isinstance(spec, dict):
            issues.append(_issue("error", "L9_BAD_BINDING", str(name), "check_commands 条目必须是映射"))
            continue
        rule_ref = spec.get("rule")
        if rule_ref and str(rule_ref) not in rule_ids:
            issues.append(_issue("error", "L9_UNKNOWN_RULE_REF", str(name),
                                 f"绑定的规则 {rule_ref!r} 不存在"))
        cmd = str(spec.get("cmd", ""))
        parts = [p for p in cmd.split() if p and not p.startswith("-")]
        script = next((p for p in parts[1:] if p.endswith((".py", ".mjs", ".js"))), None)
        if script and not (BASE / script).exists():
            issues.append(_issue("error", "L9_BINDING_CMD_MISSING", str(name),
                                 f"命令引用的脚本不存在: {script}"))
        sym = spec.get("symbol")
        if sym and ":" in str(sym):
            f, fn = str(sym).split(":", 1)
            if not (BASE / f).exists():
                issues.append(_issue("error", "L9_BINDING_FILE_MISSING", str(name), f"文件不存在: {f}"))
            elif fn not in _defined_symbols(f):
                issues.append(_issue("error", "L9_BINDING_SYMBOL_MISSING", str(name), f"{f} 中找不到 {fn!r}"))
    for prof, names in (bindings.get("profiles") or {}).items():
        for n in names or []:
            if str(n) not in cmds:
                issues.append(_issue("error", "L9_PROFILE_UNKNOWN_CHECK", str(prof),
                                     f"profile 引用了未定义的检查项 {n!r}"))

    return issues, stats


def _same(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 1e-12
    return a == b


def _load_config_sources(issues: list[dict]):
    """读取 pipeline_config.DEFAULTS 与 pipeline.yaml 全文档。失败不抛异常。"""
    defaults = None
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("_pc", BASE / "scripts" / "pipeline_config.py")
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            d = getattr(mod, "DEFAULTS", None)
            if isinstance(d, dict):
                defaults = d
    except Exception as exc:  # pragma: no cover
        issues.append(_issue("warn", "L7_CONFIG_UNREADABLE", "pipeline_config",
                             f"无法导入 pipeline_config.DEFAULTS: {exc}"))
    yaml_doc = None
    p = BASE / "scripts" / "pipeline.yaml"
    if p.exists():
        try:
            import yaml  # type: ignore

            yaml_doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover
            issues.append(_issue("warn", "L8_YAML_UNREADABLE", "pipeline.yaml", f"无法解析: {exc}"))
    return defaults, yaml_doc


# ── 覆盖率 / 渲染 ───────────────────────────────────────────

def coverage(reg: dict) -> dict:
    rules = [r for r in (reg.get("rules") or []) if isinstance(r, dict)]
    hard = [r for r in rules if r.get("severity") == "hard"]
    mech = [r for r in hard if (r.get("detector") or {}).get("type") in MECHANICAL]
    ratio = (len(mech) / len(hard)) if hard else 1.0
    gaps = [str(r.get("id")) for r in hard if (r.get("detector") or {}).get("type") not in MECHANICAL]
    return {"hard_total": len(hard), "hard_with_detector": len(mech),
            "ratio": round(ratio, 4), "gaps": gaps}


def render(reg: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rules = [r for r in (reg.get("rules") or []) if isinstance(r, dict)]
    written: list[Path] = []

    index = out_dir / "rule_index.json"
    index.write_text(json.dumps({
        "registry_version": reg.get("registry_version"),
        "updated_at": reg.get("updated_at"),
        "rule_count": len(rules),
        "rules": rules,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    written.append(index)

    lines = ["# 规则一览（由 rules/registry.yaml 渲染，请勿手改）", "",
             f"registry_version: {reg.get('registry_version')}　渲染时间：{datetime.now():%Y-%m-%d %H:%M}", "",
             "| ID | 别名 | 级别 | 类型 | 检测器 | 说明 |", "|---|---|---|---|---|---|"]
    for r in rules:
        det = r.get("detector") or {}
        if det.get("type") == "python":
            d = f"`{det.get('file')}::{det.get('symbol')}`" + (f" [{det.get('tag')}]" if det.get("tag") else "")
        elif det.get("type") == "command":
            d = f"`{det.get('cmd')}`"
        elif det.get("type") == "semantic":
            d = f"人工（{det.get('reviewer', '未指定')}）"
        else:
            d = "—"
        lines.append(f"| {r.get('id')} | {', '.join(map(str, r.get('aliases') or [])) or '—'} | "
                     f"{r.get('severity')} | {r.get('kind')} | {d} | {str(r.get('title', '')).replace('|', '/')} |")
    p = out_dir / "rules_table.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    written.append(p)

    hard = [r for r in rules if r.get("severity") == "hard"]
    pl = ["# 提示词可引用的硬约束清单（渲染产物，人工确认后再并入提示词）", ""]
    for r in hard:
        extra = ""
        if r.get("target"):
            extra = f"（字段 `{r.get('target')}` {r.get('direction')}）"
        pl.append(f"- **{r.get('id')}** {r.get('title')}{extra}")
        if r.get("notes"):
            pl.append(f"  - {r.get('notes')}")
    p = out_dir / "prompt_constraints.md"
    p.write_text("\n".join(pl) + "\n", encoding="utf-8")
    written.append(p)

    tl = ["# 由 rules/registry.yaml 渲染的 thresholds 段（候选值，需人工确认后写入 pipeline.yaml）",
          "# 全部取值 = 当前运行时实际生效值（pipeline_config.DEFAULTS），写入后行为零变化。",
          "thresholds:"]
    for item in reg.get("config_keys") or []:
        tl.append(f"  {item.get('key')}: {item.get('default')}"
                  + (f"   # {item.get('note')}" if item.get("note") else ""))
    p = out_dir / "config_thresholds.yaml"
    p.write_text("\n".join(tl) + "\n", encoding="utf-8")
    written.append(p)
    return written


def write_coverage_md(reg: dict, cov: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# 硬规则检测器覆盖率", "",
             f"- 生成时间：{datetime.now():%Y-%m-%d %H:%M}",
             f"- 注册表版本：{reg.get('registry_version')}",
             f"- hard 规则数：**{cov['hard_total']}**",
             f"- 有机械检测器：**{cov['hard_with_detector']}**",
             f"- 覆盖率：**{cov['ratio'] * 100:.1f}%**（AC-P1-03 要求 ≥80%）", ""]
    if cov["gaps"]:
        lines += ["## 未覆盖（仅有语义/人工判定）", ""]
        lines += [f"- {g}" for g in cov["gaps"]]
    else:
        lines += ["## 未覆盖", "", "无。"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── CLI ────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="规则注册表 lint / 渲染 / 覆盖率（P1-S2）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
               "  python scripts/render_rules.py --check\n"
               "  python scripts/render_rules.py --coverage\n"
               "  python scripts/render_rules.py --write\n")
    ap.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="注册表路径")
    ap.add_argument("--check", action="store_true", help="只做 lint 校验（不写渲染产物）")
    ap.add_argument("--write", action="store_true", help="渲染规则表/提示词约束/thresholds 片段")
    ap.add_argument("--coverage", action="store_true", help="输出硬规则检测器覆盖率")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT), help="渲染产物目录")
    ap.add_argument("--json", default="", help="lint 证据 JSON 输出路径（默认 reports/registry/lint_<日期>.json）")
    ap.add_argument("--no-evidence", action="store_true", help="不写证据文件")
    ap.add_argument("--quiet", action="store_true", help="只输出结论")
    args = ap.parse_args(argv)

    if not (args.check or args.write or args.coverage):
        args.check = True

    try:
        reg = load_registry(Path(args.registry))
    except Exception as exc:
        print(f"[FAIL] 注册表不可读: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    issues, stats = lint(reg)
    errors = [i for i in issues if i["level"] == "error"]
    warns = [i for i in issues if i["level"] == "warn"]
    cov = coverage(reg)

    if not args.quiet:
        print(f"注册表: {args.registry}")
        print(f"规则数: {stats['rules']}  hard={stats['hard']}  soft={stats['soft']}  process={stats['process']}")
        print(f"硬规则检测器覆盖率: {cov['hard_with_detector']}/{cov['hard_total']} = {cov['ratio'] * 100:.1f}%")
        for i in errors:
            print(f"  ✗ [{i['code']}] {i['rule_id']}: {i['msg']}")
        for i in warns:
            print(f"  ⚠ [{i['code']}] {i['rule_id']}: {i['msg']}")
        if not errors and not warns:
            print("  ✓ lint 全部通过")

    if args.check and not args.no_evidence:
        out = Path(args.json) if args.json else EVIDENCE_DIR / f"lint_{datetime.now():%Y%m%d}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "registry": str(args.registry),
            "registry_version": reg.get("registry_version"),
            "stats": stats,
            "coverage": cov,
            "error_count": len(errors),
            "warn_count": len(warns),
            "issues": issues,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"  📄 证据: {out}")

    if args.coverage:
        p = EVIDENCE_DIR / f"coverage_{datetime.now():%Y%m%d}.md"
        write_coverage_md(reg, cov, p)
        if not args.quiet:
            print(f"  📄 覆盖率报告: {p}")

    if args.write:
        written = render(reg, Path(args.out_dir))
        if not args.quiet:
            for w in written:
                print(f"  ✎ {w}")

    if errors:
        if not args.quiet:
            print(f"\n[FAIL] lint 不一致项 {len(errors)} 个（warn {len(warns)} 个）")
        return 1
    if not args.quiet:
        print(f"\n[PASS] lint 无不一致项（warn {len(warns)} 个）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
