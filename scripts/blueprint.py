#!/usr/bin/env python3
"""blueprint.py — 考频蓝图 v1（零 API 成本）

原理：贺银成真题解析中大量「查阅【2009NO122】」式跨题引用，构成 30 年真题复现网络。
被引用越多的历史真题 = 复现率越高的经典考点。按学科聚合后即为出题配额权重矩阵的原料。

数据源（本地）：
  GoldenSet/structured/GS_下册_2025_1994.json      主源：4,448 条含解析（subject 字段可用）
  知识库素材/chunks_metadata/heyincheng-zt2_chunks.jsonl  辅源：贺银成真题下册解析 chunks
  GoldenSet/structured/GS_上册_2024.json           题干索引：为高复现真题回填题干

用法：
  python scripts/blueprint.py                 # 全量扫描 → 知识库素材/blueprint.json
  python scripts/blueprint.py --top 20        # 额外打印 Top20 高复现真题（含题干）
  python scripts/blueprint.py --out 路径.json  # 自定义输出

说明：
  - 本版为 prelim-v1（纯正则，无嵌入）。章节级聚类（题干→章节 embed）留待 E-1b。
  - 遵循 CONTEXT.md Windows 规范：stdout 强制 utf-8。
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GS_DIR = os.path.join(ROOT, 'GoldenSet', 'structured')
KB_META = os.path.join(ROOT, '知识库素材', 'chunks_metadata')
DEFAULT_OUT = os.path.join(ROOT, '知识库素材', 'blueprint.json')

# 宽松模式：兼容【2009NO122】【2009N0122】【2009No.122】及方括号变体
REF = re.compile(r'[【\[](\d{4})\s*[NnＮ][Oo0Ｏ]\.?\s*(\d{1,3})\s*[】\]]')

# ── E-1b 章节分类器（2026-08-21 · 零嵌入 prelim）────────────────────
# 学科感知关键词表：按标准教材章节结构，对 top_referenced 题干做章节归因。
# 局限：关键词法非语义匹配，覆盖率有限；未命中 → chapter=None（诚实标注）。
SUBJECT_CHAPTERS = {
    '生理学': {
        '绪论': ['内环境', '稳态', '反馈', '前馈', '自动控制'],
        '细胞': ['细胞膜', '跨膜', '钠泵', '静息电位', '动作电位', '阈电位', '局部电位', '兴奋性', '离子通道', '第二信使'],
        '血液': ['血液', '血浆', '红细胞', '白细胞', '血小板', '血型', '凝血', '纤维蛋白', '血红蛋白', '血细胞'],
        '循环': ['心脏', '心动周期', '心输出量', '血压', '微循环', '心电图', '自律性', '心肌', '血管', '冠脉', '射血', '窦房结'],
        '呼吸': ['肺', '呼吸', '肺泡', '通气', '换气', '氧解离', '二氧化碳', '呼吸中枢', '潮气量', '肺活量'],
        '消化': ['胃肠', '消化', '胃液', '胰液', '胆汁', '吸收', '蠕动', '唾液', '小肠', '胃酸'],
        '泌尿': ['肾', '肾小球', '滤过', '重吸收', '尿', '排泄', '集合管', '肾单位', '膀胱'],
        '神经': ['神经元', '突触', '反射', '感觉', '运动', '自主神经', '脑', '脊髓', '神经递质', '受体'],
        '内分泌': ['激素', '内分泌', '甲状腺', '肾上腺', '胰岛', '垂体', '甲状旁腺', '糖皮质激素', '胰岛素'],
        '生殖': ['生殖', '睾酮', '雌激素', '孕激素', '排卵', '月经'],
        '感觉器官': ['眼', '耳', '视觉', '听觉', '前庭', '感受器'],
    },
    '生物化学': {
        '蛋白质': ['蛋白质', '氨基酸', '肽键', '构象', '多肽'],
        '核酸': ['核酸', 'DNA', 'RNA', '核苷酸', '碱基', '基因', '双螺旋', '嘌呤', '嘧啶'],
        '酶': ['酶', '辅酶', '抑制剂', '米氏', '活性中心', '同工酶', '酶原', '别构'],
        '糖代谢': ['糖酵解', '三羧酸', '磷酸戊糖', '糖原', '糖异生', '血糖', '丙酮酸'],
        '脂代谢': ['脂肪酸', '酮体', '胆固醇', '甘油三酯', '磷脂', '脂蛋白', '氧化'],
        '氨基酸代谢': ['转氨', '尿素', '氨基酸', '鸟氨酸', '一碳', '氨'],
        '生物氧化': ['呼吸链', '氧化磷酸化', 'ATP', '电子传递', 'NADH'],
        '基因表达': ['转录', '翻译', '复制', '密码子', '操纵子', '基因表达', '突变', '重组', '逆转录'],
        '血液生化': ['血红蛋白', '血浆蛋白', '胆红素'],
        '肝胆生化': ['肝', '胆汁酸', '胆色素'],
    },
    '病理学': {
        '细胞损伤': ['变性', '坏死', '凋亡', '萎缩', '肥大', '化生', '增生', '损伤', '钙化'],
        '修复': ['修复', '再生', '肉芽组织', '瘢痕', '创伤愈合'],
        '循环障碍': ['充血', '淤血', '出血', '血栓', '栓塞', '梗死', '水肿', '休克', 'DIC'],
        '炎症': ['炎症', '渗出', '化脓', '肉芽肿', '趋化', '白细胞'],
        '肿瘤': ['肿瘤', '癌', '肉瘤', '分化', '转移', '浸润', '异型性', '癌前'],
        '心血管': ['动脉粥样硬化', '冠心病', '高血压', '风湿', '心内膜炎', '心肌病', '心肌炎'],
        '呼吸系统': ['肺炎', '慢支', '肺气肿', '矽肺', '肺癌', '结核', '肺'],
        '消化系统': ['胃炎', '溃疡', '肝炎', '肝硬化', '肝癌', '胰腺', '肠'],
        '泌尿': ['肾炎', '肾病综合征', '肾盂肾炎', '肾癌', '肾'],
        '生殖乳腺': ['乳腺癌', '子宫', '卵巢', '前列腺', '宫颈', '乳腺'],
        '内分泌': ['甲状腺', '糖尿病', '胰岛', '肾上腺'],
        '神经系统': ['脑膜炎', '胶质瘤', '脑出血', '缺氧', '脑'],
        '传染病': ['结核', '伤寒', '痢疾', '梅毒', 'AIDS', '血吸虫', '艾滋病'],
    },
    '内科学': {
        '呼吸': ['COPD', '哮喘', '肺炎', '肺结核', '肺癌', '肺心病', '呼吸衰竭', '胸腔积液', '气胸', '肺栓塞', '支气管'],
        '循环': ['心衰', '冠心病', '心梗', '高血压', '心律失常', '瓣膜', '心肌病', '心包', '内膜炎', '房颤', '心绞痛'],
        '消化': ['溃疡', '胃炎', '肝硬化', '肝癌', '胰腺炎', '炎症性肠病', '消化道出血', '肠'],
        '泌尿': ['肾病', '肾炎', '肾衰竭', '肾病综合征', '尿路感染', '肾'],
        '血液': ['贫血', '白血病', '淋巴瘤', '血小板', '凝血', '骨髓瘤', '再障', '血'],
        '内分泌': ['糖尿病', '甲状腺', '甲亢', '肾上腺', '痛风', '胰岛素'],
        '风湿': ['类风湿', '红斑狼疮', '强直', '痛风'],
        '中毒': ['中毒', '有机磷', '毒物'],
    },
    '外科学': {
        '总论': ['无菌', '水电解质', '酸碱', '输血', '休克', '麻醉', '复苏', '感染', '创伤', '烧伤', '肿瘤', '移植', '营养', '引流', '切口'],
        '颅脑': ['颅脑', '颅内压', '脑疝', '颅骨', '脑'],
        '颈部': ['甲状腺', '颈'],
        '胸部': ['气胸', '血胸', '食管', '肺', '纵隔', '胸'],
        '腹部': ['疝', '阑尾', '肠梗阻', '胃癌', '结直肠', '肝胆', '胰腺', '脾', '腹膜', '溃疡', '胆'],
        '血管': ['动脉瘤', '静脉', '血管', '动脉'],
        '泌尿': ['泌尿', '肾', '膀胱', '前列腺', '结石'],
        '骨科': ['骨折', '脱位', '关节', '脊柱', '脊髓', '骨肿瘤', '骨', '半月板'],
    },
    '诊断学': {
        '症状学': ['发热', '疼痛', '黄疸', '水肿', '咯血', '呕血', '便血', '心悸', '呼吸困难', '眩晕'],
        '体格检查': ['体格检查', '视诊', '触诊', '叩诊', '听诊', '脉搏', '血压', '淋巴结', '肺部', '心脏'],
        '实验诊断': ['实验室', '血常规', '尿常规', '生化', '肝功能', '肾功能', '血糖', '血脂'],
        '器械检查': ['心电图', '影像', 'X线', 'CT', '超声', '内镜'],
    },
    '医学遗传学': {
        '遗传基础': ['染色体', '基因', '遗传', '孟德尔', '系谱', '突变', '等位'],
    },
    '医学心理学': {
        '心理基础': ['心理', '应激', '人格', '认知', '情绪', '医患', '焦虑', '抑郁'],
    },
    '医学伦理学': {
        '伦理原则': ['伦理', '知情同意', '隐私', '医德', '道德'],
    },
    '药理学': {
        '总论': ['药物', '受体', '药代', '药效', '给药'],
        '各论': ['抗菌药', '抗生素', '抗生素', '抗肿瘤', '降压药', '强心苷', '阿司匹林'],
    },
}


def classify_chapter(stem, subject):
    """题干 → 章节（学科感知关键词匹配，首个命中）。无匹配返回 None。"""
    if not stem or subject not in SUBJECT_CHAPTERS:
        return None
    for chapter, kws in SUBJECT_CHAPTERS[subject].items():
        for kw in kws:
            if kw in stem:
                return chapter
    return None


def scan_gs_lower():
    path = os.path.join(GS_DIR, 'GS_下册_2025_1994.json')
    data = json.load(open(path, encoding='utf-8'))
    targets = Counter()
    target_subjs = {}  # (y,n) → Counter(subject) 被引真题的学科归因（多数表决）
    subj_refs = Counter()
    subj_entries = Counter()
    entries_with_refs = 0
    year_trend = Counter()
    for e in data:
        expl = e.get('explanation') or ''
        refs = REF.findall(expl)
        subj = e.get('subject') or '未分类'
        subj_entries[subj] += 1
        if refs:
            entries_with_refs += 1
            year_trend[e.get('year')] += len(refs)
        for y, n in refs:
            t = (int(y), int(n))
            targets[t] += 1
            subj_refs[subj] += 1
            target_subjs.setdefault(t, Counter())[subj] += 1
    return {
        'entries': len(data),
        'targets': targets,
        'target_subjs': target_subjs,
        'subj_refs': subj_refs,
        'subj_entries': subj_entries,
        'entries_with_refs': entries_with_refs,
        'year_trend': year_trend,
    }


def scan_heyincheng():
    path = os.path.join(KB_META, 'heyincheng-zt2_chunks.jsonl')
    if not os.path.exists(path):
        return {'chunks': 0, 'targets': Counter(), 'refs': 0}
    targets = Counter()
    refs_total = 0
    n_chunks = 0
    for line in open(path, encoding='utf-8'):
        if not line.strip():
            continue
        n_chunks += 1
        text = json.loads(line).get('text', '')
        refs = REF.findall(text)
        refs_total += len(refs)
        for y, n in refs:
            targets[(int(y), int(n))] += 1
    return {'chunks': n_chunks, 'targets': targets, 'refs': refs_total}


def load_upper_index():
    path = os.path.join(GS_DIR, 'GS_上册_2024.json')
    data = json.load(open(path, encoding='utf-8'))
    idx = {}
    for e in data:
        idx[(e.get('year'), e.get('question_no'))] = e
    return len(data), idx


def main():
    ap = argparse.ArgumentParser(description='考频蓝图 v1（真题复现网络）')
    ap.add_argument('--top', type=int, default=0, help='打印 Top N 高复现真题')
    ap.add_argument('--out', default=DEFAULT_OUT, help='输出 JSON 路径')
    args = ap.parse_args()

    gs = scan_gs_lower()
    hy = scan_heyincheng()
    upper_n, upper_idx = load_upper_index()

    combined = gs['targets'] + hy['targets']

    vintage = Counter()
    for (y, _n), c in combined.items():
        vintage[y] += c

    top_list = []
    for (y, n), c in combined.most_common(100):
        up = upper_idx.get((y, n))
        stem = (up.get('stem', '')[:120] if up else None)
        subj_ctr = gs['target_subjs'].get((y, n))
        subject = subj_ctr.most_common(1)[0][0] if subj_ctr else None
        top_list.append({
            'year': y,
            'qno': n,
            'refs': c,
            'stem': stem,
            'stem_in_upper': up is not None,
            'subject': subject,
            'chapter': classify_chapter(stem, subject) if stem else None,
        })
    matched = sum(1 for t in top_list if t['stem_in_upper'])
    ch_attributed = sum(1 for t in top_list if t['chapter'])

    # E-1b: 章节级聚合（top_referenced 口径，按学科分组）
    by_subject_chapters = {}
    for t in top_list:
        subj = t['subject'] or '未分类'
        ch = t['chapter'] or '未分类章节'
        by_subject_chapters.setdefault(subj, {}).setdefault(ch, 0)
        by_subject_chapters[subj][ch] += t['refs']

    by_subject = {}
    for subj in sorted(gs['subj_entries'], key=lambda s: -gs['subj_refs'].get(s, 0)):
        by_subject[subj] = {
            'entries': gs['subj_entries'][subj],
            'refs': gs['subj_refs'].get(subj, 0),
            'refs_per_100_entries': round(gs['subj_refs'].get(subj, 0) * 100.0 / max(gs['subj_entries'][subj], 1), 1),
        }

    result = {
        'version': 'prelim-v1-e1b',
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'method': 'regex cross-references from GS lower explanations + heyincheng-zt2 chunks; '
                  'E-1b (2026-08-21): top_referenced chapter attribution via subject-aware keyword taxonomy '
                  '(zero-embedding prelim, keyword-only, not semantic)',
        'stats': {
            'gs_lower_entries': gs['entries'],
            'gs_lower_entries_with_refs': gs['entries_with_refs'],
            'gs_lower_refs': sum(gs['targets'].values()),
            'heyincheng_chunks': hy['chunks'],
            'heyincheng_refs': hy['refs'],
            'total_refs': sum(combined.values()),
            'unique_referenced_questions': len(combined),
            'upper_index_size': upper_n,
            'top100_stem_match': matched,
            'top100_chapter_attributed': ch_attributed,
        },
        'by_subject': by_subject,
        'by_subject_chapters': by_subject_chapters,
        'by_target_vintage': {str(y): c for y, c in sorted(vintage.items())},
        'refs_by_referring_year': {str(y or '未知'): c for y, c in sorted(gs['year_trend'].items(), key=lambda kv: (kv[0] is None, kv[0]))},
        'top_referenced': top_list,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    s = result['stats']
    print(f"[blueprint] GS下册 {s['gs_lower_entries']} 条，含引用 {s['gs_lower_entries_with_refs']} 条，引用 {s['gs_lower_refs']} 处")
    print(f"[blueprint] 贺银成zt2 {s['heyincheng_chunks']} chunks，引用 {s['heyincheng_refs']} 处")
    print(f"[blueprint] 合计 {s['total_refs']} 处引用 → {s['unique_referenced_questions']} 道唯一被引真题")
    print(f"[blueprint] Top100 题干回填率（上册匹配）: {s['top100_stem_match']}/100")
    print(f"[blueprint] E-1b 章节归因（关键词法 prelim）: {s['top100_chapter_attributed']}/100")
    print(f"[blueprint] 输出 → {args.out}")

    if args.top > 0:
        print(f"\n===== Top{args.top} 高复现真题（30 年复现网络）=====")
        for t in top_list[:args.top]:
            stem = t['stem'] if t['stem'] else '(上册未收录题干)'
            ch = f"[{t['subject']}/{t['chapter'] or '未分类章节'}]" if t['subject'] else "[学科未知]"
            print(f"  {t['refs']}× {t['year']}NO{t['qno']:>3} {ch}  {stem[:60]}")


if __name__ == '__main__':
    main()
