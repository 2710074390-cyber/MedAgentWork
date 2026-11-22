# -*- coding: utf-8 -*-
"""TKC v1.0（教师重点浓缩版）详细度门禁测试。"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "scripts"))
import check_review_detail as crd  # noqa: E402


def _doc(card_extra: str = "", repeat: bool = False) -> str:
    filler = (
        "正常时屏障完整，蛋白与细胞被挡在血管内；一旦炎症打破屏障，蛋白漏出形成闪辉，"
        "细胞漏出形成前房细胞，细胞沉积在角膜后表面形成 KP。如果屏障不破坏，就不会出现"
        "这一整套体征；恰恰是纤维素性渗出把虹膜粘在晶状体前表面，才形成后粘连并阻断房水通路。"
        "因此治疗的第一目标是扩瞳，第二目标是抗炎，第三目标是处理并发症。"
    )
    repeated = "\n\n本卡建议按定位到机制再到识别的顺序复习，每完成一遍遮住答案复述一次。" if repeat else ""
    return f"""# 测试科目 教师重点浓缩版

## 模块1：测试模块（M01）｜教师重点第1条｜约 20 分钟

### 🧩 前置知识检查

1. 屏障由什么构成？
2. 细胞从哪里漏出？

### 🎯 高收益摘要

- 前房细胞比闪辉更能代表活动炎症〔第1条〕。

### 📋 结构化笔记

#### 🔴 【掌握级】测试病（第1条｜P10）

📌 重点原文（第1条）：测试病：典型表现与处理

测试病是用于验证浓缩型结构的虚构疾病，核心是屏障破坏后蛋白与细胞进入前房（教材P10）。{card_extra}

💡 <b>为什么重要</b>：它决定首选检查与首选处理，是病例题的分水岭。

🧬 第一性原理：{filler}{filler}

临床表现是眼红、眼痛与瞳孔缩小；首选检查是裂隙灯，首选处理是扩瞳与抗炎。

#### 🔬 展开：体征细节

- 尘状 KP 多见于非肉芽肿性炎症。
- 羊脂状 KP 多见于肉芽肿性炎症。

> [!WARNING] 易错陷阱
> 把闪辉当活动炎症是经典错误，真正可靠的是前房细胞。

| 鉴别轴 | 本病 | 鉴别病 |
|---|---|---|
| 瞳孔 | 缩小 | 散大 |
| 前房细胞 | 有 | 无 |

> [!TIP] 记忆提示
> 记「小瞳孔、有细胞、眼压不高」。

> [!NOTE] 范围说明
> 本测试文档只用于门禁验证，不构成医学建议。

#### 🔬 展开：第二处细节

治疗先扩瞳，再抗炎，最后处理并发症。

| 步骤 | 动作 |
|---|---|
| 第一步 | 扩瞳 |
| 第二步 | 抗炎 |

### 🧠 因果链：屏障到体征

```
屏障破坏 → 蛋白漏出 → 闪辉
        ↓
      细胞漏出 → KP
```

> [!INFO] 临床含义
> 抗炎越早，后粘连越少。

### 🔄 主动回忆

1. 反映活动炎症的指标是什么？《前房细胞》
2. 首选处理是什么？《扩瞳与抗炎》
{repeated}
"""


def _evaluate(doc: str):
    cards, modules = crd.parse_cards(doc)
    th = crd.load_thresholds("release_teacher_keypoint_condensed", BASE / "scripts/quality_policy.json")
    return crd.evaluate_condensed(cards, modules, th, doc)


def test_condensed_card_without_nine_slots_passes():
    report = _evaluate(_doc())
    assert report["summary"]["cards"] == 1
    assert report["cards"][0]["tier"] == "core"
    assert report["cards"][0]["pass"], report["cards"][0]["deficits"]
    assert report["cards"][0]["short_anchor"] is True
    assert any("主题名" in w for w in report["warnings"])
    assert report["summary"]["status"] == "PASS", report["blocking"]


def test_condensed_missing_first_principle_fails():
    doc = _doc().replace("🧬 第一性原理：", "机制说明：")
    report = _evaluate(doc)
    assert "first" in report["cards"][0]["missing_slots"]
    assert report["summary"]["status"] == "FAIL"


def test_condensed_template_repetition_fails():
    doc = _doc(repeat=True).replace(
        "本卡建议按定位到机制再到识别的顺序复习，每完成一遍遮住答案复述一次。",
        "考试落点：本题组常以 A1 考定义、分型、首选检查或首选处理，以 A2 考典型病例。")
    doc = doc.replace("### 🔄 主动回忆", ("考试落点：本题组常以 A1 考定义、分型、首选检查或首选处理，以 A2 考典型病例。\n\n" * 8) + "### 🔄 主动回忆")
    report = _evaluate(doc)
    assert report["template_repetition"]["max_repeat"] >= 8
    assert report["summary"]["status"] == "FAIL"
    assert any("模板" in x or "禁用模板句" in x for x in report["blocking"])


def test_condensed_module_without_recall_fails():
    doc = _doc().replace("### 🔄 主动回忆", "### 课后练习")
    report = _evaluate(doc)
    assert "recall" in report["modules"][0]["missing_blocks"]
    assert report["summary"]["status"] == "FAIL"


def test_condensed_missing_page_fails():
    doc = _doc().replace("（教材P10）", "（教材）")
    report = _evaluate(doc)
    assert "page" in report["cards"][0]["missing_slots"]
    assert report["summary"]["status"] == "FAIL"
