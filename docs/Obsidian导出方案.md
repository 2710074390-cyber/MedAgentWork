# Obsidian Markdown → PDF 导出方案

> 约束：**不使用 HTML 产物**，产物为 `.md`，导入 Obsidian 后导出 PDF。
> 全部结论附实测证据（命令输出 / file:line / 官方文档原文）。

---

## 一、结论先行

**三条硬结论：**

1. **不需要"导入"** —— `C:\Users\38063\Desktop\MedAgentWork` **本身就是 Obsidian vault**（`.obsidian/` 已存在，Obsidian 1.13.7 已装）。要做的只是让产物**落在 vault 可见区域**并符合 Obsidian 的渲染约定。

2. **这条路可行，且控制力比预想的大** —— CSS snippet 确实作用于 PDF 导出（Better Export PDF README 原文："you can add custom CSS in the `Appearance > CSS Snippet`"），因此 `scripts/design-tokens.css` 那套设计语言**可以移植到 Obsidian**，不是"只能听渲染器的"。

3. **但有一个不可绕过的结构性约束** —— `<details>` 属 CommonMark **HTML block 类型 6，结束条件是空行**。这意味着：
   - `<details>` 标签行与**首个空行**之间的 markdown **不解析**；
   - **空行之后**的内容**正常解析**（表格、列表都能渲染）。

   这一条决定了所有修复动作的形状：**要么加空行，要么别用 details**。

**实测门禁结果：`FAIL=9  WARN=66  文件=30`**

---

## 二、现状诊断（实测）

### 2.1 产物形态

| 产物 | 文件 | 体积 | 图片 | details | mermaid | HTML表格 |
|---|---|---|---|---|---|---|
| 贺银成讲义·上册 | `Obsidian产物/讲义上册/`（原在 `_scratch/hyc_compile/out/`） | 2139 KB | 363 张 / 10.6 MB | 67 | 0 | 29 |
| 贺银成讲义·中册 | 同上 | 1471 KB | 116 张 / 5.8 MB | 45 | 0 | 30 |
| 贺银成讲义·下册 | 同上 | 1327 KB | 255 张 / 4.8 MB | 6 | 0 | 13 |
| 贺银成真题·上册 | 同上 | 1022 KB | 14 张 / 1.3 MB | 3 | 0 | 1 |
| 贺银成真题·下册 | 同上 | 2293 KB | 328 张 / 8.1 MB | 46 | 0 | 6 |
| 大三下复习手册 ×7 | `大三下/复习资料/` | 85~226 KB | 0 | 22~51 | 0 | 0 |
| 题库 batch ×5 | `最终产物/batch0xx/` | 160~246 KB | 0 | 0 | 0 | 0 |
| MOC 导航 ×12 | `_MOC/` | <1 KB | 0 | 0 | 0 | 0 |

**图片引用全部是 `![](images/xxx.jpg)` 形态**，无 wikilink / 无 HTML `<img>` / 无绝对路径（已 grep 验证）。
图片文件名带 64 位 hash（`p01_109d89e6...jpg`），**实测在该 vault 内唯一** —— 这一点很关键，见 §5.3。

### 2.2 FAIL 清单（9 项，逐条已复核）

| # | 代码 | 文件 | 问题 | 修法 |
|---|---|---|---|---|
| 1–5 | F5 | hyc 五册 | 被 vault 排除规则 `/_scratch` 命中，**Obsidian 里根本看不见** | 产物移出 `_scratch` |
| 6 | F4 | 中医学_主复习资料.md | `<summary>` 后无空行，10 处答案落进 HTML block | 加空行 |
| 7 | F3 | 内科学_主复习资料.md | 标题 `H1 → H3` 跳跃（L1 `#` 直连 L8 `###`） | 补 `##` 层级 |
| 8 | F4 | 外科学_主复习资料.md | 同上，6 处（L278 起三个列表项不渲染） | 加空行 |
| 9 | F3 | 精神病学_主复习资料.md | 标题 `H2 → H4` 跳跃（L55 `##` 直连 L69 `####`） | 补 `###` 层级 |

### 2.3 WARN 分布（66 项）

| 代码 | 数量 | 含义 |
|---|---|---|
| W1 | 29 | 无 frontmatter —— 无法指定样式，PDF 元数据为空 |
| W7 | 7 | H1 不唯一（真题上册 32 个、下册 33 个 H1） |
| W5 | 6 | details 未加 `open` —— 导出 PDF 为折叠态 |
| W9 | 6 | 未用 callout（Obsidian 原生折叠块） |
| W13 | 5 | details 内表格/代码块被压成单行（MinerU 造成） |
| W4 | 5 | HTML 表格（打印样式难控） |
| W2 | 5 | 单文件 > 512 KB（渲染与导出卡顿） |
| W12 | 2 | 连续空行 > 2 行 |
| W11 | 1 | 依赖文件名兜底解析（重命名即断链） |

---

## 三、实现思路：三层模型

Markdown 路线的视觉控制力集中在三处，**从下往上，越靠上越稳**：

| 层 | 做什么 | 能改什么 | 载体 |
|---|---|---|---|
| **L1 结构层** | 让 md 语义正确 | 标题层级 → 大纲树 / PDF 书签；表格语法 → 能否渲染；图片路径 → 能否显示 | 生成器输出约定 |
| **L2 样式层** | 控制渲染观感 | 字体、字号、行高、粗体、表格样式、分页 | `.obsidian/snippets/*.css` |
| **L3 导出层** | 控制 PDF 物理属性 | 纸张、页边距、页码、书签、合并 | Obsidian 导出对话框 / Better Export PDF |

**关键判断：L1 的收益远大于 L2。**
理由：L2 再怎么调，也救不了"标题全扁"和"图片断链"；而 L1 改对一次，所有导出路径（内置 / 插件 / 未来其他工具）同时受益。

---

## 四、关键步骤

### 步骤 0：把产物移出 `_scratch`（对应 FAIL 1–5）

`app.json` 的 `userIgnoreFilters` 含 `/_scratch`，产物放那里等于对 Obsidian 隐身。

```bash
# 建议落点：vault 根的 Obsidian产物/（本方案已建此目录）
# 已执行；源目录现为 Obsidian产物/_source/（原始整册归档）
mv _scratch/hyc_compile/out/讲义上册 Obsidian产物/
# …其余四册同理
```

> 注意 `app.json` 还排除了 `/docs`、`/scripts`、`/中间产物`、`/最终产物` 等 41 条规则。
> **产物落点必须在排除列表之外**，否则门禁会报 F5。

### 步骤 1：装 CSS snippet

**源文件**（入库、可追溯）：`scripts/obsidian-snippets/medagentwork-print.css`
—— 36 个选择器块 + 2 个 `@media print`，tinycss2 解析零错误。

**安装**（`.obsidian/` 属本地配置、不入库，换机器时需手动装一次）：

```bash
mkdir -p .obsidian/snippets
cp scripts/obsidian-snippets/medagentwork-print.css .obsidian/snippets/
```

然后在 Obsidian 里：`Settings → Appearance → CSS snippets → 点「刷新」→ 打开开关`

**它做了什么：**

| 模块 | 内容 |
|---|---|
| 中文排版基线 | 字体栈回落链、行高 1.75、行宽 42em |
| **粗体补偿** | `--bold-modifier: 200` —— 中文无真粗体字重，Chromium 合成加粗偏弱 |
| 标题层级 | h1~h6 字号 1.7/1.42/1.22/1.08/1/0.94 em，上间距 1.8em 归拢到下方正文 |
| 表格 | 边框、表头底色、斑马纹、行高 1.55 |
| 打印字体 | `--font-print-override` 切衬线体（宋体系，省墨更像教材） |
| **分页控制** | `break-before/after/inside`、`orphans/widows: 3`、`thead` 跨页重复 |
| 折叠块展开 | `details::details-content { content-visibility: visible }` |
| 按需变体 | `cssclasses: [mgw-book]` 章节强制分页 / `[mgw-handout]` 紧凑排版 |

### 步骤 2：改生成器的 4 条输出约定（对应 F3/F4/W1/W5/W7）

这是**唯一能根治问题的地方**。建议写进 `compile_hyc.py` 与 Agent 5 的输出规范：

**约定 1 —— 每篇必有 frontmatter**

```yaml
---
title: 内科学 高效复习手册
author: MedAgentWork
cssclasses: [mgw-handout]
---
```

作用：`cssclasses` 决定套哪套样式；`title`/`author` 进 PDF 元数据（Better Export PDF 支持从 front matter 读 PDF metadata）。

**约定 2 —— 单一 H1 + 不跳级**

- 一篇文档**只有一个 H1**（当前真题上册有 32 个）
- 层级只允许 ±1（当前有 `H1→H3`、`H2→H4`）
- 真题册的"每套试卷"应从 H1 降为 **H2**，H1 留给书名

**约定 3 —— 折叠块三选一**

| 方案 | 写法 | 适用 |
|---|---|---|
| **首选：callout** | `> [!note]- 点击展开`<br>`> 内容（markdown 完全支持）` | 复习手册答案块 |
| 次选：details + 空行 + open | `<details open>`<br>`<summary>标题</summary>`<br>**空行**<br>内容 | 需与 GitHub 兼容时 |
| 不用 | `<details>` 无空行无 open | ❌ 当前外科学/中医学的写法 |

**约定 4 —— 图片与 md 同级**

产物结构保持 `讲义上册/讲义上册.md` + `讲义上册/images/`，**不要拆散**。
理由见 §5.3。

### 步骤 3：配置导出

**当前 vault 的导出配置**（`.obsidian/app.json`）：

```json
"pdfExportSettings": { "pageSize": "Letter", "margin": "0", "downscalePercent": 100 }
```

| 项 | 当前 | 处置 | 原因 |
|---|---|---|---|
| `pageSize` | `Letter` | **改为 `"A4"`** | Letter 是美制 8.5×11 in；中文教材用 A4（210×297 mm） |
| `margin` | `"0"` | **保持不变** | `"0"` 就是 `Default`，当前值已正确 |

**`margin` 合法取值的证据**（从 `obsidian-1.13.7.asar` 提取，非推测）：

```js
addOption("0", settingMarginDefault()).addOption("2", settingMarginMinimal()).addOption("1", settingMarginNone())
```

→ 只有三个值：**`"0"` = Default / `"1"` = None / `"2"` = Minimal**。
同处代码还有 `i.marginsType = parseInt(n.margin); 1 !== i.marginsType && 2 !== i.marginsType || (i.margins = {top:0,left:0,bottom:0,right:0})`
—— 只有 None 与 Minimal 才把边距压成 0，Default 走默认边距。

**`pageSize` 合法值**（同处 asar 代码）：`A3` / `A4` / `A5` / …（字符串即 `"A4"`）。

> **修正记录**：本方案早期版本把 `margin: "0"` 误读为「无边距」，并建议改成 `"40"`。
> 从 asar 拿到真实枚举后确认 —— `"0"` 是 `Default`，**无需改动**。
> 这是本方案唯一一处需要自我纠正的配置结论，教训是**配置项语义必须从程序里挖，不能靠类型定义猜**。

**两条导出路径：**

| 路径 | 能力 | 代价 |
|---|---|---|
| **内置导出**（右键 → Export to PDF） | 应用主题与 snippet；无页码、无书签、无合并 | 零依赖，开箱可用 |
| **Better Export PDF**（你活跃 vault 已装，本 vault 未装） | 页码、书签大纲、自定义页边距、frontmatter 元数据、**多文件合并为一个 PDF**、导出预览 | 需装插件 |

**推荐：给本 vault 也装 Better Export PDF。**
核心理由：**页码 + 书签**。讲义动辄上百页，没有书签导航的 PDF 对学生几乎不可用；内置导出没有这两项能力。
（该 vault 的 `community-plugins.json` 只有 `image-link-updater` 与 `absolute-image-transfer` 两个图片插件。）

### 步骤 4：验证

```bash
# 门禁（本方案交付）
python scripts/check_obsidian.py --all          # 全量
python scripts/check_obsidian.py --all --strict # WARN 也计入退出码
python scripts/check_obsidian.py --all --json reports/obsidian_check.json

# 证伪测试（验证门禁自己没坏）
python _scratch/test_check_obsidian.py
```

再用 `Obsidian产物/Obsidian导出验证样章.md` 做**肉眼验收**（见 §6.2）。

---

## 五、限制与注意事项

### 5.1 Obsidian 不是宽松的 CommonMark 实现

| 限制 | 证据 | 影响 |
|---|---|---|
| HTML block 内的 markdown 不解析 | CommonMark HTML block 类型 6；markdown-it 实测 | `<details>` 内容可能变成纯文本 |
| HTML block 以**空行**为界 | markdown-it-py 4.2.0 实测（见下表） | 空行是"开关" |
| `details` 折叠状态无法用 CSS 改变 | HTML 规范：折叠是浏览器内部机制 | 必须在 md 侧写 `open` |
| 链接解析依赖 vault 索引 | `getFirstLinkpathDest` 行为 | 断链不报错，只显示空 |

**实测验证**（`_scratch/verify_details_render.py`，markdown-it-py 4.2.0）：

| 用例 | 渲染出 `<table>` | 结论 |
|---|---|---|
| `<details open>` + `<summary>` + **空行** + 表格 | **True** | 空行后正常解析 |
| `<details><summary>` + 无空行 + 列表 | False | 整体是 HTML block |
| 表格被压成单行 | False | 输出 `<p>\| a \| b \|...</p>`，**内容没丢但不成表格** |
| `<summary>**粗体**</summary>` | False | 标签行内 markdown 不解析 |

### 5.2 `@media print` 的作用范围

- **已确认**：Better Export PDF 应用 snippet（README 原文 + 提交记录 "Fix `@media print` extraction"）
- **待实测**：内置导出是否同样应用。原理上应该会（同为 Chromium `printToPDF` 渲染 reading view，且 Obsidian 提供了 `--font-print-override` 这个专为打印设计的变量），但**建议用样章实测确认**，不要假定。

### 5.3 图片路径：本项目"恰好"安全，但有前提

引用形态 `![](images/xxx.jpg)`，相对 md 所在目录。在 vault 中的解析顺序：

1. vault 根相对 → `images/xxx.jpg` ❌ 不存在
2. **md 同级相对 → `_scratch/.../讲义上册/images/xxx.jpg`** ✅ 命中
3. 文件名全局兜底 → 唯一命中 ✅

**能工作的原因**：hyc 产物引用的 **1076 个图片名在该 vault 内均唯一**（实测：重名 0 处 / 索引缺失 0 处）。
> vault 整体并非无重名：5708 个图片文件只有 4256 个唯一名（1273 组重名）。
> 但重名来自 `知识库素材/**/_mineru_raw/` 与正式目录的**同一文件副本**，内容一致，即使命中也无害。
**风险**：一旦出现同名文件，解析退化为"歧义"（F2）。且第 2 步依赖 **md 与 images/ 保持同级**。

> 这也解释了 vault 里为什么装着 `image-link-updater` 和 `absolute-image-transfer` —— 图片链接问题你之前已经踩过。

### 5.4 单文件体积是硬约束

- 讲义上册 2139 KB / 32726 行，**远超** 512 KB 阈值
- Obsidian 阅读视图会明显卡顿；导出 PDF 需把 10.6 MB 图片内联，耗时与内存都上去了
- **建议按章拆分**：一册拆成 5~10 个 md，再用 Better Export PDF 的 `toc: true` 目录笔记合并导出

### 5.5 中文专属问题

| 问题 | 解药 |
|---|---|
| 粗体发虚（无真粗体字重） | `--bold-modifier: 200`（Obsidian 1.6+ 官方变量） |
| 论坛有报告 PDF 丢中文字符（需强制 CJK 字体） | `--font-print-override` 显式指定中文字体栈 |
| 中文需更大行距 | 行高 1.75（西文 1.5 不够） |
| 中文一行字数过多伤眼 | 行宽 42em（约 35~45 汉字） |

### 5.6 MinerU 造成的既成事实

hyc 产物里 **W13 共 5 处**：MinerU 把图表源码压成单行（用 ` ／ ` 代替换行），导致：

- 表格源码 `| a | b | ／ | --- | --- |` → 渲染成一段含管道符的文本
- mermaid 源码 ` ```mermaid ／ graph TD ／ ... ／ ``` ` → 渲染成文本

**这些内容不会丢**（实测输出 `<p>...</p>`），但**不可能渲染成表格/图**。
修法只能回到 MinerU 源数据层（任务一已记录，属遗留项）。

---

## 六、如何保证正常渲染并成功导出

### 6.1 门禁（自动化）

`scripts/check_obsidian.py` —— 与 `check_visual.py` 同风格，FAIL 为结构性缺陷，WARN 为体验风险。

| 代码 | 级别 | 检查内容 |
|---|---|---|
| F1 / F2 | FAIL | 图片断链 / 链接歧义 |
| F3 | FAIL | 标题层级跳跃 > 1 |
| F4 | FAIL | details 标签行与首个空行之间含 markdown |
| F5 | FAIL | 被 vault 排除规则命中 |
| W1–W13 | WARN | frontmatter / 体积 / 图片总量 / HTML表格 / details 未 open / `<br>` / mermaid 样式 / callout / 远程图 / 文件名兜底 / 连续空行 / 压成单行 |

**门禁自身的可靠性**：`_scratch/test_check_obsidian.py` 共 **20 项证伪测试**，覆盖
mask 边界、HTML block 边界、图片解析、排除规则 —— 全部通过。

### 6.2 样章肉眼验收（`Obsidian产物/Obsidian导出验证样章.md`）

一个文件覆盖 9 类结构。打开后逐项对照：

| 验证项 | 期望 |
|---|---|
| 中文粗体 | 明显变重 |
| 表格 | 边框 + 表头底色 + 斑马纹 |
| 30 行长表格 | 跨页后表头重复 |
| callout | 彩色块，内部 markdown 正常 |
| details（无 open） | 折叠 |
| details（有 open） | 展开 |
| mermaid | 渲染成流程图 |
| 图片语法 A（`![[hash名]]`） | 显示 |
| 图片语法 B（跨目录相对路径） | 破图（**预期**，用于证明路径规则） |
| 第二个 H1 | 另起一页（`cssclasses: [mgw-book]`） |

### 6.3 导出前检查清单

- [ ] `check_obsidian.py --all` 无 FAIL
- [ ] snippet 已启用（Settings → Appearance → CSS snippets 开关为开）
- [ ] 导出对话框纸张 = **A4**，页边距 = `Default`（**不要选 `None`**）
- [ ] 打开导出预览（Better Export PDF）确认分页位置
- [ ] 抽查 3 处：一个长表格跨页、一处 mermaid、一处图片

---

## 七、执行结果（2026-09-21 全部落地）

| # | 决策项 | 结果 |
|---|---|---|
| 1 | hyc 五册移出 `_scratch` | ✅ 五册移入 `Obsidian产物/`；原始整册归档到 `Obsidian产物/_source/` |
| 2 | 装 Better Export PDF | ✅ v2.0.3 已装（`main.js` / `manifest.json` / `styles.css`），已注册进 `community-plugins.json` |
| 3 | 改导出配置 | ✅ `pageSize` → `A4`；`margin` 经 asar 取证确认为 `Default`，**保持不变** |
| 4 | 按章拆分 | ✅ 236 个分册（讲义按 H2 / 真题按 H1） |
| 5 | 落实 4 条输出约定 | ✅ 377 处 details → callout；全部加 frontmatter；标题归一 |
| 6 | details 默认展开 | ✅ 转为 callout `[!type]+`（`+` 即默认展开） |

### 7.1 执行后的门禁结果

```
FAIL=0  WARN=56  文件=249     ✅ 门禁通过
```

WARN 构成：**W4 ×53**（HTML 表格，任务一「含合并单元格则保 HTML」的既定取舍，已在 snippet 里用
`table:not(:has(thead)) { break-inside: avoid }` 兜住打印断页）+ 样章里 3 项**故意设计**的验证项
（W11 文件名兜底 / W7 两个 H1 / W5 未加 open）。

### 7.2 分册规模

| 册 | 分册数 | 拆分依据 | images |
|---|---|---|---|
| 讲义上册 | 57 | H2（章） | 898 |
| 讲义中册 | 43 | H2 | 621 |
| 讲义下册 | 76 | H2 | 543 |
| 真题上册 | 32 | H1（每年一套） | 16 |
| 真题下册 | 33 | H1 | 412 |
| 复习手册 ×7 | 7 | 不拆分 | 0 |

`.gitignore` 已加规则：分册 md 入库（纯文本），`Obsidian产物/**/images/` 与 `_source/` 不入库
（实测 249 个 md 待入库 / 2495 个图片与归档被忽略）。

### 7.3 仍需手动完成的两步

1. **在 Obsidian 里启用**：`Settings → Community plugins` 打开开关（受限模式信任必须由人确认），
   再 `Settings → Appearance → CSS snippets` 打开 `medagentwork-print` 开关。
2. **导出时扫一眼纸张是否为 A4**（配置已写入，但对话框显示的是当前值）。
| 6 | details 存量（168 处）处置：转 callout / 加空行+open / 保持原样 | hyc 的 details 是图注备份，影响小于复习手册 |

---

## 附：交付物清单

| 文件 | 作用 |
|---|---|
| `scripts/obsidian-snippets/medagentwork-print.css` | CSS snippet **源文件**（入库）；安装时复制到 `.obsidian/snippets/` |
| `scripts/check_obsidian.py` | 渲染/导出兼容性门禁 |
| `scripts/prepare_obsidian.py` | **转换器**：落实 4 条输出约定 + 按章拆分 + 生成 toc 目录笔记 |
| `Obsidian产物/<册>/` | 236 个分册 md + 各自的 `images/`（与 md 同级，保证链接可解析） |
| `Obsidian产物/_source/` | 原始整册 md 归档（供回溯；不入库） |
| `Obsidian产物/Obsidian导出验证样章.md` | 肉眼验收样章（9 类结构） |
| `.obsidian/plugins/better-export-pdf/` | 插件 v2.0.3（页码 / 书签 / 合并 / 导出预览） |
| `_scratch/test_check_obsidian.py` | 门禁的 20 项证伪测试 |
| `_scratch/verify_details_render.py` | HTML block 边界假设的验证脚本 |
| `reports/obsidian_check.json` | 本次全量门禁结果 |
| `docs/Obsidian导出方案.md` | 本文档 |

**转换器用法**（幂等，可重复运行；`--dry-run` 无副作用）：

```bash
python scripts/prepare_obsidian.py --all               # 五册 + 七手册
python scripts/prepare_obsidian.py --books 讲义         # 只处理讲义
python scripts/prepare_obsidian.py --handouts          # 只处理复习手册
python scripts/prepare_obsidian.py --src a.md --out-dir out --title "书名" --split-level 2
```
