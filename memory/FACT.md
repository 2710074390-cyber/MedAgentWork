# FACT — MedAgentWork 历史教训与已闭环政策

> 维护：任何 Agent 完成任务后追加一行；**≤60 行**，超限先合并同类项。
> 本文件**不复制** SOUL 的 HC 正文（铁律④）：规则原文以 `SOUL.md` 为准，这里只记「哪个坑、怎么踩的、怎么防」。
> 待办见 `memory/TODO_ACTIVE.md`；历史待办见 `docs/archive/2026-11/TODO.md`（已归档，不再追加）。

## 1. 当前状态（2026-11-04）

- 最新批次：**batch047**（急诊与灾难医学，50 题，APPROVED 并归档）；**batch048 未启动**。
- 规模：41 个 batch 键 / 注册表 **6,640 题** / 门禁脚本 17 个 / 测试 **594 通过 · 5 跳过**。
- 调度层改造进行中：`reports/实施步骤与验收标准_调度与上下文层_20261104.md`（阶段 A→B→C）。

## 2. 已闭环政策（不要再推翻）

- **2026-11-05**：门禁回执链（自 batch048 起强制）。PASS 才写回执（`最终产物/{batch}/_gate_ledger.json`），回执把「产物字节 sha256 + 门禁证据 sha256」按 `chain_prev` 链式绑定；下游 boundary 先验上游回执（verify-before-consume），跳过阶段 → `BLOCKED`；CI `batch-gate` job 对改动批次跑 `gate_audit.py --recheck`。历史批次（≤047）不追溯、只告警。
- **2026-11-05**：P1 消费方验真落地。worker SKILL 首节（`## 0.`）先跑 `gate_verify.py`：medqc←a2、medfix←a3、medreview←a4/lv；`deploy.yml` 发布前追加 `gate_audit --changed-only --recheck`（fail-closed，checkout 需 `fetch-depth: 2`）。**medgen 无上游回执可验**：r0/r1 是 advisory 门禁，WARN 不写回执，拿它当强制前置会把正常批次卡死（batch046 的 r0 实测 WARN）。`gate_verify` 对不属于本批计划的阶段返回 `SKIP NOT_APPLICABLE`（exit 0，机械判定，不需要 Agent 自己看 product_types）。**worker 侧验真只是尽早失败，真防线仍是 driver preflight + audit 复检。**
- **2026-11-05 入库政策（用户裁定）**：历史批次（≤047）**不回填**；**batch048 起签收后「产物 + 回执链」必须入库**。清单真源是 `scripts/batch_artifacts.py` 的白名单（回执链 / FIXED.json / A4 追溯日志 / review_queue + 交付件），`_backup/`、`*.html`、`*.tmp` 不入库。顺序：签收 → 重建 A4 追溯日志 → 重跑 A4/FINAL → `batch_artifacts.py stage` → `check` exit 0 → 归档。**先入库后重建回执 = 提交一份产物与回执对不上的证据。** CI 与 deploy 均带 `--require-tracked`，未入库判 `ARTIFACT_UNTRACKED`。
- **2026-11-05 P2 提交拦截**：`gate_audit.py` 新增 `--staged`（读 `git diff --cached`，**不能复用 `--changed-only` 的 `HEAD~1`**——pre-commit 时提交还没发生）。本机 `.git/hooks/pre-commit` 由 `scripts/install_git_hooks.py` 写入（零依赖，不依赖 pre-commit 框架；框架版配置在 `.pre-commit-config.yaml` 的 `batch-gate-staged`，两者择一）。⚠️ **`git` 输出中文路径必须加 `-c core.quotepath=false`**，否则批次解析全落空、审计静默跳过（`git_changed_paths` 同样已修）。
- **2026-11-03**：取消「逐题人工医学核验」作为发布前置；A/B + 确定性门禁通过即 `publishable`，人工只处理 C 级/高风险/明确冲突，且只入队列、不阻断。
- **2026-11-03**：上架版权（license）不再作门禁，仅作来源记录（`public_gate` G0/G3 恒 INFO）。
- **2026-11-02**：插图管线（HC-19）整体下线；复习资料为纯文本，不出配图清单/占位符。
- **历史批次不追溯**（batch043–047 只读）；新规则自 batch048 起生效。

## 3. 高频坑（按踩坑次数排序）

- **门禁读不到自报字段 → 误判 BLOCKED**（batch040）：`bloom_distribution.actual` 必须是百分数扁平形态；`source_file_synced` 必须在追溯日志**顶层**；📌 重点原文条号取锚定清单**第四节连续编号**（不是印刷标号）。
- **补丁不溯源 → 下次合并回归**（batch014）：修复聚合文件必须同步源文件，追溯日志写 `source_file_synced: true`。
- **输出混入非 JSON → 解析失败**（batch006）：题库 JSON 必须是**纯数组**，禁止 YAML frontmatter；修改声明单独成文件。
- **选项截断 / 缺单位**（batch007/batch014）：禁止 `text[:n]` 暴力截断；数值选项必须带完整单位；自然短术语（药名/受体）豁免长度下限。
- **转述失真**（2026-11 起）：主会话**不读产物正文、不摘要转述**；交接只传「路径 + 断言命令」，下游按路径直读。
- **证据靠路径**（2026-11）：`reports/` 被 gitignore、归档会搬走产物目录；跨阶段引用用「批次号 + 文件角色」，不要只记绝对路径。
- **按文件名白名单认证据必漏**（2026-11）：追溯日志真实命名两种（`AGENT4_追溯日志.json` / `{batch}_A4_追溯日志.json`），`*A4_追溯日志.json` 匹配不到前者；押题卷产物名也不固定。证据归属改由**回执绑定**决定（`batch_artifacts.ledger_bound_paths`），白名单只做兜底。
- **「写了规则」≠「会执行」**（2026-11）：提示词/纪律是建议，不是约束。要让别的 Agent 不跳门禁，只能靠三层：产物带回执（`gate_stamp.py`）、下游拒收（`batch_driver` preflight）、中央审计变红（`gate_audit.py` + CI）。`--no-preflight`/`--no-stamp` 是调试口子，用了一定在 payload 留痕。

## 4. 长期有效的小坑

- **Windows 控制台 GBK**：脚本输出中文/emoji 需 UTF-8 兜底，否则命令「时红时绿」。
- **`reports/` 不入库**：验收证据可落 `reports/`，但 schema / 脚本 / 测试 / 夹具**必须入库**。
- **schema 与 gate 同源**（2026-11-05）：gate_check 强制的字段必须在 `schemas/agent2_output.schema.json` 声明（枚举与 `gate_check.P9_MODES` 一致）。曾出现 schema 删 `p9_mode` 而 gate 仍判 BLOCKED 的脱节；`tests/test_schemas.py::test_p9_mode_declared_and_matches_gate_check` 已锁。
- **`docs/` 活跃文档 ≤5**（铁律⑦）：新计划/证据一律放 `reports/`（本文件与待办板属 `memory/`，不受该限制）。
- **门禁「参考模式」**：APPROVED 批次重跑门禁只作参考、不写 HALT（`gate_check.py:2276-2282`）；改动门禁时别把参考模式当 PASS 证据。
