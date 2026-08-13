import json, sys

batch2 = [
  {
    "question_id": "batch026_M8_A3_001",
    "group_id": "A3_Group3_M8",
    "group_sequence": 1,
    "question_type": "A3",
    "polarity": "positive",
    "bloom_level": "分析",
    "source_anchors": ["batch026_analysis_supp", "教材《精神病学》第十章/P125-P128", "教材《精神病学》第十七章/P209"],
    "source_pages": ["P125-P128", "P209"],
    "module_id": "M8",
    "module_name": "强迫及相关障碍",
    "priority_level": "掌握",
    "answer_key": "D",
    "option_polarities": {"A": False, "B": False, "C": False, "D": True, "E": False},
    "difficulty_index": 0.48,
    "discrimination_index": 0.44,
    "non_functioning_distractors": 0,
    "stem": "【病例组A3-3：第1题】患者男，26岁，软件工程师。因反复检查行为导致上班迟到就诊。患者近3年来反复检查门锁和水龙头，每次离家前需检查10-15次，耗时约2小时。明知门已经锁好了但仍无法控制检查冲动，若强行不检查则极度焦虑、心悸、出汗。工作方面极度追求完美，代码格式必须严格对齐，同事评价活得太累了，但患者认为做事就该如此，不觉得自己的完美主义是问题。近半年因反复检查严重影响工作，患者感到痛苦并主动求治。最可能的诊断是：",
    "options": {
      "A": "强迫性人格障碍",
      "B": "广泛性焦虑障碍",
      "C": "强迫性人格障碍共病广泛性焦虑障碍",
      "D": "强迫症",
      "E": "精神分裂症前驱期"
    },
    "explanation": {
      "correct_reason": "患者核心症状为强迫思维（门未锁的怀疑）和强迫行为（反复检查），自知力存在（明知已锁好但不能控制），症状耗时>1小时/天，引起显著痛苦和功能损害并主动求治，完全符合DSM-5强迫症诊断标准。其完美主义特征可能为强迫性人格特质，但人格障碍的核心特点是自我协调（患者不认为完美主义是问题），而强迫症的强迫症状是自我排斥的（患者感到痛苦并求治）。",
      "why_not_others": {
        "A": "强迫性人格障碍的核心特征为泛化的完美主义、秩序感和控制欲，且患者认为这些特质是合理的（自我协调）。本例患者的反复检查行为具有明确的强迫-反强迫冲突（自我排斥），且主动求治，这不符合OCPD的核心模式。",
        "B": "广泛性焦虑障碍以泛化的、多主题的担忧为特征，不局限于特定强迫思维内容，且无明显的仪式化强迫行为。本例症状高度聚焦于检查和完美主义，伴有明确仪式行为。",
        "C": "虽然有强迫性人格特质，但其求治原因是反复检查（即OCD核心症状）而非人格问题。且人格障碍的诊断需排除轴I障碍更好地解释症状。",
        "D": "正确选项：强迫思维+强迫行为+耗时>1h+自知力存在+功能损害=强迫症。",
        "E": "无任何精神病性症状（幻觉、妄想、思维紊乱），自知力完好，不符合精神分裂症。"
      },
      "common_errors": "经典陷阱：约70%强迫症患者病前有强迫型人格特质/障碍，学生容易因为看到完美主义就直接诊断OCPD。关键鉴别点：自我协调（OCPD）vs自我排斥（OCD）+主动求治行为。"
    },
    "analysis_features": ["鉴别诊断推理(OCD vs OCPD vs GAD)", "多因素综合分析(核心症状+自知力+求治行为)"],
    "design_rationale": {
      "A": "基于看到完美主义即误诊OCPD而忽略自我协调vs自我排斥的鉴别核心",
      "B": "基于忽略仪式化行为和症状聚焦性的差异",
      "C": "基于忽略OCD诊断优先于人格障碍的等级原则",
      "D": "正确答案：典型强迫症的临床诊断逻辑",
      "E": "基于将自知力存在的强迫症状误判为精神病性"
    }
  },
  {
    "question_id": "batch026_M8_A3_002",
    "group_id": "A3_Group3_M8",
    "group_sequence": 2,
    "question_type": "A3",
    "polarity": "positive",
    "bloom_level": "分析",
    "source_anchors": ["batch026_analysis_supp", "教材《精神病学》第十章/P127-P128"],
    "source_pages": ["P127-P128"],
    "module_id": "M8",
    "module_name": "强迫及相关障碍",
    "priority_level": "掌握",
    "answer_key": "B",
    "option_polarities": {"A": False, "B": True, "C": False, "D": False, "E": False},
    "difficulty_index": 0.52,
    "discrimination_index": 0.40,
    "non_functioning_distractors": 0,
    "stem": "【病例组A3-3：第2题·接上题】确诊强迫症后启动治疗。患者Y-BOCS评分26分（中度严重），无共病抑郁。首选的药物治疗方案是：",
    "options": {
      "A": "氟西汀 20mg/d",
      "B": "舍曲林 50mg/d起始，逐渐加至200mg/d",
      "C": "氯硝西泮 2mg/d",
      "D": "奥氮平 5mg/d",
      "E": "认知行为治疗（CBT）单用，不合并药物"
    },
    "explanation": {
      "correct_reason": "强迫症药物治疗首选SSRI，但所需剂量通常高于抑郁症治疗剂量（如舍曲林治疗OCD的目标剂量为150-200mg/d，而抑郁症通常50-100mg/d）。需以抗强迫剂量足量、足疗程（至少8-12周起效，通常需10-12周达到充分疗效）进行治疗。",
      "why_not_others": {
        "A": "氟西汀20mg/d为抑郁症常规起始剂量，OCD起始即可20mg/d但目标剂量需加至40-80mg/d。选项仅写20mg/d未提及加量，不足以体现OCD的高剂量治疗原则。",
        "B": "正确选项：SSRI以抗强迫剂量（舍曲林150-200mg/d）足量足疗程治疗。明确标注了起始剂量和目标剂量范围。",
        "C": "苯二氮䓬类（氯硝西泮）主要用于急性焦虑缓解，对强迫症核心症状无效，且长期使用有依赖风险。",
        "D": "非典型抗精神病药（奥氮平）不作为OCD一线单药治疗。仅在SSRI疗效不佳时作为增效剂考虑。",
        "E": "Y-BOCS 26分为中度严重OCD，单用CBT有效率有限。中重度OCD推荐药物（SSRI）+ CBT联合治疗，而非单用CBT。"
      },
      "common_errors": "核心陷阱：按抑郁症剂量使用SSRI治疗OCD。OCD需要更高剂量和更长起效时间（10-12周vs抑郁症4-8周）。如不了解这一差异，学生可能选择A（标准抑郁剂量）。"
    },
    "analysis_features": ["治疗方案比较与选择(OCD用药的特殊性：高剂量+长疗程)", "多因素综合分析(疾病严重度+治疗原则)"],
    "design_rationale": {
      "A": "基于按抑郁症剂量（20mg/d）而非OCD剂量使用氟西汀",
      "B": "正确答案：OCD的SSRI治疗需高剂量、标明剂量滴定",
      "C": "基于混淆抗焦虑与抗强迫治疗",
      "D": "基于混淆一线与增效治疗的适应证",
      "E": "基于忽略中重度OCD的药物+CBT联合治疗原则"
    }
  },
  {
    "question_id": "batch026_M8_A3_003",
    "group_id": "A3_Group3_M8",
    "group_sequence": 3,
    "question_type": "A3",
    "polarity": "positive",
    "bloom_level": "分析",
    "source_anchors": ["batch026_analysis_supp", "教材《精神病学》第十章/P127-P128"],
    "source_pages": ["P127-P128"],
    "module_id": "M8",
    "module_name": "强迫及相关障碍",
    "priority_level": "掌握",
    "answer_key": "A",
    "option_polarities": {"A": True, "B": False, "C": False, "D": False, "E": False},
    "difficulty_index": 0.42,
    "discrimination_index": 0.47,
    "non_functioning_distractors": 0,
    "stem": "【病例组A3-3：第3题·接上题】经舍曲林200mg/d治疗12周+CBT 10次后，Y-BOCS评分降至19分（减轻约27%），患者称比之前好一些，但每天仍要花1小时检查。下一步最合适的处理是：",
    "options": {
      "A": "加用利培酮 1mg/d作为SSRI增效剂",
      "B": "将舍曲林换为氯米帕明",
      "C": "停用舍曲林，单用CBT强化治疗",
      "D": "加用劳拉西泮 1mg tid",
      "E": "维持现有方案不变，继续观察6个月"
    },
    "explanation": {
      "correct_reason": "患者经足量SSRI（舍曲林200mg/d）+CBT治疗12周后Y-BOCS仅下降27%（<35%为部分有效），属于SSRI部分有效。此时标准策略为：加用非典型抗精神病药（如利培酮0.5-2mg/d、阿立哌唑）作为增效剂。多项RCT证实低剂量抗精神病药增效对SSRI抵抗的OCD有效。",
      "why_not_others": {
        "A": "正确选项：SSRI部分有效→加用低剂量非典型抗精神病药增效，是循证支持的下一线策略。",
        "B": "换用氯米帕明（TCA类）是可选策略但通常排在增效治疗之后。TCA副作用（抗胆碱能、心脏毒性）较SSRI更多，且患者对舍曲林已有部分反应，不应轻易放弃。",
        "C": "停药换单用CBT可能导致症状反弹。中重度OCD药物+CBT联合治疗优于单用CBT。",
        "D": "苯二氮䓬类仅用于急性焦虑，对强迫核心症状无效，长期使用有依赖和耐受风险。",
        "E": "12周足量治疗仅部分有效，不应继续维持不变。标准化策略是进一步升级治疗而非被动等待。"
      },
      "common_errors": "学生对OCD的阶梯治疗策略不熟悉：SSRI足量→部分有效→加用抗精神病药增效，而非直接换药或放弃药物治疗。"
    },
    "analysis_features": ["治疗方案比较与选择(OCD部分有效的增效策略)", "病程演变预测(治疗反应评估→策略升级)"],
    "design_rationale": {
      "A": "正确答案：SSRI部分有效→抗精神病药增效的标准策略",
      "B": "基于过早放弃部分有效的SSRI而换用副作用更大的TCA",
      "C": "基于忽略中重度OCD药物+CBT联合治疗优于单用CBT",
      "D": "基于使用无抗强迫作用的药物（苯二氮䓬）做增效",
      "E": "基于在部分有效时不升级治疗的消极策略"
    }
  },
  {
    "question_id": "batch026_M7_A4_001",
    "group_id": "A4_Group4_M7",
    "group_sequence": 1,
    "question_type": "A4",
    "polarity": "positive",
    "bloom_level": "分析",
    "source_anchors": ["batch026_analysis_supp", "教材《精神病学》第九章/P89-P94"],
    "source_pages": ["P89-P94"],
    "module_id": "M7",
    "module_name": "双相障碍",
    "priority_level": "掌握",
    "answer_key": "C",
    "option_polarities": {"A": False, "B": False, "C": True, "D": False, "E": False},
    "difficulty_index": 0.38,
    "discrimination_index": 0.52,
    "non_functioning_distractors": 0,
    "stem": "【病例组A4-1：第1题】患者女，35岁。丈夫陪诊诉最近2周完全变了一个人。患者近2周情绪极度不稳定，时而嚎啕大哭诉说话着没意思，时而暴怒摔东西骂人，精力异常旺盛、整夜不睡打扫卫生。言语凌乱跳跃，称脑子里想法太多太快根本停不下来。在诊室内坐立不安，时而流泪时而大笑。精神检查：情绪恶劣伴显著激越，思维奔逸，存在消极观念但无具体计划。既往史：5年前有产后抑郁史，服帕罗西汀3月缓解。家族史：父亲酗酒。最可能的诊断是：",
    "options": {
      "A": "抑郁障碍伴精神病性症状",
      "B": "边缘性人格障碍",
      "C": "双相I型障碍（混合发作）",
      "D": "分裂情感障碍（混合型）",
      "E": "躁狂发作伴抑郁症状"
    },
    "explanation": {
      "correct_reason": "患者同时满足躁狂发作标准（精力旺盛、睡眠需求减少、思维奔逸、言语增多）和抑郁发作标准（情绪低落、消极观念）≥1周，且每天大部分时间存在。DSM-5将这种情况称为伴混合特征的躁狂发作（即混合发作）。需注意混合发作不等同于快速循环（后者指≥4次发作/年）。混合发作预后更差、自杀风险更高。",
      "why_not_others": {
        "A": "患者有明显躁狂症状（思维奔逸、精力旺盛、睡眠需求减少），不符合单纯抑郁发作。",
        "B": "边缘性人格障碍心境波动通常数小时、与应激相关，伴有身份紊乱、空虚感、自伤等。本例为持续2周的类躁狂+抑郁混合状态，不符合。",
        "C": "正确选项：同时满足躁狂和抑郁发作标准→双相I型障碍混合发作。",
        "D": "分裂情感障碍要求精神病性症状（幻觉/妄想）在无心境发作期至少持续2周。本例无明显精神病性症状。",
        "E": "躁狂发作伴抑郁症状的描述不够准确。当抑郁症状达到重度抑郁发作标准时，应使用混合发作这一特定术语而非躁狂+抑郁症状。"
      },
      "common_errors": "混合发作是临床中容易被漏诊或误诊的类型。核心难点：认识到躁狂和抑郁症状可以同时而非交替出现。"
    },
    "analysis_features": ["鉴别诊断推理(混合发作vs单纯躁狂vs人格障碍)", "多因素综合分析(躁狂+抑郁症状的同时性判断)"],
    "design_rationale": {
      "A": "基于忽略躁狂症状的存在",
      "B": "基于将情绪不稳定误归为边缘性人格障碍",
      "C": "正确答案：躁狂+抑郁同时满足→双相I型混合发作",
      "D": "基于误判缺乏的精神病性症状",
      "E": "基于对混合发作术语的认知不足（症状需达发作标准而不仅是有症状）"
    }
  },
  {
    "question_id": "batch026_M7_A4_002",
    "group_id": "A4_Group4_M7",
    "group_sequence": 2,
    "question_type": "A4",
    "polarity": "positive",
    "bloom_level": "分析",
    "source_anchors": ["batch026_analysis_supp", "教材《精神病学》第九章/P95-P96"],
    "source_pages": ["P95-P96"],
    "module_id": "M7",
    "module_name": "双相障碍",
    "priority_level": "掌握",
    "answer_key": "D",
    "option_polarities": {"A": False, "B": False, "C": False, "D": True, "E": False},
    "difficulty_index": 0.45,
    "discrimination_index": 0.43,
    "non_functioning_distractors": 0,
    "stem": "【病例组A4-1：第2题·接上题】确诊双相I型混合发作后，需要启动急性期药物治疗。患者生命体征平稳，无躯体合并症。最合适的初始药物治疗方案为：",
    "options": {
      "A": "碳酸锂单药治疗",
      "B": "丙戊酸钠联合舍曲林",
      "C": "氟哌啶醇联合舍曲林",
      "D": "奥氮平联合丙戊酸钠",
      "E": "拉莫三嗪单药治疗"
    },
    "explanation": {
      "correct_reason": "混合发作对单用心境稳定剂（尤其锂盐）反应相对较差，常需联合治疗。丙戊酸盐对混合发作和快速循环型的疗效优于锂盐。奥氮平在混合发作中有明确疗效证据（教材P96：奥氮平治疗躁狂及混合发作的疗效优于安慰剂）。因此丙戊酸盐（心境稳定剂）+奥氮平（非典型抗精神病药）联合方案对混合发作是合理的初始策略。",
      "why_not_others": {
        "A": "碳酸锂对混合发作的疗效相对劣于经典躁狂，单药治疗可能不足。",
        "B": "混合发作中存在抑郁症状不应使用抗抑郁药（舍曲林），可能加重混合状态或诱发更严重的激越。",
        "C": "一代抗精神病药（氟哌啶醇）EPS风险高，且联合抗抑郁药可能加重病情。",
        "D": "正确选项：丙戊酸盐（对混合发作有效）+奥氮平（对混合发作有效的非典型抗精神病药）。",
        "E": "拉莫三嗪主要用于双相抑郁的维持治疗和预防抑郁复发，对急性躁狂/混合发作无效。"
      },
      "common_errors": "混合发作治疗的核心原则不同于经典躁狂：①抗抑郁药禁用；②单用锂盐可能不够；③丙戊酸盐在混合发作中地位高于锂盐。学生需区分纯躁狂vs混合发作的治疗差异。"
    },
    "analysis_features": ["治疗方案比较与选择(混合发作vs纯躁狂的治疗差异)", "多因素综合分析(症状类型+药物选择证据)"],
    "design_rationale": {
      "A": "基于将混合发作等同于纯躁狂治疗",
      "B": "基于在混合发作中错误使用抗抑郁药",
      "C": "基于一代药物+抗抑郁药的双重错误",
      "D": "正确答案：丙戊酸盐+奥氮平联合治疗混合发作",
      "E": "基于混淆拉莫三嗪的适应证（维持/抑郁预防vs急性期）"
    }
  },
  {
    "question_id": "batch026_M7_A4_003",
    "group_id": "A4_Group4_M7",
    "group_sequence": 3,
    "question_type": "A4",
    "polarity": "positive",
    "bloom_level": "分析",
    "source_anchors": ["batch026_analysis_supp", "教材《精神病学》第九章/P93-P97"],
    "source_pages": ["P93-P97"],
    "module_id": "M7",
    "module_name": "双相障碍",
    "priority_level": "掌握",
    "answer_key": "B",
    "option_polarities": {"A": False, "B": True, "C": False, "D": False, "E": False},
    "difficulty_index": 0.42,
    "discrimination_index": 0.45,
    "non_functioning_distractors": 0,
    "stem": "【病例组A4-1：第3题·接上题】患者经联合治疗后混合状态缓解，目前已稳定6周（丙戊酸盐+奥氮平维持）。患者询问药要吃多久？以后还会复发吗？关于长期管理的正确告知是：",
    "options": {
      "A": "维持治疗1年后如无复发可逐步停药",
      "B": "建议长期维持治疗，混合发作和快速循环型复发风险更高",
      "C": "奥氮平可在3个月后停用，单用丙戊酸盐维持即可",
      "D": "如能坚持规律心理治疗，药物可在半年后停用",
      "E": "维持治疗2年后无论情况如何均应停药评估"
    },
    "explanation": {
      "correct_reason": "教材P93：双相I型混合发作或快速循环型的预后更差。P97：如过去2年中每年均有一次以上发作，主张长期服用锂盐预防性治疗。混合发作是预后不良的危险因素，复发风险高于纯躁狂发作。双相障碍为慢性、易复发性疾病，维持治疗的理念是长期甚至终身治疗。",
      "why_not_others": {
        "A": "混合发作预后更差，1年后停药极易复发。维持治疗通常建议更长时间或终身。",
        "B": "正确选项：混合发作/快速循环型的复发风险更高，建议长期维持治疗。",
        "C": "过早停用奥氮平可能导致复发。联合方案有效的患者不应轻易减少药物种类。",
        "D": "心理治疗是辅助手段，不能替代药物治疗预防复发。双相障碍的生物学基础决定了药物治疗的核心地位。",
        "E": "对于反复发作的双相障碍患者，不建议为了评估而主动停药，这可能导致严重复发。"
      },
      "common_errors": "学生对双相障碍慢性病程和维持治疗长期性的认知不足，容易类比抑郁症的疗程化思维。需理解：双相障碍的维持治疗理念是预防复发而非治愈，尤其混合发作需更积极的长期管理。"
    },
    "analysis_features": ["病程演变预测(混合发作的长期预后)", "治疗方案比较与选择(维持治疗持续时间决策)"],
    "design_rationale": {
      "A": "基于对混合发作高复发风险的认知不足",
      "B": "正确答案：混合发作的高复发风险+长期维持治疗的必要性",
      "C": "基于过早简化有效联合方案",
      "D": "基于高估心理治疗在双相障碍预防复发中的作用",
      "E": "基于对慢性疾病停药评估的错误理念"
    }
  }
]

with open(r"C:\Users\38063\Desktop\MedAgentWork\中间产物\batch026_analysis\batch026_analysis_questions.json", "r", encoding="utf-8") as f:
    existing = json.load(f)
existing.extend(batch2)
with open(r"C:\Users\38063\Desktop\MedAgentWork\中间产物\batch026_analysis\batch026_analysis_questions.json", "w", encoding="utf-8") as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)
print(f"Batch 2 appended. Total: {len(existing)} questions")
