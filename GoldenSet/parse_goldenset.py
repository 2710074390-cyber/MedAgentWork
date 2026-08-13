#!/usr/bin/env python3
"""
GoldenSet 真题解析器 v1.0
解析 真题上册.md（试卷）和 真题下册.md（贺银成真题精析）为结构化 JSON。

输出：
  - GoldenSet/structured/GS_上册_2024.json      — 上册试卷结构化
  - GoldenSet/structured/GS_下册_2025_1994.json  — 下册答案+解析结构化
  - GoldenSet/structured/GS_schema.json           — Schema 定义
  - GoldenSet/structured/GS_index.json            — 总索引
"""

import json, re, os, sys, io
from pathlib import Path
from datetime import datetime

# 强制 UTF-8 输出（Windows GBK 兼容）
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE = Path(r"C:\Users\38063\Desktop\MedAgentWork\GoldenSet")
OUT = BASE / "structured"
OUT.mkdir(parents=True, exist_ok=True)

# ── Schema 定义 ────────────────────────────────────────────
SCHEMA = {
    "version": "1.0",
    "fields": {
        "gs_id":       "str  — GoldenSet 全局唯一 ID，格式 GS-{年份}-{序号}",
        "year":        "int  — 考试年份",
        "exam_type":   "str  — 306西综 | 执业医师 | 其他",
        "question_no": "int  — 原卷题号",
        "type":        "str  — A1 | A2 | B | X | 填空",
        "subject":     "str  — 生理学|生物化学|病理学|内科学|外科学|诊断学|药理学|...",
        "chapter":     "str  — 教材章节（可从解析推断）",
        "stem":        "str  — 题干原文",
        "options":     "list[str] — 选项列表，A/B/C/D/E 顺序",
        "answer":      "str  — 正确答案，如 A | ABD | 争议",
        "explanation": "str  — 解析原文（下册有，上册为空）",
        "source_page": "str  — 教材页码溯源",
        "bloom_level": "str  — 记忆|理解|应用|分析（可后标注）",
        "difficulty":  "str  — easy|medium|hard",
        "controversial":"bool — 是否为争议题（黄皮书 vs 贺银成不一致）",
        "source_file": "str  — 来源文件"
    }
}

SUBJECT_KEYWORDS = {
    "生理学":   ["生理", "静息电位", "动作电位", "心肌", "呼吸", "肾", "消化", "神经纤维",
                 "突触", "激素", "内分泌", "钙泵", "钠泵", "血液", "循环", "渗透压",
                 "感受器", "反射", "肌梭", "牵张反射", "体温", "产热", "散热"],
    "生物化学": ["DNA", "RNA", "蛋白质", "酶", "氨基酸", "核酸", "糖酵解", "三羧酸",
                 "氧化磷酸化", "酮体", "胆固醇", "尿素", "嘌呤", "嘧啶", "转录",
                 "翻译", "基因", "复制", "维生素", "辅酶", "生物氧化", "胆红素",
                 "血红素", "信号转导", "受体", "癌基因", "抑癌基因"],
    "病理学":   ["病理", "坏死", "凋亡", "炎症", "肿瘤", "癌", "肉瘤", "化生", "变性",
                 "血栓", "栓塞", "梗死", "淤血", "水肿", "休克", "免疫", "移植",
                 "动脉粥样硬化", "风湿", "心衰细胞", "结核", "肝硬化"],
    "内科学":   ["内科", "心衰", "冠心病", "高血压", "心律失常", "肺炎", "COPD",
                 "哮喘", "溃疡", "肝硬化", "肾病", "贫血", "白血病", "糖尿病",
                 "甲亢", "SLE", "类风湿", "中毒", "心梗", "房颤"],
    "外科学":   ["外科", "骨折", "麻醉", "休克", "感染", "创伤", "烧伤", "肿瘤",
                 "移植", "颅内", "甲状腺", "乳腺", "胸外", "腹外", "疝", "阑尾",
                 "胆囊", "胰腺", "肠梗阻", "泌尿", "骨科", "关节"],
    "诊断学":   ["诊断", "体格检查", "听诊", "叩诊", "心电图", "实验室", "影像"],
    "药理学":   ["药物", "抗生素", "抗菌", "受体阻断", "激动剂", "抑制剂", "耐药"],
    "医学心理学": ["心理", "应激", "医患", "沟通"],
    "医学伦理学": ["伦理", "知情同意", "隐私"],
}


def detect_subject(text):
    """根据题干文本推断科目"""
    scores = {}
    for subj, keywords in SUBJECT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[subj] = score
    if scores:
        return max(scores, key=scores.get)
    return "未分类"


def parse_shangce(filepath):
    """
    解析 真题上册.md —— 纯试卷（无答案）

    格式特征：
      # 一、A型题：1~40小题...    → section header
      # 二、B型题：41~55小题...
      # 三、X型题：136~165小题...
      1. 题干内容                       → 题号
      A. 选项A                          → 选项
      B. 选项B
      ...
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 移除图片和HTML标签
    content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
    content = re.sub(r'<details>.*?</details>', '', content, flags=re.DOTALL)
    content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    content = re.sub(r'<table>.*?</table>', '', content, flags=re.DOTALL)
    content = re.sub(r'<[^>]+>', '', content)

    questions = []
    lines = content.split("\n")

    # 检测年份
    year_match = re.search(r'(\d{4})年', content[:2000])
    base_year = int(year_match.group(1)) if year_match else 2024

    current_section = None
    current_type = None
    current_q = None
    current_options = []
    in_question = False

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # 跳过空行和纯标记行
        if not line or line.startswith('#') and '小题' not in line:
            i += 1
            continue

        # 检测 Section
        section_match = re.match(r'#*\s*([一二三])[、.]\s*(A型题|B型题|X型题)', line)
        if section_match:
            sec_num, sec_type = section_match.groups()
            current_section = f"{sec_num}_{sec_type}"
            if "A型" in sec_type:
                current_type = "A型"
            elif "B型" in sec_type:
                current_type = "B型"
            elif "X型" in sec_type:
                current_type = "X型"
            i += 1
            continue

        # 检测题号起始
        q_match = re.match(r'^(\d{1,3})[\.\s、]', line)
        if q_match:
            qno = int(q_match.group(1))
            # 保存上一题
            if current_q and current_options:
                questions.append({
                    "gs_id": f"GS-{base_year}-{current_q['no']:03d}",
                    "year": base_year,
                    "question_no": current_q['no'],
                    "type": current_q['type'],
                    "section": current_section,
                    "stem": current_q['stem'],
                    "options": current_options,
                    "answer": "",  # 上册无答案
                    "explanation": "",
                    "subject": detect_subject(current_q['stem']),
                    "source_file": "真题上册.md"
                })

            # 提取题干（去掉题号）
            stem = re.sub(r'^\d{1,3}[\.\s、]\s*', '', line).strip()
            current_q = {"no": qno, "stem": stem, "type": current_type}
            current_options = []
            in_question = True
            i += 1
            continue

        # 检测选项
        option_match = re.match(r'^([A-E])[\.\s、]', line)
        if option_match and in_question:
            opt_label = option_match.group(1)
            opt_text = re.sub(r'^[A-E][\.\s、]\s*', '', line).strip()
            current_options.append(opt_text)
            i += 1
            continue

        # 可能是题干续行或多行选项
        if in_question and current_q and not current_options:
            current_q['stem'] += " " + line
        elif in_question and current_options:
            # 可能是长选项的续行
            current_options[-1] += " " + line

        i += 1

    # 保存最后一题
    if current_q and current_options:
        questions.append({
            "gs_id": f"GS-{base_year}-{current_q['no']:03d}",
            "year": base_year,
            "question_no": current_q['no'],
            "type": current_q['type'],
            "section": current_section,
            "stem": current_q['stem'],
            "options": current_options,
            "answer": "",
            "explanation": "",
            "subject": detect_subject(current_q['stem']),
            "source_file": "真题上册.md"
        })

    return questions, base_year


def parse_xiace(filepath):
    """
    解析 真题下册.md —— 贺银成历年真题精析（含答案+解析）

    格式特征：
      # 2025年全国硕士研究生招生考试...    → year header
      1. ABCD ①题干+解析...                → question with answer
      (答案为绿色的选项)                    → answer format hint
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 移除图片、HTML标签、mermaid图表
    content = re.sub(r'!\[.*?\]\(.*?\)', '', content)
    content = re.sub(r'<details>.*?</details>', '', content, flags=re.DOTALL)
    content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    content = re.sub(r'```mermaid.*?```', '', content, flags=re.DOTALL)
    content = re.sub(r'<[^>]+>', '', content)
    content = re.sub(r'!\[.*?\].*?\n', '', content)

    entries = []
    lines = content.split("\n")

    current_year = None
    current_subject = "未分类"
    # 科目标签映射
    subject_tags = {
        "生理": "生理学", "生化": "生物化学", "病理": "病理学",
        "内科": "内科学", "外科": "外科学", "诊断": "诊断学",
        "药理": "药理学", "微生物": "医学微生物学", "免疫": "医学免疫学",
        "遗传": "医学遗传学", "统计": "医学统计学", "伦理": "医学伦理学",
        "心理": "医学心理学", "预防": "预防医学"
    }

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # 检测年份
        year_match = re.match(r'#\s*(\d{4})年.*研究生.*考试.*西医', line)
        if year_match:
            current_year = int(year_match.group(1))
            i += 1
            continue

        # 检测科目标签 (如 "丙科学-01(57分/8)")
        subj_tag_match = re.match(r'.*?科学?[-—]?\d+', line)
        if not subj_tag_match:
            for tag, subj in subject_tags.items():
                if tag in line and len(line) < 40:
                    current_subject = subj
                    break

        # 检测题目条目: "1. ABCD ①..." 或 "1. A ①..."
        # 答案标记可能是单个字母或多个字母
        q_match = re.match(r'^(\d{1,3})[\.\s、]\s*([A-E]{1,5})\s', line)
        if q_match and current_year:
            qno = int(q_match.group(1))
            answer = q_match.group(2)
            # 提取剩余文本（题干+解析）
            rest = line[q_match.end():].strip()

            # 分离题干和解析
            # 格式: ①题干... ②选项A... ③选项B... 或直接是题干+解析
            stem_parts = []
            explanation = rest

            # 尝试用 ① ② ③ 分割
            numbered_parts = re.split(r'([①②③④⑤⑥⑦⑧⑨⑩])', rest)

            entry = {
                "gs_id": f"GS-{current_year}-{qno:03d}",
                "year": current_year,
                "question_no": qno,
                "type": detect_type_from_answer(answer, rest),
                "subject": detect_subject(rest[:200]),
                "stem_abbreviated": rest[:300],
                "answer": answer,
                "explanation": rest,
                "source_file": "真题下册.md"
            }
            entries.append(entry)
            i += 1
            continue

        # 可能续行（解析内容跨行）
        if entries and not re.match(r'^(\d{1,3})[\.\s、]', line) and not line.startswith('#') and line:
            entries[-1]["explanation"] += "\n" + line

        i += 1

    return entries


def detect_type_from_answer(answer, text):
    """根据答案格式和文本推断题型"""
    if len(answer) > 1:
        return "X型"  # 多选→X型
    # 尝试从文本中检测
    if "A型" in text[:100] or "a型" in text[:100]:
        return "A型"
    if "B型" in text[:100] or "b型" in text[:100]:
        return "B型"
    return "A型"  # 默认


# ── 执行解析 ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("GoldenSet 真题解析器 v1.0")
    print(f"执行时间: {datetime.now().isoformat()}")
    print("=" * 60)

    # 1. 解析上册
    shangce_path = BASE / "真题上册.md"
    if shangce_path.exists():
        print(f"\n📖 解析 真题上册.md ({shangce_path.stat().st_size / 1024:.0f} KB)...")
        questions, base_year = parse_shangce(str(shangce_path))
        print(f"   提取 {len(questions)} 道题目 (年份: {base_year})")

        # 按科目分类统计
        subj_count = {}
        for q in questions:
            s = q["subject"]
            subj_count[s] = subj_count.get(s, 0) + 1
        for s, c in sorted(subj_count.items(), key=lambda x: -x[1]):
            print(f"     {s}: {c}题")

        # 保存
        out_path = OUT / f"GS_上册_{base_year}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)
        print(f"   ✅ 保存至 {out_path}")
    else:
        print("⚠️ 真题上册.md 未找到")
        questions = []

    # 2. 解析下册
    xiace_path = BASE / "真题下册.md"
    if xiace_path.exists():
        print(f"\n📖 解析 真题下册.md ({xiace_path.stat().st_size / 1024:.0f} KB)...")
        entries = parse_xiace(str(xiace_path))
        print(f"   提取 {len(entries)} 条记录")

        # 按年份统计
        year_count = {}
        for e in entries:
            y = e["year"]
            year_count[y] = year_count.get(y, 0) + 1
        for y, c in sorted(year_count.items(), reverse=True):
            print(f"     {y}年: {c}题")

        # 保存
        out_path = OUT / "GS_下册_2025_1994.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        print(f"   ✅ 保存至 {out_path}")
    else:
        print("⚠️ 真题下册.md 未找到")
        entries = []

    # 3. 保存 Schema
    schema_path = OUT / "GS_schema.json"
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(SCHEMA, f, ensure_ascii=False, indent=2)
    print(f"\n📋 Schema 保存至 {schema_path}")

    # 4. 生成总索引
    index = {
        "version": "1.0",
        "generated_at": datetime.now().isoformat(),
        "files": {
            "上册_试卷": {
                "path": "structured/GS_上册_2024.json",
                "description": "2024年考研西综真题试卷（纯题目，无答案）",
                "count": len(questions),
                "has_answers": False,
                "has_explanations": False
            },
            "下册_精析": {
                "path": "structured/GS_下册_2025_1994.json",
                "description": "贺银成历年真题精析（2025-1994，含答案+解析）",
                "count": len(entries),
                "has_answers": True,
                "has_explanations": True
            }
        },
        "total_questions": len(questions) + len(entries),
        "layers": {
            "Layer0_锚定层": {
                "description": "306西综真题精选（2005-2025）",
                "source": "真题上册.md + 真题下册.md",
                "target": 500,
                "current": len(entries)
            },
            "Layer1_扩展层": {
                "description": "CMB-val + 校内期末高频题",
                "target": 300,
                "current": 0
            },
            "Layer2_临床推理": {
                "description": "临床案例深度推理题",
                "target": 50,
                "current": 0
            }
        }
    }

    index_path = OUT / "GS_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"📊 总索引保存至 {index_path}")

    print(f"\n{'='*60}")
    print(f"解析完成。结构化文件目录: {OUT}")
    print(f"  GS_schema.json        — 字段定义")
    print(f"  GS_index.json         — 总索引")
    print(f"  GS_上册_*.json        — 试卷结构化数据")
    print(f"  GS_下册_2025_1994.json — 答案精析结构化数据")
    print(f"{'='*60}")
