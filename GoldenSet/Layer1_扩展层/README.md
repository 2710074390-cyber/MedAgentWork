# Layer 1 — 扩展层（CMB开源基准 + 校内期末题）

## 目标
300道题目，补充锚定层覆盖不到的盲区（局部解剖/微生物/免疫/药理/预防/伦理/法规）。

## 数据来源

### CMB-val (推荐优先)
- 来源：FreedomIntelligence/CMB (Apache-2.0)
- 规模：280题，带solution & explanation
- 覆盖：6大类28子类（医师/护理/药师/医技/专业知识/医学考研）
- 用途：术语规范基准 + 覆盖面校验

### 校内高频题
- 人卫版教材章后复习思考题
- 历年期末真题回忆版（校内年级群/丁香园）
- 答案以教材+CMB为仲裁标准

## 字段映射（CMB → GS Schema）
| CMB字段 | GS字段 |
|---------|--------|
| exam_type | exam_type |
| exam_class | exam_class |
| exam_subject | subject |
| question | stem |
| answer | answer |
| question_type | type |
| option | options |
| solution | explanation |

## 导入状态
- [ ] CMB-val 280题 → 待下载
- [ ] 校内期末题 → 待收集
