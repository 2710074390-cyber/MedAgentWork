# -*- coding: utf-8 -*-
"""HC-26 复习资料详细度契约测试。"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))
import check_review_detail as crd  # noqa: E402

FACTS = [
    "该病的本质是局部组织缺血后炎症介质释放，毛细血管通透性升高，渗出液进入组织间隙，形成可逆性水肿。",
    "如果早期解除诱因，水肿可以完全吸收；一旦持续缺血超过临界时间，细胞坏死与纤维化便不可逆。",
    "因此治疗的第一目标是去除诱因，第二目标是减轻水肿，第三目标是阻止纤维化与功能丧失。",
    "典型场景是中年患者在受凉或劳累后出现单侧症状，伴轻度全身不适，但生命体征通常稳定。",
    "关键体征包括局部压痛、边界不清的肿胀与活动受限，阴性体征是神经系统检查正常。",
    "首选检查是高频超声，它可以区分积液、实变与血流信号；确诊金标准是增强影像或病理。",
    "实验室检查用于评估炎症程度与器官功能，不能单独作为确诊依据，也不能替代影像定位。",
    "处置原则是先稳定生命体征，再处理病因；有明确感染时选择覆盖常见致病菌的抗菌药物。",
    "出现脓肿、进行性呼吸困难或器官功能恶化时，应立即引流或转诊，不得继续门诊观察。",
    "与肿瘤鉴别时看病程与边界，与感染鉴别时看发热与炎症指标，与免疫病鉴别时看多系统受累。",
    "学生最易错的地方是把影像正常当成排除诊断，忽略早期病变在平扫上可能完全不显示。",
    "第二个易错点是只记住药名而不记疗程与禁忌，导致考试中遇到停药指征时无法判断。",
    "记忆钩子：先问“堵不堵”，再问“感染不感染”，最后问“要不要手术”，三步定处置。",
    "案例：52 岁男性，受凉后单侧肿痛 3 天，无发热，超声示液性暗区，血常规基本正常。",
    "该案例的下一步是穿刺抽液并送检，同时评估是否需要引流；不需要立即使用广谱抗生素。",
    "把上述链路反过来复述：诱因解除后水肿消退，水肿不退则纤维化，纤维化后功能受损。",
    "考试落点通常集中在首选检查、确诊金标准、手术指征与禁忌证四个位置，复习时优先背这些。",
    "最后用一句话压缩：这是“可逆的堵”，不是“不可逆的坏”，判断关键是时间窗与组织活力。",
]


def _card_body() -> str:
    return "\n".join([
        "<b>🎯 定位</b>：该病是局部组织缺血导致的可逆性水肿，位于体表软组织间隙。",
        "<b>🧬 机制</b>：" + FACTS[0] + FACTS[1],
        "<b>👁 识别</b>：" + FACTS[3] + FACTS[4],
        "<b>🔍 诊断</b>：" + FACTS[5] + FACTS[6],
        "<b>🩺 处置</b>：" + FACTS[7] + FACTS[8],
        "<b>⚖️ 鉴别</b>：",
        "| 鉴别轴 | 本病 | 肿瘤 | 感染 |",
        "|---|---|---|---|",
        "| 病程 | 数天 | 数周至数月 | 数天，伴发热 |",
        "| 边界 | 不清 | 较清 | 不清 |",
        "| 炎症指标 | 轻升 | 多正常 | 明显升高 |",
        "<b>🚨 易错</b>：" + FACTS[10] + FACTS[11],
        "<b>🧠 记忆钩子</b>：" + FACTS[12],
        "<b>🏥 案例</b>：" + FACTS[13] + FACTS[14],
        "<b>🔄 自测</b>：首选检查是什么？手术指征是什么？（答案见附录五）",
        FACTS[15] + FACTS[16] + FACTS[17],
    ])


def _doc(card_body: str | None = None, include_answer: bool = True) -> str:
    body = card_body if card_body is not None else _card_body()
    answer = "| 1 | 高频超声；脓肿或进行性呼吸困难时引流 | K-M01-001 |" if include_answer else ""
    return f"""# 测试科目 主复习资料

## 模块1：测试模块

### 🧩 前置知识检查

- 该区域由哪些层次构成？
- 血供来自哪条动脉？

### 🎯 30 秒摘要

1. 可逆性水肿，关键在时间窗。
2. 首选超声，确诊靠增强影像或病理。

### 📋 考点卡

#### 🔴 K-M01-001｜测试病（教师重点第1条｜P10）

📌 重点原文（第1条）：测试病应尽早评估，必要时在 2 周内处理。

{body}

### 📊 对比速查

| 项目 | 本病 | 对照病 |
|---|---|---|
| 病程 | 数天 | 数周 |
| 首选检查 | 超声 | CT |
| 处置 | 引流 | 手术 |

### 🔗 因果链

```text
诱因
  ↓
局部缺血
  ↓
水肿 → 纤维化
```

### 🏥 案例推演

52 岁男性，受凉后单侧肿痛 3 天，超声示液性暗区，下一步穿刺抽液。

### 📌 本章小结

- 先判断可逆性，再决定是否引流。

#### 🔬 展开：机制细节

缺血时间越长，纤维化越重。

#### 🔬 展开：数据补充

超声液性暗区的直径与引流指征相关。

## 附录五：主动回忆答案

### M01

| 题 | 答案 | 卡片 |
|---|---|---|
{answer}
"""


def _evaluate(doc: str, mode: str = "teacher_keypoint", profile: str = "release_teacher_keypoint"):
    cards, modules = crd.parse_cards(doc)
    units = crd.parse_schedule_units(doc) if mode == "course_schedule" else []
    th = crd.load_thresholds(profile, BASE / "scripts/quality_policy.json")
    report = crd.evaluate(cards, modules, units, mode, th, crd.selftest_answer_keys(doc))
    return cards, modules, units, report


def test_good_core_card_passes():
    cards, modules, _, report = _evaluate(_doc())
    assert len(cards) == 1 and len(modules) == 1
    assert cards[0]["tier"] == "core"
    assert report["cards"][0]["pass"], report["cards"][0]["deficits"]
    assert report["summary"]["status"] == "PASS", report["blocking"]
    assert report["summary"]["overall"] >= 0.9


def test_missing_diagnose_blocks_core():
    body = _card_body().replace(
        "<b>🔍 诊断</b>：首选检查是高频超声，它可以区分积液、实变与血流信号；确诊金标准是增强影像或病理。"
        "实验室检查用于评估炎症程度与器官功能，不能单独作为确诊依据，也不能替代影像定位。\n", "")
    _, _, _, report = _evaluate(_doc(card_body=body))
    card = report["cards"][0]
    assert "diagnose" in card["missing_slots"]
    assert report["summary"]["core_slot_ratio"] == 0.0
    assert report["summary"]["status"] == "FAIL"


def test_selftest_without_answer_fails():
    _, _, _, report = _evaluate(_doc(include_answer=False))
    assert report["cards"][0]["slots"]["selftest"] is False
    assert report["summary"]["selftest_answer_ratio"] == 0.0


def test_generic_v5_heading_parsed():
    doc = _doc().replace("#### 🔴 K-M01-001｜测试病（教师重点第1条｜P10）",
                         "#### 🔴 【掌握级】测试病（教师重点第1条｜P10）")
    cards, _, _, _ = _evaluate(doc)
    assert len(cards) == 1
    assert cards[0]["id"].startswith("C-M01-")
    assert cards[0]["tier"] == "core"


def test_module_without_case_or_expand_fails():
    doc = _doc()
    doc = doc.replace("### 🏥 案例推演\n\n52 岁男性，受凉后单侧肿痛 3 天，超声示液性暗区，下一步穿刺抽液。\n", "")
    doc = doc.replace("<b>🏥 案例</b>：案例：52 岁男性，受凉后单侧肿痛 3 天，无发热，超声示液性暗区，血常规基本正常。"
                      "该案例的下一步是穿刺抽液并送检，同时评估是否需要引流；不需要立即使用广谱抗生素。\n", "")
    doc = doc.replace("#### 🔬 展开：机制细节\n\n缺血时间越长，纤维化越重。\n", "")
    doc = doc.replace("#### 🔬 展开：数据补充\n\n超声液性暗区的直径与引流指征相关。\n", "")
    _, _, _, report = _evaluate(doc)
    m = report["modules"][0]
    assert "case" in m["missing_blocks"]
    assert "expand" in m["missing_blocks"]
    assert report["summary"]["module_block_ratio"] < 1.0


def test_course_schedule_requires_all_blocks():
    long_facts = "\n".join(FACTS * 2)
    unit = f"""## 第1周：耳科学基础（4 学时）

### 🎯 学习目标

- 掌握：传导性与感音神经性聋的鉴别。
- 熟悉：纯音测听与声导抗的判读。
- 了解：前庭功能检查的适应证。

### 🧩 课前准备

- 复习耳部解剖三层结构。
- 预习气导与骨导的区别。

### 📚 课堂重点

- 外耳、中耳、内耳的分区与功能。
- 传导性聋与感音神经性聋的听力学特征。
- 眩晕三病的时间轴鉴别。

### 🧬 机制

{long_facts}

### 🏥 案例

45 岁女性，感冒后右耳闷 2 周，鼓膜内陷，声导抗 B 型。

### 🔄 课后自测

- 气导下降而骨导正常提示哪类听力损失？
- 答案：传导性听力损失。

### ⏱ 时间预算

4 学时：讲授 3 学时，案例讨论 1 学时。

### ⏭️ 下周衔接

下周进入鼻科学，先复习鼻窦开口与引流。
"""
    cards, modules = crd.parse_cards(unit)
    units = crd.parse_schedule_units(unit)
    assert len(units) == 1
    th = crd.load_thresholds("release_teaching_plan", BASE / "scripts/quality_policy.json")
    report = crd.evaluate(cards, modules, units, "course_schedule", th, set())
    assert report["units"][0]["pass"], report["units"][0]["deficits"]
    assert report["summary"]["status"] == "PASS"


def test_course_schedule_missing_time_fails():
    doc = """## 第1周：测试（4 学时）

### 🎯 学习目标

- 掌握测试目标。

### 🧩 课前准备

- 预习。

### 📚 课堂重点

- 重点一。
- 重点二。
- 重点三。

### 🧬 机制

因为 A，所以 B。

### 🏥 案例

病例一例。

### 🔄 课后自测

- 问题？答案：回答。

### ⏭️ 下周衔接

下周继续。
"""
    units = crd.parse_schedule_units(doc)
    th = crd.load_thresholds("release_teaching_plan", BASE / "scripts/quality_policy.json")
    report = crd.evaluate([], [], units, "course_schedule", th, set())
    assert "time" in report["units"][0]["missing_blocks"]
    assert report["summary"]["status"] == "FAIL"
