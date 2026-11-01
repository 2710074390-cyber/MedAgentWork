# MedAgentWork 试点基线冻结报告

> 批次：batch043 ｜ 范围：耳鼻咽喉头颈外科学教师重点版（batch040） ｜ 生成：2026-10-27T00:33:11
> 用途：T1 基线冻结；任何源文件变动都会导致 `pilot_baseline.py verify` FAIL。

## 1. 输入文件

| 输入 | 路径 | SHA256（前 16 位） | 字节 | 行数 | 关键计数 |
|---|---|---|---:|---:|---|
| review | `复习资料/急诊与灾难医学教师重点版/急诊与灾难医学教师重点版_BPA_主复习资料.md` | `79b8b7d64c8f3e57` | 150440 | 1988 | 48 卡 / 61 重点 / 0 自测 / 0 答案行 |
| questions | `最终产物/batch043/ALL_questions_FIXED.json` | `9c669c9a868e7c0c` | 792738 | - | 200 题 / 200 有引用 / 0 含补充引用 |
| keypoints | `输入素材/大四上/急诊与灾难医学/急诊与灾难医学_教师重点_锚定清单_20261026.md` | `54529a56dfc6ee6a` | 21871 | 117 | 0 条 / 连续=True |
| blueprint | `中间产物/batch043/出题蓝图_batch043.md` | `fce419a117ca0733` | 1866 | 40 | 200 题配额 / 8 模块 |
| learning_value | `reports/validate/learning_value_batch043.json` | `0f7bc74fc8817b98` | 112884 | - | 4 题 / kc_id 0 题 / exact 0 |
| pilot | `中间产物/batch043/pilot/kc_registry.json` | `5f0746947a22d4c6` | 34663 | - | 7 题人工试点 |

## 2. 汇总

| 指标 | 数值 |
|---|---:|
| 复习资料卡片 | 48 |
| 教师重点条数 | 61 |
| 主动回忆题 | 0 |
| 附录答案行 | 0 |
| 题库题量 | 200 |
| 含补充引用题 | 0 |
| 锚定清单条目 | 0 |
| 出题蓝图配额 | 200 |
| 题目 v2 数据 | 4 |
| 人工试点样本 | 7 |

## 3. 复现

```bash
python scripts/pilot_baseline.py verify \
  --manifest "中间产物/batch040/pilot/baseline_manifest.json"
```

> 说明：本报告只记录结构计数与哈希，不评价内容质量；12 维评分见 `review_scorecard`。
