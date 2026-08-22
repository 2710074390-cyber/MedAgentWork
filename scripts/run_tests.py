#!/usr/bin/env python3
"""
run_tests.py — MedAgentWork 零依赖测试运行器 v1.0 (2026-08-13 · P0-2)

发现 tests/test_*.py 中名为 test_* 的函数并执行（纯 assert，pytest 兼容）。
有 pytest 时也可直接用 `python -m pytest tests/ -q`。

用法:
  python scripts/run_tests.py            # 全部测试
  python scripts/run_tests.py -v         # 详细输出
  python scripts/run_tests.py test_qbank # 按文件名过滤
"""
import importlib.util
import sys
import traceback
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = Path(__file__).resolve().parent.parent
TESTS_DIR = BASE / 'tests'


def load_module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    verbose = '-v' in sys.argv
    filt = next((a for a in sys.argv[1:] if not a.startswith('-')), None)

    test_files = sorted(TESTS_DIR.glob('test_*.py'))
    if filt:
        test_files = [f for f in test_files if filt in f.name]

    passed = failed = errors = 0
    failures = []
    for tf in test_files:
        try:
            mod = load_module(tf)
        except Exception:
            errors += 1
            failures.append((tf.name, '<模块导入失败>', traceback.format_exc()))
            continue
        funcs = [(n, f) for n, f in sorted(vars(mod).items())
                 if n.startswith('test_') and callable(f)]
        for name, fn in funcs:
            try:
                fn()
                passed += 1
                if verbose:
                    print(f'  ✓ {tf.name}::{name}')
            except AssertionError as e:
                failed += 1
                failures.append((tf.name, name, f'AssertionError: {e}'))
            except Exception as e:
                errors += 1
                failures.append((tf.name, name, f'{type(e).__name__}: {e}'))

    print(f'\n{"─"*60}')
    print(f'  MedAgentWork 测试套件 ({len(test_files)} 个文件)')
    print(f'  ✅ {passed} 通过  ✗ {failed} 失败  ⚠️ {errors} 错误')
    if failures:
        print(f'\n  失败详情:')
        for fname, tname, detail in failures:
            print(f'  ✗ {fname}::{tname}')
            for line in str(detail).splitlines()[:6]:
                print(f'      {line}')
    print(f'{"═"*60}')
    sys.exit(0 if (failed == 0 and errors == 0) else 1)


if __name__ == '__main__':
    main()
