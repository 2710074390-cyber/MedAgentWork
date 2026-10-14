"""
validate 包 — 选项设计机械化校验器模块化拆分
从 validate_options.py (1691行) 拆分而来，提高可维护性。

用法:
    from scripts.validate import validate_batch, validate_file
    from scripts.validate.parsers import parse_json_file, parse_md_file
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path.cwd()
OUTPUT_BASE = BASE / 'reports' / 'validate'

from .parsers import parse_json_file, parse_md_file
from .engine import validate_questions, discover_files
from .reporter import print_report, save_json_report

__all__ = [
    'parse_json_file',
    'parse_md_file',
    'validate_questions',
    'discover_files',
    'print_report',
    'save_json_report',
    'validate_file',
    'validate_batch',
]


def validate_file(filepath, mode='full', verbose=False):
    """校验单个文件"""
    from .parsers import parse_json_file, parse_md_file

    filepath = Path(filepath)
    if not filepath.exists():
        print(f"  ✗ 文件不存在: {filepath}")
        return None

    if filepath.suffix == '.json':
        questions = parse_json_file(filepath)
    elif filepath.suffix == '.md':
        questions = parse_md_file(filepath)
    else:
        print(f"  ✗ 不支持的文件格式: {filepath.suffix}")
        return None

    if not questions:
        print(f"  ⚠️ 未解析到任何题目: {filepath}")
        return None

    all_issues, summary = validate_questions(questions, verbose, mode=mode, filepath=str(filepath))
    print_report(all_issues, summary, filepath)
    save_json_report(all_issues, summary, filepath, filepath.stem, mode=mode)
    return summary


def validate_batch(batch_id, mode='full', verbose=False):
    """校验整个批次"""
    from .parsers import parse_json_file, parse_md_file

    files = discover_files(batch_id)
    if not files:
        print(f"  ✗ 未找到批次 {batch_id} 的题库文件")
        return None

    print(f"  📁 批次 {batch_id}: 发现 {len(files)} 个文件")

    all_questions = []
    for filepath in files:
        print(f"  📄 解析: {filepath.name}")
        if filepath.suffix == '.json':
            qs = parse_json_file(filepath)
        elif filepath.suffix == '.md':
            qs = parse_md_file(filepath)
        else:
            continue
        all_questions.extend(qs)
        print(f"      → {len(qs)} 题")

    if not all_questions:
        print(f"  ⚠️ 未解析到任何题目")
        return None

    all_issues, summary = validate_questions(all_questions, verbose, mode=mode, filepath=str(files[0]))
    print_report(all_issues, summary, files[0])
    save_json_report(all_issues, summary, files[0], batch_id, mode=mode)
    return summary
