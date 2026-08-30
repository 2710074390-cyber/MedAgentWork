# User Profile — MedAgentWork

> 5 个 Agent 共享此用户信息。

## Name
（待补充）

## Preferences
- **语言**：简体中文
- **医学专业**：临床医学
- **学习阶段**：大三下学期
- **核心需求**：将教材章节转化为结构化题库

## Timezone
UTC+8（中国标准时间）

## Context
- 用户正在准备临床医学考试
- 使用 5-Agent 工作流：编排（MedMaster）→ 出题（MedGen）→ 质检（MedQC）→ 修复（MedFix）→ 复习资料（MedReview）
- 2026-08-13 起主流程迁移至 DeepSeek Harness（DSH）：角色技能位于 `.dsh/skills/`，编排在主会话完成；Cherry Studio 接力流程保留为备用
- 金标准（GoldenSet）由用户手动维护
- 工作目录：`C:\Users\38063\Desktop\MedAgentWork`
- 角色提示词：`Prompt版本/*_current_prompt.md`（DSH skill 引用同一文件，单一事实来源）

## 关联 Agent 工作区
| 工作区 | 路径 | 角色 |
|--------|------|------|
| **CherryClaw** | `C:\Users\38063\Desktop\Web-AI\` | 总编排者 |
| **web-med** | `C:\Users\38063\Desktop\web-med\` | 医学知识检索 |
| **Agent-PPT** | `C:\Users\38063\Desktop\agent-ppt\` | PPTX 生成 |
| **黑曜石** | `C:\Users\38063\Desktop\黑曜石\` | Obsidian 知识管理 |
