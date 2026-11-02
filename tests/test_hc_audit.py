# -*- coding: utf-8 -*-
"""P1-S6 HC 编号治理测试（AC-P1-08 / AC-P1-09）。

两条验收在这里变成可执行的断言：
  · 无 HC 双定义 —— 活定义 ≥2 即失败；
  · 活跃 docs ≤5 —— docs/*.md 计数。

为什么要测「判定逻辑」而不只测结果：编号治理最可能的失败形态不是改错某个字，
而是**审计脚本自己失去判别力**——比如把已废止的行仍然算作活定义，于是改完
依旧报重复；或者把作用域后缀归并回父编号，于是 HC-6.A1 与 HC-6.A4 又撞在一起。
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "scripts"))

import hc_audit as ha  # noqa: E402


# ── 编号归一 ────────────────────────────────────────────────

def test_norm_keeps_scope_suffix():
    """作用域后缀是治理手段，归一化时不能被抹掉。"""
    assert ha.norm('HC-6.A1') == 'HC-6.A1'
    assert ha.norm('HC-6.A4') == 'HC-6.A4'
    assert ha.norm('HC-6') == 'HC-6'
    assert ha.norm('HC-3a') == 'HC-3a'


def test_norm_drops_parenthetical():
    assert ha.norm('HC-6(修复)') == 'HC-6'
    assert ha.norm('HC-7(Gen)') == 'HC-7'


# ── 已废止判定 ──────────────────────────────────────────────

def test_retired_markers():
    assert ha.is_retired('| **HC-18（配额·已废止，由 HC-22 接管）** |')
    assert ha.is_retired('## HC-18（已接管）')
    assert not ha.is_retired('## HC-18 产物形态契约')


# ── 定义/引用识别 ──────────────────────────────────────────

def _scan(tmp: Path, name: str, text: str) -> tuple:
    p = tmp / name
    p.write_text(text, encoding='utf-8')
    return ha.scan_soul(p) if name == 'SOUL.md' else ha.scan_prompt(p)


def test_table_definition_detected(tmp_path=None):
    import tempfile

    tmp = Path(tmp_path or tempfile.mkdtemp())
    defs, refs = _scan(tmp, 'SOUL.md', '| **HC-6.A1** | Agent 1 | 干扰项区分度 |\n')
    assert len(defs) == 1 and defs[0]['number'] == 'HC-6.A1'
    assert defs[0]['owner'] == 'Agent 1'


def test_section_definition_detected(tmp_path=None):
    import tempfile

    tmp = Path(tmp_path or tempfile.mkdtemp())
    defs, _ = _scan(tmp, 'SOUL.md', '## HC-27 概念标注强制\n正文\n')
    assert defs[0]['number'] == 'HC-27' and defs[0]['kind'] == 'section'


def test_strikethrough_is_not_reference(tmp_path=None):
    """别名对照表里的 ~~HC-1~~ 是「已改名」，不能算它还活着。"""
    import tempfile

    tmp = Path(tmp_path or tempfile.mkdtemp())
    _, refs = _scan(tmp, 'p.md', '| `PG-01` | ~~HC-1~~ | 本文件原小节 |\n正文引用 PG-01。\n')
    assert refs == []


def test_prompt_section_detected(tmp_path=None):
    import tempfile

    tmp = Path(tmp_path or tempfile.mkdtemp())
    secs, _ = _scan(tmp, 'p.md', '### HC-29：干扰项生成协议\n')
    assert secs[0]['number'] == 'HC-29'


# ── 真实仓库验收 ───────────────────────────────────────────

def test_real_repo_has_no_duplicate_number():
    """AC-P1-08：活定义 ≥2 即失败。"""
    d = ha.build()
    assert d['duplicate_count'] == 0, f"仍有重复定义：{d['duplicate']}"


def test_real_repo_has_no_orphan_number():
    """被引用但 SOUL 无定义的编号必须为 0（父编号算已定义）。"""
    d = ha.build()
    assert d['orphan_count'] == 0, f"仍有孤儿编号：{d['orphan']}"


def test_hc18_quota_is_marked_retired():
    """HC-18 配额条款必须留痕为已废止，而不是被悄悄删掉。"""
    text = (BASE / 'SOUL.md').read_text(encoding='utf-8')
    assert 'HC-18（配额·已废止，由 HC-22 接管）' in text
    assert 'HC-22' in text


def test_soul_defines_hc19_27_29():
    """回写在 SOUL 里的三条必须真的存在，且能被审计识别。"""
    d = ha.build()
    numbers = {r['number'] for r in d['rows']}
    for n in ('HC-19', 'HC-27', 'HC-29'):
        assert n in numbers, f'SOUL 缺 {n} 定义'


def test_prompt_internal_numbers_migrated_to_pg():
    """提示词内部规则已改 PG-，旧编号只出现在别名对照表（删除线里）。"""
    text = (BASE / 'Prompt版本' / 'MedGen_current_prompt.md').read_text(encoding='utf-8')
    assert '### PG-01：' in text
    # 硬约束编号仍保留 HC
    assert '### HC-27：' in text and '### HC-29：' in text
    assert '~~HC-1~~' in text


# ── AC-P1-09 ──────────────────────────────────────────────

def test_active_docs_at_most_five():
    active = sorted((BASE / 'docs').glob('*.md'))
    names = [p.name for p in active]
    assert len(active) <= 5, f"活跃 docs 超限：{names}"


def test_archived_docs_are_kept_not_deleted():
    """归档 ≠ 删除：18 篇必须还在 archive 里。"""
    arch = list((BASE / 'docs' / 'archive' / '2026-11').glob('*.md'))
    assert len(arch) >= 18, f'归档只剩 {len(arch)} 篇，可能被误删'
    assert any(p.name == 'README.md' for p in arch), '归档目录缺说明'
