---
name: medgen
description: "MedGen 临床医学题库生成专家（Agent 2）。根据教材章节/输入素材生成结构化题库 JSON（纯数组）+ 备考资料，遵守 PG-01~HC-7 等全部出题硬约束、HC-22 真题双族配额（考研 1/5 + 执业医师 1/5，执医族内历年真题与 CMExam 双源均可直接入选）、HC-24 学习价值层（schema v2）、HC-27 概念标注（2.1 起）与 HC-29 干扰项协议（2.2 起，结构字段 + 机制标签），交付前必须通过 validate_options.py、check_learning_value.py 与 check_source_concepts.py 三道门禁自检（FAIL==0）。"
---
<!-- medagentwork-host-stub v2 source=.dsh/skills/medgen/SKILL.md sha256=7e66532dad8e6ae562834660dd48fca30d3b412293ad29e655e38294f2cf4c84 level=L2 -->
# medgen（宿主路由占位，勿手改）

本文件**只做路由**，不是规则正文；规则正文在仓库里：

1. 先读仓库根 `AGENTS.md`（唯一入口：§1 读什么 / §2 四条硬约束 / §3 四个自检命令 / §5 推 main 走 PR）。
2. 再按路径直读 `.dsh/skills/medgen/SKILL.md`（正文，按需读，不要整份读 SOUL.md / CONTEXT.md）。
3. 硬约束由**脚本**判定（batch_driver / gate_stamp / gate_audit），与提示词无关：
   跳过门禁 → 下游 preflight 拒收；改产物不重跑 → ARTIFACT_MISMATCH；未入库 → CI 红。
4. 动手前自检：`python scripts/host_bootstrap.py check`（exit 0 才继续）。
5. 宿主能力 `level=L2`：下游阶段按 `中间产物/{batch}/_handoff/{stage}.json` 执行（L2 派生隔离子代理 / L1 同会话顺序执行、每阶段重读 `_ctx.md` / L0 用 `batch_driver.py brief`）。交接包不含工具名，三种方式产出的门禁回执是同一份字节。

重新生成：`python scripts/host_bootstrap.py install --hosts workbuddy`
