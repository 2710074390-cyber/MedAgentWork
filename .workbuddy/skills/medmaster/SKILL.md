---
name: medmaster
description: "MedMaster 临床医学题库工作流主控编排器（Agent 1）。解析用户\"开始新批次/继续/终审\"意图，按交接包编排 MedGen→MedQC→MedFix→MedReview 五阶段管线（HC-19 生图阶段已下线，不出配图），并在每个阶段转换时通过 `batch_driver.py`（唯一执行面）强制门禁；宿主能力由入口桩 `level=` 声明，DSH / WorkBuddy / Trae / 人工消费同一份包。"
---
<!-- medagentwork-host-stub v2 source=.dsh/skills/medmaster/SKILL.md sha256=580e0168437929b81a0bacdc43c9fc42b4166b9d1687716fbaf6407ca0189714 level=L2 -->
# medmaster（宿主路由占位，勿手改）

本文件**只做路由**，不是规则正文；规则正文在仓库里：

1. 先读仓库根 `AGENTS.md`（唯一入口：§1 读什么 / §2 四条硬约束 / §3 四个自检命令 / §5 推 main 走 PR）。
2. 再按路径直读 `.dsh/skills/medmaster/SKILL.md`（正文，按需读，不要整份读 SOUL.md / CONTEXT.md）。
3. 硬约束由**脚本**判定（batch_driver / gate_stamp / gate_audit），与提示词无关：
   跳过门禁 → 下游 preflight 拒收；改产物不重跑 → ARTIFACT_MISMATCH；未入库 → CI 红。
4. 动手前自检：`python scripts/host_bootstrap.py check`（exit 0 才继续）。
5. 宿主能力 `level=L2`：下游阶段按 `中间产物/{batch}/_handoff/{stage}.json` 执行（L2 派生隔离子代理 / L1 同会话顺序执行、每阶段重读 `_ctx.md` / L0 用 `batch_driver.py brief`）。交接包不含工具名，三种方式产出的门禁回执是同一份字节。

重新生成：`python scripts/host_bootstrap.py install --hosts workbuddy`
