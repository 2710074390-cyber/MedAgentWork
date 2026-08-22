# MedAgentWork — Domain Context

> 共享规则表。5 个 Agent（MedMaster / MedGen 出题 / MedQC 质检 / MedFix 修复 / MedReview 主复习资料）共用此文件。

## 网络环境约束

> ⚠️ **用户 IP 位于中国大陆。以下站点在未确认代理可用的情况下不可直连，不要浪费时间尝试。**

### 不可访问（GFW 阻断）
| 类别 | 域名 | 影响 |
|------|------|------|
| Google 全系 | `google.com`, `googleapis.com`, `gstatic.com`, `fonts.googleapis.com` | CDN/字体/验证码均不可用 |
| 社交媒体 | YouTube, Twitter/X, Facebook, Instagram, Reddit, Discord | 完全阻断 |
| AI 服务 | `api.openai.com`, `chatgpt.com`, `claude.ai`, `docs.anthropic.com` | API 不可直连 |
| 代码托管 | GitHub 直连不稳定（clone/fetch 易超时），Hugging Face 不稳定 | 用镜像或确认代理 |
| 其他 | Docker Hub, Cloudflare 保护站点（触发 CAPTCHA） | — |

### 中国境内可直连（优先使用）
**搜索/文档**：百度、Bing 中国 (`cn.bing.com`)、CSDN、知乎、博客园、掘金
**代码托管**：Gitee、Coding.net、GitHub 镜像 (`ghproxy.com`)
**云服务**：阿里云、腾讯云、华为云

### 操作规则
1. **优先用可直连资源** — 未确认代理前，不尝试访问被墙站点
2. **GitHub 镜像前缀**：`https://mirror.ghproxy.com/https://github.com/...`
3. **npm 替代**：`--registry=https://registry.npmmirror.com`
4. **pip 镜像**：`-i https://pypi.tuna.tsinghua.edu.cn/simple`
5. **确认代理后再试** — 如任务必须访问被墙资源，先向用户确认代理可用性

## 中国工程师约束 (CN Engineer Constraints)

> 在中国大陆网络 + Windows 平台下高效工作的硬规则。违反一条 = 反复踩坑。

### 网络决策树
| 场景 | ❌ 错误做法 | ✅ 正确做法 |
|------|-----------|-----------|
| pip install 超时 | 反复重试 | `-i https://pypi.tuna.tsinghua.edu.cn/simple` |
| npm install 超时 | 反复重试 | `--registry=https://registry.npmmirror.com` |
| GitHub clone 失败 | 手动重试5次 | `https://mirror.ghproxy.com/https://github.com/...` |
| GitHub release 下载失败 | 找偷渡链接 | 找 Python pip 替代品 |
| HuggingFace 下载失败 | 死等 | 用 ModelScope 镜像 |
| 不确定网站能否访问 | 试试再说 | 默认被墙，走镜像或告知用户 |

### Windows 避坑指南
| 陷阱 | 表现 | 解法 |
|------|------|------|
| 中文路径 | 命令提示找不到文件 | 路径加英文双引号 `"C:/path/中文/"` |
| GBK 编码 | Python print/文件读写报错 | `encoding='utf-8'` + `sys.stdout.reconfigure(encoding='utf-8')` |
| 反斜杠转义 | Python 字符串 `\n` 变换行 | 正斜杠 `C:/Users/...` 或 raw string `r'...'` |
| CRLF 行尾 | .sh 脚本报 `$'\r'` | Git 设置 `core.autocrlf=true`；复杂操作写 Python 脚本 |

### 工具选型层级
```
优先: pip/npm 可安装（走国内镜像）
可用: Python 标准库（零外部依赖）
不可用: GitHub release 二进制（被墙阻断）
  → jq → python -c "import json; json.load(open('f.json'))"
  → ffmpeg → 标记不可用
  → ImageMagick → Pillow
  → Inkscape → Pillow + lxml
```

### 输出质量规范
1. **语言**：面向用户全简体中文（代码/路径/命令保持英文）
2. **可执行**：安装命令自带镜像参数，直接复制粘贴可用
3. **归因**：报错区分「GFW阻断」/「工具不存在」/「代码错误」
4. **效率**：独立操作并行发送，大任务先验证小步骤再继续

### 一句口诀
```
网络超时=切镜像|编码报错=utf-8|路径中文=双引号|二进制=Python替代|大任务=分步验证
```

## 跨 Agent 工具同步规则

> 安装/下载任何新工具后，必须同步更新全部 6 个工作区的 CONTEXT.md 工具路径表。

### 同步目标（6 个文件）
| # | 文件 | Agent 工作区 |
|---|------|-------------|
| 1 | `C:\Users\38063\Desktop\Web-AI\CONTEXT.md` | CherryClaw（编排者） |
| 2 | `C:\Users\38063\Desktop\web-med\CONTEXT.md` | web-med（医学检索） |
| 3 | `C:\Users\38063\Desktop\agent-ppt\CONTEXT.md` | Agent-PPT（PPTX 生成） |
| 4 | `C:\Users\38063\Desktop\黑曜石\CONTEXT.md` | 黑曜石（知识管理） |
| 5 | `C:\Users\38063\Desktop\MedAgentWork\CONTEXT.md` | MedAgentWork（本题库）← 自己 |
| 6 | `C:\Users\38063\Desktop\测试\CONTEXT.md` | Data Lab（数据分析） |

### 同步格式
四列表格（工具 / 版本 / 路径 / 调用方式），与现有表格一致。

### 原则
- 不在自己 CONTEXT.md 里的工具 = 当作「未安装」
- 每个 Agent 的 CONTEXT.md 是其他 Agent 判断是否需要下载的唯一依据

## 文件管理原则（v2 · 2026-06-24 重构）

> 技术社区最佳实践融合：Johnny Decimal（区域编号）、PARA Method（项目/领域/资源/归档）、Clean Architecture（概念分组 > 类型分组）。

### 7 条铁律（所有 Agent 强制执行）

#### 铁律 ① 根目录白名单

根目录仅允许：
```
✅ SOUL.md  USER.md  CONTEXT.md  workflow_state.json  操作流程.txt  .gitignore
✅ gate_check.py  healthcheck.py  validate_options.py  save.py  ingest.py  verify_page_numbers.py
✅ .git/  .dsh/（DSH 技能与版本控制，2026-08-13 起）
```

绝对禁止出现在根目录：
```
❌ 任何 *_report_*.json（validate/healthcheck/maintenance/gate 产物）
❌ __pycache__/  *.pyc
❌ 临时文件、备份文件、下载文件、输出报告(.md)
```

#### 铁律 ② 报告自动分类

所有脚本产出报告写入 `reports/` 子目录：
```
reports/
  ├── validate/       ← validate_options.py 输出
  ├── healthcheck/    ← healthcheck.py 输出
  ├── maintenance/    ← maintenance.py 输出
  └── gate/           ← gate_check.py 输出

保留策略：
  healthcheck:  保留 7 天 → 超期移入 archive/reports/
  maintenance:  保留 30 天 → 超期移入 archive/reports/
  validate:     保留至对应批次归档 → 同步归档
```

#### 铁律 ③ 统一归档

`archive/` 位于根级别，按来源+批次组织，**不使用分散的子目录 archive/**：
```
archive/
  ├── 中间产物/batchXXX/     ← 从 中间产物/ 归档
  ├── 最终产物/batchXXX/     ← 从 最终产物/ 归档
  ├── 质检报告/batchXXX/     ← 从 质检报告/ 归档
  └── reports/YYYY-MM/       ← 超期报告归档

触发条件（maintenance.py 自动化）：
  - 批次 APPROVED → 其中间产物/ 和 质检报告/ 可归档
  - 批次 SUPERSEDED → 同上
  - 报告超期 → 自动移入 archive/reports/
```

#### 铁律 ④ 无副本原则

同一文件在工作区全目录树中只存在一份。
检测到同名文件在不同目录 → 保留最上游位置的版本，删除副本。
```
例: validate report 同时在 root/ 和 reports/ → 保留 reports/，删 root/
例: batch产物 同时在 中间产物/ 和 最终产物/ → 保留 最终产物/，归档 中间产物/
```

#### 铁律 ⑤ 脚本输出路径锁定

| 脚本 | 产出 | 固定输出路径 |
|------|------|------|
| validate_options.py | 校验报告 | `reports/validate/` |
| healthcheck.py | 健康报告 | `reports/healthcheck/` |
| maintenance.py | 维护报告 | `reports/maintenance/` |
| gate_check.py | 门禁报告 | `reports/gate/` |
| save.py | 题库 MD/JSON | `中间产物/{batchID}/` 或 `最终产物/{batchID}/` |
| qbank.py export-md | 最终交付题库 MD | 默认 `最终产物/{batchID}/ALL_questions_FIXED.md`（2026-08-20 起 GATE-A4 强制） |
| inject_obsidian_theme.py | Obsidian 树主题注入/移除（`--remove` 反注入）| 就地修改 `最终产物/*押题卷*.html` 与 `index.html`（⚠️ 2026-08-12 已从线上站移除 Obsidian 主题，站点恢复三主题；脚本保留备用） |
| verify_obsidian_theme.py | 主题浏览器实测截图 | `reports/theme_shots/` |

脚本不可将报告写入根目录。maintenance.py 每次运行检测并修正。

#### 铁律 ⑥ Python 缓存隔离

`__pycache__/` `*.pyc` 加入 `.gitignore`。maintenance.py 每次运行时自动清理所有 `__pycache__/`。

#### 铁律 ⑦ 文档版本管理

`docs/` 保留 ≤ 5 个活跃文档。过时文档移至 `archive/docs/`。技术报告合并为单一索引文档，不分散存放。

### 命名规范速查
| 规则 | 示例 | 反例 |
|------|------|------|
| 目录名：语义化中文 | `输入素材/`, `最终产物/` | `input/`, `output_v2/` |
| 文件名：科目_章节_版本 | `内科学_心衰_v2.md` | `新建文档.txt` |
| 日期：YYYYMMDD | `20260615` | `6-15` |
| JSON 报告：含批次号 | `质检报告_batch001.json` | `report.json` |
| GoldenSet：含来源标注 | `真题上册_2024.md` | `题目.md` |

### 5-Agent 工作流产物规范
```
输入素材/                    ← 用户放入原始教材
  └── 内科学_心衰_章节原文.txt

中间产物/                    ← Agent 2 产出（备考资料+题库JSON）
  └── batch001_内科学_心衰_questions.json

复习资料/                    ← 从Agent 2产物提取的备考资料MD
  └── 内科学_心律失常_备考复习资料.md

质检报告/                    ← Agent 3 产出
  └── batch001_质检报告.json

最终产物/                    ← Agent 4 产出
  └── batch001_内科学_心衰_最终版.json
  └── batch001_内科学_心衰_最终版.md   ← 最终交付 MD（export-md 生成，2026-08-20 起强制）
  └── batch001_追溯日志.md

GoldenSet/                   ← 用户签收后加入
  └── 真题上册.md

question_bank/               ← 统一题库注册表（P0-1，2026-08-13）
  ├── registry.jsonl         ← 全库题目注册（一行一题：hash/批次/题型/溯源）
  └── registry_meta.json     ← 注册表元信息（版本/统计）

reports/                     ← 自动化脚本输出（按子目录分类）
  ├── validate/              ← validate_options.py
  ├── healthcheck/           ← healthcheck.py
  ├── maintenance/           ← maintenance.py
  └── gate/                  ← gate_check.py

archive/                     ← 统一归档（根级别）
  ├── 中间产物/batchXXX/
  ├── 最终产物/batchXXX/
  ├── 质检报告/batchXXX/
  └── reports/YYYY-MM/
```

### 根目录禁止清单（Root Blocklist）

> 以下文件类型**绝对不可**出现在任何工作区根目录。

| 禁止类型 | 示例 | 正确做法 |
|----------|------|----------|
| 安装程序 | `.exe`, `.msi` | 安装后立即删除 |
| 报告产物 | `validate_options_report_*.json`, `healthcheck_*.json` | 移入 `reports/validate/` 或 `reports/healthcheck/` |
| 日志文件 | `*.log` | 放入 `logs/` 或 `.gitignore` |
| Python缓存 | `__pycache__/`, `*.pyc` | `.gitignore` + maintenance.py 自动清理 |
| ~~重复目录~~ | ~~`02_中间产物/` + `中间产物/`~~ | ✅ 已统一，2026-06-16 |
| 空目录 | 无内容的目录 | 删除 |
| 散落脚本 | 不属于工作流的 .py | 移入 `scripts/` 或删除 |
| 报告/文档 | `技术报告.md`, `架构介绍.md` | 移入 `docs/` |

**例外规则**：`_scratch/` 目录用于临时放置，但必须在一周内清理。

### 文件生命周期（Lifecycle Gate）

每个新文件经过以下检查再决定位置：
1. **这个文件属于哪个工作流阶段？** → 放入对应目录（输入/中间/质检/最终/GoldenSet）
2. **3 个月后还有用吗？** → 没用就删除或放入 `archive/`
3. **属于哪个批次？** → 文件名必须含 `batch{NNN}` 编号
4. **是报告/文档吗？** → 放入 `docs/`，不放根目录

### 工作区清理检查（每次任务完成后）

Agent 每完成一轮任务后执行：
- [ ] 根目录有无新增不应存在的文件？（对照铁律①）
- [ ] 根目录有无 `validate_options_report_*.json` 泄漏？（对照铁律⑤）
- [ ] 有无重复文件跨目录存在？（对照铁律④）
- [ ] 已签收的批次是否已移入 `archive/`？（对照铁律③）
- [ ] `reports/` 子目录有无超期文件？（对照铁律②）
- [ ] `__pycache__/` 是否已清理？（对照铁律⑥）
- [ ] `知识库素材/` 索引是否需要更新？

### MedAgentWork 特定修复清单

| 文件 | 问题 | 处置 |
|------|------|------|
| ~~`02_中间产物/`~~ | ~~与 `中间产物/` 重复~~ | ✅ 已合并，2026-06-16 |
| ~~`04_最终产物/`~~ | ~~与 `最终产物/` 重复~~ | ✅ 已合并，2026-06-16 |
| ~~`pipeline.yaml`~~ | ~~根目录散落~~ | ✅ 移至 scripts/，2026-06-24 |
| ~~`regression_db.json`~~ | ~~根目录散落~~ | ✅ 移至 scripts/，2026-06-24 |
| ~~`validate_options_report_*.json`（9个）~~ | ~~根目录泄漏~~ | ✅ 已删（reports/ 有副本），2026-06-24 |
| ~~`__pycache__/`~~ | ~~根目录缓存~~ | ✅ 已删，2026-06-24 |
| ~~分散的 archive/~~ | ~~中间产物/archive/ + 最终产物/archive/~~ | ✅ 已合并至根级 archive/，2026-06-24 |
| `技术报告_面向技术爱好者.md` | 报告在根目录 | 移入 `docs/` |
| `面向医学生的架构介绍.md` | 报告在根目录 | 移入 `docs/` |

### 整洁度原则（Clean Workspace Doctrine）

> 工作区的整洁度直接影响 Agent 运行效率。根目录每多一个无关文件，Agent 定位目标的 token 成本就增加。

## 知识库个性化 RAG（2026-06-20 新增）

> 每个医学学科有独立的分块策略、检索参数和语义保护规则。一刀切策略已废弃。

### 核心脚本

| 脚本 | 用途 | 关键参数 |
|------|------|----------|
| `知识库素材/embed_index.py` | PDF 教材嵌入索引 | `--force` 强制重新索引；`--subject <code>` 单科索引 |
| `知识库素材/embed_md.py` | 贺银成 Markdown 嵌入索引 | `--force` 强制重新索引 |
| `知识库素材/embed_zhaozhao.py` | 昭昭题眼 Markdown 嵌入索引 | `--force` 强制重新索引 |
| `知识库素材/search_kb.py` | 两阶段检索（向量+重排序） | `--hybrid` 启用混合检索；`--no-hybrid` 禁用；`--no-rerank` 成本降级（跳过付费 rerank）；`--no-cache` 禁用磁盘缓存（默认开启，2026-08-20 成本优化） |
| `知识库素材/validate_configs.py` | 配置完整性/一致性校验 | 每次改配置后运行 |

### 学科 RAG 配置速查

| 学科 | code | chunk | top_n | hybrid | kw | 保护规则数 |
|------|------|:-----:|:-----:|:------:|:--:|:----------:|
| 内科学 | internal-med | 800 | **7** | ✓ | 0.3 | 2 |
| 外科学 | surgery | 1000 | 5 | ✓ | 0.4 | 2 |
| 儿科学 | pediatrics | 600 | **7** | ✓ | 0.3 | 3 |
| 神经病学 | neurology | 800 | 5 | ✓ | **0.5** | 3 |
| 精神病学 | psychiatry | 500 | 5 | ✓ | 0.3 | 3 |
| 皮肤性病学 | dermatology | 600 | 5 | — | — | 2 |
| 中医学 | tcm | 500 | 5 | ✓ | **0.6** | 4 |
| 医患沟通 | doctor-patient | 800 | 3 | — | — | 3 |
| 贺银成讲义 | heyincheng-jy* | 500 | 5 | ✓ | 0.4 | 1 |
| 贺银成真题 | heyincheng-zt* | 800 | 3 | ✓ | 0.5 | 1 |
| 昭昭题眼 | zhaozhao-part* | 400 | 3 | ✓ | 0.4 | — |

### 配置文件结构

```
知识库素材/
├── subject_config.json              ← 全局注册表（15个学科入口+默认值）
├── configs/                          ← 各学科独立配置
│   ├── internal-med_config.json      ← chunk_strategy + retrieval_strategy + query_enhancement
│   ├── surgery_config.json
│   └── ...
├── index_store/                      ← 向量索引 + 配置快照
│   ├── index_manifest.json           ← 每个entry含 config_version + chunk_size
│   └── {subject_code}/index_config.json  ← 索引时配置快照
└── chunks_metadata/                  ← 元数据 JSONL
```

### 混合检索原理

```
Stage 1: query → embed API → cosine_similarity → top-20候选
         └─ query → keyword tokens → Jaccard+coverage → keyword scores
         └─ blended = (1-kw)*cosine + kw*keyword → 重排 → top-20
Stage 2: 重排后候选 → rerank API → top-N结果（≥threshold）
```

### 鲁棒性保障

- **配置校验**：`python 知识库素材/validate_configs.py` — JSON/pattern/范围/manifest一致性
- **容错降级**：配置文件损坏→自动回退默认参数（不打乱检索流程）
- **版本追踪**：manifest 记录 `subject_config_version`，检索时检测配置-索引不一致并警告
- **索引快照**：每科索引目录保存 `index_config.json` 快照，可对比当前配置差异

## 考研真题配额（HC-18 · 2026-08-21 新增）

> 题库生成规则：每个学科批次约 1/5（目标 20%，合格带 15%–25%）的题目为考研原题（引用或轻度改编），
> 其余 4/5 按教材原创。本机素材已含 1994–2025 考研西综真题，之后所有学科批次按此执行。

### 真题素材源（只读，禁止写入/修改）

| 素材 | 位置 | 内容 |
|------|------|------|
| 真题试卷（题干+选项） | `GoldenSet/真题上册.md` → 解析产物 `GoldenSet/structured/GS_上册_2024.json` | 1994–2024 西综真题试卷，5168 题（B 型题组共享选项已绑定；**无答案**） |
| 真题精析（答案+解析） | `GoldenSet/真题下册.md` → 解析产物 `GoldenSet/structured/GS_下册_2025_1994.json` | 贺银成历年真题精析 4448 条（含答案/解析；**按 gs_id 与上册配对**） |
| RAG 真题索引 | `search_kb.py --subject heyincheng-zt1/2`、`zhaozhao-part1/2` | 贺银成真题 / 昭昭题眼（补充检索） |

### 配额工具与流程

```text
检索候选  python scripts/kaoyan_picker.py pick --subject {科目} --keywords "{章节关键词,逗号分隔}" --target {ceil(题数×0.2)} --out 中间产物/{batchID}/kaoyan_candidates.json
终审校验  python scripts/kaoyan_picker.py check --file 最终产物/{batchID}/ALL_questions_FIXED.json    # 占比<15% → exit 1
```

- 流程：批次启动 MedMaster 检索真题候选（注入 Agent 2 调用指令）→ MedGen 按 HC-18 引用/改编（`kaoyan_origin` 元数据 + `[源:考研真题 GS-XXX]` 溯源 + 解析来源句）→ MedQC D21 比对 → MedFix HC-4b 保护 → 终审 check
- **红线**：真题答案以官方公布为准（发现与教材冲突 → 升级告警，不得静默修改）；数值/诊断标准零改动
- 无真题覆盖章节（如中医方剂、医患沟通、部分皮肤性病学）：配额清零、以原创补齐，批次统计如实标注

## 工具路径

> Agent 不要重新下载这些工具。使用表中路径直接调用。
>
> 🔄 **跨 Agent 工具同步规则**：安装/下载任何新工具后，必须同步更新全部 6 个工作区的 CONTEXT.md 工具路径表。避免不同 Agent 重复下载相同工具。

| 工具 | 版本 | 路径 | 调用方式 |
|------|------|------|----------|
| **Python** | 3.12.10 | `C:\Users\38063\AppData\Local\Programs\Python\Python312\python.exe` | `python` |
| **Node.js** | v24.16.0 | `C:\Program Files\nodejs\node.exe` | `node` |
| **npm** | 11.13.0 | `C:\Program Files\nodejs\npm.cmd` | `npm` |
| **Git** | 2.54.0 | `C:\Program Files\Git\mingw64\bin\git.exe` | `git` |
| **gh** (GitHub CLI) | 2.97.0 | `C:\Program Files\GitHub CLI\gh.exe` | `gh` |
| **wrangler** (Cloudflare CLI) | 4.120.0 | 全局 npm 包 | `wrangler` |
| **Pandoc** | 3.8.3 | `C:\Program Files\RStudio\resources\app\bin\quarto\bin\tools\pandoc.exe` | 完整路径（不在 PATH） |
| **R** | 4.6.0 | `C:\Program Files\R\R-4.6.0\bin\R.exe` | `R`（不在 PATH） |
| **RStudio** | — | `C:\Program Files\RStudio\rstudio.exe` | 完整路径 |
| **Chrome** | — | `C:\Users\38063\AppData\Local\Google\Chrome\Application\chrome.exe` | Playwright 自动发现 |
| **Playwright** | 1.60.0 | `C:\Users\38063\AppData\Roaming\npm\playwright.cmd` | `npx playwright` |
| **curl** | — | Git Bash 自带 | `curl` |
| **mmdc** (Mermaid) | 11.15.0 | 全局 npm 包 | `mmdc` |
| **render_review.py** | 1.0.0 | `知识库素材/render_review.py` | `python 知识库素材/render_review.py "复习资料/XXX.md"` |
| **review_template.html** | 1.0.0 | `知识库素材/review_template.html` | 渲染模板（含 demo 内容），供 render_review.py 参考 |
| **r2_balancer.py** | 2.0.0 | `scripts/r2_balancer.py` | `python scripts/r2_balancer.py --file <path>` — **只扩充不截断**的R2选项长度平衡器 |
| **workflow_state.py** | 1.0.0 | `scripts/workflow_state.py` | `python scripts/workflow_state.py --check / --migrate / --show {batchID}` — 状态统一读写/校验/迁移（2026-08-13 重构） |
| **qbank.py** | 1.1.0 | `scripts/qbank.py` | `python scripts/qbank.py init / register / query / stats / check / export-md / rehome` — 统一题库注册表 + 最终交付 MD 导出 + 归档路径重定位（2026-08-20 升级） |
| **run_tests.py** | 1.0.0 | `scripts/run_tests.py` | `python scripts/run_tests.py` — 零依赖测试运行器（P0-2，2026-08-13）；有 pytest 时可用 `python -m pytest tests/ -q` |
| **fact_check.py** | 1.0.0 | `scripts/fact_check.py` | `python scripts/fact_check.py pages --file X --subject neurology` / `golden --file X` — 事实校验机械化（P1-1，2026-08-13）：页码反查 + GoldenSet 交叉验证 |
| **kaoyan_picker.py** | 1.0.0 | `scripts/kaoyan_picker.py` | `python scripts/kaoyan_picker.py pick --subject 内科学 --keywords "心衰,心力衰竭" --target 20 --out ...` / `check --file ...` — 考研真题配额（HC-18，2026-08-21）：pick 按章节检索真题候选（上册题干+下册答案按 gs_id 配对），check 校验 kaoyan_origin 占比（<15% exit 1） |
| **blueprint.py** | 1.0.0 | `scripts/blueprint.py` | `python scripts/blueprint.py` — 考频蓝图（2026-08-20 第三方交付）：GS 下册 + 贺银成引用 → 学科权重 + 高频真题，输出 `知识库素材/blueprint.json`（标准库） |
| **anchor_bank.py** | 1.0.0 | `scripts/anchor_bank.py` | `C:/Users/38063/AppData/Local/Programs/Python/Python312/python.exe scripts/anchor_bank.py download/embed/anchor/check` — CMExam 锚点难度体系（2026-08-20 第三方交付）。⚠️ **必须用 Python312**（torch+sentence-transformers 已装，默认 python 3.10 无 torch）；embed 已缓存可跳过；重跑 anchor 后必须 `python scripts/apply_calibrated_difficulty.py` 回写 registry |
| **apply_calibrated_difficulty.py** | 1.1.0 | `scripts/apply_calibrated_difficulty.py` | `python scripts/apply_calibrated_difficulty.py [--dry-run]` — **expanded 校准值回写 registry（2026-08-21 终审修订）**：默认读 `calibrated_difficulty.expanded.jsonl`，按 qid join 刷新 calibrated_p/calibration_confidence/calibration_flag/max_sim/prior_key + 补 anchor_source；写前自动备份 registry.jsonl；registry 已去重为 qid 唯一，qid join 安全 |
| **paper_builder.py** | 1.0.0 | `scripts/paper_builder.py` | `python scripts/paper_builder.py --subject 内科学 --count 100 [--dry-run]` — 组卷公式 v1.0（2026-08-20）：考频权重 × 难度配平(calibrated_p) × NFD 过滤；输出兼容 `scripts/quiz_template.html` QUESTIONS 数组 |
| **clean_produce_markup.py** | 1.0.0 | `scripts/clean_produce_markup.py` | `python scripts/clean_produce_markup.py [--dry-run]` — 交付物清理（2026-08-22）：清除复习资料 MD/HTML 的批次标记/自检报告残留 + 押题卷副标题成品化（去「统一模板/TEST」）；备份至 `archive/交付物清理前备份_*` |
| **verify_produce_rules.py** | 1.0.0 | `scripts/verify_produce_rules.py` | `python scripts/verify_produce_rules.py` — 产物形态门禁（2026-08-22，FAIL==0 才放行）：扩展名白名单（押题卷=仅html / 题库=md+html+pdf / 复习资料=md+html）、押题卷副标题质检、复习资料无流程残留/无 Mermaid、PDF 人工上传标记。规则源：`docs/产物格式规范.md`（HC-18） |
| **render_qbank_html.py** | 1.0.0 | `scripts/render_qbank_html.py` | `python scripts/render_qbank_html.py --input <题库JSON> --output <out.html> [--title ...]` — 题库最终产物 HTML 交付版（2026-08-22）：题库 PDF 一律人工上传，本脚本只产 HTML |
| **quiz_template.html** | 1.0.0 | `scripts/quiz_template.html` | 统一押题卷模板（2026-08-20 第三方交付）：CSS 变量化/亮暗主题/响应式/作答采集；题目注入 `<script id="quiz-data">` 的 QUESTIONS 数组 |
| **dsh** (DeepSeek Harness) | 0.1.0-rc.7 | `C:\Users\38063\Desktop\Web-AI\tools\dsh\node_modules\.bin\dsh` | `cd C:\Users\38063\Desktop\Web-AI\tools\dsh && npx dsh web`（需 API key） |

### 环境备忘（2026-08-20 · 第三方交付后）

| 项 | 备忘 |
|---|---|
| **Python312** | `C:/Users/38063/AppData/Local/Programs/Python/Python312/python.exe` — torch 2.12 + sentence-transformers 5.5.1 + scipy/sklearn 齐全；**anchor_bank.py 必须用此解释器**（默认 `python` 3.10 无 torch） |
| **bge-small-zh-v1.5** | 已缓存 `~/.cache/huggingface/hub`，离线可跑；如需重下走 `HF_ENDPOINT=https://hf-mirror.com` |
| **GitHub 镜像序** | `gh-proxy.com` → `ghproxy.net` → `mirror.ghproxy.com` → 直连（实测 gh-proxy.com 可用，mirror.ghproxy.com 超时） |
| **calibrated_p 性质** | CMExam 人工标注锚点 + 先验表的外部先验估计，**非本库实测**。允许：组卷配平/异常筛查/推送排序；禁止：对外标注「实测难度」 |
| **注册表覆盖** | registry 现 4917 题（2026-08-20 补齐 batch004/006/007/008/009/010/011/012/013/014/016/020/021/023/027 注册）；batch003(SUPERSEDED)/005/024/025 无结构化 JSON 未注册 |

### 复习资料渲染（2026-06-21 新增）
- `python 知识库素材/render_review.py "复习资料/XXX_主复习资料.md"` → 生成精美自包含 HTML
- 选项：`-o output.html` 指定输出路径，`--dark` 默认暗色模式
- 特性：暗色/亮色模式、固定侧栏导航、填空点击显示、打印优化、零外部依赖

### 全局 npm 包
`@anthropic-ai/claude-code@2.1.167` `@mermaid-js/mermaid-cli@11.15.0` `playwright@1.60.0`

### 关键 Python 包（已安装，全局可用）
**PDF**: `pypdf` `PyMuPDF` `pdfplumber` `pdfminer-six`
**文档**: `markitdown` `beautifulsoup4` `lxml` `markdown`
**AI/ML**: `openai` `tiktoken` `chromadb` `sentence-transformers` `torch` `transformers`
**HTTP**: `requests` `httpx` `aiohttp`
**数据**: `numpy` `pandas` `matplotlib` `openpyxl` `scikit-learn` `seaborn`
**开发**: `rich` `typer` `loguru` `Pillow` `playwright` `python-pptx`
**Web**: `fastapi` `uvicorn` `streamlit` `crawl4ai`

### MCP Server
| Server | 主要工具 | 用途 |
|--------|---------|------|
| **medical-rag** | `query`, `index` 等 | 医学知识检索增强（本地 RAG） |

### 未安装（GitHub 直连被 GFW 阻断，无法下载）
- **jq** — 替代：`python -c "import json; ..."`
- **ffmpeg** — 媒体处理不可用
- **ImageMagick** — 替代：Pillow
- **Inkscape** — 替代：Pillow + lxml

## 多 Agent 协作规则

> 5 个 Agent 共享同一工作文件夹。**2026-08-13 起主流程为 DSH 自动编排**（角色技能 `.dsh/skills/`，编排在主会话完成）；Cherry Studio 用户中转接力（下节"旧调用链路"）保留为备用。

### DSH 调用链路（主流程 · 2026-08-13 重构）
```
用户 → 主会话 (MedMaster, medmaster skill) → 回显意图 → 用户确认
      → 编排者后台调用 MedGen (medgen skill) → 题库直写 中间产物/{batchID}/
      → 编排者运行 validate_options.py 门禁 (FAIL==0)
      → 后台调用 MedQC (medqc skill) → 质检报告直写 质检报告/{batchID}/
      → 编排者运行 gate_check.py --stage agent3_done
      → 后台调用 MedFix (medfix skill) → 修复版直写 最终产物/{batchID}/
      → 编排者运行 gate_check.py --stage agent4_done
      → 后台调用 MedReview (medreview skill) → 复习资料直写 复习资料/
      → 编排者运行 gate_check.py --stage final
      → 用户审查 → 签收/打回 → 合格手动加入 GoldenSet/
```
批次运行手册：`.dsh/skills/medbatch/SKILL.md`（阶段序列/门禁命令/目录命名/故障处置）。
每批次建议独立 DSH 会话；事件记入 `memory/JOURNAL.jsonl`。

### 旧调用链路（Cherry Studio 用户中转，已弃用）
```
用户 → Agent 1 (MedMaster) → 回显意图 → 用户确认
      → Agent 1 给出 Agent 2 调用指令 → 用户粘贴到 Agent 2
      → Agent 2 产出 → 用户存入 中间产物/
      → Agent 1 给出 Agent 3 调用指令 → 用户粘贴到 Agent 3
      → Agent 3 产出 JSON → 用户存入 质检报告/
      → Agent 1 给出 Agent 4 调用指令 → 用户粘贴到 Agent 4
      → Agent 4 修改文件 → 输出最终产物 + 追溯日志
      → Agent 1 给出 Agent 5 调用指令 → 用户粘贴到 Agent 5
      → Agent 5 生成主复习资料 → 用户存入 复习资料/
      → 用户审查 → 签收/打回 → 合格加入 GoldenSet/
```

### 各 Agent 职责
| Agent | 职责 | 输入 | 输出 |
|-------|------|------|------|
| **Agent 1 (MedMaster)** | 编排者：解析意图、分发任务 | 用户指令 | 下游 Agent 调用指令 |
| **Agent 2 (MedGen)** | 根据教材生成题目+备考资料 | 输入素材/ | 中间产物/ batch JSON + 备考资料 |
| **Agent 3 (MedQC)** | 质量检查 + 打分 | 中间产物/ + GoldenSet/ | 质检报告/ JSON |
| **Agent 4 (MedFix)** | 自动修改 + 追溯 | 中间产物/ + 质检报告/ | 最终产物/ + 追溯日志 |
| **Agent 5 (MedReview)** | 生成主复习资料 | 备考资料 + 修复后题库 + RAG教材 | 复习资料/ 主复习资料 MD |

### 交接规范
- 每个 Agent 只读写自己负责的目录
- 产出文件命名含 `batch` 号（如 `batch001_质检报告.json`）
- 追溯日志记录每次修改的依据（质检报告中的具体问题编号）
- GoldenSet 由用户手动签收，Agent 不直接写入

### 管线强制规则（2026-06-20 新增）

> `save.py` 和 `ingest.py` 内置以下保护：
> 1. **阶段顺序锁**：前置阶段产出不存在时拒绝入库（如 agent3 产出未就绪时不能 save agent4）
> 2. **防覆盖**：同名文件已存在时自动加时间戳后缀，不覆盖
> 3. **防剪贴板错乱**：检测到 Agent 1 调用指令时拒绝（防止误存指令为产出）
> 4. **GoldenSet 写保护**：任何脚本拒绝写入 GoldenSet/ 目录（只能用户手动签收）
> 5. **防格式错配**：agent3 阶段检测内容是否含质检报告特征字段
