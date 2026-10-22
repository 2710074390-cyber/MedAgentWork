---
name: medbatch
description: MedAgentWork 批次运行手册。定义 batch 从启动到签收的完整生命周期：阶段序列、门禁命令、目录与命名规范、交接规则、常见故障处置。MedMaster 编排每个批次时按此执行。
whenToUse: 编排者开始新批次、推进管线阶段、遇到门禁阻断或处理签收归档时加载。
---

# MedAgentWork 批次运行手册

本手册定义一个批次从启动到签收的全部规则。编排者（MedMaster）在每个批次开始时加载并逐条执行。

## 1. 批次生命周期

```
启动(登记批次) → 阶段2 MedGen → 门禁A2 → 阶段3 MedQC → 门禁A3
→ 阶段4 MedFix → 门禁A4 → 阶段5 MedReview → 门禁A5*
→ 阶段6 生图(豆包·HC-19，仅配图范围科目) → 门禁GATE-A6
→ 终审门禁 → 用户签收(APPROVED) → 归档
```

- 门禁未通过 → **halt** → 回退对应 Agent 修复 → 重跑门禁（不可跳过，HC-12）
- GoldenSet 签收只由用户手动执行，任何 Agent 禁止写入
- *门禁A5：MedReview 产出主复习资料 MD + 配图清单，编排者核对占位符与清单一致（`python scripts/check_inline_images.py --md … --list …`，首次跑允许 0 张占位 = MD 无图）后进入阶段 6
- **门禁A5 附加（HC-20/D0 · 2026-10-18，有教师重点/复习大纲输入的批次强制）**：跑 `python scripts/check_keypoint_coverage.py --keypoints <教师重点原文> --md <主复习资料 MD>`（数值/时间窗类硬事实缺失或重点条目缺锚点 → exit 1 → 回退 Agent 5 补写；无教师重点输入 → SKIPPED，不视为通过）
- **阶段 6（HC-19）**：生图主责在豆包（Doubao 图片 Agent，调用 `medillustration` skill），DSH 不调用 image_gen；编排者打包交接（配图清单 + skill 要点 + 图谱索引 + 可复用图路径 + 科目目录规范），豆包回传 `images_webp/*.webp` 后运行 GATE-A6 并人工质检（解剖准确性抽查）

## 2. 目录与命名（铁律，详见 CONTEXT.md）

| 阶段 | 目录 | 产物命名 |
|---|---|---|
| 输入 | `输入素材/{科目}/` | 用户放入教材/笔记 |
| Agent 2 | `中间产物/{batchID}/` | `ALL_questions.json`、备考资料 .md |
| Agent 3 | `质检报告/{batchID}/` | `A3_质检报告.json` |
| Agent 4 | `最终产物/{batchID}/` | `ALL_questions_FIXED.json`、**`ALL_questions_FIXED.md`（最终交付格式，2026-08-20 起强制）**、`AGENT4_追溯日志.json`、`AGENT4_修改声明.md`、`escalations_for_human.md` |
| Agent 5 | `复习资料/{科目}教学计划版/` | `{科目}_主复习资料.md`、**`{科目}_配图清单.md`（HC-19 强制）** |
| Agent 6 生图 | `复习资料/{科目}教学计划版/` | `raw/`（无字底图）、`annotate_configs/*.yaml`（标注）、`annotated/`（标注版 PNG）、`images_webp/*.webp`（MD 引用此目录，1600px q=82） |
| 金标准 | `GoldenSet/` | 仅用户手动移入 |
| 归档 | `archive/{类别}/{batchID}/` | 签收后由 maintenance 归档 |

批次号格式 `batch{NNN}`（如 batch026）；子批用 `batch026-A/B/C` 时必须在 workflow_state 中登记说明。

## 3. 门禁命令（每个阶段转换前强制执行）

```text
GATE-A2   python -m scripts.validate --batch {batchID}          # FAIL==0 才放行
GATE-A3   python gate_check.py --batch {batchID} --stage agent3_done
GATE-A4   python gate_check.py --batch {batchID} --stage agent4_done
MD导出    python scripts/qbank.py export-md --file 最终产物/{batchID}/ALL_questions_FIXED.json   # 最终交付 MD（2026-08-20 起强制）
真题配额  python scripts/kaoyan_picker.py check --file 最终产物/{batchID}/ALL_questions_FIXED.json   # HC-18 legacy（旧批次兼容）
真题双族配额 python scripts/real_question_cli.py check --file 最终产物/{batchID}/ALL_questions_FIXED.json --plan 中间产物/{batchID}/real_question_plan.json --keypoints {锚定清单} --out reports/validate/real_question_check_{batchID}.json   # HC-22 考研族+执医族 20%+20%（执医族=历年真题优先/CMExam补位；新题库批次终审前执行）
插图门禁  python scripts/check_inline_images.py --md 复习资料/{科目}教学计划版/{科目}_主复习资料.md --img-dir 复习资料/{科目}教学计划版/images_webp --list 复习资料/{科目}教学计划版/{科目}_配图清单.md   # GATE-A6 / HC-19 插图占位一致性（配图范围科目，生图验收后与终审前各跑一次；exit 1 → 回退豆包补图）
重点覆盖  python scripts/check_keypoint_coverage.py --keypoints 输入素材/{科目}/{科目}_教师重点_*.md --md 复习资料/{科目}教学计划版/{科目}_主复习资料.md   # HC-20/D0 教师重点原文锚定（有教师重点输入的批次，门禁A5 与终审前各跑一次；exit 1 → 回退 Agent 5 补写；无教师重点输入 → SKIPPED）
终审      python gate_check.py --batch {batchID} --stage final
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
- **真题双族配额（HC-22 · 2026-10-22 修订，新题库批次）**：批次启动前运行 `python scripts/real_question_cli.py plan --subject {科目} --target {题数} --batch {batchID} --keypoints {教师重点锚定清单} --blueprint {出题蓝图} --out 中间产物/{batchID}/real_question_plan.json`，把 `selected` 逐题注入 Agent 2；终审前运行 `real_question_cli.py check`（考研族/执医族各 15%–25%，答案可信/重复/覆盖/license/溯源任一 FAIL → halt）。执业医师族内**历年真题（tier=pdf）优先、CMExam（tier=cmexam）补位**；`quota_status=reduced/cancelled` 允许，但必须保留检索日志与减量原因并用原创补齐。
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
- 批次关键事件（启动/门禁/halt/签收）记入 `memory/JOURNAL.jsonl`（UTF-8 JSONL，一行一条）
- 新教训 → 更新 SOUL.md HC-* 表 + `memory/FACT.md`；完成项 → 更新 `docs/TODO.md`

## 5. 常见故障处置

| 症状 | 处置 |
|---|---|
| 门禁 BLOCKED | 读 gate 的 reason → 回退对应 Agent 修复 → 重新运行门禁 |
| JSON 解析失败 / YAML 前置 | 要求 Agent 输出纯 JSON 数组，元数据单独 .md（batch006 教训） |
| 选项截断/缺单位 | validate R7/R8/R9 → MedFix 修复，禁止暴力截断（batch014 教训） |
| Bloom 偏差 >15% | 回退 Agent 2 按配额修正（`scripts/bloom_sampler.py`，HC-15） |
| 补丁未溯源 | 追溯日志缺 source_file_synced → 打回 Agent 4（HC-13，batch014 教训） |
| 签收 | 用户确认 → 状态置 APPROVED → 用户手动移入 GoldenSet → 归档 |
| RAG 余额不足(402) | 降级：`search_kb.py --no-rerank`（跳过付费 rerank，用 Stage1 余弦）；查询优先复用缓存结果（batch027 教训） |
| 注册表报"文件不存在" | 已归档批次属预期：`qbank.py check` 已归档感知；如需修正路径用 `qbank.py rehome`（2026-08-20） |
| 插图缺失/占位符与文件不一致 | GATE-A6 exit 1 → 读输出定位（C2 文件缺失 / C3 图号断号 / C5 清单不一致）→ 回退豆包补图或修正清单 → 重跑门禁（HC-19） |
| 复习资料丢失教师重点细节（时间窗/分级界值被概括成"大概意思"） | 跑 `scripts/check_keypoint_coverage.py --keypoints <原文> --md <MR MD>` 定位缺失硬事实 → 回退 Agent 5：在对应考点补 `📌 重点原文（第X条）：…` 落点行并原样保留数值/并列/禁止结构（HC-20/D0，batch039 突发性聋教训）；确属非命题范围的细节 → 写入 `--allowlist` 并注明理由，禁默认忽略 |
| 豆包回传图片解剖错误 | 试点 2/2 首轮出错（肝画成肾、视神经放大图画成尿道样结构）→ 打回豆包重生成，提示词加强形态特征描述（如"楔形、右叶大于左叶"）；AI 图内中文标注一律禁用（乱码），改 annotate_image.py 程序叠加 |
| 配图标注错位（文字/引线与结构位置不符） | 2026-09-30 实证（面神经腮腺标在鼻上、五支/溃疡/修复体全偏）→ ①先跑 `scripts/_analyze_annot_pos.py` 量化底图结构坐标（颜色掩膜网格热区/角度端点/xband），禁止目测估算；②重写 annotate YAML：label 一律带 `anchor` 引线指向实测坐标、文字放空白区、`output` 字段写 `annotated/xxx.png` 正确名；③侧脸图先 Read 底图判五官朝向（鼻/耳/腮腺相对位，腮腺=耳前神经主干根部）；④重标后逐张 Read 成品核验引线端点，再导出 webp → 重渲染 HTML（--embed-images，MD 先规范化无 BOM+LF）→ 重跑 check_inline_images exit 0 → 重新交付 |

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
