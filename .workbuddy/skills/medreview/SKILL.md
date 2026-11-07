---
name: medreview
description: "MedReview 主复习资料生成器（Agent 5）。根据教师重点、课程安排、教材与其他可核实来源生成自适应复习资料，逐条锚定教师原文，区分来源补写并执行覆盖和导出自检。"
---
<!-- medagentwork-host-stub v2 source=.dsh/skills/medreview/SKILL.md sha256=d7d3ef9ae258d5523b8c3c9e6a36c3bea0a819146c17ef8c9b05ad387b736e77 level=L2 -->
# medreview（宿主路由占位，勿手改）

本文件**只做路由**，不是规则正文；规则正文在仓库里：

1. 先读仓库根 `AGENTS.md`（唯一入口：§1 读什么 / §2 四条硬约束 / §3 四个自检命令 / §5 推 main 走 PR）。
2. 再按路径直读 `.dsh/skills/medreview/SKILL.md`（正文，按需读，不要整份读 SOUL.md / CONTEXT.md）。
3. 硬约束由**脚本**判定（batch_driver / gate_stamp / gate_audit），与提示词无关：
   跳过门禁 → 下游 preflight 拒收；改产物不重跑 → ARTIFACT_MISMATCH；未入库 → CI 红。
4. 动手前自检：`python scripts/host_bootstrap.py check`（exit 0 才继续）。
5. 宿主能力 `level=L2`：下游阶段按 `中间产物/{batch}/_handoff/{stage}.json` 执行（L2 派生隔离子代理 / L1 同会话顺序执行、每阶段重读 `_ctx.md` / L0 用 `batch_driver.py brief`）。交接包不含工具名，三种方式产出的门禁回执是同一份字节。

重新生成：`python scripts/host_bootstrap.py install --hosts workbuddy`
