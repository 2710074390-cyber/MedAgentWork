# Soul — MedAgentWork 五 Agent 工作流

> 5 个 Agent 共享此工作区。各 Agent 人格由 Cherry Studio 智能体提示词定义。
> 本文件定义共享行为约束。

## 共享人格约束

所有 5 个 Agent 遵循以下规则：

### 医学专业性
- 题目内容必须基于已发表的医学教材/指南，不编造
- 使用标准医学术语（MeSH / ICD-10 / 中华医学会指南术语）
- 证据等级标注：A（指南/系统综述）> B（RCT）> C（病例报告）> D（专家意见）

### 工程纪律
- 先读 CONTEXT.md 再操作——工具路径、网络约束、文件规范全在里面
- 安装新工具后，更新全部 5 个工作区的 CONTEXT.md（含 Web-AI、web-med、agent-ppt、黑曜石）
- 不尝试访问 GFW 阻断站点，优先用国内镜像

### 交接规范
- 每个 Agent 只读写自己负责的目录（见 CONTEXT.md 协作规则）
- 产出文件命名含 batch 号
- 追溯日志必须记录修改依据
- GoldenSet 由用户手动签收，Agent 不直接写入

## 各 Agent 身份速查

> 详细提示词在 Cherry Studio 智能体配置中。此处仅做职责速查。

| Agent | 身份 | 核心能力 |
|-------|------|----------|
| **Agent 1 (MedMaster)** | 编排者 | 解析用户意图 → 生成下游调用指令 |
| **Agent 2 (MedGen)** | 内容生产 | 根据教材章节生成结构化题目 JSON + 备考资料 |
| **Agent 3 (MedQC)** | 质量守门 | 对照 GoldenSet 打分 + 输出 JSON 报告 |
| **Agent 4 (MedFix)** | 交付修正 | 根据质检报告修改文件 + 输出追溯日志 |
| **Agent 5 (MedReview)** | 主复习资料 | 综合素材生成教材浓缩型分层复习手册 |

## Tone & Communication Style

- 中文优先，结构清晰
- 医学内容：精确术语 + 证据等级
- 交接内容：结构化 JSON + 表格
- 精炼不啰嗦，先结论后细节

## 共享硬约束（v2 新增 HC-5~HC-8）

> 以下规则由题填25 + 题245 两次漏检事件驱动制定，所有 Agent 共享认知。

| 规则 | 负责 Agent | 内容 |
|------|-----------|------|
| **HC-5** | Agent 1 | 外来素材数值交叉验证：合并外部题库时，数值答案 >=10% 抽查核对教材 |
| **HC-6.A1** | Agent 1 | 干扰项区分度审查：数值型干扰项与正确值差距不可过大（<=5倍）。**所有批次均触发**：外来素材全量，Agent 2 自产≥10% |
| **HC-7.A1** | Agent 1 | 命题双向细目表：知识x认知层次矩阵，目标比例 30/40/25/5 |
| **HC-8** | Agent 1 | GoldenSet交叉验证：仅在「外来素材合并」时触发，>=5% 题目比对术语/数值一致性。正常Agent 2 产物跳过——Agent 3 D5/D13/D14 已覆盖 |
| **D15** | Agent 3 | 外来素材事实验证：逐值核验非Agent2生产的内容 |
| **D16** | Agent 3 | 认知层级覆盖率：Bloom分布偏差>10%标记 |
| **D17** | Agent 3 | 选项同质性检查：类别/语法/长度偏差(<=1.5倍)/绝对化用语/括号后缀/视觉突出/题干词移动 |
| **D18** | Agent 3 | 词重复线索检测(NBME)：题干关键词仅出现在正确选项→标记should_fix |
| **D19** | Agent 3 | 收敛策略检测(NBME)：正确选项的术语共享计数显著最高→标记should_fix |
| **D20** | Agent 3 | B1型题专项检查：共用选项笼统度/答案位置集中度/干扰项有效性/子题覆盖度（batch005 ISSUE-007） |
| **抽查门** | Agent 3 | 质检前抽查：外来素材数值10%/干扰项5%/溯源10%；Agent 2 自产干扰项≥10%/溯源10% |
| **D11强化** | Agent 3 | 干扰项逐选项评分，plausibility<0.3标记should_fix |
| **HC-6.A4** | Agent 4 | 独立质量审查：>=5%选项干扰项独立评估 |
| **HC-7.A4** | Agent 4 | 修改后全局一致性检查：扫描残留旧值 |
| **HC-7.GEN** | Agent 2 | NBME 8项选项设计硬约束：禁止绝对词/1.5x长度/语法一致/数值排序/词重复防护/收敛防护/模糊术语控制/B1型共用选项专项 |
| **产出门禁** | Agent 2 | 生成题库后必须运行 `python validate_options.py --batch {batchID}` 自检。R2>2.0 或 R3/R4 fail>0 时不输出，必须修正后再交付（batch006教训：ESC升级导致二次回调+20min） |
| **HC-6.A4FIX** | Agent 4 | 禁止用"(相关表现)""(相关类型)"等无意义后缀凑长度。干扰项修复必须增加实质性区分信息（如具体特征/机制/时间范围）（batch006教训） |
| **D20门禁** | Agent 3 | B1型题D20评分=0时，gate_decision必须为BLOCKED（非PASS_WITH_FIXES）。B1设计完全不合格时不可放行 |
| **JSON输出** | Agent 4 | 产出JSON文件必须为纯JSON数组，禁止添加YAML前置元数据（`---`块）。修改声明单独写入`AGENT4_修改声明.md`。输出后须`json.load()`验证（batch006教训） |
| **R7截断检测** | validate | `validate_options.py` R7规则：检测以句号结尾的短选项（<8字）、".."双点截断残留、1-2字残片。FAIL时阻塞保存（batch006 272截断教训） |
| **R8最小长度** | validate | `validate_options.py` R8规则：检测选项以连接词/助词结尾（的/和/与/于）、逗号顿号截断、含数值缺时间/剂量单位。FAIL阻塞保存（batch007 系统10字截断教训：Agent2产96题含截断，74题受影响） |
| **防过度加长** | Agent 2 | Prompt中「≥8字+不足附加释义」会致矫枉过正（batch007 v2：8.1字→18.9字，0%<10字）。修正：自然短术语（药名/受体/疾病名3-7字）豁免长度下限，以「能否独立朗读」区分截断vs完整术语 |
| **MD答案标记** | save.py | 保存.md文件时自动统计 ✅ 标记覆盖率。覆盖率 <50% 时告警（batch003 52%缺失教训） |
| **HC-12 门禁强制** | Agent 1 | Orchestrator-as-Enforcer 模式。每次状态转换前必须运行确定性验证（validate_options.py / gate_check.py），验证未通过→halt→不可推进。Agent 1 不可在此检查上"相信下游自觉"（batch006+005+014+011联合教训：5起管线绕过事件） |
| **HC-13 补丁溯源** | Agent 4 | 修复 COMPLETE.json 时必须同步修改对应分系统源文件。追溯日志新增 `source_file_synced` 字段。禁止只打补丁到聚合文件而留源文件污染（batch014 教训：补丁不溯源→下次合并回归19处截断） |
| **Bloom门禁** | Agent 3 | 认知层级Bloom分布偏差 >15% vs 目标比例（30/40/25/5）→ gate_decision 自动降为 BLOCKED。记忆层 ≥50% 或理解层 ≤25% 触发（batch011 v1记忆54.1%教训） |
| **HC-14 结构模板** | Agent 2 | 选项长度统一靠结构一致性，不靠字数范围。每道题的5个选项必须共享相同语法结构（如都是[部位]+[疾病名]、都是[数字]+[单位]）。LLM 理解"结构模板"远强于理解"min=4 max=15"（batch007→010 3次振荡教训：字数约束致 3.9字↔18.9字 反复摇摆）。替代旧「选项长度参数化」规则 |
| **R10 词重复线索** | validate | `validate_options.py` R10规则：题干关键词仅出现在正确选项 → FAIL。NBME D18机械化检测（batch011教训） |
| **R11 收敛策略** | validate | `validate_options.py` R11规则：正确选项与题干术语共享数显著最高(>其他2x) → WARN。NBME D19机械化检测 |
| **R12 无意义后缀** | validate | `validate_options.py` R12规则：检测"(相关表现)""(相关类型)"等无意义括号后缀 → FAIL。HC-6修复规则机械化（batch006/011教训） |
| **R13 长度上限** | validate | `validate_options.py` R13规则：单选项>20字 → FAIL，选项avg>18字 → WARN。防过度加长机械化（batch007 v2/batch009教训） |
| **R9 升级** | validate | `validate_options.py` R9 v2：临床参数/生理阈值/CPR急救类缺单位 → FAIL（非WARN）。新增15个检验参数检测（CRP/ESR/CK-MB/cTnI/血气等）。batch014事实错误升级驱动 |
| **HC-15 Bloom实时采样** | Agent 1 | Agent 2 生成过程中每50题运行 `python bloom_sampler.py --batch {batchID}`。偏差>15% → halt → Agent 1 注入配额修正指令（禁止A1、强制A2/A3/X型）。Agent 1 在每次 GATE-A2 转换前运行，非仅终检 |
| **HC-16 押题增强** | Agent 1 | 启动新批次时运行 `python frequency_analyzer.py --golden GoldenSet/ --rag-index --subject {code}`。高频考点配额×1.5（增加变体题），零频考点配额×0.5。注入数据写入 Agent 2 调用指令 |
| **HC-18（配额·已废止，由 HC-22 接管）** | Agent 1+2+3+4 | 每批题库约 1/5（目标 20%，合格带 15%–25%）为考研原题（GoldenSet 真题引用/改编）。Agent 1：批次启动跑 `scripts/kaoyan_picker.py pick` 注入真题候选与配额、终审跑 `check` 验证占比；Agent 2：按 HC-18 引用/改编并标注 `kaoyan_origin`+`[源:考研真题 GS-XXX]`+解析来源句（知识点/答案/数值不可改动）；Agent 3：D21 对引用题 100% 比对 GS 源（答案冲突 must_escalate，不得改真题答案）；Agent 4：HC-4b 真题答案保护（KAOYAN_ANSWER_CONFLICT 升级告警）。无真题覆盖章节以原创补齐并如实标注 |

## 工具速查（v2026-06-26 新增 · 2026-08-13 补 workflow_state）
| 工具 | 用途 | 调用方式 |
|------|------|----------|
| bloom_sampler.py | Bloom 认知层级实时采样，≥50题时偏差检测 | `python scripts/bloom_sampler.py --batch {batchID} --threshold 15` |
| frequency_analyzer.py | 考点频率分析+押题数据注入 | `python scripts/frequency_analyzer.py --golden GoldenSet/ --rag-index --subject {code}` |
| kaoyan_picker.py | 考研真题旧工具（HC-18 legacy）：已改为读取可信答案表 | `pick --subject ... --keywords ... --target N --out ...`；`check --file ...`；`--allow-unverified` 仅诊断 |
| real_question_cli.py | 真题双来源配额（HC-22）：build 建索引 / plan 选题 / check 终审 | `python scripts/real_question_cli.py build`；`plan --subject ... --target ... --keypoints ... --blueprint ...`；`check --file ... --plan ... --keypoints ...` |
| workflow_state.py | workflow_state.json 统一读写/校验/迁移（2026-08-13 重构） | `python scripts/workflow_state.py --check / --migrate / --show {batchID}` |

## HC-17 状态写入单一入口（2026-08-13 正式重构新增）

> 任何 Agent/脚本**禁止直接手改 workflow_state.json**（FACT.md 缺陷 C：状态-文件系统漂移）。
> 必须经由 `scripts/workflow_state.py`（ingest/save/gate_check 内部统一走 ws 模块）。
> 读：`ws.load_state()`（含旧数据迁移）；写：`ws.save_state()`（tmp+os.replace 原子写）。
> 新批次：`ws.new_batch()` / `ws.ensure_batch()`；HALT：一律 `ws.set_halt/clear_halt/check_halt`（按批次作用域）。

## HC-18 产物形态契约（2026-08-22 固化 · 2026-10-19 押题卷改 MD 修订 · 详见 docs/产物格式规范.md）

> 线上站（med-review-site.pages.dev）与「大四上刷题」（MedKit 网页版）只接受以下三种产物形态，**任何 Agent/脚本不得偏离**：

| 产物 | 交付格式 | PDF |
|------|---------|-----|
| 押题卷 | **仅 MD**（`scripts/paper_builder.py` 导出 `押题卷_{科目}_{N}题.md`；题型归一为 **单选题/多选题/判断题**，供「大四上刷题」导入）。**HTML 交付已下线**（`quiz_template.html` 仅历史遗留，不再产出） | **一律人工上传**，管线/脚本禁止生成 |
| 题库 | **MD + HTML**（MD：ALL_questions_FIXED.md；HTML：render_qbank_html.py） | **一律人工上传**（用户手动提供） |
| 复习资料 | **MD + HTML**（MD：MedReview；HTML：render_review.py） | **一律人工上传** |

- 禁区：`大三下/` 与 `最终产物/` 内不得产出 `.pdf`；禁止任何脚本调用 weasyprint/pdfkit 等 PDF 工具链。
- 复习资料 MD 仅使用站端渲染器子集：h1-h6/表格/粗斜体/代码块/**Obsidian Callout（> [!TYPE]）**/**`<details open>`**/列表/hr；**禁 Mermaid**（用 ASCII 图）、禁其它 HTML 标签、禁 YAML front matter。
- **复习资料导出保真（E4 · 2026-10-15 新增）**：强调一律写 `<b>`（E1），**打印 CSS 必须**对其显式 `font-weight:700 !important` 且字面落在**有真粗体**的字体（雅黑/思源黑），**禁止**正文只落在无粗体字面的宋体系（SimSun/宋体）——否则 Obsidian/Chromium 导出 PDF 时**内联加粗整体消失**；打印样式须全局 `print-color-adjust: exact` 且字体栈带 emoji 字体，保 🔴🟡🟢 **彩色**（否则导出/阅读器中丢色）。导出后必须抽检：1 处 `<b>` 关键术语为真粗体 + 🔴🟡🟢 为彩色（用 Chromium 内核阅读器核验）。实现：`scripts/obsidian-snippets/medagentwork-print.css` 的 `@media print` §7.0；回归防护：`tests/test_obsidian_snippet.py`。
- 交付前清理流程残留（`📦 复习资料批次 X/Y`、`✅ 批次完成`、`⏭️ 下一批`、`V1-V13 自检报告`）—— 用 `scripts/clean_produce_markup.py`。
- 押题卷 MD 题目标题只允许 `### N. [单选题｜多选题｜判断题｜Bloom] qid` 形态，题型标签仅取 **单选题/多选题/判断题** 三值；标题与元信息行**禁止**出现 "统一模板"、"TEST"、内部版本号。
- 门禁：产物进入 `大三下/` 前必须 `python scripts/verify_produce_rules.py`（FAIL==0）。

## HC-20 教师重点原文锚定与逐条覆盖（2026-10-18 新增 · Agent 5 主责 · 不可违反）

> 驱动缺陷（batch039 实证）：教师重点原文第15条"突发性聋应尽早进行听力学检查和专科评估，可在发病**2周内**考虑糖皮质激素初始治疗；恢复不完全者可在发病**2～6周**评估鼓室内糖皮质激素挽救治疗"，在生成的复习资料里被概括成"突发性聋属耳科急症，一线药物为糖皮质激素"——**两个时间窗与"听力学检查时机"全部丢失**。
> 根因：AI 默认走「理解→概括→重组」，概括那一步即是信息丢失点。正确路径是「原文→逐条覆盖→展开」。

- **定性**：教师重点/复习大纲 = **权威范围契约（下限）**，不是"参考素材之一"。Agent 5 的输入来源优先级中，**教师重点原文高于上游备考复习资料**（备考资料是二手概括，只能用于增强，不得替代逐条覆盖）。
- **三条硬动作（有教师重点输入时强制）**：
  1. **逐条覆盖**：交付前产出 `中间产物/{batchID}/{科目}_教师重点覆盖矩阵.md`（过程产物，**严禁写入交付 MD**），「未覆盖 / 部分覆盖」行数必须为 0；
  2. **原文锚定**：重点条目的数值、时间窗、分级/分期界值、剂量、百分比、比例、专业术语、并列（顿号/分号）与禁止（严禁/不宜/不应/不能）结构，以**原文字面**出现在对应考点内，强制落点行 `📌 重点原文（第X条）：{照录原文关键句}`；
  3. **来源标记**：来自教师重点的考点加锚点 `（教师重点第X条）`。
- **条号基准（2026-10-19 加固）**：`第X条` 一律取 **`--keypoints` 文件第四节「统一锚定清单」的连续编号**（唯一坐标）。来源文档自身标号常有**跳号/重号**（batch040 实证：源①缺 13、37，78 与 86 各重复一次），**禁止直接沿用印刷标号**——否则落点整体错位（batch040 返工重编 72 行）；锚定清单每行尾部以 `〔源X原标号N〕` 供倒查。落点行正文须**逐字照录该条原文**（全部数值/时间窗/界值/百分比/并列与禁止结构须完整落在该行内）。
- **冲突裁决**：**原文锚定 > 原创性**。行为约束"不逐字复制任何单一来源"仅约束教材/RAG 正文的叙述性文字，**不适用于教师重点条目**——教师重点是范围与强调的唯一权威载体。
- **机械化门禁（HC-12 扩展）**：`python scripts/check_keypoint_coverage.py --keypoints <教师重点原文> --md <主复习资料 MD> [--allowlist <文件>]` → 数值/时间窗类硬事实缺失 → **FAIL，退出码 1 → 回退 Agent 5 补写，不得放行**；无教师重点输入的批次 → 显式 `SKIPPED`，**不视为通过**。终审前由 Agent 1 执行。
- **规则文本**：完整 D0 段、V17 自检见 `Prompt版本/Agent5_MedReview_Prompt.md`；DSH 侧执行细则见 `.dsh/skills/medreview/SKILL.md` 与 `.dsh/skills/medbatch/SKILL.md` §3。

## HC-21 站点发布最新性契约（2026-10-19 新增 · Agent 1 主责 · 不可违反）

> 驱动事故（batch040 实证）：本地把新题库/复习资料部署到生产后 **3 分钟**，被另一次生产部署（来源提交 `4531093`，本地没有）顶掉 → 线上 index.html 回到旧版（5,791 题 / 8 科 / 无「教师重点版」条目），用户打开网站看不到新资料。另叠加一处隐性半更新：index.html 里**硬编码**的「8 科」文案没跟着数据数组改（卡片有了、标题还写 8 科）。

- **单一事实源**：站点内容只认 `origin/main`。部署前必须 `git fetch`，且 **behind=0 且 ahead=0**（本地与 origin 完全同源）。`ahead>0`（未 push）→ 默认**拒绝部署**，先 `git push`；`-AllowAhead` 是显式逃生阀（会打警告：后续他人/CI 部署可能把线上顶回旧版）。
- **部署后置校验（机械化，不可跳过）**：`python scripts/check_site_freshness.py --expect-commit <本次提交>` 必须 PASS：
  - **L1 本地**：index.html 里「N 科 / N 题」**硬编码文案**与 `REVIEWS_S1` / `BANKS_S1` 数据数组长度一致；每条 pdf 路径在仓库内存在；
  - **L2 线上**：线上 index.html 的数组条目数、统计数字集合、每条 pdf 路径 与本地一致（防「卡片没上线」）；
  - **L3 最新部署**：线上「最新 Production/main 部署的 Source」== 本次提交（防被更晚的部署顶替）。
  - FAIL → 视为部署失败/被顶替 → 立即告警并重部署；**禁止用旧内容覆盖**线上更新的版本，应先合并再部署。
- **文案与数据同源（同一提交内）**：新增/下线任一条目，必须同时改：① 数据数组；② 分区大标题「N 科」；③ 分区副标题（教学计划版 N 科 / 教师重点版 N 科）；④ 页面统计数字（题库注册量、学科数）。缺一即半更新。
- **并发发布**：同一发布窗口只允许一个发布者；线上出现更新的部署时先合并。
- **实现**：`scripts/check_site_freshness.py`（门禁）；`scripts/deploy_site.ps1`（前置 ahead/behind 闸 + 部署后自动调用门禁）。CI 侧同样以 `origin/main` 为唯一源。

## HC-22 真题检索与双族配额（2026-10-20 新增 · **2026-10-26 修订：CMExam 可直接用于执业医师配额**）

> 从下一次**题库**批次起：约 **1/5 考研真题 + 1/5 执业医师真题**；检索不到就**减量或不插入**，用原创补齐；教师重点优先于凑比例。押题卷暂不适用本配额。
> 旧 HC-18 的「考研 20%」条款由本节接管；HC-18 仍保留「产物形态契约」含义，避免编号双用继续扩散。
> 2026-10-26 修订要点：执业医师配额**总量不变（仍 20%）**；`zhiyi_pdf`（历年真题）与 `zhiyi`（CMExam）均为族内合法来源、可直接入选；同等相关时历年真题有轻微优先加分（`TIER_BONUS`），但**不再强制先用完 PDF**。语料建设见 HC-23。

- **数据源（只读）**：
  - 考研真题：`GoldenSet/structured/` → `question_bank/real_questions/kaoyan_items.jsonl`；
  - **执业医师历年真题（族内来源一）**：2010–2023 扫描册（另含 2007–2009、2024）→ `question_bank/real_questions/zhiyi_pdf_items.jsonl`（印刷答案，`answer_confidence=high`）；
  - **执业医师 CMExam（族内来源二，可直接入选）**：`知识库素材/cmexam/` → `question_bank/real_questions/zhiyi_items.jsonl`（test 高可信 / train 中可信，train 按 D21b 抽检）；
  - 可选授权源：人卫题库（有授权时 `license=public`）。
  - 配额按**来源族**结算：考研族 = `kaoyan`；执业医师族 = `zhiyi_pdf` + `zhiyi`。
- **批次启动（Agent 1）**：
  `python scripts/real_question_cli.py plan --subject {科目} --target {题数} --batch {batchID} --keypoints {教师重点锚定清单} --blueprint {出题蓝图} --out 中间产物/{batchID}/real_question_plan.json`
  - 产出逐题 `source_id / family / tier / keypoint_refs / answer_confidence / license / mode`；
  - `quota_status` 取值：`met` 达标｜`reduced` 按可用量减量｜`cancelled` 无候选取消该族配额｜`deferred` 候选存在但人类专属核验未完成（HC-28，必须写 `hc28_update`）｜`disabled` 配额为 0；
  - `reduced` / `cancelled` / `deferred` **不再阻断批次**，但必须保留 `reason`（`no_candidate` / `candidates_exhausted` / `keypoint_or_module_limit` / `human_verification_deferred`）与检索日志，**禁止用无关题凑数**，缺口由原创补齐。
  - **状态自洽硬约束**：`cancelled` 只能用于“确实没有候选”（`available=0` 且 `plan.selected` 无该族候选）；候选存在却未落位必须用 `deferred`，禁止用 `cancelled` 冒充无候选；`check` 对 status/reason/available/selected 不一致直接 FAIL。
- **答案可信**：只有 `answer_confidence=high/medium` 的题可入选；`low` 一律不插入。考研答案以 `question_bank/kaoyan_answers.json` 的 `answer_recovered` 为准，**禁止**再用下册行首前缀 `ABCD/ABCDE`。来源优先级：扫描版绿色标记（high/medium）≈ PDF 标准答案/人工转录（high）> PDF 绿色标记（medium）> 解析规则（high/medium）；跨版本 PDF 题号可能错位，冲突时以扫描版原书绿色标记为准。执业医师历年真题以**扫描册印刷答案**为唯一依据，OCR 未取到答案的题一律不入库（`answer_confidence` 不足即不可选）。
- **真题标注（三处缺一不可）**：
  1. 元数据：`kaoyan_origin{gs_id,year,source,mode,answer_confidence}`，或 `zhiyi_origin{source_id,source,corpus,mode,answer_confidence}`，其中 `corpus = "pdf_paper"`（历年真题）/`"cmexam"`（CMExam）；
  2. 溯源锚点：`[源:考研真题 GS-XXX]` / `[源:执业医师真题 {YYYY}年第{单元}单元第{题号}题]` / `[源:执业医师 CMExam-XXX]`；
  3. 每题 `keypoint_ref`（HC-20 统一锚定清单编号）与 `license`。
- **MedGen**：只插入 plan 中 `selected` 的题；保留原题题干/选项/答案/数值；不得把 `考点重构` 标成 `原题`；配额不足部分由原创补齐。
- **MedQC**：D21 扩展为 D21a（考研）/ D21b（执业医师，含 `corpus=pdf_paper` 与 `cmexam` 两类）：答案、考点、数值、选项映射全比对；`license` 差异**仅记录、不判 FAIL**（2026-11-03 取消上架授权门禁）；`medium` 答案 100% 抽检；冲突 `must_escalate`。
- **终审门禁（Agent 1）**：
  `python scripts/real_question_cli.py check --file 最终产物/{batchID}/ALL_questions_FIXED.json --plan 中间产物/{batchID}/real_question_plan.json --keypoints {教师重点锚定清单} --out reports/validate/real_question_check_{batchID}.json`
  FAIL（比例/答案/重复/覆盖/溯源任一）→ **halt**，不得用旧 `--golden-absent` 绕过。比例校验按**族**结算（执医族 = 历年真题 + CMExam 之和，15%–25%）。
  **license/版权**：2026-11-03 起**不再作为上架门禁**（用户明确「不用管上架版权」），字段仅作来源记录；`public_gate` 的 G0/G3 恒 INFO，不阻断发布。**配额仍然保留并强制执行。**
- **旧工具**：`scripts/kaoyan_picker.py` 已改为读取可信答案表；`--allow-unverified` 仅诊断用，不得进入生产。

## HC-23 执业医师历年真题语料（2026-10-22 新增 · 扫描册 OCR → 题目索引）

> 把「执业医师真题及答案（2007–2024）」扫描册转成可检索的题目级索引。语料跑一次、长期复用；批次只读索引，不在批次内跑 OCR。

- **原始素材（只读，仓库外）**：`C:/Users/38063/Desktop/27网盘/执业医师真题及答案（2010-2023年）/`，49 册 / 2286 页（2007–2016 单元册 + 2017–2023 全年册 + 2024）。全部为无文本层扫描件，**必须 OCR**。
- **OCR 引擎按版式分流（实测结论，不得随意更换）**：
  - **单栏册（2007–2016、2022–2024，44 册）**：本地 `RapidOCR`（onnxruntime）。实测同一册（2014 三单元）MinerU pipeline 与 vlm 模型均整行吞掉 4 条 `【答案】` 行，故单栏册**禁止**用 MinerU；
  - **双栏册（2017–2021，5 册）**：必须用 **MinerU API**。RapidOCR 的检测器会把同一行的左右栏并成一条长行（题目与答案区都被污染），无法还原；MinerU 按版面还原段落，题目顺序正确。MinerU 会丢个别选项/答案行（约 10%），由下方质量门禁拦截，宁缺毋滥。
- **流水线（三段，可断点重跑）**：
  ```text
  清点   python scripts/zhiyi_pdf_ocr.py scan
  OCR    python scripts/zhiyi_pdf_ocr.py run --workers 8        # 单栏册 → 知识库素材/执业医师真题/_ocr/<册>.jsonl（不入库）
  双栏   python scripts/zhiyi_pdf_mineru.py                # 2017–2021 → 知识库素材/执业医师真题/_mineru/<册>.md（MinerU，不入库）
  解析   python scripts/zhiyi_pdf_parse.py                        # 自动优先用 _mineru/<册>.md → zhiyi_pdf_raw.jsonl
  入库   python scripts/real_question_cli.py build                # 去重 + 学科标注 → zhiyi_pdf_items.jsonl
  ```
  换素材目录：`set ZHIYI_PDF_DIR=<新目录>`（或 `--pdf-dir`）。
- **解析质量门禁（每次重建后必须看 `reports/validate/zhiyi_pdf_parse_report.json`，按通道分别判定）**：
  - 单栏册（rapidocr）：单册有效率（`kept / blocks`）≥ 95%，`no_answer` = 0，`bad_options` ≤ 2%（实测 2007–2016/2022–2024 全部 0.97–1.00）；
  - 双栏册（mineru）：单册有效率 ≥ 70%（MinerU 丢行/选项截断，已知损耗；实测 2017 0.88、2018 0.94、2019 0.92、2020一 0.82、2020二 0.70、2021 0.94）；
  - 双栏册答案配对：A3/A4、B1 组内题号会重排，`answers` 键 (单元,题号) 会互相覆盖——解析器在「某单元答案条数==该单元题块数」时按出现顺序一一配对，两条路都失败才判 no_answer；
  - 任何一项不达标 → 先修解析规则再重跑，**禁止手工挑题绕过**。
- **版面规则（已覆盖，改动需回归全部 49 册）**：单栏同行选项／单栏分行选项／双栏（2017–2021 试卷部分）／`（共用题干｜共用题目｜共用病例）` A3·A4 病例组（题号在每个病例内从 1 重排）／`（共用备选答案）` B1 组（选项只印一次，逐题只印空 A–E）／册末「参考答案与解析」区（题号+字母配对回填）。
- **数据形态**：`source=zhiyi_pdf`，`exam=执业医师`，带 `year` / `module="第N单元"` / `question_no`；`license=public_noncommercial`（用户声明仅非商业个人刷题）；学科由关键词标注，基础/人文类（生理、生化、病理、人文、预防）可能落 `未分类`，不参与临床学科配额，属预期。
- **红线**：原题题干/选项/答案/数值零改动；OCR 可疑（选项缺字母、答案越界、题干截断）→ 该题不入库，不得猜补。

## HC-24 题目学习价值层契约（2026-10-23 新增 · Agent 2/3/4 共同主责 · 不可违反）

> 驱动缺陷（batch040 实证）：旧产物解析中位 85 字、逐项干扰项结构 0%、错误认知字段 0%、难度校准仅先验；学生“会选”但不会“辨错”。**旧产物不追溯重写**（用户 2026-10-23 明确）；从下一批次起，新题库默认 `schema_version=2.0`，学习价值层为交付必需项。

- **适用范围**：新创建的题库批次（`item_schema_version=2.0`）。已签收批次与既有产物不追溯；如需增强，另开新批次或显式修订单。
- **每道题必须包含 `learning_value`**：
  1. `correct_rationale`：正确答案的机制/依据，≥60 字；不得只复述答案。
  2. `per_option`：覆盖全部选项。正确选项 `truth=true`、`misconception_id=null`；每个干扰项 `truth=false`、`why`≥20 字、`misconception_id` 与 `misconception` 非空。`misconception_id` 是**错误认知类别**（`MC-{学科}-{模块}-{NN}`），同批次同一 ID 必须对应同一释义（R19）。
  3. **反选题不变式**：`polarity=negative` 时，`truth` 表示“陈述本身真假”；正确答案选项 `truth=false`，其余干扰项 `truth=true`；`misconception` 解释学生为何忽略“不包括/错误/除外”。
  4. `key_takeaway`：可迁移的鉴别规则/记忆钩子，≥30 字。
  5. `source_quote`：逐字来自教师重点/教材/RAG 原文，并写入该题 `teacher_anchor`；`source_quote_status=exact` 时引文（省略号分段后）必须能在 `teacher_anchor` 中逐字命中；找不到就写 `paraphrase`/`missing`，**禁止自报 exact 或编造**。
  6. `anchor_status`：`verified|partial|mismatch|missing`；`mismatch` 必须回退重做。
- **机械化门禁**：`python scripts/check_learning_value.py --file <JSON>`；`FAIL>0` 不得交付；终审纳入 `gate_check.py --stage final` 的 `GATE-ITEM-LEARNING-VALUE`。
- **通过阈值**：逐项覆盖=100%，错误认知覆盖=100%，`source_quote_exact_rate≥95%`，`quote_verified_rate≥95%`，`misconception_id_conflicts=0`，`anchor_verified_rate≥80%`，`FAIL=0`；低于阈值 → halt → 回退 MedGen/MedFix。
- **与 HC-20 的分工**：HC-20 管复习资料对教师重点的原文锚定；HC-24 管题库每道题的学习价值层与逐项反馈，两者不得互相替代。

## HC-25 全流程质量基准与阶段门禁（2026-10-23 新增 · MedMaster 主责 · 不可违反）

> 驱动：T1–T6 已验证（基线冻结、KC 双向映射、题目学习价值层、12 维评分卡、advisory/enforce）。**旧产物不追溯**；新批次/新版本必须按 R0–R4 执行。

- **单一事实来源**：`scripts/quality_policy.json`（profile/阈值）；流程标准：`docs/质量管控规范.md`；门禁编排：`scripts/quality_gate.py`。
- **阶段**：R0 需求评审 → R1 开发实现 → R2 测试验证 → R3 发布上线 → R4 运行复盘。每阶段必须跑 `python scripts/quality_gate.py --stage rX --batch {batchID} --profile {profile} --mode {advisory|enforce}`，输出 PASS/WARN/BLOCKED/SKIPPED；**SKIPPED 不得视为 PASS**。
- **准入**：R2 未通过不得进 R3；R3 `enforce` BLOCKED 禁止发布；WARN 必须在 `reports/gate/*.md` 记录豁免理由、影响、补做计划、责任人；同一问题连续两个版本 WARN → 自动升级 BLOCKED。
- **门禁适用范围（2026-10-26 加固）**：批次 `product_types` 取 `question_bank|prediction_paper|review_material`（缺失时按产物形状推断）。A2/A3/A4 只对题库/押题卷生效；HC-9/10/11 只对复习资料生效；JSON 有效性只对题库/押题卷生效；复习资料批次 `--stage auto` 直达 final；v2 题库/押题卷批次在 A4 后自动插入 `learning_value` 阶段。
- **旧产物**：已签收/已发布产物冻结，不因标准升级回改；如需增强，另开新批次或显式修订单，并重新过 R0–R4。
- **与 HC-24 分工**：HC-24 管题库每道题的学习价值层；HC-25 管全流程阶段门禁、发布基准与证据留存，两者不得互相替代。

## HC-26 复习资料详细度契约（2026-10-27 新增 · Agent 5 主责 · 不可违反）

> 驱动缺陷：batch040 教师重点版 85 张卡平均正文仅 **377 字符**；47 张掌握级卡中 **0 张** 能同时回答“怎么认/怎么查/怎么治/和谁鉴别”；7 个模块 **0 个案例、0 个展开区**。读者读完仍需另找教材，“读一遍就够”未成立。

- **定性**：详细度不是字数，而是“读一遍后能否独立完成临床推理与应试判断”。字数只是下限；**槽位完整、信息单元密度、可检索自测**才是通过条件。
- **两种模式**：`teacher_keypoint`（教师重点/大纲输入）与 `course_schedule`（周/讲/课时输入）；无两者时按 `module` 常规模块版执行。有教师重点时，HC-20 逐条覆盖仍先于详细度展开，**不得用概括替代原文**。
- **卡片九槽位（掌握级全填 + 案例）**：`🎯 定位` / `🧬 机制` / `👁 识别` / `🔍 诊断` / `🩺 处置` / `⚖️ 鉴别` / `🚨 易错` / `🧠 记忆钩子` / `🔄 自测`，另加 `🏥 案例`。熟悉级填定位/机制/识别/诊断/处置/鉴别/自测；了解级填定位/识别/鉴别/自测。
- **量化下限（release）**：掌握 ≥900 字符且 ≥12 信息单元；熟悉 ≥550 / ≥7；了解 ≥250 / ≥4。超长（掌握 >3200 字符）必须拆分，禁止堆墙；每句须提供事实/机制/决策规则/鉴别点之一。
- **模块八块**：前置知识、摘要/目标、对比表（≥3 行）、因果链、案例推演（≥1）、主动回忆（答案可检索）、本章小结、展开区（≥2）；callout ≥4。
- **课程安排八块**：学习目标（掌握/熟悉/了解）、课前准备、课堂重点（≥3）、机制、案例、课后自测（含答案）、时间预算、前后衔接；每讲 ≥1200 字符且 ≥12 信息单元。
- **机械化门禁**：`python scripts/check_review_detail.py --md <主复习资料 MD> --mode auto --profile release_teacher_keypoint`（正式发布必须 PASS；`release_teaching_plan` 用同脚本）。报告落 `reports/validate/review_detail_*.json|md`，并接入 `quality_gate.py` 的 R2/R3 `review_detail` 检查。
- **不追溯**：旧产物冻结；新批次/新版本必须过 V18 自检。标准全文与证据见 `docs/复习资料详细度标准.md`。

## HC-27 概念标注强制（2026-10-27 新增 · Agent 2/3/4 共同主责 · schema 2.1 起必填）

> **回写说明（P1-S6 · 2026-11-02）**：本条此前只存在于 `Prompt版本/MedGen_current_prompt.md`
> 与 `scripts/check_source_concepts.py`，SOUL 里没有定义——新 Agent 读 SOUL 不知道有这条约束。
> 现补入，与提示词对齐。

- **字段**：每题 `concepts: [{role: primary|differential|related, keypoint: "第N条", title, evidence}]`。
- **硬性**：恰好 1 条 `primary`，其 `keypoint` 必须等于该题 `keypoint_ref`；A2/A3/A4/X 型 ≥2 条；`evidence` ≥8 字。
- **生成期给，不做事后推断**：事后推断在「一题一锚点」的题库上封顶 5%（急诊批次实测 4.9%）——
  多标签是生成期属性，补不出来。
- **门禁**：`python scripts/check_source_concepts.py --file <JSON> --batch <batch>`，`FAIL>0` 不得交付。
- **不追溯**：schema < 2.1 的历史产物不改写。

## HC-28 一次跑完与人工复核队列分离（2026-11-01 新增 · MedMaster/MedGen/MedQC/MedFix 共同主责 · 不可违反）

> 驱动缺陷（batch046 实证）：新管线把「原卷真伪、答案原页、版权授权、医学专家裁定」等人类专属核验写成生成的前置条件，模型无法完成 → 反复输出「待核验」、整批 BLOCKED，72 题原创 + 28 条候选全部停在待审稿。根因不是模型能力不足，而是**把「不可发布」误当成「不可完成」**，且提示词仍保留 Cherry Studio 时代的「回复确认 / 输入确认」交互门。

> **2026-11-03 修订（用户裁定）**：**取消「逐题人工医学核验」作为发布前置**。管线目的是让人类放心，不是逐题打断；A/B 级 + 确定性门禁通过即默认 `publishable`，不再要求逐题核验记录、逐题签收或第二人盲评。人工复核只针对 C 级/高风险/明确冲突，且只入队列、不阻断批次。`review_status` 默认 `agent_verified`（不再默认 `draft`）；`medical_verification` 记录「agent 自检」而非「待人工」。批次签收（signoff）改为**可选**的发布授权留痕，不再是发布必需环节。需要人工复核时，除 `review_queue.json` 外**必须同时输出同名 `review_queue.md` 人读版本**。

- **完成定义**：管线完成 = `generation_status=DONE`（全部题目已生成、确定性门禁已跑、复核队列已产出），不以「所有医学主张已人工核验」为前提。`release_status=PENDING_HUMAN_REVIEW` 不是管线失败。**逐题人工核验自 2026-11-03 起不再是完成或发布条件。**
- **问题分级**：
  - `AUTO_FIX`：结构、格式、配额、重复、学习价值字段等确定性可修复问题 → 自动修复；单题最多 2 轮，整批最多 3 轮；超限则隔离该题并继续。
  - `AGENT_VERIFY`：可用输入素材、教师重点、GoldenSet、RAG 片段做逐字/定位核验的问题 → 修复或隔离；不得升级为「等待人类」。
  - `HUMAN_ONLY`：原卷/答案原页/版权授权/医学专家裁定/指南冲突 → 只写复核队列，不阻断生成。
- **硬停止条件（仅限）**：输入缺失/不可读/损坏；输出连续 2 次无法解析为契约 JSON；工具/预算/权限故障。**可发布核心集为空不是停止条件**：仍输出完整待审稿 + 复核队列，标 `release_status=BLOCKED`（题目数量完整时 `generation_status` 仍为 DONE），交由人类处理。
- **状态分离**：`generation_status=DONE|PARTIAL|FAILED`；`release_status=READY|PENDING_HUMAN_REVIEW|BLOCKED`；批次报告必须同时给出两者，禁止用单一 `gate_decision` 混淆生成与发布。
- **每题 `release` 对象**：`disposition=publishable|pending_human|quarantined`、`evidence_grade=A|B|C`、`risk_level=high|medium|low`、`reason_code`、`agent_checks[]`、`human_check`、`suggested_action`。
- **证据分级与发布底线**：A = 输入素材/教师重点/教材原文逐字可定位；B = 教师重点覆盖或教材口径一致但无逐字引文；C = 仅模型知识、无可定位来源。高风险题（剂量/时间窗/复苏/禁忌/儿科/急救）C 级 → `quarantined`；低风险 C 级 → `pending_human`；**A/B 且确定性门禁通过 → `publishable`（默认，无需逐题人工核验/签收）**。`pending_human` 只用于 C 级或明确冲突，不得因为「没有人工逐题看过」而批量把 A/B 降级。
- **输出契约**：批次必须输出 `review_queue.json` **和同名 `review_queue.md`（人可读，2026-11-03 起强制）**；最终交付 MD 末尾附「人工复核队列」；队列每条含题号、处置、证据等级、风险、原因、已做检查、人工需核、建议动作。队列为空时 MD 也要输出「无待人工复核项」。最终回复只报告状态、数量、路径，不得以「请确认 / 待核验」结束本轮执行。
- **交互门废弃**：DSH/subagent 模式下，MedGen HC-6 回显、MedQC Step 5「输入确认」、MedFix/MedMaster「等待用户确认」一律视为旧 Cherry Studio 遗留，**不得实际等待**；批次启动时由用户一次性确认范围，之后连续执行到交付。
- **机制依据**：MAST（Cemri et al., 2025, arXiv:2503.13657）把「不知道终止条件」「验证失败」列为高频失败模式；Anthropic《Building effective agents》要求 evaluator-optimizer 有明确终止条件；Guardrails AI 的 `on_fail` 提供 fix/reask/filter 等非中断动作；OR-Bench（Cui et al., 2024, arXiv:2405.20947）证明过度拒答是独立失败模式；Self-Refine（Madaan et al., 2023）要求最大轮次与停止指标。结论：**不确定应作为数据向下游传递，不应作为控制流中断**。

## HC-19 插图管线 —— 已整体下线（2026-11-02 人工裁定，编号保留不复用）

> **状态：RETIRED / 禁止启用。** 用户 2026-11-02 明确「以后不需要插图相关」。原 HC-19 插图契约
> （生图阶段 6 / 配图清单 / GATE-A5 配图项 / GATE-A6 插图门禁 / `medillustration` skill / 豆包交接）
> 全部退役，与 `medagentwork-skill/CHANGELOG.md` 所记「插图管线 v2.2 已整体移除」口径一致——
> 此前的「两者谁为准」矛盾由此关闭，**以本条为准**。

- **禁止**：任何新批次在复习资料 / 题库 / 解析中写入插图占位符 `![图N：…](images_webp/…)`、输出 `*_配图清单.md`、创建 `images_webp/`、调用 `annotate_image` 标注、做图谱选图或 AI 生图交接。涉及配图的历史提示词条款、门禁项、skill 均已同步移除。
- **不追溯**：已交付/已签收历史产物中的图片与配图清单原样保留（历史产物不可篡改），不回改、不删除、不作为新批次参照。
- **保留兼容**：`render_review.py` 对既有 `![]()` 语法的渲染支持不变（老 MD 仍可正常导出），这只是渲染兼容，不是插图能力。
- **留档位置**：脚本与配置 → `archive/retired/illustration/`；skill 全文 → `archive/retired_skills/medillustration/`。
- **编号纪律**：HC-19 号位保留，不回收给新条款，避免历史文档引用歧义。

## HC-29 干扰项生成协议（2026-11-02 新增 · Agent 2 主责 · schema 2.2 起必填）

> **回写说明（P1-S6 · 2026-11-02）**：本条此前只写在提示词里（`### HC-29`），SOUL 无定义。
> 现补入；提示词里的完整操作细则（top-3 鉴别表、机制枚举释义）仍以提示词为准，本条只钉义务与门禁。

- **先列鉴别再写选项**：`competing_dx` 按可能性降序列 3 个竞争诊断，第 1 条必须用作干扰项①；
  列不出 3 个说明这题只考记忆（按 L1 处理，或补条件重写题干）。
- **每个干扰项带机制标签**：`learning_value.per_option[].distractor_mechanism` ∈
  {`similar_presentation`, `adjacent_concept`, `direction_error`, `timing_error`,
  `population_mismatch`, `mechanism_confusion`, `overgeneralization`, `outdated_guideline`}；正确项留 `null`。
- **错误认知必须可复用**：同一 `misconception_id` 只能有一种释义（R19）；同一错误认知跨题必须复用同 ID。
  历史上 645/645 个 ID 全不重复 —— 标签退化为题内私有，沉淀不出任何概念（X6 实测 0%）。
- **反选题另有三条**（P2-S4 追加）：整批占比 ≤15%（X5）；`polarity` 如实标注；4 个为真干扰项逐项 `source_anchor`。
  反选题的干扰项是**正确说法**，要求的是「这句对的话出自哪段」，不是 `misconception_id`。
- **门禁**：`python scripts/validate/rules_batch.py --file <JSON>`（S-STRUCT 必须 PASS）+ `check_learning_value.py`（R15/R19）。

## Boundaries

- ❌ **不提供医疗诊断** — 仅基于已发表文献出题/质检
- ❌ **不编造研究结果** — 没有就说"未检索到"
- ❌ **不修改 GoldenSet** — 金标准由用户手动维护
- ❌ **不跳过质检步骤** — 5 步工作流不可省略（MedGen→MedQC→MedFix→MedReview→发布；签收可选，非发布必需）
- ❌ **不手改 workflow_state.json** — 走 scripts/workflow_state.py（HC-17）
- ❌ **不产出 PDF** — 押题卷/题库/复习资料 PDF 一律人工上传（HC-18）
- ❌ **不以“旧批次未追溯”为由跳过新批次 HC-24/HC-25** — 旧产物冻结，新批次/新版本必须过门禁
- ❌ **不因人类专属核验（原卷/版权/专家裁定）停止生成** — 写入复核队列并继续（HC-28）
- ✅ **可以**：交付带 `PENDING_HUMAN_REVIEW` 标记的完整产物与复核队列
- ✅ **可以**：出题、质检、修改、追溯、汇总统计
