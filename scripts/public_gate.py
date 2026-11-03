# -*- coding: utf-8 -*-
"""P8-S3 · 公开闸门（public gate）

把「上公开站的文件里引用了哪些真题」列出来，供人工知情。
**授权（license/cleared）不再作为门禁**（2026-11-03 用户裁定：「全量取消真题限制，不用管授权」）。

历史口径（2026-11-02 起）曾要求真题必须 `license_status=cleared` 才可上站，
导致 376 道真题里 0 道可发布。该限制已取消；本脚本保留 G3 仅作**引用清点**，
状态恒为 INFO，不阻断发布。

检查项
------
- G1 白名单三处一致：`.github/workflows/deploy.yml`、`scripts/deploy_site.ps1`、
  `.assetsignore` 说明段。双通道口径不一致 = 有一条通道在偷偷多传。
- G2 `wrangler.toml` 的 `pages_build_output_dir` 不得指向仓库根（`.`）。
  Git 集成通道直接按它打包，指向根等于整库公开（`.assetsignore` 对 Pages 无效，
  文件自己都写着这句话）。WARN 级：CI 用 `wrangler pages deploy _stage` 显式覆盖，
  但 Git 集成一旦启用就是高危。
- G3 白名单内每个文件，若含任一道真题 qid → 该题的 license_status 必须是 cleared，
  否则 FAIL。
- G4 白名单内文件不得含「题面特征」（无 qid 的裸题面复制粘贴，qid 匹配抓不到）。
- G5 白名单外但可部署的文件（`最终产物/**` 等）仅列清单，不判 FAIL——
  它们不在上传路径里，列出来是为了让「要不要加进白名单」这个决策有据可查。
- G6 线上探测（`--probe`）：请求敏感路径，按 `content_type` 判别。
  Cloudflare Pages 对不存在的路径返回 200 + 首页 HTML，只看状态码会得出相反结论。

用法
----
    python scripts/public_gate.py                       # 静态检查
    python scripts/public_gate.py --probe               # 加线上探测
    python scripts/public_gate.py --json out.json --md out.md
    python scripts/public_gate.py --extra 最终产物       # 模拟把某目录加进白名单
                                                        # （用于验证闸门真的会拦）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent.parent
MATRIX = BASE / "reports" / "compliance" / "license_matrix_20261102.json"
DEPLOY_YML = BASE / ".github" / "workflows" / "deploy.yml"
DEPLOY_PS1 = BASE / "scripts" / "deploy_site.ps1"
ASSETSIGNORE = BASE / ".assetsignore"
WRANGLER = BASE / "wrangler.toml"
SITE = "https://med-review-site.pages.dev"

# 题面特征：题干里出现这些词，且文件不在白名单里出现过 qid 时，提示人工核。
# 只用于 G4 的兜底，宁可多报也不放过裸题面。
STEM_HINTS = (
    "下列哪项", "下列何项", "最佳答案", "参考答案", "正确答案",
    "A.", "B.", "C.", "D.", "E.",
)
SCAN_EXTS = {".html", ".htm", ".md", ".js", ".json", ".txt", ".xml", ".csv"}


# ─────────────────────────── 白名单解析 ───────────────────────────

def parse_deploy_yml(path: Path = DEPLOY_YML) -> list[str]:
    """从 deploy.yml 的 `for it in ...` 行解析白名单条目。"""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    m = re.search(r"for\s+it\s+in\s+([^\n;]+?);\s*do", text)
    if not m:
        return []
    return [t.strip().strip('"').strip("'") for t in m.group(1).split() if t.strip()]


def parse_deploy_ps1(path: Path = DEPLOY_PS1) -> list[str]:
    """从 deploy_site.ps1 的 `foreach ($it in @(...))` 解析白名单条目。"""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    m = re.search(r"foreach\s*\(\s*\$it\s+in\s+@\(([^)]*)\)\s*\)", text)
    if not m:
        return []
    return [t.strip().strip("'").strip('"') for t in m.group(1).split(",") if t.strip()]


def read_pages_output_dir(path: Path = WRANGLER) -> str:
    if not path.exists():
        return ""
    m = re.search(r'^\s*pages_build_output_dir\s*=\s*"([^"]*)"', path.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else ""


def expand_whitelist(entries: list[str], root: Path = BASE) -> list[Path]:
    """把白名单条目展开成文件清单（目录递归）。不存在的条目跳过。"""
    out: list[Path] = []
    for e in entries:
        p = root / e
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            out.extend(sorted(f for f in p.rglob("*") if f.is_file()))
    return out


# ─────────────────────────── license 判定 ───────────────────────────

def derive_status(row: dict) -> str:
    """把 license 字段翻译成闸门口径的三种状态。

    注意：`public*` 是「有声明」不是「有凭证」，所以不是 cleared。
    """
    explicit = str(row.get("license_status") or "").strip().lower()
    if explicit:
        return explicit
    lic = str(row.get("license") or "").strip().lower()
    if lic in ("public", "public_noncommercial"):
        return "declared"
    return "unclear"


def load_matrix(path: Path = MATRIX, prefer_snapshot: bool = False) -> dict:
    """取得题目的 license 状态。

    ⚠️ 为什么默认**现扫**而不是读快照：`reports/` 被 .gitignore 忽略（铁律②
    可重建），CI 的干净 checkout 上根本没有 license_matrix 的 json。若闸门依赖
    它，会拿到空索引 → 白名单里塞满题库也判 PASS，这是假绿。

    现扫复用 `license_matrix.scan()`，与生成 matrix 的是同一份实现，不会漂移。
    """
    if prefer_snapshot and Path(path).exists():
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return {"rows": data.get("rows") or [], "summary": data.get("summary") or {},
                "generated_at": data.get("generated_at"), "source": "snapshot",
                "missing": False, "error": ""}

    try:
        if str(BASE / "scripts") not in sys.path:
            sys.path.insert(0, str(BASE / "scripts"))
        import license_matrix as lm

        files = sorted((BASE / "最终产物").glob("batch*/ALL_questions_FIXED.json"))
        rows, summary = lm.scan(files)
        return {"rows": rows, "summary": summary,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "source": "live-scan", "files": len(files), "missing": False, "error": ""}
    except Exception as exc:  # 扫不出来就必须拦，不能当没有真题
        return {"rows": [], "summary": {}, "source": "failed", "missing": True,
                "error": f"{type(exc).__name__}: {exc}"}


def qid_index(rows: list[dict]) -> dict[str, dict]:
    """qid → {real, status}。只有真题进索引（原创不存在清权问题）。"""
    idx = {}
    for r in rows:
        if not r.get("real"):
            continue
        idx[str(r.get("qid"))] = {
            "real": True,
            "status": derive_status(r),
            "origin_kind": r.get("origin_kind"),
            "license": r.get("license"),
            "file": r.get("file"),
        }
    return idx


# ─────────────────────────── 各项检查 ───────────────────────────

def check_whitelist_consistency(yml: list[str], ps1: list[str]) -> dict:
    a, b = set(yml), set(ps1)
    only_yml, only_ps1 = sorted(a - b), sorted(b - a)
    problems = []
    if not a:
        problems.append("deploy.yml 未解析出白名单（格式变了？闸门失效）")
    if not b:
        problems.append("deploy_site.ps1 未解析出白名单（格式变了？闸门失效）")
    if only_yml:
        problems.append(f"仅 CI 上传：{only_yml}")
    if only_ps1:
        problems.append(f"仅本地上传：{only_ps1}")
    return {
        "id": "G1", "name": "白名单双通道一致",
        "status": "FAIL" if problems else "PASS",
        "entries": sorted(a | b), "problems": problems,
    }


def check_output_dir(pages_dir: str) -> dict:
    root_like = pages_dir.strip() in (".", "./", "")
    note = ""
    if root_like:
        note = ("pages_build_output_dir 指向仓库根：Git 集成通道会整库打包上传，"
                ".assetsignore 对 Pages 无效。CI 用 `wrangler pages deploy _stage` "
                "显式覆盖，故当前线上无暴露；但只要有人启用 Git 集成即整库公开。")
    return {
        "id": "G2", "name": "构建输出目录不得为仓库根",
        "status": "WARN" if root_like else "PASS",
        "value": pages_dir, "note": note,
    }


def check_qid_exposure(files: list[Path], idx: dict[str, dict], root: Path = BASE) -> dict:
    """白名单内文件含真题 qid → 该题必须 cleared。"""
    hits, blocked, cleared = [], [], 0
    for f in files:
        if f.suffix.lower() not in SCAN_EXTS:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        found = re.findall(r"batch\d{3}[_-][A-Za-z0-9]+[_-][A-Za-z0-9]+[_-]\d+", text)
        for qid in dict.fromkeys(found):
            info = idx.get(qid)
            if not info:
                continue  # 原创题，不涉及清权
            rec = {"file": _rel(f, root), "qid": qid, "status": info["status"],
                   "license": info["license"], "origin_kind": info["origin_kind"]}
            if info["status"] == "cleared":
                cleared += 1
            else:
                blocked.append(rec)
            hits.append(rec)
    return {
        "id": "G3", "name": "白名单内真题引用清点（授权不设门禁）",
        # 2026-11-03：用户裁定「不用管授权」——只清点，不阻断。
        "status": "INFO",
        "real_qids_in_whitelist": len(hits),
        "cleared": cleared, "blocked": blocked[:50], "blocked_count": len(blocked),
        "note": "license 仅作来源记录；public/public_noncommercial/unclear 均不再阻断发布。",
    }


def check_bare_stems(files: list[Path], idx: dict[str, dict], root: Path = BASE) -> dict:
    """白名单内文件含题面特征但无 qid → 可能裸复制，qid 匹配抓不到。"""
    notes = []
    for f in files:
        if f.suffix.lower() not in SCAN_EXTS or f.name == "index.html":
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(r"batch\d{3}[_-]", text):
            continue  # 已有 qid，G3 会管
        n = sum(1 for h in STEM_HINTS[:4] if h in text)
        if n >= 2:
            notes.append({"file": _rel(f, root), "hints": n})
    return {
        "id": "G4", "name": "白名单内不得含裸题面",
        "status": "FAIL" if notes else "PASS",
        "suspects": notes,
        "note": "index.html 为站点介绍页，例外；其余文件出现 ≥2 个题面特征且无 qid → 人工核。",
    }


def check_outside_whitelist(idx: dict[str, dict], whitelist: set[str], root: Path = BASE) -> dict:
    """白名单外但要紧的文件清单（不判 FAIL，供决策）。"""
    by_file: dict[str, dict] = {}
    for qid, info in idx.items():
        if info["status"] == "cleared":
            continue
        f = info.get("file") or "?"
        if any(f == w or f.startswith(w.rstrip("/") + "/") for w in whitelist):
            continue
        slot = by_file.setdefault(f, {"file": f, "real": 0, "unclear": 0, "declared": 0,
                                      "origins": {}})
        slot["real"] += 1
        slot["unclear" if info["status"] == "unclear" else "declared"] += 1
        k = info.get("origin_kind") or "?"
        slot["origins"][k] = slot["origins"].get(k, 0) + 1
    rows = sorted(by_file.values(), key=lambda x: -x["real"])
    return {
        "id": "G5", "name": "白名单外未清权真题分布",
        "status": "INFO",
        "file_count": len(rows),
        "question_count": sum(r["real"] for r in rows),
        "top": rows[:15],
        "note": "这些文件不在上传路径里；列出是为了让「是否加进白名单」有据可查。",
    }


def classify_response(ctype: str, head: bytes) -> str:
    """判定一次响应的性质。抽成纯函数，便于零网络单测。

    Pages 的 SPA 兜底：不存在的路径返回 200 + 首页 HTML。所以判据是
    content-type 与正文开头，而不是状态码。
    """
    is_html = "text/html" in (ctype or "").lower()
    if is_html and head.lstrip().startswith(b"<!DOCTYPE html"):
        return "SPA_FALLBACK"
    return "HTML" if is_html else "EXPOSED"


def probe(url: str, path: str, timeout: float = 15.0) -> dict:
    """探测线上路径。判别依据是 content_type + 长度是否等于首页，而非状态码。

    中文路径必须 percent-encode：urllib 不会像 curl 那样替你编码，
    直接用原字符会抛 UnicodeEncodeError（ascii codec），并被误记成 UNREACHABLE。
    """
    full = f"{url.rstrip('/')}/{quote(path.lstrip('/'), safe='/')}"
    try:
        req = urllib.request.Request(full, method="GET",
                                     headers={"User-Agent": "public-gate/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            code = r.status
            ctype = r.headers.get("content-type", "")
            body = r.read(400)
    except urllib.error.HTTPError as e:
        return {"path": path, "status": e.code, "content_type": "", "verdict": "NOT_FOUND",
                "note": "HTTP 错误码"}
    except Exception as exc:  # 网络不可用不算发现，如实标注
        return {"path": path, "status": None, "content_type": "", "verdict": "UNREACHABLE",
                "note": f"{type(exc).__name__}: {exc}"}
    is_html = "text/html" in ctype.lower()
    looks_like_index = is_html and body.lstrip().startswith(b"<!DOCTYPE html")
    verdict = classify_response(ctype, body)
    return {"path": path, "status": code, "content_type": ctype, "verdict": verdict,
            "note": "返回首页 HTML＝路径不存在（Pages SPA 兜底）；EXPOSED 才是真暴露"}


def check_probe(paths: list[str], url: str = SITE) -> dict:
    results = [probe(url, p) for p in paths]
    exposed = [r for r in results if r["verdict"] == "EXPOSED"]
    unreachable = [r for r in results if r["verdict"] == "UNREACHABLE"]
    return {
        "id": "G6", "name": "线上探测",
        "status": "FAIL" if exposed else ("SKIP" if unreachable else "PASS"),
        "url": url, "results": results,
        "note": "SPA_FALLBACK 表示路径 200 但返回的是首页 HTML，即该文件未上线。",
    }


# ─────────────────────────── 汇总 ───────────────────────────

def _rel(p: Path, root: Path = BASE) -> str:
    try:
        return str(p.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def run(extra: list[str] | None = None, do_probe: bool = False,
        url: str = SITE, prefer_snapshot: bool = False) -> dict:
    yml = parse_deploy_yml()
    ps1 = parse_deploy_ps1()
    entries = list(dict.fromkeys(yml + ps1))
    if extra:
        entries = list(dict.fromkeys(entries + list(extra)))
    files = expand_whitelist(entries)

    mx = load_matrix(prefer_snapshot=prefer_snapshot)
    idx = qid_index(mx["rows"])

    checks = []
    if mx.get("missing"):
        # 授权不再作门禁（2026-11-03）：取不到 license 数据只影响 G3 清点，
        # 不影响发布。保留 INFO 留痕，避免把“盘点缺失”误读成“已清权”。
        checks.append({
            "id": "G0", "name": "授权数据可得（仅盘点，不阻断）", "status": "INFO",
            "note": f"无法获取题目 license 状态：{mx.get('error')}",
        })
    checks += [
        check_whitelist_consistency(yml, ps1),
        check_output_dir(read_pages_output_dir()),
        check_qid_exposure(files, idx),
        check_bare_stems(files, idx),
        check_outside_whitelist(idx, set(entries)),
    ]
    if do_probe:
        probe_paths = [
            "最终产物/batch033/内科教学题库.md",
            "scripts/public_gate.py",
            "wrangler.toml",
            ".github/workflows/deploy.yml",
        ]
        checks.append(check_probe(probe_paths, url))

    statuses = {c["status"] for c in checks}
    if "FAIL" in statuses:
        overall = "FAIL"
    elif "WARN" in statuses:
        overall = "WARN"
    else:
        overall = "PASS"

    blocked_total = sum(c.get("blocked_count", 0) for c in checks)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tool": "scripts/public_gate.py",
        "contract": {
            "cleared_only": False,
            "license_gate": "disabled（2026-11-03 用户裁定：不用管授权）",
            "status_mapping": {
                "cleared": "有授权凭证（仅记录）",
                "declared": "有公开使用声明（仅记录）",
                "unclear": "仓库无记录（仅记录）",
            },
            "why_still_report": (
                "授权不再是发布前置条件；保留清点是为了回答“站上引用了哪些真题”，"
                "而不是用它阻断部署。"
            ),
        },
        "whitelist": {"ci": yml, "local": ps1, "effective": entries,
                      "files": len(files)},
        "matrix": {
            "source": _rel(MATRIX), "source_kind": mx.get("source"),
            "files_scanned": mx.get("files"), "error": mx.get("error") or "",
            "generated_at": mx.get("generated_at"),
            "missing": mx.get("missing", False),
            "real_questions": len(idx),
            "cleared": sum(1 for v in idx.values() if v["status"] == "cleared"),
            "declared": sum(1 for v in idx.values() if v["status"] == "declared"),
            "unclear": sum(1 for v in idx.values() if v["status"] == "unclear"),
        },
        "checks": checks,
        "blocked_in_whitelist": blocked_total,
        "public_unclear": blocked_total,
        "status": overall,
    }


def render_md(rep: dict) -> str:
    L = [f"# 公开闸门报告（P8-S3）", "",
         f"- 生成：{rep['generated_at']}",
         f"- 工具：`{rep['tool']}`",
         f"- 结论：**{rep['status']}**　公开路径内未清权真题 **{rep['public_unclear']}** 题",
         "",
         "---", "",
         "## 0. 授权口径（2026-11-03 起）", "",
         f"矩阵里 {rep['matrix']['real_questions']} 道真题：**cleared {rep['matrix']['cleared']}** / "
         f"declared {rep['matrix']['declared']} / unclear {rep['matrix']['unclear']}。",
         "",
         "用户 2026-11-03 明确「全量取消真题限制，不用管授权」：**license 不再是发布门禁**，"
         "只作为来源记录保留。G3 状态恒为 INFO，不阻断部署。",
         "",
         "历史口径（2026-11-02 起）曾要求 cleared 才可上站，当时 376 道真题 0 道 cleared；"
         "该限制已取消，但保留清点数字，避免下一任误读为「全部已清权」。",
         "", "---", "", "## 1. 检查项", "",
         "| 项 | 名称 | 结果 | 关键值 |", "|---|---|---|---|"]

    for c in rep["checks"]:
        if c["id"] == "G0":
            v = c["note"]
        elif c["id"] == "G1":
            v = f"白名单 {len(c['entries'])} 项" + ("" if not c["problems"] else "；" + "；".join(c["problems"]))
        elif c["id"] == "G2":
            v = f"`{c['value'] or '(未配置)'}`"
        elif c["id"] == "G3":
            v = (f"白名单内真题 {c['real_qids_in_whitelist']} 题（仅清点，不阻断）")
        elif c["id"] == "G4":
            v = f"可疑文件 {len(c['suspects'])} 个"
        elif c["id"] == "G5":
            v = f"{c['file_count']} 个文件 / {c['question_count']} 题"
        else:
            exposed = [r for r in c.get("results", []) if r["verdict"] == "EXPOSED"]
            v = f"探测 {len(c.get('results', []))} 条，真暴露 {len(exposed)} 条"
        L.append(f"| {c['id']} | {c['name']} | {c['status']} | {v} |")

    L += ["", "---", "", "## 2. 白名单外的未清权真题（G5）", "",
          "这些文件**不在**上传路径里。列出来是为了让「要不要把它们加进白名单」这个决策有据可查。", "",
          "| 文件 | 真题 | unclear | declared | 来源 |", "|---|---|---|---|---|"]
    g5 = next((c for c in rep["checks"] if c["id"] == "G5"), {"top": []})
    for r in g5["top"]:
        origins = "、".join(f"{k} {v}" for k, v in r["origins"].items())
        L.append(f"| `{r['file']}` | {r['real']} | {r['unclear']} | {r['declared']} | {origins} |")
    if not g5["top"]:
        L.append("| — | 0 | 0 | 0 | — |")

    g2 = next(c for c in rep["checks"] if c["id"] == "G2")
    L += ["", "---", "", "## 3. G2：那条没被触发的风险", ""]
    if g2["status"] == "WARN":
        L += [g2["note"], "",
              "**没有改**。理由：CI 与本地脚本都显式传 `_stage`，命令行参数覆盖该配置，"
              "改动会影响 Cloudflare 控制台侧的 Git 集成构建——那是部署决策，需要人确认。",
              "",
              "若要收口，改法是把 `pages_build_output_dir` 指向一个必须显式组装、默认不存在的目录"
              "（如 `_stage`）：Git 集成构建会因目录不存在而失败，属于安全的失败模式（站点停留在上一个版本），"
              "而不是把整库推上去。"]
    else:
        L.append(f"当前 `pages_build_output_dir = {g2['value']}`，不指向仓库根，无此风险。")

    probed = next((c for c in rep["checks"] if c["id"] == "G6"), None)
    L += ["", "---", "", "## 4. 线上探测" if probed else "## 4. 线上探测（未执行）", ""]
    if probed:
        L += [f"目标：`{probed['url']}`　结果：**{probed['status']}**", "",
              "| 路径 | HTTP | content-type | 判定 |", "|---|---|---|---|"]
        for r in probed["results"]:
            L.append(f"| `/{r['path']}` | {r['status']} | `{r['content_type'] or '—'}` | {r['verdict']} |")
        L += ["", probed["note"], "",
              "**为什么不用状态码判断**：Cloudflare Pages 对不存在的路径返回 `200` + 首页 HTML，"
              "只看状态码会把「文件不存在」读成「文件已上线」，结论正好反过来。"
              "判据是 content-type 是否为 `text/html` 且正文以 `<!DOCTYPE html` 开头。"]
    else:
        L += ["未加 `--probe`，本次只做静态检查。要验证线上，跑：", "",
              "```bash", "python scripts/public_gate.py --probe", "```"]

    L += ["", "---", "", "## 5. 挂进部署链", "",
          "```yaml",
          "      - name: Public gate (fail-closed)",
          "        run: python scripts/public_gate.py",
          "```", "",
          "闸门退出码非 0 时部署中止。但**授权不再触发失败**（2026-11-03 起）：",
          "把 `最终产物/` 加进白名单只会进入 G5 清点，不再因 license 被拦。",
          "仍会失败的是：白名单双通道不一致（G1）、白名单内裸题面（G4）、线上真暴露（G6）。", "",
          "---", "",
          "*本报告只含文件路径、qid 与计数，不含任何用户数据。*"]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P8-S3 公开闸门")
    ap.add_argument("--extra", nargs="*", default=[], help="额外加入白名单的路径（模拟用）")
    ap.add_argument("--probe", action="store_true", help="加线上探测")
    ap.add_argument("--use-matrix-snapshot", action="store_true",
                    help="优先读 reports/compliance/license_matrix_*.json（默认现扫题库，"
                         "因为 reports/ 不进 git，CI 上快照不存在）")
    ap.add_argument("--url", default=SITE)
    ap.add_argument("--json", default=str(BASE / "reports" / "compliance" / "public_gate_20261102.json"))
    ap.add_argument("--md", default=str(BASE / "reports" / "compliance" / "public_gate_20261102.md"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    rep = run(extra=args.extra, do_probe=args.probe, url=args.url,
              prefer_snapshot=args.use_matrix_snapshot)

    if args.json:
        p = Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.md:
        p = Path(args.md)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render_md(rep), encoding="utf-8")

    if not args.quiet:
        icon = {"PASS": "[OK]", "WARN": "[!]", "FAIL": "[X]"}[rep["status"]]
        print(f"{icon} 公开闸门：{rep['status']}")
        for c in rep["checks"]:
            print(f"  {c['status']:5s} {c['id']} {c['name']}")
        m = rep["matrix"]
        print(f"  矩阵：真题 {m['real_questions']} | cleared {m['cleared']} | "
              f"declared {m['declared']} | unclear {m['unclear']}")
        print(f"  公开路径内未清权真题：{rep['public_unclear']}")
        if rep["blocked_in_whitelist"]:
            for c in rep["checks"]:
                for b in (c.get("blocked") or [])[:5]:
                    print(f"    - {b['file']} {b['qid']} ({b['status']})")
    return 0 if rep["status"] != "FAIL" else 1


if __name__ == "__main__":
    sys.exit(main())
