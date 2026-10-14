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
真题配额  python scripts/kaoyan_picker.py check --file 最终产物/{batchID}/ALL_questions_FIXED.json   # HC-18 考研真题占比（2026-08-21 起，终审前执行）
插图门禁  python scripts/check_inline_images.py --md 复习资料/{科目}教学计划版/{科目}_主复习资料.md --img-dir 复习资料/{科目}教学计划版/images_webp --list 复习资料/{科目}教学计划版/{科目}_配图清单.md   # GATE-A6 / HC-19 插图占位一致性（配图范围科目，生图验收后与终审前各跑一次；exit 1 → 回退豆包补图）
终审      python gate_check.py --batch {batchID} --stage final
```

- 已签收（APPROVED）批次重跑门禁只作参考，不写 HALT
- `python gate_check.py --batch {batchID} --clear-halt` 清除该批次 HALT（修复后使用）
- validate 报告输出在 `reports/validate/`，gate 报告在 `reports/gate/`
- **MD 导出是最终交付格式**：GATE-A4 通过后必须运行 export-md 生成 `ALL_questions_FIXED.md`（JSON 为机器可读源，MD 为用户可读交付），与 JSON 同目录交付
- **考研真题配额（HC-18）**：批次启动前运行 `kaoyan_picker.py pick`（检索该章节真题候选，注入 Agent 2 调用指令）；终审前运行 `kaoyan_picker.py check`（占比 ≥15% 通过；<15% 时核对候选，确无真题覆盖则标注"无真题覆盖"后放行）

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
