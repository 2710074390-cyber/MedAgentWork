# MedAgentWork · 医学复习资料库

> 大三下 · 大四上 · 押题卷 + 题库 + 复习手册

## 🌐 在线访问

**Cloudflare Pages**（国内可直连）：https://med-review-site.pages.dev

**本地一键部署**（与 CI 同环境，从干净 git 树部署，规避本地大文件超限）：

```
powershell scripts\deploy_site.ps1
```

## ✨ 特性

- **未来主义设计** — 黑蓝深海配色 · 玻璃拟态 UI · ASCII 原子像素星域（粒子特效可开关，localStorage 记忆）
- **58 秒品牌介绍片** — 首屏右栏终端的第 3 个 Tab（默认展示）：封面先行、点击才加载视频，进剧场全屏播放（详见下节）
- **三支科普短片** — 幕后管线三张卡各挂一支 38–42 秒短片（管线 / 质量门禁 / 学科 RAG），点「了解更多」丝滑过渡进剧场，可一键换片（详见下节）
- **五阶段 Agent 管线** — MedGen 出题 → MedQC 质检 → MedFix 修复 → MedReview 成册，门禁强制校验
- **三视图导航** — 主页（介绍与软件下载）/ 大三下（押题卷 · 题库 · 复习手册）/ 大四上（5 科教学版资料 PDF）
- **访问计数** — 首页统计条实时显示累计访问次数（Cloudflare Pages Function + KV，一次页面打开 +1；站长打开 `?noself=1` 可将自己本机访问设为免计）
- **软件工坊（MedKit）** — 本站产物的桌面生成器下载区（`#software`）
  - GitHub API 动态显示最新版本号与安装包大小，直链下载 + ghproxy 镜像备用
  - 总览台第 4 磁贴 / 导航「软件下载」/ 移动端菜单均可直达
  - 软件仓库：[2710074390-cyber/medkit](https://github.com/2710074390-cyber/medkit)
- 各产物支持：👁️ 预览 / ⬇️ 下载 / 🖨️ 打印

## 🎬 首屏介绍片（2026-10-19）

首屏右栏终端新增第三个 Tab「介绍片」（默认停留），点封面进入铺满视口的深色剧场。58 秒七幕：品牌开场 → 备考命题 → 网页刷题 → 复习手册 → 幕后管线 → 规则与演进 → 收束。其中「规则与演进」独占 15 秒（32.5s–47.5s），分两拍讲清「质量为什么高」：

主张是「不赌模型零失误，只赌管线兜得住」——模型仍有概率出错，靠 Harness 收住自由度、靠管线兜住结果：

- **A 拍 · 规则（4条）**：R1 先管线后模型（五阶段固定输入输出，模型只填其中一段）/ R2 Harness 收口（结构、格式、判分口径由代码校验，不靠模型自觉）/ R3 引用可查（页码反查 + GoldenSet 交叉验证，来源不合格即 FAIL）/ R4 每步可回放（中间产物、批次状态与日志留痕，错了能定位）
- **B 拍 · 演进（5 节点）**：V1.0 技能包首发 → V2.x 契约化重构（阶段输入输出写成 schema，摄入即校验）→ HC-18 真题锚定（每批约 1/5 考研原题，逐条比对一致性）→ GATE 发布门禁（断链、来源不合格直接拒绝部署）→ V5.1（7 科 1,848 题；批次 039 的 199 题主动撤回，待并集后再发）
- **证据条**：每批约 1/5 考研原题 · GoldenSet 9,616 条比对；页码反查 · 断链与不合格来源一律拒绝部署；90 项测试 + 门禁 · 全绿才发布
- **收束句**：不是让模型更准，是让错误出不来。

- **封面先行**：只加载封面图（WebP 约 50–60KB，JPEG 兜底）；`<video>` 无 `src`、`preload="none"`，首次点击封面才注入地址并 `load()`——首屏零视频流量（Playwright 实测：点击前 MP4 请求数 0）。
- **双画幅**：桌面 1920×1080（16:9），移动 1080×1350（4:5）；按 600px 断点选择。终端面板内封面固定 16:9，避免移动端卡片过高。
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


## 🎞️ 科普短片（2026-10-19 上线 / 2026-10-31 下架）

> **已下架**：`pipeline`（五阶段管线）/ `gate`（质量门禁）/ `rag`（个性化学科 RAG）三支短片已从站点撤下，`assets/shorts/` 下 18 个文件（6 支 MP4 + 12 张封面，合计 12.97MB）同时从仓库删除；播放器注册表只保留首屏介绍片，幕后三张能力卡保留文字说明、不再带播放入口。需要复播时从 git 历史取回删除前的提交即可（下架前 HEAD：`9120ef0`）。以下内容保留为制作备忘。

首屏介绍片回答「这是什么、为什么可信」；三支短片回答「具体怎么做的、踩过什么坑」。每支 38–42 秒，双画幅各 2–3MB，点击才加载。**文案里的规则、编号、事故全部来自项目真实记录**（`操作流程.txt`、`docs/TODO.md`、`docs/交接文档_新Agent接手_v1.0.md`、`scripts/validate/rules_*.py`、`scripts/fact_check.py`），不编造。

| 短片 | 时长 | 讲什么 | 出现的真实细节 |
|---|---|---|---|
| `pipeline` 五阶段管线 | 40s | 为什么不让一个模型一口气写完；契约先行、状态机、BLOCKED 就地回退 | MedMaster/MedGen/MedQC/MedFix/MedReview 五角色、jsonschema 摄入即校验、原子写与血缘、HALT |
| `gate` 质量门禁 | 42s | 让模型检查自己靠不靠谱；机械规则 + 事实反查 + 不达标不发布 | R2 正确选项显著更长、R6 数值区分度、R9 数值缺单位、R10/R11 NBME 线索、GoldenSet 9,616 条、批次 039 撤回 199 题 |
| `rag` 个性化学科 RAG | 38s | 23 个学科不能用同一套检索；逐科分块、混合检索、成本降级 | 方剂组成不切碎、向量+关键词+rerank、batch027 余额不足 402、`--no-rerank` 降级、`calibrated_p` 是先验不是实测 |

- **入口（下架前）**：幕后管线三张能力卡右下角的「看短片」胶囊按钮；现仅保留三张卡的文字说明。
- **过渡**：点击后卡片先 `scale(1.035)` 推近并淡出，剧场同时从 `translateY(8px) scale(1.03)` 收到原位（0.46s `cubic-bezier(.16,1,.3,1)`），读起来是同一块画面在放大；`prefers-reduced-motion` 下全部关掉。
- **换片（下架前）**：结束卡下方列出另两支，点击时先黑场 260ms 再切源，避免画面硬跳；左上角常驻徽标显示当前片名与时长。注册表现只剩 `intro`，换片条已停用。
- **懒加载**：`<video>` 无 src、`preload=none`，首屏与滚动到该栏目都不会产生任何 MP4 请求（Playwright 实测：点击前 0）。

历史产物（`assets/shorts/`，已随下架删除）：

| 文件 | 规格 | 体积 |
|---|---|---|
| `{pipeline,gate,rag}-16x9.mp4` | 1920×1080 · H.264 High · AAC 96k | 2.3–2.6 MB |
| `{pipeline,gate,rag}-4x5.mp4` | 1080×1350 · 同上 | 2.2–2.5 MB |
| `poster-{film}-{16x9,4x5}.webp/.jpg` | 封面（4.2s 定格） | 20–80 KB |

工程 `tools/short-film/`（与主片同一套方法：`window.__seek(ms)` 可定位时间轴 → Playwright 逐帧 30fps → ffmpeg 编码；`audio.html` 合成音轨）：

```bash
python tools/short-film/render.py --film all --format both
python tools/short-film/render.py --film gate --format wide      # 只渲一支
python tools/short-film/render.py --skip-frames --no-audio       # 只重新编码
```

文案与分镜：`tools/short-film/SCRIPT.md`（改文案只改这里，渲染前先跑 `_chk.py` 看排版是否溢出）。

## 📂 目录结构

```
├── index.html              # 导航页（未来主义 · 深海玻璃风格）
├── 大三下/
│   ├── 押题卷/             # 5 套交互式答题 HTML
│   ├── 题库/               # 6 科 PDF 题库
│   └── 复习资料/           # 7 科 MD（4 科含 HTML）
└── 大四上/
    └── 复习资料/           # 8 科教学版资料 PDF（内科学合订本 · 外科学二 · 急诊与灾难医学 · 耳鼻咽喉头颈外科学 · 妇产科学 · 传染病学 · 口腔科学 · 眼科学）
                            #   急诊另有教师重点版、妇产科另有深度版
```

## 🔒 隐私

- ✅ 纯静态 + 单个 Pages Function（访问计数），无第三方脚本
- ✅ 除访问计数与 MedKit 版本查询（GitHub 公开 API）外无任何外部请求
- ✅ 仅记录累计访问次数（Cloudflare KV），**不采集任何个人信息 / IP / 位置**
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
