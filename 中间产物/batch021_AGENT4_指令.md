# Agent 4 (MedFix) 调用指令 — batch021 中医学押题卷

## 基本信息
- **批次ID**：batch021
- **科目**：中医学
- **题数**：95题
- **门禁**：PASS_WITH_FIXES（85.0分·两科最优）
- **质检报告**：`质检报告/batch021_质检报告.json`
- **题目文件**：`中间产物/batch021/batch021_questions.json`

## 问题摘要

| 严重度 | 数量 | 维度 |
|--------|:---:|------|
| critical | 0 | — |
| major   | 0 | — |
| minor   | 6 | D3/D4/D17/D18/D9 |

> ✅ batch021为本轮两科最优：Bloom偏差仅6.7%，无major/critical问题，全部为safe_auto级别的格式修正。

## 修复清单（5个补丁·4 safe_auto + 1 auto_with_review）

### 安全自动修复 (safe_auto)

**PATCH-TCM-001** — A3A4_001~005 中风病例组：
- 操作：添加共享`case_scenario`字段
- case_scenario: "患者男性，65岁。高血压病史15年。今晨起床突发言语不清、右侧肢体麻木、口眼歪斜、舌强语謇。神志清楚，舌红，苔白腻，脉弦滑。"
- 各题题干去除重复的病例描述，仅保留独立设问部分

**PATCH-TCM-002** — A3A4_006~008 痹证病例组：
- 操作：添加共享`case_scenario`字段
- case_scenario: "患者男性，55岁。双膝关节疼痛反复发作2年，加重3天。3天前因淋雨后双膝关节疼痛明显加重，痛处固定不移，遇寒痛增，得热痛减，关节屈伸不利。舌淡，苔白腻，脉弦紧。"

**PATCH-TCM-004** — TF_001~015 判断题答案格式：
- 操作：`answer`字段从`"正确"/"错误"`标准化为`"A"/"B"`
- 选项A=正确，B=错误（选项文本不变）
- 批量：15题全部统一

**PATCH-TCM-005** — A1_010.optionE：
- 原文：`仅发生于体弱之人`
- 改为：`多见于体弱之人`
- 理由：去除绝对词「仅」，七情内伤体质强者亦可发生

### 需审查修复 (auto_with_review)

**PATCH-TCM-003** — A3A4_009~010 痹证变证组：
- 操作：添加共享`case_scenario`字段
- 基于006-008病例的延续描述（多关节受累+游走性特征）
- ⚠️ 需确认与006-008的逻辑承接关系，新case_scenario不矛盾

---

## 🟢 无需升级项

- Bloom分布精准（分析层5.3%超目标）
- 无重大缺失模块
- 无D18/D19严重问题
- 无D11干扰项区分度问题

---

## HC-6 独立审查（Agent 4必做）

修复完成后，抽查≥5%题目（5题）：
1. 重点检查：A3A4病例组的case_scenario提取是否完整
2. 判断题A/B映射是否正确
3. 方剂选项是否全部为真实方剂名

## HC-7 全局一致性（Agent 4必做）

- [ ] 所有A3/A4题case_scenario字段格式一致
- [ ] 判断题答案全部为A/B格式，无遗漏
- [ ] 无残留绝对词
- [ ] `json.load()` 验证 → 纯JSON数组
- [ ] validate_options.py 重跑 → 0 FAIL

---

## 输出规范

```
最终产物/batch021/
├── ALL_questions_FIXED.json     ← 修复后完整题库（纯JSON数组，禁止YAML前置元数据）
├── AGENT4_追溯日志.json         ← 每项修改的 before/after/source_file_synced
├── AGENT4_修改声明.md           ← 修改声明
└── escalations_for_human.md     ← 升级告警（本批次预计为空）
```

## 禁止
- ❌ JSON文件添加YAML前置元数据
- ❌ 用无意义后缀凑长度
- ❌ 对中药名/方剂名/穴位名做机械截断
- ❌ 只改COMPLETE不改源文件

## 修复后验证
```bash
python validate_options.py --batch batch021
```
