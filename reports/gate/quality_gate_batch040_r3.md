# 全流程质量门禁报告

> 批次：batch040 ｜ 阶段：r3 ｜ Profile：release_teacher_keypoint ｜ 模式：enforce
> 结论：**BLOCKED** ｜ 时间：2026-10-23T15:42:46

## 检查项

| 检查 | 状态 | 必需 | 说明 |
|---|---|---|---|
| r1.baseline | PASS | 是 | 基线冻结校验 PASS |
| r2.kc_registry | FAIL | 是 | content_only 19/85=22.4% 超过 block 阈值 |
| r2.item_learning_value | FAIL | 是 | anchor verified=77.0% < block |
| r2.scorecard | FAIL | 是 | overall=3.63 < 3.8 |
| r2.review_items | PASS | 否 | 卡片 200（keypoint 125 / recall 75） |
| r3.produce_rules | PASS | 是 | 产物形态门禁 PASS |
| r3.site_freshness | PASS | 是 | 站点一致性 PASS |
| r3.site_links | PASS | 是 | 站点链接 PASS |

## 阻断项

- content_only 19/85=22.4% 超过 block 阈值
- anchor verified=77.0% < block
- overall=3.63 < 3.8

## 警告/跳过

无。

## 说明

- 本报告由 `scripts/quality_gate.py` 生成，只读源产物与既有报告；不修改源题库/源复习资料/workflow_state。
- SKIP 不代表 PASS；enforce 模式下 required FAIL 会阻断发布。
