# batch046 偏考研正式题库 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: 按任务逐项执行并在每个门禁处复核；确定性门禁未通过不得写入 Obsidian **正式产物**，但生成阶段必须继续产出待审稿与复核队列（HC-28），不得因等待人工核验而中断。

**Goal:** 在复用现有规则和真题候选的前提下，生成100题、偏考研、答案位置受约束随机且完成完整门禁的急诊与灾难医学 batch046 正式题库。

**Architecture:** 保留现有 MedGen → MedQC → MedFix → 导出链路，只新增 batch046 蓝图、真题计划和答案位置计划；原创题全部重新生成，真题候选沿用已核验来源。batch045 v5 只作试点留档，不作为原创题输入。只有 A2/A3/A4、Bloom、重点覆盖、真题配额、答案位置、学习价值、概念等确定性门禁通过后，才进入可发布核心；人工医学复核队列随产物交付，不阻断生成，正式发布前由用户签收。

**执行契约（HC-28）:** 一次会话内连续执行 Task 1–6，不等待人工确认；人类专属核验（原卷/答案原页/版权/专家裁定/指南冲突）写入 `review_queue`；只有确定性门禁 FAIL、输入损坏或工具故障才停。可发布核心为空不是停止条件：交付完整待审稿 + 队列，标 `release_status=BLOCKED`（题目数量完整时 `generation_status` 仍为 DONE）。

**Tech Stack:** Python 标准库、现有 scripts/real_question_cli.py、scripts/check_learning_value.py、scripts/check_source_concepts.py、python -m scripts.validate、validate_options.py、现有 MedQC/MedFix 规则、Markdown/JSON。

---

### Task 1: 撤回试点正式索引并登记 batch046

**Files:**
- Modify: `_MOC/急诊与灾难医学.md`
- Create: `中间产物/batch046/` 及批次登记所需状态文件（使用现有 workflow_state.py 接口）

- [x] 从 MOC 的正式题库区移除 batch045 链接及最终产物副本；中间产物草稿保留并标明未审核。
- [ ] 使用现有批次状态接口登记 batch046，声明 `product_types=question_bank`、目标100题、偏考研、原创题重新生成、允许复用真题候选。
- [ ] 核对 batch046 目录为空或仅含本批次状态文件；禁止覆盖 batch045。

### Task 2: 生成正式蓝图与受约束答案位置计划

**Files:**
- Create: `中间产物/batch046/出题蓝图_batch046.md`
- Create: `中间产物/batch046/answer_position_plan.json`
- Reuse: `输入素材/大四上/急诊与灾难医学/急诊与灾难医学_教师重点_锚定清单_20261026.md`

- [ ] 固定随机种子生成100个答案位置，A/B/C/D/E各15–25题，任一连续窗口不出现3个相同答案；计划作为生成输入，不在生成后移动答案。
- [ ] 蓝图固定：A1约30题、A2约45题、A3/A4约25题；记忆≤20%、理解约25%、应用约35%、分析约20%；教师重点第1–61条全部覆盖。
- [ ] 按 HC-22 双族配额：考研族和执医族各15–25题、各目标20题，余题为全新原创；候选不足依规则留痕减量。记录每题来源、许可证、目标题型、Bloom、重点条号和答案位置。
- [ ] 运行 `python scripts/real_question_cli.py plan --subject 急诊与灾难医学 --target 100 --batch batch046 --keypoints 输入素材/大四上/急诊与灾难医学/急诊与灾难医学_教师重点_锚定清单_20261026.md --out 中间产物/batch046/real_question_plan.json`；若既有候选不足，记录 reduced/cancelled 原因，并用原创题补齐题位，不强行凑无关题、**不留空题位**（HC-28）。

### Task 3: 重新生成原创题并复用真题候选

**Files:**
- Create: `中间产物/batch046/ALL_questions.json`
- Create: `中间产物/batch046/生成日志.md`

- [ ] 真题候选只复用已有来源、答案、许可和核验字段，不改写原题事实；原创题不得复制 batch045 原创题题干、选项或解析。候选未完成原卷/答案原页/授权核验 → 标 `pending_human|quarantined` 并放入复核队列，**题位由原创题补齐**，不得留下空题位或把未核验候选计为合格题。
- [ ] MedGen 按蓝图、answer_position_plan 和 real_question_plan 生成纯 JSON 数组；每题 schema 2.1、完整 Bloom、concepts、learning_value、来源锚点和 draft/review 状态。
- [ ] 每50题做一次答案分布、Bloom、题型和重点覆盖抽样；偏离蓝图时回退生成，不用 MedFix 机械改答案。
- [ ] 执行 `python -m scripts.validate --file 中间产物/batch046/ALL_questions.json`、`python scripts/check_learning_value.py --file 中间产物/batch046/ALL_questions.json`、`python scripts/check_source_concepts.py --file 中间产物/batch046/ALL_questions.json --batch batch046`；任一 FAIL 先修复；单题 2 轮、整批 3 轮后仍 FAIL 的题标 `quarantined` 并继续，不整批停止（HC-28）。

### Task 4: 完成 MedQC 独立质检

**Files:**
- Create: `质检报告/batch046/A3_质检报告.json`
- Create: `质检报告/batch046/人工复核队列.md`
- Create: `最终产物/batch046/review_queue.json`（导出时生成，HC-28）

- [ ] 对每题屏蔽答案和解析盲攻，检查唯一答案、竞争项、医学依据、教材口径与现行临床边界。
- [ ] 对高风险急救、剂量、时间窗、复苏、溺水、卒中、烧伤内容逐题核验；来源不足或存在指南冲突的题标 `release.disposition=pending_human|quarantined` 并写入 `review_queue`，**不整批 BLOCKED、不停止其余题**（HC-28）。
- [ ] 校验答案分布、A1/A2/A3/A4、Bloom、考研配额、重点覆盖和原创去重；报告绑定原始 JSON SHA-256。

### Task 5: MedFix 定向修复并重跑门禁

**Files:**
- Create: `最终产物/batch046/ALL_questions_FIXED.json`
- Create: `最终产物/batch046/AGENT4_追溯日志.json`
- Create: `最终产物/batch046/AGENT4_修改声明.md`

- [ ] 仅按 A3 报告修复；同步修改来源文件或记录无法修复的题目，不改变答案位置计划和原创/真题身份。无法修复的题标 `pending_human|quarantined` 并继续其余题；单题最多 2 轮、整批最多 3 轮。
- [ ] 运行 A4、学习价值、概念、答案分布、重点覆盖、真题双族配额和 final 门禁；确定性 FAIL 退回 MedGen/MedFix，禁止跳过；人类专属核验只进队列，不阻断生成。
- [ ] 运行 `python scripts/real_question_cli.py check --file 最终产物/batch046/ALL_questions_FIXED.json --plan 中间产物/batch046/real_question_plan.json --keypoints 输入素材/大四上/急诊与灾难医学/急诊与灾难医学_教师重点_锚定清单_20261026.md --out reports/validate/real_question_check_batch046.json`。

### Task 6: 导出并写入 Obsidian

**Files:**
- Create: `最终产物/batch046/ALL_questions_FIXED.md`（生成阶段交付）
- Create: `最终产物/batch046/review_queue.json`（生成阶段交付）
- Create（签收后）: `最终产物/batch046/急诊与灾难医学·偏考研正式题库.md`
- Modify（签收后）: `_MOC/急诊与灾难医学.md`

- [ ] 生成阶段：确定性门禁通过后运行 `python scripts/qbank.py export-md --file 最终产物/batch046/ALL_questions_FIXED.json --review-queue-out 最终产物/batch046/review_queue.json`；**不等待人工复核即可完成生成并交付待审稿**。
- [ ] 核对 Markdown 100题、答案分布、来源标记与 JSON 一致；确认每题有 `release` 标注，MD 末尾附人工复核队列。
- [ ] 发布到 Obsidian 正式题库区前必须用户签收；未签收时只写待审稿/复核队列，不写正式链接。batch045 仅保留在试点/归档说明区。
- [ ] 最终检查 Obsidian 链接可解析、旧 batch045 文件未被删除、batch046 JSON/MD/review_queue SHA 可追溯。

### 验收标准

- 题数恰为100，ID唯一，原创题与 batch045 原创题无重复。
- 答案 A–E 各15–25题，受约束随机且可由 `answer_position_plan.json` 复现。
- 教师重点1–61全部覆盖；Bloom无缺失，记忆≤20%，A2/A3/A4和应用/分析比例达到蓝图。
- 考研族和执医族各15–25题，或依 HC-22 有据记录减量；来源、答案、许可和核验记录完整。
- schema、选项、学习价值、概念、来源、A3、A4、真题配额和终审门禁无 FAIL。
- `generation_status=DONE`：100 题全部生成并带 `release` 对象；`review_queue.json` 已产出；允许 `release_status=PENDING_HUMAN_REVIEW` 而不判生成失败（HC-28）。
- 未完成人工医学复核或存在来源争议的题不得进入 Obsidian **正式产物**，但必须保留在待审稿/复核队列中，不得因此停止生成。
