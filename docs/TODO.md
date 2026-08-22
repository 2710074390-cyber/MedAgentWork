# MedAgentWork 待办清单

> 更新：2026-08-21（HC-18 考研真题配额落地 + 公开仓库同步）| 基于：v3.0 技术报告批判分析 + Week 1 四条防线落地 + 四科 v5 测试 + 正式重构 + 五域代码审查

---

## 🟢 已完成 (2026-08-21 · HC-18 考研真题配额 + 公开仓库同步)

- [x] **HC-18 考研真题配额规则**：题库生成规则新增「每批约 1/5（目标 20%，合格带 15%–25%）为考研原题」——MedGen prompt（HC-18 完整规则 + kaoyan_origin 标注 + 解析来源句 + 批量统计行）、MedMaster prompt（HC-18 配额编排：批次启动 pick 检索真题候选 → Agent 2 指令注入配额 → 终审 check 校验占比）、MedQC prompt（新增 D21 考研原题一致性：kaoyan_origin 题 100% 比对 GoldenSet 源）、MedFix prompt（HC-4b 真题答案保护：答案冲突升级告警不静默改）；SOUL.md 共享硬约束表 + 工具速查、CONTEXT.md 真题素材源/配额流程/工具表、medgen/medmaster/medqc/medbatch 四技能同步
- [x] **真题素材确认**：GoldenSet 解析产物 9,616 条（上册 5,168 题 1994–2024 含题干/选项 + 下册 4,448 条贺银成精析含答案/解析，gs_id 配对 4,003 条完整可用）——确认「素材中有考研题内容」成立
- [x] **scripts/kaoyan_picker.py 落地**：pick（按学科/关键词检索真题候选，上册题干+下册答案配对，写中间产物 kaoyan_candidates.json）+ check（终审占比校验，<15% exit 1）；实测 内科学-心衰 关键词 429 命中/5 条输出
- [x] **契约同步**：schemas/agent2_output.schema.json 增加 kaoyan_origin（optional，additionalProperties 兼容）
- [x] **文档**：docs/MedAgentWork_项目介绍_v4.0.md（最新版项目介绍，作为仓库入口文档）；使用指南 v2.0 顶部加交叉引用；工程思路 v1.0 移入 archive/docs/（铁律⑦ ≤5 活跃文档）
- [x] **公开仓库同步**：MedAgentWork-Public main 更新 prompts（5 个当前版提示词，含 HC-18/D21/HC-4b）/ pipeline skills（6 个）/ pipeline schemas（agent2 + kaoyan_origin）/ tools（kaoyan_picker.py + 差异脚本）/ docs（项目介绍 v4.0 + 使用指南）/ README（最新数据与 HC-18 说明）

---

## 🟢 已完成 (Week 1·2026-06-26)

- [x] R9 缺单位升级 (WARN→FAIL + 15新参数)
- [x] Bloom 实时采样 (bloom_sampler.py + 四科回归全PASS)
- [x] 押题频率分析 (frequency_analyzer.py + GoldenSet 938考点)
- [x] Agent 5 v5.1 Prompt (五维深度D1-D5 + 三机械约束)
- [x] 四科 v5 测试 (精神7.8/内科8.3/中医8.5/神经9.0)
- [x] v5.1 Prompt 固化为主Prompt
- [x] SOUL.md HC-15/16 规则 + 工具速查表
- [x] FACT.md 更新 Week 1 成果

## 🟢 已完成 (正式重构·2026-08-13)

- [x] **医患沟通首次试运行**（batch019 已交付 v5.1，2026-07-04）
- [x] **DSH 迁移**：6 个角色 skill（.dsh/skills/）+ 主会话编排 + 文件直传替代剪贴板
- [x] **P0 修复**：gate_check 报告路径/回归库路径/按批次 HALT/APPROVED 跳过；save.py lost-update；validate 输出至 reports/validate/；ingest 预检 schema 兼容
- [x] **统一状态模块**：scripts/workflow_state.py（原子读写/血缘/按批次HALT/迁移/校验），ingest/save/gate_check 全部接入；workflow_state.json 迁移至 schema_version=2
- [x] **契约 schema 落地**：schemas/agent2/3/4_output.schema.json + ingest 摄入时 jsonschema 实际校验
- [x] **git 版本控制**：仓库初始化 + 基线/清理/重构三提交
- [x] **工作区整理**：16 个旧复习资料版本 + 30 份旧 validate 报告归档，输入素材残留清理
- [x] **文档同步**：USER.md 5-Agent、操作流程.txt DSH 版、CONTEXT.md 协作规则/工具表、healthcheck 补 scripts/ 扫描
- [x] **P0-1 统一题库数据层**：scripts/qbank.py（统一解析器/注册表/去重/查询/统计），1743 题迁移入库；ingest 自动注册；healthcheck 新增 H 维度
- [x] **P0-2 测试套件**：tests/ 四模块 44 用例；scripts/run_tests.py 零依赖运行器；healthcheck 新增 I 维度（自动回归）
- [x] **P1-1 事实校验机械化**：scripts/fact_check.py（页码反查 pages + GoldenSet 交叉验证 golden，HC-8 机械化）；jieba 分词 + containment 相似度；ignore-pairs 持久化

## 🟢 已完成 (2026-08-20 · 成本优化 + MD 最终交付)

- [x] **RAG 检索磁盘缓存**：search_kb.py 查询结果 + embed 双层缓存；`--no-cache`/`--cache-clear`（batch027 402 余额不足事件驱动）
- [x] **RAG 成本降级模式**：`--no-rerank` 跳过付费 rerank（成本约减半），余额不足时管线不中断
- [x] **题库最终交付 MD 格式**：qbank.py 新增 `export-md` 子命令；medbatch/medfix/medmaster skill + Prompt 同步强制「GATE-A4 后必须导出 ALL_questions_FIXED.md」；gate_check 新增 GATE-A4-MD 子门禁
- [x] **注册表归档感知**：qbank check 支持 archive/ 路径回退；新增 `rehome` 命令持久化重写失效路径
- [x] **测试扩充**：tests/test_export_md.py + test_search_cache.py，全量 46→58 用例通过

## 🟢 已完成 (2026-08-20 · 代码质量全面审查)

- [x] **batch027 签收**：内科学·呼吸系统疾病 100 题全管线完成并 APPROVED（GATE-A2/A3/A4/FINAL 全 PASS，QC 96.5 分，Bloom 偏差 0%）
- [x] **五域深度审查**：核心门禁 / 数据层 / 工具脚本 / 测试契约Web / RAG+GoldenSet 五组并行审查，主代理对 10+ 项关键结论做实测复核（全部属实）
- [x] **基线验证**：测试套件 58/58 通过；56 个活动 .py 全部 py_compile 通过；healthcheck HEALTHY (159 项 0 警告)；注册表 2074 题无跨批次重复
- [x] **审查结论**：整体约 **6.8/10（良好，未达"优秀"）** — 实现工艺（UTF-8/原子写/铁律⑤/教训注释/测试隔离）优秀，但存在门禁 fail-open、GoldenSet 数据污染、多选答案截断等关键缺陷（详见下方 P0）
- [x] **文档漂移核对**：学科覆盖率实为 7 科（医患沟通 batch019、精神病学 batch023 均已 APPROVED）；"D21-D23 维度待补充"备注作废（当前体系为 D1-D20 + 反向题专项 + D20 门禁）；测试用例数 46→58

---

## 🟢 已完成 (2026-08-20 · P0 关键缺陷修复)

- [x] **门禁 fail-open 三连修复**（gate_check.py v2.0）：
  GATE-A3 现在把 gate_decision 作硬输入（REJECT/BLOCKED/FAIL/REDO → BLOCKED）；无质检报告/D20/Bloom 证据即 BLOCKED（fail-closed）；D20 提取兼容 list 形态 dimensions、bloom_distribution 兼容嵌套形态（batch027 实测 PASS）；GATE-FINAL 不再信任自报字符串（json_valid 必须布尔 true、hc11 空串不通过、normalize 不再自动补 'OK'）；target_bloom 畸形值受控 BLOCKED 不崩溃；APPROVED 批次参考模式退出码归 0；门禁执行异常兜底 exit 2
- [x] **R9 'FEV1/FVC<0.7' 假阳性修复**（validate_options.py v2.1）：复合参数 'FEV1/FVC' 提前 + 'FVC' 负向后顾排除子串误报；补 4 个回归用例
- [x] **X 型多选答案截断修复**（qbank.py v1.2）：_norm_answer 整串匹配 [A-E]+（'ABD'→'ABD'），兼容列表形态与 'E/A' 复合答案；export-md 逐字母 ✅ 标记；补 2 个用例（test_export_md.py）
- [x] **状态覆写数据丢失窗口修复**（ingest.py/save.py v2.0）：load_state 失败即中止 exit 3，不再空状态覆写 24 批次；save.py 批次自增改数值排序 + 严格 batch\d{3} 过滤
- [x] **工具自欺修复**：r2_balancer min/max 颠倒（现如实报告失败 + 补 UTF-8 stdout）；bloom_sampler BASE 指向仓库根（--batch 模式恢复可用）；contract_check 契约违反 WARN→FAIL、main 非零退出；gate_check 回归规则明确标注"仅提示，不参与门禁判定"
- [x] **workflow_state.py CLI 修复**：删除 `or True` 死条件（无参数打印帮助）、校验失败 exit 1、migrate_legacy 实际写入 schema_version
- [x] **GoldenSet 题组解析重写**（parse_goldenset.py v2.0，审查 C1/C2 修复）：
  上册 2641 条/180 个唯一 gs_id → **5168 题 / 31 套卷（1994-2024）/ gs_id 全局唯一**；B 型题组共享选项正确绑定（116/117 同组共享实测 ✅）；`# 题号` 头形式题目不再丢失（61 题）；节标题不再拼进题干；行内选项（'A.瞳孔散大 B.汗腺分泌…'）正确拆分；小数开头题干续行（'0.5cm…'）不再误判为题号；源文件损坏保护（选项 >6 截断并告警，6 题）；出口断言强制 gs_id 唯一/字段完整/选项 ≤6
  下册（贺银成精析，源文件无题干/选项）2754→**4448 条**，gs_id 唯一，老西综双编号消歧（GS-2007-151-s4/s5）
- [x] **GoldenSet regression.py 按册分级 schema**（v1.1）：下册改为 ANALYSIS_REQUIRED_FIELDS（answer/explanation），critical 2754→**0**；上册保持 stem/options 全字段
- [x] 全量回归：测试 58→**64 用例全绿**；batch027 全门禁端到端 PASS（exit 0）；GoldenSet 两册断言 + regression 校验全过

## 🟢 已完成 (2026-08-20 · P1 代码级架构修复)

- [x] **缓存失效键修复**（search_kb.py v1.1）：`_config_sig` 改读 `subject_config_version|chunk_size|indexed_at`（此前读不存在的 `config_version` 键 → 签名恒 '?|chunk_size'，索引重建后缓存不失效）；实测签名 `1.0|600|indexed_at` 无占位符
- [x] **契约双源收敛**（schemas/ + contract_check.py v2.0）：删除漂移的 `agent_contracts.json`（git 可恢复）；contract_check 改读 `*_output.schema.json` 并用标准 jsonschema Draft7 校验（弃用自研简化校验器）；agent3 schema `dimensions` 对齐真实数组产物（[{dimension,status,score,detail}]，status 含 MINOR/MAJOR/N/A）；test_schemas.py 正例更新；实测 batch027 三类契约 agent2/3/4 全 PASS、ingest 摄入校验 0 问题（此前 120 错）
- [x] **渲染链收敛**（render_*/build_*，部分完成）：删除必然 NameError 的死脚本 build_interactive_html.py；render_interactive_html/render_predict_html 补 esc 单引号转义 + 新增 esc_js 并应用到 onclick JS 字符串/qid/tp/label/bloom/模块名；build_html_final_template 同补（esc+escJs+tp/l/c/bl 全转义）；**A3 复合题判定经实测确认为正确语义**（每个选项字母=完整病例假设链，子问共用同一字母——predict-035 解析证实 (1)(2) 均=B），删除死代码 parse_answer 并注释说明；四脚本输出冲突已在各自文件头标注（收敛为单一入口列入 P3）
- [x] **embed 三脚本部分索引降级修复**（embed_index/md/zhaozhao v1.1）：批次失败计数告警、全部失败抛错不写盘、meta/npy 原子写（tmp+os.replace）、manifest status 支持 'partial' 且 chunk_count 用实际入库数；search_kb load_index 对 partial 显式告警
- [x] **GoldenSet 校验器语义修复**（validate.py/regression.py v1.1）：validate 数值比对先按术语重叠≥2 对齐"同一知识点"再比（消除跨题巧合误报）、抽样固定 seed=42、按 gate 设置退出码（BLOCKED→1/有数值问题→2）；regression overall 判定翻转修复（MISMATCH 只把 PASS 降 PARTIAL，不覆盖 FAIL）+ FAIL 时 exit 1
- [x] **终审门禁机械化**（verify_page_numbers.py + gate_check.py）：verify_page_numbers 全分支补退出码（任一 FAIL→1）；GATE-FINAL 新增 GATE-FINAL-PAGES 子门禁——对可解析科目实跑 `verify_page_numbers.py --check-appendix`（exit 1→BLOCKED，异常/无文件→WARN 提示），实测内科学路径真实执行且 PASS
- [x] 全量回归：64 用例全绿；regression.py/validate.py 实跑 exit 0；GATE-FINAL 机械校验探针 PASS

---

## 🔴 P0 — 审查发现的关键缺陷（本周优先修复）

- [ ] ~~门禁 fail-open 三连~~ ✅ 已修复（见上方"P0 关键缺陷修复"区）
- [ ] ~~GoldenSet 数据污染~~ ✅ 已修复（parse_goldenset v2.0 重写 + 重跑两册，见上方）
- [ ] ~~R9 假阳性~~ ✅ 已修复
- [ ] ~~多选答案截断~~ ✅ 已修复
- [ ] ~~状态覆写窗口~~ ✅ 已修复
- [ ] ~~工具自欺~~ ✅ 已修复

**P0 全部完成（2026-08-20）。** 剩余待办见 P1/P2/P3。

---

## 🟠 P1 — 架构级（两周内）

- [ ] ~~缓存失效键修复~~ ✅ 已修复（2026-08-20，见上方 P1 完成区）
- [ ] ~~契约双源收敛~~ ✅ 已修复
- [ ] ~~渲染链收敛~~ ✅ 已修复（输出单一入口收敛留 P3）
- [ ] ~~embed 三脚本 partial 降级~~ ✅ 已修复
- [ ] ~~GoldenSet 校验器语义修复~~ ✅ 已修复
- [ ] ~~终审门禁机械化~~ ✅ 已修复
- [ ] 内科学全科目压力测试（目标 800+ 题，当前 batch014 仅呼吸+循环+血液）
- [ ] 干扰项"易混淆概念对"知识库 MVP（贺银成真题错误选项 + GoldenSet 干扰项统计 → Top 20 混淆对注入 Agent 2）
- [ ] 中医学独立 RAG 分块策略（方剂组成不分块；中药异名强制对照表）
- [ ] v5 Prompt 中文化适配检查（batch009/011 表格激增回归检测）

---

## 📦 第三方交接待办（2026-08-20 外部审查 Agent 交付，DSH 执行）

> 依据《交接报告_第三方已完成与DSH待办.md》+《AGENT_TASKS.md》。第三方已完成：考频蓝图（blueprint.py）、CMExam 锚点体系（anchor_bank.py：6,811 题嵌入 + difficulty_prior.json + calibrated_difficulty.jsonl 2,074 题 + anchor_check_report.json）、统一押题卷模板（quiz_template.html）、render_review.py 五处修复（--dark/badge/Hero 暗色）。红线：calibrated_p 是先验估计非实测难度；宁可标记待审，不可静默覆盖。

- [x] **#1 registry 去重**（✅ 已完成 2026-08-21，终审版 #1）：4,917 行 → 4,296 行（497 重复 qid / 621 冗余行，按「每 qid 保留原产行、删引用行」收敛）；移除 batch023_existing_ref 242 + 精神病学统一题库 189 + predict 系列 76 + batch022_supplement 14 + 其他 100；rehome 重写 1,453 条失效路径；指针 4,296/4,296 精确命中；qbank check 零跨批次重复；产物 `reports/registry_dedup_report.json` + `reports/registry_dedup_answer_conflicts.jsonl`（150 条 answer 分歧备查）；备份 `registry_backup_20260821_181137.jsonl`；registry_meta.json 已刷新
- [x] **#2 expanded 刷新回写 registry**（✅ 已完成 2026-08-21，终审版 #2）：行位置对齐刷新 calibrated_p/calibration_confidence/calibration_flag/max_sim/prior_key + 补写 anchor_source（direct 4,111 / chain 185）；543 行 snippet 失真旧值已随 expanded 修正；`apply_calibrated_difficulty.py` 升级 v1.1（默认读 expanded + qid join 安全 + anchor_source，CONTEXT.md 同步）
- [x] **#3 8 道冲突题 MedQC 复检**（✅ 已完成 2026-08-21，终审版 #3）：处置记录 `reports/conflict_recheck_20260821.json`（gate=PASS_WITH_FIXES）——6 题 KEEP_PRIOR（锚点误配，建议按先验 0.6973）、2 题 FLAG_MEDFIX（NRO-M2-A2-006 / NRO-M6-A2-004 Wallenberg 体征侧别矛盾，组卷已排除，待 MedFix 后重跑锚定）
- [x] **#4 五卷迁移 quiz_template.html**（✅ 已完成 2026-08-21，终审版 #4）：内科 90/外科 108/神经 106/精神 91/医患 60 共 455 题迁移至统一模板（原卷备份 `archive/最终产物/押题卷_迁移前备份_20260821/`）；模板补 X 型多选确认判分按钮（原模板只切换不判分）；11 项令牌全齐；Playwright 实测作答/错题重刷/系统筛选/主题记忆/375px 全通过
- [x] **#5 中医学 HTML 重生成 + 打印折叠展开**（✅ 已完成 2026-08-21，终审版 #5）：`render_review.py` 补打印强制展开折叠区 + reveal-all 按钮工厂修复（原 cloneNode 不带监听器=死按钮）；重生成 `大三下/复习资料/中医学_主复习资料.html`（新令牌、无旧令牌、badge 86、t/m 快捷键、暗色实测）
- [x] **#6 组卷公式接入 pipeline**（✅ v1.0 2026-08-20 + v1.1 2026-08-21 终审接线）：`paper_builder.py` v1.1——难度主源改读 `calibrated_difficulty.expanded.jsonl`（按 qid 覆盖 registry）；MedQC 处置接入（KEEP_PRIOR 按先验 / FLAG_MEDFIX 排除）；实测综合 60 题卷面 P=0.629 ✅（目标带 [0.55,0.65]，从 0.68 向 hard 侧配平）；样卷 `最终产物/押题卷_综合_60题.json` 已验证模板兼容
- [x] **#7 人工抽检 50 题**（✅ 清单已备 2026-08-21，抽检待用户本人执行）：`reports/人工抽检清单_50题_20260821.md`（high 10/medium 25/low 15，含 8 冲突题 ★ + 5 chain 样例 ◆，附抽检记录表）
- [x] **#8（可选）E-1b 章节级考频**（✅ 已完成 2026-08-21）：`blueprint.py` 增学科感知关键词章节分类器（零嵌入 prelim），top100 归因 61/100，blueprint.json 新增 `by_subject_chapters` + version=prelim-v1-e1b（局限已诚实标注，非语义匹配）
- [x] **#4 calibrated_difficulty 回写 registry**（✅ 已完成 2026-08-20）：新增 `scripts/apply_calibrated_difficulty.py`（备份 + 原子写 + dry-run + 行序 qid 校验）；2074/2074 行回写成功，15→20 字段只新增未覆盖；备份 `registry_backup_20260820_195003.jsonl`；qbank check 完整性通过（2026-08-21 起该脚本升级为 v1.1 expanded 刷新版，见 #2）
- [x] **#9 环境备忘**（✅ 已完成 2026-08-20）：CONTEXT.md 新增"环境备忘"节（Python312 路径/torch、bge-small-zh-v1.5 缓存与 HF 镜像、GitHub 镜像序、calibrated_p 性质红线、注册表覆盖 4917 题说明）+ 工具表新增 blueprint/anchor_bank/apply_calibrated_difficulty/paper_builder/quiz_template 五条目

---

## 🟡 P2 — 功能级（本月）

- [ ] **门禁逻辑黄金用例测试**（核心门禁审查 M13）：gate_agent2/3/4、gate_final、normalize_batch 零测试 → 把 P0 的 fail-open 探针转正为回归用例；补 R6/S1-S4/JS1/B1 组/两个解析器的测试（当前解析器完全无测试）
- [ ] **exit code 语义统一**：validate_options WARN-only 也 exit 1 而 gate_check 只看 fail（M1）；contract_check/verify_page_numbers/runbook 无退出码；全项目退出码约定写进文档
- [ ] **healthcheck 精度修复**（M9/M12）：JSON 扫描静默截断 100 个无提示；根目录白名单与实况不一致（README.md 误报、index.html 漏报、__pycache__ 目录级漏查）；F1 金标准缺失仅 WARN 不 FAIL
- [ ] **register 一致性**（数据层 M1-M5）：_norm_type 恒等函数修复（'X型题'/'A1型题' 归一）；JSONL 追加原子化；query 全量 stem 检索；--save 豁免对改合并追加；提供 delete/软删除子命令
- [ ] **workflow_state 收尾**（数据层 M6-M8，部分完成）：~~migrate_legacy 写入 schema_version~~ ✅ 已修；~~CLI 死条件 `or True` 删除、校验失败 exit 1~~ ✅ 已修（2026-08-20）；剩余：并发写锁 + 唯一 tmp 名；批次签收后自动清空 active_batch/status/current_agent 全局字段（当前 batch027 已 APPROVED 但全局状态仍显示 AGENT2_COMPLETE/Agent3_MedQC）
- [ ] 跨学科题目 Phase 1（人工指定 5 对跨学科考点，Agent 1 协调两科 RAG 合并注入 Agent 2）
- [ ] 影像描述题 MVP（RAG 索引"X线表现/CT征象/镜下观"段落）
- [ ] Anki CSV 导出格式（正面=考点设问，背面=答案+解析）
- [ ] RAG 检索精度评估（每学科 50 条标注查询，recall@5/precision@5，确立最优混合权重）
- [ ] GoldenSet 回归测试自动门禁（regression.py 输出结构化分数 + 阈值自动 PASS/FAIL）

---

## ⚪ P3 — 增强级（下月+）

- [ ] 跨模型双盲复核（Agent 3 增加 Claude/GPT 作为独立质检方）
- [ ] 知识图谱 MVP（跨学科关联自动发现）
- [ ] PDF 试卷格式输出（A4 排版 + 答题卡）
- [ ] 交互式病例模拟（"虚拟病人"问诊决策训练）
- [ ] 用户薄弱模块标注 → Agent 5 个性化深度版本
- [ ] 工具脚本族收敛：fix_* 系列 ~65 行 JS 构建器重复、render_*/build_* 输出收敛为单一入口；maintenance/runbook/fact_check 的魔法路径与阈值集中配置化

---

## 🔁 定期维护（每次任务后）

- [ ] 根目录清洁度检查（对照 CONTEXT.md 铁律①）
- [ ] `reports/` 子目录超期文件清理（validate 7天 / maintenance 30天）
- [ ] `__pycache__/` 清理
- [ ] 跨区 CONTEXT.md 工具路径同步（6个工作区）
- [ ] `知识库素材/` 索引是否需要更新
- [ ] **batch027 收尾归档**：签收已满 7 天 → maintenance 自动归档 中间产物/batch027 + 质检报告/batch027；`_scratch/build_batch027_report.py` 随批次归档或删除
- [ ] **.gitignore 补漏**：`_scratch/`、`知识库素材/cache/`、`知识库素材/retrieval_log/`（现 2 文件）、`GoldenSet/regression_reports/`（现 22 文件）
- [ ] **注册表 bloom 标签规范化**：registry.jsonl 中英文标签混用（comprehension/memory/application…）与 242 条"未标注"，建议 register 时归一

---

## 📊 健康指标看板

| 指标 | 当前值 | 目标 | 状态 |
|------|:-----:|:----:|:----:|
| 学科覆盖率 | 7/7 (100%) | 7/7 | ✅ 医患沟通/精神病学已补齐（另认知神经科学 batch018 未签收） |
| 代码审查评分 | 6.0–7.5/10（门禁7.0/数据7.5/工具7.0/Web契约6.5/RAG+GS 6.0） | ≥8.5 | 🔴 未达优秀，P0 修复后复评 |
| v5 平均评分 | 8.4/10 | ≥8.0 | ✅ |
| Bloom 最大偏差 | 8.4% (batch014) | ≤15% | ✅ |
| Callout 达标率 | 3/5 v5.1批次（batch027=77 callouts 达标） | 4/4 | 🟡 待复核 019/023 |
| GoldenSet 利用率 | 5% | ≥50% | 🔴 押题管线刚起步；⚠️ GoldenSet 解析污染（P0）修复前利用率数据不可信 |
| 管线绕过事件 | 5起(已修复) | 0 | ✅ HC-12门禁+HC-13溯源已部署 |
| 测试用例 | 58 (58/58 通过) | 持续增长 | ✅ 缺门禁逻辑/解析器/R6/S1-S4 用例 |

---

*本文件为 MedAgentWork 唯一待办清单。完成项移入上方「已完成」区域，新增项按 P0→P1→P2→P3 分级插入。*
