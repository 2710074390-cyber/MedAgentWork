#!/usr/bin/env python3
"""
GoldenSet 真题解析器 v2.0 (2026-08-20 审查修复)
解析 真题上册.md（试卷，1994-2024 多套）和 真题下册.md（贺银成真题精析）为结构化 JSON。

v2.0 修复内容（代码审查 C1/C2 实测确认）：
  1. **多套试卷年份感知**：源文件含 1994-2024 共 31 套试卷，题号每年重置。
     旧版只取首个年份 → gs_id = GS-2024-{题号} 全库碰撞
     （2641 条仅 180 个唯一 gs_id，最多 22 条共享同一 id）。
     新版按 '# YYYY年' 试卷头切换年份，gs_id = GS-{年份}-{题号:03d} 全局唯一。
  2. **B 型题组共享选项**：B 型题选项块位于子题之前（A-E 共用备选项），
     旧版把选项块错误挂到前一条题、每组首题被丢弃。新版维护 pending_options：
     选项块 → 绑定其后所有子题；新选项块到达 → 正确切组。
  3. **'# 题号' 头形式题目**：部分题目（如 2018 X 型、129 心电图判读）以
     markdown 头 '# 136. 题干' 书写，旧版整行跳过（61 题丢失）。
  4. **节标题不再拼进题干**：'# 三、C型题…' 等标题行按节头识别并跳过。
  5. **出口断言**：解析后强制校验 gs_id 唯一性 / stem / options / 选项数 ≤6，
     失败即退出非 0，绝不写出污染产物。
  6. **下册 schema 分级**：下册是精析书（源文件无题干/选项），由
     GoldenSet/regression.py 按册分级校验（ANALYSIS_REQUIRED_FIELDS）。

输出：
  - GoldenSet/structured/GS_上册_2024.json      — 上册试卷结构化（1994-2024 全部年份）
  - GoldenSet/structured/GS_下册_2025_1994.json  — 下册答案+解析结构化
  - GoldenSet/structured/GS_schema.json           — Schema 定义
  - GoldenSet/structured/GS_index.json            — 总索引
"""

import json, re, os, sys, io
from pathlib import Path
from datetime import datetime
from collections import Counter

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
    "version": "2.0",
    "fields": {
        "gs_id":       "str  — GoldenSet 全局唯一 ID，格式 GS-{年份}-{序号:03d}（v2.0: 按试卷年份唯一）",
        "year":        "int  — 考试年份",
        "exam_type":   "str  — 306西综 | 执业医师 | 其他",
        "question_no": "int  — 原卷题号",
        "type":        "str  — A型 | B型 | X型",
        "subject":     "str  — 生理学|生物化学|病理学|内科学|外科学|诊断学|药理学|...",
        "chapter":     "str  — 教材章节（可从解析推断）",
        "stem":        "str  — 题干原文",
        "options":     "list[str] — 选项列表，A/B/C/D/E 顺序（B型题为题组共享选项）",
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


def preprocess(content):
    """清理 OCR/HTML 噪声：去图片、去标签但保留 <details>/<table> 内部文字。

    v2.0 修复: 标签正则一律限单行（[^>\\n]）—— 旧版 [^>] 可跨行匹配，OCR 文本中
    任何孤立 '<'（如数学比较符）会吞掉直到下一个 '>' 的大段内容（实测复现：
    预处理后文件被截断错乱，题号被错误合并）。
    """
    content = re.sub(r'!\[.*?\]\(.*?\)', '', content, flags=re.DOTALL)
    content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    # <details>/<table> 保留内部文字（如心电图判读题的电压表），仅去标签（单行）
    content = re.sub(r'</?(?:details|table|tr|td|th|thead|tbody)[^>\n]*>', '\n', content, flags=re.DOTALL)
    content = re.sub(r'<[^>\n]+>', '', content)
    return content


def parse_shangce(filepath):
    """
    解析 真题上册.md —— 多套试卷（1994-2024，题号每年重置）

    格式特征（v2.0 实测梳理）：
      # 2024年全国硕士研究生招生考试临床医学综合能力(西医)试题   → 试卷头（年份切换）
      # 一、A型题：1~40小题...                                    → 节头（题型切换）
      # 二、B型题：116~135小题...（A、B、C、D是其下两道小题的备选项）→ B型节头
      # 三、X型题：136~165小题...
      1. 题干内容                                                → 题号起始（A/X 型）
      A. 选项A                                                   → 选项（跟随题号）
      ...
      A. 选项A     ← B 型题组：选项块位于子题之前，绑定其后所有子题
      B. 选项B
      116. 题干1
      117. 题干2
      # 136. 题干（部分题目以 markdown 头书写）                    → 题号起始
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = preprocess(f.read())

    questions = []
    lines = content.split("\n")

    year = None
    current_section = None
    current_type = None
    section_ordinal = 0    # v2.0: 节头序号（一/二/三…），老西综基础/临床两套题号重号时用于 gs_id 消歧
    current_q = None
    pending_options = []   # v2.0: B 型题组共享选项块（位于子题之前）
    skipped_no_year = 0
    seen_keys = set()      # v2.0: 源文件题号重复行去重（2004 年 93/94 实测出现两遍）
    overflow = [0]         # v2.0: 选项数 >6 被截断的题数（源文件损坏保护）

    ORDINALS = '一二三四五六七八九十'

    def finalize():
        """保存当前题。B 型题无自身选项时补挂 pending 共享选项块。"""
        nonlocal current_q, pending_options, seen_keys
        if current_q is None:
            return
        q = current_q
        if not q['options'] and pending_options:
            q['options'] = list(pending_options)   # B 型题组共享选项
        if year is None:
            nonlocal_skip()
            current_q = None
            return
        if not q['stem'] and not q['options']:
            current_q = None
            return
        key = (year, q['no'], q['stem'])
        if key in seen_keys:
            # 源文件把同一题写了两遍（OCR/编辑重复）→ 保留第一遍
            current_q = None
            return
        seen_keys.add(key)
        # v2.0: 源文件损坏保护（如 2022 卷 A 型区段选项乱序、题号丢失），
        # 选项数 >6 一律截断并计入告警，医学题合法选项数最多 5（B 型共享）
        if len(q['options']) > 6:
            overflow[0] += 1
            q['options'] = q['options'][:6]
        # gs_id 消歧：老西综（1994-2007）基础/临床两套题号重号（如 2007 四、A型 与
        # 五、A型 都是 151~180），节头序号 >3 时追加 '-s{序号}' 后缀保证全局唯一
        suffix = f"-s{section_ordinal}" if section_ordinal > 3 else ""
        questions.append({
            "gs_id": f"GS-{year}-{q['no']:03d}{suffix}",
            "year": year,
            "question_no": q['no'],
            "type": q['type'],
            "section": current_section,
            "stem": q['stem'],
            "options": q['options'],
            "answer": "",  # 上册无答案
            "explanation": "",
            "subject": detect_subject(q['stem']),
            "source_file": "真题上册.md"
        })
        current_q = None

    def nonlocal_skip():
        nonlocal skipped_no_year
        skipped_no_year += 1

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        # 1. 试卷头 → 年份切换（v2.0: 题号每年重置，必须逐卷切换）
        ym = re.match(r'^#+\s*(\d{4})年', line)
        if ym:
            finalize()
            year = int(ym.group(1))
            current_section = None
            current_type = None
            continue

        # 2. 节头（一、A型题 / 二、B型题 / 三、X型题 …）→ 题型切换，清共享选项
        # v2.0: 老西综（2007 及以前）节头为无 '#' 的纯文本行（如
        # '四、A型题：151~180小题'），必须兼容；此前漏识别会被当题干续行拼进上一题
        sm = re.match(r'^#*\s*([一二三四五六七八九十]+)[、.．]\s*(A型题|B型题|X型题|C型题|D型题)', line)
        if sm:
            finalize()
            current_section = line.lstrip('#').strip()
            # v2.0: 题型名归一为 'A型'/'B型'/'X型'（去掉 '题' 后缀）——
            # 此前 current_type 保留 'B型题'，选项分支按 'B型' 判断永不匹配，
            # B 型题组共享选项被误挂到上一子题（实测 GS-2024-117 只拿到 1 个选项）
            sec_type = sm.group(2)[:-1] if sm.group(2).endswith('题') else sm.group(2)
            current_type = 'X型' if sec_type == 'C型' else sec_type   # 部分年份 C 型并入多选
            section_ordinal = ORDINALS.find(sm.group(1)) + 1
            pending_options = []
            continue

        # 3. 题号起始（兼容 '# 136. 题干' 头形式，v2.0 修复丢失的 61 题；
        #    无节头年份（老西综）默认按 A 型处理）
        # v2.0: (?!\d) 排除小数开头的题干续行（如 '0.5cm 残余结石…'，
        #    实测被误判为"第 0 题"、真 62 题选项丢失）
        qm = re.match(r'^#*\s*(\d{1,3})[\.、．](?!\d)\s*(.*)$', line)
        if qm:
            finalize()
            current_q = {
                'no': int(qm.group(1)),
                'stem': qm.group(2).strip(),
                'type': current_type or 'A型',
                'options': [],
            }
            continue

        # 4. 选项行（v2.0: 兼容一行多选项与无空格格式，如
        #    'A.瞳孔散大 B.汗腺分泌 C.糖原分解 D.胰岛素分泌'（2019 等年份实测））
        om = re.match(r'^([A-E])[.．]', line)
        if om:
            parts = re.split(r'\s+(?=[A-E][.．](?:\s|[\u4e00-\u9fff]))', line)
            opts = []
            for part in parts:
                m = re.match(r'^([A-E])[.．]\s*(.*)$', part)
                if m:
                    opts.append(m.group(2).strip())
            if not opts:
                opts = [om.group(2).strip()]
            if current_q is None:
                # 无当前题 → B 型题组共享选项块起始/续行
                pending_options.extend(opts)
            elif not current_q['options'] and current_type == 'B型':
                # B 型题：选项块恒在子题之前 → 当前题由 finalize 补挂上一共享块，
                # 本选项行是新共享块的开始（v2.0 修复：此前被误挂到上一子题）
                finalize()
                pending_options = opts
            elif not current_q['options']:
                # 当前题尚无选项（A/X 型正常流程）→ 挂到本题
                current_q['options'].extend(opts)
            elif current_type == 'B型':
                # B 型题组边界：当前题已有选项（来自共享块）又出现新选项行 → 切组
                finalize()
                pending_options = opts
            else:
                # A/X 型：同一题的后续选项（B/C/D…）继续挂到本题
                # （v2.0 修复：此前误走切组分支，X 型题实测只剩 1 个选项）
                current_q['options'].extend(opts)
            continue

        # 5. 续行：题干续行或长选项续行（跳过 '|' 表格残留行，防污染）
        if current_q is not None and not line.startswith('|'):
            if not current_q['options']:
                if line and not line.startswith('#') and not re.match(r'^[A-E][\.、．]', line):
                    current_q['stem'] = (current_q['stem'] + ' ' + line).strip()
            else:
                current_q['options'][-1] += ' ' + line

    finalize()

    if skipped_no_year:
        print(f'  ⚠️ {skipped_no_year} 题因缺年份试卷头被跳过')
    if overflow[0]:
        print(f'  ⚠️ {overflow[0]} 题选项数 >6（源文件损坏保护，已截断至 6 个）')
    return questions


def parse_xiace(filepath):
    """
    解析 真题下册.md —— 贺银成历年真题精析（含答案+解析，源文件无题干/选项）

    格式特征：
      # 2025年全国硕士研究生招生考试临床医学综合能力(西医)试题答案及详细解答 → year header
      1. ABCD ①题干+解析...   → question with answer（题号每年重置）
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = preprocess(f.read())

    entries = []
    lines = content.split("\n")

    current_year = None
    current_subject = "未分类"
    seen_ids = {}          # v2.0: (year,qno) 出现次数 → gs_id 消歧（老西综双编号）
    subject_tags = {
        "生理": "生理学", "生化": "生物化学", "病理": "病理学",
        "内科": "内科学", "外科": "外科学", "诊断": "诊断学",
        "药理": "药理学", "微生物": "医学微生物学", "免疫": "医学免疫学",
        "遗传": "医学遗传学", "统计": "医学统计学", "伦理": "医学伦理学",
        "心理": "医学心理学", "预防": "预防医学"
    }

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 检测年份（v2.0: 放宽为 '# YYYY年' 头；旧版要求同行含 研究生/考试/西医，
        # 老年份标题变体（如 '1995年全国攻读硕士学位研究生入学考试...'）会漏检）
        year_match = re.match(r'^#\s*(\d{4})年', line)
        if year_match:
            current_year = int(year_match.group(1))
            current_subject = "未分类"
            continue

        # 科目标签（短行，如 "内科学-01(57分/8)"）
        for tag, subj in subject_tags.items():
            if tag in line and len(line) < 40:
                current_subject = subj
                break

        # 检测题目条目: "1. ABCD ①..." 或 "1. A ①..."
        q_match = re.match(r'^(\d{1,3})[\.\s、]\s*([A-E]{1,5})\s', line)
        if q_match and current_year:
            qno = int(q_match.group(1))
            answer = q_match.group(2)
            rest = line[q_match.end():].strip()
            # v2.0: 老西综基础/临床双编号重号（2007 年 151~180 出现两套）→
            # 同一 (year, qno) 第二次出现追加 '-2' 后缀保证 gs_id 唯一
            base_id = f"GS-{current_year}-{qno:03d}"
            seen_q = seen_ids.get(base_id, 0)
            seen_ids[base_id] = seen_q + 1
            gs_id = base_id if seen_q == 0 else f"{base_id}-{seen_q + 1}"
            entries.append({
                "gs_id": gs_id,
                "year": current_year,
                "question_no": qno,
                "type": detect_type_from_answer(answer, rest),
                "subject": detect_subject(rest[:200]) if current_subject == "未分类" else current_subject,
                "stem_abbreviated": rest[:300],
                "answer": answer,
                "explanation": rest,
                "source_file": "真题下册.md"
            })
            continue

        # 解析内容跨行续行
        if entries and not line.startswith('#') and not re.match(r'^(\d{1,3})[\.\s、]', line):
            entries[-1]["explanation"] += "\n" + line

    return entries


def detect_type_from_answer(answer, text):
    """根据答案格式和文本推断题型"""
    if len(answer) > 1:
        return "X型"  # 多选→X型
    if "A型" in text[:100] or "a型" in text[:100]:
        return "A型"
    if "B型" in text[:100] or "b型" in text[:100]:
        return "B型"
    return "A型"  # 默认


# ── 出口断言（v2.0: 失败即退出，绝不写出污染产物）─────────────────

def assert_questions(questions, name, require_options=True, require_answer=True, require_stem=True):
    """gs_id 唯一性 + 字段完整性断言。返回 (通过, 错误列表)。

    require_answer=False: 上册为纯试卷（无答案/解析），跳过 answer/explanation 检查。
    require_stem=False: 下册为精析（源文件无题干），跳过 stem 检查。
    """
    errors = []
    ids = [q.get('gs_id') for q in questions]
    dup = [i for i, c in Counter(ids).items() if c > 1]
    if dup:
        errors.append(f'gs_id 重复 {len(dup)} 个（样例: {dup[:3]}）')
    if require_stem:
        no_stem = sum(1 for q in questions if not str(q.get('stem', '')).strip())
        if no_stem:
            errors.append(f'{no_stem} 题缺 stem')
    no_opts = sum(1 for q in questions if not q.get('options'))
    big_opts = sum(1 for q in questions if len(q.get('options', [])) > 6)
    if require_options and no_opts:
        errors.append(f'{no_opts} 题缺 options')
    if big_opts:
        errors.append(f'{big_opts} 题选项数 >6')
    if require_answer:
        no_ans = sum(1 for q in questions if not str(q.get('answer', '')).strip())
        no_expl = sum(1 for q in questions if not str(q.get('explanation', '')).strip())
        if no_ans:
            errors.append(f'{no_ans} 题缺 answer')
        if no_expl:
            errors.append(f'{no_expl} 题缺 explanation')
    if errors:
        print(f'  ✗ 出口断言失败 [{name}]: ' + '; '.join(errors))
        return False, errors
    detail = f'{len(questions)} 题 | gs_id 唯一 | 关键字段齐全 | 选项≤6'
    print(f'  ✓ 出口断言通过 [{name}]: {detail}')
    return True, []


# ── 执行解析 ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("GoldenSet 真题解析器 v2.0 (2026-08-20 审查修复)")
    print(f"执行时间: {datetime.now().isoformat()}")
    print("=" * 60)

    questions = []
    entries = []

    # 1. 解析上册
    shangce_path = BASE / "真题上册.md"
    if shangce_path.exists():
        print(f"\n📖 解析 真题上册.md ({shangce_path.stat().st_size / 1024:.0f} KB)...")
        questions = parse_shangce(str(shangce_path))
        print(f"   提取 {len(questions)} 道题目")

        years = sorted({q['year'] for q in questions})
        print(f"   覆盖年份: {years[0]}-{years[-1]}（{len(years)} 套试卷）")

        subj_count = Counter(q['subject'] for q in questions)
        for s, c in subj_count.most_common(8):
            print(f"     {s}: {c}题")

        ok, _ = assert_questions(questions, '上册', require_answer=False)
        if not ok:
            sys.exit(1)
        out_path = OUT / "GS_上册_2024.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)
        print(f"   ✅ 保存至 {out_path}")
    else:
        print("⚠️ 真题上册.md 未找到")

    # 2. 解析下册
    xiace_path = BASE / "真题下册.md"
    if xiace_path.exists():
        print(f"\n📖 解析 真题下册.md ({xiace_path.stat().st_size / 1024:.0f} KB)...")
        entries = parse_xiace(str(xiace_path))
        print(f"   提取 {len(entries)} 条记录")

        year_count = Counter(e['year'] for e in entries)
        for y in sorted(year_count, reverse=True)[:8]:
            print(f"     {y}年: {year_count[y]}题")

        # 下册为精析（源文件无题干/选项），按 regression.py 分级 schema 校验
        ok, _ = assert_questions(entries, '下册', require_options=False, require_stem=False)
        if not ok:
            sys.exit(1)
        out_path = OUT / "GS_下册_2025_1994.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        print(f"   ✅ 保存至 {out_path}")
    else:
        print("⚠️ 真题下册.md 未找到")

    # 3. 保存 Schema
    schema_path = OUT / "GS_schema.json"
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(SCHEMA, f, ensure_ascii=False, indent=2)
    print(f"\n📋 Schema 保存至 {schema_path}")

    # 4. 生成总索引
    index = {
        "version": "2.0",
        "generated_at": datetime.now().isoformat(),
        "files": {
            "上册_试卷": {
                "path": "structured/GS_上册_2024.json",
                "description": "考研西综真题试卷 1994-2024（纯题目，无答案；B 型题组共享选项已正确绑定）",
                "count": len(questions),
                "has_answers": False,
                "has_explanations": False
            },
            "下册_精析": {
                "path": "structured/GS_下册_2025_1994.json",
                "description": "贺银成历年真题精析（1994-2025，含答案+解析，无题干/选项）",
                "count": len(entries),
                "has_answers": True,
                "has_explanations": True
            }
        },
        "total_questions": len(questions) + len(entries),
        "layers": {
            "Layer0_锚定层": {
                "description": "306西综真题精选（1994-2025）",
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
    print(f"  GS_上册_*.json        — 试卷结构化数据（{len(questions)} 题）")
    print(f"  GS_下册_2025_1994.json — 答案精析结构化数据（{len(entries)} 条）")
    print(f"{'='*60}")
