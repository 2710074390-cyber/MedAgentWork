# MedAgentWork Skill — 医学题库生产管线

把教材/笔记变成高质量题库与复习手册的 **AI Agent 技能**：五阶段工作流（出题 → 质检 → 修复 → 成册），每个阶段转换由确定性 Python 门禁强制校验，配 Bloom 认知分层配额、金标准比对、NBME 反套路检测与回归教训库。

**核心管线零第三方依赖（纯 Python 标准库），装好即用。**

由 [MedAgentWork](https://med-review-site.pages.dev) 项目转化而来，保留了原版全部方法论资产：HC-0~HC-19 硬约束（每条背后是一次真实事故）、D1-D22 质检维度、R1-R13 机械化校验规则、五个角色的完整提示词。

## 安装

技能采用通用 Agent Skills 格式（SKILL.md + scripts/ + references/），支持 TRAE 与 Claude Code。

**TRAE**：把 `skills/medagentwork/` 整个目录复制到你的工作区技能目录：

```
<你的复习资料项目>/.trae/skills/medagentwork/
```

**Claude Code**：复制到个人技能目录（全局可用）或项目技能目录：

```
~/.claude/skills/medagentwork/          # 全局
<你的复习资料项目>/.claude/skills/medagentwork/   # 单项目
```

**其他兼容环境**：任何支持 Agent Skills（SKILL.md）规范的宿主均可，将 `skills/medagentwork/` 放入对应技能目录即可。

**安装自检**（可选）：`python smoketest/run_smoketest.py` 会在临时工作区跑通「批次登记 → 坏题阻断 → 修复 → FAIL==0 放行 → MD 导出」全链路（10 项断言），用于确认脚本在你机器上可用。

## 快速开始

1. 新建一个工作区目录（你的复习资料项目），放入教材/笔记：

   ```
   我的复习/
   └── 输入素材/
       └── 神经病学/
           ├── 第1章.md
           └── ...
   ```

2. 对你的 AI agent 说：

   > 加载 medagentwork 技能。开始新批次：神经病学+脑血管疾病，目标 50 题。

3. Agent 会回显批次计划（模块划分 / Bloom 目标 / 真题配额）→ 你确认后自动执行：出题 → 门禁校验 → 质检 → 修复 → 复习手册成册。任何门禁不通过，管线自动停止并回退修复——你拿到手的一定是通过全部校验的产物。

4. 交付物：`最终产物/{批次}/ALL_questions_FIXED.md`（题库，含 ✅ 答案标记）+ `复习资料/{科目}教学计划版/`（分层复习手册，可渲染 HTML）。

## 依赖

| 组件 | 依赖 | 说明 |
|---|---|---|
| 核心管线（validate / gate_check / workflow_state / qbank / fact_check / bloom_sampler / kaoyan_picker / render_qbank_html / render_review / contract_check） | **无**（纯标准库） | Python 3.10+ |
| 插图四件套（render_diagram / annotate_image / export_webp / compose_atlas） | Pillow, PyYAML | 可选阶段，仅配图时需要：`pip install Pillow PyYAML` |
| schema 契约校验 | jsonschema | 可选，缺失时自动跳过 |

## 目录结构

```
skills/medagentwork/
├── SKILL.md                 # 技能入口：管线总览 + 阶段调度 + 门禁速查
├── references/              # 按需加载的角色手册与规则
│   ├── runbook.md           #   批次生命周期 / 门禁命令 / 故障处置
│   ├── medmaster.md         #   编排规则
│   ├── medgen.md            #   出题阶段执行规则
│   ├── medqc.md            #   质检阶段执行规则
│   ├── medfix.md            #   修复阶段执行规则
│   ├── medreview.md         #   复习资料成册执行规则
│   ├── medillustration.md   #   插图工作流（三通道路由）
│   ├── hard-constraints.md #   HC/D/R 硬约束全集（教训库）
│   └── prompts/             #   五个角色的完整提示词（原版全量）
├── scripts/                 # 全部门禁/状态/渲染脚本（纯标准库）
│   └── validate/            #   R1-R13 校验规则引擎
├── schemas/                 # agent2/3/4 产物契约
├── assets/                  # 押题卷 HTML 模板、成品页模板
└── pipeline.yaml            # 声明式管线配置（阶段/门禁/SLO）
```

## 使用约定

- **所有脚本必须在工作区目录下运行**（脚本按当前目录定位 `中间产物/`、`workflow_state.json` 等）：`cd <工作区> && python <技能目录>/scripts/xxx.py ...`
- 工作区目录（`输入素材/`、`中间产物/`、`质检报告/`、`最终产物/`、`复习资料/`、`GoldenSet/`）由 agent 首次使用时自动创建
- 金标准（GoldenSet）只允许用户手动维护——真题/权威题库由你自行放入，机制会按 20% 配额引用并 100% 比对答案一致性（支持 `--upper/--lower` 指定你自己的金标准 JSON）

## 与原版的差异

| 原版特性 | skill 版处理 |
|---|---|
| RAG 知识库检索（向量+重排序） | 缩减：直接读素材文件；检索增强由宿主 agent 自行接入 |
| 考研真题库内容 | 机制保留，数据用户自备（版权） |
| 人体解剖图谱复用 | 机制保留，图谱素材用户自备（版权） |
| Cloudflare 站点部署 / MedKit 桌面生成器 | 不含（与管线无关） |
| DSH subagent 编排 | 通用化：单会话顺序执行（宿主支持时可用 subagent） |
| 跨工作区运维脚本 | 不含（原项目专属） |

## 设计哲学（一分钟版）

- **门禁即防线**：LLM 自检不可信，一切质量判定交给确定性脚本
- **教训入库**：每次事故沉淀为可机械执行的规则（`regression_db.json` + HC 表），同类错误永不重犯
- **结构模板优于字数约束**：选项长度靠「每题选项共享相同语法结构」，而非 min/max 字数
- **NBME 反套路**：R10 词重复 / R11 收敛 / R2 长度比等机械化检测，防 LLM 出题的隐性泄题
- **补丁溯源**：修复必须同步源文件，杜绝「聚合文件修好了、源文件还坏着」

## 许可

[MIT](LICENSE)。技能本体（文档、提示词、脚本、方法论）由原作者原创。
注意：skill 不含任何真题、教材、图谱等第三方版权数据——这些由使用者自备，且其使用需遵循相应版权方的授权条款。
