# -*- coding: utf-8 -*-
"""Build and self-validate batch027 QC report JSON."""
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

report = {
  "report_metadata": {
    "report_id": "QC-20260819-batch027",
    "batch_source": "Agent 2 输出批次 batch027 内科学·呼吸系统疾病（100 题 / 8 模块）",
    "total_questions": 100,
    "total_materials": 1,
    "gate_decision": "PASS_WITH_FIXES",
    "overall_score": 96.5,
    "_score_methodology": "加权扣分制：满分100，按问题严重度与影响面扣分——D6 反向题极性标注错乱 7 题（4 题选项极性真值表反转 critical、3 题极性标签与题意不符 major）共扣2.5；D7 答案位置集中（60.9% 为 A）major 扣0.5；D2 错别字 minor 扣0.2；D5 事实、D16 Bloom（30/40/24/6 精确达标）、D20 B1（10/10）等全通过维度不扣分；另加 R2/R8 42 项结构/受体名豁免说明。",
    "spot_check_ratio": {
      "numeric_fact_check": "25+ 数值项全量核对教材原文（≥10% 要求，实际约 30% 数值型题目）",
      "source_trace_check": "18/18 溯源页码锚点核对教材原文通过（≥10%）",
      "distractor_check": "数值型干扰项相邻区间设计（≥10% 抽查）",
      "cross_batch": "batch014 呼吸 155 题术语/数值/方案一致性核对通过"
    },
    "validate_report_note": "validate_options.py 报告 42 条 WARN（41×R2 选项长度比 1.5-2.0x + 4×R8 β2 受体名豁免），0 FAIL。R2 为结构豁免（短疾病名如'肺腺癌'3字 vs 长短语如'慢性阻塞性肺疾病'8字，属 HC-14 结构模板允许的自然差异），R8 为受体名豁免（短效/长效β2激动剂），均按编排者指令视为豁免，不计入 D17 失败。",
    "dimension_scores": {
      "D1_术语规范性": {"pass": 100, "fail": 0},
      "D2_语法拼写": {"pass": 99, "fail": 1},
      "D3_结构完整性": {"pass": 100, "fail": 0},
      "D4_格式一致性": {"pass": 100, "fail": 0},
      "D5_事实准确性": {"pass": 100, "fail": 0},
      "D6_题型极性自洽": {"pass": 93, "fail": 7},
      "D7_选项互斥性": {"pass": 99, "fail": 1},
      "D8_答案唯一性": {"pass": 100, "fail": 0},
      "D9_解析完整度": {"pass": 100, "fail": 0},
      "D10_认知层级校准": {"pass": 100, "fail": 0},
      "D11_干扰项质量": {"pass": 100, "fail": 0},
      "D12_考点溯源": {"pass": 100, "fail": 0},
      "D13_跨题一致性": {"pass": 100, "fail": 0},
      "D14_跨章节一致性": {"pass": 100, "fail": 0},
      "D15_外来素材验证": {"pass": 100, "fail": 0},
      "D16_认知层级覆盖率": {"pass": 100, "fail": 0},
      "D17_选项同质性": {"pass": 100, "fail": 0},
      "D18_词重复线索": {"pass": 100, "fail": 0},
      "D19_收敛策略": {"pass": 100, "fail": 0},
      "D20_B1型题专项": {"pass": 100, "fail": 0, "score": 10.0}
    }
  },
  "dimensions": [
    {"dimension": "D1_术语规范性", "status": "PASS", "score": 10.0, "detail": "标准医学术语，药物通用名（左氧氟沙星、吉非替尼、孟鲁司特等），缩写（FEV1、PaO2、PaCO2、PEEP、CTPA）均在首次出现处有解释或上下文自明；β2 受体名属 R8 豁免项。"},
    {"dimension": "D2_语法拼写", "status": "MINOR", "score": 9.9, "detail": "仅 1 处错别字：M1-A1-001 解析'胸腔积液积液上方'重复'积液'。其余语法、标点、编号规范。"},
    {"dimension": "D3_结构完整性", "status": "PASS", "score": 10.0, "detail": "100/100 题含题型、题干、选项组、polarity、bloom、answer、explanation、source_page、option_polarities 全字段。"},
    {"dimension": "D4_格式一致性", "status": "PASS", "score": 10.0, "detail": "ID 命名 batch027-M{1-8}-{A1/A2/A3/B1/X}-NNN 一致；X 型 answer 为字符串'ABCD'式；A3 子题 001a/001b/001c 连续；A1 43/A2 27/B1 10/A3 12/X 8，与 HC7 目标（45/25/10/12/8）偏差 2 题（A1→A2），属可接受小幅偏移。"},
    {"dimension": "D5_事实准确性", "status": "PASS", "score": 10.0, "detail": "数值全量对照教材原文.md 核验通过：GOLD 分级（≥80%/50-79%/30-49%/<30%）、FEV1/FVC<70% 诊断标准、长期家庭氧疗 1-2L/min 与氧浓度=21+4×流量、pH<7.2 补碱、2HRZE/4HR 方案、ARDS 小潮气量 6-8ml/kg 与 PEEP 5→8-18cmH2O、平台压≤30-35cmH2O、允许性高碳酸血症 pH7.25-7.30、Ⅱ型呼衰 PaO2<60+PaCO2>50、茶碱 6-15mg/L、激发试验 FEV1≥20%、CURB-65 呼吸≥30 次/分、HAP≥48h、右下肺动脉干≥15mm、肺型P波≥0.25mV、右心导管 mPAP≥25mmHg、PAWP≤18mmHg、小细胞癌对放化疗最敏感、Pancoast 经胸壁穿刺活检、恶性胸水=Ⅳ期等全部与教材一致。"},
    {"dimension": "D6_题型极性自洽", "status": "FAIL", "score": 7.0, "detail": "7 题 polarity=negative 存在两类问题：(a) 4 题真反选题（M2-A2-004/M4-A1-005/M4-A2-004/M7-A2-003）option_polarities 真值表反转——答案选项标 true、其余标 false，违反 HC-1'正确答案选项 option_polarity 必须为 false、其余为 true'（MedGen 反向题不变式：答案陈述必须为假）及 batch013/019 既有约定；(b) 3 题（M3-A3-001c/M4-A3-001c/M7-A3-001c）题干为'主要原因是？/其原因是？'的正面设问（答案陈述为真），却被标为 negative，极性标签与题意不符。7 题否定词均已加粗（**不包括/不用/无效/错误/不会/不宜**），答案反向不变式内容层面成立（答案选项确为反选语义），但标注层需修正。"},
    {"dimension": "D7_选项互斥性", "status": "MAJOR", "score": 9.5, "detail": "选项互斥性/逻辑穷举/数值排序均良好；但答案位置分布严重集中：92 道单选答案 A=56（60.9%）、B=9、C=15、D=9、E=3（M6 全 A×10、M8 全 A×10、M4 A×9），构成 NBME 应试技巧风险（testwiseness），考生可按位置猜答。"},
    {"dimension": "D8_答案唯一性", "status": "PASS", "score": 10.0, "detail": "全部单选题唯一答案无歧义；X 型答案与 option_polarities 完全一致（如 M2-X-001 ABCD 对应 A-D true/E false）。"},
    {"dimension": "D9_解析完整度", "status": "PASS", "score": 10.0, "detail": "100/100 解析≥50 字并逐项说明对错机制，含鉴别要点与教材页码锚点；与 answer_key 一致。"},
    {"dimension": "D10_认知层级校准", "status": "PASS", "score": 10.0, "detail": "记忆题均为短题干单知识点直答；分析题（M2-A2-004/M3-A2-002/M4-A2-004/M5-A2-003/M7-A2-003/M8-A2-006）均需多步推理，标定合理。"},
    {"dimension": "D11_干扰项质量", "status": "PASS", "score": 10.0, "detail": "数值型干扰项为相邻区间（如 1~2/2~2.5/2.5~3L/min、pH<7.10~7.30、≥15/18/20mm），差距<5 倍且均为常见混淆值；临床型干扰项基于真实疾病/机制。抽查≥10% 无弱干扰项（plausibility≥0.5）。"},
    {"dimension": "D12_考点溯源", "status": "PASS", "score": 10.0, "detail": "100/100 题含 source_page（教材P##）；抽样 18 题页码锚点逐一对照教材原文分页标记全部命中。"},
    {"dimension": "D13_跨题一致性", "status": "PASS", "score": 10.0, "detail": "同知识点跨题陈述一致：如 COPD 诊断（FEV1/FVC<70%）、AECOPD 分级（Ⅰ/Ⅱ/Ⅲ级）、哮喘重度（心率>120、PEF<60%）、强心苷指征等在 M2/M3/M7/M8 间无矛盾。"},
    {"dimension": "D14_跨章节一致性", "status": "PASS", "score": 10.0, "detail": "与 batch014 呼吸 155 题交叉核对：2HRZE/4HR、PaO2<60/PaCO2>50、激发试验≥20%、ARDS 氧合指数≤300、GOLD 分级依据 FEV1%pred 等表述一致；无术语/数值冲突；题干无近重复（相似度最高 0.65 为 HAP 与 CAP 病原体不同题）。"},
    {"dimension": "D15_外来素材验证", "status": "N/A", "score": 10.0, "detail": "Agent 2 自产内容，D5 已全量覆盖，不适用外来素材逐值核验；跨批比对见 D13/D14。"},
    {"dimension": "D16_认知层级覆盖率", "status": "PASS", "score": 10.0, "detail": "实际分布 记忆30/理解40/应用24/分析6 = 目标 30/40/24/6，偏差 0%；记忆 30%<50%、理解 40%≥35%，Bloom 门禁 PASS。"},
    {"dimension": "D17_选项同质性", "status": "PASS", "score": 10.0, "detail": "选项类别/语法结构同质（全疾病名/全药物名/全数值区间/全机制短语）；长度比 1.5-2.0x 的 41 题属 R2 结构豁免（HC-14 结构模板允许）；无绝对化用语问题、无括号后缀变体；β2 受体名 4 处为 R8 豁免。"},
    {"dimension": "D18_词重复线索", "status": "PASS", "score": 10.0, "detail": "机械检测：题干专业术语仅在正确选项出现的命中数=0（R10 亦 0 FAIL）。"},
    {"dimension": "D19_收敛策略", "status": "PASS", "score": 10.0, "detail": "机械检测：正确选项术语共享计数无显著最高（R11 无 WARN 以上）。"},
    {"dimension": "D20_B1型题专项", "status": "PASS", "score": 10.0, "detail": "2 组×5 子题。组1（M1 呼吸系统体征鉴别）：共用选项 5-8 字无笼统项（B1-1 OK），答案 C/D/A/B/E 五位各 1 次无集中（B1-2 OK），覆盖 5 个不同选项位（B1-3 OK），5 病种均为合理干扰；组2（M5 抗结核药与菌群）：异烟肼/利福平/吡嗪酰胺/链霉素/乙胺丁醇 3-4 字，答案 A/C/B/D/E 各 1 次，覆盖 5 位，子题考查 A群/B群/C群/半杀菌/抑菌剂 5 个不同维度。两组成绩均为 10/10，D20≠0 不触发 BLOCKED。"}
  ],
  "bloom_distribution": {
    "target": {"记忆": 30, "理解": 40, "应用": 24, "分析": 6},
    "actual": {"记忆": 30, "理解": 40, "应用": 24, "分析": 6},
    "actual_pct": {"记忆": "30%", "理解": "40%", "应用": "24%", "分析": "6%"},
    "deviation_pct": 0.0,
    "gate": "PASS",
    "note": "与 HC7 双向细目表目标 30/40/24/6 精确一致，偏差 0%<15%，记忆层 30%<50%，Bloom 门禁放行"
  },
  "issues": [
    {
      "issue_id": "ISSUE-001",
      "target": "batch027-M2-A2-004.option_polarities",
      "dimension": "D6",
      "severity": "critical",
      "description": "真反选题（机制**不包括**）option_polarities 反转：答案 D 标 true、其余标 false，违反 HC-1（正确答案选项 polarity 必须 false、其余 true）。",
      "current_text": "{\"A\":false,\"B\":false,\"C\":false,\"D\":true,\"E\":false}",
      "impact": "下游渲染/复习资料将把反选题答案选项显示为'真陈述'，与反向题不变式语义冲突；HC-1 绝对保护被违反。"
    },
    {
      "issue_id": "ISSUE-002",
      "target": "batch027-M4-A1-005.option_polarities",
      "dimension": "D6",
      "severity": "critical",
      "description": "真反选题（对支原体**无效**）option_polarities 反转：答案 D（青霉素）标 true、其余标 false。",
      "current_text": "{\"A\":false,\"B\":false,\"C\":false,\"D\":true,\"E\":false}",
      "impact": "同 ISSUE-001：反选题答案选项真值极性标注错误。"
    },
    {
      "issue_id": "ISSUE-003",
      "target": "batch027-M4-A2-004.option_polarities",
      "dimension": "D6",
      "severity": "critical",
      "description": "真反选题（痰液特征对应**错误**）option_polarities 反转：答案 D 标 true、其余标 false。",
      "current_text": "{\"A\":false,\"B\":false,\"C\":false,\"D\":true,\"E\":false}",
      "impact": "同 ISSUE-001。"
    },
    {
      "issue_id": "ISSUE-004",
      "target": "batch027-M7-A2-003.option_polarities",
      "dimension": "D6",
      "severity": "critical",
      "description": "真反选题（强心苷指征**不包括**）option_polarities 反转：答案 E 标 true、其余标 false。",
      "current_text": "{\"A\":false,\"B\":false,\"C\":false,\"D\":false,\"E\":true}",
      "impact": "同 ISSUE-001。"
    },
    {
      "issue_id": "ISSUE-005",
      "target": "batch027-M3-A3-001c.polarity",
      "dimension": "D6",
      "severity": "major",
      "description": "题干为'主要原因是？'正面设问（答案 A'地塞米松起效慢、不良反应大'为真陈述），却标 polarity=negative；应为 positive，或改写题干为'关于地塞米松的说法**错误**的是'。",
      "current_text": "polarity=negative, answer=A, option_polarities={A:true,B:false,C:false,D:false,E:false}",
      "impact": "极性标签与题意不符，反向题不变式（答案陈述必须为假）被违反；下游按 negative 处理将语义错配。"
    },
    {
      "issue_id": "ISSUE-006",
      "target": "batch027-M4-A3-001c.polarity",
      "dimension": "D6",
      "severity": "major",
      "description": "题干'该患者胸片**不会**出现空洞，主要原因是？'为正面设问（答案 A 为真陈述'不产生毒素、无肺组织坏死'），极性标签 negative 与题意不符。",
      "current_text": "polarity=negative, answer=A, option_polarities={A:true,B:false,C:false,D:false,E:false}",
      "impact": "同 ISSUE-005。"
    },
    {
      "issue_id": "ISSUE-007",
      "target": "batch027-M7-A3-001c.polarity",
      "dimension": "D6",
      "severity": "major",
      "description": "题干'该患者**不宜**常规应用利尿剂，其原因是？'为正面设问（答案 A 为真陈述'利尿可致痰液黏稠、呼酸合并代碱'），极性标签 negative 与题意不符。",
      "current_text": "polarity=negative, answer=A, option_polarities={A:true,B:false,C:false,D:false,E:false}",
      "impact": "同 ISSUE-005。"
    },
    {
      "issue_id": "ISSUE-008",
      "target": "GLOBAL.answer_position",
      "dimension": "D7",
      "severity": "major",
      "description": "92 道单选答案位置严重集中：A=56（60.9%）、E 仅 3；M6 与 M8 各 10 道单选答案全为 A，M4 有 9 道 A。构成答案位置应试技巧漏洞。",
      "current_text": "A:56 B:9 C:15 D:9 E:3（M6 全 A、M8 全 A）",
      "impact": "考生可按'无把握选 A'策略获得异常高分，降低考试效度；NBME 建议答案均匀分布（各约 20%）。"
    },
    {
      "issue_id": "ISSUE-009",
      "target": "batch027-M1-A1-001.explanation",
      "dimension": "D2",
      "severity": "minor",
      "description": "解析错别字：'胸腔积液积液上方'重复'积液'。",
      "current_text": "肺内空洞及胸腔积液积液上方",
      "impact": "文字瑕疵，不影响正确性。"
    },
    {
      "issue_id": "ISSUE-010",
      "target": "GLOBAL.source_trace",
      "dimension": "D12",
      "severity": "minor",
      "description": "抽样 18 题页码锚点全部命中教材原文分页（含 P20/P27/P87/P88/P97/P100/P112/P116/P125/P128 等），仅个别页码标注可细化为跨页（如 M4-A2-004 标 P69 但解析涉及 P69-71），不影响溯源有效性。",
      "current_text": "source_page 均在教材P1-155 范围内",
      "impact": "无实质影响，可选优化。"
    }
  ],
  "modification_instructions": [
    {
      "patch_id": "PATCH-HX-001",
      "target": "batch027-M2-A2-004.option_polarities",
      "operation": "fix_polarity",
      "current_value": "{\"A\":false,\"B\":false,\"C\":false,\"D\":true,\"E\":false}",
      "proposed_value": "{\"A\":true,\"B\":true,\"C\":true,\"D\":false,\"E\":true}",
      "reason": "真反选题答案选项（弥散功能障碍，为假机制）极性必须为 false，其余为 true（HC-1 反向题不变式）。",
      "linked_issue_ids": ["ISSUE-001"],
      "preconditions": ["修改后该选项真值极性不得改变。原始极性={A:false,B:false,C:false,D:true,E:false}。", "答案键仍为 D，不改动选项文本内容。"],
      "post_checks": ["重新验证本题选项极性分布：1 false + 4 true。", "answer_key=D 不变，explanation 无需改动。"],
      "risk_level": "auto_with_review"
    },
    {
      "patch_id": "PATCH-HX-002",
      "target": "batch027-M4-A1-005.option_polarities",
      "operation": "fix_polarity",
      "current_value": "{\"A\":false,\"B\":false,\"C\":false,\"D\":true,\"E\":false}",
      "proposed_value": "{\"A\":true,\"B\":true,\"C\":true,\"D\":false,\"E\":true}",
      "reason": "真反选题答案选项（青霉素对支原体无效）极性必须为 false，其余为 true。",
      "linked_issue_ids": ["ISSUE-002"],
      "preconditions": ["修改后该选项真值极性不得改变。原始极性={A:false,B:false,C:false,D:true,E:false}。", "答案键仍为 D。"],
      "post_checks": ["重新验证本题选项极性分布：1 false + 4 true。", "answer_key=D 不变。"],
      "risk_level": "auto_with_review"
    },
    {
      "patch_id": "PATCH-HX-003",
      "target": "batch027-M4-A2-004.option_polarities",
      "operation": "fix_polarity",
      "current_value": "{\"A\":false,\"B\":false,\"C\":false,\"D\":true,\"E\":false}",
      "proposed_value": "{\"A\":true,\"B\":true,\"C\":true,\"D\":false,\"E\":true}",
      "reason": "真反选题答案选项（粉红色泡沫样痰-支原体对应错误）极性必须为 false，其余为 true。",
      "linked_issue_ids": ["ISSUE-003"],
      "preconditions": ["修改后该选项真值极性不得改变。原始极性={A:false,B:false,C:false,D:true,E:false}。", "答案键仍为 D。"],
      "post_checks": ["重新验证本题选项极性分布：1 false + 4 true。", "answer_key=D 不变。"],
      "risk_level": "auto_with_review"
    },
    {
      "patch_id": "PATCH-HX-004",
      "target": "batch027-M7-A2-003.option_polarities",
      "operation": "fix_polarity",
      "current_value": "{\"A\":false,\"B\":false,\"C\":false,\"D\":false,\"E\":true}",
      "proposed_value": "{\"A\":true,\"B\":true,\"C\":true,\"D\":true,\"E\":false}",
      "reason": "真反选题答案选项（双下肢水肿明显者非强心苷指征）极性必须为 false，其余为 true。",
      "linked_issue_ids": ["ISSUE-004"],
      "preconditions": ["修改后该选项真值极性不得改变。原始极性={A:false,B:false,C:false,D:false,E:true}。", "答案键仍为 E。"],
      "post_checks": ["重新验证本题选项极性分布：1 false + 4 true。", "answer_key=E 不变。"],
      "risk_level": "auto_with_review"
    },
    {
      "patch_id": "PATCH-HX-005",
      "target": "batch027-M3-A3-001c.polarity",
      "operation": "fix_polarity",
      "current_value": "polarity=negative",
      "proposed_value": "polarity=positive（同步将题干否定词加粗改为普通强调或保留；option_polarities {A:true,...} 保持不变）",
      "reason": "题干为'主要原因是？'正面设问，答案 A 为真陈述，极性标签应为 positive 以符合反向题不变式。",
      "linked_issue_ids": ["ISSUE-005"],
      "preconditions": ["确认题干问句为'主要原因'正面设问而非'哪项错误/除外'。", "答案键 A 与 option_polarities 保持 true。"],
      "post_checks": ["polarity=positive 后正选题校验：答案选项唯一 true。", "D6 复检通过。"],
      "risk_level": "safe_auto"
    },
    {
      "patch_id": "PATCH-HX-006",
      "target": "batch027-M4-A3-001c.polarity",
      "operation": "fix_polarity",
      "current_value": "polarity=negative",
      "proposed_value": "polarity=positive（option_polarities {A:true,...} 保持不变）",
      "reason": "题干'胸片不会出现空洞，主要原因是？'为正面设问，答案 A 为真陈述。",
      "linked_issue_ids": ["ISSUE-006"],
      "preconditions": ["确认题干问句为'主要原因'正面设问。", "答案键 A 与 option_polarities 保持 true。"],
      "post_checks": ["polarity=positive 后正选题校验：答案选项唯一 true。", "D6 复检通过。"],
      "risk_level": "safe_auto"
    },
    {
      "patch_id": "PATCH-HX-007",
      "target": "batch027-M7-A3-001c.polarity",
      "operation": "fix_polarity",
      "current_value": "polarity=negative",
      "proposed_value": "polarity=positive（option_polarities {A:true,...} 保持不变）",
      "reason": "题干'不宜常规应用利尿剂，其原因是？'为正面设问，答案 A 为真陈述。",
      "linked_issue_ids": ["ISSUE-007"],
      "preconditions": ["确认题干问句为'原因'正面设问。", "答案键 A 与 option_polarities 保持 true。"],
      "post_checks": ["polarity=positive 后正选题校验：答案选项唯一 true。", "D6 复检通过。"],
      "risk_level": "safe_auto"
    },
    {
      "patch_id": "PATCH-HX-008",
      "target": "GLOBAL.answer_position",
      "operation": "fix_format",
      "current_value": "A=56(60.9%) B=9 C=15 D=9 E=3；M6/M8 全 A",
      "proposed_value": "对 92 道单选做答案位置重排（保持选项文本与答案键联动），使 A/B/C/D/E 分布趋近各约 20%（每字母 17-21 题）；至少覆盖 M6、M8、M4 高集中模块；同步更新每题的 answer 与 option_polarities 键值。",
      "reason": "答案位置集中构成 NBME 应试技巧漏洞（D7），需均匀化。",
      "linked_issue_ids": ["ISSUE-008"],
      "preconditions": ["重排仅调整选项顺序（A-E 标签重新映射），不改动选项文本与解析内容。", "每题同步更新 answer_key 与 option_polarities（HC-2 答案联动）。", "数值型选项保持升/降序排列逻辑（D7）。"],
      "post_checks": ["重排后答案分布每字母 17-21 题。", "逐题校验 answer_key 指向的选项文本与原正确选项一致。", "validate_options.py 复检 FAIL=0。", "反向题 7 题 polarity 修复后 D6 复检通过。"],
      "risk_level": "auto_with_review"
    },
    {
      "patch_id": "PATCH-HX-009",
      "target": "batch027-M1-A1-001.explanation",
      "operation": "replace_text",
      "current_value": "胸腔积液积液上方",
      "proposed_value": "胸腔积液上方",
      "reason": "修正错别字（重复'积液'）。",
      "linked_issue_ids": ["ISSUE-009"],
      "preconditions": ["确认原文含'胸腔积液积液上方'。"],
      "post_checks": ["解析文本无重复词。"],
      "risk_level": "safe_auto"
    }
  ],
  "escalations": []
}

# self-validate
s = json.dumps(report, ensure_ascii=False, indent=2)
json.loads(s)
print("JSON valid. length:", len(s))

out = r"C:\Users\38063\Desktop\MedAgentWork\质检报告\batch027_质检报告.json"
with open(out, "w", encoding="utf-8") as f:
    f.write(s)
print("written:", out)

# summary stats
sev = {}
for i in report["issues"]:
    sev[i["severity"]] = sev.get(i["severity"], 0) + 1
print("severity counts:", sev)
