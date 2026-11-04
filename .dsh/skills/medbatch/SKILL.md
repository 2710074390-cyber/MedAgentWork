---
name: medbatch
description: MedAgentWork 批次运行手册。定义 batch 从启动到签收的完整生命周期：阶段序列、门禁命令、目录与命名规范、交接规则、常见故障处置。MedMaster 编排每个批次时按此执行。
whenToUse: 编排者开始新批次、推进管线阶段、遇到门禁阻断或处理签收归档时加载。
---

# MedAgentWork 批次运行手册

本手册定义一个批次从启动到签收的全部规则。编排者（MedMaster）在每个批次开始时加载并逐条执行。

## 1. 批次生命周期

```
batch048+：R0/R1 → 启动(登记批次) → 阶段2 MedGen → 门禁A2 → 阶段3 MedQC → 门禁A3
→ 阶段4 MedFix → 门禁A4 → **门禁LV** → 阶段5 MedReview → 门禁A5*
→ R2 测试验证 → R3 发布上线（enforce）→ 终审门禁（检查 HC-22/R0–R3/P9/Bloom 四项）
→ 用户签收(可选) → 归档 → R4 复盘
```

> HC-19 插图管线（原阶段6 生图 + GATE-A5 配图项 + GATE-A6）已于 2026-11-02 整体下线，见 `SOUL.md § HC-19`。复习资料产出**纯文本**，不写占位符、不出配图清单。

- **门禁LV（HC-24 · 2026-10-23 新增）**：`item_schema_version≥2.0` 的新批次（batch047 起为 2.2），MedFix 后必须跑 `python scripts/check_learning_value.py --file 最终产物/{batchID}/ALL_questions_FIXED.json --batch {batchID} --out reports/validate/learning_value_{batchID}_final.json`；`FAIL>0`、逐项覆盖<100%、错误认知覆盖<100%、`source_quote_exact_rate<95%`、`quote_verified_rate<95%`、`misconception_id_conflicts>0` 或 `anchor_verified_rate<80%` → **halt**，回退 MedGen/MedFix。已签收旧批次（无 `item_schema_version`）显式 SKIPPED，不追溯。
- **门禁适用范围（2026-10-26 加固）**：批次可显式声明 `product_types`（`question_bank`/`prediction_paper`/`review_material`），缺失时按产物形状推断。A2/A3/A4 只对题库/押题卷生效；PG-09/10/11 只对复习资料生效；JSON 有效性只对题库/押题卷生效。`--stage auto` 按此矩阵路由：复习资料批次直达 final；v2 题库/押题卷批次在 A4 后自动插入 `learning_value`，不会被跳过。

- 门禁未通过 → **halt** → 回退对应 Agent 修复 → 重跑门禁（不可跳过，HC-12）
- **HC-28 一次跑完（2026-11-01）**：只有**确定性门禁**（schema/JSON、R1–R13、D20=0、Bloom 偏差、ID 冲突、答案唯一性硬检查）FAIL 才回退；单题最多修 2 轮、整批最多 3 轮，仍失败则隔离该题并继续。**人类专属核验**（原卷/答案原页/版权授权/医学专家裁定/指南冲突）只写 `review_queue`，不触发 halt。`generation_status=DONE` 即生成完成；`release_status=PENDING_HUMAN_REVIEW` 不是失败。**可发布核心为空也不是停止条件**：仍交付完整待审稿 + 队列，标 `release_status=BLOCKED`（题目数量完整时 `generation_status` 仍为 DONE）。只有输入损坏、连续 2 次不可解析或工具故障才终止批次。
- **交付必须带队列**：`review_queue.json` 由 `qbank.py export-md --review-queue-out` 生成；最终 MD 末尾附「人工复核队列」；签收前用户审查队列，签收只改变发布状态，不改变已完成的生成产物。
- GoldenSet 签收只由用户手动执行，任何 Agent 禁止写入
- *门禁A5：MedReview 产出主复习资料 MD（纯文本，HC-19 已下线不出配图清单）
- **门禁A5 附加（HC-20/D0 · 2026-10-18，有教师重点/复习大纲输入的批次强制）**：跑 `python scripts/check_keypoint_coverage.py --keypoints <教师重点原文> --md <主复习资料 MD>`（数值/时间窗类硬事实缺失或重点条目缺锚点 → exit 1 → 回退 Agent 5 补写；无教师重点输入 → SKIPPED，不视为通过）
- **门禁A5 附加（HC-26 · 2026-10-27，所有复习资料批次强制）**：跑 `python scripts/check_review_detail.py --md <主复习资料 MD> --mode auto --profile <release_teacher_keypoint|release_teaching_plan>`（掌握级九槽位+案例/卡片达标/自测答案/模块八块/课程八块任一 FAIL → 回退 Agent 5 补写；报告 `reports/validate/review_detail_*.json|md`）
- **阶段 6 生图（HC-19）已下线（2026-11-02）**：不再有豆包交接、配图清单与 GATE-A6。复习资料到门禁A5（含 HC-20/D0 与 HC-26 附加项）通过即进入终审。

## 1.5 全流程质量阶段（HC-25 · 2026-10-23 新增 · 2026-11-03 batch048 起强制）

> 标准：`docs/质量管控规范.md`；阈值：`scripts/quality_policy.json`；编排：`scripts/quality_gate.py`。
> 旧批次/旧产物冻结、不追溯；新批次/新版本必须按 R0–R4 执行。
> **2026-11-03 起（batch048+）**：R0–R3 必须全部落报告，且 R3 必须 `--mode enforce`；`gate_check.py --stage final` 会检查 `reports/gate/quality_gate_{batchID}_r0..r3_*.json` 是否存在、非 BLOCKED/SKIPPED、R3 是否为 enforce。缺任一 → BLOCKED。R4 在归档后补。

```
R0 需求评审  python scripts/quality_gate.py --stage r0 --batch {batchID} --mode advisory
R1 开发实现  python scripts/quality_gate.py --stage r1 --batch {batchID} --profile pilot --mode advisory
R2 测试验证  python scripts/quality_gate.py --stage r2 --batch {batchID} --profile pilot --mode advisory --with-tests
R3 发布上线  python scripts/quality_gate.py --stage r3 --batch {batchID} --profile release_teacher_keypoint --mode enforce
R4 运行复盘  python scripts/quality_gate.py --stage r4 --batch {batchID} --commit {commit}
```

- R2 未通过不得进 R3；R3 `enforce` BLOCKED 禁止发布；WARN 必须在 `reports/gate/*.md` 写豁免理由/影响/补做计划/责任人。

> **批次登记（batch048+）**：在 `workflow_state.json` 的批次对象写 `target_bloom`（教师重点 20/20/45/15；100 题大卷 10/25/35/20）与 `p9_mode`，否则 Bloom 目标检查会 SKIP、P9 检查无依据。
>
> **发布前置四项（batch048+，final 门禁机械判定）**：① HC-22 配额（无 plan 或配额不足且无 reduced/cancelled 理由 → BLOCKED）；② R0–R3 报告齐全 + R3=enforce；③ 每题 `p9_mode`（teacher_keypoint/course_schedule/module）覆盖 100%；④ 理解/分析型占比低于 `target_bloom` 5pp → BLOCKED 并要求补题。
- SKIPPED 不得视为 PASS；同一问题连续两个版本 WARN → 自动升级 BLOCKED。
- `quality_gate.py` 只读源产物与既有报告，不修改源题库/源复习资料/workflow_state。

## 2. 目录与命名（铁律，详见 CONTEXT.md）

| 阶段 | 目录 | 产物命名 |
|---|---|---|
| 输入 | `输入素材/{科目}/` | 用户放入教材/笔记 |
| Agent 2 | `中间产物/{batchID}/` | `ALL_questions.json`、备考资料 .md |
| Agent 3 | `质检报告/{batchID}/` | `A3_质检报告.json` |
| Agent 4 | `最终产物/{batchID}/` | `ALL_questions_FIXED.json`、**`ALL_questions_FIXED.md`（最终交付格式，2026-08-20 起强制）**、`AGENT4_追溯日志.json`、`AGENT4_修改声明.md`、`escalations_for_human.md`、`review_queue.json`（HC-28） |
| Agent 5 | `复习资料/{科目}教学计划版/` | `{科目}_主复习资料.md`（纯文本；配图清单已随 HC-19 下线，不再产出） |
| 金标准 | `GoldenSet/` | 仅用户手动移入 |
| 归档 | `archive/{类别}/{batchID}/` | 签收后由 maintenance 归档 |

批次号格式 `batch{NNN}`（如 batch026）；子批用 `batch026-A/B/C` 时必须在 workflow_state 中登记说明。

## 3. 门禁命令（每个阶段转换前强制执行）

> **2026-11-04 起（SA-4）**：编排者**不得直接执行**本节命令——阶段门禁一律通过
> `python scripts/batch_driver.py check --batch {batchID} [--stage auto]` 一次调用完成
> （driver 内部按本节命令调用各脚本，并给出 `passed/failed[code,fix_hint,owner]/next_stage`）。
> 本节保留为 **driver 内部实现参考 + 审计清单**；`batch_driver.py plan --batch {batchID}` 可打印该批次的实际执行序列。

```text
GATE-A2   python -m scripts.validate --file 中间产物/{batchID}/ALL_questions.json   # FAIL==0 才放行，禁止返工时误扫最终产物
GATE-A3   python gate_check.py --batch {batchID} --stage agent3_done
GATE-A4   python gate_check.py --batch {batchID} --stage agent4_done
学习价值  python scripts/check_learning_value.py --file 最终产物/{batchID}/ALL_questions_FIXED.json --batch {batchID} --out reports/validate/learning_value_{batchID}_final.json   # HC-24（新批次 schema v2 强制；FAIL>0 → 回退）
GATE-LV   python gate_check.py --batch {batchID} --stage learning_value
MD导出    python scripts/qbank.py export-md --file 最终产物/{batchID}/ALL_questions_FIXED.json --review-queue-out 最终产物/{batchID}/review_queue.json   # 最终交付 MD + 复核队列（HC-28）
真题配额  python scripts/kaoyan_picker.py check --file 最终产物/{batchID}/ALL_questions_FIXED.json   # HC-18 legacy（旧批次兼容）
真题双族配额 python scripts/real_question_cli.py check --file 最终产物/{batchID}/ALL_questions_FIXED.json --plan 中间产物/{batchID}/real_question_plan.json --keypoints {锚定清单} --out reports/validate/real_question_check_{batchID}.json   # HC-22 考研族+执医族 20%+20%（执医族=历年真题+CMExam 双源；新题库批次终审前执行）
重点覆盖  python scripts/check_keypoint_coverage.py --keypoints 输入素材/{科目}/{科目}_教师重点_*.md --md 复习资料/{科目}教学计划版/{科目}_主复习资料.md   # HC-20/D0 教师重点原文锚定（有教师重点输入的批次，门禁A5 与终审前各跑一次；exit 1 → 回退 Agent 5 补写；无教师重点输入 → SKIPPED）
详细度    python scripts/check_review_detail.py --md 复习资料/{科目}教师重点版/{科目}教师重点版_主复习资料.md --mode auto --profile release_teacher_keypoint --json-out reports/validate/review_detail_{科目}.json --md-out reports/validate/review_detail_{科目}.md   # HC-26 九槽位/模块八块/课程八块（门禁A5 与终审前各跑一次；FAIL → 回退 Agent 5）
终审      python gate_check.py --batch {batchID} --stage final
质量阶段  python scripts/quality_gate.py --stage r2 --batch {batchID} --profile pilot --mode advisory --with-tests   # HC-25 R0–R4；正式发布用 r3 + enforce
```

### 门禁输入字段形状契约（2026-10-19 加固 · 防门禁误判）

> batch040 实证：三处「下游产物字段形状 ≠ 门禁解析形状」导致门禁假 BLOCKED（内容本身合格），须由编排者在跑门禁前核对。

| 产物字段 | 门禁解析形状 | 常见错误形状 | 后果 |
|---|---|---|---|
| `A3_质检报告.json` → `bloom_distribution.actual` | 扁平百分数 或 `{"actual":{...}}` / `{"actual_pct":{...}}` | `{"记忆":{"count":n,"ratio":r}}` 嵌套计数 | GATE-A3（BLOOM / BLOOM-RECOMPUTE）误判自述 0.0% → BLOCKED |
| `AGENT4_追溯日志.json` → `source_file_synced` | **顶层** `source_file_synced`/`source_files_synced`（或 `patches[]` 全员 true） | 写在 `execution_metadata` 内部 | GATE-A4-HC13 误判 false → BLOCKED |
| 主复习资料 MD → `📌 重点原文（第X条）` | `--keypoints` **文件第四节连续编号**，落点行逐字照录该条原文 | 沿用来源文档印刷标号（源文档常跳号/重号） | 落点整体错位 → `partial_facts` 失败 |

**编排者动作**：GATE-A3/A4 前先按上表核对形状；不符时**先判明是「形状不符」还是「内容不合格」**——形状不符可归一化（须留痕），内容不合格必须回退重做。

### 站点发布门禁（HC-21 · 2026-10-19 新增 · 签收后执行）

签收后把交付物上线时必须按 HC-21（SOUL.md）执行，**禁止绕过**：

```text
发布前置  git fetch origin main                     # 要求 behind=0 且 ahead=0（ahead>0 先 git push）
页面一致性  python scripts/check_site_freshness.py --offline    # 硬编码「N 科/N 题」== 数据数组
链接门禁    node scripts/check_site_links.mjs index.html
发布        powershell scripts\deploy_site.ps1      # 自动前置闸 + 部署 + 后置校验
```
- 部署脚本**默认拒绝**「本地领先 origin（未 push）」——未推送的提交部署出去会被他人/CI 从 origin 的部署顶掉（batch040 实证：部署后 3 分钟被顶掉，线上回到旧版）。确需本地部署用 `-AllowAhead`（会打警告）。
- 部署后置校验 **不可跳过**：`python scripts/check_site_freshness.py --expect-commit <提交>` → L1 本地文案/数据一致 · L2 线上指纹与本地一致 · L3 线上最新 Production 部署的 Source == 本次提交。FAIL → 告警并重部署；**禁止用旧内容覆盖线上更新的版本**（先 merge 再发）。
- 新增/下线任一条目，**同一提交内**必须同步四处：数据数组 + 分区大标题「N 科」+ 分区副标题 + 页面统计数字（batch040 教训：漏改分区大标题 → 线上「卡片有了、标题还写 8 科」）。


- 已签收（APPROVED）批次重跑门禁只作参考，不写 HALT
- `python gate_check.py --batch {batchID} --clear-halt` 清除该批次 HALT（修复后使用）
- validate 报告输出在 `reports/validate/`，gate 报告在 `reports/gate/`
- **MD 导出是最终交付格式**：GATE-A4 通过后必须运行 export-md 生成 `ALL_questions_FIXED.md`（JSON 为机器可读源，MD 为用户可读交付），与 JSON 同目录交付
- **真题双族配额（HC-22 · 2026-10-22 修订，新题库批次）**：批次启动前运行 `python scripts/real_question_cli.py plan --subject {科目} --target {题数} --batch {batchID} --keypoints {教师重点锚定清单} --blueprint {出题蓝图} --out 中间产物/{batchID}/real_question_plan.json`，把 `selected` 逐题注入 Agent 2；终审前运行 `real_question_cli.py check`（考研族/执医族各 15%–25%，答案可信/重复/覆盖/license/溯源任一 FAIL → halt）。执业医师族内**历年真题（tier=pdf）优先、CMExam（tier=cmexam）补位**；`quota_status=reduced/cancelled/deferred` 允许，但必须保留检索日志与减量/延后原因并用原创补齐。`cancelled` 仅用于 `available=0` 且无候选；候选存在但人类专属核验未完成时必须用 `deferred` 并写 `hc28_update`，`check` 会校验 status/reason/available/selected 自洽。
- **执业医师语料维护（HC-23，非批次内动作）**：`python scripts/zhiyi_pdf_ocr.py run --workers 8` → `python scripts/zhiyi_pdf_parse.py` → `python scripts/real_question_cli.py build`；重建后核对 `reports/validate/zhiyi_pdf_parse_report.json`（单册有效率 ≥95%、`no_answer`=0、`bad_options`≤2%），不达标先修解析规则。
- **考研真题旧配额（HC-18 legacy）**：仅旧批次兼容；`kaoyan_picker.py pick/check` 已改为读取可信答案表，`--allow-unverified` 仅诊断。
- **教师重点覆盖（HC-20/D0 · 2026-10-18）**：有教师重点/复习大纲输入的批次，Agent 5 交付前必须产出 `中间产物/{batchID}/{科目}_教师重点覆盖矩阵.md`（未覆盖/部分覆盖行数=0）；编排者在门禁A5 与终审前跑 `check_keypoint_coverage.py`，数值/时间窗/分级界值缺失或重点条目缺 `📌 重点原文（第X条）` 锚点 → exit 1 → 回退 Agent 5 补写（batch039 突发性聋时间窗丢失教训）

### 押题卷交付（2026-10-19 · HC-18 修订）

> 押题卷**交付形态由 HTML 改为 MD**，供「大四上刷题」（MedKit 网页版）等刷题软件导入。

```text
组卷导出  python scripts/paper_builder.py --subject {科目} --count {N} [--md-out …]   # JSON（机器源）+ 押题卷_{科目}_{N}题.md（交付）
形态门禁  python scripts/verify_produce_rules.py    # 押题卷 MD：题型标签仅 单选/多选/判断 + `**答案：X**` 行；FAIL==0 才放行
```
- **题型归一为三标签**：`单选题` / `多选题` / `判断题`（A1/A2/A3/A4/B1 → 单选题；X → 多选题；判断 → 判断题；判断题固定两选项 `正确`/`错误`、答案 A/B）
- **HTML 交付已下线**（`quiz_template.html` 仅历史遗留，不再产出）
- 押题卷不参与批次端到端生命周期（可对已签收批次按需组卷）；MD 进 `大三下/押题卷/`（或 `大四上/押题卷/`）前必须过 `verify_produce_rules.py`；PDF 一律人工导出上传

### 事实校验（P1-1 · 2026-08-13，GATE-A2 前执行）

```text
python scripts/fact_check.py pages --file 中间产物/{batchID}/*.json --subject {code}
python scripts/fact_check.py golden --file 中间产物/{batchID}/*.json
```
- `pages` FAIL（P0 占位符/页码越界）→ 打回 Agent 2 修正页码锚点
- `golden` 冲突（术语相似但数值不一致）→ 人工核对后裁决
- 科目缺分块索引时 pages 自动跳过（提示 WARN，不阻断）

## 4. 状态与记忆

- `workflow_state.json`：批次状态/步骤/血缘/门禁结果。由编排者或 ingest/save/gate_check 更新，**子代理不得直接改写**
- **本批上下文（SA-6 · 2026-11-04）**：`python scripts/build_batch_context.py --batch {batchID}` 生成 `中间产物/{batchID}/_ctx.md`（≤8,000 chars）与 `_kpidx.jsonl`（教师重点原文的 ID 索引，**sidecar，不替代原文**——`check_keypoint_coverage.py` 仍直接读原文）。A2 冻结或教师重点变更后需重建；归档后 `ctx_fetch.py` 自动回退 `archive/` 取数。Agent 起步只读 `_ctx.md`，规则/原文按指针用 `ctx_fetch.py --id` 取。
- 批次关键事件（启动/门禁/halt/签收）记入 `memory/JOURNAL.jsonl`（UTF-8 JSONL，一行一条）
- 新教训 → 更新 SOUL.md HC-* 表 + `memory/FACT.md`；完成项 → 更新 `memory/TODO_ACTIVE.md`（历史待办板 `docs/archive/2026-11/TODO.md` 已归档，不再追加）

## 5. 常见故障处置

| 症状 | 处置 |
|---|---|
| 门禁 BLOCKED | 读 gate 的 reason → 回退对应 Agent 修复 → 重新运行门禁 |
| 门禁连续 BLOCKED 同一失败原因 / 补丁反复改同样字段 | 跑 `python scripts/batch_watchdog.py --batch {batchID}`：判「无进展」时按 `actions` 隔离该题 + 入 `review_queue` + 继续其余题（HC-28），只有反复无进展才升级人工 |
| 报 `CHAIN-*` / `STAGE_MISSING` / `ARTIFACT_MISMATCH`（上游没跑门禁就想往下走） | driver 的 verify-before-consume 拦住了：按提示跑 `batch_driver.py check --batch {batchID} --stage <上游>` 补上回执。**不要用 `--no-preflight` 绕过**（它会绕过防跳过机制，并把 `preflight.enabled=false` 写进证据）。回执链在 `最终产物/{batchID}/_gate_ledger.json`；事后复核用 `gate_audit.py --batch {batchID} --recheck`，单阶段验真用 `gate_verify.py --batch {batchID} --stage <阶段>` |
| JSON 解析失败 / YAML 前置 | 要求 Agent 输出纯 JSON 数组，元数据单独 .md（batch006 教训） |
| 选项截断/缺单位 | validate R7/R8/R9 → MedFix 修复，禁止暴力截断（batch014 教训） |
| Bloom 偏差 >15% | 回退 Agent 2 按配额修正（`scripts/bloom_sampler.py`，HC-15） |
| 补丁未溯源 | 追溯日志缺 source_file_synced → 打回 Agent 4（HC-13，batch014 教训） |
| 签收 | 用户确认 → 状态置 APPROVED → 用户手动移入 GoldenSet → 归档 |
| RAG 余额不足(402) | 降级：`search_kb.py --no-rerank`（跳过付费 rerank，用 Stage1 余弦）；查询优先复用缓存结果（batch027 教训） |
| 注册表报"文件不存在" | 已归档批次属预期：`qbank.py check` 已归档感知；如需修正路径用 `qbank.py rehome`（2026-08-20） |
| 复习资料丢失教师重点细节（时间窗/分级界值被概括成"大概意思"） | 跑 `scripts/check_keypoint_coverage.py --keypoints <原文> --md <MR MD>` 定位缺失硬事实 → 回退 Agent 5：在对应考点补 `📌 重点原文（第X条）：…` 落点行并原样保留数值/并列/禁止结构（HC-20/D0，batch039 突发性聋教训）；确属非命题范围的细节 → 写入 `--allowlist` 并注明理由，禁默认忽略 |
| 复习资料"读一遍仍不会"（缺诊断/处置/案例/自测答案） | 跑 `scripts/check_review_detail.py --md <MR MD> --mode auto --profile release_*` → 读 `cards[].missing_slots` 与 `modules[].missing_blocks` → 回退 Agent 5 按 D6 九槽位/模块八块补写；不得用加字数、重复段落或"详见教材"糊弄（HC-26） |

## 6. 成本纪律（2026-08-20 · 余额不足事件后新增）

检索是付费 API（每查询 = 1 embed + 1 rerank）。**默认开启磁盘缓存**：

- 相同查询重复执行 → 0 API 调用（缓存 key 含参数与索引配置签名，索引重建自动失效）
- 批量查询 `-f`：embed 结果按查询粒度缓存，跨批次重复查询免重复付费
- 降级模式：`search_kb.py "查询" --subject X --no-rerank`（跳过 rerank，成本约减半）
- 缓存清理：`search_kb.py --cache-clear`（仅索引重建/参数调整后执行）
- 检索前先查 `中间产物/kb_search_result.json` 与 cache，避免 MedGen/MedReview 重复检索同一查询
- MedMaster 检索尽量一次批量覆盖多考点（`-f queries.txt`），减少交互式单发调用

## 6. DSH 流程差异（vs 旧 Cherry Studio 流程）

- 无剪贴板接力：产物由子代理直接写文件，编排者传路径
- save.py / ingest.py 保留给手工流程；DSH 流程下编排者校验产物后直接更新血缘
- 每批次建议独立会话，避免上下文膨胀与批次间污染
