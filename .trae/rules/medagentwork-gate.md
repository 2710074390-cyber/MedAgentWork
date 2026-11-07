---
description: MedAgentWork 批次门禁与防跳过硬约束（始终生效；由 scripts/host_bootstrap.py 生成）
alwaysApply: true
---
<!-- medagentwork-host-stub v2 source=AGENTS.md sha256=92edd85ba21bfe8ab395dc20b655c2a3e0763c51ed3f8198635f9b6bb8e96a63 level=L1 -->
# MedAgentWork · 项目规则（路由，勿手改）

本文件只做路由，规则正文在仓库 `AGENTS.md` 与 `.dsh/skills/`。

1. **先读 `AGENTS.md`**：§1 决定读哪个角色 SKILL；§2 四条硬约束；§3 四个自检命令；§4 不要做的事；§5 推 main 走 PR。
2. 角色 SKILL 正文按路径直读：`.dsh/skills/medmaster/SKILL.md`、`medbatch`、`medgen`、`medqc`、`medfix`、`medreview`。
3. 这四条**不是纪律，是脚本判定**：
   - 门禁只能 `python scripts/batch_driver.py check --batch <id> --stage auto`（唯一执行面）
   - 产物与门禁执行字节绑定：改产物不重跑 → `ARTIFACT_MISMATCH`；伪造回执 → `CHAIN_BROKEN`
   - 消费上游前先验回执：`python scripts/gate_verify.py --batch <id> --stage <阶段> --quiet`
   - 提交前：`python scripts/gate_audit.py --staged --require-tracked`（hook 已装；该命令等价）
4. 动手前自检：`python scripts/host_bootstrap.py check`（exit 0 才继续）。
5. 宿主能力 `level=L1`：本宿主按 L1 顺序执行 —— 每阶段读 `中间产物/{batch}/_handoff/{stage}.json`，先重读 `_ctx.md` 复位上下文，再按 `inputs[].read` 限定的范围直读；不派生子代理、不并发写 `write_scope=question_bank` 的阶段。

重新生成：`python scripts/host_bootstrap.py install --hosts trae`
