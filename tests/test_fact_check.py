"""fact_check 事实校验单元测试（pytest 兼容，纯 assert，临时数据隔离）。

运行: python scripts/run_tests.py  或  python -m pytest tests/ -q
"""
import json
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / 'scripts'))
sys.path.insert(0, str(BASE))
import fact_check as fc
import qbank


def _chunks(tmp, code, pages):
    p = Path(tmp) / 'chunks_metadata'
    p.mkdir(parents=True, exist_ok=True)
    with open(p / f'{code}_chunks.jsonl', 'w', encoding='utf-8') as f:
        for pg in pages:
            f.write(json.dumps({'page_number': pg, 'text': 'x'}, ensure_ascii=False) + '\n')


def _questions(pages_list):
    """pages_list: [(qid, source_pages_raw), ...] — 走 qbank.parse_question 真实规范化。"""
    out = []
    for qid, raw in pages_list:
        rawq = {'question_id': qid, 'stem': '测试题干',
                'options': {'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd', 'E': 'e'},
                'answer': 'A', 'source_pages': raw}
        q = qbank.parse_question(rawq)
        q['qid'] = qid
        out.append(q)
    return out


def test_pages_placeholder_and_out_of_range():
    with tempfile.TemporaryDirectory() as tmp:
        _chunks(tmp, 'tst', [10, 12, 20, 30])
        qs = _questions([
            ('Q1', ['P0']),          # 占位符 → FAIL
            ('Q2', ['P999']),        # 越界 → FAIL
            ('Q3', ['P20']),         # 有效
            ('Q4', ['P15']),         # 不在索引 → WARN
            ('Q5', []),              # 缺页码 → WARN
            ('Q6', ['指南2023']),    # 非页码来源 → WARN
            ('Q7', ['P10-P12']),     # 区间 → 检查两个端点
        ])
        issues = fc.check_pages(qs, 'tst', kb_base=tmp)
        by_qid = {}
        for i in issues:
            by_qid.setdefault(i['qid'], []).append(i['severity'])
        assert 'FAIL' in by_qid['Q1'] and '占位符' in next(i['detail'] for i in issues if i['qid'] == 'Q1')
        assert 'FAIL' in by_qid['Q2']
        assert not by_qid.get('Q3')
        assert 'WARN' in by_qid['Q4'] and '不在教材分块索引' in next(i['detail'] for i in issues if i['qid'] == 'Q4')
        assert 'WARN' in by_qid['Q5'] and '缺页码' in next(i['detail'] for i in issues if i['qid'] == 'Q5')
        assert 'WARN' in by_qid['Q6'] and '非教材页码' in next(i['detail'] for i in issues if i['qid'] == 'Q6')
        assert not by_qid.get('Q7')  # P10、P12 均在索引


def test_golden_duplicate_and_conflict():
    with tempfile.TemporaryDirectory() as tmp:
        gs_path = Path(tmp) / 'gs.json'
        gs = [
            {'gs_id': 'GS-DUP-1', 'year': 2020, 'stem': '急性心肌梗死患者突发胸痛首选检查是',
             'answer': 'A', 'explanation': '急性心肌梗死首选心电图检查，必要时查肌钙蛋白'},
            {'gs_id': 'GS-CONF-1', 'year': 2020, 'stem': '高血压患者血压控制目标值一般应该是多少',
             'answer': 'B', 'explanation': '普通高血压患者血压控制目标为140/90mmHg以下'},
        ]
        gs_path.write_text(json.dumps(gs, ensure_ascii=False), encoding='utf-8')
        gs_items = fc.load_golden(gs_path)
        assert len(gs_items) == 2

        # 近重复题（同主题同数值）→ duplicate（真实 jieba 路径）
        q_dup = {'qid': 'N1', 'stem': '急性心肌梗死患者突发胸痛，首选检查是',
                 'options': {'A': '心电图', 'B': 'CT', 'C': '超声', 'D': 'MRI', 'E': '胸片'},
                 'answer': 'A', 'explanation': '急性心肌梗死首选心电图检查', 'source_pages': []}
        # 同主题但数值不同（130/80 vs 金标准 140/90）→ conflict
        # 关键词用 mock 保证确定性（jieba 分词版本差异会导致 containment 波动）；
        # 数值提取走真实 regex 路径
        q_conf = {'qid': 'N2', 'stem': '高血压患者血压控制到多少合适',
                  'options': {'A': '150/90mmHg以下', 'B': '140/90mmHg以下', 'C': '130/80mmHg以下',
                              'D': '120/80mmHg以下', 'E': '160/100mmHg以下'},
                  'answer': 'C', 'explanation': '高血压患者血压控制目标为130/80mmHg以下', 'source_pages': []}

        orig_keywords = fc.keywords

        def fake_keywords(text):
            if '高血压' in text:
                # GS 5 词 vs 新题 5 词, 交集 {高血压,血压,控制}=3 → containment=3/5=0.6
                return {'高血压', '血压', '控制', '目标', '一般'} if '应该' in text \
                    else {'高血压', '血压', '控制', '多少', '合适'}
            return orig_keywords(text)

        fc.keywords = fake_keywords
        try:
            gs_items = fc.load_golden(gs_path)
            results = fc.golden_crosscheck([q_dup, q_conf], gs_items)
        finally:
            fc.keywords = orig_keywords
        kinds = {r['qid']: r['kind'] for r in results}
        assert kinds.get('N1') == 'duplicate', results
        assert kinds.get('N2') == 'conflict', results
