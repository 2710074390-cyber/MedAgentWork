# MedAgentWork 试点基线冻结报告

> 批次：batch040 ｜ 范围：耳鼻咽喉头颈外科学教师重点版（batch040） ｜ 生成：2026-10-23T15:18:00
> 用途：T1 基线冻结；任何源文件变动都会导致 `pilot_baseline.py verify` FAIL。

## 1. 输入文件

| 输入 | 路径 | SHA256（前 16 位） | 字节 | 行数 | 关键计数 |
|---|---|---|---:|---:|---|
| review | `复习资料/耳鼻咽喉头颈外科学教师重点版/耳鼻咽喉头颈外科学教师重点版_主复习资料.md` | `3ad51ee24f863922` | 204966 | 3119 | 85 卡 / 125 重点 / 82 自测 / 90 答案行 |
| questions | `最终产物/batch040/ALL_questions_FIXED.json` | `539bcd1947efa776` | 1058782 | - | 200 题 / 200 有引用 / 56 含补充引用 |
| keypoints | `输入素材/大四上/耳鼻咽喉头颈外科学/耳鼻咽喉头颈外科学_教师重点_锚定清单_20261019.md` | `7783751b0ec5f43c` | 179833 | 705 | 125 条 / 连续=True |
| blueprint | `中间产物/batch040/出题蓝图_batch040.md` | `919818002062927b` | 5474 | 87 | 200 题配额 / 7 模块 |
| learning_value | `中间产物/batch040/learning_value_v2/items_v2_progress.json` | `4b39fa30377ade66` | 1079328 | - | 200 题 / kc_id 12 题 / exact 200 |
| pilot | `中间产物/batch040/learning_value_pilot/item_v2_pilot.json` | `f6abb3f12c264afd` | 48426 | - | 12 题人工试点 |

## 2. 汇总

| 指标 | 数值 |
|---|---:|
| 复习资料卡片 | 85 |
| 教师重点条数 | 125 |
| 主动回忆题 | 82 |
| 附录答案行 | 90 |
| 题库题量 | 200 |
| 含补充引用题 | 56 |
| 锚定清单条目 | 125 |
| 出题蓝图配额 | 200 |
| 题目 v2 数据 | 200 |
| 人工试点样本 | 12 |

## 3. 复现

```bash
python scripts/pilot_baseline.py verify \
  --manifest "中间产物/batch040/pilot/baseline_manifest.json"
```

> 说明：本报告只记录结构计数与哈希，不评价内容质量；12 维评分见 `review_scorecard`。
