# 任务：为 batch040 题目补写“学习价值层”

你是临床医学命题与学习科学专家。请为下面 3 道题补写结构化解析与错误认知字段。
**只输出严格 JSON 数组**，不要 Markdown 代码块，不要解释，不要改写题干/选项/答案。

## 硬规则

1. 只能使用题目中给出的 `stem`、`options`、`answer`、`explanation`、`teacher_anchor`、`source_page` 信息；不得引入未给出的数值、指南、药物剂量或研究结论。
2. `correct_rationale`：解释正确答案的机制/依据，至少 60 字；不要只复述答案。
3. `per_option`：必须覆盖全部选项，label 与输入完全一致。
   - 正确选项：`truth=true`，`misconception_id=null`，`misconception=null`；`why` 说明为什么对。
   - 错误选项：`truth=false`，`why` 至少 20 字，说明为什么错；`misconception_id` 用 `MC-ENT-XX` 格式；`misconception` 说明学生为什么会选它。
4. `key_takeaway`：可迁移到同类题的鉴别规则/记忆钩子，至少 30 字。
5. `source_quote`：从 `teacher_anchor` 中**逐字摘录**支持答案的句子；若 teacher_anchor 为空或与题目不匹配，`source_quote=""`，`source_quote_status` 写 `missing` 或 `mismatch`。
6. `source_quote_status`：`exact` / `paraphrase` / `missing` / `mismatch`。
7. `anchor_status`：`verified` / `partial` / `mismatch` / `missing`。
8. `quality_flags`：数组；记录“疑似双答案/锚点不匹配/来源不足/需人工裁定”等问题。没有则空数组。
9. 不要修改原题；输出中 `id` 必须与输入一致。

## 输出格式（只输出这个数组）

```json
[
  {
    "id": "batch040-...",
    "teacher_anchor": "原样复制输入的 teacher_anchor",
    "keypoint_ref": ["原样复制"],
    "learning_value": {
      "correct_rationale": "...",
      "per_option": [
        {"label": "A", "truth": false, "why": "...", "misconception_id": "MC-ENT-01", "misconception": "..."},
        {"label": "B", "truth": true, "why": "...", "misconception_id": null, "misconception": null}
      ],
      "key_takeaway": "...",
      "source_quote": "...",
      "source_quote_status": "exact",
      "anchor_status": "verified",
      "quality_flags": [],
      "review_status": "pilot_unreviewed"
    }
  }
]
```

## 输入题目

```json
[
  {
    "id": "batch040-M02-A1-003",
    "type": "A1",
    "module": "M02",
    "module_name": "耳科学",
    "stem": "梅尼埃病发作性旋转性眩晕的持续时间通常为",
    "options": [
      {"label": "A", "text": "每次发作持续数秒钟至数十秒钟"},
      {"label": "B", "text": "每次发作持续数分钟至十分钟"},
      {"label": "C", "text": "每次发作持续20分钟至12小时"},
      {"label": "D", "text": "每次发作持续约1～2天"},
      {"label": "E", "text": "每次发作持续约3～7天"}
    ],
    "answer": "C",
    "explanation": "梅尼埃病临床诊断标准中，发作性旋转性眩晕每次持续20分钟至12小时；临床实际多为20分钟至数小时，通常2∼3小时转入缓解期，持续超过24小时者较少见（教材P114）。",
    "teacher_anchor": "椭圆囊斑和球囊斑感受直线加速度，半规管壶腹嵴感受角加速度；梅尼埃病眩晕通常持续20分钟至12小时并伴波动性听力改变；BPPV由头位改变诱发，通常不超过1分钟。",
    "source_page": "教材P114",
    "keypoint_ref": ["第119条", "第29条"],
    "difficulty": "基础",
    "bloom": "记忆"
  },
  {
    "id": "batch040-M03-A1-002",
    "type": "A1",
    "module": "M03",
    "module_name": "鼻科学",
    "stem": "生理性鼻周期表现为两侧鼻腔阻力交替变化，其变化主要与下列哪一结构的状态有关",
    "options": [
      {"label": "A", "text": "鼻中隔偏曲程度"},
      {"label": "B", "text": "鼻腔筛窦引流通道状态"},
      {"label": "C", "text": "双侧下鼻甲充血状态"},
      {"label": "D", "text": "蝶窦自然开口位置"},
      {"label": "E", "text": "鼻前庭鼻毛的多少"}
    ],
    "answer": "C",
    "explanation": "鼻周期是鼻阻力昼夜及左右交替变化的现象，主要受双侧下鼻甲充血状态影响，间隔2~7小时出现一个周期（教材P161）。",
    "teacher_anchor": "正常人的鼻阻力呈昼夜及左右规律和交替变化，这种变化主要受双侧下鼻甲充血状态影响间隔2~7小时出现一个周期，称之为生理性的鼻周期。",
    "source_page": "教材P161",
    "keypoint_ref": ["第35条"],
    "difficulty": "基础",
    "bloom": "记忆"
  },
  {
    "id": "batch040-M05-A1-002",
    "type": "A1",
    "module": "M05",
    "module_name": "喉部疾病及危重气道处理",
    "stem": "成人喉的上界约平",
    "options": [
      {"label": "A", "text": "第2～3颈椎"},
      {"label": "B", "text": "第3～4颈椎"},
      {"label": "C", "text": "第4～5颈椎"},
      {"label": "D", "text": "第5～6颈椎"},
      {"label": "E", "text": "第6～7颈椎"}
    ],
    "answer": "C",
    "explanation": "成人喉位于颈前部，上通喉咽、下接气管，上界约平第4～5颈椎，下界约平第6颈椎。喉的支架主要由甲状软骨、环状软骨、会厌软骨及成对的杓状软骨等构成，其中甲状软骨是喉部最大的软骨，前方正中融合处形成喉结（教材P290）。",
    "teacher_anchor": "成人喉的上界约平第4～5颈椎，下界约平第6颈椎。",
    "source_page": "教材P290",
    "keypoint_ref": ["补充·源③模块正文·喉科学"],
    "difficulty": "基础",
    "bloom": "记忆"
  }
]
```
