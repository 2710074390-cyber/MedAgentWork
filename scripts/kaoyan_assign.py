#!/usr/bin/env python3
"""
kaoyan_assign.py — 按模块分配「答案可信」的考研真题（HC-18 配额） v1.0

依赖 kaoyan_answer_fix.py 产出的 question_bank/kaoyan_answers.json（答案已恢复+校验）。
只分配答案经过交叉校验的真题，杜绝把 GoldenSet 行首选项前缀误当答案。

用法:
  python scripts/kaoyan_assign.py --out 中间产物/batch031/kaoyan_assigned.json --per-module 4
"""
import sys, json, re, glob, argparse, collections
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = Path(__file__).resolve().parent.parent
ANS_FILE = BASE / 'question_bank' / 'kaoyan_answers.json'

# 23 模块 → 关键词（权重：题干 3 / 选项 1 / 解析 1）
MODULES = [
    ("M1",  "消化系统总论",        "消化不良|胃肠|消化系统|消化道|吞咽困难|恶心呕吐|腹泻|便秘|黄疸|腹痛"),
    ("M2",  "胃食管反流病",        "反流|烧心|GERD|食管炎|Barrett|食管裂孔疝|食管下括约肌|LES"),
    ("M3",  "胃炎",              "胃炎|萎缩性胃炎|幽门螺杆菌|Hp|胃黏膜萎缩|自身免疫性胃炎|A型胃炎"),
    ("M4",  "消化性溃疡",         "消化性溃疡|胃溃疡|十二指肠溃疡|溃疡病|PU|幽门螺杆菌|NSAID|溃疡并发症|穿孔|幽门梗阻"),
    ("M5",  "胃癌",              "胃癌|胃恶性肿瘤|皮革胃|印戒细胞|早期胃癌|进展期胃癌|胃镜活检"),
    ("M6",  "炎症性肠病",         "溃疡性结肠炎|克罗恩|炎症性肠病|IBD|黏液脓血便|结肠镜|回肠末段|跳跃"),
    ("M7",  "脂肪性肝病",         "脂肪肝|非酒精性脂肪性肝病|NAFLD|酒精性肝病|ALD|肝酶升高|代谢相关脂肪性肝病"),
    ("M8",  "肝硬化",            "肝硬化|门静脉高压|肝性脑病|腹水|食管胃底静脉|脾大|假小叶|Child|自发性细菌性腹膜炎|肝肾综合征"),
    ("M9",  "原发性肝癌",         "原发性肝癌|肝细胞癌|HCC|甲胎蛋白|AFP|肝占位|肝动脉化疗栓塞"),
    ("M10", "消化道出血",         "上消化道出血|呕血|黑便|便血|食管胃底静脉曲张破裂|失血性休克|内镜止血|三腔二囊管"),
    ("M11", "肾小球肾炎",         "肾小球肾炎|急性肾炎|急进性肾炎|IgA肾病|血尿|蛋白尿|肾病综合征|肾小球|急性肾小球肾炎|链球菌"),
    ("M12", "肾病综合征",         "肾病综合征|大量蛋白尿|低白蛋白血症|水肿|高脂血症|微小病变|膜性肾病|激素|泼尼松"),
    ("M13", "尿路感染",           "尿路感染|膀胱炎|肾盂肾炎|尿频|尿急|尿痛|白细胞尿|尿培养|大肠杆菌|UTI"),
    ("M14", "慢性肾衰竭",         "慢性肾衰竭|慢性肾脏病|CKD|尿毒症|肾小球滤过率|GFR|透析|血肌酐升高|肾性贫血|肾性骨病"),
    ("M15", "内分泌总论",         "内分泌|激素|垂体|肾上腺皮质|库欣|嗜铬细胞瘤|原发性醛固酮|激素分泌|负反馈"),
    ("M16", "甲状腺功能亢进症",     "甲亢|甲状腺功能亢进|Graves|甲状腺毒症|突眼|甲状腺肿大|TSH|游离T3|游离T4|抗甲状腺药物|甲巯咪唑|丙硫氧嘧啶|131", ),
    ("M17", "糖尿病",            "糖尿病|胰岛素|酮症酸中毒|高渗|糖化血红蛋白|HbA1c|降糖|空腹血糖|糖耐量|二甲双胍|糖尿病肾病|糖尿病视网膜"),
    ("M18", "风湿性疾病总论",      "风湿性疾病|关节炎|自身抗体|抗核抗体|结缔组织病|关节痛|晨僵|滑膜炎"),
    ("M19", "类风湿关节炎",       "类风湿|类风湿关节炎|类风湿因子|RF|关节畸形|滑膜炎|晨僵|抗CCP|DMARD|甲氨蝶呤"),
    ("M20", "系统性红斑狼疮",      "红斑狼疮|SLE|狼疮|抗dsDNA|抗Sm|抗核抗体|免疫复合物|狼疮肾炎|光过敏|蝶形红斑|补体C3"),
    ("M21", "理化因素所致疾病总论", "中暑|物理因素|高原病|电击|淹溺|电离辐射|减压病|热射病|冻伤|噪声"),
    ("M22", "中毒总论",          "中毒|毒物|解毒|洗胃|活性炭|清除毒物|特效解毒|催吐|导泻|血液净化|一氧化碳"),
    ("M23", "急性有机磷杀虫药中毒", "有机磷|胆碱酯酶|ChE|阿托品|中间型综合征|复能剂|解磷定|氯解磷定|毒蕈碱|烟碱|胆碱能|阿托品化"),
]

LATEX_CLEAN = [
    (re.compile(r'\$([^$]{1,60})\$'), r'\1'),
    (re.compile(r'\\mathrm\{([^}]*)\}'), r'\1'),
    (re.compile(r'\\geqslant|\\geq'), '≥'),
    (re.compile(r'\\leqslant|\\leq'), '≤'),
    (re.compile(r'\\sim'), '~'),
    (re.compile(r'\\%'), '%'),
    (re.compile(r'【\d{4}NO\d+】'), ''),
    (re.compile(r'!\[[^\]]*\]\([^)]*\)'), ''),
    (re.compile(r'```mermaid[\s\S]*?```'), ''),
    (re.compile(r'<[^>]{1,200}>'), ''),
    (re.compile(r'_{2,}'), ''),
]


def clean(s):
    if not isinstance(s, str):
        return ''
    for p, r in LATEX_CLEAN:
        s = p.sub(r, s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--per-module', type=int, default=4)
    args = ap.parse_args()

    answers = json.load(open(ANS_FILE, encoding='utf-8'))
    up = []
    for f in sorted(glob.glob(str(BASE / 'GoldenSet' / 'structured' / 'GS_上册_*.json'))):
        up += json.load(open(f, encoding='utf-8'))
    upm = {q['gs_id']: q for q in up}

    pool = [q for q in upm.values() if q['gs_id'] in answers and q.get('stem') and q.get('options')]
    print(f'可用真题池（题干+选项+可信答案）：{len(pool)} 条')

    scored = collections.defaultdict(list)
    for q in pool:
        a = answers[q['gs_id']]
        stem, opts, expl = q['stem'], q['options'], a.get('explanation', '')
        for mid, mname, kw in MODULES:
            rx = re.compile(kw)
            s = 3 * len(rx.findall(stem)) + 1 * len(rx.findall(' '.join(opts))) + 1 * len(rx.findall(expl[:600]))
            if s > 0:
                scored[mid].append((s, q['gs_id']))

    used, assigned, warn = set(), [], []
    for mid, mname, kw in MODULES:
        cands = [g for s, g in sorted(scored[mid], key=lambda x: -x[0]) if g not in used]
        got = 0
        for g in cands:
            if got >= args.per_module:
                break
            q, a = upm[g], answers[g]
            opts = [clean(o) for o in q['options']]
            n = len(opts)
            ans = a['answer_recovered']
            # 一致性校验：答案字母必须在选项范围内
            if max(ord(c) - 64 for c in ans) > n:
                warn.append(f'{g} 答案 {ans} 超出 {n} 个选项 → 跳过')
                continue
            if any(not o for o in opts):
                warn.append(f'{g} 选项清洗后为空 → 跳过')
                continue
            opts = opts[:5]
            if max(ord(c) - 64 for c in ans) > len(opts):
                continue
            used.add(g)
            got += 1
            assigned.append({
                'module': mid, 'module_name': mname,
                'gs_id': g, 'year': a['year'],
                'source': f"{a['year']}考研西综·第{a['question_no']}题",
                'stem': clean(q['stem']),
                'options': opts,
                'answer': ans,
                'explanation': clean(a['explanation'])[:600],
                'kaoyan_origin': {'gs_id': g, 'year': a['year'],
                                  'source': f"{a['year']}考研西综·第{a['question_no']}题",
                                  'mode': '原题'},
                'answer_confidence': a['confidence'],
            })
        if got < args.per_module:
            warn.append(f'{mid} {mname}：仅分配到 {got}/{args.per_module} 条真题（题库无可靠覆盖，由原创补齐）')

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(assigned, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    per = collections.Counter(x['module'] for x in assigned)
    print(f'\n✅ 已分配 {len(assigned)} 条真题 → {args.out}')
    for mid, mname, _ in MODULES:
        print(f'  {mid:4s} {mname:16s} {per.get(mid,0)} 条')
    if warn:
        print('\n⚠ 告警：')
        for w in warn:
            print('  -', w)


if __name__ == '__main__':
    main()
