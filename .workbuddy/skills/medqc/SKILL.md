---
name: medqc
description: "MedQC 临床医学题库质量检测官（Agent 3）。对 Agent 2 产物按 D1-D24 维度矩阵质检，输出结构化 JSON 质检报告（含 gate_decision、dimensions、bloom_distribution、learning_value_summary），对照 GoldenSet 与教材做交叉验证；D22 已随 HC-19 下线（恒 N/A，编号保留不复用）、D23/D24 学习价值层与来源逐字性（HC-24）强制。"
---
<!-- medagentwork-host-stub v2 source=.dsh/skills/medqc/SKILL.md sha256=f84b8768b0f6b727887b79c951368ed5b26db034d36a6371c7a56e6b69036002 level=L2 -->
# medqc（宿主路由占位，勿手改）

本文件**只做路由**，不是规则正文；规则正文在仓库里：

1. 先读仓库根 `AGENTS.md`（唯一入口：§1 读什么 / §2 四条硬约束 / §3 四个自检命令 / §5 推 main 走 PR）。
2. 再按路径直读 `.dsh/skills/medqc/SKILL.md`（正文，按需读，不要整份读 SOUL.md / CONTEXT.md）。
3. 硬约束由**脚本**判定（batch_driver / gate_stamp / gate_audit），与提示词无关：
   跳过门禁 → 下游 preflight 拒收；改产物不重跑 → ARTIFACT_MISMATCH；未入库 → CI 红。
4. 动手前自检：`python scripts/host_bootstrap.py check`（exit 0 才继续）。
5. 宿主能力 `level=L2`：下游阶段按 `中间产物/{batch}/_handoff/{stage}.json` 执行（L2 派生隔离子代理 / L1 同会话顺序执行、每阶段重读 `_ctx.md` / L0 用 `batch_driver.py brief`）。交接包不含工具名，三种方式产出的门禁回执是同一份字节。

重新生成：`python scripts/host_bootstrap.py install --hosts workbuddy`
