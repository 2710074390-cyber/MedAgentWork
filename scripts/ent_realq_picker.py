# -*- coding: utf-8 -*-
"""ent_realq_picker.py — 耳鼻咽喉头颈外科学真题专项选题器（HC-23 真题检索 v3 扩展）。

背景
----
`scripts/real_question/sources.py` 的学科分类器按「关键词命中数 ≥ 3」打标签，
而 ENT 真题大量落在 `zhiyi_pdf` 的「未分类」桶里（2024 册 4879 条未分类，
其中含大量耳鼻喉题），导致 `real_question_cli.py plan --subject 耳鼻咽喉头颈外科学`
只能捞到 119 条。本模块改用**专用 ENT 词库 + 域归属打分**做归类，
不依赖通用 subject 字段。

产物
----
- `pick`：从三源索引（kaoyan / zhiyi_pdf / zhiyi）分层选出 N 道 ENT 真题
- 配比：考研族与执业医师族双轨；执业医师族内 `zhiyi_pdf`（历年真题扫描册）优先、
  `zhiyi`（CMExam）补位（HC-23）
- 每题输出 ENT 域归属、命中词、溯源信息，供人工逐题复核

用法
----
    python scripts/ent_realq_picker.py pick --target 100 \
        --out 中间产物/batch042/ent_realq_plan.json
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from real_question.schema import RealQuestion, read_jsonl

BASE = Path(__file__).resolve().parent.parent
DEFAULT_INDEX_DIR = BASE / "question_bank" / "real_questions"

# ──────────────────────────────────────────────────────────────
# ENT 专用词库
# ──────────────────────────────────────────────────────────────
# tier 3 = ENT 专有解剖/术式/疾病名（命中即可判定属科）
# tier 2 = 强相关临床名词（需 tier3 或 tier2×2 同时出现）
# tier 1 = 弱相关词（仅计分，不单独定科；易与非 ENT 科重叠）

TIER3 = {
    "耳": [
        "咽鼓管", "鼓膜", "乳突", "耳蜗", "半规管", "鼓室", "听骨", "镫骨", "锤骨", "砧骨",
        "耵聍", "耳石", "耳石症", "耳廓", "耳郭", "耳道", "外耳道", "中耳", "内耳",
        "鼓窦", "鼓膜穿刺", "鼓室注射", "镫骨肌", "耳蜗电图", "耳声图", "耳镜", "耳内镜",
        "鼓膜切开", "乳突根治", "乳突凿开", "鼓膜置管", "耳气压", "耵聍栓塞",
        "梅尼埃", "美尼尔", "喉迷路", "耳蜗神经", "突发性耳聋", "特发性突聋",
    ],
    "鼻": [
        "鼻窦", "鼻甲", "鼻中隔", "鼻息肉", "鼻泪管", "鼻前庭", "蝶窦", "筛窦", "额窦",
        "上颌窦", "鼻咽", "鼻腔", "鼻漏", "鼻疖", "鼻窦炎", "变应性鼻炎", "鼻过敏",
        "鼻内镜", "鼻中隔矫正", "鼻后孔", "鼻窦镜", "鼻用减充血", "鼻出血",
    ],
    "咽": [
        "扁桃体", "腺样体", "腭扁桃体", "咽旁间隙", "扁桃体周围脓肿", "悬雍垂", "口咽",
        "下咽", "梨状窝", "咽后间隙", "咽峡", "鼻咽部", "扁桃体炎", "腺样体肥大",
        "扁桃体切除", "腺样体切除", "咽异感症", "扁桃体周围脓肿",
    ],
    "喉": [
        "喉癌", "声带息肉", "声带小结", "声门型", "喉阻塞", "喉梗阻", "喉水肿", "喉炎",
        "会厌炎", "喉返神经", "喉上神经", "声带", "声门", "声嘶", "喉镜", "纤维喉镜",
        "喉气管", "喉癌根治", "全喉切除", "部分喉切除", "喉部", "喉囊肿", "喉结核",
        "喉乳头状瘤", "喉狭窄", "气管切开",
    ],
    "头颈": [
        "颈淋巴结结核", "颈部肿块", "颈部包块", "腮腺", "颌下腺", "鼻咽癌",
        "颈部淋巴结", "腮腺炎", "腮腺肿瘤", "颈动脉体瘤", "迷走神经鞘瘤",
        "颈部肿物", "颈淋巴结", "肌性斜颈", "先天性肌性斜颈", "胸锁乳突肌",
        "甲状舌管囊肿", "鳃裂瘘", "第二鳃裂", "颈部皮样", "囊性淋巴管瘤",
        "甲状旁腺",
    ],
}

TIER2 = {
    "耳": [
        "眩晕", "前庭", "听力", "助听器", "耳鸣", "传导性聋", "感音神经性聋", "混合性聋",
        "耳蜗功能", "声导抗", "纯音测听", "耳声发射", "鼓室图", "耳镜检查", "耳部",
        "听觉", "平衡功能", "眼震", "位置性眩晕", "突发性耳聋", "特发性突聋", "耳痛",
        "骨传导", "气传导", "声波", "听阈", "眼震颤", "加速度", "旋转", "耳石",
        "壶腹嵴", "囊斑", "神经性耳鸣", "感音性耳聋", "传导性耳聋", "耳漏", "耳流脓",
    ],
    "鼻": [
        "鼻塞", "鼻涕", "喷嚏", "嗅觉", "鼻出血", "鼻甲肥大", "鼻息肉样", "鼻窦开口",
        "鼻窦炎", "鼻窦CT", "鼻内镜手术", "蝶筛窦", "鼻翼", "鼻道", "减充血药",
    ],
    "咽": [
        "咽痛", "咽部不适", "异物感", "吞咽痛", "吞咽困难", "扁桃体", "腺样体",
        "咽部检查", "间接喉镜", "咽反射", "咽部", "扁桃体炎", "腺样体肥大",
    ],
    "喉": [
        "喉部不适", "声音嘶哑", "呼吸困难", "吸气性", "喘鸣", "三凹征", "吸气困难",
        "发声", "嗓音", "喉部检查", "气管切开", "喉水肿", "喉梗阻", "喉鸣",
    ],
    "头颈": [
        "颈部", "颈侧", "淋巴结", "浅表淋巴结", "甲状腺肿", "颈部包块", "头颈部",
        "颈部肿物", "斜颈",
    ],
}

TIER1 = {
    "耳": ["颞", "岩部", "乳突", "镫", "耳", "听力", "前庭"],
    "鼻": ["鼻"],
    "咽": ["咽", "腭"],
    "喉": ["喉", "声带"],
    "头颈": ["颈", "甲状腺", "颌下", "腮腺"],
}

DOMAINS = ["耳", "鼻", "咽", "喉", "头颈"]

# 与 ENT 无关但常共现的干扰词：命中则降权（避免把内科/儿科题算成 ENT）
NEGATIVE = [
    "鼻翼煽动", "鼻翼", "鼻尖", "鼻翼部", "护理", "口腔护理", "会阴", "会厌反射",
]


@dataclass
class EntHit:
    domain: str = ""
    score: float = 0.0
    terms: list[str] = field(default_factory=list)
    tier3: bool = False


def classify_ent(stem: str, options: list[str], explanation: str = "") -> EntHit | None:
    """判定一题是否属耳鼻咽喉头颈外科学，并给出域归属。

    判定链：
      1. **题干**命中任一 tier3 词 → 判定属科，域 = 命中 tier3 最多的域
      2. **题干**命中某域 tier2 ≥ 2 个 → 判定属科
      3. 选项里出现 ENT 词 → 只作干扰项线索，**不足以定科**
         （典型陷阱：「短暂性脑缺血发作 vs 梅尼埃病」，考的是 TIA 不是 ENT）
      4. 解析命中 ENT 词但题干无 → 不算（其他科题目解析提到 ENT）
    """
    main = (stem or "").replace(" ", "")
    opt = " ".join([str(o) for o in (options or [])]).replace(" ", "")
    best = EntHit()

    for dom in DOMAINS:
        t3 = [w for w in TIER3.get(dom, []) if w in main]
        t2 = [w for w in TIER2.get(dom, []) if w in main]
        t1 = [w for w in TIER1.get(dom, []) if w in main]
        if not (t3 or t2 or t1):
            continue
        sc = len(t3) * 3.0 + len(t2) * 1.0 + len(t1) * 0.2
        if t3:
            sc += 2.0
        if len(t2) >= 2 and not t3:
            sc += 1.5
        # 跨域判定：主文只命中 1 域的 tier1 弱词（单字）→ 视为噪声
        if not t3 and len(t2) < 2:
            sc = min(sc, 0.5)
        if sc > best.score:
            best = EntHit(
                domain=dom,
                score=round(sc, 3),
                terms=sorted(set(t3 + t2 + t1)),
                tier3=bool(t3),
            )

    if best.score < 2.0:
        return None
    for neg in NEGATIVE:
        if neg in main and best.tier3 is False:
            return None
    # ③ 跨科过滤
    if _hard_noise(main):
        return None
    if _cross_domain_noise(main, best) and not _is_ent_clinical(main, best.domain):
        return None
    return best


# 明确属于非 ENT 科室、但常含 ENT 关键词的语境
NOISE_PATTERNS = [
    # 神经内科 / 骨科（颈椎病、椎动脉）
    (["颈椎病", "椎动脉", "椎间孔", "神经根型", "脊髓型"], ["眩晕", "耳鸣", "耳聋", "听力"]),
    # 精神科 / 药理（药物不良反应）
    (["镇静催眠", "苯二氮", "安眠药"], ["耳鸣", "耳聋", "听力", "眩晕"]),
    # 血液科（ITP、血小板、凝血）
    (["ITP", "血小板减少", "紫癜", "凝血", "血友病", "再生障碍性贫血", "骨髓增生",
      "骨髓细胞学", "MPO", "DIC", "肝硬化", "血友病"],
     ["鼻出血", "牙龈出血", "耳鸣", "耳聋"]),
    # 口腔颌面外科（拔牙、上颌窦瘘）
    (["拔牙", "牙髓", "牙根", "牙槽窝", "腭根", "牙冠", "上颌骨全切", "植皮"],
     ["上颌窦", "鼻腔", "鼻窦"]),
    # 呼吸科 / 哮喘
    (["支气管哮喘", "哮鸣音", "吸入糖皮质激素", "喘息", "咳喘"], ["三凹征", "吸气性", "喉鸣", "声嘶"]),
    # 普外 / 内分泌（甲状腺疾病归普外，不属 ENT 头颈）
    (["甲状腺结节", "甲状腺肿块", "甲状腺癌", "甲状腺乳头状癌", "甲状腺滤泡癌",
      "甲状腺功能", "甲亢", "甲巯咪唑", "弥漫性甲状腺肿", "甲状腺危象"],
     ["颈部", "颈淋巴结", "咽部", "吞咽"]),
    # 心血管内科
    (["硝酸甘油", "胸部闷胀", "心绞痛", "心电图"], ["咽喉", "吞咽", "声嘶"]),
    # 风湿免疫
    (["环形红斑", "游走性疼痛", "风湿热", "心内膜炎"], ["扁桃体", "咽峡炎"]),
    # 口腔颌面外科（解剖标志、智齿、拔牙、间隙感染）——该科语境明确，整体判非 ENT
    (["切牙乳突", "智牙", "智齿", "上颌磨牙", "下颌磨牙", "牙槽突", "面中部凹陷",
      "颌下间隙", "咬肌间隙", "翼下颌间隙", "颊间隙", "颞间隙", "口底",
      "牙髓治疗", "牙槽窝", "腭根", "牙冠碎裂", "分根", "上颌骨全切", "游离植皮",
      "牙周", "龋齿", "牙髓", "正畸", "种植体"],
     ["乳突", "外耳道", "颈部", "腮腺", "下鼻甲", "上颌窦", "鼻腔", "咽部", "喉"]),
    # 泌尿外科
    (["膀胱", "前列腺", "尿道", "肾结石", "输尿管"], ["颈部", "咽部", "鼻腔", "喉"]),
    # 呼吸科肿瘤 / 肺科
    (["肺鳞癌", "肺腺癌", "肺癌", "支气管肺癌", "肺结核", "肺脓肿"],
     ["颈部", "咽部", "鼻腔", "喉"]),
    # 甲状腺本身归普外/内分泌，不属 ENT 头颈
    (["甲状腺"], ["颈部", "颈淋巴结", "咽部", "吞咽", "喉"]),
    # 心血管内科（心绞痛放射至咽喉）
    (["硝酸甘油", "心绞痛", "胸部闷胀", "心电图", "心内膜炎"], ["咽喉", "咽部", "吞咽", "声嘶"]),
    # 儿科传染病（猩红热、手足口、水痘）——题干出现即整题判儿科
    (["草莓舌", "麻疹", "猩红热", "手足口", "水痘", "风疹", "皮疹"],
     ["扁桃体", "咽部", "咽峡", "咽痛", "发热"]),
    # 感染性心内膜炎（心内科）
    (["感染性心内膜炎", "心力衰竭", "血培养"], ["扁桃体", "咽部", "咽峡"]),
    # 呼吸科肿瘤
    (["肺癌", "肺鳞癌", "肺腺癌", "支气管肺癌"], ["颈部", "咽部", "鼻腔", "喉"]),
    # 神经外科 / 颅脑（脑出血、脑梗、小脑、共济失调）
    (["脑出血", "脑梗", "小脑", "脑桥", "基底节", "枕叶", "蛛网膜下腔", "脑电图",
      "脑脊液检查", "脑部CT", "指鼻", "跟膝胫", "共济失调", "颅内出血", "短暂性脑缺血"],
     ["眩晕", "耳鸣", "耳聋", "听力", "鼻出血"]),
    # 呼吸科 / 传染病
    (["肺脓肿", "肺炎", "支气管", "肺结核", "脑膜炎", "流脑", "乙脑", "钩端螺旋体"],
     ["中耳", "鼻窦", "乳突", "耳鸣", "耳聋", "听力"]),
    # 单纯生理学听力学（教材生理章节，非 ENT 临床）
    (["感受器", "换能", "行波", "微音器", "螺旋器", "柯蒂"], ["耳蜗", "前庭"]),
    # 眼科 / 口腔
    (["眼球", "角膜", "晶状体", "视网膜", "视力", "视野", "眼压", "瞳孔"],
     ["鼻泪", "鼻前庭"]),
    # 单纯颅底骨折归神经外科（但保留伴耳漏/鼻漏者）
    (["颅底骨折", "熊猫眼", "颞骨骨折", "颅前窝", "颅中窝", "颅后窝"],
     ["鼓膜", "中耳", "乳突", "听骨", "耳蜗", "前庭", "梅尼埃"]),
]


# 硬排除：出现即判非 ENT，不给任何豁免（这些科室语境与 ENT 无交集）
HARD_NOISE = [
    # 口腔颌面外科
    ["切牙乳突", "智牙", "智齿", "上颌磨牙", "下颌磨牙", "牙槽突", "面中部凹陷",
     "颌下间隙", "咬肌间隙", "翼下颌间隙", "颊间隙", "颞间隙", "牙髓治疗",
     "牙槽窝", "腭根", "牙冠碎裂", "分根", "牙周", "龋齿", "牙髓", "正畸", "种植体",
     "腭裂", "牙合", "游离植皮", "下颌下腺", "颌下区", "咬肌", "磨牙后区",
     "下颌支", "颌下手术", "颊肌"],
    # 心血管内科
    ["硝酸甘油", "心绞痛", "心电图示", "感染性心内膜炎", "主动脉瓣", "二尖瓣",
     "心房颤动", "室性早搏", "P₂亢进", "三尖瓣", "肝颈回流征", "洋地黄"],
    # 神经内科
    ["短暂性脑缺血", "脑梗死", "小脑半球", "脑桥", "基底节区", "脑电图", "肌电图",
     "共济失调", "指鼻试验", "跟膝胫试验", "吉兰-巴雷", "格林巴利", "多发性硬化"],
    # 呼吸内科
    ["支气管哮喘", "肺源性心脏病", "慢性阻塞性肺", "肺间质", "胸腔积液", "肺结核",
     "肺脓肿", "肺穿刺", "支气管扩张", "肺癌", "肺鳞癌", "肺腺癌", "吸入糖皮质激素"],
    # 儿科传染病
    ["草莓舌", "麻疹", "猩红热", "手足口", "水痘", "风疹", "幼儿", "小儿肺炎"],
    # 血液 / 泌尿
    ["紫癜", "血小板减少", "血友病", "再生障碍性贫血", "膀胱", "前列腺", "肾结石"],
    # 内分泌 / 普外（甲状腺本身不属 ENT 头颈范围）
    ["甲状腺功能", "甲巯咪唑", "弥漫性甲状腺肿", "甲状腺危象", "甲状腺结节",
     "甲状腺肿块", "甲状腺癌", "甲状腺乳头状癌", "甲状腺滤泡癌", "冷结节"],
]


# 人工复核排除清单：自动规则筛不掉的边界题，逐题定夺后固定排除。
# key = 题干前 40 字（归一化），value = 排除理由。
MANUAL_EXCLUDE = {
    # 口腔颌面外科（拔牙后上颌窦瘘的处理属口腔科）
    "拔除上颌第一磨牙时牙根完整拔除但上颌窦有直径约8mm穿孔": "口腔颌面外科",
    "拔除上颌第一磨牙时牙根完整拔除但上颌窦有直径约4mm大小的穿孔": "口腔颌面外科",
    "拔除上颌第一磨牙时牙根完整拔除拔牙后发现口腔上颌窦瘘": "口腔颌面外科",
    "拔除上颌磨牙时牙根完整的拔除拔牙后发现口腔上颌窦瘘": "口腔颌面外科",
    # 甲状旁腺激素分泌调节 / 甲旁亢 / 甲旁腺单独损伤 → 属内分泌科，非 ENT 头颈
    "甲状旁腺激素的分泌调节形式是": "甲状旁腺归内分泌",
    "下列关于甲状旁腺功能亢进的叙述错误的是": "甲状旁腺归内分泌",
    "甲状旁腺损伤": "甲状旁腺归普外",
    "女性27岁右颈部肿物伴低热2周抗生素治疗无效经查体临床诊断为亚急性甲状腺炎": "甲状腺归内分泌",
    # 血液/淋巴瘤（颈部淋巴结只是表现，病种属血液科）
    # 呼吸科 / 其它
    "男性56岁低热盗汗伴咳嗽咳痰2月余既往吸烟30年": "呼吸科",
    "男性16岁低热咳嗽咽部不适2周胸部X线片示两肺下部网状": "呼吸科",
    "女38岁进食后胸骨后疼痛伴暖气1年加重1周偶有吞咽痛": "消化内科",
    # 内分泌/普外（颈部肿物随吞咽移动=甲状腺）
    "女性40岁发现颈部肿物伴疼痛3天就诊查体左颈前可触及直径3cm肿物": "甲状腺肿物归普外",
    "女55岁体检发现颈部包块3个月查体气管右侧可扪及一质硬结节": "甲状腺归普外",
    "患者女45岁颈部肿块轻度疼痛生长迅速坚硬表面不平推之不动随吞咽": "甲状腺归普外",
    # 医患沟通/伦理（考点不在 ENT 专业知识）
    "女性34岁突发耳鸣1天到医院诊治经检查被诊断为神经性耳鸣医生很快给患者开": "考点为医患沟通非ENT专业",
    "女童5岁因发热伴腮腺部位肿痛到急诊就诊父亲急切地对医生说": "考点为医患沟通非ENT专业",
    "某男性患者26岁在准备结婚过程中连续多日劳累患化脓性扁桃体炎医生在其诊治": "考点为母婴保健法非ENT专业",
    # 神经内科
    "女60岁有高血压病史突然出现双下肢无力倒地随即自行站起": "短暂性脑缺血属神经内科",
    "男15岁四肢无力3天伴吞咽困难1天大小便正常1周前腹泻2次": "吉兰巴雷属神经内科",
    # 肾内科（扁桃体炎后肾炎，ENT 仅为诱因）
    "8岁患儿2周前患扁桃体炎近2天发现眼脸及下肢水肿查体显示血压150/110mmHg": "肾小球肾炎属肾内科",
    "男性32岁一周前扁桃体炎近3天出现水肿红细胞尿": "肾小球肾炎属肾内科",
    "患儿7岁2周前患咽峡炎1天前发现颜面部水肿": "肾小球肾炎属肾内科",
    # 血液科（淋巴瘤 / 白血病 / 霍奇金）
    "男性65岁无痛性双颈部淋巴结进行性肿大半个月到医院行淋巴结活检病理发现淋": "淋巴瘤属血液科",
    "男性20岁发热颈部淋巴结肿大伴疼痛1月余就诊于我院体检发现双侧颈部及腹股沟淋": "淋巴瘤属血液科",
    "女25岁右颈部淋巴结肿大1个月无发热淋巴结活检提示弥漫性B细胞淋巴瘤": "淋巴瘤属血液科",
    "男55岁颈部淋巴结进行性肿大2个月发热2周发病以来体重减轻14kg": "淋巴瘤属血液科",
    "女59岁右颈部淋巴结肿大3个月蚕豆大小其可能性最小的病变是": "颈部淋巴结属血液科",
    "男36岁双侧颈部淋巴结肿大伴发热1周查体T38.4℃": "淋巴瘤属血液科",
    "男性32岁右颈部无痛性淋巴结肿大半个月发热1周": "颈部淋巴结属血液科",
    "男36岁5天前发热咽疼应用抗生素治疗无效颈部浅表淋巴结肿大咽部充血扁桃体Ⅱ°肿大": "白血病属血液科",
    "女性20岁病史10天发热贫血出血肝脾轻度肿大颈部淋巴结肿大伴关节痛": "白血病属血液科",
    "男18岁发热伴颈部淋巴结进行性无痛性肿大3个月最高体温38.7℃": "淋巴瘤属血液科",
    "女10岁颈淋巴结肿大2周活检示淋巴结结构破坏可见R-S细胞": "霍奇金淋巴瘤属血液科",
    "皮肤结节性红斑疱疹性结膜炎多发性一过性关节炎颈淋巴结肿大常见于": "Still病属儿科风湿",
    # 儿科（传染病 / 免疫 / 肺炎）
    "男8个月反复感染淋巴组织中查不到mIg阳性细胞无生发中心扁桃体小": "儿科免疫缺陷",
    "男孩4岁发热2天皮疹1天伴咽部疼痛查体T39.2℃": "儿科传染病",
    "女孩3岁咳嗽5天发热2天查体咽红双侧扁桃体Ⅰ度肿大双肺可闻及较固定的中细湿啰音": "儿科肺炎",
    "某患儿女5岁低度发热口咽部疼痛口腔黏膜牙龈咽部嘴唇以及手和脚后跟边缘": "手足口病属儿科",
    "3男性16岁低热咳嗽咽部不适2周胸部X线片示两肺下部网状": "呼吸科",
    # 心内科（扁桃体炎后感染性心内膜炎）
    "20岁某青年摘除扁桃体后发热出现心力衰竭采血培养细菌血平板有草绿色溶血环": "感染性心内膜炎属心内科",
    # 口腔科
    "口腔癌中最易发生颈部淋巴结转移的是": "口腔癌属口腔科",
    # 普外甲状腺
    "男性30岁颈部包块6个月查体甲状腺右叶可触及直径2cm质硬结节": "甲状腺归普外",
    "女35岁颈部肿块4年余随吞咽上下移动近3个月肿块增大明显手术切除后病理诊断": "甲状腺归普外",
    "影响甲状旁腺激素分泌最重要的因素是": "甲状旁腺归内分泌",
    "甲状旁腺激素对血钙的调节主要是通过": "甲状旁腺归内分泌",
    # 儿科风湿（Still 病）
    "5岁男孩低热干咳皮肤结节性红斑疱疹性结膜炎多发性一过性关节炎及颈淋巴结肿大": "Still病属儿科风湿",
    # 口腔颌面外科：下颌下腺 / 颌下区 / 咬肌间隙
    "怀疑下颌下腺导管阳性结石首选检查方法是": "下颌下腺属口腔颌面外科",
    "男性43岁左侧下颌下区反复肿胀3个月检查左侧下颌下腺肿大": "下颌下区属口腔颌面外科",
    "位于咬肌与下颌支之间前界为磨牙后区黏膜后界为腮腺的是": "咬肌间隙属口腔颌面外科",
    "18岁男性右颌下区无痛性质软肿物发现三月": "颌下区属口腔颌面外科",
    "男43岁左侧下颌下区反复肿胀3个月": "颌下区属口腔颌面外科",
    # 风湿免疫 / 血液 / 新生儿 / 麻疹 / 甲状旁腺
    "患者女18岁2周前患扁桃体炎近日心悸气短发热出汗踝膝关节游走性疼痛": "风湿热属风湿免疫",
    "男21岁患急性白血病半个月化疗期间出现皮肤瘀斑": "白血病属血液科",
    "早产儿孕龄32自然分娩出生后2小时出现呼吸困难": "新生儿呼吸窘迫属儿科",
    "女孩4岁发热咳流涕4天发疹1天体温39.5°C": "麻疹属儿科传染病",
    "主要调节甲状旁腺激素分泌的因素是": "甲状旁腺归内分泌",
    "男性30岁颈部包块6个月查体甲状腺右叶可触及直径2cm质硬结节": "甲状腺归普外",
}


def _manual_exclude(stem: str) -> str:
    """按题干前缀匹配人工排除清单，返回排除理由（未排除返回空串）。"""
    key = re.sub(r"[^一-鿿A-Za-z0-9]", "", stem or "")[:40]
    for prefix, reason in MANUAL_EXCLUDE.items():
        if key.startswith(re.sub(r"[^一-鿿A-Za-z0-9]", "", prefix)[:40]):
            return reason
    return ""


def _hard_noise(main: str) -> bool:
    for ctx in HARD_NOISE:
        if any(c in main for c in ctx):
            return True
    return False


def _cross_domain_noise(main: str, hit: EntHit) -> bool:
    """判断是否属于「ENT 词只是陪衬」的跨科题。

    规则：命中「非 ENT 语境词」时，若该语境属于明确的独占科室，则直接判噪声。
    （药理、病理等语境中 ENT 词常是唯一考点，需靠 tier3 + 临床语境放行。）
    """
    for ctx, ent_words in NOISE_PATTERNS:
        if any(c in main for c in ctx) and any(w in main for w in ent_words):
            return True
    return False


# ENT 语境放行词：题中同时出现这些词，说明确属 ENT 临床题，可豁免跨科噪声判定
ENT_CLINICAL_CONTEXT = {
    "耳": [
        "耳科", "耳镜", "耳内镜", "鼓膜", "咽鼓管", "中耳", "乳突", "鼓室", "听骨",
        "镫骨", "锤骨", "砧骨", "耳蜗", "半规管", "前庭", "外耳道", "耳道", "耳郭",
        "耳廓", "耵聍", "耳石", "梅尼埃", "耳聋", "耳鸣", "鼓膜穿刺", "鼓膜切开",
        "乳突根治", "鼓膜置管", "耳声图", "耳蜗电图", "感音神经性聋", "传导性聋",
        "突发性耳聋", "特发性突聋", "神经性耳鸣", "鼓膜炎", "中耳炎",
    ],
    "鼻": [
        "鼻科", "鼻窦", "鼻甲", "鼻中隔", "鼻息肉", "鼻泪管", "鼻前庭", "蝶窦",
        "筛窦", "额窦", "上颌窦", "鼻咽", "鼻腔", "鼻内镜", "鼻窦镜", "鼻后孔",
        "鼻窦炎", "变应性鼻炎", "鼻过敏", "鼻漏", "鼻疖", "鼻部检查",
    ],
    "咽": [
        "扁桃体", "腺样体", "腭扁桃体", "咽旁", "扁桃体周围脓肿", "悬雍垂",
        "口咽", "下咽", "梨状窝", "咽后间隙", "咽峡", "鼻咽部", "扁桃体炎",
        "腺样体肥大", "扁桃体切除", "腺样体切除", "咽部检查", "间接喉镜",
    ],
    "喉": [
        "喉科", "喉镜", "纤维喉镜", "声带", "声门", "喉癌", "喉阻塞", "喉梗阻",
        "喉水肿", "喉炎", "会厌炎", "喉返神经", "喉上神经", "喉部检查", "气管切开",
        "气管异物", "食管异物", "声嘶", "喉鸣", "喉结核", "喉乳头状瘤", "喉狭窄",
    ],
    "头颈": [
        "头颈外科", "颈部肿块", "颈部包块", "颈部肿物", "颈部淋巴结", "颈淋巴结",
        "颈淋巴结结核", "甲状舌管囊肿", "鳃裂瘘", "第二鳃裂", "颈动脉体瘤",
        "肌性斜颈", "先天性肌性斜颈", "腮腺", "颌下腺", "鼻咽癌",
    ],
}


def _is_ent_clinical(main: str, domain: str = "") -> bool:
    """该域是否有 ENT 专属语境词。

    `domain` 非空时只查该域的词，避免"题里某处提到中耳"就整体放行跨科题。
    """
    doms = [domain] if domain else list(ENT_CLINICAL_CONTEXT)
    for dom in doms:
        if any(w in main for w in ENT_CLINICAL_CONTEXT.get(dom, [])):
            return True
    return False


# ──────────────────────────────────────────────────────────────
# 答案自洽性校验
# ──────────────────────────────────────────────────────────────
# 贺银成解析里常写「故答X」「答案为X」，可与存储的答案键交叉比对。
# 两者矛盾说明答案键存错（或解析与答案错位），该题不进题库。
ANSWER_PHRASES = [
    re.compile(r"故答\s*([A-E]{1,5})(?![A-E])"),
    re.compile(r"答案为\s*([A-E]{1,5})(?![A-E])"),
    re.compile(r"答案\s*[是为:：]\s*([A-E]{1,5})(?![A-E])"),
    re.compile(r"故选\s*([A-E]{1,5})(?![A-E])"),
    re.compile(r"应选\s*([A-E]{1,5})(?![A-E])"),
    re.compile(r"本题选\s*([A-E]{1,5})(?![A-E])"),
    re.compile(r"正确选项\s*[是为:：]?\s*([A-E]{1,5})(?![A-E])"),
    re.compile(r"正确答案\s*[是为:：]?\s*([A-E]{1,5})(?![A-E])"),
]


def check_answer_consistency(item: RealQuestion) -> tuple[bool, str]:
    """用解析里的显式答案短语校验存储答案键。

    返回 (是否自洽, 证据描述)。无显式短语时视为无法校验 → 自洽。
    """
    text = item.explanation or ""
    if not text:
        return True, "no_explanation"
    for pat in ANSWER_PHRASES:
        hits = [m.group(1) for m in pat.finditer(text)]
        if not hits:
            continue
        # 多处命中时取众数
        norm = sorted({h for h in hits})
        if len(norm) == 1:
            implied = norm[0]
            if implied == item.answer:
                return True, f"解析自证 {implied}"
            return False, f"答案键冲突：存储={item.answer} 解析={implied}"
        # 解析里出现多个不同答案（跨题引用），无法判定 → 放过
        return True, "解析含多答案引用，放过"
    return True, "no_explicit_phrase"


# ──────────────────────────────────────────────────────────────
# 候选池构建
# ──────────────────────────────────────────────────────────────

def load_pool(index_dir: Path) -> list[RealQuestion]:
    items: list[RealQuestion] = []
    for name in ("kaoyan_items.jsonl", "zhiyi_pdf_items.jsonl", "zhiyi_items.jsonl"):
        p = index_dir / name
        if p.exists():
            items.extend(read_jsonl(p))
    return items


# 题号前缀残留（如 "2.男婴，4个月…"）——解析层未剥净，需剥离
LEADING_QNO = re.compile(r"^\s*(\d{1,3})\s*[\.、]\s*")
# 跨题粘连标志：出现即说明该题把下一题/下一单元的内容吞进来了
BLEED_MARKERS = [
    "题共用题干", "共用题干", "题共用", "答案:", "答案：", "【答案】", "【解析】",
    "A2 型选择题", "A1型选择题", "A2型题", "每一道考题下面",
]
# 题干残缺标志：句子未闭合
BROKEN_END = re.compile(r"[（(][^）)]{0,3}$")


def _strip_leading_qno(stem: str) -> str:
    return LEADING_QNO.sub("", stem).strip()


def _text_ok(item: RealQuestion) -> bool:
    """过滤 OCR 残缺 / 串题 / 粘连题。

    三道闸门：
      ① 结构完整性（题干不过长、括号闭合、无跨题粘连标志、无残句）
      ② 选项完整性（无超长串题选项、选项无重复、无下一题题号残留）
      ③ 答案合法性（字母、范围、单多选型匹配）
    """
    stem = _strip_leading_qno((item.stem or "").strip())
    if len(stem) < 6:
        return False
    # ① 题干过长 = 版面重建把多题吞成一段（实测有 269 字题干）
    if len(stem) > 180:
        return False
    # 括号闭合
    if stem.count("（") != stem.count("）") and stem.count("(") != stem.count(")"):
        return False
    # 跨题粘连标志
    if any(m in stem for m in BLEED_MARKERS):
        return False
    # 残句收尾
    if BROKEN_END.search(stem):
        return False
    # 题干内嵌大段选项（题干里出现 A. B. C. 等连排）
    if len(re.findall(r"[A-E][\.、）)]", stem)) >= 3:
        return False

    # ② 选项
    if not item.options or len(item.options) < 4:
        return False
    for o in item.options:
        if len(o) > 60:
            return False
        if any(m in o for m in BLEED_MARKERS):
            return False
        if LEADING_QNO.match(o):
            return False
    if len({o.strip() for o in item.options}) < 4:
        return False
    if len(item.options) > 5:
        return False

    # ③ 答案
    if not item.answer or not all(c in "ABCDE" for c in item.answer):
        return False
    if max(ord(c) - 64 for c in item.answer) > len(item.options):
        return False
    if len(item.answer) > 1 and item.question_type not in ("X", "B1"):
        return False
    return True


@dataclass
class Candidate:
    item: RealQuestion
    ent: EntHit
    source_file: str = ""
    explain_len: int = 0


def build_candidates(items: list[RealQuestion]) -> list[Candidate]:
    out: list[Candidate] = []
    rejected_answer = 0
    for it in items:
        if not it.selectable:
            continue
        if it.answer_confidence not in ("high", "medium"):
            continue
        if it.license not in ("public", "public_noncommercial"):
            continue
        if not _text_ok(it):
            continue
        ok, _evidence = check_answer_consistency(it)
        if not ok:
            rejected_answer += 1
            continue
        if _manual_exclude(it.stem):
            continue
        hit = classify_ent(it.stem, it.options, it.explanation)
        if hit is None:
            continue
        out.append(Candidate(item=it, ent=hit, explain_len=len(it.explanation or "")))
    build_candidates.last_rejected_answer = rejected_answer  # type: ignore[attr-defined]
    return out


# ──────────────────────────────────────────────────────────────
# 选题
# ──────────────────────────────────────────────────────────────

SOURCE_FAMILY = {"kaoyan": "kaoyan", "zhiyi_pdf": "zhiyi", "zhiyi": "zhiyi"}
FAMILY_NAME = {"kaoyan": "考研", "zhiyi": "执业医师"}
TIER_NAME = {"kaoyan": "考研真题(306西综)", "zhiyi_pdf": "执业医师历年真题(扫描册)",
             "zhiyi": "CMExam执业医师题库"}


def _score(c: Candidate) -> tuple:
    """排序键：域特异性 → 答案可信度 → 年份 → 解析完整度。"""
    it = c.item
    tier = {"zhiyi_pdf": 3, "kaoyan": 2, "zhiyi": 1}.get(it.source, 0)
    return (
        round(c.ent.score, 2),
        1 if it.answer_confidence == "high" else 0,
        it.year or 0,
        min(c.explain_len, 400),
        tier,
    )


def pick(
    index_dir: Path,
    target: int,
    domain_weights: dict[str, float] | None = None,
    kaoyan_cap: int | None = None,
    out_path: str | Path | None = None,
) -> dict:
    items = load_pool(index_dir)
    cands = build_candidates(items)

    # 域配额
    weights = domain_weights or {"耳": 0.30, "鼻": 0.22, "咽": 0.16, "喉": 0.20, "头颈": 0.12}
    dom_target = {}
    for dom, w in weights.items():
        dom_target[dom] = max(1, round(target * w))
    diff = target - sum(dom_target.values())
    order = sorted(dom_target, key=lambda d: -dom_target[d])
    i = 0
    while diff != 0:
        dom_target[order[i % len(order)]] += 1
        diff += -1 if diff > 0 else 1
        i += 1
        if i > 1000:
            break

    # 族上限：考研族取可用上限（西综无 ENT 独立科目），执医族不限
    by_dom: dict[str, list[Candidate]] = defaultdict(list)
    for c in cands:
        by_dom[c.ent.domain].append(c)
    for dom in by_dom:
        by_dom[dom].sort(key=_score, reverse=True)

    # 考研候选单独列出（优先级：tier3 > tier2）
    ky_pool = [c for c in cands if c.item.source == "kaoyan"]
    ky_pool.sort(key=_score, reverse=True)
    ky_cap = kaoyan_cap if kaoyan_cap is not None else max(0, round(target * 0.30))

    selected: list[Candidate] = []
    used: set[str] = set()
    stats = {"kaoyan": 0, "zhiyi_pdf": 0, "zhiyi": 0}

    def take(c: Candidate) -> None:
        selected.append(c)
        used.add(c.item.item_id)
        stats[c.item.source] += 1

    # ① 域内选：每个域先取考研候选（域内优先级最高），再取执医（PDF 历年真题优先于 CMExam）
    for dom in DOMAINS:
        want = dom_target.get(dom, 0)
        pool = by_dom.get(dom, [])
        ky = [c for c in pool if c.item.source == "kaoyan"]
        zp = [c for c in pool if c.item.source == "zhiyi_pdf"]
        cm = [c for c in pool if c.item.source == "zhiyi"]

        ky_take = min(len(ky), want, ky_cap - stats["kaoyan"])
        for c in ky[:ky_take]:
            take(c)
        want -= ky_take

        # 执医族内：PDF 历年真题优先，CMExam 补位
        for c in zp:
            if want <= 0:
                break
            if c.item.item_id in used:
                continue
            take(c)
            want -= 1
        if want > 0:
            for c in cm:
                if want <= 0:
                    break
                if c.item.item_id in used:
                    continue
                take(c)
                want -= 1

    # ② 全局补齐：任一域富余候选（避免某域候选不足导致总数不满）
    if len(selected) < target:
        rest = [c for c in cands if c.item.item_id not in used]
        rest.sort(key=_score, reverse=True)
        for c in rest:
            if len(selected) >= target:
                break
            if c.item.source == "kaoyan" and stats["kaoyan"] >= ky_cap:
                continue
            take(c)

    # ③ 近重复去重：同一题在不同年份册中重复出现（2016 单元4 同一题两份），
    #    或题干前 24 字高度重合 → 保留排序最靠前者
    def _key(c: Candidate) -> str:
        return re.sub(r"[^一-鿿]", "", c.item.stem)[:24]

    def _jaccard(a: str, b: str) -> float:
        A = set(re.sub(r"[^一-鿿]", "", a))
        B = set(re.sub(r"[^一-鿿]", "", b))
        if not A or not B:
            return 0.0
        return len(A & B) / len(A | B)

    seen_stem: dict[str, Candidate] = {}
    deduped: list[Candidate] = []
    dropped_dup = 0
    for c in selected:
        k = _key(c)
        # 精确近重复：题干前缀相同
        if k in seen_stem:
            dropped_dup += 1
            continue
        # 语义近重复：同一考点换皮（如 2013/2011 两版听骨链振动题）
        if any(_jaccard(c.item.stem, seen_c.item.stem) > 0.55
               for seen_c in deduped):
            dropped_dup += 1
            continue
        seen_stem[k] = c
        deduped.append(c)
    if dropped_dup:
        # 去重后数量不足，用未选中的候选补齐
        need = target - len(deduped)
        if need > 0:
            extra = [c for c in cands
                     if c.item.item_id not in used and _key(c) not in seen_stem]
            extra.sort(key=_score, reverse=True)
            for c in extra:
                if len(deduped) >= target:
                    break
                if c.item.source == "kaoyan" and stats["kaoyan"] >= ky_cap:
                    continue
                if any(_jaccard(c.item.stem, seen_c.item.stem) > 0.55
                       for seen_c in deduped):
                    continue
                take(c)
                deduped.append(c)
                seen_stem[_key(c)] = c
        selected = deduped
        # 重建统计
        stats = {"kaoyan": 0, "zhiyi_pdf": 0, "zhiyi": 0}
        for c in selected:
            stats[c.item.source] += 1

    records = []
    for c in selected:
        it = c.item
        records.append({
            "item_id": it.item_id,
            "source": it.source,
            "family": SOURCE_FAMILY.get(it.source, it.source),
            "tier": TIER_NAME.get(it.source, it.source),
            "source_id": it.source_id,
            "exam": it.exam,
            "year": it.year,
            "question_no": it.question_no,
            "question_type": it.question_type,
            "ent_domain": c.ent.domain,
            "ent_score": c.ent.score,
            "ent_terms": c.ent.terms[:8],
            "answer": it.answer,
            "answer_confidence": it.answer_confidence,
            "answer_evidence": it.answer_evidence,
            "license": it.license,
            "stem": it.stem,
            "options": it.options,
            "explanation": it.explanation,
            "module": it.module,
            "source_file": it.source_file,
        })

    pool_by_source = Counter(c.item.source for c in cands)
    report = {
        "target": target,
        "selected": len(selected),
        "pool_size": len(cands),
        "pool_by_source": dict(pool_by_source),
        "pool_by_domain": dict(Counter(c.ent.domain for c in cands)),
        "selected_by_source": dict(stats),
        "selected_by_domain": dict(Counter(r["ent_domain"] for r in records)),
        "selected_by_family": dict(Counter(r["family"] for r in records)),
        "selected_by_year": dict(sorted(Counter(str(r["year"]) for r in records).items())),
        "domain_target": dom_target,
        "records": records,
    }
    if out_path:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ENT 真题专项选题器")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_pick = sub.add_parser("pick", help="分层选出 ENT 真题")
    p_pick.add_argument("--target", type=int, default=100)
    p_pick.add_argument("--index-dir", default=str(DEFAULT_INDEX_DIR))
    p_pick.add_argument("--kaoyan-cap", type=int, default=None)
    p_pick.add_argument("--out", required=True)

    args = ap.parse_args(argv)
    if args.cmd == "pick":
        rep = pick(Path(args.index_dir), args.target, kaoyan_cap=args.kaoyan_cap,
                   out_path=args.out)
        print(f"✅ 候选池 {rep['pool_size']} 条 → 选出 {rep['selected']}/{rep['target']} 题")
        print(f"  候选池来源：{rep['pool_by_source']}")
        print(f"  候选池域别：{rep['pool_by_domain']}")
        print(f"  选中来源：{rep['selected_by_source']}")
        print(f"  选中族别：{rep['selected_by_family']}")
        print(f"  选中域别：{rep['selected_by_domain']}")
        return 0
    return 1


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
