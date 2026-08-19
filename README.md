# MedAgentWork · 医学复习资料库

> 大三下 · 大四上 · 押题卷 + 题库 + 复习手册

## 🌐 在线访问

**Cloudflare Pages**（国内可直连）：https://med-review-site.pages.dev

## ✨ 特性

- **三主题切换**（右上角 ●●●，localStorage 记忆）
  - 古典 · 羊皮纸 + 墨绿/赭红 + 宋体（默认）
  - 现代 · 纯白 + 医蓝 + 无衬线
  - 暗夜 · 深炭 + 青绿/琥珀（护眼）
- **打印继承主题** — 复习手册打印时继承当前主题配色
- **学期切换** — 大三下（完整内容）/ 大四上（敬请期待）
- 各产物支持：👁️ 预览 / ⬇️ 下载 / 🖨️ 打印

## 📂 目录结构

> 本仓库**仅存放资料与题库数据**，项目代码（5-Agent 管线、质量门禁、测试）见 [MedAgentWork-Public](https://github.com/2710074390-cyber/MedAgentWork-Public)。

```
├── index.html              # 导航页（三主题 + 学期切换）
├── question_bank/          # 题库注册表（registry.jsonl + 元数据）
├── 大三下/
│   ├── 押题卷/             # 5 套交互式答题 HTML
│   ├── 题库/               # 6 科 PDF 题库
│   └── 复习资料/           # 7 科 MD（4 科含 HTML）
├── 复习资料/               # 主复习资料 MD
├── 知识库素材/             # RAG 素材（configs + OCR 文本 + subject_config）
├── GoldenSet/              # 金标真题数据（结构化 JSON + 真题 MD）
├── 中间产物/ 最终产物/      # 批次生产产物（batch027）
└── 质检报告/               # QC 质检报告
```

## 🔒 隐私

- ✅ 纯静态，无 API 调用，无敏感信息
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
