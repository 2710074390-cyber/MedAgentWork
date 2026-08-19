# MedAgentWork 待办清单

> 更新：2026-08-13 | 基于：v3.0 技术报告批判分析 + Week 1 四条防线落地 + 四科 v5 测试 + 正式重构

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

- [x] **医患沟通首次试运行**（batch019 已交付 v5.1，2026-07-04；D21-D23 维度待补充记录）
- [x] **DSH 迁移**：6 个角色 skill（.dsh/skills/）+ 主会话编排 + 文件直传替代剪贴板
- [x] **P0 修复**：gate_check 报告路径/回归库路径/按批次 HALT/APPROVED 跳过；save.py lost-update；validate 输出至 reports/validate/；ingest 预检 schema 兼容
- [x] **统一状态模块**：scripts/workflow_state.py（原子读写/血缘/按批次HALT/迁移/校验），ingest/save/gate_check 全部接入；workflow_state.json 迁移至 schema_version=2
- [x] **契约 schema 落地**：schemas/agent2/3/4_output.schema.json + ingest 摄入时 jsonschema 实际校验（修 pipeline.yaml 死引用）
- [x] **git 版本控制**：仓库初始化 + 基线/清理/重构三提交（.gitignore 已排除 reports/archive/索引/大文件）
- [x] **工作区整理**：16 个旧复习资料版本 + 30 份旧 validate 报告归档，输入素材残留清理
- [x] **文档同步**：USER.md 5-Agent、操作流程.txt DSH 版、CONTEXT.md 协作规则/工具表、healthcheck 补 scripts/ 扫描
- [x] **P0-1 统一题库数据层**：scripts/qbank.py（统一解析器/注册表/去重/查询/统计），1743 题迁移入库；
      ingest 自动注册；healthcheck 新增 H 维度；实测发现 1 组跨批次重复待裁决
- [x] **P0-2 测试套件**：tests/ 四模块 44 用例（validate R1-R13 黄金用例 / workflow_state / qbank / 契约 schema），
      scripts/run_tests.py 零依赖运行器；healthcheck 新增 I 维度（自动回归）；
      修 agent4 schema final_gate 类型 bug（实际数据为字符串）
- [x] **P1-1 事实校验机械化**：scripts/fact_check.py（页码反查 pages + GoldenSet 交叉验证 golden，HC-8 机械化）；
      jieba 分词 + containment 相似度（实测校准：真题重复 0.61-0.83）；
      实测 batch022 神经病学 322 题：页码 0 FAIL/38 WARN（P55 集中引用 28 题疑似占位模式）、
      金标准 1 组疑似重复（脊髓型颈椎病，待人工确认）；
      qbank 页码规范化修复（P310-P312 区间、指南年份不再误提取）；
      ignore-pairs 持久化到 registry_meta.json（--save，healthcheck 自动读取）

## 🟢 已完成 (2026-08-20 · 成本优化 + MD 最终交付)

- [x] **RAG 检索磁盘缓存**：search_kb.py 查询结果 + embed 双层缓存（key 含参数与索引配置签名，索引重建自动失效）；相同查询跨 Agent/批次命中缓存 → 0 API 调用；`--no-cache` 关闭、`--cache-clear` 清理（batch027 402 余额不足事件驱动）
- [x] **RAG 成本降级模式**：`--no-rerank` 跳过付费 rerank，用 Stage1 余弦分数（成本约减半），余额不足时管线不中断
- [x] **题库最终交付 MD 格式**：qbank.py 新增 `export-md` 子命令（统一解析器兼容 6 种字段变体，按模块分组，✅ 答案标记/解析/页码/Bloom）；medbatch/medfix/medmaster skill + Prompt 同步强制「GATE-A4 后必须导出 ALL_questions_FIXED.md」
- [x] **注册表归档感知**：qbank check 支持 archive/ 路径回退（学期切换归档后 14 条注册失效问题修复）；新增 `rehome` 命令持久化重写失效路径
- [x] **测试扩充**：tests/test_export_md.py 5 用例（export-md 格式/判断题原文答案/归档感知/rehome 读写），全量 46→51 用例通过

---

## 🟠 P1 — 架构级（两周内）

- [ ] **内科学全科目压力测试**
  - 目标 800+ 题全科目生成（当前 batch014 仅呼吸+循环+血液）
  - 记录 Bloom 分布/选项质量/D1-D5 覆盖率在大规模下的变化

- [ ] **干扰项"易混淆概念对"知识库 MVP**
  - 从贺银成真题错误选项 + GoldenSet 干扰项统计中提取 Top 20 混淆对
  - 注入 Agent 2 出题指令作为干扰项强制来源
  - 混淆对示例：NYHA↔Killip、克罗恩↔UC、中枢性↔周围性面瘫

- [ ] **中医学独立 RAG 分块策略**
  - 方剂组成部分不分块（当前 500 字符分块会切断方剂组成）
  - 建立中药异名强制对照表（同一药物 3+ 别名 → 注入 HC-9 附录）

- [ ] **v5 Prompt 中文化适配检查**
  - 当前 v5 中文指令可能触发 LLM "矫枉过正"（如表格保护规则被过度执行→表格激增）
  - 对 batch009/011 做表格激增回归检测

---

## 🟡 P2 — 功能级（本月）

- [ ] **跨学科题目 Phase 1**
  - 人工指定 5 对跨学科考点（如 DM+肾病、肝性脑病）
  - Agent 1 协调两个学科的 RAG 检索结果合并注入 Agent 2

- [ ] **影像描述题 MVP**
  - RAG 检索中专门索引教材中的影像学描述段落（"X线表现""CT征象""镜下观"）
  - 生成不含图片的文字影像判读题

- [ ] **Anki CSV 导出格式**
  - Agent 5 新增输出格式：正面=考点设问，背面=答案+解析
  - 可直接导入 Anki 间隔重复系统

- [ ] **RAG 检索精度评估**
  - 为每个学科构建 50 条标注查询
  - 计算 recall@5 / precision@5
  - 确立最优混合检索权重（当前权重凭直觉设定）

- [ ] **GoldenSet 回归测试自动门禁**
  - regression.py 输出结构化分数（术语一致率/答案一致率）
  - 设定阈值自动 PASS/FAIL

---

## ⚪ P3 — 增强级（下月+）

- [ ] 跨模型双盲复核（Agent 3 增加 Claude/GPT 作为独立质检方）
- [ ] 知识图谱 MVP（跨学科关联自动发现）
- [ ] PDF 试卷格式输出（A4 排版 + 答题卡）
- [ ] 交互式病例模拟（"虚拟病人"问诊决策训练）
- [ ] 用户薄弱模块标注 → Agent 5 个性化深度版本

---

## 🔁 定期维护（每次任务后）

- [ ] 根目录清洁度检查（对照 CONTEXT.md 铁律①）
- [ ] `reports/` 子目录超期文件清理（validate 7天 / maintenance 30天）
- [ ] `__pycache__/` 清理
- [ ] 跨区 CONTEXT.md 工具路径同步（6个工作区）
- [ ] `知识库素材/` 索引是否需要更新

---

## 📊 健康指标看板

| 指标 | 当前值 | 目标 | 状态 |
|------|:-----:|:----:|:----:|
| 学科覆盖率 | 5/7 (71%) | 7/7 | 🟡 缺医患沟通+精神病学待验证 |
| v5 平均评分 | 8.4/10 | ≥8.0 | ✅ |
| Bloom 最大偏差 | 8.4% (batch014) | ≤15% | ✅ |
| Callout 达标率 | 2/4 (50%) | 4/4 | 🟡 batch007/014未用v5.1 |
| GoldenSet 利用率 | 5% | ≥50% | 🔴 押题管线刚起步 |
| 管线绕过事件 | 5起(已修复) | 0 | ✅ HC-12门禁+HC-13溯源已部署 |

---

*本文件为 MedAgentWork 唯一待办清单。完成项移入上方「已完成」区域，新增项按 P0→P1→P2→P3 分级插入。*
