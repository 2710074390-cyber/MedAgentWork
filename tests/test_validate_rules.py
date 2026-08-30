"""validate_options R1-R13 规则黄金用例（pytest 兼容，纯 assert）。

用例来源：FACT.md 历史灾难样本（batch006 截断 / batch007 系统截断 /
batch014 缺单位回归 / NBME D18/D19 线索检测）+ 规则文档。
运行: python scripts/run_tests.py  或  python -m pytest tests/ -q
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
import validate_options as vo


def _q(options, answer='A', stem='关于该疾病的治疗，以下哪项是正确的？', qtype='A1', qid='T-001'):
    return {'id': qid, 'type': qtype, 'question': stem, 'options': options, 'answer': answer}


def _sev(issues, rule):
    return [i['severity'] for i in issues if i['rule'] == rule]


# ── R1 禁止项 / 绝对化用语 ──

def test_r1_forbidden_all_of_above():
    q = _q({'A': '以上都是', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'FAIL' in _sev(vo.check_r1_forbidden(q), 'R1')


def test_r1_absolute_words_warn():
    q = _q({'A': '必须立即手术', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'WARN' in _sev(vo.check_r1_forbidden(q), 'R1')


# ── R2 长度比 ──

def test_r2_ratio_over_2_fail():
    q = _q({'A': '短', 'B': '这是一个非常长的选项内容超过两倍长度阈值', 'C': '中', 'D': '中', 'E': '中'})
    assert 'FAIL' in _sev(vo.check_r2_length_ratio(q), 'R2')


def test_r2_ratio_15_to_2_warn():
    q = _q({'A': '短选项内容', 'B': '中等长度选项内容测试', 'C': '中等长度选项', 'D': '中等长度选项', 'E': '中等长度选项'})
    sev = _sev(vo.check_r2_length_ratio(q), 'R2')
    assert sev and sev[0] == 'WARN'


# ── R3 数值排序 ──

def test_r3_numeric_not_sorted_warn():
    q = _q({'A': '3ml', 'B': '1ml', 'C': '2ml', 'D': '5ml', 'E': '4ml'})
    assert 'WARN' in _sev(vo.check_r3_numeric_sort(q), 'R3')


# ── R4 否定词加粗 ──

def test_r4_negation_not_bolded_warn():
    q = _q({'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁', 'E': '戊'},
           stem='关于心衰的治疗，以下哪项不包括？')
    assert 'WARN' in _sev(vo.check_r4_negation_bold(q), 'R4')


# ── R5 选项数量 ──

def test_r5_a1_needs_five_options():
    q = _q({'A': '甲', 'B': '乙', 'C': '丙', 'D': '丁'})
    assert 'FAIL' in _sev(vo.check_r5_option_count(q), 'R5')


# ── R7 截断（batch006 教训）──

def test_r7_double_dot_residue_fail():
    q = _q({'A': '治疗..', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'FAIL' in _sev(vo.check_r7_truncation(q), 'R7')


def test_r7_severe_truncation_fail():
    q = _q({'A': '致.', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'FAIL' in _sev(vo.check_r7_truncation(q), 'R7')


# ── R8 最小长度 / 助词结尾（batch007 教训）──

def test_r8_ends_with_conjunction_fail():
    q = _q({'A': '该患者需要立即给予抗凝治疗的', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'FAIL' in _sev(vo.check_r8_min_length(q), 'R8')


def test_r8_number_without_unit_warn():
    q = _q({'A': '血压120', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'WARN' in _sev(vo.check_r8_min_length(q), 'R8')


# ── R9 缺单位（batch014 教训）──

def test_r9_clinical_param_missing_unit_fail():
    q = _q({'A': 'LVEF<40', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'FAIL' in _sev(vo.check_r9_missing_unit(q), 'R9')


def test_r9_with_unit_no_issue():
    q = _q({'A': 'LVEF<40%', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert vo.check_r9_missing_unit(q) == []


# v2.1 (2026-08-20 审查修复): FEV1/FVC 是无量纲比值，0.7/<0.7 是标准 COPD 诊断表述
# （此前 'FVC' 子串先命中 → 假 FAIL；本用例是修复的回归防线）

def test_r9_fev1fvc_ratio_no_false_positive():
    q = _q({'A': 'FEV1/FVC<0.7', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert vo.check_r9_missing_unit(q) == []


def test_r9_fev1fvc_ratio_without_comparator_no_false_positive():
    q = _q({'A': 'FEV1/FVC 0.7', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert vo.check_r9_missing_unit(q) == []


def test_r9_fev1fvc_other_param_still_detected():
    # 同一选项内 FEV1/FVC 比值豁免，但其他缺单位参数仍应被检出
    q = _q({'A': 'FEV1/FVC<0.7，PaO2<60', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    sev = _sev(vo.check_r9_missing_unit(q), 'R9')
    assert 'FAIL' in sev
    assert any('PaO2' in i['detail'] for i in vo.check_r9_missing_unit(q))


def test_r9_bare_fvc_still_fail():
    # 裸 'FVC'（非 FEV1/FVC 复合）后跟无量纲数值仍应报缺单位（FVC 以 L 计量）
    q = _q({'A': 'FVC<1.5', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'FAIL' in _sev(vo.check_r9_missing_unit(q), 'R9')


# ── R10 词重复线索（NBME D18）──
# 注: 强制 n-gram 关键词提取（_JIEBA_AVAILABLE=False），使用例不依赖 jieba 分词版本

def test_r10_exclusive_keyword_fail():
    vo._JIEBA_AVAILABLE = False  # 确定性 n-gram 模式
    q = _q({'A': '肺栓塞应给予抗凝治疗', 'B': '给予对症支持', 'C': '观察随访', 'D': '口服止痛药', 'E': '卧床休息'},
           stem='肺栓塞首选治疗是')
    assert 'FAIL' in _sev(vo.check_r10_clue_repetition(q), 'R10')


# ── R11 收敛策略（NBME D19）──

def test_r11_convergence_warn():
    vo._JIEBA_AVAILABLE = False  # 确定性 n-gram 模式
    # 正确选项命中 9 个题干词；其他选项 0-1 个 → avg_other=0.5, max_other=1
    # 9 > 0.5×2 且 9 > 1×1.5 → 收敛策略触发
    q = _q({'A': '急性肺栓塞首选溶栓治疗', 'B': '困难病例', 'C': '呼吸支持', 'D': '卧床休息', 'E': '随访观察'},
           stem='急性肺栓塞患者突发呼吸困难，首选治疗是')
    assert 'WARN' in _sev(vo.check_r11_convergence(q), 'R11')


# ── R12 无意义后缀（HC-6 修复）──

def test_r12_meaningless_suffix_fail():
    q = _q({'A': '肺栓塞抗凝治疗（相关表现）', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'FAIL' in _sev(vo.check_r12_meaningless_suffix(q), 'R12')


# ── R13 长度上限（防过度加长）──

def test_r13_single_option_over_20_fail():
    q = _q({'A': '这是一个超过二十个字符的选项内容确实太长了', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})
    assert 'FAIL' in _sev(vo.check_r13_length_ceiling(q), 'R13')


def test_r13_avg_over_18_warn():
    q = _q({'A': '选项内容平均长度超过十八个字触发整体偏长告警', 'B': '另一个同样长度的选项内容也超过十八个字', 'C': '第三选项的内容长度也超过十八个字的阈值', 'D': '第四选项内容同样超过十八个字的阈值长度', 'E': '第五选项内容依旧超过十八个字的阈值长度'})
    assert 'WARN' in _sev(vo.check_r13_length_ceiling(q), 'R13')


# ── 主引擎冒烟 ──

def test_validate_questions_smoke():
    questions = [_q({'A': '以上都是', 'B': '甲', 'C': '乙', 'D': '丙', 'E': '丁'})]
    all_issues, summary = vo.validate_questions(questions, mode='full')
    assert summary['total_questions'] == 1
    assert summary['fail'] >= 1  # R1 命中的 FAIL 被计入
