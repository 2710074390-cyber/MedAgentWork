# Layer 0 — 锚定层（306西综真题）

## 目标
500道精选真题，覆盖生理学/生物化学/病理学/内科学/外科学/诊断学/药理学。

## 数据来源
- 贺银成《历年真题精析》2005-2025（含答案+解析）
- 北医黄皮书（按章节编排，交叉验证答案一致性）

## 问题类型
- A型题（A1/A2）：单选题
- B型题：共用选项题
- X型题：多选题

## 结构化文件
- `../structured/GS_上册_2024.json` — 2024真题试卷（纯题，无答案，2641条）
- `../structured/GS_下册_2025_1994.json` — 贺银成精析（含答案+解析，2754条，2025-1994）

## Schema 字段
| 字段 | 类型 | 说明 |
|------|------|------|
| gs_id | str | 全局唯一ID: GS-{年份}-{序号} |
| year | int | 考试年份 |
| question_no | int | 原卷题号 |
| type | str | A型/B型/X型 |
| subject | str | 科目分类 |
| stem | str | 题干原文 |
| options | list[str] | 选项列表 |
| answer | str | 正确答案 |
| explanation | str | 解析原文 |
| source_page | str | 教材页码溯源 |
| bloom_level | str | 认知层级 |
| difficulty | str | easy/medium/hard |
| controversial | bool | 争议题标记 |

## 争议题处理规则
当黄皮书与贺银成答案不一致时：
1. 标记 `controversial: true`
2. 记录两个版本的答案和解析
3. 以第10版教材为准进行仲裁
4. 无法仲裁的标注「待定」
