#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""host_bootstrap.py — 三宿主入口生成器（DSH / WorkBuddy / Trae）

要解决的问题
------------
规则正文都在仓库里，但**每个宿主只认自己的加载路径**：

| 宿主 | 自动加载什么 | 不做什么就会怎样 |
|---|---|---|
| DSH（DeepSeek Harness） | 仓库根 `AGENTS.md` + `.dsh/skills/<name>/SKILL.md` | 原生支持，无需生成 |
| WorkBuddy（腾讯） | 项目级 `.workbuddy/skills/<name>/SKILL.md` 或用户级 `~/.workbuddy/skills/<name>/SKILL.md` | 仓库里的 `.dsh/skills` **不会被它自动加载** |
| Trae（字节） | 项目级 `.trae/rules/*.md`（front-matter `alwaysApply: true`） | 没有规则文件 = 每次都要人贴规则 |

路径核实（2026-11-05）：
- Trae 官方文档：项目规则 = 项目路径下 `.trae/rules/`（front-matter `alwaysApply`）。
- WorkBuddy：官方指南明确「用户级 `~/.workbuddy/skills/`、项目级 <项目>/.workbuddy/skills/，
  文件结构就一个 SKILL.md」；本机实测用户目录 `~/.workbuddy/skills/{humanize-writing-zh,pdfkit-py}/SKILL.md`。
- 默认装**项目级**（随仓库入库、CI 可校验、换机器零步骤），用户级用 `--scope user|both` 追加。

设计：单一真源 + 路由桩
------------------------
- **真源**：`AGENTS.md`（规则路由与四条硬约束）与 `.dsh/skills/*/SKILL.md`（正文）。
- **桩**：WorkBuddy / Trae 只放**路由占位文件**，正文让 Agent 按路径直读，避免「三份规则漂移」。
- **防漂移**：每个桩里写源文件 `sha256`；源改了而桩没重生成 → `check` 判 `STALE`（exit 1）。
- **H4（2026-11-07）**：桩标记行升级 `v2`，额外写 `level=` 能力等级（L2/L1/L0），
  **不写 front-matter**——宿主不认识这个 YAML 键，塞进去是未经验证的兼容假设。
  `check` 校验 level 存在且合法，并检测 WorkBuddy「项目级 / 用户级同名桩不同步」的
  `SCOPE_CONFLICT`（WARN，不阻断；裁决为项目级优先）。
  角色如何按 level 执行，见 `batch_driver.py` 的 handoff bundle 与 `AGENTS.md` §3.5。
- **不静默覆盖**：目标文件不是本脚本写的（没有 MARKER）→ 拒绝覆盖 / 拒绝删除，需 `--force`。

命令
----
    python scripts/host_bootstrap.py check                       # 三宿主是否就绪（exit 0 才继续）
    python scripts/host_bootstrap.py install                     # 生成 WorkBuddy + Trae 入口
    python scripts/host_bootstrap.py install --dry-run           # 只看会写什么
    python scripts/host_bootstrap.py uninstall                   # 只删本脚本写的桩
    python scripts/host_bootstrap.py check --hosts dsh,trae      # 只查某几个宿主

退出码：check 0=全就绪 / 1=有缺失或过期 / 2=参数/环境错误
职责边界：只生成路由桩，不复制规则正文、不改 SKILL、不写 workflow_state。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SKILLS_DIR = ".dsh/skills"
AGENTS_NAME = "AGENTS.md"
TRAE_RULE_NAME = "medagentwork-gate.md"
STUB_VERSION = "v2"
MARKER = "medagentwork-host-stub"
# H4：能力等级写在 MARKER 行（不写 front-matter，避免宿主对未知 YAML 键的兼容风险）。
# L2=可派生隔离子代理 / L1=单会话顺序执行 / L0=纯手工接力。
HOST_LEVEL = {"dsh": "L2", "workbuddy": "L2", "trae": "L1"}
VALID_LEVELS = ("L0", "L1", "L2")


# ── 基础 ────────────────────────────────────────────────
def sha256_text(path) -> str:
    """源文件的「换行归一」哈希（CRLF / LF 同值）。

    为什么不用裸字节哈希：桩是提交进仓库的，Windows 检出是 CRLF、CI（Linux）是 LF，
    裸字节哈希会在 CI 上判成 STALE。这里只归一 `\r\n` → `\n`，仍能发现真实内容改动。
    注意：**门禁回执（gate_stamp）必须用裸字节哈希**，那是「产物字节绑定」，不能归一。
    """
    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def rel(path, base: Path) -> str:
    try:
        return Path(path).resolve().relative_to(Path(base).resolve()).as_posix()
    except Exception:
        return Path(path).as_posix()


def front_matter(path):
    """解析 `---` 包裹的 YAML 头（只取顶层 key: value，够用即可）。"""
    text = Path(path).read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[3:end].strip("\n").splitlines():
        if ":" not in line or line.startswith((" ", "\t", "#")):
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, text[end + 4:].lstrip("\n")


def skills(base: Path = BASE):
    """枚举 canonical skills（`.dsh/skills/<name>/SKILL.md`）。"""
    root = Path(base) / SKILLS_DIR
    out = []
    if not root.is_dir():
        return out
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        f = d / "SKILL.md"
        if not f.is_file():
            continue
        meta, _body = front_matter(f)
        out.append({
            "name": d.name,
            "file": f,
            "rel": rel(f, base),
            "sha256": sha256_text(f),
            "description": meta.get("description") or f"{d.name}（MedAgentWork）",
        })
    return out


SCOPES = ("project", "user", "both")


def workbuddy_skills_dir(base: Path, home, scope: str = "project") -> Path:
    """WorkBuddy 技能目录：project=<仓库>/.workbuddy/skills，user=~/.workbuddy/skills。"""
    return (Path(base) if scope == "project" else Path(home)) / ".workbuddy" / "skills"


def trae_rules_dir(base: Path) -> Path:
    return Path(base) / ".trae" / "rules"


# ── 桩内容 ──────────────────────────────────────────────
def marker_line(source_rel: str, sha: str, level: str) -> str:
    return f"<!-- {MARKER} {STUB_VERSION} source={source_rel} sha256={sha} level={level} -->"


def workbuddy_stub(skill, level: str) -> str:
    return (
        "---\n"
        f"name: {skill['name']}\n"
        f"description: {json.dumps(skill['description'], ensure_ascii=False)}\n"
        "---\n"
        f"{marker_line(skill['rel'], skill['sha256'], level)}\n"
        f"# {skill['name']}（宿主路由占位，勿手改）\n\n"
        "本文件**只做路由**，不是规则正文；规则正文在仓库里：\n\n"
        f"1. 先读仓库根 `{AGENTS_NAME}`（唯一入口：§1 读什么 / §2 四条硬约束 / §3 四个自检命令 / §5 推 main 走 PR）。\n"
        f"2. 再按路径直读 `{skill['rel']}`（正文，按需读，不要整份读 SOUL.md / CONTEXT.md）。\n"
        "3. 硬约束由**脚本**判定（batch_driver / gate_stamp / gate_audit），与提示词无关：\n"
        "   跳过门禁 → 下游 preflight 拒收；改产物不重跑 → ARTIFACT_MISMATCH；未入库 → CI 红。\n"
        "4. 动手前自检：`python scripts/host_bootstrap.py check`（exit 0 才继续）。\n"
        f"5. 宿主能力 `level={level}`：下游阶段按 `中间产物/{{batch}}/_handoff/{{stage}}.json` 执行"
        "（L2 派生隔离子代理 / L1 同会话顺序执行、每阶段重读 `_ctx.md` / L0 用 `batch_driver.py brief`）。"
        "交接包不含工具名，三种方式产出的门禁回执是同一份字节。\n\n"
        "重新生成：`python scripts/host_bootstrap.py install --hosts workbuddy`\n"
    )


def trae_rule(agents_sha: str, level: str) -> str:
    return (
        "---\n"
        "description: MedAgentWork 批次门禁与防跳过硬约束（始终生效；由 scripts/host_bootstrap.py 生成）\n"
        "alwaysApply: true\n"
        "---\n"
        f"{marker_line(AGENTS_NAME, agents_sha, level)}\n"
        "# MedAgentWork · 项目规则（路由，勿手改）\n\n"
        f"本文件只做路由，规则正文在仓库 `{AGENTS_NAME}` 与 `.dsh/skills/`。\n\n"
        f"1. **先读 `{AGENTS_NAME}`**：§1 决定读哪个角色 SKILL；§2 四条硬约束；§3 四个自检命令；§4 不要做的事；§5 推 main 走 PR。\n"
        "2. 角色 SKILL 正文按路径直读：`.dsh/skills/medmaster/SKILL.md`、`medbatch`、`medgen`、`medqc`、`medfix`、`medreview`。\n"
        "3. 这四条**不是纪律，是脚本判定**：\n"
        "   - 门禁只能 `python scripts/batch_driver.py check --batch <id> --stage auto`（唯一执行面）\n"
        "   - 产物与门禁执行字节绑定：改产物不重跑 → `ARTIFACT_MISMATCH`；伪造回执 → `CHAIN_BROKEN`\n"
        "   - 消费上游前先验回执：`python scripts/gate_verify.py --batch <id> --stage <阶段> --quiet`\n"
        "   - 提交前：`python scripts/gate_audit.py --staged --require-tracked`（hook 已装；该命令等价）\n"
        "4. 动手前自检：`python scripts/host_bootstrap.py check`（exit 0 才继续）。\n"
        f"5. 宿主能力 `level={level}`：本宿主按 L1 顺序执行 —— 每阶段读 "
        "`中间产物/{batch}/_handoff/{stage}.json`，先重读 `_ctx.md` 复位上下文，再按 `inputs[].read` 限定的范围直读；"
        "不派生子代理、不并发写 `write_scope=question_bank` 的阶段。\n\n"
        "重新生成：`python scripts/host_bootstrap.py install --hosts trae`\n"
    )


# ── 目标计划 ────────────────────────────────────────────
def plan(hosts, base: Path = BASE, home=None, scope: str = "project", level: str | None = None):
    """返回 [{host, name, path, content, source_rel, sha256, level}]。"""
    base, home = Path(base), Path(home or Path.home())
    out = []
    if "trae" in hosts:
        agents = base / AGENTS_NAME
        if agents.is_file():
            lv = level or HOST_LEVEL["trae"]
            agents_sha = sha256_text(agents)
            out.append({"host": "trae", "name": TRAE_RULE_NAME,
                        "path": trae_rules_dir(base) / TRAE_RULE_NAME,
                        "content": trae_rule(agents_sha, lv),
                        "source_rel": AGENTS_NAME, "sha256": agents_sha, "level": lv})
    if "workbuddy" in hosts:
        lv = level or HOST_LEVEL["workbuddy"]
        scopes = ["project", "user"] if scope == "both" else [scope]
        for sc in scopes:
            for skill in skills(base):
                out.append({"host": "workbuddy", "scope": sc, "name": skill["name"],
                            "path": workbuddy_skills_dir(base, home, sc) / skill["name"] / "SKILL.md",
                            "content": workbuddy_stub(skill, lv),
                            "source_rel": skill["rel"], "sha256": skill["sha256"], "level": lv})
    return out


def is_ours(path: Path) -> bool:
    try:
        return MARKER in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def stub_sha(path: Path):
    """从桩的 MARKER 行里取源 sha256（取不到返回 None）。"""
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if MARKER in line and "sha256=" in line:
                return line.split("sha256=", 1)[1].split()[0].rstrip("->").strip()
    except OSError:
        return None
    return None


def stub_level(path: Path):
    """从桩的 MARKER 行取 level=；v1 桩没有该字段 → None。"""
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if MARKER in line and "level=" in line:
                return line.split("level=", 1)[1].split()[0].rstrip("->").strip()
    except OSError:
        return None
    return None


# ── check ───────────────────────────────────────────────
def _dsh_entry(base: Path):
    entries = []
    found = skills(base)
    for skill in found:
        name = front_matter(skill["file"])[0].get("name")
        status = "PASS" if name == skill["name"] else "STALE"
        entries.append({"name": skill["name"], "path": skill["rel"], "status": status,
                        "detail": "front-matter name 与目录一致" if status == "PASS"
                                  else f"front-matter name={name!r} ≠ 目录名"})
    agents = Path(base) / AGENTS_NAME
    entries.append({"name": AGENTS_NAME, "path": AGENTS_NAME,
                    "status": "PASS" if agents.is_file() else "MISSING",
                    "detail": "仓库根入口存在" if agents.is_file() else "缺 AGENTS.md（唯一入口）"})
    if not found:
        entries.insert(0, {"name": SKILLS_DIR, "path": SKILLS_DIR, "status": "MISSING",
                           "detail": "没有 canonical skills 目录"})
    return entries


def check(hosts, base: Path = BASE, home=None, scope: str = "project", level: str | None = None):
    base, home = Path(base), Path(home or Path.home())
    report = {"generated_at": datetime.now().isoformat(timespec="seconds"),
              "base": str(base), "home": str(home), "hosts": []}
    for host in hosts:
        lv = level or HOST_LEVEL.get(host, "L1")
        if host == "dsh":
            entries = _dsh_entry(base)
        else:
            entries = []
            for item in plan([host], base, home, scope, level):
                p = item["path"]
                if not p.exists():
                    entries.append({"name": item["name"], "path": rel(p, base) if str(p).startswith(str(base)) else str(p),
                                    "status": "MISSING", "detail": "未生成（跑 install --hosts " + host + "）"})
                elif not is_ours(p):
                    entries.append({"name": item["name"], "path": str(p), "status": "FOREIGN",
                                    "detail": "目标文件不是本脚本生成的，拒绝判定/覆盖"})
                elif stub_sha(p) != item["sha256"]:
                    entries.append({"name": item["name"], "path": str(p), "status": "STALE",
                                    "detail": f"源已变更（{item['source_rel']}）：重跑 install --hosts {host}"})
                elif stub_level(p) not in VALID_LEVELS:
                    entries.append({"name": item["name"], "path": str(p), "status": "LEVEL_MISSING",
                                    "detail": "v1 桩缺 level= 声明：重跑 install 升级到 v2"})
                elif stub_level(p) != item["level"]:
                    entries.append({"name": item["name"], "path": str(p), "status": "LEVEL_MISMATCH",
                                    "detail": f"level={stub_level(p)} ≠ 期望 {item['level']}：重跑 install"})
                else:
                    entries.append({"name": item["name"], "path": str(p), "status": "PASS",
                                    "detail": f"与 {item['source_rel']} 同步 · level={stub_level(p)}"})
            # SCOPE_CONFLICT：项目级与用户级同名桩内容/等级不一致 → 静默漂移（只告警，不阻断）
            if host == "workbuddy":
                for skill in skills(base):
                    up = workbuddy_skills_dir(base, home, "user") / skill["name"] / "SKILL.md"
                    pp = workbuddy_skills_dir(base, home, "project") / skill["name"] / "SKILL.md"
                    if up.is_file() and pp.is_file() and (
                            stub_sha(up) != stub_sha(pp) or stub_level(up) != stub_level(pp)):
                        entries.append({"name": f"{skill['name']}@user", "path": str(up),
                                        "status": "WARN",
                                        "detail": "SCOPE_CONFLICT：项目级与用户级同名桩不同步，项目级优先；"
                                                  "修复 `uninstall --hosts workbuddy --scope user`"})
        blocking = [e for e in entries if e["status"] in
                    ("MISSING", "STALE", "FOREIGN", "LEVEL_MISSING", "LEVEL_MISMATCH")]
        warns = [e for e in entries if e["status"] == "WARN"]
        summary = f"{len(entries) - len(blocking)}/{len(entries)} 就绪"
        if warns:
            summary += f"（{len(warns)} 条 WARN）"
        report["hosts"].append({
            "host": host,
            "level": lv,
            "verdict": "FAIL" if blocking else "PASS",
            "summary": summary,
            "entries": entries,
        })
    report["summary"] = {"pass": sum(1 for h in report["hosts"] if h["verdict"] == "PASS"),
                         "fail": sum(1 for h in report["hosts"] if h["verdict"] != "PASS"),
                         "hosts": len(report["hosts"])}
    return report


# ── install / uninstall ─────────────────────────────────
def install(hosts, base: Path = BASE, home=None, dry_run=False, force=False,
            scope: str = "project", level: str | None = None):
    base, home = Path(base), Path(home or Path.home())
    result = {"generated_at": datetime.now().isoformat(timespec="seconds"),
              "dry_run": dry_run, "written": [], "unchanged": [], "skipped": [], "error": None}
    for item in plan(hosts, base, home, scope, level):
        p, content = item["path"], item["content"]
        if p.exists() and not is_ours(p) and not force:
            result["skipped"].append({"path": str(p), "reason": "foreign",
                                      "detail": "已有非本脚本文件，拒绝覆盖（确认后再 --force）"})
            continue
        if p.exists() and p.read_text(encoding="utf-8", errors="replace") == content:
            result["unchanged"].append(str(p))
            continue
        if dry_run:
            result["written"].append({"path": str(p), "action": "create" if not p.exists() else "update"})
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(content, encoding="utf-8", newline="\n")
        os.replace(str(tmp), str(p))
        result["written"].append({"path": str(p), "action": "create" if not p.exists() else "update"})
    if result["skipped"]:
        result["error"] = f"{len(result['skipped'])} 个目标被他方占用，未覆盖"
    return result


def uninstall(hosts, base: Path = BASE, home=None, dry_run=False, scope: str = "project",
              level: str | None = None):
    base, home = Path(base), Path(home or Path.home())
    result = {"dry_run": dry_run, "removed": [], "skipped": [], "error": None}
    for item in plan(hosts, base, home, scope, level):
        p = item["path"]
        if not p.exists():
            continue
        if not is_ours(p):
            result["skipped"].append({"path": str(p), "reason": "foreign"})
            continue
        if dry_run:
            result["removed"].append(str(p))
            continue
        p.unlink()
        try:  # 顺手清掉空目录（不递归，避免误删）
            if p.parent.name and not any(p.parent.iterdir()):
                p.parent.rmdir()
        except OSError:
            pass
        result["removed"].append(str(p))
    return result


# ── CLI ─────────────────────────────────────────────────
def _parse_hosts(value):
    hosts = [h.strip() for h in str(value or "").split(",") if h.strip()]
    unknown = [h for h in hosts if h not in ("dsh", "workbuddy", "trae")]
    if unknown:
        return None, f"未知宿主 {unknown}（可选 dsh, workbuddy, trae）"
    return hosts or ["dsh", "workbuddy", "trae"], None


def main(argv=None) -> int:
    for _s in (sys.stdout, sys.stderr):  # Windows 控制台 GBK 兜底
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="三宿主入口生成器（DSH / WorkBuddy / Trae）")
    ap.add_argument("action", choices=["check", "install", "uninstall"])
    ap.add_argument("--hosts", default="dsh,workbuddy,trae", help="逗号分隔：dsh,workbuddy,trae")
    ap.add_argument("--base", default=None, help="仓库根（默认脚本所在仓库；测试用）")
    ap.add_argument("--home", default=None, help="用户主目录（默认 Path.home()；测试用）")
    ap.add_argument("--scope", default="project", choices=list(SCOPES),
                    help="WorkBuddy 技能位置：project=仓库内(默认，入库) / user=用户目录 / both")
    ap.add_argument("--dry-run", action="store_true", help="只显示会写/删什么")
    ap.add_argument("--force", action="store_true", help="install 时覆盖非本脚本生成的文件")
    ap.add_argument("--level", default=None, choices=list(VALID_LEVELS),
                    help="覆盖所有指定宿主的 level 声明（默认 dsh/workbuddy=L2、trae=L1）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    base = Path(args.base).resolve() if args.base else BASE
    if not base.is_dir():
        print(f"[ERROR] --base 不是目录：{base}", file=sys.stderr)
        return 2
    home = Path(args.home).resolve() if args.home else Path.home()
    hosts, err = _parse_hosts(args.hosts)
    if err:
        print(f"[ERROR] {err}", file=sys.stderr)
        return 2

    if args.action == "check":
        report = check(hosts, base, home, args.scope, args.level)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"宿主入口自检（base={base} ｜ home={home}）")
            for h in report["hosts"]:
                icon = "✅" if h["verdict"] == "PASS" else "🛑"
                print(f"  {icon} [{h['host']}] {h['level']} {h['verdict']} {h['summary']}")
                for e in h["entries"]:
                    if e["status"] != "PASS":
                        tag = "⚠️ " if e["status"] == "WARN" else "   - "
                        print(f"       {tag}{e['name']}: {e['status']} {e['detail']}")
            print(f"合计：PASS {report['summary']['pass']} / FAIL {report['summary']['fail']}")
            if report["summary"]["fail"]:
                print("  ↳ 修复: python scripts/host_bootstrap.py install")
        return 0 if report["summary"]["fail"] == 0 else 1

    if args.action == "install":
        result = install(hosts, base, home, dry_run=args.dry_run, force=args.force,
                         scope=args.scope, level=args.level)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            prefix = "[dry-run] " if args.dry_run else ""
            for w in result["written"]:
                print(f"{prefix}{w['action']}: {w['path']}")
            for u in result["unchanged"]:
                print(f"unchanged: {u}")
            for s in result["skipped"]:
                print(f"skipped: {s['path']}（{s['detail']}）")
            if not result["written"] and not result["skipped"]:
                print("所有入口已是最新")
        return 0 if result["error"] is None else 1

    result = uninstall(hosts, base, home, dry_run=args.dry_run, scope=args.scope,
                       level=args.level)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        prefix = "[dry-run] " if args.dry_run else ""
        for r in result["removed"]:
            print(f"{prefix}removed: {r}")
        for s in result["skipped"]:
            print(f"skipped（非本脚本生成）: {s['path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
