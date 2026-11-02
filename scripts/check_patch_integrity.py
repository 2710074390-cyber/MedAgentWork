#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_patch_integrity.py — 修复闭环的 Patch 契约与 Diff 审计（P5-S2 / P5-S3）。

为什么有这个脚本：
    MedFix 的 patch 长期是「整题覆盖写」，没有任何机制能证明
    「这一版到底改了哪几个字段」「有没有顺手改掉答案或真题原文」。
    batch014 的教训（只打补丁到聚合文件、源文件不溯源）就是这么来的；
    batch046 的 A2→A4 更是**内容零变化**却被当作「已修复」交付。

本脚本做四件事（无用户数据，只处理题目/规则/哈希）：
    1. immutable 断言 —— answer / 真题题干与答案 / HC-20 引文等字段一旦变化即 FAIL；
    2. diff 审计      —— 声明字段 vs 实际变化字段，未声明的变化即拒收；
    3. no-op 检测     —— 声称修复但 diff 为空（含整文件哈希相同）；
    4. 修复统计       —— 规则级 修复成功率 / 复发率（复用 validate 引擎）。

用法::

    # 不可变字段 + diff 审计（证据同时写 JSON 与 Markdown）
    python scripts/check_patch_integrity.py \
        --before 中间产物/batch045/ALL_questions_pilot_draft.json \
        --after  中间产物/batch045/ALL_questions_pilot_revised_v5.json \
        --tag batch045 --json reports/repair/immutable_check_20261102.json

    # 带声明文件的严格 diff 审计（声明哪些字段允许改）
    python scripts/check_patch_integrity.py --before A.json --after B.json \
        --declared declared.json

    # no-op 检测
    python scripts/check_patch_integrity.py --before A.json --after A.json --noop

    # 修复统计（跑 R1–R13 + R14–R19）
    python scripts/check_patch_integrity.py --before A.json --after B.json --stats

退出码：0 = 无违例；1 = 存在 immutable 违例 / 未声明变化；2 = 输入不可读。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / 'scripts'))

# ── Patch 契约 ──────────────────────────────────────────────

#: 允许被 patch 修改的字段（白名单）
ALLOWED_FIELDS = frozenset({
    'stem', 'options', 'explanation', 'learning_value', 'option_polarities',
    'difficulty', 'bloom', 'concepts', 'review_status', 'topic', 'module_name',
    'distractors', 'explanation_v2',
})

#: 永远不可变（答案、锚定引文、溯源、契约字段）
IMMUTABLE_FIELDS = frozenset({
    'id', 'answer', 'answer_key', 'correct_answer',
    'teacher_anchor', 'source_anchors', 'source_page', 'keypoint_ref',
    'kaoyan_origin', 'license', 'schema_version', 'type', 'module', 'polarity',
})

#: 真题标记字段（命中则题干/答案一并 immutable）
REAL_QUESTION_KEYS = ('kaoyan_origin', 'real_question', 'is_real', 'source_type')
REAL_QUESTION_MARKERS = ('[源:考研真题', '[源：考研真题', '真题引用', '真题改编')

#: 既不在白名单也不在 immutable 的字段（新增字段需显式登记）
UNCLASSIFIED_POLICY = 'reject'   # reject | warn


def _sha256_path(path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _norm(v):
    """容器做 canonical 序列化后比较，避免 dict 顺序造成假 diff。"""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, sort_keys=True)
    return v


def is_real_question(q: dict) -> bool:
    if not isinstance(q, dict):
        return False
    for k in REAL_QUESTION_KEYS:
        if q.get(k):
            return True
    blob = f"{q.get('stem', '')}{q.get('explanation', '')}"
    return any(m in blob for m in REAL_QUESTION_MARKERS)


def load_items(path) -> list:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(data, dict):
        for key in ('questions', 'items', 'data'):
            if isinstance(data.get(key), list):
                return data[key]
        raise ValueError(f'{path}: 顶层对象不含 questions/items 数组')
    if not isinstance(data, list):
        raise ValueError(f'{path}: 顶层必须是数组')
    return data


def index_by_id(items: list) -> dict:
    out, dup = {}, []
    for i, q in enumerate(items):
        if not isinstance(q, dict):
            continue
        qid = str(q.get('id') or q.get('question_id') or f'#{i}')
        if qid in out:
            dup.append(qid)
        out[qid] = q
    return out, dup


def changed_fields(before: dict, after: dict) -> list[str]:
    keys = set(before) | set(after)
    return sorted(k for k in keys if _norm(before.get(k)) != _norm(after.get(k)))


# ── 核心审计 ───────────────────────────────────────────────

def audit(before_path, after_path, declared: dict | None = None, tag: str = '') -> dict:
    before_items = load_items(before_path)
    after_items = load_items(after_path)
    b_idx, b_dup = index_by_id(before_items)
    a_idx, a_dup = index_by_id(after_items)

    added = sorted(set(a_idx) - set(b_idx))
    removed = sorted(set(b_idx) - set(a_idx))

    records = []
    violations = []
    undeclared = []
    unclassified = []

    for qid in sorted(set(b_idx) & set(a_idx)):
        b, a = b_idx[qid], a_idx[qid]
        fields = changed_fields(b, a)
        real = is_real_question(b) or is_real_question(a)
        immutable_hit = [f for f in fields if f in IMMUTABLE_FIELDS]
        if real and 'stem' in fields:
            immutable_hit.append('stem(真题题干)')
        # 真题答案另有一层保护（答案字段已 immutable，这里只为报告口径）
        if real and ('answer' in immutable_hit or 'answer_key' in immutable_hit):
            immutable_hit.append('answer(真题答案)')

        allowed_hit = [f for f in fields if f in ALLOWED_FIELDS]
        other = [f for f in fields
                 if f not in IMMUTABLE_FIELDS and f not in ALLOWED_FIELDS and f != 'stem']
        if other:
            unclassified.append({'id': qid, 'fields': other})

        decl = None
        if declared is not None:
            decl = sorted(declared.get(qid, []))
            extra = [f for f in fields if f not in decl and f not in immutable_hit]
            if extra:
                undeclared.append({'id': qid, 'fields': extra, 'declared': decl})

        records.append({
            'id': qid,
            'is_real_question': real,
            'changed_fields': fields,
            'immutable_violations': immutable_hit,
            'allowed_changes': allowed_hit,
            'declared_fields': decl,
            'sha256_before': _sha256_of_item(b),
            'sha256_after': _sha256_of_item(a),
        })
        if immutable_hit:
            violations.append({'id': qid, 'fields': immutable_hit})

    changed_records = [r for r in records if r['changed_fields']]
    report = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'tag': tag,
        'before': {'path': str(before_path), 'items': len(before_items),
                   'sha256': _sha256_path(before_path)},
        'after': {'path': str(after_path), 'items': len(after_items),
                  'sha256': _sha256_path(after_path)},
        'file_identical': _sha256_path(before_path) == _sha256_path(after_path),
        'declared_mode': declared is not None,
        'counts': {
            'added': len(added), 'removed': len(removed),
            'unchanged': len(records) - len(changed_records),
            'changed': len(changed_records),
            'items_patched': len(changed_records) + len(added),
            'immutable_violations': len(violations),
            'undeclared_changes': len(undeclared),
            'unclassified_fields': len(unclassified),
        },
        'added_ids': added, 'removed_ids': removed,
        'duplicate_ids': sorted(set(b_dup) | set(a_dup)),
        'violations': violations,
        'undeclared': undeclared,
        'unclassified': unclassified,
        'records': records,
    }
    report['result'] = 'FAIL' if (violations or undeclared
                                   or (unclassified and UNCLASSIFIED_POLICY == 'reject')) else 'PASS'
    return report


def _sha256_of_item(q: dict) -> str:
    blob = json.dumps(q, ensure_ascii=False, sort_keys=True).encode('utf-8')
    return hashlib.sha256(blob).hexdigest()


# ── no-op 检测（P5-S5 的最小实现，供 AC-P5-04 出证据）────────

def detect_noop(report: dict) -> dict:
    """找出「声称修复、实际零变化」的 patch。

    判定：文件级 sha256 相同 → 整批 no-op；
          或 patch 里逐题 before==after（records 中 changed_fields 为空且未新增）。
    """
    noop_ids = [r['id'] for r in report['records'] if not r['changed_fields']]
    file_noop = report['file_identical']
    status = 'NOOP' if (file_noop or not report['counts']['changed']) else 'EFFECTIVE'
    return {
        'status': status,
        'file_identical': file_noop,
        'changed_items': report['counts']['changed'],
        'added_items': report['counts']['added'],
        'noop_items': noop_ids if not file_noop else [],
        'verdict': ('整批内容与上一版完全一致（哈希相同），属 no-op 修复，应转 REGENERATE 或人工复核'
                    if file_noop else
                    ('本批无任何题目发生变化，属 no-op 修复' if not report['counts']['changed']
                     else f'{report["counts"]["changed"]} 题发生变化，补丁有效')),
    }


# ── 修复统计（AC-P5-05）─────────────────────────────────────

def _rule_issues(path) -> tuple[dict, dict]:
    """对一版题库跑 R1–R13 + B1 + JS1 + S3，返回 ({qid: {(rule, detail): severity}}, summary)。

    注意：题目在磁盘上是 `options=[{label,text,is_correct}]` 的形态，
    而校验器要 `options={label: text}`。这里统一走 `scripts.validate.parsers.parse_json_file`
    做投影（与 validate_options.py 的入口完全一致），不自己另造一套转换。
    """
    from scripts.validate.engine import validate_questions
    from scripts.validate.parsers import parse_json_file

    items = parse_json_file(str(path))
    by_q, summary = validate_questions(items, mode='full')
    out = {}
    for qid, issues in (by_q or {}).items():
        bucket = {}
        for it in issues or []:
            if not isinstance(it, dict):
                continue
            # 只按 rule 归并，不按 detail：同一规则换了措辞仍是同一个问题，
            # 否则「改个字就算修好」，成功率会被系统性夸大。
            key = str(it.get('rule', '?'))
            sev = str(it.get('severity', 'WARN')).upper()
            if key not in bucket or sev == 'FAIL':
                bucket[key] = sev
        out[str(qid)] = bucket
    return out, summary


def repair_stats(before_path, after_path) -> dict:
    """修复成功率 / 复发率。

    定义（明确写死，避免口径漂移）：
      - 修复成功率 = 已消除问题数 / (已消除 + 仍存在) ，只看 before 里存在的问题；
      - 复发率     = 修复后又出现的同类问题（after 有、before 该题也有的同 rule）占 after 全部问题的比例；
      - 新引入率   = after 新增（before 该题没有该 rule）问题 / after 全部问题。
    """
    b_items = load_items(before_path)
    a_items = load_items(after_path)
    b_idx, _ = index_by_id(b_items)
    a_idx, _ = index_by_id(a_items)

    b_issues, b_sum = _rule_issues(before_path)
    a_issues, a_sum = _rule_issues(after_path)

    fixed = persist = new = 0
    per_rule = {}
    per_sev = {s: {'fixed': 0, 'persist': 0, 'new': 0} for s in ('FAIL', 'WARN')}
    for qid, b in b_issues.items():
        a = a_issues.get(qid, {})
        for rule, sev in b.items():
            sev = 'FAIL' if sev == 'FAIL' else 'WARN'
            per_rule.setdefault(rule, {'fixed': 0, 'persist': 0, 'new': 0})
            if rule in a:
                persist += 1
                per_rule[rule]['persist'] += 1
                per_sev[sev]['persist'] += 1
            else:
                fixed += 1
                per_rule[rule]['fixed'] += 1
                per_sev[sev]['fixed'] += 1
    for qid, a in a_issues.items():
        b = b_issues.get(qid, {})
        for rule, sev in a.items():
            if rule not in b:
                sev = 'FAIL' if sev == 'FAIL' else 'WARN'
                new += 1
                per_rule.setdefault(rule, {'fixed': 0, 'persist': 0, 'new': 0})
                per_rule[rule]['new'] += 1
                per_sev[sev]['new'] += 1

    total_before = sum(len(v) for v in b_issues.values())
    total_after = sum(len(v) for v in a_issues.values())
    touched = fixed + persist
    success = (fixed / touched) if touched else 1.0
    recurrence = (new / total_after) if total_after else 0.0
    sev_rates = {}
    for s, d in per_sev.items():
        t = d['fixed'] + d['persist']
        sev_rates[s] = {
            'fixed': d['fixed'], 'persist': d['persist'], 'new': d['new'],
            'repair_success_rate': round((d['fixed'] / t) if t else 1.0, 4),
        }

    return {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'before': {'path': str(before_path), 'items': len(b_items), 'issues': total_before,
                   'fail': (b_sum or {}).get('fail'), 'warn': (b_sum or {}).get('warn')},
        'after': {'path': str(after_path), 'items': len(a_items), 'issues': total_after,
                  'fail': (a_sum or {}).get('fail'), 'warn': (a_sum or {}).get('warn')},
        'fixed': fixed, 'persist': persist, 'new_or_recurring': new,
        'repair_success_rate': round(success, 4),
        'recurrence_rate': round(recurrence, 4),
        'per_severity': sev_rates,
        'per_rule': per_rule,
        'definitions': {
            'repair_success_rate': '已消除问题 / (已消除 + 仍存在)，分母仅含 before 存在的问题；按 rule 归并（不按 detail）',
            'recurrence_rate': 'after 中出现、该题 before 没有的 rule 问题 / after 全部问题',
            'ac_scope': 'AC-P5-05 的 90% 口径取 per_severity.FAIL.repair_success_rate（WARN 不要求全修）',
        },
    }


# ── 报告渲染 ───────────────────────────────────────────────

def render_md(reports: list[dict]) -> str:
    lines = ['# Patch Diff 审计报告', '',
             f'生成时间：{datetime.now():%Y-%m-%d %H:%M}', '',
             '> 本报告由 `scripts/check_patch_integrity.py` 生成：只统计题目/字段/哈希，不含任何用户数据。', '']
    for r in reports:
        c = r['counts']
        lines += [f"## {r['tag'] or '未命名'}：{Path(r['before']['path']).name} → {Path(r['after']['path']).name}", '',
                  f"- 文件哈希：before `{r['before']['sha256'][:16]}` / after `{r['after']['sha256'][:16]}"
                  f"　{'**完全相同**' if r['file_identical'] else '不同'}",
                  f"- 题量：{r['before']['items']} → {r['after']['items']}",
                  f"- 新增 {c['added']} / 删除 {c['removed']} / 变更 {c['changed']} / 未变 {c['unchanged']}",
                  f"- 不可变字段违例：**{c['immutable_violations']}**",
                  f"- 未声明变化：{c['undeclared_changes']}　未分类字段：{c['unclassified_fields']}",
                  f"- 结论：**{r['result']}**", '']
        if r['violations']:
            lines += ['### 不可变字段违例', '', '| 题目 | 被改字段 |', '|---|---|']
            lines += [f"| {v['id']} | {', '.join(v['fields'])} |" for v in r['violations'][:50]]
            lines.append('')
        changed = [rec for rec in r['records'] if rec['changed_fields']]
        if changed:
            lines += ['### 变更明细（声明字段 ≠ 实际字段时以实际为准）', '',
                      '| 题目 | 实际变更字段 | 声明字段 | 真题 |', '|---|---|---|---|']
            for rec in changed[:100]:
                decl = ', '.join(rec['declared_fields']) if rec['declared_fields'] is not None else '—（未提供声明）'
                lines.append(f"| {rec['id']} | {', '.join(rec['changed_fields'])} | {decl} | "
                             f"{'是' if rec['is_real_question'] else '否'} |")
            if len(changed) > 100:
                lines.append(f'| … | 其余 {len(changed) - 100} 条见 JSON | | |')
            lines.append('')
        if r['added_ids']:
            lines += [f"- 新增题目：{', '.join(r['added_ids'][:20])}"
                      + ('…' if len(r['added_ids']) > 20 else ''), '']
    return '\n'.join(lines) + '\n'


# ── CLI ────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description='Patch 契约与 Diff 审计（P5-S2/S3）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='示例:\n'
               '  python scripts/check_patch_integrity.py --before A.json --after B.json --tag batch045\n'
               '  python scripts/check_patch_integrity.py --before A.json --after A.json --noop\n'
               '  python scripts/check_patch_integrity.py --before A.json --after B.json --stats\n')
    ap.add_argument('--before', required=True, help='修复前题库 JSON')
    ap.add_argument('--after', required=True, help='修复后题库 JSON')
    ap.add_argument('--declared', default='', help='声明文件：{"题目ID": ["允许变更字段", ...]}')
    ap.add_argument('--tag', default='', help='标签（批次/版本）')
    ap.add_argument('--json', default='', help='JSON 证据输出路径')
    ap.add_argument('--md', default='', help='Markdown diff 报告输出路径')
    ap.add_argument('--noop', action='store_true', help='只做 no-op 检测')
    ap.add_argument('--stats', action='store_true', help='计算修复成功率/复发率')
    ap.add_argument('--quiet', action='store_true', help='只输出结论')
    args = ap.parse_args(argv)

    try:
        declared = json.loads(Path(args.declared).read_text(encoding='utf-8')) if args.declared else None
    except Exception as e:
        print(f'[FAIL] 声明文件不可读: {e}', file=sys.stderr)
        return 2

    try:
        report = audit(args.before, args.after, declared=declared, tag=args.tag)
    except Exception as e:
        print(f'[FAIL] {type(e).__name__}: {e}', file=sys.stderr)
        return 2

    if args.noop:
        report['noop'] = detect_noop(report)
        # no-op 不得算 PASS：声称修复却零变化，必须阻断而不是默默放行
        if report['noop']['status'] == 'NOOP' and report['result'] == 'PASS':
            report['result'] = 'NOOP'
    if args.stats:
        try:
            report['repair_stats'] = repair_stats(args.before, args.after)
        except Exception as e:
            report['repair_stats'] = {'error': f'{type(e).__name__}: {e}'}

    if not args.quiet:
        c = report['counts']
        print(f"审计 {args.tag or ''}: {Path(args.before).name} → {Path(args.after).name}")
        print(f"  题量 {report['before']['items']} → {report['after']['items']}"
              f"　新增 {c['added']} / 删除 {c['removed']} / 变更 {c['changed']} / 未变 {c['unchanged']}")
        print(f"  不可变违例 {c['immutable_violations']}　未声明变化 {c['undeclared_changes']}"
              f"　未分类字段 {c['unclassified_fields']}")
        if report['file_identical']:
            print('  ⚠ 文件哈希完全相同 → no-op 修复')
        for v in report['violations'][:10]:
            print(f"  ✗ {v['id']}: 改了不可变字段 {v['fields']}")
        for u in report['undeclared'][:10]:
            print(f"  ✗ {u['id']}: 未声明变化 {u['fields']}（声明 {u['declared']}）")
        if 'noop' in report:
            print(f"  no-op 判定: {report['noop']['status']} — {report['noop']['verdict']}")
        if 'repair_stats' in report and 'error' not in report['repair_stats']:
            s = report['repair_stats']
            fail_rate = (s.get('per_severity') or {}).get('FAIL', {}).get('repair_success_rate')
            print(f"  修复成功率（FAIL 级）{('%.1f%%' % (fail_rate * 100)) if fail_rate is not None else 'n/a'}"
                  f"　全级别 {s['repair_success_rate']:.1%}　复发率 {s['recurrence_rate']:.1%}"
                  f"　（问题 {s['before']['issues']} → {s['after']['issues']}；"
                  f"FAIL {s['before']['fail']} → {s['after']['fail']}）")
        print(f"  结论: {report['result']}")

    if args.json:
        p = Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        if not args.quiet:
            print(f"  📄 JSON: {p}")
    if args.md:
        p = Path(args.md)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render_md([report]), encoding='utf-8')
        if not args.quiet:
            print(f"  📄 MD: {p}")

    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
