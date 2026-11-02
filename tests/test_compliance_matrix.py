# -*- coding: utf-8 -*-
"""P8 合规盘点回归：真题判定、unknown 单列、公开暴露计数。

这些用例保护的是**判定的保守性**：宁可把没标注的题当原创（可能漏检），
也不能把原创题误判成真题（会造成无谓的下架压力）。
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import license_matrix as lm  # noqa: E402
import public_risk as pr  # noqa: E402


def _q(**over):
    q = {'id': 'T1', 'type': 'A1', 'stem': 'x', 'options': {'A': 'a'}, 'answer': 'A'}
    q.update(over)
    return q


def _write(items):
    d = Path(tempfile.mkdtemp()) / 'batch999' / 'ALL_questions_FIXED.json'
    d.parent.mkdir(parents=True, exist_ok=True)
    d.write_text(json.dumps(items, ensure_ascii=False), encoding='utf-8')
    return d


# ── 真题判定 ───────────────────────────────────────────────

def test_kaoyan_origin_detected():
    o = lm.origin_of(_q(kaoyan_origin={'gs_id': 'GS-1', 'year': 2024, 'source': '2024考研西综·第12题'}))
    assert o['kind'] == 'kaoyan' and o['year'] == '2024' and o['ref'] == 'GS-1'


def test_zhiyi_origin_detected():
    o = lm.origin_of(_q(zhiyi_origin={'source_id': 'ZY-9', 'corpus': 'pdf_paper', 'mode': '原题'}))
    assert o['kind'] == 'zhiyi' and o['ref'] == 'ZY-9'


def test_declared_source_type_counts_as_real():
    assert lm.origin_of(_q(source_type='考研真题'))['kind'] == 'declared'


def test_unmarked_question_is_original():
    """没有标注 → 按原创处理。这是保守方向：宁可漏检，不误判。"""
    assert lm.origin_of(_q())['kind'] == 'original'


def test_license_missing_becomes_unknown():
    rows, s = lm.scan([_write([_q(kaoyan_origin={'gs_id': 'G1'})])])
    assert rows[0]['license'] == 'unknown' and rows[0]['license_known'] is False
    assert s['real_without_license'] == 1
    assert rows[0]['qid'] in s['unknown_qids']


def test_license_present_counted():
    rows, s = lm.scan([_write([_q(kaoyan_origin={'gs_id': 'G1'}, license='public_noncommercial')])])
    assert rows[0]['license_known'] is True
    assert s['real_license_coverage'] == 1.0


def test_original_questions_not_in_coverage_denominator():
    """原创题不参与真题 license 覆盖率，否则分母被稀释成好看的数字。"""
    rows, s = lm.scan([_write([_q(), _q(id='T2'), _q(id='T3', kaoyan_origin={'gs_id': 'G'})])])
    assert s['real_total'] == 1 and s['original_total'] == 2
    assert s['real_license_coverage'] == 0.0


def test_evidence_collects_license_note_and_anchors():
    ev = lm.evidence_of(_q(license_note='已获授权', source_anchors=['a', 'b']))
    assert any('license_note' in e for e in ev) and any('×2' in e for e in ev)


# ── 公开暴露计数 ───────────────────────────────────────────

def test_scan_file_counts_only_real_qids():
    real = {'Q1': {'license_known': False, 'origin_kind': 'kaoyan'},
            'Q2': {'license_known': True, 'origin_kind': 'kaoyan'}}
    p = Path(tempfile.mkdtemp()) / 'page.md'
    p.write_text('Q1 出现两次 Q1，Q2 一次，Q3 是原创', encoding='utf-8')
    r = pr.scan_file(p, real)
    assert r['real_qids'] == 2, r          # Q1、Q2；Q3 不在真题表里
    assert r['unclear_qids'] == 1          # 只有 Q1 未记录 license
    assert r['unclear_by_origin'] == {'kaoyan': 1}


def test_scan_file_without_hits():
    p = Path(tempfile.mkdtemp()) / 'empty.md'
    p.write_text('没有任何题目', encoding='utf-8')
    r = pr.scan_file(p, {'Q1': {'license_known': False, 'origin_kind': 'kaoyan'}})
    assert r['real_qids'] == 0 and r['unclear_qids'] == 0
