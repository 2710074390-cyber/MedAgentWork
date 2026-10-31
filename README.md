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
