#!/usr/bin/env python3
"""
选项设计机械化校验器 — 入口文件

用法:
  python validate_options.py --batch batch005
  python validate_options.py --file path/to/file.json

注意: 本文件仅为向后兼容保留，实际代码已拆分至 scripts/validate/ 包。
建议使用: python -m scripts.validate --batch batch005
"""
import sys
from pathlib import Path

# 本文件位于 skill 的 scripts/ 目录；上级（skill 根）需在路径中使 scripts.validate 可导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.validate.__main__ import main
from scripts.validate import validate_file, validate_batch
from scripts.validate.engine import validate_questions, discover_files
from scripts.validate.rules_numeric import (
    check_r1_forbidden,
    check_r2_length_ratio,
    check_r3_numeric_sort,
    check_r4_negation_bold,
    check_r5_option_count,
    check_r6_numeric_discrimination,
    check_r7_truncation,
    check_r8_min_length,
    check_r9_missing_unit,
)
from scripts.validate.rules_structural import (
    check_r10_clue_repetition,
    check_r11_convergence,
    check_r12_meaningless_suffix,
    check_r13_length_ceiling,
    check_b1_groups,
    check_js1_json_integrity,
    check_s3_placeholder_pages,
    _extract_stem_keywords,
)
from scripts.validate.rules_static import (
    check_s1_schema_completeness,
    check_s2_null_values,
    check_s4_absolute_language,
)

if __name__ == '__main__':
    main()
