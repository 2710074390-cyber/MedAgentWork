# MedAgentWork 基于 Cherry Studio 的完整实现教程

> 目标读者：技术背景用户，希望从零搭建这套 4-Agent 医学题库生产系统
> 预期耗时：首次搭建约 2-3 小时（含 MCP 配置 + Agent Prompt 配置 + 知识库索引）

---

## 一、整体架构速览

在开始搭建前，先理解我们在 Cherry Studio 中要做什么：

```
Cherry Studio 桌面应用
│
├── Agent 1: MedMaster (deepseek-v4-pro)
│   ├── MCP: CherryFilesystem + CherryPython + CherryBraveSearch + CherryFetch + ...
│   ├── 工作目录: MedAgentWork/
│   └── 职责: 编排调度
│
├── Agent 2: MedGen (deepseek-v4-pro)
│   ├── MCP: CherryFilesystem
│   ├── 工作目录: MedAgentWork/
│   └── 职责: 出题
│
├── Agent 3: MedQC (qwen3.7-max)
│   ├── MCP: CherryFilesystem + CherryPython + CherryBraveSearch
│   ├── 工作目录: MedAgentWork/
│   └── 职责: 质检
│
├── Agent 4: MedFix (qwen3.7-max)
│   ├── MCP: CherryFilesystem
│   ├── 工作目录: MedAgentWork/
│   └── 职责: 修改执行
│
├── MCP 服务器组（全局配置）
│   ├── CherryFilesystem    ← 文件系统读写
│   ├── CherryPython        ← Python 脚本执行
│   ├── CherryBraveSearch   ← 网络搜索
│   ├── CherryFetch         ← 网页抓取
│   ├── CherrySequentialthinking ← 序列思考
│   └── aliyunbailianmcpWebsearch ← 阿里云搜索
│
└── 知识库（Knowledge Base）
    └── 临床医学教材库 ← RAG 检索源
```

**关键设计决策**：
- 4 个 Agent 共享同一个工作目录（MedAgentWork），但通过文件目录约定隔离操作范围
- Agent 间通过「用户人工中转」传递信息（粘贴指令/产物），不进行 Agent 间直接调用
- MedMaster 使用最强模型 deepseek-v4-pro（需大量 MCP 工具），MedQC/MedFix 使用 qwen3.7-max（成本低，纯文本分析任务）

---

## 二、前置准备

### 2.1 安装 Cherry Studio

从 [Cherry Studio 官方发布页](https://github.com/CherryHQ/cherry-studio/releases) 下载安装包。

Cherry Studio 是一个开源的 AI 对话客户端，支持多模型接入、Agent 智能体、MCP 服务器、知识库等能力。

### 2.2 准备 API Key

本系统需要以下 API 服务：

| 用途 | 服务商 | 最低需求 | 获取方式 |
|------|--------|----------|----------|
| **MedMaster/MedGen 模型** | DeepSeek | deepseek-v4-pro | deepseek.com |
| **MedQC/MedFix 模型** | 阿里云百炼 | qwen3.7-max | 百炼控制台 |
| **语义嵌入 + 重排序** | 硅基流动 | SILICONFLOW_API_KEY | cloud.siliconflow.cn |
| **网络搜索** | Brave Search | FREE 计划可用 | api.search.brave.com |

在 Cherry Studio 中配置：
1. 左下角设置 → **模型服务商**
2. 分别填入 DeepSeek、阿里云百炼、硅基流动的 API Key
3. 硅基流动的 API Key 还需要在 Agent 环境变量中设置（见后文）

### 2.3 创建目录结构

在与用户桌面创建以下目录结构：

```
MedAgentWork/              ← 工作根目录（4 个 Agent 共享）
├── 输入素材/              ← 原始教材/笔记/重点（用户放入）
│   ├── 内科学/
│   ├── 神经病学/
│   ├── 儿科学/
│   └── ...
├── 中间产物/              ← Agent 2 产出
├── 质检报告/              ← Agent 3 产出
├── 最终产物/              ← Agent 4 产出
├── GoldenSet/             ← 金标准真题（用户签收）
├── 知识库素材/            ← RAG 索引源文件
│   ├── 索引规则.md
│   ├── embed_index.py
│   ├── search_kb.py
│   ├── 内科学/
│   ├── 神经病学/
│   └── ...
├── Prompt版本/            ← Agent Prompt 版本历史
├── memory/                ← 持久化记忆
├── CONTEXT.md             ← 共享上下文（工作流规则）
├── SOUL.md                ← 共享人格约束
├── USER.md                ← 用户信息
├── workflow_state.json    ← 工作流状态机
└── 操作流程.txt           ← 用户操作指引
```

> **技巧**：`CONTEXT.md` 和 `SOUL.md` 是两个关键的工作流文档，它们定义了 4 个 Agent 共享的「工作语言」，包括目录规范、网络约束、交接格式等。所有 Agent 的 Prompt 中应引用这些文件。详见工程文件。

---

## 三、配置 MCP 服务器

MCP（Model Context Protocol）是 Cherry Studio 的「工具协议层」——Agent 通过 MCP 服务器获得文件系统、Python 执行、网络搜索等能力。

### 3.1 MCP 服务器清单

| MCP 服务器 | 用途 | 被哪些 Agent 使用 |
|-----------|------|------------------|
| **CherryFilesystem** | 文件系统读写（最核心） | 全部 4 个 Agent |
| **CherryPython** | 执行 Python（语义检索脚本） | MedMaster, MedQC |
| **CherryBraveSearch** | 网络搜索验证 | MedMaster, MedQC |
| **CherryFetch** | 网页内容获取 | MedMaster, MedQC |
| **CherrySequentialthinking** | 复杂任务拆解 | MedMaster |
| **aliyunbailianmcpWebsearch** | 阿里云搜索补充 | MedMaster |

### 3.2 配置步骤

在 Cherry Studio 左下角设置 → **MCP 服务器** → **添加**：

#### CherryFilesystem

| 字段 | 值 |
|------|-----|
| 名称 | CherryFilesystem |
| 类型 | stdio |
| 命令 | npx |
| 参数 | `-y @anthropic-ai/claude-code --mcp CherryFilesystem` |
| 环境变量 | CHERRY_WORK_DIR=`C:\Users\{你的用户名}\Desktop\MedAgentWork` |

> **说明**：CherryFilesystem 是最关键的 MCP——Agent 通过它读写工作目录中的所有文件。注意设置 CHERRY_WORK_DIR 环境变量锁定可访问的根目录，防止 Agent 访问敏感系统文件。

#### CherryPython

| 字段 | 值 |
|------|-----|
| 名称 | CherryPython |
| 类型 | stdio |
| 命令 | npx |
| 参数 | `-y @anthropic-ai/claude-code --mcp CherryPython` |

#### CherryBraveSearch

| 字段 | 值 |
|------|-----|
| 名称 | CherryBraveSearch |
| 类型 | stdio |
| 命令 | npx |
| 参数 | `-y @anthropic-ai/claude-code --mcp CherryBraveSearch` |
| 环境变量 | BRAVE_API_KEY=`你的Brave API Key` |

#### CherryFetch

| 字段 | 值 |
|------|-----|
| 名称 | CherryFetch |
| 类型 | stdio |
| 命令 | npx |
| 参数 | `-y @anthropic-ai/claude-code --mcp CherryFetch` |

#### CherrySequentialthinking

| 字段 | 值 |
|------|-----|
| 名称 | CherrySequentialthinking |
| 类型 | stdio |
| 命令 | npx |
| 参数 | `-y @anthropic-ai/claude-code --mcp CherrySequentialthinking` |

#### aliyunbailianmcpWebsearch

| 字段 | 值 |
|------|-----|
| 名称 | aliyunbailianmcpWebsearch |
| 类型 | stdio |
| 命令 | npx |
| 参数 | `-y @anthropic-ai/claude-code --mcp aliyunbailianmcpWebsearch` |

### 3.3 验证 MCP 连接

每个 MCP 配置完成后，Cherry Studio 会显示「已连接」状态指示灯。如果显示红色：
1. 检查命令和参数是否正确（特别注意：这是 `npx` 而非 `npm`）
2. 检查环境变量是否设置正确
3. 检查网络（中国大陆用户可能需要代理）

---

## 四、创建 4 个 Agent

### 4.1 Agent 参数总表

| 参数 | Agent 1 MedMaster | Agent 2 MedGen | Agent 3 MedQC | Agent 4 MedFix |
|------|------------------|---------------|---------------|---------------|
| **类型** | claude-code | claude-code | claude-code | claude-code |
| **模型** | deepseek:deepseek-v4-pro | deepseek:deepseek-v4-pro | dashscope:qwen3.7-max | dashscope:qwen3.7-max |
| **工作目录** | MedAgentWork | MedAgentWork | MedAgentWork | MedAgentWork |
| **权限模式** | Bypass | Bypass | Bypass | Bypass |
| **MCP 数量** | 6 个 | 1 个 | 4 个 | 1 个 |

### 4.2 创建步骤

1. 左侧导航栏点击 **Agent** 图标
2. 点击 **+ 创建 Agent**
3. 填入名称（如"① MedMaster 主控编排器"）
4. **关键设置**：
   - **类型**选择 `claude-code`（这是启用 MCP 工具调用的前提）
   - **模型**按上表选择（需提前在模型服务商中配置好 API Key）
   - **工作目录**设置为 `C:\Users\{你的用户名}\Desktop\MedAgentWork`
   - **权限模式**建议选 `Bypass`（否则每次文件读写都需要手动确认）
5. 勾选需要的 **MCP 服务器**（按上表）
6. 将对应 Agent 的 **System Prompt** 粘贴到指令框
7. 保存

> **⚠️ 重要**：一定要将类型设为 `claude-code`，否则 MCP 工具无法使用。这是 Cherry Studio 的一个关键配置——普通 Agent 类型只支持对话，不支持工具调用。

### 4.3 各 Agent System Prompt 来源

4 个 Agent 的 System Prompt 已在工程 `Prompt版本/` 目录中归档：

| Agent | Prompt 文件 | 说明 |
|-------|-----------|------|
| MedMaster | `Prompt版本/MedMaster_current_prompt.md` | 编排器——状态机 + HC 约束 + 调度模板 |
| MedGen | `Prompt版本/MedGen_current_prompt.md` | 出题器——NBME 规范 + Schema 格式 |
| MedQC | `Prompt版本/MedQC_current_prompt.md` | 质检器——19 维度检测矩阵 |
| MedFix | `Prompt版本/MedFix_current_prompt.md` | 执行器——Patch 执行引擎 + 门禁规则 |

直接复制文件中 `<START>...<内容部分>...` 之间的内容（去掉 `<START>` 和 `</START>` 标记）粘贴到 Cherry Studio 的指令框中。

#### MedMaster 专用设置：环境变量

MedMaster 需要硅基流动 API Key 来执行语义检索（RAG 验证），需要在 Agent 设置中添加环境变量：

1. 在 Agent 编辑页找到 **环境变量** 区域
2. 添加：`SILICONFLOW_API_KEY = sk-你的硅基流动API Key`

### 4.4 Model ID 映射说明

Cherry Studio 中使用 `服务商:模型名` 的格式引用模型：

| Cherry Studio 格式 | 实际模型 | 提供商 |
|-------------------|----------|--------|
| `deepseek:deepseek-v4-pro` | DeepSeek V4 Pro | DeepSeek |
| `dashscope:qwen3.7-max` | Qwen 3.7 Max | 阿里云百炼 |

这些模型名取决于你在 Cherry Studio **模型服务商**配置中填入的模型列表。如果找不到对应模型，请检查：
- DeepSeek: 在设置中启用 deepseek-v4-pro
- 阿里云: 在百炼控制台开通 qwen3.7-max 服务

---

## 五、搭建 RAG 知识库

知识库是本系统的事实锚点——Agent 2 出题时以知识库检索到的教材原文为事实依据，避免 AI 编造数据。

### 5.1 准备教材 PDF

将教材 PDF 放入 `知识库素材/` 目录下的对应子目录：

```
知识库素材/
├── 内科学/
│   └── 21. 内科学（第10版）.pdf
├── 神经病学/
│   └── 25. 神经病学（第9版）.pdf
├── 儿科学/
│   └── 24. 儿科学（第9版）.pdf
├── 外科学/
│   └── 22. 外科学（第9版）.pdf
└── ...
```

### 5.2 配置索引规则

`知识库素材/索引规则.md` 中定义嵌入模型、分块策略、检索配置等。关键参数：

| 参数 | 值 | 说明 |
|------|-----|------|
| 嵌入模型 | BAAI/bge-m3 | 1024 维，中英双语 |
| 重排序模型 | BAAI/bge-reranker-v2-m3 | 交叉编码器 |
| chunk_size | 800 字符 | 中文医学文本高密度 |
| chunk_overlap | 150 字符 | 防止数值边界截断 |
| 检索 top_k | 20 | 初次召回数 |
| 重排序后 top_n | 5 | 最终返回数 |

### 5.3 运行索引脚本

项目中已包含建立索引的 Python 脚本，通过 CherryPython MCP 执行：

```
知识库素材/embed_index.py   ← 主索引脚本（批量处理）
知识库素材/embed_md.py      ← Markdown 文件索引
知识库素材/embed_zhaozhao.py ← 特定素材索引
知识库素材/search_kb.py     ← 检索脚本（Agent 1 调用）
```

**首次索引**：在 MedMaster（或其他有 CherryPython MCP 的 Agent）中执行：
```
python 知识库素材/embed_index.py
```

这将遍历 `知识库素材/` 下所有 PDF，按 800 字符分块 + 150 字符重叠，调用硅基流动 API 生成嵌入向量，存入 `知识库素材/index_store/`。

### 5.4 验证检索

```bash
python 知识库素材/search_kb.py "心房颤动 CHA2DS2-VASc评分" --subject 内科学 --top 5
```

如果返回结果中得分 ≥0.80 的片段数 ≥3，说明索引质量合格。

---

## 六、认知：Agent 间如何协作工作

这是理解本系统运行方式最关键的一环——**Agent 间不直接通信**，用户作为中转站。

### 6.1 为什么这样设计？

原因有 3 个：

1. **审计需求**：每次交接都是显式操作，不会出现 Agent 静默调用链
2. **纠错窗口**：用户可以在任意环节拦截、检查、修正
3. **安全隔离**：不需要为每个 Agent 开放对其他 Agent 产物的写权限

### 6.2 完整的工作循环

以下是一个批次的完整工作流程：

```
你 → 打开 Agent 1 (MedMaster)
  │  你说：「开始新批次，科目：神经病学」
  │  Agent 1 读取输入素材 → 检索知识库 → 输出「意图确认回显」
  │  你确认 → Agent 1 生成 Agent 2 调用指令
  │
  ▼
你 → 复制 Agent 1 生成的指令 → 粘贴到 Agent 2 (MedGen)
  │  Agent 2 读取教材 → 按规范生成题目 → 输出结构化题库 JSON
  │  你将产物保存到 中间产物/batchXXX/
  │
  ▼
你 → 切回 Agent 1
  │  你说：「Agent 2 产出已就绪」
  │  Agent 1 读取中间产物 → 生成 Agent 3 质检指令
  │
  ▼
你 → 复制质检指令 → 粘贴到 Agent 3 (MedQC)
  │  Agent 3 从 19 个维度逐题检查 → 输出 JSON 质检报告
  │  你将报告保存到 质检报告/batchXXX_质检报告.json
  │
  ▼
你 → 切回 Agent 1
  │  你说：「质检报告已就绪」
  │  Agent 1 读取质检报告 → 解析门禁状态 → 生成 Agent 4 修改指令
  │
  ▼
你 → 复制修改指令 + 质检报告 → 粘贴到 Agent 4 (MedFix)
  │  Agent 4 逐条执行 patch → 输出最终产物 + 追溯日志
  │  产物保存到 最终产物/batchXXX/
  │
  ▼
你 → 审查最终产物 → 签收/打回
  │  签收 → 加入 GoldenSet/
  │  打回 → 重新修改
```

### 6.3 每次切换 Agent 的操作细节

下表是你在 Cherry Studio 界面中的实际操作：

| 步骤 | 操作 | 耗时 |
|------|------|------|
| 1. 在 Agent 1 聊天框输入指令 | 打字约 10s | ~10s |
| 2. Agent 1 响应 → 复制输出 | 等待 + 复制约 30s | ~30s |
| 3. 左侧切换 Agent 2 → 粘贴并发送 | 鼠标切换 + 粘贴约 10s | ~10s |
| 4. Agent 2 响应 → 文件自动保存 | 等待约 3-10min | ~5min |
| 5. 切换回 Agent 1 → 通知就绪 | 约 10s | ~10s |
| 6. Agent 1 生成质检指令 → 复制 | 约 30s | ~30s |
| 7. 切换 Agent 3 → 粘贴指令 + 产物 | 约 15s | ~15s |
| 8. Agent 3 响应 → 质检报告保存 | 等待约 3-15min | ~8min |
| 9. 切换回 Agent 1 → 通知就绪 | 约 10s | ~10s |
| 10. 切换 Agent 4 → 粘贴指令 + 报告 | 约 15s | ~15s |
| 11. Agent 4 执行修改 → 保存产物 | 等待约 2-5min | ~3min |
| 12. 审查最终产物 | 约 5-15min | ~10min |

**合计**：约 20-30 分钟人工操作 + 20-40 分钟 Agent 处理时间。一次完整批次约 40-70 分钟。

---

## 七、运行工作流的首次实操

### 7.1 准备输入素材

以神经病学批次为例，将以下文件放入 `输入素材/神经病学/`：
- 教材原文 PDF（或提取的 txt）
- 课堂笔记
- 考试重点（教师划的重点大纲）

### 7.2 启动批次

打开 **Agent 1 (MedMaster)**，输入：

```
开始新批次。科目：神经病学。
素材在 输入素材/神经病学/ 目录下。
目标考试：考研西综，难度介于考研与期末之间。
要求：仅选择题，约 300 题，覆盖全部 12 个模块。
```

Agent 1 会：
1. 读取输入素材
2. 运行 `search_kb.py` 检索知识库
3. 生成 HC-7 命题双向细目表
4. 输出意图确认回显

确认无误后回复「确认」，Agent 1 会生成 Agent 2 调用指令。

### 7.3 后续交互

严格按 6.2 节的循环依次操作。每次用户说「Agent X 产出已就绪」，Agent 1 会自动读取对应的中间产物并生成下一步指令。

---

## 八、Golden Set 回归测试

### 8.1 什么是 Golden Set？

Golden Set 是**已签收的历年真题金标准**，用于在 Prompt 修改后验证系统质量是否回退。本工程包含：

- `GoldenSet/真题上册.md`：2017-2024 考研西综真题
- `GoldenSet/真题下册.md`：1994-2025 考研西综真题
- `GoldenSet/structured/`：结构化 JSON 版本的真题
- `GoldenSet/validate.py`：Golden Set 验证脚本
- `GoldenSet/regression.py`：回归测试脚本

### 8.2 何时运行回归

- **每次修改任意 Agent 的 Prompt 后**（Agent 1 会自动提示）
- **批量生产前**，确认系统状态正常

### 8.3 运行方式

```bash
python GoldenSet/regression.py
```

脚本会：读取 Golden Set → 逐题用当前质检流程检测 → 对比历史回归结果 → 输出回归报告。

### 8.4 用户自动触发机制

Agent 1 的 Prompt 中内置了 HC-4 规则：检测到 Prompt 文件变更后，自动提示用户运行回归测试。

---

## 九、故障排查与常见问题

### 9.1 MCP 连接失败

```
错误：MCP server XXX 连接失败
```

- 检查命令格式：`npx -y @anthropic-ai/claude-code --mcp ServerName`
- 检查环境变量是否正确设置
- 中国大陆用户可能需要配置系统代理（Cherry Studio 设置 → 网络）
- 尝试重启 Cherry Studio

### 9.2 Agent 不需要的 MCP 被勾选

- Agent 2 (MedGen) 只需要 CherryFilesystem，不需要其他 MCP
- Agent 4 (MedFix) 只需要 CherryFilesystem
- 多余的 MCP 会浪费 token 并可能引起不必要的工具调用

### 9.3 模型响应质量差

- MedMaster/MedGen 使用 deepseek-v4-pro，不适合用 qwen 替代
- MedQC/MedFix 不需要太强模型，qwen3.7-max 性价比高
- 如果发现模型拒绝执行某些指令，检查权限模式是否设为 Bypass

### 9.4 硅基流动 API 调用失败

```
错误：401 Unauthorized / 403 Forbidden
```

- 确认 `SILICONFLOW_API_KEY` 已设置在 Agent 1 的环境变量中
- 确认硅基流动账户余额充足
- 确认 API 端点 `https://api.siliconflow.cn` 可访问

### 9.5 CherryPython 执行脚本报错

- 确认 Python 依赖已安装：`pip install openai tiktoken pypdf PyMuPDF`
- 确认 Python 版本 ≥ 3.10
- 路径中含中文不影响 Python 执行，但影响某些库的文件读取

### 9.6 Agent 2 出题质量不佳

- 检查输入素材是否完整（教材原文 + 重点笔记）
- 检查 RAG 检索结果是否返回了相关片段
- 检查命题双向细目表（HC-7）的 Bloom 层级分配是否合理
- 检查 NBME 7 项硬约束在 Agent 2 Prompt 中是否完整

---

## 十、工程文件清单与用途

| 文件/目录 | 用途 | 谁创建/维护 |
|-----------|------|-------------|
| `输入素材/` | 存放原始教材/笔记/重点 | 用户放入 |
| `中间产物/` | Agent 2 的题库产出 | Agent 2 写入 |
| `质检报告/` | Agent 3 的 JSON 质检报告 | Agent 3 写入 |
| `最终产物/` | Agent 4 修改后的最终版本 | Agent 4 写入 |
| `GoldenSet/` | 真题金标准（签收后加入） | 用户手动维护 |
| `知识库素材/` | 教材 PDF + 索引 + 检索脚本 | 用户放入 + 脚本自动索引 |
| `Prompt版本/` | 各 Agent Prompt 版本历史 | Agent 1 写入 |
| `workflow_state.json` | 工作流状态（batch/step/timestamp） | Agent 1 维护 |
| `CONTEXT.md` | 共享上下文规则 | 用户/Agent 维护 |
| `SOUL.md` | 共享人格约束 | 用户/Agent 维护 |
| `memory/` | 持久化记忆（FACT.md + JOURNAL.jsonl） | Agent 维护 |

---

## 十一、经验与建议

### 11.1 初始阶段

- **先跑一个小批次验证**：不要一上来就 300 题。先用 1 个模块 20 题跑通全流程，确认所有组件工作正常
- **Golden Set 先不建**：前几个批次的签收产物自然积累为 Golden Set，不需要一次性导入
- **知识库先建高频科目**：内科、外科优先索引，其他科目按需索引

### 11.2 日常使用

- **保持 Prompt 版本记录**：Agent 1 会自动记录到 `Prompt版本/` 目录
- **Prompt 修改后一定跑回归**：跳过这一步可能导致质量回退了但不知道
- **定期清理中间产物**：已签收批次的中间产物可移入 `archive/`，保持目录整洁
- **监控硅基流动 API 消耗**：大 PDF 索引会消耗较多 token

### 11.3 质量红线

以下情况**必须停止**并检查：
1. Agent 4 的追溯日志中出现 `POLARITY_VIOLATION`
2. 质检报告 gate_decision 为 `BLOCKED`
3. 同一题目连续 2 个批次质检不合格
4. 数值型答案在最终产物中与教材原文不一致
