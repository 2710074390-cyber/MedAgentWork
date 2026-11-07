# MedAgentWork · 医学复习资料库

> 大三下 · 大四上 ｜ 在线刷题 + 题库 PDF + 复习手册 + 教师重点蓝图版 + Obsidian 笔记库

## 🌐 在线访问

**Cloudflare Pages**（国内可直连）：https://med-review-site.pages.dev

| 入口 | 地址 | 说明 |
|---|---|---|
| 资料主页 | https://med-review-site.pages.dev | 三视图浏览 · 预览 / 下载 / 打印 |
| 网页刷题 | `/drill` | 站点导航「开始刷题」与全站常驻悬浮按钮；302 跳转到刷题 SPA 入口页，之后浏览器直连源站 |

**本地一键部署**（与 CI 同环境，从干净 git 树部署，规避本地大文件超限）：

```
powershell scripts\deploy_site.ps1
```

## ✨ 特性

- **未来主义设计** — 黑蓝深海配色 · 玻璃拟态 UI · ASCII 原子像素星域（粒子特效可开关，localStorage 记忆）
- **58 秒品牌介绍片** — 首屏介绍片封面卡（默认展示）：封面先行、点击才加载视频，进剧场全屏播放（详见下节）
- **五阶段 Agent 管线** — MedMaster 编排 → MedGen 出题 → MedQC 质检 → MedFix 修复 → MedReview 成册；阶段转换由门禁强制校验，产物与门禁回执字节绑定
- **跨宿主（DSH / WorkBuddy / Trae / 人工）** — 规则真源 `.dsh/skills/`，三宿主入口由 `scripts/host_bootstrap.py` 生成路由桩；`scripts/batch_driver.py` 是门禁唯一执行面，并在 PASS 后生成宿主无关的交接包 `中间产物/{batch}/_handoff/{stage}.json`。宿主能力由桩的 `level=` 声明（L2 隔离子代理 / L1 单会话 / L0 人工接力），三档消费同一份包、产出同一份字节证据（见 `AGENTS.md §3.5`）。
- **三视图导航** — 主页（介绍与 MedKit 下载）/ 大三下 / 大四上：
  - **大三下** — 5 套交互式押题卷 HTML · 6 科题库 PDF · 7 科复习手册 MD（中医 / 中医心理 / 外科 / 精神 4 科另含 HTML）
  - **大四上** — 复习资料 11 份 PDF：8 科教学版（内科学为 23 模块合订本）+ 妇产科深度版 + 急诊与耳鼻咽喉教师重点蓝图版；题库与押题 12 项（含教师重点版题库、耳鼻咽喉真题专项）
- **网页刷题** — 导航「开始刷题」+ 全站左下角常驻悬浮按钮直达 `/drill`，无需安装
- **概念图谱** — 题库题目挂到稳定考点 ID（K-*），支持概念卡、前置关系与掌握度统计（见 `question_bank/concept_graph.json`）
- **Obsidian 笔记库** — `Obsidian产物/` 300+ 篇 Markdown：复习手册 / 教师重点蓝图版 / 概念卡 / 概念索引 / 专项练习 / 真题与讲义；PDF 由笔记人工导出
- **访问计数** — 首页统计条实时显示累计访问次数（Cloudflare Pages Function + KV，一次页面打开 +1；站长打开 `?noself=1` 可将自己本机访问设为免计）
- **软件工坊（MedKit）** — 本站产物的桌面生成器下载区（`#software`，导航「MedKit」）
  - GitHub API 动态显示最新版本号与安装包大小，直链下载 + ghproxy 镜像备用
  - 主页总览台磁贴 / 导航「MedKit」/ 移动端菜单均可直达
  - 软件仓库：[2710074390-cyber/medkit](https://github.com/2710074390-cyber/medkit)
- 各产物支持：👁️ 预览 / ⬇️ 下载 / 🖨️ 打印

## 📊 当前状态（2026-11-06）

数字均可核对，改数请改源头而非本文：

| 指标 | 数值 | 源头 |
|---|---|---|
| 题库注册表累计 | 6,640 题 | `question_bank/registry_meta.json` |
| 考研真题锚定集 | 9,616 条 | `GoldenSet/structured/*.json` |
| 批次 | 交付 batch031–batch048（batch046 / 047 已归档，最新 batch048） | `最终产物/` · `archive/` |
| 自动化测试 | 43 个测试文件 · 461 项用例 | `python scripts/run_tests.py` |
| Obsidian 笔记 | 308 篇 Markdown | `Obsidian产物/` |

## 🎬 首屏介绍片（2026-10-19 定格）

首屏介绍片封面卡，点封面进入铺满视口的深色剧场。58 秒七幕：品牌开场 → 备考命题 → 网页刷题 → 复习手册 → 幕后管线 → 规则与演进 → 收束。其中「规则与演进」独占 15 秒（32.5s–47.5s），分两拍讲清「质量为什么高」：

主张是「不赌模型零失误，只赌管线兜得住」——模型仍有概率出错，靠 Harness 收住自由度、靠管线兜住结果：

- **A 拍 · 规则（4条）**：R1 先管线后模型（五阶段固定输入输出，模型只填其中一段）/ R2 Harness 收口（结构、格式、判分口径由代码校验，不靠模型自觉）/ R3 引用可查（页码反查 + GoldenSet 交叉验证，来源不合格即 FAIL）/ R4 每步可回放（中间产物、批次状态与日志留痕，错了能定位）
- **B 拍 · 演进（5 节点）**：V1.0 技能包首发 → V2.x 契约化重构（阶段输入输出写成 schema，摄入即校验）→ HC-18 真题锚定（每批约 1/5 考研原题，逐条比对一致性）→ GATE 发布门禁（断链、来源不合格直接拒绝部署）→ V5.1（视频口径：7 科 1,848 题）
- **证据条**：每批约 1/5 考研原题 · GoldenSet 9,616 条比对；页码反查 · 断链与不合格来源一律拒绝部署；90 项测试 + 门禁 · 全绿才发布
- **收束句**：不是让模型更准，是让错误出不来。

> 视频为 2026-10-19 定格产物，其中的版本号、题量与测试项数（V5.1 · 7 科 1,848 题 · 90 项测试）都是拍摄时口径，此后管线与批次仍在推进。当前实际规模见上节「📊 当前状态」。

影片交互：

- **封面先行**：只加载封面图（WebP 约 50–60KB，JPEG 兜底）；`<video>` 无 `src`、`preload="none"`，首次点击封面才注入地址并 `load()`——首屏零视频流量（Playwright 实测：点击前 MP4 请求数 0）。
- **双画幅**：桌面 1920×1080（16:9），移动 1080×1350（4:5）；按 600px 断点选择。封面卡内固定 16:9，避免移动端卡片过高。
- **剧场播放**：播放/暂停、进度拖动、静音、全屏、键盘（空格/K 播放暂停、←/→ ±5s、M 静音、F 全屏、Esc 关闭）、点遮罩关闭、切后台自动暂停、焦点陷阱与关闭后焦点归位。
- **结束状态**：播放完毕显示「现在，开始刷题」结束卡（再看一遍 / 去网页刷题）；封面角标改为「已看完 · 点击重看」。
- **移动优先**：控制按钮 44×44 触控目标；`prefers-reduced-motion` 下关闭封面脉冲与位移动画。

产物（`assets/intro/`）：

| 文件 | 规格 | 体积 |
|---|---|---|
| `medagentwork-intro-16x9.mp4` | 1920×1080 · H.264 High · AAC 112k · 58s | ≈ 7.8 MB |
| `medagentwork-intro-4x5.mp4` | 1080×1350 · 同上 | ≈ 6.8 MB |
| `poster-16x9.webp/.jpg`、`poster-4x5.webp/.jpg` | 封面（首帧 4.9s 定格） | 50–150 KB |

重新生成（需 Playwright + ffmpeg，见 `requirements-dev.txt`）：

```bash
python tools/intro-film/render.py --format both

# 只重渲某一段（改某一幕后）：--start/--end 指定帧区间
python tools/intro-film/render.py --format both --frames-only --start 960 --end 1425
# 只重新编码（复用已渲染的帧）
python tools/intro-film/render.py --format both --skip-frames
```

- `tools/intro-film/index.html` 是一条**可定位时间轴**：`window.__seek(ms)` 可在任意时刻复现同一帧；Playwright 逐帧截图（30fps）后交 ffmpeg 编码，因此转场/动效完全可复现。
- `tools/intro-film/audio.html` 用 OfflineAudioContext 合成 58s 氛围音轨（低频铺底 + 和弦垫 + 转场铃 + 收束冲击），不依赖任何外部素材。
- 发布：CI 与 `scripts/deploy_site.ps1` 的白名单已加入 `assets`；`_headers` 对 `/assets/intro/*` 设 7 天缓存。

## 📂 目录结构

```
├── index.html              # 单页站点（三视图 · 未来主义深海玻璃风格）
├── 大三下/
│   ├── 押题卷/             # 5 套交互式答题 HTML
│   ├── 题库/               # 6 科题库 PDF
│   └── 复习资料/           # 7 科主复习资料 MD（4 科另含 HTML）
├── 大四上/
│   ├── 押题卷/             # 2 份押题卷 MD（急诊 · 耳鼻咽喉，各 100 题）
│   ├── 题库/               # 教学题库 PDF + 教师重点版题库 + 真题专项 + 新版押题卷
│   └── 复习资料/           # 11 份 PDF：8 科教学版（内科学合订本）+ 妇产深度版 + 急诊/耳鼻咽喉教师重点蓝图版
├── Obsidian产物/           # Obsidian 笔记库（复习手册 / 教师重点蓝图版 / 概念卡 / 概念索引 / 专项练习 / 真题与讲义）
├── 最终产物/               # 各批次交付 JSON + 门禁回执
├── 中间产物/               # 批次暂存（生成分片 / 质检报告 / 追溯日志）
├── question_bank/          # 题库注册表 · 概念图与标签 · 难度标定
├── GoldenSet/              # 考研真题锚定集（9,616 条）+ 回归与校验脚本
├── scripts/                # 管线 · 门禁 · 导出 · 部署脚本
├── functions/              # Pages Functions：/api/visits（计数）· /drill（刷题跳转）
├── assets/                 # 介绍片视频与封面、小红书配图
└── tools/intro-film/       # 介绍片渲染工程（可定位时间轴 + 逐帧截图）
```

## 🧪 质量与门禁

门禁不是纪律要求，是脚本判定：

```bash
python scripts/run_tests.py                                    # 测试套件
python scripts/batch_driver.py check --batch batchNNN --stage auto   # 阶段门禁唯一入口
python scripts/gate_verify.py  --batch batchNNN --stage a3 --quiet   # 消费上游前验回执
python scripts/gate_audit.py --staged --require-tracked             # 提交前查证据完整性
```

- 门禁只能通过 `batch_driver.py` 执行；产物必须与一次门禁执行字节绑定（`gate_stamp` 回执链）。
- 消费上游前先验上游回执，缺失即 `BLOCKED`；跳过门禁无法绕过下游校验。
- 批次签收要求 A/B 级证据 + 四门禁通过，C 级高风险题一律隔离。

## 🔒 隐私

- ✅ 纯静态 + 两个 Pages Function（访问计数、刷题跳转），无第三方脚本
- ✅ 除访问计数与 MedKit 版本查询（GitHub 公开 API）外无任何外部请求
- ✅ 仅记录累计访问次数（Cloudflare KV），**不采集任何个人信息 / IP / 位置**
- ⚠️ `/drill` 为外部刷题应用的跳转入口，该应用由第三方托管平台承载（自带 sharecode 校验），离开本站后的数据处理遵循其自身规则
- ✅ `.wrangler/` 缓存已加入 .gitignore

## 👥 贡献者

复习资料与题库由多 Agent 系统辅助生产，感谢以下大模型服务提供方：

<a href="https://github.com/deepseek-ai" title="深度求索 DeepSeek"><img src="https://avatars.githubusercontent.com/deepseek-ai?s=72&v=4" width="64" height="64" alt="深度求索 DeepSeek"/></a>
<a href="https://github.com/zhipuai" title="智谱 AI · GLM"><img src="https://avatars.githubusercontent.com/zhipuai?s=72&v=4" width="64" height="64" alt="智谱 AI · GLM"/></a>
<a href="https://github.com/QwenLM" title="通义千问 Qwen"><img src="https://avatars.githubusercontent.com/QwenLM?s=72&v=4" width="64" height="64" alt="通义千问 Qwen"/></a>

- **深度求索（DeepSeek）** — [deepseek.com](https://www.deepseek.com)
- **智谱 AI（GLM）** — [zhipuai.cn](https://www.zhipuai.cn)
- **通义千问（Qwen · 阿里云）** — [tongyi.aliyun.com](https://tongyi.aliyun.com)

---

**仅供学习交流使用**
