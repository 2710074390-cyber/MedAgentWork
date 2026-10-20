# -*- coding: utf-8 -*-
"""sources.py — GoldenSet（考研）与 CMExam（执业医师）源适配。

只读原始素材；输出统一 RealQuestion 记录。
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from .answer_recovery import recover_answer
from .schema import RealQuestion, exact_hash, prepare_item, simhash64

BASE = Path(__file__).resolve().parent.parent.parent
GS_DIR = BASE / "GoldenSet" / "structured"
GS_UP = GS_DIR / "GS_上册_2024.json"
GS_LOW = GS_DIR / "GS_下册_2025_1994.json"
ANSWER_FILE = BASE / "question_bank" / "kaoyan_answers.json"
CMEXAM_DIR = BASE / "知识库素材" / "cmexam" / "data"
CMEXAM_TEST = CMEXAM_DIR / "test_with_annotations.csv"
CMEXAM_TRAIN = CMEXAM_DIR / "train.csv"

# 项目学科与关键词（用于补 306 未分类、给 CMExam train 打标）
SUBJECT_KEYWORDS: dict[str, list[str]] = {
    "内科学": [
        "心衰", "心力衰竭", "冠心病", "高血压", "心律失常", "房颤", "室颤", "心梗",
        "心肌梗死", "肺炎", "COPD", "慢性阻塞性肺疾病", "哮喘", "支气管", "溃疡",
        "肝硬化", "肾病", "肾炎", "肾病综合征", "肾衰", "贫血", "白血病", "淋巴瘤",
        "糖尿病", "甲亢", "甲状腺功能亢进", "甲减", "SLE", "系统性红斑狼疮",
        "类风湿", "中毒", "消化", "呼吸", "循环", "泌尿", "内分泌", "血液", "风湿",
        "发热", "黄疸", "腹水", "水肿", "胸痛", "咳嗽", "咯血", "呕血", "黑便",
        "尿频", "尿急", "尿痛", "蛋白尿", "血尿", "肾功能", "肝功能", "血糖",
        "血脂", "垂体", "肾上腺", "酸碱", "电解质",
    ],
    "外科学": [
        "手术", "切除", "骨折", "阑尾", "疝", "胆囊", "胆管", "胰腺", "肠梗阻",
        "创伤", "烧伤", "休克", "麻醉", "移植", "骨科", "关节", "乳腺", "甲状腺",
        "颅内", "结石", "前列腺", "痔", "瘘", "脓肿", "清创", "缝合", "引流",
        "术前", "术后", "并发症", "外科", "普外", "胸外", "泌尿外科", "神经外科",
    ],
    "妇产科学": [
        "妊娠", "分娩", "产程", "胎儿", "胎盘", "羊水", "剖宫产", "子宫", "卵巢",
        "宫颈", "阴道", "月经", "异位妊娠", "肌瘤", "内膜", "不孕", "更年期",
        "妇科", "产科", "产后", "流产", "葡萄胎", "子痫", "妊娠期高血压",
    ],
    "儿科学": [
        "新生儿", "婴儿", "幼儿", "儿童", "小儿", "生长发育", "疫苗", "母乳",
        "佝偻", "川崎", "手足口", "麻疹", "早产", "低体重", "儿童保健", "儿科",
        "新生儿黄疸", "小儿肺炎", "小儿腹泻",
    ],
    "传染病学": [
        "传染", "病毒性肝炎", "乙肝", "丙肝", "结核", "艾滋病", "HIV", "伤寒",
        "副伤寒", "菌痢", "细菌性痢疾", "霍乱", "疟疾", "血吸虫", "水痘", "带状疱疹",
        "狂犬", "流行性", "隔离", "消毒", "潜伏期", "传染病报告", "甲肝", "戊肝",
    ],
    "精神病学": [
        "精神", "抑郁", "焦虑", "精神分裂", "双相", "躁狂", "强迫", "痴呆", "谵妄",
        "幻觉", "妄想", "失眠", "自杀", "抗精神病", "抗抑郁", "心境稳定", "电休克",
        "心理治疗", "精神病", "自知力", "抑郁发作", "躁狂发作", "焦虑障碍",
        "强迫障碍", "精神分裂症",
    ],
    "急诊与灾难医学": [
        "急诊", "中毒", "休克", "心肺复苏", "中暑", "淹溺", "电击", "急救", "气道",
        "除颤", "洗胃", "解毒", "危重", "灾难", "蛇咬", "蜂蜇", "高原", "减压病",
        "急性", "抢救",
    ],
    "眼科学": [
        "视力", "角膜", "视网膜", "青光眼", "白内障", "葡萄膜", "结膜",
        "虹膜", "晶状体", "玻璃体", "屈光", "斜视", "弱视", "眼底", "眼压",
        "失明", "复视", "眼科", "眼睑", "泪器", "眼眶", "视神经", "黄斑",
        "眼外伤",
    ],
    "耳鼻咽喉头颈外科学": [
        "中耳", "内耳", "耳聋", "耳鸣", "眩晕", "鼻窦", "鼻炎", "鼻出血", "扁桃体",
        "腺样体", "声带", "喉癌", "气管异物", "食管异物", "颈部肿块", "鼻咽癌",
        "睡眠呼吸", "打鼾", "听力", "耳鼻咽喉", "外耳道", "鼓膜", "听骨", "咽鼓管",
        "乳突", "胆脂瘤", "鼓室", "前庭", "半规管", "听神经", "鼻中隔", "下鼻甲",
        "上颌窦", "额窦", "筛窦", "蝶窦", "声嘶", "喉阻塞", "喉返神经", "会厌",
        "扁桃体周围脓肿", "睡眠呼吸暂停", "OSA", "鼻咽", "口咽", "下咽",
        "颈淋巴结", "耳廓", "耳郭",
    ],
    "口腔科学": [
        "口腔", "颌", "颞下", "唾液腺", "龋", "牙髓", "牙周", "口腔黏膜",
        "拔牙", "种植", "正畸", "义齿", "唇裂", "腭裂", "颌面", "口腔科",
        "眶下间隙", "牙槽", "牙龈", "颌骨", "口腔颌面", "颞间隙", "翼下颌",
        "颌面部", "牙体", "牙列",
    ],
    "皮肤性病学": [
        "皮疹", "皮炎", "湿疹", "银屑", "荨麻", "疱疹", "梅毒", "淋病",
        "尖锐湿疣", "真菌", "瘙痒", "红斑", "鳞屑", "色素", "脱发", "痤疮",
        "皮肤", "性病", "皮损", "斑疹", "丘疹", "水疱", "大疱", "苔藓",
    ],
    "诊断学": [
        "诊断", "体格检查", "听诊", "叩诊", "触诊", "呼吸音", "心电图",
        "实验室", "影像", "血压测量", "淋巴结", "腹部检查",
    ],
    "药理学": [
        "药物", "抗生素", "抗菌", "受体阻断", "激动剂", "抑制剂", "耐药",
        "阿司匹林", "药理", "剂量", "不良反应", "半衰期", "首过效应",
    ],
    "神经病学": [
        "脑梗", "脑出血", "脑栓塞", "TIA", "蛛网膜", "帕金森", "癫痫", "偏头痛",
        "阿尔茨海默", "痴呆", "面神经", "三叉神经", "多发性硬化", "重症肌无力",
        "吉兰-巴雷", "共济失调", "瘫痪", "感觉障碍", "反射", "脑电图", "肌电图",
    ],
    "中医学": [
        "中医", "阴阳", "五行", "藏象", "辨证", "八纲", "六经", "卫气营血",
        "方剂", "中药", "针灸", "经络", "腧穴", "脉象", "舌象", "肝郁", "情志",
        "中成药", "证属", "舌红", "舌淡", "脉细", "脉沉", "脉弦", "肾精",
        "肝火", "肾阴虚", "脾虚", "气虚", "血瘀",
    ],
}

# CMExam Clinical Department -> 项目学科
DEPARTMENT_TO_SUBJECT = {
    "内科": "内科学",
    "外科": "外科学",
    "妇产科": "妇产科学",
    "妇女保健": "妇产科学",
    "儿科": "儿科学",
    "儿童保健科": "儿科学",
    "儿童外科": "儿科学",
    "传染科": "传染病学",
    "结核病科": "传染病学",
    "精神科": "精神病学",
    "急诊医学科": "急诊与灾难医学",
    "重症医学科": "急诊与灾难医学",
    "眼科": "眼科学",
    "耳鼻咽喉科": "耳鼻咽喉头颈外科学",
    "皮肤科": "皮肤性病学",
    "口腔科": "口腔科学",
    "肿瘤科": "内科学",
    "医学检验科": "诊断学",
    "医学影像科": "诊断学",
    "病理科": "病理学",
    "麻醉科": "外科学",
    "康复医学科": "内科学",
    "全科医疗": "内科学",
}

# 学科优先级：越具体越靠前，避免「休克/感染」被内科学抢走
SUBJECT_PRIORITY = [
    "耳鼻咽喉头颈外科学", "眼科学", "口腔科学", "皮肤性病学", "精神病学",
    "传染病学", "妇产科学", "儿科学", "急诊与灾难医学", "神经病学",
    "外科学", "内科学", "中医学",
]


# 跨学科强信号：命中且当前学科不是该学科时，判为噪声（用于 CMExam 弱标签清洗）
CROSS_SUBJECT_SIGNALS = {
    "中医学": ["中成药", "证属", "舌红", "舌淡", "脉细", "脉沉", "脉弦", "肾精", "肝火"],
    "药理学": ["阿司匹林", "半衰期", "首过效应", "受体阻断", "不良反应"],
    "诊断学": ["呼吸音", "心电图", "叩诊", "听诊", "体格检查"],
    "眼科学": ["视野", "眼压", "眼底", "视力"],
    "急诊与灾难医学": ["化工", "职业病", "渔民", "中暑", "淹溺", "电击"],
    "神经病学": ["指鼻试验", "跟膝胫", "轮替动作", "病理征", "脑膜刺激征", "肌张力"],
}


def _is_cross_subject(subject: str, text: str) -> bool:
    for other, terms in CROSS_SUBJECT_SIGNALS.items():
        if subject == other:
            continue
        if any(t in text for t in terms):
            return True
    return False


def _norm_subject(s: str) -> str:
    s = (s or "").strip()
    aliases = {
        "耳鼻咽喉科学": "耳鼻咽喉头颈外科学",
        "耳鼻咽喉头颈外科": "耳鼻咽喉头颈外科学",
        "妇产科": "妇产科学",
        "儿科": "儿科学",
        "传染科": "传染病学",
        "精神科": "精神病学",
        "眼科": "眼科学",
        "口腔科": "口腔科学",
        "皮肤科": "皮肤性病学",
        "神经科": "神经病学",
        "急诊科": "急诊与灾难医学",
    }
    return aliases.get(s, s)


def classify_subject(text: str, min_score: int = 2) -> tuple[str, list[str]]:
    """关键词打分返回 (subject, matched_subjects)。"""
    text = text or ""
    scores: dict[str, int] = {}
    for subject, kws in SUBJECT_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in text)
        if score:
            scores[subject] = score
    if not scores:
        return "未分类", []
    max_score = max(scores.values())
    if max_score < min_score:
        return "未分类", [s for s, v in scores.items() if v == max_score]
    candidates = [s for s, v in scores.items() if v == max_score]
    for subject in SUBJECT_PRIORITY:
        if subject in candidates:
            return subject, sorted(candidates)
    return sorted(candidates)[0], sorted(candidates)


def _parse_options(raw: str) -> list[str]:
    """解析 A/B/C/D/E 行式选项。"""
    if not raw:
        return []
    lines = [x.strip() for x in str(raw).splitlines() if x.strip()]
    out: list[str] = []
    for line in lines:
        m = re.match(r"^([A-E])\s*[.、:：]?\s*(.*)$", line)
        if m:
            out.append(m.group(2).strip())
        else:
            out.append(line)
    return out


def _infer_type(stem: str, answer: str, options: list[str]) -> str:
    if len(answer) > 1:
        return "X"
    if "共用题干" in stem or "以下" in stem and len(stem) > 80:
        return "A3"
    if len(stem) > 60:
        return "A2"
    return "A1"


def build_kaoyan_items() -> tuple[list[RealQuestion], dict]:
    """考研 306：上册题干/选项 + 下册答案/解析。"""
    upper = json.loads(GS_UP.read_text(encoding="utf-8"))
    lower = json.loads(GS_LOW.read_text(encoding="utf-8"))
    low_by_id = {q.get("gs_id"): q for q in lower}
    verified = json.loads(ANSWER_FILE.read_text(encoding="utf-8")) if ANSWER_FILE.exists() else {}
    items: list[RealQuestion] = []
    stats = {"upper": len(upper), "lower": len(lower), "recovered": 0, "dropped": 0, "from_answer_file": 0}
    for q in upper:
        qid = q.get("gs_id", "")
        low = low_by_id.get(qid) or {}
        stem = (q.get("stem") or "").strip()
        options = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
        if not stem or not options:
            stats["dropped"] += 1
            continue
        # 优先使用 question_bank/kaoyan_answers.json（含 PDF 标准答案），
        # 其次才从解析文本规则恢复。
        rec = verified.get(qid) or {}
        answer = (rec.get("answer_recovered") or "").strip().upper()
        if answer:
            result_answer = answer
            result_confidence = rec.get("confidence", "high")
            result_evidence = rec.get("evidence", "answer_file")
            stats["from_answer_file"] += 1
        else:
            result = recover_answer(
                low.get("explanation", ""),
                raw_answer=low.get("answer"),
                n_options=len(options),
            )
            result_answer = result.answer
            result_confidence = result.confidence
            result_evidence = result.evidence
        if not result_answer:
            stats["dropped"] += 1
            continue
        stats["recovered"] += 1
        subject = _norm_subject(q.get("subject", "未分类"))
        aliases = [subject]
        if subject == "未分类":
            guessed, _ = classify_subject(
                stem + " " + " ".join(options) + " " + low.get("explanation", "")
            )
            if guessed != "未分类":
                subject = guessed
                aliases = [subject]
        # 306 的 subject 字段是可靠的；不再追加跨学科别名，
        # 否则「耳毒性药物」会被误判成耳鼻喉真题，污染其他学科配额。
        item = RealQuestion(
            item_id=f"KY-{qid}",
            source="kaoyan",
            source_id=qid,
            exam="306西综",
            year=q.get("year"),
            question_no=q.get("question_no"),
            subject=subject,
            subject_aliases=aliases,
            department="",
            module="",
            chapter="",
            keypoints=[],
            teacher_keypoint_refs=[],
            stem=stem,
            options=options,
            answer=result_answer,
            explanation=(low.get("explanation") or "").strip(),
            question_type=(
                _infer_type(stem, result_answer, options)
                if str(q.get("type", "")).startswith("A")
                else str(q.get("type", "")).replace("型", "")
            ),
            bloom="",
            difficulty_p=None,
            answer_confidence=result_confidence,
            answer_evidence=result_evidence,
            license="public_noncommercial",
            license_note="考研真题；用户声明仅非商业个人刷题使用",
            dedup_hash=exact_hash(stem, options),
            simhash=simhash64(stem + " " + " ".join(options)),
            selectable=True,
            source_file="真题上册.md(题干)+真题下册.md(答案解析)",
        )
        items.append(prepare_item(item))
    stats["usable"] = sum(1 for x in items if x.selectable)
    return [x for x in items if x.selectable], stats


def _cmexam_license_note() -> str:
    return "CMExam 学术数据集；用户声明仅非商业个人刷题使用"


def build_zhiyi_items() -> tuple[list[RealQuestion], dict]:
    """执业医师：CMExam test（有标签）+ train（关键词补标签）。"""
    items: list[RealQuestion] = []
    stats = {"test": 0, "train": 0, "train_labeled": 0, "dropped": 0}

    if CMEXAM_TEST.exists():
        with open(CMEXAM_TEST, "r", encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f)):
                stem = (row.get("Question") or "").strip()
                options = _parse_options(row.get("Options") or "")
                answer = (row.get("Answer") or "").strip().upper()
                if not stem or not options or not answer:
                    stats["dropped"] += 1
                    continue
                department = (row.get("Clinical Department") or "").strip()
                discipline = (row.get("Medical Discipline") or "").strip()
                subject = DEPARTMENT_TO_SUBJECT.get(department, "")
                if not subject and discipline == "口腔医学":
                    subject = "口腔科学"
                if not subject and discipline in {"中医学", "中西医结合"}:
                    subject = "中医学"
                if not subject:
                    # test 的科室标签比关键词更可靠；未知科室直接丢弃，避免把职业病/公卫题塞进临床科
                    stats["dropped"] += 1
                    continue
                if _is_cross_subject(subject, stem + " " + " ".join(options)):
                    stats["dropped"] += 1
                    continue
                diff = (row.get("Difficulty level") or "").strip()
                p_map = {"1": 0.85, "2": 0.70, "3": 0.55, "4": 0.40, "5": 0.25}
                item = RealQuestion(
                    item_id=f"ZY-T-{i}",
                    source="zhiyi",
                    source_id=f"CMExam-test-{i}",
                    exam="执业医师",
                    year=None,
                    question_no=None,
                    subject=_norm_subject(subject),
                    subject_aliases=[_norm_subject(subject)],
                    department=department,
                    module="",
                    chapter="",
                    keypoints=[],
                    teacher_keypoint_refs=[],
                    stem=stem,
                    options=options,
                    answer=answer,
                    explanation=(row.get("Explanation") or "").strip(),
                    question_type=_infer_type(stem, answer, options),
                    bloom="",
                    difficulty_p=p_map.get(diff),
                    answer_confidence="high",
                    answer_evidence="CMExam test answer",
                    license="public_noncommercial",
                    license_note=_cmexam_license_note(),
                    dedup_hash=exact_hash(stem, options),
                    simhash=simhash64(stem + " " + " ".join(options)),
                    selectable=True,
                    source_file="CMExam-test",
                    quality_flags=[
                        f"competency:{row.get('Area of Competency', '')}".strip(":"),
                        f"disease_group:{row.get('Disease Group', '')}".strip(":"),
                    ],
                )
                items.append(prepare_item(item))
                stats["test"] += 1

    if CMEXAM_TRAIN.exists():
        with open(CMEXAM_TRAIN, "r", encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f)):
                stem = (row.get("Question") or "").strip()
                options = _parse_options(row.get("Options") or "")
                answer = (row.get("Answer") or "").strip().upper()
                if not stem or not options or not answer:
                    stats["dropped"] += 1
                    continue
                # train 无科室标签：要求至少 3 个关键词命中，优先保证精度
                subject, _matched = classify_subject(stem + " " + " ".join(options), min_score=3)
                if subject == "未分类":
                    stats["dropped"] += 1
                    continue
                if _is_cross_subject(subject, stem + " " + " ".join(options)):
                    stats["dropped"] += 1
                    continue
                stats["train_labeled"] += 1
                item = RealQuestion(
                    item_id=f"ZY-R-{i}",
                    source="zhiyi",
                    source_id=f"CMExam-train-{i}",
                    exam="执业医师",
                    year=None,
                    question_no=None,
                    subject=subject,
                    subject_aliases=[subject],
                    department=subject,
                    module="",
                    chapter="",
                    keypoints=[],
                    teacher_keypoint_refs=[],
                    stem=stem,
                    options=options,
                    answer=answer,
                    explanation=(row.get("Explanation") or "").strip(),
                    question_type=_infer_type(stem, answer, options),
                    bloom="",
                    difficulty_p=None,
                    answer_confidence="medium",
                    answer_evidence="CMExam train answer",
                    license="public_noncommercial",
                    license_note=_cmexam_license_note(),
                    dedup_hash=exact_hash(stem, options),
                    simhash=simhash64(stem + " " + " ".join(options)),
                    selectable=True,
                    source_file="CMExam-train",
                )
                items.append(prepare_item(item))
                stats["train"] += 1

    stats["usable"] = sum(1 for x in items if x.selectable)
    return [x for x in items if x.selectable], stats
