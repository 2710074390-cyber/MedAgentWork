"""
engine.py — 主校验引擎
从 validate_options.py 拆分而来
"""
import os
import sys
from pathlib import Path
from .rules_numeric import BASIC_NUMERIC_CHECKS
from .rules_structural import STRUCTURAL_CHECKS, check_b1_groups, check_js1_json_integrity, check_s3_placeholder_pages

# v2.1 回灌 (2026-10-13)：telemetry 导入加固（评审 §6.5-P1.2 同源问题）。
# 此前 `from scripts.telemetry import log_validation ...` 因 telemetry 缺失
# log_validation 而 ImportError 被静默吞掉 → 校验遥测一直失效。
# 现改为：scripts.telemetry（根在 sys.path 的命名空间包）→ telemetry
# （scripts 目录在 sys.path）→ 显式警告降级，不再静默。
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
try:
    from scripts.telemetry import log_validation, log_info, log_error
    TELEMETRY_AVAILABLE = True
except ImportError:
    try:
        from telemetry import log_validation, log_info, log_error
        TELEMETRY_AVAILABLE = True
    except ImportError as _e:
        print(f"  ⚠️ telemetry 模块不可用({_e})，事件日志已跳过（不影响校验结果）", file=sys.stderr)
        TELEMETRY_AVAILABLE = False

        def log_validation(*a, **k):
            pass

        def log_info(*a, **k):
            pass

        def log_error(*a, **k):
            pass

BASE = Path(__file__).parent.parent.parent


def validate_questions(questions: list[dict], verbose: bool = False, mode: str = 'basic', filepath: str | None = None) -> tuple[dict, dict]:
    """对题目列表执行校验规则，返回 (issues_by_question, summary)

    mode: 'basic' = R1-R9 + B1（默认）
          'full'  = R1-R9 + B1 + R10-R13 + JS1 + S3
    """
    if TELEMETRY_AVAILABLE:
        log_info(f"Starting validation for {len(questions)} questions", mode=mode, filepath=filepath)

    all_issues = {}
    total_pass = 0
    total_warn = 0
    total_fail = 0

    checks = list(BASIC_NUMERIC_CHECKS)
    if mode == 'full':
        checks.extend(STRUCTURAL_CHECKS)

    for q in questions:
        q_issues = []
        for check_fn in checks:
            q_issues.extend(check_fn(q))

        all_issues[q['id']] = q_issues

        fail_count = sum(1 for i in q_issues if i['severity'] == 'FAIL')
        warn_count = sum(1 for i in q_issues if i['severity'] == 'WARN')

        if fail_count > 0:
            total_fail += 1
        elif warn_count > 0:
            total_warn += 1
        else:
            total_pass += 1

    b1_issues = check_b1_groups(questions)
    for issue in b1_issues:
        all_issues.setdefault('_b1_groups', []).append(issue)
        if issue['severity'] == 'FAIL':
            total_fail += 1
        elif issue['severity'] == 'WARN':
            total_warn += 1

    if mode == 'full':
        s3_issues = check_s3_placeholder_pages(questions)
        for issue in s3_issues:
            all_issues.setdefault('_cross_question', []).append(issue)
            if issue['severity'] == 'FAIL':
                total_fail += 1
            elif issue['severity'] == 'WARN':
                total_warn += 1

        js1_issues = check_js1_json_integrity(questions, filepath)
        for issue in js1_issues:
            all_issues.setdefault('_json_integrity', []).append(issue)
            if issue['severity'] == 'FAIL':
                total_fail += 1
            elif issue['severity'] == 'WARN':
                total_warn += 1

    summary = {
        'total_questions': len(questions),
        'pass': total_pass,
        'warn': total_warn,
        'fail': total_fail,
        'b1_groups_checked': len([q for q in questions if q.get('type') == 'B1' and q.get('b1_group')]),
    }

    if TELEMETRY_AVAILABLE:
        log_validation(filepath or 'unknown', mode, total_fail, total_warn, total_pass, summary)

    return all_issues, summary


def discover_files(batch_id):
    """发现指定批次的所有题库文件"""
    batch_dir = BASE / "最终产物" / batch_id
    if not batch_dir.exists():
        batch_dir = BASE / "中间产物" / batch_id
    if not batch_dir.exists():
        return []

    exclude_keywords = ('追溯', 'escalation', 'trace', '调用指令', 'module_')
    for name in ('ALL_questions_FIXED.json', 'ALL_questions_FIXED.md',
                 'ALL_questions.json', 'ALL_questions.md'):
        f = batch_dir / name
        if f.exists():
            return [f]

    files = []
    for ext in ('*.json', '*.md'):
        for f in sorted(batch_dir.glob(ext)):
            if any(kw in f.name for kw in ('追溯', 'escalation', 'trace', '调用指令')):
                continue
            files.append(f)
    return files
