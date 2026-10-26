# Release v0.4.0-pilot · 质量基准与 batch040 试点基线

> 日期：2026-10-26 ｜ 类型：工程/治理 + 试点基线 ｜ **不是 batch040 内容发布**
> Tag：`v0.4.0-pilot` ｜ 目标环境：GitHub main + Cloudflare Pages（站点内容不变）

## 1. 发布范围

**纳入：**

- HC-25 全流程质量基准：`docs/质量管控规范.md`、`scripts/quality_policy.json`、`quality_policy.py`、`quality_gate.py`
- T1–T6 试点能力：基线冻结、KC 注册表/映射、题目学习价值层、12 维评分卡、advisory/enforce 门禁
- M3/T7–T10：200 张复习卡、SM-2 调度、Anki CSV、离线复习 HTML、答案对账报告
- HC-24/HC-25 规则回写：SOUL/CONTEXT/操作流程/medbatch 等 skill/提示词/CI
- batch040 试点证据：`中间产物/batch040/pilot/`、`reports/validate/`、`reports/gate/`
- 调研交付：`reports/research/medical-review-material-optimization-research-20261022/`

**不纳入：**

- batch041 内容：状态 `IN_PROGRESS`，`GATE-FINAL=BLOCKED`，不发布、不部署；WIP 快照归档在仓库，但不进入站点内容发布
- batch040 内容重发布：旧产物已 `APPROVED`，本次只固化试点工具与证据，不回改内容
- `中间产物/learning_value_raw/`：原始 API 响应，本地可重建，不入库
- 站点内容变更：`大四上/`、`大三下/`、`index.html` 等本次未改动；部署为同内容同步

## 2. 验证结果

| 项 | 结果 |
|---|---|
| 全量测试 | **142 passed / 0 failed / 0 errors** |
| quality policy | PASS（3 profiles / v1.0.0） |
| 基线冻结 | PASS |
| KC 注册表 | PASS（200/200 主映射；125/125 重点；content_only 19/85 记录） |
| 评分卡 | 3.63/5；ADVISORY_PASS；13 warnings；0 blocking |
| R0 需求评审 | PASS |
| R2 试点测试 | WARN（advisory，不阻断） |
| R3 正式发布 | **BLOCKED**（3.63<3.8；content_only 22.4%>15%；anchor 77%<80%） |
| 站点离线一致性 | PASS（本地文案/数据一致） |

## 3. 已知例外

- 7 道自测缺附录答案，集中在 M02；未编造，已记录在 `answer_reconciliation.md`，不进入复习队列。
- `content_only` 19/85（22.4%）：题库覆盖缺口，已逐卡记录；补题后目标 ≤15%。
- 教师版评分卡 3.63/5：仍低于正式发布 3.8 门槛，故 batch040 保持试点/已签收状态，不按新标准重新发布。
- batch041 `GATE-FINAL=BLOCKED`：WIP 数据快照归档在仓库，不进入站点内容发布。

## 4. 部署与回滚

- 部署通道：push `main` → GitHub Actions `Deploy to Cloudflare Pages`；站点白名单不变。
- 部署前：`quality_policy.py --validate` + `check_site_links.mjs`。
- 部署后：`check_site_freshness.py --expect-commit <HEAD>`；要求线上 Source 与本次提交一致。
- 回滚：以 `v0.4.0-pilot` 之前的 release commit（`dd60730`）为回退基线；站点内容未变，回滚风险低。
- 若 CI 部署失败：按 `scripts/deploy_site.ps1` 的 HC-21 规则处理，不本地抢先部署。

## 5. 版本锁定

- Git tag：`v0.4.0-pilot`（发布基线 commit）
- 仓库中的 WIP 数据快照仅作归档，不改变站点发布内容。
- 证据哈希见 `release_manifest.json`；tag 指向包含完整归档证据的 release commit。
