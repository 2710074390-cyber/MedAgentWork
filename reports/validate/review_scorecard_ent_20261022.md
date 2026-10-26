# 复习资料学习价值评分卡 · 耳鼻咽喉头颈外科学（教师重点版）

> 生成：2026-10-26T22:31:08 ｜ 科目：ENT ｜ 批次：batch040
> 总分：**3.63/5** ｜ 目标：4.6/5 ｜ Gate：**ADVISORY_PASS**（advisory）

## 1. 12 维评分

| # | 维度 | 权重 | 分数 | 加权 | 证据 |
|---|---|---:|---:|---:|---|
| 1 | 内容专业性与深度 | 12% | 4.0 | 0.48 | 教师版 0 个展开区；教学版 40 个展开区；内科学合订本 93 个展开区<br>7 模块均具备 D2 因果链/D3 谱系/D4 决策树/D5 概念地图结构<br>cards=85 张（info）<br>content_chars=79,988 字符（info） |
| 2 | 知识点准确性与一致性 | 14% | 3.8 | 0.53 | 125/125 条教师重点覆盖，44 类硬事实缺失 0<br>200 题 v2 初检：原文精确 96.5%，锚点已核 74%<br>source_quote_exact_rate=100.0%（ok）<br>anchor_verified_rate=77.0%（warn） |
| 3 | 考点匹配度与覆盖面 | 14% | 4.3 | 0.60 | 125/125 条教师重点覆盖；蓝图权重 M01–M07 完整<br>卡片/字数/题量三口径偏差：M05 +26.1%、M07 字数 +509.1%、M07 题量 +400%<br>keypoint_coverage_rate=125/125（ok）<br>blueprint_max_rel_dev=518.1%（fail） |
| 4 | 知识体系逻辑性 | 10% | 4.2 | 0.42 | 7 模块疾病谱系、因果链、决策树、概念地图齐全<br>21 个 fenced ASCII 图承载谱系/决策/对比结构<br>callout_density=3.14/模块（warn）<br>expand_density=0.00/模块（fail） |
| 5 | 记忆强化设计 | 12% | 3.4 | 0.41 | 82 道主动回忆 + 90 行附录答案 + 7 张一页纸 + 5 个记忆主轴 + 10 个陷阱<br>尚无间隔重复调度与错题回链<br>recall_answer_coverage=75/82 匹配（缺口 7，多余 15）（fail）<br>schedule_coverage=已实现（ok） |
| 6 | 学习效率与认知负荷 | 8% | 3.0 | 0.24 | 87,358 字符、820 行表格、3 条阅读路径<br>无掌握度诊断，无法按薄弱点跳过已会内容<br>content_chars=79,988 字符（info）<br>table_density=117.1 行/模块（info） |
| 7 | 临床关联与推理迁移 | 10% | 3.2 | 0.32 | 题库 40 道案例题；教师版有决策树与鉴别表<br>无 illness script 卡、无对比病例组；病例提及仅 7 处<br>case_question_count=40 题（info）<br>illness_script_count=0 个（warn） |
| 8 | 可溯源性与时效性 | 8% | 4.0 | 0.32 | 125 个 📌 落点行；85 卡中 80 卡有重点条号；教材页码可反查<br>指南版本/证据等级/复查日期尚未结构化<br>source_anchor_rate=80/85（warn）<br>source_quote_exact_rate=100.0%（ok） |
| 9 | 格式易用性与可访问性 | 5% | 3.8 | 0.19 | 教师版有 MD + 站点 PDF；教学版有 HTML<br>教师版无独立 HTML、无搜索/进度；PDF 5.5 MB<br>html_available=无（warn）<br>image_count=0 张（warn） |
| 10 | 交互性与反馈 | 3% | 2.0 | 0.06 | 82 道自测答案在附录五，需要翻页对答案<br>无答案展开、无即时反馈、无错题本<br>feedback_coverage=已实现（ok） |
| 11 | 个性化适配 | 2% | 1.5 | 0.03 | 无诊断性自测、无掌握度画像、无个性化路径<br>diagnostic_available=未实现（unknown） |
| 12 | 学习效果证据 | 2% | 1.5 | 0.03 | 无 pre/post、无延迟测验、无真实考试分数<br>learner_outcome_available=未实现（unknown） |

## 2. 自动指标

| 指标 | 值 | 状态 | 阈值 | 来源 |
|---|---|---|---|---|
| blueprint_max_rel_dev | 518.1% | fail | ≤20% | review MD + kc_question_map |
| expand_density | 0.00/模块 | fail | ≥2/模块 | review MD |
| recall_answer_coverage | 75/82 匹配（缺口 7，多余 15） | fail | ≥95% | review MD + appendix5 |
| anchor_verified_rate | 77.0% | warn | ≥90% | learning_value_v2 report |
| callout_density | 3.14/模块 | warn | ≥4/模块 | review MD |
| content_only_ratio | 19/85 | warn | ≤15% | kc_registry |
| html_available | 无 | warn | 教师版 HTML | teacher dir |
| illness_script_count | 0 个 | warn | ≥10 个（P2） | review MD |
| image_count | 0 张 | warn | — | review MD |
| r18_low_overlap_count | 24 题 | warn | =0 | learning_value_v2 report |
| source_anchor_rate | 80/85 | warn | ≥95% | review MD |
| diagnostic_available | 未实现 | unknown | D2 | pilot artifacts |
| learner_outcome_available | 未实现 | unknown | A8 | pilot reports |
| feedback_coverage | 已实现 | ok | D8 | pilot artifacts |
| kc_mapping_rate | 200/200 | ok | =100% | kc_question_map |
| keypoint_coverage_rate | 125/125 | ok | =100% | KC registry |
| needs_review_ratio | 15/200 | ok | ≤10% | kc_question_map |
| provisional_ratio | 10/200 | ok | ≤10% | kc_question_map |
| schedule_coverage | 已实现 | ok | D3 | pilot artifacts |
| source_quote_exact_rate | 100.0% | ok | ≥95% | learning_value_v2 report |
| ascii_blocks | 21 个 | info | — | review MD |
| cards | 85 张 | info | — | review MD |
| case_question_count | 40 题 | info | — | question bank |
| content_chars | 79,988 字符 | info | — | review MD |
| kc_alias_count | 12 条 | info | — | kc_aliases |
| modules | 7 模块 | info | — | review MD |
| table_density | 117.1 行/模块 | info | — | review MD |

## 3. 改进建议（Top 5）

1. **content_only 19/85**：为 19 张无题卡补题，或在下一批明确标为 content-only；目标 ≤12 张。
2. **anchor_verified 74%**：优先处理 26 题 R18 低主题覆盖与 R16 警告；目标 ≥90%。
3. **expand_density 0 / image_count 0**：教师版补 D1–D5 展开区与 10–20 张可信图；先做图谱/确定性图。
4. **blueprint_max_rel_dev 518.1%**：M07 字数与题量超配、M02/M04 内容欠配；先出配平报告，不删低权重条目。
5. **schedule/feedback 未实现**：D3 间隔重复与 D8 交互式 HTML 尚未落地；这是记忆保持与反馈闭环的关键。

## 4. 限制

- 12 维分数为专家 rubric，不是学习者结果测量；目标 4.6 为设计目标，不是承诺。
- 自动指标是证据，不单独决定总分；总分由人工 rubric 的 12 维加权。
- 本评分卡不替代医学内容专家复核。

## 5. 评审角色

- 学习科学顾问（角色化评审）；医学内容专家（角色化评审）

## 6. 门禁

- `gate_check.py --learning-value-mode advisory` 读取本文件；advisory 只 WARN，不阻断。
- 当前 warnings：13 条；blocking_issues：0 条。
