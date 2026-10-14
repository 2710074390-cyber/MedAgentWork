# MedAgentWork Skill 改进报告

- **依据**：`medagentwork-skill-评审报告.md`（v1.0 / commit `282af28` 评审）
- **改进对象**：`C:\Users\38063\Desktop\MedAgentWork\medagentwork-skill`（skill 分享版）
- **改进版本**：v1.0 → **v2.1**
- **改进日期**：2026-09-12
- **验证方式**：本地实跑冒烟测试（23 项断言，全通过）+ `compileall` + 定向门禁场景复现

---

## 一、核对结论：评审问题与实际代码的对应关系

评审报告 §6.5 提出的 9 项 P1/P2 问题，**逐条核对后全部属实**，无一条误报。核对证据如下：

| 评审条目 | 核对结果 | 证据位置 |
|---|---|---|
| P1.1 R1 `(见上文)` 分支是死代码 | ✅ 属实，已本地复现 `branch_reachable=False` | `validate/rules_numeric.py:22`（改前） |
| P1.2 `scripts.telemetry` 模块缺失 | ✅ 属实，且**双重失效**：包内无此文件，且 `scripts` 非可导入包，`from scripts.telemetry` 路径本身不成立 | `gate_check.py:41`、`validate/engine.py:10` |
| P1.3 `medillustration_config` 缺失 + 字体写死 | ✅ 属实，4 个插图脚本引用，`annotate_image.py:31` 写死 `C:\Windows\Fonts\msyhbd.ttc`；`render_diagram.py`/`compose_atlas.py` 同样写死 | 4 脚本 + 2 脚本 |
| P1.4 R2 文案写"均"实际取 `min` | ✅ 属实 | `rules_numeric.py:67`（改前） |
| P1.5 R8 白名单是精神科专属硬编码 | ✅ 属实，24 个词全为精神科术语；`pipeline.yaml` 的 `subject_short_terms` 确实没被读取 | `rules_numeric.py:217-219` |
| P2.6 `pipeline.yaml` 约 1/3 内容指向未分发脚本 | ✅ 属实，`runbook.patterns` 引用 4 个不存在的脚本，`paper_assembly` 引用 `paper_builder.py`，`subjects` 携带整套已废弃 RAG 参数 | `pipeline.yaml` |
| P2.7 提示词正文残留原项目路径 | ✅ 属实，实测正文残留 `.dsh/skills/`×7、`知识库素材/`×12、`豆包`×13、`search_kb`×9 | `references/prompts/*.md` |
| P2.8 无 CI / 冒烟测试不验规则命中 | ✅ 属实，冒烟测试 10 项断言全为"退出码可执行"类检查 | `smoketest/run_smoketest.py` |
| P2.9 无 `requirements.txt` | ✅ 属实，可选依赖只散落在 README/SKILL.md 文字里 | 仓库根目录 |

**额外发现**（评审未提，本次一并修复）：`scripts/` 目录无 `__init__.py`，故 `scripts.telemetry` 这类包式导入在本仓库**从来不可能成功** —— 这也解释了为什么它一直静默降级而无人察觉。

---

## 二、改动清单

### A. P1 确凿实现缺陷（4 项）

| # | 文件 | 具体改动 | 改进原因（评审条目） | 预期效果 |
|---|---|---|---|---|
| A1 | `validate/rules_numeric.py` | 重写 R1 括号后缀分支：`not re.search(r'[（(]见上\|见下\|[）)]$', text)` → `not re.search(r'[（(]见[上文下][）)]', text)`，并删除恒不可达的内层 `if` | §6.5-P1.1 死代码 | 该分支恢复可达；末尾括号后缀（HC-6「凑长度」信号）能被真正检出。已由冒烟测试「R1 末尾括号后缀分支可达」永久看护 |
| A2 | `scripts/telemetry.py`（新增）<br>`gate_check.py`<br>`validate/engine.py` | 补齐零依赖 JSONL 事件日志模块（写 `reports/telemetry/telemetry.jsonl`，5MB 轮转，永不抛出）；两处导入改为同目录 `from telemetry import ...`；降级时**打印警告而非静默** | §6.5-P1.2 死依赖 | ① 不再有指向不存在模块的导入；② 真实的 `ImportError` 不再被吞掉；③ `pipeline.yaml` 的 `observability` 段从"装饰性声明"变为真实落地 |
| A3 | `scripts/medillustration_config.py`（新增）<br>`annotate_image.py`<br>`render_diagram.py`<br>`compose_atlas.py`<br>`export_webp.py`<br>`check_inline_images.py` | 补齐配置源模块：`load()` / `fonts()` / `canvas()`；**跨平台中文字体探测**（Windows/macOS/Linux 候选列表 + `MEDAGENTWORK_FONT_BOLD` 环境变量 + matplotlib 兜底）；字体不可用时抛出**可诊断错误**（提示具体设置方式）而非晦涩 `OSError`；其余脚本的静默 `except` 改为打印警告 | §6.5-P1.3 非 Windows 直接坏 | ① 非 Windows 环境中文标注不再必然失败；② 4 个插图脚本的"单一配置源"名副其实；③ 配置损坏时可诊断，不再静默用错参数 |
| A4 | `validate/rules_numeric.py` | R2 文案「均{min_other}字」→「最短{min_other}字」 | §6.5-P1.4 文案与实现不符 | 日志不再误导排障者；已由冒烟测试断言看护 |

### B. P2 工程与分发问题（4 项）

| # | 文件 | 具体改动 | 改进原因（评审条目） | 预期效果 |
|---|---|---|---|---|
| B1 | `pipeline.yaml` | ① `subjects` 段剥离全部 RAG 参数（`chunk_size`/`top_n`/`hybrid_search`/`keyword_weight`），保留真实可用的 `short_term_categories`/`option_length_ratio`/`protect_rules`；② `runbook.patterns`（引用 4 个未分发脚本）替换为只声明**真实存在能力**的故障处置表；③ `paper_assembly` 改为 `distributed: false` + 设计说明 | §6.5-P2.6 声明与实现脱节 | 配置文件不再承诺跑不起来的脚本；使用者不会被"单一事实来源"误导 |
| B2 | `references/prompts/*.md`（5 个） | 正文路径全文清洗：`.dsh/skills/` → `references/`、`知识库素材/` → `输入素材/`、`subject_config.json` → `pipeline.yaml`、`豆包(Doubao)图片 Agent` → 「外部生图 Agent（用户自备）」；文件头 NOTE 块重写为准确的清洗说明 | §6.5-P2.7 路径断层 | Agent 读到提示词正文时不会再去尝试 `.dsh/skills/` 这类不存在的路径。实测正文残留归零（仅文件头说明块保留原名以便对照） |
| B3 | `smoketest/run_smoketest.py` | 新增 §11「规则命中断言」：构造 11 道探针题，逐条断言 **R1/R2/R5/R7/R8/R10/R11/R12/R13/JS1 真的被触发**；另加 3 项专项断言（R1 死代码回归、R2 文案一致性、R8 词表配置驱动）。断言数 10 → **23** | §6.5-P2.8 测试测不出规则失效 | 规则被改坏时 CI 立刻失败。R1 那类"死代码"问题从此不可能静默复发 |
| B4 | `requirements-optional.txt`（新增）<br>`.github/workflows/ci.yml`（新增） | ① 可选依赖清单成文件（Pillow/PyYAML/jsonschema/jieba，各注明用途与降级行为）；② CI 工作流：`compileall` + `pyflakes` + 冒烟测试 + `pipeline.yaml` 阈值可解析性，矩阵 3.10/3.12 | §6.5-P2.8/P2.9、§七.11 无 CI | ① 依赖安装有据可依；② push/PR 自动拦截语法错误与未定义模块引用（`telemetry` 那类问题 CI 可直接抓到） |

### C. 中期结构性改进（5 项）

| # | 文件 | 具体改动 | 改进原因（评审条目） | 预期效果 |
|---|---|---|---|---|
| C1 | `scripts/pipeline_config.py`（新增）<br>`rules_numeric.py`<br>`rules_structural.py`<br>`gate_check.py`<br>`pipeline.yaml` | **让 `pipeline.yaml` 真正成为单一事实来源**：新增 `thresholds:` 段集中全部阈值；新增零依赖加载器（优先 PyYAML → 内置最小解析器 → 内置默认值）；R2 的 2.0/1.5、R13 的 20/18、GATE-A3 的 15% 全部改为**运行时读取** | §6.4「风险」、§七.7 配置双轨制 | 改 `pipeline.yaml` 即全局生效，不再需要改 Python 代码。且因保留了内置默认值，**未安装 PyYAML 的零依赖环境行为完全不变** |
| C2 | `rules_numeric.py`<br>`pipeline.yaml` | R8 豁免词表接入配置：`thresholds.r8_legit_terms_default` + 按科目叠加（`tcm`/`surgery`/`psychiatry`）；科目来源支持题目 `subject` 字段或 `MEDAGENTWORK_SUBJECT` 环境变量 | §6.5-P1.5、§七.9 精神科词表硬编码 | 中医/外科等科目可各自配置豁免词，不再产生系统性误报/漏报。**默认值与原精神科词表一致，故默认行为零回归** |
| C3 | `gate_check.py` | **Bloom 独立重算交叉验证**（新增子门禁 `GATE-A3-BLOOM-RECOMPUTE`）：门禁用题库 JSON 的 `bloom_level` 字段（缺失时按题型映射兜底）**机械重算** Bloom 分布，与质检报告自述值比对，偏差 > `bloom_recompute_tolerance`（默认 5%）即 **BLOCKED**；题库缺失时记录 SKIPPED（不阻断，已有 NO-BLOOM 兜底） | §7.14（评审称"本项目最值得做的一处加固"） | Bloom 门禁从"读 LLM 自述"升级为"确定性重算 + 自述交叉验证"。**实测有效**：构造「题库真实 100% 记忆层、质检报告自述 30/40/25/5」的场景，门禁正确 BLOCKED 并报出「最大偏差 70.0% > 5%」 |
| C4 | `SKILL.md`<br>`README.md` | 新增 **§7.1「门禁保证什么、不保证什么」边界声明**：表格化区分「确定性门禁」与「MedQC + 人工签收」两层质量，明确「门禁是防呆不是防错」，并逐条说明 D20 仍属 LLM 自述、只有 Bloom 做了重算、答案正确性最终责任在人工签收 | §6.5-P0、§七.12 | 读者不会再把"过了门禁"误读为"题目正确"，避免最危险的预期偏差 |
| C5 | `kaoyan_picker.py`<br>`assets/golden_set_template.json`（新增）<br>`SKILL.md` §6.1<br>`runbook.md`<br>`hard-constraints.md` | ① `check` 新增 `--golden-absent`：显式声明无金标准 → 报告留痕 `degraded: true` + `golden_status: "absent(降级)"` + 醒目警告；**不加参数仍 fail-closed**；② 提供最小可用金标准模板（10–20 题，字段与 `--upper/--lower` 输入一致）；③ 三处文档同步降级路径 | §7.13 GoldenSet 冷启动门槛 | 无自备真题的用户有了**明确且有留痕**的降级出口，不再卡死在第一条门禁上；同时降级不会静默发生，也不会被误认为"门禁通过" |

### D. 补充说明类改动

| 文件 | 改动 | 原因 |
|---|---|---|
| `SKILL.md` 顶部 | 新增「两个前置条件」提示块：数据需自备 / 生图需自备，无生图能力请跳过插图阶段 | §七.16（原说明埋在 Agent5 提示词中段） |
| `SKILL.md` §3、§5、§7 | 插图阶段可选性前置说明；`--golden-absent` 命令示例；GATE-A3 双 Bloom 子门禁说明；「配置即事实来源」「Bloom 独立重算」「规则命中有测试」三条设计原则 | 与上述改动保持一致 |
| `SKILL.md` §8、`README.md` | 差异表补充「组卷器不含」「pipeline.yaml 已清理」两行 | 如实反映 v2.1 状态 |

---

## 三、未做的改动及原因

评审 §七.8 建议拆分巨型文件（`render_review.py` 1520 行、`gate_check.py` 1134 行）。**本次未做**，理由：

- 两项拆分都是**纯机械重构**，不改变行为，属于"锦上添花"而非缺陷修复；
- 当前冒烟测试虽已覆盖规则命中，但对 `render_review.py` 的 HTML 渲染输出**尚无回归基线**，此时拆分风险大于收益；
- 建议路径：先为 `render_review.py` 补一个渲染快照测试作为安全网，再按「解析 / 布局 / 组件 / 导出」拆分。已在本报告中留档，建议列入下一轮。

其余评审建议（§七.1–7、9–16）**已全部落地**。

---

## 四、验证结果

| 验证项 | 命令 | 结果 |
|---|---|---|
| 冒烟测试（含规则命中断言） | `python smoketest/run_smoketest.py` | **23 passed, 0 failed**（改前 10 passed） |
| 语法编译 | `python -m compileall -q skills/medagentwork/scripts smoketest` | 通过 |
| 阈值配置加载（无 PyYAML） | 屏蔽 `yaml` 后 `pipeline_config.load_thresholds()` | 正确读出 `r2_ratio_fail=2.0 / option_length_max=20 / option_avg_max=18 / bloom_deviation_max=15` |
| `pipeline.yaml` 语法 | PyYAML 解析 | 通过（顶层 8 个段，`thresholds` 10 个键） |
| R8 科目词表 | `get_r8_legit_terms('中医')` | 正确叠加 16 个中医术语 |
| **Bloom 独立重算门禁** | 构造「题库真实 100% 记忆层 vs 自述 30/40/25/5」 | **正确 BLOCKED**，报出「最大偏差 70.0% > 5%」 |
| 金标准降级模式 | `kaoyan_picker.py check` 加/不加 `--golden-absent` | 不加 → exit 1 FAIL；加 → exit 0 DEGRADED 并打印警告 |
| 提示词正文路径残留 | `grep` 正文（跳过文件头） | 归零 |

**变更规模**：新增 6 个文件，修改 17 个文件，+613 / −221 行。

---

## 五、预期评分影响

| 维度 | 评审原分 | 预期 | 依据 |
|---|---|---|---|
| 实现质量 | ★★★★☆ | **★★★★★** | 唯一确凿缺陷（R1 死代码）已修；死依赖补齐；非 Windows 坏路径修复；规则命中纳入测试 |
| 可维护性 | ★★★☆☆ | **★★★★☆** | 配置双轨制消除（真·单一事实来源）；有 CI + 可选依赖清单；巨型文件拆分仍待做故未给满分 |
| 实用性 | ★★★☆☆ | **★★★★☆** | 金标准冷启动有降级出口 + 模板；生图依赖前置声明；边界声明消除预期偏差 |
| 设计思路 | ★★★★★ | ★★★★★ | 保持；新增的 Bloom 独立重算是设计层面的实质增强 |
| **综合** | ★★★☆☆+ | **★★★★☆** | 评审结语「清理尾部残留后可到四星」的目标达成 |
