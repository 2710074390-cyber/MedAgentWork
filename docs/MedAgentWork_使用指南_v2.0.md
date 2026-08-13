# MedAgentWork 使用指南 v2.0（2026-08-13 正式重构版）

> 本文档是重构后系统的唯一用户手册。主流程运行于 DeepSeek Harness (DSH)，
> 5 个角色以 `.dsh/skills/` 技能形式存在，编排在主会话自动完成。
> 旧 Cherry Studio 接力流程已弃用（存档：`archive/docs/`）。

---

## 1. 系统架构（30 秒版）

```
你（用户）─► DSH 主会话（MedMaster 编排者）
                 │  后台 subagent（技能 + 文件直写，无剪贴板）
                 ├─► MedGen    → 中间产物/{batchID}/      （题库 JSON）
                 │     │ 门禁: validate_options.py（FAIL==0）
                 ├─► MedQC    → 质检报告/{batchID}/       （质检 JSON）
                 │     │ 门禁: gate_check.py agent3_done
                 ├─► MedFix   → 最终产物/{batchID}/       （修复版+追溯日志）
                 │     │ 门禁: gate_check.py agent4_done
                 ├─► MedReview → 复习资料/{科目}_主复习资料.md
                 │     │ 终审: gate_check.py final
                 └─► 你审查 → 签收 → 手动移入 GoldenSet/
```

关键文件：
| 文件 | 作用 |
|------|------|
| `.dsh/skills/medbatch/SKILL.md` | 批次运行手册（编排者的操作规范） |
| `scripts/workflow_state.py` | 状态统一读写/校验/迁移（HC-17：禁止手改状态文件） |
| `schemas/agent2/3/4_output.schema.json` | 产物契约（ingest 摄入时自动校验） |
| `workflow_state.json` | 批次状态（schema_version=2，git 版本控制） |

---

## 2. 快速上手：一个完整批次（约 30 分钟人工介入）

### 准备
1. 教材/笔记放入 `输入素材/{科目}/`（PDF/DOCX/MD 均可）
2. 打开 DSH Web（http://127.0.0.1:3080）→ 进入 MedAgentWork 工作区 → **新建会话**（每批次独立会话，避免上下文膨胀）

### 启动
```
输入：开始新批次：内科学+心力衰竭
```
编排者回显意图（科目/模块/目标题数）→ 你回复「确认」→ 之后全自动：

| 阶段 | 编排者动作 | 你的动作 |
|------|-----------|---------|
| MedGen 出题 | 后台子代理生成题库到 `中间产物/`，自动跑 validate 门禁 | 无 |
| MedQC 质检 | 子代理产出质检报告，自动跑 gate_check | 无 |
| MedFix 修复 | 子代理产出修复版+追溯日志，自动复检 | 无 |
| MedReview 复习资料 | 子代理产出主复习资料 | 无 |
| 终审 | 汇总交付 + 终审门禁 | 审查产物 |
| 签收 | 批次置 APPROVED | 输入「签收 batch026」；**手动**将合格题移入 `GoldenSet/` |

### 收尾
```
输入：python healthcheck.py   ← 或在会话中让编排者执行
```

---

## 3. 日常命令速查

### 状态与批次
```text
python scripts/workflow_state.py --check                  # 结构校验
python scripts/workflow_state.py --migrate                # 旧数据迁移（一次性/自愈）
python scripts/workflow_state.py --show batch026          # 查看批次详情
```

### 统一题库注册表（P0-1 · 2026-08-13）
```text
python scripts/qbank.py init                              # 初始化注册表
python scripts/qbank.py register --dir 中间产物 --dir 最终产物   # 注册题库（自动去重检测）
python scripts/qbank.py stats                             # 全库统计（批次/题型/Bloom）
python scripts/qbank.py query --stem 心衰 --type A1 --limit 10  # 跨批次查询
python scripts/qbank.py check                             # 跨批次重复报告 + 完整性
```
说明：ingest 摄入 agent2/agent4 题库时自动注册；重复只报告不删除；
中间产物与最终产物的新旧版本共存属预期（check 分类为"同批次多版本"）。

### 门禁（编排者自动执行；手动复核用）
```text
python validate_options.py --batch batch026               # 选项质量（报告在 reports/validate/）
python gate_check.py --batch batch026 --stage auto        # 自动检测阶段门禁
python gate_check.py --batch batch026 --stage final       # 终审全量
python gate_check.py --batch batch026 --clear-halt        # 修复后清除 HALT
```

### 手动流程（备用，非 DSH）
```text
python ingest.py <产物文件> --batch batch026 --stage agent2   # 文件直摄入（不再依赖剪贴板）
python save.py --batch batch026                               # 剪贴板模式（兼容保留）
```

### 维护
```text
python healthcheck.py                    # 9 维健康检查（46+ 脚本存活性 + 题库注册表 + 测试套件）
python healthcheck.py --full             # 含 GoldenSet 回归 + RAG 检查
python scripts/maintenance.py            # 自动归档/清理/跨区同步
python verify_page_numbers.py --all      # 知识库页码真实性
```

### 测试（P0-2 · 2026-08-13）
```text
python scripts/run_tests.py              # 零依赖回归套件（44 用例：规则/状态/注册表/schema）
python scripts/run_tests.py -v           # 详细输出
# 有 pytest 时: python -m pytest tests/ -q
```
说明：重构或改规则后必须跑一次；healthcheck [I] 维度会自动执行。

### 事实校验（P1-1 · 2026-08-13）
```text
python scripts/fact_check.py pages --file <题库.json> --subject neurology   # 页码反查
python scripts/fact_check.py golden --file <题库.json>                      # GoldenSet 交叉验证
```
说明：`pages` 对照教材分块索引核验 source_pages（P0 占位符/越界=FAIL，不在索引=WARN，
指南年份等非页码来源单独标注）；`golden` 用 jieba 分词对比金标准（下册 2754 题），
containment≥0.85 且交集≥4 判疑似重复、≥0.55 判相似，其中双方数值≥2 且不一致=冲突（需人工核对）。
已知限制：GS 下册 stem 为①②③多子题打包块 + gs_id 重复 469 组，重复判定已加防误报门槛。

### RAG 知识库
```text
python 知识库素材/embed_index.py --subject internal-med --force   # 重建单科索引
python 知识库素材/search_kb.py --subject internal-med --hybrid "心衰 NYHA 分级"
python 知识库素材/validate_configs.py                             # 配置一致性校验
```

---

## 4. 目录与产物规范（铁律速查）

| 目录 | 内容 | 谁写 |
|------|------|------|
| `输入素材/` | 教材/笔记 | 你 |
| `中间产物/{batchID}/` | 题库 JSON、备考资料 | MedGen |
| `质检报告/{batchID}/` | 质检 JSON | MedQC |
| `最终产物/{batchID}/` | 修复版+追溯日志+修改声明 | MedFix |
| `复习资料/` | 主复习资料 MD/HTML（仅保留当前版） | MedReview |
| `GoldenSet/` | 金标准（只读，**仅你手动签收写入**） | 你 |
| `reports/` | validate/healthcheck/maintenance/gate 报告（脚本自动分类） | 脚本 |
| `question_bank/` | 统一题库注册表（registry.jsonl，跨批次去重/查询） | qbank.py + ingest 自动注册 |
| `archive/` | 批次归档 + 历史版本（git 忽略，不入库） | maintenance |
| `schemas/` | 产物契约 JSON Schema | 重构维护 |
| `.dsh/skills/` | DSH 角色技能（medmaster/medgen/medqc/medfix/medreview/medbatch） | 重构维护 |

命名：`batch{NNN}`（如 batch026）；产物文件名含批次号；日期 `YYYYMMDD`。

---

## 5. 版本控制（git 工作流）

工程已纳入 git（2026-08-13 起），**每个有意义的变更一个提交**：

```text
git add -A
git commit -m "类型: 摘要 — 说明"
git log --oneline          # 查看历史
git status                 # 查看未提交变更
```

提交类型约定：`feat:`（新功能）/ `fix:`（缺陷修复）/ `refactor:`（重构）/ `chore:`（整理/杂务）/ `docs:`（文档）。
.gitignore 已排除：`reports/`、`archive/`、`知识库素材/index_store/`、PDF/DOCX、`*.lnk`。

---

## 6. 常见问题处置

| 症状 | 处置 |
|------|------|
| 门禁 BLOCKED | 看 gate 的 reason → 让编排者回退对应 Agent 修复 → 重跑门禁 |
| JSON 解析失败/YAML 前置 | 要求产出纯 JSON 数组，元数据单独 .md（batch006 教训） |
| 选项截断/缺单位 | validate R7/R8/R9 → MedFix 修复（禁止暴力截断） |
| Bloom 偏差 >15% | 回退 MedGen 按配额修正（`scripts/bloom_sampler.py`） |
| 追溯日志缺 source_file_synced | 打回 MedFix（HC-13，batch014 教训） |
| 状态文件异常 | `python scripts/workflow_state.py --check` → `--migrate` 自愈 |
| 签收后想改题 | 从 GoldenSet 打回 → 新批次处理（GoldenSet 禁止直接改） |

---

## 7. 进阶用法

### 7.1 并行模块出题（大批次提速）
流程稳定后，可要求编排者用 workflow 并行化：把 10 个模块同时分给多个 MedGen 子代理出题，再合并质检。301 题类大批次从小时级压到分钟级。

### 7.2 模型分级
子代理支持指定模型：MedQC/MedFix 可配更强模型做质检与修复，MedGen 用默认模型省成本。在编排指令中注明即可。

### 7.3 押题增强（HC-16）
新批次启动时运行 `python scripts/frequency_analyzer.py --golden GoldenSet/ --rag-index --subject {code}`，高频考点配额×1.5 注入出题指令。

### 7.4 复习资料渲染
`python 知识库素材/render_review.py "复习资料/神经病学_主复习资料_v5.md"` → 生成自包含 HTML（暗色/亮色、侧栏导航、填空点击显示）。

---

## 8. 已知遗留（待优化）

| 项 | 状态 |
|----|------|
| 押题卷 HTML 渲染链（render_predict/build_interactive/build_html_final） | batch017 一次性脚本，硬编码路径，待整合为通用渲染器 |
| 补丁溯源 Source-Completeness Gate（TODO P0） | gate_check 已查 source_file_synced，完整 diff 检测待实现 |
| 内科学全科目 800+ 题压力测试 | TODO P1，未启动 |
| 医患沟通 D21-D23 质检维度 | batch019 已交付，维度记录待补充 |

---

*本文档为 MedAgentWork 唯一使用指南。旧版 Cherry Studio 教程已归档。*
