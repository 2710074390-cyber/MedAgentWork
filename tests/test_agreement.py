# -*- coding: utf-8 -*-
"""P3-S2 评分者一致性统计回归（agreement.py）。

重点不是"公式跑得动"，而是三条硬线：
  1. 只有一名评分者时必须 BLOCKED，κ 必须是 None —— 不许拿单人的两轮冒充专家一致性；
  2. 完全相反的两轮评分要给出 κ = -1，而不是被"能算出来"糊过去；
  3. κ 通过而 Bland–Altman 偏倚不为 0 的情况必须同时暴露（系统性偏高/偏低）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import agreement as ag  # noqa: E402


def _ratings(r1, r2=None, dims=('D1',)):
    items = []
    for i, (a, b) in enumerate(zip(r1, r2 or []), 1):
        sc = {'r1': {d: a for d in dims}}
        sc['r2'] = {d: b for d in dims}
        items.append({'qid': f'Q{i:03d}', 'scores': sc})
    if r2 is None:
        items = [{'qid': f'Q{i:03d}', 'scores': {'r1': {d: a for d in dims}}}
                 for i, a in enumerate(r1, 1)]
    return {'meta': {'raters': ['r1', 'r2'] if r2 is not None else ['r1'], 'dims': list(dims)},
            'items': items}


# ── 加权 κ ──

def test_perfect_agreement_kappa_is_one():
    a = [3, 2, 1, 0, 3, 2]
    r = ag.weighted_kappa(a, a)
    assert r['kappa'] == 1.0
    assert r['observed_agreement'] == 1.0


def test_reversed_agreement_kappa_is_minus_one():
    """完全反向且边际分布相同 → κ = −1（最差一致）。边际不同的反向不算 −1。"""
    a = [3, 2, 1, 0, 3, 2, 1, 0]
    b = [0, 1, 2, 3, 0, 1, 2, 3]
    assert ag.weighted_kappa(a, b)['kappa'] == -1.0


def test_mixed_case_matches_hand_calculation():
    """x=[3,3,2,1,0,2] / y=[3,2,2,2,0,1]，二次加权 κ = 0.7568（手算 pin）。"""
    r = ag.weighted_kappa([3, 3, 2, 1, 0, 2], [3, 2, 2, 2, 0, 1])
    assert r['kappa'] == 0.7568, r
    assert r['observed_agreement'] == 0.5


def test_kappa_rejects_out_of_range():
    try:
        ag.weighted_kappa([0, 4], [0, 1], levels=4)
        raise AssertionError('越界评分应报错，而不是静默算出一个数')
    except ValueError as e:
        assert '超界' in str(e)


def test_kappa_degenerate_returns_none_not_one():
    """两人评分全部落在同一格 → 期望一致率 0，κ 无定义；必须返回 None，不能当 1.0。"""
    r = ag.weighted_kappa([3, 3, 3], [3, 3, 3], levels=4)
    assert r['kappa'] is None and r['degenerate'] is True


# ── ICC(2,1) ──

def test_icc_perfect_is_one():
    a = [3, 2, 1, 0, 3, 2]
    assert ag.icc_2_1([[x, x] for x in a])['icc'] == 1.0


def test_icc_single_rater_is_none():
    r = ag.icc_2_1([[3], [2], [1]])
    assert r['icc'] is None and r['k'] == 1
    assert '只有 1 名评分者' in r['note']


def test_icc_near_zero_for_systematic_offset():
    """评分者 A 恒比 B 高 1 分且题目间有变异 → ICC 低（绝对一致性差）。"""
    b = [0, 1, 2, 3, 0, 1, 2, 3]
    a = [min(x + 1, 3) for x in b]
    r = ag.icc_2_1([[p, q] for p, q in zip(a, b)])
    assert r['icc'] < 0.8, r


# ── Bland–Altman ──

def test_bland_altman_zero_bias_on_perfect():
    r = ag.bland_altman([3.0, 2.0], [3.0, 2.0])
    assert r['bias'] == 0.0 and r['loa_lower'] == r['loa_upper'] == 0.0


def test_bland_altman_detects_systematic_bias():
    """κ 可能因为"顺序一致"而很高，但两人整体差 1 分——BA 必须把这个偏倚暴露出来。"""
    b = [0, 1, 2, 3, 0, 1, 2, 3]
    a = [x + 1 for x in b]
    r = ag.bland_altman([float(x) for x in a], [float(x) for x in b])
    assert r['bias'] == 1.0 and r['sd'] == 0.0


# ── 报告层：BLOCKED 与阈值 ──

def test_single_rater_report_is_blocked_with_null_kappa():
    rep = ag.build_report(_ratings([2, 3, 1, 0]))
    assert rep['status'] == 'BLOCKED'
    assert '只有 1 名评分者' in rep['reason']
    assert all(r.get('kappa') is None for r in rep['per_dim']) if rep['per_dim'] else True


def test_two_raters_high_agreement_passes():
    a = [3, 2, 2, 1, 0, 3, 2, 1]
    rep = ag.build_report(_ratings(a, a[:]))
    assert rep['status'] == 'PASS'
    assert rep['per_dim'][0]['kappa'] == 1.0


def test_two_raters_low_agreement_is_below():
    a = [3, 3, 2, 2, 1, 1]
    b = [0, 0, 1, 1, 2, 2]
    rep = ag.build_report(_ratings(a, b))
    assert rep['status'] == 'BELOW'
    assert rep['low_dims'] == ['D1']


def test_report_marks_incomplete_items():
    data = _ratings([3, 2, 1], [3, 2, 1])
    data['items'].append({'qid': 'Q9', 'scores': {'r1': {'D1': 2}}})  # 缺 r2
    rep = ag.build_report(data)
    assert rep['n_items_total'] == 4 and rep['n_items_complete'] == 3


def test_bootstrap_ci_is_ordered():
    a = [3, 3, 2, 1, 0, 2, 1, 3, 2, 1, 0, 3]
    b = [3, 2, 2, 2, 0, 1, 1, 3, 2, 0, 0, 3]
    ci = ag._bootstrap_kappa_ci(a, b, 4, iters=200)
    assert ci is not None and ci[0] <= ci[1], ci


def test_render_md_carries_mode_and_threshold():
    rep = ag.build_report(_ratings([3, 2, 1], [3, 2, 1]))
    md = ag.render_md(rep)
    assert 'inter-rater' in md and '0.61' in md
