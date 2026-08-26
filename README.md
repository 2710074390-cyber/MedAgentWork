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
- **五阶段 Agent 管线** — MedGen 出题 → MedQC 质检 → MedFix 修复 → MedReview 成册，门禁强制校验
- **学期切换** — 大三下（完整内容）/ 大四上（敬请期待）
- **访问计数** — 首页统计条实时显示累计访问次数（Cloudflare Pages Function + KV，一次页面打开 +1；站长打开 `?noself=1` 可将自己本机访问设为免计）
- **软件工坊（MedKit）** — 本站产物的桌面生成器下载区（`#software`）
  - GitHub API 动态显示最新版本号与安装包大小，直链下载 + ghproxy 镜像备用
  - 总览台第 4 磁贴 / 导航「软件下载」/ 移动端菜单均可直达
  - 软件仓库：[2710074390-cyber/medkit](https://github.com/2710074390-cyber/medkit)
- 各产物支持：👁️ 预览 / ⬇️ 下载 / 🖨️ 打印

## 📂 目录结构

```
├── index.html              # 导航页（未来主义 · 深海玻璃风格）
└── 大三下/
    ├── 押题卷/             # 5 套交互式答题 HTML
    ├── 题库/               # 6 科 PDF 题库
    └── 复习资料/           # 7 科 MD（4 科含 HTML）
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
