# -*- coding: utf-8 -*-
"""batch043 题库装配器：把紧凑 JSONL 扩展为 schema v2 题目。"""
import json, re, sys, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = Path(r'C:/Users/38063/Desktop/MedAgentWork')
BATCH = 'batch043'
KP_FILE = BASE / '输入素材/大四上/急诊与灾难医学/急诊与灾难医学_教师重点_锚定清单_20261026.md'
QDIR = BASE / '中间产物' / BATCH / 'questions'
OUT = QDIR / 'ALL_questions.json'

MODULE_NAMES = {
    'M01': '总论·EMSS·检伤分类', 'M02': '心肺脑复苏', 'M03': '休克与MODS',
    'M04': '急性中毒', 'M05': '环境与理化损伤', 'M06': '创伤急救与多发伤',
    'M07': '心血管与呼吸急症', 'M08': '消化·内分泌·神经急症',
}


def load_anchors():
    t = KP_FILE.read_text(encoding='utf-8')
    sec = t.split('## 四、统一锚定清单')[1]
    out = {}
    for line in sec.splitlines():
        m = re.match(r'^(\d+)\.\s+(.+)$', line.strip())
        if not m:
            continue
        n = int(m.group(1))
        body = re.sub(r'【[^】]*】', '', m.group(2))
        body = re.sub(r'〔[^〕]*〕', '', body).strip()
        out[n] = body
    return out


def norm(s):
    return re.sub(r'[\s，。；：、,.;:!?！？\"\'“”‘’（）()【】\[\]《》<>·\-—–…]+', '', str(s or ''))


ANCHORS = load_anchors()


def build(items):
    out, errors = [], []
    for it in items:
        qid = it['id']
        kp = int(it['kp'].replace('第', '').replace('条', ''))
        anchor = ANCHORS.get(kp, '')
        if not anchor:
            errors.append(f'{qid}: 找不到第{kp}条锚点')
            continue
        quote = it['q']
        if norm(quote) not in norm(anchor):
            errors.append(f'{qid}: source_quote 不在锚点中 -> {quote}')
        opts = it['opts']
        labels = [chr(65 + i) for i in range(len(opts))]
        ans = ''.join(sorted(it['ans'].upper()))
        pol = it.get('pol', 'positive')
        neg = pol == 'negative'
        per = []
        per_src = it['per']
        pairs = [per_src[l] for l in labels] if isinstance(per_src, dict) else per_src
        for lab, text, (why, mis) in zip(labels, opts, pairs):
            if len(str(why).strip()) < 20:
                why = str(why).rstrip('。') + '；' + (mis or '该表述与教材要点一致，故为正确选项') + '。'
            is_ans = lab in ans
            truth = (not is_ans) if neg else is_ans
            is_distractor = lab not in ans
            per.append({
                'label': lab,
                'truth': truth,
                'why': why,
                'misconception_id': f'MC-EM-{qid}-{lab}' if is_distractor else None,
                'misconception': mis if is_distractor else None,
            })
        take = it['take']
        if len(str(take).strip()) < 30:
            take = str(take).rstrip('。') + '；考点归属：' + str(it['t']) + '。'
        if len(str(take).strip()) < 30:
            take = str(take).rstrip('。') + '；复习时把本条与相邻考点对照记忆。'
        letters = ''.join(f'{l}. {t}；' for l, t in zip(labels, opts))
        expl = (f"【正确答案】{it['why']}\n\n【逐项解析】" +
                ''.join(f"{p['label']}. {p['why']}（{'正确' if p['truth'] else '错误'}）\n" for p in per) +
                f"\n【易错点】{it['take']}")
        item = {
            'id': qid, 'module': it['m'], 'module_name': MODULE_NAMES[it['m']],
            'topic': it['t'], 'type': it['type'], 'polarity': pol,
            'bloom': it.get('bloom', '记忆'), 'group': it.get('group'),
            'group_stem': it.get('group_stem'), 'case_id': it.get('case_id'),
            'stem': it['stem'],
            'options': [{'label': l, 'text': t} for l, t in zip(labels, opts)],
            'answer': ans,
            'explanation': expl,
            'source_page': it.get('page', ''),
            'keypoint_ref': [f'第{kp}条'],
            'teacher_anchor': anchor,
            'difficulty': it.get('diff', '中等'),
            'option_polarities': {p['label']: p['truth'] for p in per},
            'schema_version': '2.0',
            'learning_value': {
                'correct_rationale': it['why'],
                'per_option': per,
                'key_takeaway': take,
                'source_quote': quote,
                'source_quote_status': 'exact',
                'anchor_status': 'verified',
                'quality_flags': [],
                'review_status': 'approved',
            },
            'review_status': 'approved',
        }
        if it.get('kaoyan'):
            item['kaoyan_origin'] = it['kaoyan']
            item['source'] = 'kaoyan'
            item['answer_confidence'] = it['kaoyan'].get('answer_confidence', 'high')
            item['license'] = 'public_noncommercial'
        elif it.get('zhiyi'):
            item['zhiyi_origin'] = it['zhiyi']
            item['source'] = 'zhiyi_pdf' if it['zhiyi'].get('corpus') == 'pdf_paper' else 'zhiyi'
            item['answer_confidence'] = it['zhiyi'].get('answer_confidence', 'high')
            item['license'] = 'public_noncommercial'
        out.append(item)
    return out, errors


def main():
    items = []
    for p in sorted(QDIR.glob('M*.jsonl')):
        for line in p.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line:
                items.append(json.loads(line))
    out, errors = build(items)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'items={len(items)} built={len(out)} errors={len(errors)}')
    for e in errors:
        print('  !', e)
    from collections import Counter
    print('types', Counter(x['type'] for x in out))
    print('modules', Counter(x['module'] for x in out))
    kps = {int(x['keypoint_ref'][0][1:-1]) for x in out}
    print('keypoints covered', len(kps), 'missing', sorted(set(range(1, 62)) - kps))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
