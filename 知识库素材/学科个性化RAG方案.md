# 学科个性化 RAG 方案 v1.0

> 基于各学科知识结构与命题规律调研，设计差异化索引策略。
> 2026-06-18

---

## 一、核心总纲

**现状问题**：所有学科统一使用 chunk_size=800 / overlap=150 / top_k=20 / top_n=5 的一刀切策略。

**改进总则**：每个学科独立配置 chunk 策略、检索策略、特殊处理规则。配置以 `subject_config.json` 为单一事实源（Single Source of Truth）。

---

## 二、学科调研结论与个性化策略

### 2.1 内科学（分值占比 ~33%，最高）

| 维度 | 调研结论 | 策略设计 |
|------|----------|----------|
| **知识类型** | 疾病中心制，诊断标准密集、数值阈值多（评分量表、实验室值）、治疗方案分层 | chunk_size=800（不变），overlap=200（防诊断标准截断） |
| **命题规律** | 病例分析多、鉴别诊断常考、治疗原则须区分一线/二线/禁忌 | top_n=5→**7**（需多段覆盖诊断+鉴别+治疗） |
| **知识密度** | 每页含多个数值型诊断标准 | 数值密集阈值从≥3降至≥2即保护整段 |
| **表格密集** | 大量鉴别诊断表、分期分型表 | 增强表格检测：同时保护表格前后的说明文字（各+1句上下文） |
| **特殊处理** | 风险评分（CHA2DS2-VASc、CURB-65）必须完整 | 检测评分量表模式，强制独立 chunk 且不拆分 |
| **混合检索** | 药名（β受体阻滞剂、ACEI）需要精确匹配 | 开启 hybrid_search=true，keyword_weight=0.3 |

### 2.2 外科学（分值占比 ~23%）

| 维度 | 调研结论 | 策略设计 |
|------|----------|----------|
| **知识类型** | 手术中心制，术前→术中→术后时序性强，解剖标志多 | chunk_size=800→**1000**（手术步骤连续性要求高） |
| **命题规律** | 手术适应症/禁忌症高频、并发症及处理常考、解剖层次决定手术入路 | top_k=20→**25**（外科知识较分散） |
| **时序连续性** | 同一疾病术前评估→手术方式→术后管理必须在同一或相邻 chunk | preserve_sequence=true，章节内强制按原文顺序检索 |
| **分期分型** | TNM 分期、骨折分型（Garden、Neer）密集 | 分期分型表独立 chunk + 标注 `data_type="staging"` |
| **总论 vs 各论** | 总论（无菌术、水电解质、休克）与各论（普外、骨科）知识差异大 | chapter-level filter 作为默认路由 |
| **混合检索** | 术式名（Bilroth I/II、Lichtenstein）需精确匹配 | hybrid_search=true，keyword_weight=0.4（高于内科） |

### 2.3 儿科学（分值占比 ~18%）

| 维度 | 调研结论 | 策略设计 |
|------|----------|----------|
| **知识类型** | 年龄特异性参数密集（生长曲线、发育里程碑、按体重给药） | chunk_size=800→**600**（参数密度高但每个参数独立） |
| **命题规律** | 病例分析题占比高（~35%），年龄-症状-诊断的联动关系常考 | top_n=5→**7**（需覆盖多个年龄段的参数对比） |
| **数值特异性** | 不同年龄正常值（心率、呼吸、血压）完全不同 | age_aware=true，chunk 元数据标注 `age_range` |
| **药物剂量** | 按体重/体表面积计算，单位精确 | 所有含 `mg/kg` 的段落自动保护，不拆分 |
| **发育里程碑** | 粗大运动→精细运动→语言→社交，按月龄排列 | 发育里程碑表独立 chunk，标注 `data_type="milestone"` |
| **混合检索** | 年龄+症状+病名的联合查询常见 | hybrid_search=true，年龄数字做 keyword boost |

### 2.4 神经病学

| 维度 | 调研结论 | 策略设计 |
|------|----------|----------|
| **知识类型** | 解剖定位驱动，综合征复杂（Wallenberg、Millard-Gubler），定位→定性诊断 | chunk_size=800（适中），overlap=180 |
| **命题规律** | 定位诊断（哪个部位病变）高频、综合征临床表现常考 | 解剖路径描述必须完整，不拆分神经传导通路段落 |
| **综合征密集** | 每个综合征含病因+临床表现+体征+治疗的完整链条 | 综合征检测：含「综合征」或「syndrome」的段落独立 chunk |
| **影像学关联** | CT/MRI 对应解剖位置与临床表现的关系常考 | 影像学描述+临床表现的关联段落保留上下文 |
| **脑血管病分区** | TOAST 分型、OCSP 分型、缺血半暗带概念 | 分型标准独立 chunk |
| **检索策略** | 解剖名词精确匹配（展神经、面神经核、内侧丘系） | hybrid_search=true，keyword_weight=0.5（解剖名词精确） |

### 2.5 精神病学

| 维度 | 调研结论 | 策略设计 |
|------|----------|----------|
| **知识类型** | 诊断标准中心制（DSM/ICD 诊断标准结构化），症状群分类 | chunk_size=600→**500**（诊断标准每条简明） |
| **命题规律** | 诊断标准鉴别（抑郁 vs 双相）、药物副作用对比、量表应用常考 | **诊断标准不拆分原则**：ICD-10/DSM-5 诊断条目须整条在一个 chunk |
| **症状学** | 阳性症状/阴性症状/认知症状分类 | 症状描述独立 chunk，标注 `symptom_type` |
| **评定量表** | 量表名称+条目+评分标准+临床意义 | 量表独立 chunk，标注 `data_type="scale"` |
| **药物分类** | 抗精神病药（典型/非典型）、抗抑郁药（SSRI/SNRI）、心境稳定剂 | 药类名精确匹配，hybrid_search=true |
| **检索策略** | 语义匹配更重要（「情绪低落」vs「抑郁发作」的区分） | top_k=20, top_n=5 |

### 2.6 皮肤性病学

| 维度 | 调研结论 | 策略设计 |
|------|----------|----------|
| **知识类型** | 形态学描述为主（原发疹/继发疹）、分布规律、形态+分布→诊断 | chunk_size=800→**600**（形态描述简洁） |
| **命题规律** | 皮损形态鉴别（斑疹 vs 丘疹 vs 斑块）、分布部位（四肢伸侧 vs 屈侧）常考 | 形态描述+好发部位+诊断的三元组不分拆 |
| **诊断路径** | 皮损形态→分布→实验室检查→诊断，逻辑链条 | preserve_sequence=true |
| **性病部分** | 潜伏期、实验室检查、治疗方案数值密集 | 数值密集保护（≥2 个数值即保护） |
| **外用药物** | 剂型选择（溶液、乳膏、软膏）与皮损类型匹配 | 外用药选择规则独立 chunk |
| **检索策略** | 形态描述词（「银白色鳞屑」「Auspitz 征」）需要语义匹配 | semantic 为主，hybrid 为辅 |

### 2.7 中医学

| 维度 | 调研结论 | 策略设计 |
|------|----------|----------|
| **知识类型** | 范式独立：辨证论治为核心、方剂为最小知识单元、经络腧穴定位 | chunk_size=800→**500**（概念紧凑，每方一单元） |
| **命题规律** | 方剂组成+功用+主治的三位一体常考、辨证分型（同病异证）高频 | **每方独立 chunk**，方名+组成+功用+主治+加减不拆分 |
| **辨证论治** | 同一病种多个证型（风寒/风热/痰热），各证治法方药不同 | 每证独立 chunk，标注 `pattern_type` |
| **中药学** | 性味归经+功效+主治+用法+禁忌 | 每药独立 chunk（单味药知识紧凑，不宜与其他药混合） |
| **针灸腧穴** | 定位+归经+主治+刺灸法 | 每穴独立 chunk，标注 `acupoint=true` |
| **基础理论** | 阴阳五行、藏象、气血津液、病因病机 | chunk_size=500，概念定义独立 |
| **检索策略** | 方名/药名/穴名精确匹配需求极高 | hybrid_search=true，**keyword_weight=0.6**（中医术语匹配最关键） |

### 2.8 医患沟通

| 维度 | 调研结论 | 策略设计 |
|------|----------|----------|
| **知识类型** | 沟通模型（Kalamazoo、Calgary-Cambridge）、伦理原则、法律法规 | chunk_size=800（适中） |
| **命题规律** | 医患权利与义务、知情同意、医疗纠纷处理、伦理原则案例应用 | top_n=5→**3**（科目内容少，top_n 过高引入噪声） |
| **法律条文** | 《医师法》《民法典》《医疗纠纷预防和处理条例》引文精确 | 法律条文整段保护，不拆分 |
| **模型描述** | 沟通步骤（SPIKES 坏消息告知模型）按步骤序列 | 模型完整 chunk，标注 `model_name` |
| **检索策略** | 语义匹配即可，不需要 keyword boost | hybrid_search=false（纯语义足够） |

### 2.9 辅助资料（贺银成、昭昭）

| 资料 | 性质 | 策略 |
|------|------|------|
| 贺银成讲义（3卷） | 考点浓缩型总结，非逐字教材 | chunk_size=**500**（考点精炼短小），top_n=5 |
| 贺银成真题（2卷） | 历年真题+解析 | 每题独立 chunk（题+解析不拆分），检索时优先按章节过滤 |
| 昭昭题眼狂背（2卷） | 口诀/记忆法，碎片化 | chunk_size=**400**，top_n=3（仅辅助记忆），score_threshold≥0.75 |

---

## 三、学科级配置 Schema

### 3.1 配置文件格式

每学科独立配置，存储在 `知识库素材/{subject}/subject_config.json`：

```json
{
  "subject": "内科学",
  "subject_code": "internal-med",
  "version": "1.0",

  "chunk_strategy": {
    "chunk_size": 800,
    "overlap": 200,
    "min_chunk_size": 100,
    "split_priority": ["\\n\\n", "\\n", "。", "；", "、"],
    "numeric_threshold": 2,
    "preserve_sequence": false,
    "special_rules": [
      {
        "type": "table_protect",
        "description": "表格前后各保留1句上下文",
        "context_sentences": 1
      },
      {
        "type": "numeric_protect",
        "min_values": 2
      },
      {
        "type": "pattern_protect",
        "pattern": "(CHA2DS2|CURB-65|GCS|APACHE|MELD|Child[ -]?Pugh)",
        "description": "评分量表不拆分"
      },
      {
        "type": "section_boundary",
        "pattern": "第[一二三四五六七八九十百\\d]+节"
      }
    ],
    "metadata_enrichment": ["has_diagnostic_criteria", "has_drug_dosage"]
  },

  "retrieval_strategy": {
    "top_k": 20,
    "top_n": 7,
    "score_threshold": 0.70,
    "hybrid_search": true,
    "keyword_weight": 0.3,
    "chapter_filter": true,
    "rerank_model": "BAAI/bge-reranker-v2-m3"
  },

  "query_enhancement": {
    "synonym_expansion": true,
    "term_normalization": {
      "房颤": "心房颤动",
      "心梗": "心肌梗死",
      "脑梗": "脑梗死",
      "甲亢": "甲状腺功能亢进症"
    }
  }
}
```

### 3.2 所有学科配置摘要

| 学科 | chunk_size | overlap | top_k | top_n | hybrid | keyword_weight | 最特殊规则 |
|------|-----------|---------|-------|-------|--------|---------------|-----------|
| 内科学 | 800 | 200 | 20 | **7** | true | 0.3 | 评分量表不拆分 |
| 外科学 | **1000** | 200 | **25** | 5 | true | **0.4** | 手术步骤顺序保护 |
| 儿科学 | **600** | 150 | 20 | **7** | true | 0.3 | 年龄感知标注 |
| 神经病学 | 800 | 180 | 20 | 5 | true | **0.5** | 传导通路不拆分 |
| 精神病学 | **500** | 120 | 20 | 5 | true | 0.3 | 诊断标准不拆分 |
| 皮肤性病学 | **600** | 150 | 20 | 5 | false | — | 形态描述三元组 |
| 中医学 | **500** | 120 | 20 | 5 | true | **0.6** | 每方/每药独立 chunk |
| 医患沟通 | 800 | 150 | 15 | **3** | false | — | 法律条文保护 |
| 贺银成讲义 | **500** | 100 | 15 | 5 | true | 0.4 | 考点精炼 |
| 贺银成真题 | 800 | 150 | 10 | 3 | true | 0.5 | 每题独立 |
| 昭昭题眼 | **400** | 80 | 10 | 3 | true | 0.4 | 口诀碎片 |

---

## 四、索引结构设计

### 4.1 目录结构

```
知识库素材/
├── 索引规则.md                         ← 通用索引规则（保留）
├── 学科个性化RAG方案.md                ← 本文档
├── subject_config.json                 ← 全局注册表（所有学科的配置入口）
│
├── 内科学/
│   ├── 21. 内科学（第10版）.pdf        ← 原始 PDF
│   ├── subject_config.json             ← 学科级配置（参考3.1）
│   └── raw/                            ← 预处理中间文件（可选）
│
├── 外科学/
│   ├── 22. 外科学 .pdf
│   ├── subject_config.json
│   └── raw/
│
├── ...（其余学科同级结构）
│
├── index_store/                        ← 索引持久化（不变）
│   ├── index_manifest.json             ← 升级：每个 entry 增加 config_version 字段
│   ├── internal-med/
│   │   ├── embeddings.npy              ← 按学科策略重新索引后的向量
│   │   └── index_config.json           ← 该索引实际使用的配置快照
│   ├── surgery/
│   ├── ...
│   └── shared_index/                   ← 跨学科检索时的统一视图（可选）
│
├── chunks_metadata/                    ← 元数据（不变，但元数据字段扩展）
│   ├── internal-med_chunks.jsonl
│   ├── surgery_chunks.jsonl
│   └── ...
│
└── retrieval_log/                      ← 检索日志（不变）
```

### 4.2 元数据扩展

在现有元数据基础上，增加学科个性化字段：

```json
{
  "chunk_id": "internal-med_ch03_s3.5_p223_c0001",
  "subject": "内科学",
  "subject_code": "internal-med",

  "data_type": "diagnostic_criteria | staging | scale | drug_info | procedure | milestone | syndrome | formula | acupoint | law | model | general",
  "age_range": "新生儿 | 婴儿 | 幼儿 | 学龄前 | 学龄期 | 青春期" ,

  "preserve_order": true,
  "sequence_group": "preop | intraop | postop",

  "has_numeric_data": true,
  "numeric_values": ["mg/kg", "mmHg", "mmol/L"],

  "special_tags": ["scale:CHA2DS2-VASc", "nerve:facial", "formula:麻黄汤"]
}
```

### 4.3 全局注册表 `subject_config.json`

```json
{
  "schema_version": "1.0",
  "subjects": {
    "internal-med": {
      "name": "内科学",
      "priority": 0,
      "config_file": "知识库素材/内科学/subject_config.json",
      "index_status": "needs_reindex | indexed | deprecated",
      "last_reindexed": "2026-06-17",
      "config_version": "1.0"
    },
    "surgery": {
      "name": "外科学",
      "priority": 1,
      "config_file": "知识库素材/外科学/subject_config.json",
      "index_status": "needs_reindex",
      "last_reindexed": "2026-06-17",
      "config_version": "1.0"
    }
  }
}
```

---

## 五、实现路线图

### Phase 1：基础设施（预计 1-2 天）
1. 创建 `subject_config.json` 全局注册表
2. 为每个学科创建 `subject_config.json` 配置文件
3. 扩展 `embed_index.py`：读取学科配置，按学科定制 chunk 参数和特殊规则
4. 扩展 `search_kb.py`：按学科加载检索配置，开启 hybrid_search

### Phase 2：逐步重新索引
按优先级重新索引。不影响现有工作流，可逐个学科进行：

| 顺序 | 学科 | 原因 |
|:----:|------|------|
| 1 | 内科学 | 分值最高，急需个性化 |
| 2 | 外科学 | 分值第二，chunk 变化最大 |
| 3 | 儿科学 | 年龄感知需求新字段 |
| 4 | 神经病学 | 综合征保护重要 |
| 5 | 中医学 | 策略差异最大 |
| 6 | 其余学科 | 按需进行 |

### Phase 3：混合检索实现
- `search_kb.py` 增加 `--hybrid` 开关
- 关键词检索使用 BM25（内置实现，无外部依赖）
- 向量检索与关键词检索加权融合（`keyword_weight` 控制比例）

---

## 六、与现有工作流兼容

- **向后兼容**：未配置 `subject_config.json` 的学科回退到统一默认值（800/150/20/5）
- **增量迁移**：重新索引后只覆盖该学科索引，不影响其他学科
- **检索无缝切换**：`search_kb.py` 读取 manifest 中的 `config_version`，自动加载对应策略

---

## 七、附录：各学科关键知识类型标记标准

| data_type | 说明 | 适用学科 |
|-----------|------|----------|
| `diagnostic_criteria` | 诊断标准/分类标准 | 内、外、儿、精神 |
| `staging` | 分期分型表 | 内、外、神 |
| `scale` | 评定量表/评分 | 内、精神 |
| `drug_info` | 药物信息 | 内、外、儿、精神、皮 |
| `procedure` | 手术/操作步骤 | 外 |
| `millstone` | 发育里程碑 | 儿 |
| `syndrome` | 综合征 | 神、内 |
| `formula` | 方剂 | 中医 |
| `acupoint` | 腧穴 | 中医 |
| `law` | 法律法规 | 医患沟通 |
| `model` | 沟通模型 | 医患沟通 |
| `dosage_calc` | 剂量计算 | 儿 |
| `anatomy_pathway` | 解剖传导通路 | 神 |
| `morphology` | 皮损形态 | 皮 |
