"""契约 schema 正反例测试（jsonschema，pytest 兼容）。

运行: python scripts/run_tests.py  或  python -m pytest tests/ -q

P1-S4 变更（2026-11-02）：本机默认解释器无 jsonschema，原先顶层
`import jsonschema` 会让整个模块 ImportError —— 模块内用例**从未执行**。
现改为：
  - 顶层 import 加守卫，缺依赖时每用例显式 skip（不再拖着整模块一起炸）；
  - 新增 test_schema_checker_is_fail_loud / test_ingest_* 用零依赖路径断言
    「缺依赖不得静默放行」（AC-P1-05 的可执行形态）。
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / 'scripts'))

try:
    import jsonschema
except ImportError:  # 与 ingest.py 的 degrade 口径一致：可降级，但必须显式
    jsonschema = None

_SKIP_MSG = "缺可选依赖 jsonschema（工作指令 §0.2 禁止安装新依赖）；已按 P1-S4 显式 skip"


def _need_jsonschema():
    if jsonschema is None:
        raise unittest.SkipTest(_SKIP_MSG)


def _load_schema(name):
    with open(BASE / 'schemas' / name, encoding='utf-8') as f:
        return json.load(f)


def _valid(schema, data):
    _need_jsonschema()
    jsonschema.Draft7Validator(schema).validate(data)


def _tmp_questions(payload, name='q.json'):
    d = tempfile.mkdtemp()
    p = Path(d) / name
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    p.write_text(text, encoding='utf-8')
    return p


# ── jsonschema 正反例（缺依赖时显式 skip）─────────────────────

def test_agent2_positive():
    _need_jsonschema()
    _valid(_load_schema('agent2_output.schema.json'), [{
        'question_id': 'TEST-M1-A1-001', 'type': 'A1', 'polarity': 'positive',
        'bloom_level': 'memory', 'module': 'M1', 'stem': '题干',
        'options': {'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'},
        'answer_key': 'C', 'explanation': '解析', 'source_pages': ['P12'],
    }])


def test_agent2_legacy_fields_ok():
    _need_jsonschema()
    # 旧契约字段（question/answer/correct_answer）也应通过
    _valid(_load_schema('agent2_output.schema.json'), [{
        'id': 'T1', 'type': 'A1', 'question': '题干',
        'options': [{'label': 'A', 'text': '甲'}, {'label': 'B', 'text': '乙'},
                    {'label': 'C', 'text': '丙'}, {'label': 'D', 'text': '丁'},
                    {'label': 'E', 'text': '戊'}],
        'answer': 'C',
    }])


def test_agent2_negative_missing_options():
    _need_jsonschema()
    from jsonschema import ValidationError
    schema = _load_schema('agent2_output.schema.json')
    try:
        _valid(schema, [{'stem': '题干'}])
        raise AssertionError('缺少 options 应触发 ValidationError')
    except ValidationError:
        pass


def test_agent3_positive():
    _need_jsonschema()
    # v2.0 (2026-08-20 审查修复): dimensions 按真实产物为数组形态
    # （[{dimension,status,score,detail}]，batch027 实测）；旧 dict 形态用例
    # 固化了错误契约，已替换
    _valid(_load_schema('agent3_output.schema.json'), {
        'report_metadata': {'gate_decision': 'PASS_WITH_FIXES', 'overall_score': 82.5},
        'dimensions': [
            {'dimension': 'D1_术语规范性', 'status': 'PASS', 'score': 10.0, 'detail': 'OK'},
            {'dimension': 'D20_B1型题专项', 'status': 'PASS', 'score': 10.0},
        ],
        'bloom_distribution': {'记忆': 30, '理解': 40, '应用': 25, '分析': 5},
        'issues': [{'question_id': 'T1', 'severity': 'major', 'rule': 'D17', 'detail': 'x'}],
    })


def test_agent3_negative_gate_decision():
    _need_jsonschema()
    from jsonschema import ValidationError
    schema = _load_schema('agent3_output.schema.json')
    try:
        _valid(schema, {'report_metadata': {'gate_decision': 'MAYBE'}})
        raise AssertionError('非法 gate_decision 应报错')
    except ValidationError:
        pass


def test_agent4_object_form_with_hc13():
    _need_jsonschema()
    _valid(_load_schema('agent4_output.schema.json'), {
        'source_file_synced': True,
        'execution_metadata': {},
        'patch_log': [{'patch_id': 'P1', 'status': 'EXECUTED'}],
        'final_gate': 'PASS',
    })


def test_agent4_array_form():
    _need_jsonschema()
    _valid(_load_schema('agent4_output.schema.json'), [
        {'question_id': 'T1', 'issue_type': 'D17', 'action': 'fix', 'detail': 'x'},
    ])


def test_agent4_negative_missing_hc13():
    _need_jsonschema()
    from jsonschema import ValidationError
    schema = _load_schema('agent4_output.schema.json')
    try:
        _valid(schema, {'execution_metadata': {}})  # 无 source_file_synced
        raise AssertionError('缺 HC-13 字段应报错')
    except ValidationError:
        pass


# ── 零依赖路径：缺依赖不得静默放行（AC-P1-05）────────────────

def test_schema_checker_is_fail_loud():
    """contract_check 在缺 jsonschema 时必须报错，而不是返回「无问题」。"""
    import contract_check

    errs = contract_check.validate_against_schema([{'x': 1}], {'type': 'array'})
    if jsonschema is None:
        assert errs, "缺 jsonschema 时 validate_against_schema 必须返回错误（fail-loud）"
        assert any('jsonschema' in e for e in errs), errs
    else:
        assert errs == [] or all('jsonschema' not in e for e in errs)


def test_ingest_bad_json_is_fail_not_silent():
    """坏 JSON 必须返回解析错误 —— 旧实现 except Exception: return [] 会放行。"""
    import ingest

    p = _tmp_questions('{not json')
    errs = ingest.validate_schema(p, 'agent2')
    assert errs, "坏 JSON 不得静默通过"
    assert any('解析' in e for e in errs), errs


def test_ingest_strict_mode_rejects_without_jsonschema():
    """strict 模式下缺依赖即 FAIL；本机无 jsonschema，条件不满足时跳过。"""
    if jsonschema is not None:
        raise unittest.SkipTest("本机已装 jsonschema，strict 缺依赖分支不可构造")
    import ingest

    p = _tmp_questions([{'id': 'T1', 'type': 'A1'}])
    saved = os.environ.get(ingest.SCHEMA_STRICT_ENV)
    os.environ[ingest.SCHEMA_STRICT_ENV] = '1'
    try:
        errs = ingest.validate_schema(p, 'agent2')
        assert errs and any('jsonschema' in e for e in errs), errs
    finally:
        if saved is None:
            os.environ.pop(ingest.SCHEMA_STRICT_ENV, None)
        else:
            os.environ[ingest.SCHEMA_STRICT_ENV] = saved


def test_ingest_degrade_records_evidence():
    """degrade 模式必须留证据（JSONL 一行），否则等于静默降级。"""
    if jsonschema is not None:
        raise unittest.SkipTest("本机已装 jsonschema，degrade 分支不可构造")
    import ingest

    p = _tmp_questions([{'id': 'T1', 'type': 'A1'}])
    saved = os.environ.pop(ingest.SCHEMA_STRICT_ENV, None)
    log = ingest._DEGRADED_LOG
    before = log.read_text(encoding='utf-8') if log.exists() else ''
    try:
        ingest.validate_schema(p, 'agent2')
    finally:
        if saved is not None:
            os.environ[ingest.SCHEMA_STRICT_ENV] = saved
    after = log.read_text(encoding='utf-8') if log.exists() else ''
    assert len(after) > len(before), "降级校验未落盘证据"
    assert 'degraded_fallback' in after.splitlines()[-1]


# ═══════════════════════════════════════════════════════════
# P2-S1：schema v2.2 结构字段（2026-11-02）
#
# 分两层：
#   1) 零依赖「契约声明」断言 —— 本机无 jsonschema 也能真跑，防止字段被悄悄删掉；
#   2) jsonschema 正反例 —— 有依赖时校验 actual 校验行为（CI 上生效，本机 skip）。
# 覆盖率的强制不在 schema（新字段 optional 以便回滚），而在
# scripts/validate/rules_batch.py 的 S-STRUCT（按 schema_version ≥ 2.2 触发）。
# ═══════════════════════════════════════════════════════════

V22_FIELDS = ('difficulty_tier', 'step_count', 'competing_dx', 'negative_cues', 'conditionals')


def _items_props():
    return _load_schema('agent2_output.schema.json')['items']['properties']


def test_schema_declares_v22():
    schema = _load_schema('agent2_output.schema.json')
    assert schema.get('x-schema-version') == '2.2'
    assert '2.2' in _items_props()['schema_version']['enum']


def test_schema_v22_fields_present():
    props = _items_props()
    for f in V22_FIELDS:
        assert f in props, f'schema 缺 v2.2 字段 {f}'
        assert props[f].get('description'), f'{f} 必须有 description（字段语义靠它传递）'


def test_difficulty_tier_and_step_count_constraints():
    props = _items_props()
    assert props['difficulty_tier']['enum'] == ['L1', 'L2', 'L3', 'L4']
    assert props['step_count']['minimum'] == 1 and props['step_count']['maximum'] == 8
    assert props['competing_dx']['minItems'] == 1


def test_difficulty_index_marked_deprecated():
    di = _items_props()['difficulty_index']
    assert di.get('deprecated') is True
    assert '弃用' in di['description']


def test_distractor_mechanism_enum_matches_rule_module():
    """schema 的机制枚举必须与 rules_batch.MECHANISMS 完全一致（防两处漂移）。"""
    from scripts.validate import rules_batch as rb

    prop = _items_props()['learning_value']['properties']['per_option']['items']['properties']
    enum = [e for e in prop['distractor_mechanism']['enum'] if e is not None]
    assert tuple(enum) == rb.MECHANISMS, f'schema={enum} vs rules_batch={rb.MECHANISMS}'


def test_v22_item_passes_struct_rule():
    """零依赖：一条字段齐全的 v2.2 题必须通过 S-STRUCT。"""
    from scripts.validate import rules_batch as rb

    rep = rb.check_structural_coverage([_v22()])
    assert rep['status'] == 'PASS', rep
    assert rep['mechanism_coverage'] == 1.0


# ── jsonschema 正反例（缺依赖时显式 skip）──────────────────────

def _lv(**over):
    """learning_value 的完整最小样本。

    2026-11-02 修正：此前 fixture 只写 per_option，缺 schema 里 learning_value.required
    的 6 个字段。本机默认解释器没有 jsonschema，那批用例全部 skip，所以**错误一直没暴露**；
    在装有 jsonschema 的解释器（Python312）上跑 pytest 会直接 FAIL。
    """
    lv = {
        'correct_rationale': (
            '急性心衰合并肾功能不全时应先评估容量状态再决定利尿强度，避免肾前性氮质血症加重；'
            '利尿过程中需每日监测体重、尿量与血肌酐，出现少尿或肌酐上升应立即减量。'),
        'key_takeaway': '合并肾功能不全时先评估容量与灌注，再决定利尿强度，不能照搬常规剂量。',
        'source_quote': '合并肾功能不全者应减量并监测血肌酐',
        'source_quote_status': 'paraphrase',
        'anchor_status': 'verified',
        'review_status': 'draft',
        'per_option': [
            {'label': 'A', 'truth': True, 'why': 'y' * 20, 'distractor_mechanism': None},
            {'label': 'B', 'truth': False, 'why': 'y' * 20, 'misconception_id': 'MC-1',
             'misconception': 'x', 'distractor_mechanism': 'similar_presentation'},
            {'label': 'C', 'truth': False, 'why': 'y' * 20, 'misconception_id': 'MC-1',
             'misconception': 'x', 'distractor_mechanism': 'adjacent_concept'},
            # 2026-11-02 补齐：options 是 A–E 五个，per_option 只写 3 个时，
            # 用 truth 找干扰项的旧逻辑恰好漏掉 D/E；改成「非答案项」判定后立刻暴露。
            {'label': 'D', 'truth': False, 'why': 'y' * 20, 'misconception_id': 'MC-2',
             'misconception': 'y', 'distractor_mechanism': 'timing_error'},
            {'label': 'E', 'truth': False, 'why': 'y' * 20, 'misconception_id': 'MC-2',
             'misconception': 'y', 'distractor_mechanism': 'overgeneralization'},
        ],
    }
    lv.update(over)
    return lv


def _v22(**over):
    """单条 v2.2 题的完整样本（schema 正例与结构规则共用同一份，避免两处漂移）。"""
    q = {
        'question_id': 'V22-M1-A1-001', 'type': 'A1', 'schema_version': '2.2',
        'stem': '题干', 'answer': 'A', 'difficulty_tier': 'L3', 'step_count': 2,
        'competing_dx': ['急性心衰', '肺炎'], 'negative_cues': [],
        'conditionals': ['若合并肾功能不全'],
        'options': {'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'},
        # 2026-11-03：schema 2.2 起 concepts 仍是必填（HC-27），此前夹具漏带，
        # 只在装了 jsonschema 的解释器上暴露；补上主概念 + 鉴别概念。
        'concepts': [
            {'role': 'primary', 'keypoint': '第1条', 'title': '急性心衰',
             'evidence': '题干描述呼吸困难与端坐呼吸，指向急性心衰'},
            {'role': 'differential', 'keypoint': '第1条', 'title': '肺炎',
             'evidence': '肺炎同样可表现为呼吸困难与肺部啰音，需鉴别'},
        ],
        'learning_value': _lv(),
    }
    q.update(over)
    return q


# ── 零依赖：fixture 必须满足 schema 声明的 required ────────────
#
# 只实现 required 这一条关键字（不是完整 schema 校验）。目的是让"fixture 少字段"
# 这类错误在**没有 jsonschema 的解释器上**也能被抓住——否则正例只会在装了依赖的
# 机器上失败，平时全部 skip，等于没有测试。

def _required_gaps(node, obj, path=''):
    gaps = []
    if not isinstance(obj, dict) or not isinstance(node, dict):
        return gaps
    for k in node.get('required', []):
        if k not in obj or obj[k] in (None, ''):
            gaps.append(f'{path}{k}')
    props = node.get('properties') or {}
    for k, sub in props.items():
        if k not in obj or not isinstance(sub, dict):
            continue
        if sub.get('type') == 'object':
            gaps += _required_gaps(sub, obj[k], f'{path}{k}.')
        elif sub.get('type') == 'array' and isinstance(obj[k], list):
            items = sub.get('items') or {}
            if isinstance(items, dict):
                for i, el in enumerate(obj[k]):
                    gaps += _required_gaps(items, el, f'{path}{k}[{i}].')
    return gaps


def test_v22_fixture_meets_all_declared_required_fields():
    """回归：v2.2 正例必须满足 schema 的每一项 required（含 learning_value 6 字段）。"""
    items = _load_schema('agent2_output.schema.json')['items']
    gaps = _required_gaps(items, _v22())
    assert not gaps, f'_v22() 缺必填字段：{gaps}'


def test_v21_fixture_meets_required_fields():
    """2.1 样本（只有 concepts、没有 learning_value）也必须满足自己的 required。"""
    items = _load_schema('agent2_output.schema.json')['items']
    q = {
        'question_id': 'OLD-M1-A1-001', 'type': 'A1', 'schema_version': '2.1',
        'stem': '题干', 'answer': 'A',
        'options': {'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'},
        'concepts': [{'role': 'primary', 'keypoint': '第1条', 'title': '心衰',
                      'evidence': '题干描述呼吸困难与端坐呼吸'}],
    }
    assert not _required_gaps(items, q)


def test_required_walker_actually_catches_missing_field():
    """反向验证：去掉一个必填字段，walker 必须报出来（防止 walker 自身失效）。"""
    items = _load_schema('agent2_output.schema.json')['items']
    q = _v22()
    del q['learning_value']['key_takeaway']
    gaps = _required_gaps(items, q)
    assert 'learning_value.key_takeaway' in gaps, gaps


def test_agent2_v22_positive():
    _valid(_load_schema('agent2_output.schema.json'), [_v22()])


def test_agent2_v22_rejects_bad_tier():
    _need_jsonschema()
    from jsonschema import ValidationError
    try:
        _valid(_load_schema('agent2_output.schema.json'), [_v22(difficulty_tier='L9')])
        raise AssertionError('非法 difficulty_tier 应报错')
    except ValidationError:
        pass


def test_agent2_v22_rejects_bad_mechanism():
    _need_jsonschema()
    from jsonschema import ValidationError
    q = _v22()
    q['learning_value']['per_option'][1]['distractor_mechanism'] = 'made_up'
    try:
        _valid(_load_schema('agent2_output.schema.json'), [q])
        raise AssertionError('非法 distractor_mechanism 应报错')
    except ValidationError:
        pass


def test_agent2_v21_still_valid_without_new_fields():
    """回滚口径：v2.1 题不带任何 v2.2 字段也必须照常通过（新字段 optional）。"""
    _need_jsonschema()
    _valid(_load_schema('agent2_output.schema.json'), [{
        'question_id': 'OLD-M1-A1-001', 'type': 'A1', 'schema_version': '2.1',
        'stem': '题干', 'answer': 'A',
        'options': {'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'},
        'concepts': [{'role': 'primary', 'keypoint': '第1条', 'title': '心衰',
                      'evidence': '题干描述呼吸困难与端坐呼吸'}],
    }])
