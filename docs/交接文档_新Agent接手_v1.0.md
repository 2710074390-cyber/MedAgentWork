# MedAgentWork 交接文档 —— 新 Agent 快速上手（v1.0 · 2026-09-04）

> **读者**：接手本项目的任何/多个 Agent 软件（Claude Code、Cherry Studio 智能体、Cursor、其他 Harness 实例均可）。
> **用法**：把本文档作为新 Agent 的「第一条系统提示」或首批上下文粘贴进去，然后按 §10 的 Checklist 执行。
> **核对日期**：文中所有状态、路径、数据均于 2026-09-04 核对；跨天使用前先跑一遍 §7 的 `--check` 类命令确认无漂移。
> **一句话传承**：MedAgentWork = 「临床医学教材 + 考研真题」→ 五阶段 Agent 管线 → 结构化题库 / 复习手册 / 押题卷 → 线上站，**门禁强制、铁律优先、PDF 一律人工**。

---

## 1. 项目是什么

- **位置**：`C:\Users\38063\Desktop\MedAgentWork`（Windows，中文路径，命令中加英文双引号）
- **目标**：把临床医学教材章节 + 1994–2025 考研西综真题，量产为三类产物：**题库**（JSON→MD/HTML）、**主复习资料**（MD→HTML→PDF）、**押题卷**（HTML）→ 上架到站点 `大三下/`（已发布 https://med-review-site.pages.dev）与 `大四上/`
- **生产系统**：5 个角色 Agent 串行管线 + 机械化门禁。角色完整提示词是核心资产，见 §3「角色提示词」行
- **输入**：用户教材全文 txt（带页码锚点）+ 本地 RAG 索引（付费 API，成本纪律见 §9）

### 当前所处阶段（2026-09）

| 线 | 状态 |
|----|------|
| 大三下（7 科：内/外/神经/精神/中医/中医心理/医患沟通） | ✅ 全部完成：题库 6 科 PDF + 押题卷 5 套 + 复习资料 7 科，已上线 |
| 大四上 · 教学计划版复习资料（8 科，**无题目版**） | 🟡 已完成 5 科（内科 23 模块/外科二 8/妇产 14（另有深度版）/急诊 11/耳鼻喉 5）；**待生成 3 科：传染病学、眼科学、口腔科学** |
| 题库批次 | ⏸️ 无活动批次（`active_batch=null`）；最后签收 batch027（内科学·呼吸 100 题，2026-08-20） |
| 大四上题库/押题卷 | 未启动（可选 Phase 3，默认不做） |

**当前唯一主线 = 大四上 3 科复习资料生成**，执行依据：`docs/大四复习资料生成方案_v1.0.md`（2026-09-04，**含用户待确认决策清单 §9**；开工前必须先确认）。

---

## 2. 当前主线任务：大四上 3 科复习资料

### 任务表（方案 v1.0 §5、§7）

| 顺序 | 科目 | 建议批号 | 模块 | RAG code | 状态 |
|:---:|------|:---:|:---:|----------|------|
| 1 | 传染病学（第10版，李兰娟） | batch028 | 7 | `infectious-diseases` | 素材+索引就绪，**可立即开工** |
| 2 | 眼科学（第10版，范先群/颜华） | batch029 | 10 | `ophthalmology` | 同上 |
| 3 | 口腔科学（第10版，郭传瑸/程斌） | batch030 | 9 | `stomatology` | **需先向用户要本校教学大纲**（无大纲按建议 9 模块执行） |

### 三大硬约束（复习资料生产，违反即返工）

1. **页码锚点真实**：引用教材必须用真实印刷页（hc-10），页偏移必须**先实测后使用**（急诊 N−17、内科 N−31 先例），禁止占位符。文本中页码分隔符为 `===== 第 N 页 =====`（N=PDF 页）。
2. **产物形态（HC-18 契约）**：复习资料 = MD + HTML（`render_review.py` 渲染）；**PDF 一律人工打印**，任何脚本禁止生成 PDF。
3. **v5.2 导出兼容（E1-E3）**：行内强调用 `<b>`/`<i>`（**禁用 `**`/`*`**）、折叠区用 `#### 🔬 展开：名称`（**禁用 `<details>`**）、0 Mermaid（用 ASCII 图）、0 流程残留（`✅ 批次完成`/`V1-V14 自检报告` 等），详见 `docs/产物格式规范.md` §3。

### 生产配方（方案 §6 的 9 步，已实操 3 次，直接照抄）

```
S1  建工作目录：中间产物/{code}_review/（如 infectious_review/、ophthalmology_review/）
S2  写 00_编写规范与素材映射.md：
    - 页偏移测定（目录印刷页 vs txt 页码锚点对照，≥3 处验证）
    - 教学内容块 → 模块分配表（含 txt 行号范围；用 grep 定位章首）
    - 贺银成补充定位（grep 讲义中/下册，无则如实声明跳过）
    - 格式契约 v5.2 要点摘录（参考 中间产物/ent_review/02_格式契约_v5.1.md）
S3  并行子 agent（每模块 1 个；prompt 含角色提示词 + 模块范围 + 行号范围 + 契约摘录）
S4  子 agent 产出 模块N_XXX.md → 主会话逐份核对（页码非占位、无试题形态、无流程残留）
S5  主会话写：科目导航（一句话核心逻辑链/命题规律/复习路径/避坑提示）+ 使用指南
    + D3 谱系总览 + 模块速览 + D5 跨模块概念地图 + 附录一页码索引/附录二术语表(HC-9)/附录三口诀
S6  合并 → {科目}_主复习资料.md（放入 复习资料/{科目}教学计划版/）
S7  机械约束自检（沿用 中间产物/ent_review/check_fences.py 思路）：
    callout ≥ 模块数×4 | 展开区 ≥ 模块数×2 | 每模块 D2 图 ≥1 | D4 树 ≥1 | 对比表 ≥5/模块
    V14：`**`计数=0、`<details>`计数=0、`<b></b>`配对、0 Mermaid、0 批次/自检残留、0 试题形态
S8  python 知识库素材/render_review.py "{文件}" → 自包含 HTML（--dark 默认）
S9  人工：浏览器打印→PDF → 大四上/复习资料/；跑 verify_produce_rules.py（PDF 走人工上传标记）
```

**范本**（结构照抄）：
- `中间产物/emergency_review/00_编写规范与素材映射.md`（最完整，4 块 11 模块分工）
- `复习资料/妇产科学教学计划版/妇产科学_主复习资料_深度版.md`（**v5.2 最新写法范本**：`<b>/<i>`、无 `<details>`、无题目版、导航 4 段式）
- `复习资料/内科学教学计划版/内科学_主复习资料_合订本.md`（23 模块纯连续版排版范本）
- `中间产物/ent_review/02_格式契约_v5.1.md`（格式契约）

**注意**：本阶段只产复习资料，**不产题库**，因此**不执行 HC-18 考研真题配额**（配额仅适用于题库批次，见 §5）。

---

## 3. 目录与关键文件速查（Agent 只读写自己负责的目录）

```
MedAgentWork/
├── SOUL.md  CONTEXT.md  USER.md        ← 共享规则（硬约束/工具路径/用户画像），开工先读
├── README.md  操作流程.txt             ← 用户操作手册（DSH 版速查）
├── workflow_state.json                 ← 批次状态机（禁止手改！只经 scripts/workflow_state.py，HC-17）
├── gate_check.py  validate_options.py  healthcheck.py  save.py  ingest.py  verify_page_numbers.py（根级门禁）
│
├── Prompt版本/                         ← ★核心资产：5 个角色完整提示词（单一事实来源）
│    MedMaster_current_prompt.md / MedGen_current_prompt.md / MedQC_current_prompt.md
│    MedFix_current_prompt.md / Agent5_MedReview_Prompt.md
├── .dsh/skills/                        ← DSH 技能（medmaster/medgen/medqc/medfix/medreview/medbatch）
│    （新软件无 skill 机制时，直接用 Prompt版本/ 文件做角色提示词，效果等价）
├── 输入素材/大四上/{8科}/{教材}_第X版_v1.txt   ← 教材全文（页码锚点 ===== 第 N 页 =====）
├── 知识库素材/                          ← RAG 系统（23 学科入口/26 索引/混合检索）
│    search_kb.py  embed_index.py  validate_configs.py  render_review.py  subject_config.json  configs/  index_store/
├── QuestionBank（question_bank/registry.jsonl）  ← 统一题库注册表（4,296 题，qbank.py 维护）
├── 中间产物/ 质检报告/ 最终产物/         ← 管线各阶段产物（按 batch{NNN} 子目录）
├── 复习资料/{科目}教学计划版/            ← 大四上复习资料现行交付目录
├── GoldenSet/                            ← 真题素材+金标准（← 只读！用户手动签收）
├── scripts/                              ← 门禁与工具（~40 个，见 §7）
├── schemas/  tests/                      ← 输出契约 JSON Schema + 回归测试（64 用例）
├── docs/                                 ← 技术文档（≤5 活跃：项目介绍/TODO/产物格式规范/目录结构说明/大四方案）
├── memory/JOURNAL.jsonl                  ← 事件日志（批次关键事件记这里，一行一条）
├── 大三下/  大四上/                      ← 站点产物目录（上架物；禁止出现 .pdf 之外的杂文件）
├── archive/                              ← 统一归档（中间/最终/质检/reports 按批次）
└── reports/                              ← 脚本报告（validate/gate/healthcheck/maintenance 子目录）
```

**7 条文件铁律**（CONTEXT.md §文件管理，违反=返工）：根目录白名单 / 报告入 `reports/` / 统一归档 / 无副本 / 脚本输出路径锁定 / `__pycache__` 清理 / docs ≤5。

---

## 4. 生产流程 A：题库批次（Phase 3 可选，按大三下模式）

生命周期（详见 `.dsh/skills/medbatch/SKILL.md`）：

```
启动(登记批次) → MedGen → GATE-A2 → MedQC → GATE-A3 → MedFix → GATE-A4 → MD导出
→ MedReview → 终审门禁 → 用户签收(APPROVED) → 用户手动移入 GoldenSet → 归档
```

**阶段与目录**：Agent2 出题 → `中间产物/{batchID}/ALL_questions.json`；Agent3 质检 → `质检报告/{batchID}/`；Agent4 修复 → `最终产物/{batchID}/ALL_questions_FIXED.json + ALL_questions_FIXED.md（最终交付 MD，强制）+ AGENT4_追溯日志.json + AGENT4_修改声明.md`；Agent5 复习手册 → `复习资料/`。批次号 `batch{NNN}`。

**出题硬约束**（全文在 SOUL.md，要点）：
- HC-1~4b 题型极性/Schema/溯源锚点/禁幻觉/真题答案保护；HC-7 双向细目表（Bloom 30/40/25/5）；HC-14 选项用**结构模板**（同语法结构）而非字数范围；HC-15 Bloom 每 50 题采样（`bloom_sampler.py`）；HC-16 押题考频增强；**HC-18 考研真题配额：约 1/5（目标 20%，合格带 15–25%）为考研原题引用/改编，标注 `kaoyan_origin` + `[源:考研真题 GS-XXX]`；无真题覆盖章节以原创补齐并如实标注**
- 选项设计 NBME 八项：禁绝对词/长度比 ≤1.5/语法一致/数值排序/词重复/收敛策略/B1 共用选项专项

**门禁不可跳过（HC-12 教训：5 起绕过事件）**：每阶段转换前实测门禁，BLOCKED → halt → 回退上游修复 → 清 halt（`--clear-halt`）→ 重跑，绝不"相信下游自觉"。

---

## 5. 门禁与校验命令速查（全部在项目根目录运行）

### 题库批次
```text
python validate_options.py --batch {batchID}           # GATE-A2，FAIL==0 才放行
python gate_check.py --batch {batchID} --stage agent3_done   # GATE-A3
python gate_check.py --batch {batchID} --stage agent4_done   # GATE-A4
python scripts/qbank.py export-md --file 最终产物/{batchID}/ALL_questions_FIXED.json  # 最终交付 MD（强制）
python scripts/kaoyan_picker.py check --file 最终产物/{batchID}/ALL_questions_FIXED.json  # HC-18 占比，<15% exit 1
python gate_check.py --batch {batchID} --stage final   # 终审（先跑第 5 行）
python scripts/fact_check.py pages --file 中间产物/{batchID}/*.json --subject {code}  # 页码反查（GATE-A2 前）
python scripts/fact_check.py golden --file 中间产物/{batchID}/*.json                  # GoldenSet 交叉验证
python scripts/workflow_state.py --show {batchID} / --check        # 状态读写（唯一入口，HC-17）
```
批次启动时：`python scripts/kaoyan_picker.py pick --subject {科目} --keywords "..." --target {ceil(题数×0.2)} --out 中间产物/{batchID}/kaoyan_candidates.json`

### 复习资料（当前主线）
```text
python 知识库素材/render_review.py "复习资料/{科目}教学计划版/{科目}_主复习资料.md"   # → 自包含 HTML
python scripts/verify_produce_rules.py       # 产物形态门禁，FAIL==0 才可上架
python scripts/clean_produce_markup.py       # 交付前清理流程残留（成品化）
python scripts/healthcheck.py                # 全系统巡检（7 维度 164 项）
python scripts/run_tests.py                  # 回归测试 64 用例
python 知识库素材/validate_configs.py       # RAG 配置校验（改配置后）
```

---

## 6. 资源清单（已就绪，勿重复下载/索引）

| 资源 | 位置 | 说明 |
|------|------|------|
| 教材全文 | `输入素材/大四上/{8科}/{科目}_第X版_v1.txt` | 页码锚点文本层；**教材正文是唯一内容来源**（网络资料只作考情参考，禁止摘抄入库） |
| RAG 索引 | `知识库素材/index_store/` 26 个索引 | 3 科待生成均 indexed；`search_kb.py "查询" --subject {code} --no-rerank`（降级省钱，缓存默认开） |
| 考研真题 | `GoldenSet/`（只读）：上册 5,168 题题干/选项 + 下册 4,448 条答案/解析（gs_id 配对）+ `GoldenSet/structured/` | 仅题库批次使用（HC-18）；答权威性以官方为准 |
| 贺银成讲义/真题、昭昭题眼 | `知识库素材/` 索引 jy1/jy2/jy3、zt1/zt2、zhaozhao-part1/2 | 复习资料补充上下文用**本地 grep**（0 API 费用），行内标注「贺银成讲义补充」 |
| 校准难度/考频蓝图 | `scripts/blueprint.py` → `知识库素材/blueprint.json`；`question_bank/` calibrated 字段 | 组卷/押题用；**calibrated_p 是先验估计，禁止对外标注实测难度** |
| 统一押题卷模板 | `scripts/quiz_template.html`（QUESTIONS 数组注入） | 押题卷 = 仅 HTML；PDF 一律人工 |

**学科 RAG code 速查**（subject_config.json 23 入口）：内科学 internal-med / 外科学 surgery / 妇产 obgyn / 急诊 emergency / 耳鼻喉 ent / **传染病 infectious-diseases / 口腔 stomatology / 眼科 ophthalmology**（新增三科均为 chunk 800 / top_n 5 / hybrid ✓ / kw 0.3~0.4）。

---

## 7. 环境与网络避坑（中国内地 · Windows）

- **Python**：默认 `python` = 3.10；**torch 系（anchor_bank.py）必须用** `C:/Users/38063/AppData/Local/Programs/Python/Python312/python.exe`
- **RAG 成本**：付费 API（每查询 1 embed + 1 rerank）。磁盘缓存默认开（同查询 0 调用）；余额不足 402 → `--no-rerank` 降级 + 复用缓存；**先查 `中间产物/kb_search_result.json` 与缓存再检索**；尽量批量 `-f queries.txt`
- **网络**：GitHub 用 `https://mirror.ghproxy.com/https://github.com/...`（镜像序：gh-proxy.com → ghproxy.net → mirror.ghproxy.com）；pip 加 `-i https://pypi.tuna.tsinghua.edu.cn/simple`；npm 加 `--registry=https://registry.npmmirror.com`；Google/OpenAI 系被墙勿试
- **编码**：所有文件 UTF-8；控制台输出前 `sys.stdout.reconfigure(encoding='utf-8')`；中文路径加英文引号
- **JSON 纪律**：Agent 产出必须**纯 JSON 数组**（禁 YAML 前置 `---` 块），输出后 `json.load()` 自验（batch006 教训）
- **状态纪律 (HC-17)**：禁止手改 `workflow_state.json`，统一走 `scripts/workflow_state.py`；子代理不得改写
- **答权限**：真题/金标准只读；GoldenSet 仅用户手动写入；不得产出 PDF（HC-18 契约）

---

## 8. 当前批次历史（速览，便于续管）

| 批号 | 科目 | 状态 | 备注 |
|------|------|------|------|
| batch003 | 神经病学 | SUPERSEDED | 被 batch004 取代 |
| batch004/005/006/007/008/009/010/011/012/013/014/016/019/020/021/023/024/025/027 | 内科/外科/神经/精神/中医/中医心理/医患沟通 | APPROVED | 全部签收；**batch027 = 最后一次（内科学·呼吸 100 题，QC 96.5 分）** |
| batch015/017/018/022 | — | AGENT2_INVOKED / COMPLETE / AGENT5_DONE | 历史未签收批次，不再续做（继续前问用户） |

注册表：4,296 题（`scripts/qbank.py stats/check`）；测试 64 用例；GoldenSet 解析产物 9,616 条。

---

## 9. 交接 Checklist（新 Agent 第一天按此执行）

- [ ] 1. 读本文件 + `CONTEXT.md` + `SOUL.md`（工具路径/硬约束）
- [ ] 2. 跑 `python scripts/run_tests.py` 与 `python scripts/healthcheck.py`，确认基线全绿（若有红项先读 `docs/TODO.md` P0-P3）
- [ ] 3. 与用户确认 `docs/大四复习资料生成方案_v1.0.md` §9 决策清单：**A. 传染病学立即开工？B. 口腔科学教学大纲？C. 眼科 10 模块确认？D. Phase 2 深度版？E. Phase 3 题库+押题卷？**
- [ ] 4. 确认后按 §2 生产配方执行（每科 1 个独立会话/批次，先建 `中间产物/{code}_review/` 并测页偏移）
- [ ] 5. 交付收尾：`verify_produce_rules.py`（FAIL==0）→ 工作区清洁 → 站点 `index.html` 大四上区加 3 科入口（如需）→ 事件记入 `memory/JOURNAL.jsonl` → git commit（GitHub Actions 自动部署）
- [ ] 6. 全程遵守：门禁不跳过 / PDF 不脚本生成 / 页码不占位 / 真题不静默改答

---

## 10. 后续可选项（本阶段不强制）

- **Phase 2 深度版**（内科/外科二/急诊/耳鼻喉各 ≈150 页，用户时间允许时）
- **Phase 3 题库+押题卷**（大四上 3 科，按 §4 流程 + HC-18 配额，单科 3–5 天）
- 工程待办（P2）：门禁逻辑黄金用例 / exit code 语义统一 / healthcheck 精度修复 / qbank register 一致性 / Anki CSV 导出等（`docs/TODO.md`）

---

*本文档由 DSH 主会话（MedMaster）编制。数据核对：2026-09-04。若与 `docs/工作区目录结构与资源路径说明.md`、`docs/产物格式规范.md`、`docs/TODO.md` 冲突，以后三者为准（它们是被维护的权威源）。docs 活跃数上限 5（铁律⑦）：「项目介绍 v4.0」已于 2026-09-04 归档至 `archive/docs/`，本文档成为新的仓库入口文档。*
