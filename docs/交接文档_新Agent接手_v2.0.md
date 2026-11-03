# MedAgentWork 交接文档 —— 新 Agent 快速上手（v2.0 · 2026-11-02）

> **读者**：接手本项目的任何 Agent（Claude Code / Cherry Studio / Cursor / 其他 harness 均可）。
> **用法**：本文档作为新 Agent 的第一份上下文；先读 §1，再按 §9 的 Checklist 执行。
> **上一版**：`docs/archive/2026-11/交接文档_新Agent接手_v1.0.md`（2026-09-04，生产流程与资源清单仍有效，本文档不重复其内容，只写**变化**与**新坑**）。
> **一句话**：v1.0 教你怎么**生产**；v2.0 记录的是把"生产"变成"**可验证的生产**"——规则有了单一事实来源，门禁有了自测，修复有了 no-op 检测，合规有了暴露面数字。

---

## 1. 30 秒速览

### 1.1 位置与基线

| 项 | 值 |
|---|---|
| 工作区 | `C:\Users\38063\Desktop\MedAgentWork`（Windows，中文路径，命令加英文双引号） |
| Python | 默认 `python` 现为 **3.12.10（有 jsonschema/numpy）**；3.13 在 `C:/Users/38063/.workbuddy/binaries/python/versions/3.13.12/python.exe`（无这些依赖）；torch 系用 Python312 |
| 测试基线 | **两种解释器口径不同，都要看**（数字随新增用例增长，**不变量是 0 失败 / 0 错误**）：<br>① 默认 `python` 3.12.10（**有** jsonschema+numpy）→ 2026-11-03 实测 **422 通过 / 0 失败 / 0 错误 / 61 跳过**<br>② 3.13（`.workbuddy`，**无** jsonschema/numpy）→ **386 通过 / 0 失败 / 0 错误 / 97 跳过** |
| 规则注册表 | **74 条**（hard 57 / soft 10 / process 7），lint `exit 0`，硬规则检测器覆盖 **98.2%** |
| 题库注册表 | **6,640 题**（`question_bank/registry_meta.json`，含 batch047 +50） |
| 本轮改动 | **未提交 git**（working tree 55 项，含本轮新增文档；提交前先看 §9 第 6 步） |

### 1.2 阶段 0 完成情况（本轮交付）

| 线 | 内容 | 状态 |
|---|---|---|
| P1 知识治理 | 规则注册表 / lint 与渲染 / 配置 SSOT / schema fail-loud / lineage 五元组 | ✅ AC-P1-01~07 通过（06 由 batch047 闭合，2026-11-03） |
| P5 修复闭环 | 重试隔离 / patch 契约 / diff 审计 / no-op 检测 | ✅ AC-P5-01~05 |
| P6 可观测 | 按批遥测 / 指标聚合 / 黄金缺陷集 / 策略动作 | ✅ AC-P6-01~05 |
| P2 题目质量 | schema v2.2 / HC-29 干扰项协议 / X1·X2·X6 批次门禁 | ✅ 01·02·03·04 通过（02/04 由 batch047 闭合，2026-11-03） |
| P3 评估证据 | 50 题回填 / κ·ICC·BA / 7 维 rubric / 措辞核查 | ⚠️ 原清单 BLOCKED；κ 单评分者 BLOCKED；措辞 PASS |
| P8 合规 | license matrix / 公开风险清单 | ✅ AC-P8-02、03；01 按"显式授权 29.3%"如实报 |

**下一步第一优先**：batch047 已**签收并归档**（`status=APPROVED`，50 题 `publishable`、`release_status=READY`），四道门禁全 PASS。交付物已移入 **`archive/最终产物/batch047/`**（`ALL_questions_FIXED.json/.md`、`batch047_A4_追溯日志.json`、`A4_补丁明细.json`、`batch047_医师试读卷.md`、`batch047_签收单.md`、`review_queue.json`，签收/修复前备份在 `_backup/`），源文件与质检报告分别在 `archive/中间产物/batch047/`、`archive/质检报告/batch047/`；路径映射见 **`archive/batch047_归档说明.md`**。证据见 `reports/implementation/batch047_验收证据_20261103.md`（§7 A4、§8 签收）。**接力点只剩一件**：若要满足 AC-P3-02，需第二位医师独立评分算 κ。

---

## 2. 这一轮改了什么（按能力组织，不按任务号）

### 2.1 规则有了单一事实来源

`rules/registry.yaml`——74 条规则的唯一清单，覆盖 R1–R20、S1–S4、B1、JS1、**X1/X2/X6/S-STRUCT**、10 个 GATE、20 条 HC、quality_policy 绑定、config_keys。

```bash
python scripts/render_rules.py --check --coverage   # 门禁口径：exit 0
python scripts/render_rules.py --write              # 只渲染到 reports/registry/rendered/，不改 SOUL/提示词
```

lint 的关键不是格式，是 **L6**：用 AST 验证 detector 指向的函数/标签**真实存在**。写一个不存在的检测器，立刻报错——这是"注册表说有、代码里没有"的唯一有效防线。

**改规则的姿势**：先改注册表条目 → 再改 detector 指向的实现 → 跑 `--check` → 跑 `run_tests.py`。**不要**先改代码再补登记。

### 2.2 配置有了单一事实来源

`scripts/pipeline.yaml` 的顶层 `thresholds:` 段。读取入口 `scripts/pipeline_config.py`。

```bash
python scripts/pipeline_config.py --print-config            # 打印生效阈值 + config_hash
python scripts/pipeline_config.py --key option_length_max   # 单键
```

⚠️ 只能用**扁平 `key: value`** 写法：未装 PyYAML 的环境走内置最小解析器，嵌套结构会被忽略。

### 2.3 版本血缘五元组

`prompt_sha256 / model_id / config_hash / input_hash / artifact_sha256`，记录在 `workflow_state.json` 的 `lineage[]`。

- 写入口 `scripts/workflow_state.add_lineage(strict=...)`：`strict=None` **不按批次号自动开闸**（否则历史批次与旧测试夹具全被打断），强制点放在 `ingest.py`（显式传 strict）与 `gate_check._lineage_issues`（batch047+）。
- `'unknown'` 一律视为**缺失**——这是消灭 `prompt_version=unknown` 的关键。
- 历史批次 ≤046：`SKIP`，只读体检、不追溯。

### 2.4 修复不再能"假装修好"

`scripts/check_patch_integrity.py`：

```bash
python scripts/check_patch_integrity.py --before A.json --after B.json --tag batch0XX --noop --stats
```

- **不可变字段**：`id / answer / teacher_anchor / source_* / keypoint_ref / license`…；命中真题标记的题干也一并不可变。
- **`--declared` 不能豁免不可变字段**：声明"我要改答案"照样判违例。
- **no-op 检测**：前后文件 sha256 相同 → 直接 `NOOP`，退出码 1。

### 2.5 重试与隔离

`workflow_state.record_retry / is_quarantined / clear_quarantine / retry_summary`。

单题 >2 次 → 该题 QUARANTINE；整批 >3 次 → 整批 QUARANTINE（覆盖题目级）。阈值在 `thresholds.retry_item_max / retry_batch_max`。放行必须留痕（`clear_quarantine(by=..., reason=...)`）。

### 2.6 能看到自己在干什么

- `scripts/telemetry.record_event(batch, event, **fields)` → `reports/obs/<batch>_telemetry.jsonl`；**18 字段白名单**，出现 `user_id` / `session_id` 直接拒收（不是静默丢）。
- `python scripts/aggregate_metrics.py --backfill` → SQLite + `reports/obs/metrics_20261102.json`。
- `python scripts/gate_selftest.py` → 黄金缺陷集（10 类 × 3 例 + 5 好题）跑门禁，输出检出率/误报率。

### 2.7 题目质量有了结构字段

schema **v2.2**：`difficulty_tier`(L1–L4) / `step_count`(1–8) / `competing_dx` / `negative_cues` / `conditionals` + `per_option.distractor_mechanism`(8 枚举)；`difficulty_index` 标 deprecated。

```bash
python scripts/validate/rules_batch.py --file x.json            # X1/X2/X6 + S-STRUCT（advisory）
python -m scripts.validate --file x.json --batch-mode           # 同入口，顺带落 reports/validate/<batch>_batch_rules.md
```

### 2.8 评估与合规

| 脚本 | 作用 | 现在的真实结果 |
|---|---|---|
| `scripts/review_sample.py` | 分层抽 50 题 + 7 维机器代理分 | 新样本 50/50；专家列全 `BLOCKED` |
| `scripts/agreement.py` | 加权 κ / ICC(2,1) / Bland–Altman | **BLOCKED**（单评分者，κ=None） |
| `scripts/check_wording.py` | 实测类宣称 + 无据结论 | PASS（越界 0/20） |
| `scripts/license_matrix.py` | 逐题权利盘点 | 2747 题 / 真题 376 / 显式 license 29.3% |
| `scripts/public_risk.py` | 哪些文件带 unclear 真题 | 公开站 0；可部署 7 个文件 |

---

## 3. 五个必读坑位（踩过才知道）

### 坑 1：`scripts/validate/contracts.py` 不是校验器

它是**纯常量文件**（67 行，`grep schema` 零命中）。工作指令 §P1-S4 把它当成 schema 校验落点，是写错了。真正的静默放行在 `ingest.py:validate_schema` 的 `except Exception: return []`——已改成四分支显式化（缺契约=SKIP 留痕 / 解析失败=FAIL / 缺库=降级留痕或 strict FAIL / 校验器异常=FAIL）。

### 坑 2：`pipeline.yaml` 曾经是死配置

改之前 `pipeline_config.PIPELINE_YAML` 指向**仓库根**（文件不存在），而真实文件在 `scripts/`，且**没有顶层 `thresholds:` 段** → 所有阈值一直走 `DEFAULTS`。现在路径指向同目录、段已补、取值严格等于 `DEFAULTS`，所以 `overridden_keys=[]`、行为零变化。

**推论**：以后看到"某个阈值好像不生效"，第一件事是 `--print-config` 看它到底读到了什么。

### 坑 3：`run_tests.py` 把 ImportError 记成"错误"，不是跳过

`tests/test_learning_value.py` 曾因只把 `scripts/` 放进 `sys.path`、没放仓库根，**单文件跑必炸**（全量跑时靠前一个测试文件的 `sys.path.insert` 副作用才侥幸通过）。已补 `sys.path.insert(0, str(ROOT))`。

**推论**：单文件跑测试是必须能过的；如果"全量过、单跑炸"，说明有路径副作用，别用全量跑当通过证据。

### 坑 4：`aggregate_metrics --backfill` 必须幂等

第一版没有清旧数据，跑两次事件从 87 堆到 261。现在先删 `source=backfill` 再重推，live 事件保留。**推论**：任何"从历史产物反推"的脚本，都要问一句"跑两次会怎样"。

### 坑 5：Windows 上 `Path('/tmp/x')` 会落到 `C:\tmp`

Git Bash 的 `/tmp` 与 Python 看到的不一样。脚本输出一律用**仓库内相对路径**（`reports/...`），不要写 `/tmp`。

### 附：两个"看起来像 bug 其实不是"

- **两个 `max_chars` 不冲突**：18 是生成目标（`prompt_constraints.option_length.max_chars`），20 是 R13 校验上限（`option_length_max`）。注册表用 `distinct_from` 显式声明，lint 只抓未声明的重复约束。
- **X6 在两批都是 0% 不是脚本坏了**：batch043 有 645 个 `misconception_id`、645 个全不同；batch046 是 400/400。历史标签体系本来就不支持复用——这正是 P9 概念层多标签率上不去（急诊 4.9%）的根因。

---

## 4. 怎么判断"绿"（不要只看 exit code）

| 检查 | 命令 | 期望 |
|---|---|---|
| 单元/回归 | `python scripts/run_tests.py` | 421 通过 / 0 失败 / **0 错误** / 52 跳过 |
| 同上（3.13，无依赖） | `.workbuddy/.../3.13.12/python.exe scripts/run_tests.py` | 385 通过 / 0 失败 / **0 错误** / 88 跳过 |
| 规则一致性 | `python scripts/render_rules.py --check` | exit 0，warn ≤1（HC-18-FORM 语义项） |
| 配置可读 | `python scripts/pipeline_config.py --print-config` | `overridden_keys` 与你改动的键一致 |
| 门禁自测 | `python scripts/gate_selftest.py` | hard 检出 1.0、好题误报 0.0 |
| 表述合规 | `python scripts/check_wording.py` | PASS |

⚠️ **必须用两个解释器各跑一次**（这是一条血泪教训）：

- 默认 `python` 3.13 **没有** jsonschema/numpy → 36 条依赖那批库的用例被显式 skip；
- `Python312/python.exe` 有 → 它们真的执行。

2026-11-02 就栽在这里：`tests/test_schemas.py` 的 `_v22()` fixture 缺 `learning_value` 的 6 个必填字段，**只在 Python312 上暴露**（默认解释器上整批 skip，看起来全绿）。现在补了三件事：①补齐 fixture；②加零依赖的 `_required_gaps()` 走查（只实现 `required` 关键字），让这类错误在无依赖环境也能被抓；③§4 表格改成双基线。

⚠️ **skipped 不是失败，但要看得懂**：86 / 50 条跳过分三类——
1. 缺 `jsonschema` / `numpy` / `rank_bm25`（P1-S4 起显式 skip，不再静默零执行）——两种解释器的差值就来自这一类；
2. 依赖 pytest 夹具的用例（`run_tests.py` 无法注入，交给 pytest）；
3. 条件不成立的防御性用例（如"本机已装 jsonschema，缺依赖分支不可构造"）。

---

## 5. 未闭环项（不是遗漏，是条件不满足）

| 项 | 为什么没闭 | 闭的条件 |
|---|---|---|
| AC-P1-06 lineage 真实批次 | ✅ batch047 已闭（2026-11-03，A2/A3/A4 三段） | 证据 `reports/gate/batch047_lineage.json`：PASS / required=true / entries=3，五元组逐条齐全 |
| AC-P2-02 结构字段覆盖 100% | ✅ batch047 已闭（2026-11-03，A2 与 A4 双版本各测一次） | 证据 `reports/validate/batch047_structural.json`：5 字段各 1.0，items=50，historical=0（path 指向 A4 交付 `ALL_questions_FIXED.json`） |
| AC-P2-04 机制标签覆盖 | ✅ batch047 已闭（2026-11-03） | 同报告 `mechanism_coverage=1.0`（195/195）＋ R20 PASS |
| batch047 医学核验 | **2026-11-03 政策更新：逐题人工核验不再作为发布前置**（A/B + 确定性门禁通过即可发布）；batch047 的「无逐题记录」不再算未闭环 | 仅剩第二评分者盲评（κ），属独立评估项，不影响发布 |
| AC-P3-01 50 题回填 | **原清单 20/20 来源文件已不在仓库**（batch004–027） | 找回文件，或接受"新样本 ≠ 原清单" |
| AC-P3-02 κ ≥0.61 | 只有机器一个评分者 | 第二名独立评分者（人） |
| AC-P8-01 显式授权 100% | **2026-11-03 用户裁定：不用管上架版权，授权不再作为发布门禁** | 本项关闭（license 仅作来源记录） |

**红线**：以上任何一项都**不要**用"造一个数据"的方式闭环。这批验收本身就是在测"你会不会造假"。

---

## 6. 下一步路线

### 6.1 batch047 已完成并签收（2026-11-03）

```
A2 出题（schema 2.2）→ GATE-A2 PASS
→ A3 质检（PASS_WITH_FIXES，25 维）
→ A4 修复（MOD-002：9 题 11 处缩写补全称）→ GATE-A4 PASS
→ GATE-FINAL PASS
→ 签收：50 题 pending_human → publishable，status=APPROVED，release_status=READY
```

交付物已归档至 `archive/最终产物/batch047/`，签收回执 `batch047_签收单.md`。**剩下的只有第二评分者盲评（κ）**。管线侧不要再对 batch047 做结构性改动——A2 已冻结，签收后的交付 sha 是 `35c4dc28…`，任何改动都会让追溯日志、签收回执、MD 三方 sha 失配。⚠️ 归档后**不要再对该批跑 `gate_check`**（文件已不在原路径，会判 BLOCKED）；确需复核先按 `archive/batch047_归档说明.md` 的映射临时还原。

### 6.2 阶段 1 待办（按性价比排序）

| 优先 | 项 | 说明 |
|---|---|---|
| ✅ | P8-S3 公开闸门 | 2026-11-03 用户裁定「不用管上架版权」：G0/G3 改为 INFO，只清点不阻断；G1/G4/G6 仍 fail-closed |
| 高 | P2-S5 R13 降级 + 条件从句豁免 | 当前 R13 误伤"条件从句长选项"，需回测误伤率 <5% |
| 中 | P2-S4 反选题封顶 ≤15% | 需提示词 + schema 配合 |
| 中 | P3-S3 → 注册表 | 把 7 维 rubric 正式并入 `rules/registry.yaml` |
| ✅ | HC-22 配额接入 final | 无 plan 或配额不足且无 reduced/cancelled 理由 → BLOCKED（2026-11-03） |
| ✅ | batch048+ R0–R3 强制 | final 检查 `quality_gate_{batch}_r0..r3` 报告齐全、R3=enforce；签收同样前置检查 |
| ✅ | P6 遥测/指标接线 | `gate_check` 每阶段自动写 `reports/obs/<batch>_telemetry.jsonl`；final 自动跑 `aggregate_metrics` |
| ✅ | P9 模式元数据 / Bloom 补题门禁 | batch048 起 `p9_mode` 覆盖 100%、理解/分析型达 `target_bloom`（低 5pp → BLOCKED）；配套 `scripts/bloom_gap.py` |

---

## 7. 新增文件地图（本轮）

```
rules/registry.yaml                      ★ 规则 SSOT（70 条）
scripts/render_rules.py                  lint（L0–L9）+ 渲染
scripts/pipeline_config.py               （改造）配置读取 + hash + --print-config
scripts/validate/rules_batch.py          ★ X1/X2/X6 + S-STRUCT
scripts/workflow_state.py                （改造）lineage 五元组 + 重试隔离
scripts/check_patch_integrity.py         ★ 补丁契约 / no-op / 修复统计
scripts/telemetry.py                     （改造）按批 JSONL + 字段白名单
scripts/aggregate_metrics.py             ★ 事件反推 + SQLite 指标
scripts/gate_selftest.py                 ★ 黄金缺陷集自测
scripts/agreement.py                     ★ 加权 κ / ICC(2,1) / Bland–Altman
scripts/review_sample.py                 ★ 分层抽题 + 7 维机器代理分
scripts/check_wording.py                 ★ 实测类宣称 + 无据结论核查
scripts/license_matrix.py                ★ 权利盘点
scripts/public_risk.py                   ★ 公开暴露面
schemas/agent2_output.schema.json        （改造）v2.2
Prompt版本/MedGen_current_prompt.md      （改造）HC-29
docs/archive/2026-11/评审协议_20261102.md                ★ 7 维 rubric
tests/fixtures/defects/defects.json      ★ 黄金缺陷集
tests/{test_render_rules,test_pipeline_config,test_patch_integrity,test_obs_pipeline,test_agreement,test_check_wording,test_compliance_matrix}.py
reports/implementation/                  ★ worklog + 基线 + P1/P2/P3+P8 报告
reports/{registry,validate,repair,obs,calibration,compliance,gate}/   ★ 各类证据
```

---

## 8. 合规红线（不变，重申）

1. **零用户数据**：不采集、不存储学习者标识；遥测字段白名单强制。
2. **不造数**：无专家就写 `BLOCKED`，无数据就写 `null`，不填 0 充数。
3. **不做法律定性**：`license=unknown` 只表示"仓库没记录"；2026-11-03 起授权不再作为上架门禁，仅保留来源记录。
4. **历史不追溯**：≤batch046 只读体检，不改写产物。
5. **PDF 一律人工**：任何脚本禁止生成 PDF。

---

## 9. 交接 Checklist（第一天按序执行）

- [ ] 1. 读本文件 + `CONTEXT.md` + `SOUL.md`（v1.0 交接文档 §3–§7 仍是生产流程权威）
- [ ] 2. `python scripts/run_tests.py` → 确认 422/0/0/61（3.13 口径 386/0/0/97）
- [ ] 3. `python scripts/render_rules.py --check` → exit 0
- [ ] 4. `python scripts/pipeline_config.py --print-config` → 确认阈值来源是 `scripts/pipeline.yaml`
- [ ] 5. 读 `reports/implementation/worklog_20261102.md` 的任务板，确认哪些是 DONE / BLOCKED / TODO
- [ ] 6. **提交前先与用户确认**：本轮 54 项改动未提交；`workflow_state.json`、`Obsidian产物/`、`最终产物/` 里的改动不是本轮产生，不要一并提交
- [ ] 7. 与用户确认：**A. 是否需要第二评分者做 κ 盲评（不影响发布，仅评估项）；B. 是否仍要对 7 个含 unclear 真题的文件做版权处置（不再阻断发布）；C. 是否继续按抽样盲攻执行 MedQC。**
- [ ] 8. 任意改规则/阈值前，先跑一遍 §4 的五个检查留基线，改完再跑一遍对比

---

*本文档由 2026-11-02 阶段 0 执行会话编制。所有数字均可在 `reports/implementation/` 与 `reports/{registry,validate,repair,obs,calibration,compliance}/` 下复核。若与 `workflow_state.json` 冲突，以状态机为准。*
