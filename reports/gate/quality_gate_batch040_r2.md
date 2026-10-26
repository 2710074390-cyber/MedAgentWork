# 全流程质量门禁报告

> 批次：batch040 ｜ 阶段：r2 ｜ Profile：pilot ｜ 模式：advisory
> 结论：**WARN** ｜ 时间：2026-10-23T15:42:44

## 检查项

| 检查 | 状态 | 必需 | 说明 |
|---|---|---|---|
| r1.baseline | PASS | 是 | 基线冻结校验 PASS |
| r2.kc_registry | WARN | 是 | content_only 19/85=22.4% 超过 warn 阈值 |
| r2.item_learning_value | WARN | 是 | anchor verified=77.0% < warn |
| r2.scorecard | WARN | 是 | overall=3.63；warnings=13 |
| r2.review_items | PASS | 否 | 卡片 200（keypoint 125 / recall 75） |

## 阻断项

无。

## 警告/跳过

- content_only 19/85=22.4% 超过 warn 阈值
- anchor verified=77.0% < warn
- overall=3.63；warnings=13

## 说明

- 本报告由 `scripts/quality_gate.py` 生成，只读源产物与既有报告；不修改源题库/源复习资料/workflow_state。
- SKIP 不代表 PASS；enforce 模式下 required FAIL 会阻断发布。
