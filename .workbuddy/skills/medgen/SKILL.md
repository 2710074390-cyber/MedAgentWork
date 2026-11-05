---
name: medgen
description: "MedGen 临床医学题库生成专家（Agent 2）。根据教材章节/输入素材生成结构化题库 JSON（纯数组）+ 备考资料，遵守 PG-01~HC-7 等全部出题硬约束、HC-22 真题双族配额（考研 1/5 + 执业医师 1/5，执医族内历年真题与 CMExam 双源均可直接入选）、HC-24 学习价值层（schema v2）、HC-27 概念标注（2.1 起）与 HC-29 干扰项协议（2.2 起，结构字段 + 机制标签），交付前必须通过 validate_options.py、check_learning_value.py 与 check_source_concepts.py 三道门禁自检（FAIL==0）。"
---
<!-- medagentwork-host-stub v1 source=.dsh/skills/medgen/SKILL.md sha256=f0ee8ac2fbc990e7bd45092e9deeb5b5e8399cb5a541b41f99015ee30e379a09 -->
# medgen（宿主路由占位，勿手改）

本文件**只做路由**，不是规则正文；规则正文在仓库里：

1. 先读仓库根 `AGENTS.md`（唯一入口：§1 读什么 / §2 四条硬约束 / §3 四个自检命令 / §5 推 main 走 PR）。
2. 再按路径直读 `.dsh/skills/medgen/SKILL.md`（正文，按需读，不要整份读 SOUL.md / CONTEXT.md）。
3. 硬约束由**脚本**判定（batch_driver / gate_stamp / gate_audit），与提示词无关：
   跳过门禁 → 下游 preflight 拒收；改产物不重跑 → ARTIFACT_MISMATCH；未入库 → CI 红。
4. 动手前自检：`python scripts/host_bootstrap.py check`（exit 0 才继续）。

重新生成：`python scripts/host_bootstrap.py install --hosts workbuddy`
