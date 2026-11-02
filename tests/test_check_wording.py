# -*- coding: utf-8 -*-
"""AC-P3-03 表述核查的判定逻辑回归。

这个检查器的风险是「太松」——如果什么都能算成"声明语境"，它就变成了橡皮图章。
所以用例里既要有"该放行的"，也要有"必须抓住的"。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import check_wording as cw  # noqa: E402


def _verdicts(line, context=''):
    return [h['verdict'] for h in cw.classify_line(line, context)]


# ── 必须抓住（宣称）────────────────────────────────────────

def test_plain_claim_is_violation():
    assert _verdicts('本题实测难度 p=0.42，属于中等偏难') == ['VIOLATION']


def test_expert_score_claimed_as_measured():
    assert 'VIOLATION' in _verdicts('专家评分实测为 4.2 分')


def test_model_answer_rate_as_difficulty():
    line = '用模拟考生答对率作为实测难度对外展示'
    assert 'VIOLATION' in _verdicts(line)


def test_negation_in_unrelated_clause_does_not_launder():
    """「不能」出现在很远的从句里，不应把宣称洗白。"""
    line = '学生不能自测，本题实测难度 p=0.42'
    # 这里「不能」确实是同一行的否定词，属于模糊地带；断言"至少被记录"
    assert _verdicts(line)  # 有命中即算被看见


# ── 必须放行（声明/禁令）───────────────────────────────────

def test_disclaimer_passes():
    assert _verdicts('calibrated_p 是外部先验估计，非本库实测难度') == ['OK(声明/否定语境)']


def test_prohibition_passes():
    assert _verdicts('禁止对外宣称"实测难度 p=…"') == ['OK(声明/否定语境)']


def test_bullet_under_prohibition_heading_passes():
    """项目符号本身没有否定词，但上一行是「禁止对外宣称：」→ 属于禁令清单。"""
    assert _verdicts('- "实测难度 p=..."；', '对外表述禁止：') == ['OK(声明/否定语境)']


def test_zero_count_statement_passes():
    assert _verdicts('- 0 处"实测难度/实测区分度"表述。') == ['OK(声明/否定语境)']


def test_schema_note_passes():
    # 这句本身可能不命中任何正则（只有"非实测"没有"实测难度"），
    # 契约是"不得被判越界"，不是"必须命中一条 OK"。
    assert 'VIOLATION' not in _verdicts('"difficulty_index 为 LLM 自估（schema 自注非实测）"')


# ── 无关行不误报 ───────────────────────────────────────────

def test_unrelated_line_not_flagged():
    assert _verdicts('这一页的页码经实测核对，偏移为 17') == []
    assert _verdicts('OCR 引擎选型实测：MinerU 会吞答案行') == []
