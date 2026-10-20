#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""real_question_cli.py — 真题检索子系统入口（薄包装）。

用法：
  python scripts/real_question_cli.py build
  python scripts/real_question_cli.py plan --subject 内科学 --target 200 --keypoints ...
  python scripts/real_question_cli.py check --file 最终产物/batchXXX/ALL_questions_FIXED.json
  python scripts/real_question_cli.py recover
  python scripts/real_question_cli.py stats
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from real_question.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
