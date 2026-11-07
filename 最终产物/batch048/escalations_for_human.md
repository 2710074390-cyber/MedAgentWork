# batch048 升级告警清单（需人工处理）

> 生成时间：2026-11-05T23:41+08:00 ｜ 批次：batch048（内科学·泌尿系统疾病，30 题）
> 结论：3 项升级，均为「A3 指令与 A4 执行契约冲突」，非医学争议；其余 10 项 patch 已执行且复检 FAIL=0 / WARN=0。

---

## ESC-001 · Q020 真题题干去 Markdown（HC-22 逐字性 vs 不可变字段契约）

- **目标**：`batch048-Q020.stem`
- **现状**：`尿路感染的易感因素**不包括**`（源题原文应为 `尿路感染的易感因素不包括`）
- **答案/极性**：E / negative（A–D 为真、E 为假），不受影响
- **为什么 A4 不能改**：Q020 `source_type=执业医师真题`，`check_patch_integrity.IMMUTABLE_FIELDS` 把真题题干列为不可变；试改实测
  ```
  审计 batch048: 不可变违例 1
  ✗ batch048-Q020: 改了不可变字段 ['stem(真题题干)']
  结论: FAIL
  ```
  → `GATE-A4-PATCH-AUDIT` BLOCKED（`gate_check.py` 对不可变违例直接阻断整批交付）。
- **影响**：交付 MD 第 20 题渲染为 `**尿路感染的易感因素**不包括****`，纯文本环境会露出星号；不影响医学结论与答案。
- **建议处置（二选一）**
  1. **首选**：在 A2 阶段把该题 stem 的 `**` 去掉（源头应为干净原文），重跑 A3→A4；
  2. 由人工签收并在 `workflow_state` 记录豁免理由后重跑 A4，允许本题去掉标记。
- **修复动作（人工执行，改完需重跑 A4 复检）**：`Q020.stem` → `尿路感染的易感因素不包括`

---

## ESC-002 · Q030 Bloom 层级校准无法在 A4 落地（D10 major）

- **目标**：`batch048-Q030`（`bloom` / `bloom_level`）
- **现状**：`bloom=记忆`、`bloom_level=记忆`；题干 154 字、9 项变量、`step_count=3`、`difficulty_tier=L3`，实为「药物性 AIN＋Ⅰ型 RTA」多步归因，A3 判为 major 并给出 `记忆→分析`。
- **为什么 A4 不能改**：该 patch 的 precondition 要求 `bloom_level` 与 `bloom` 同步；而 `bloom_level` 未登记于 `check_patch_integrity.ALLOWED_FIELDS`（计入未分类字段 → 审计 FAIL）。
  - 只改 `bloom`：留下 `bloom=分析 / bloom_level=记忆` 自相矛盾，且 `qbank.py export-md` 按 `bloom_level` 渲染（MD 与 JSON 会打架）。
  - 改两个：审计未分类字段 +1 → `result=FAIL` → `GATE-A4-PATCH` FAIL。
  - 故整体不执行，不做「半改」。
- **建议处置**：把 `bloom_level` 纳入 `ALLOWED_FIELDS`（或改为由 `bloom` 派生、或在下游统一只读 `bloom`）后重跑 A4。
- **改判后的分布**（已验证在门禁容差内）：记忆 16.7% / 理解 26.7% / 应用 33.3% / 分析 23.3%，对目标 20/25/35/20 最大偏差 3.3pp。
- **手动改法**：`bloom` 与 `bloom_level` 同时由 `记忆` 改为 `分析`（`step_count=3`、`difficulty_tier=L3` 无需调整）。

---

## ESC-003 · 全批 `negative_cues` 未沉淀（A3 ISSUE-014 / HC-29）

- **目标**：`negative_cues`（29/30 题为空数组）
- **可沉淀的阴性线索**（A3 已点名，题干可逐字取证）
  - Q001：`光镜下肾小球结构未见明显异常`
  - Q014：`无皮疹与关节痛`／`无糖尿病史`／`乙型肝炎病毒标志物阴性`
  - Q018：`无活动性感染及活动性结核`
  - Q022：`无尿频、尿急、尿痛`
- **为什么 A4 不能写**：`negative_cues` 既不在 `ALLOWED_FIELDS` 也非 `IMMUTABLE_FIELDS` → 计入未分类字段。探针实测：仅 Q001 一题写入即 `未分类字段=1 → result=FAIL`。
- **建议处置**：在 A2 阶段补齐 `negative_cues`；或把该字段加入 `ALLOWED_FIELDS` 后由 A4 补录。

---

## 附：未升级但需知悉的偏差

- **ISSUE-003 / ISSUE-004（Q001、Q002 Bloom 记忆→理解）**：A3 已明确「保留并留痕，不生成 patch」，且改判会使记忆层降至 10%（偏差 10pp）。按 PG-00（只执行结构化指令）未执行，仅在此留痕。若确需改判，请先补一条结构化 patch。
- **`teacher_anchor` 破折号**：`teacher_anchor` 属不可变字段，未随 `source_quote` 联动去破折号；`check_learning_value.py` 规范化匹配（去标点/空格）后仍逐字命中，`source_quote_exact_rate=1.0`，无实质影响。
