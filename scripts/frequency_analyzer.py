#!/usr/bin/env python3
"""考点频率分析器 v1.0 — GoldenSet+贺银成真题→高频考点CSV+热点JSON"""
import json, sys, re, csv, argparse
from pathlib import Path
from collections import Counter
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = Path(__file__).parent

DISEASE_PATTERNS = [
    r'(?:急性|慢性)?(?:(?:稳定性|不稳定性)\s*)?(?:心力衰竭|心衰|冠心病|心肌梗死|高血压|心律失常|房颤|室颤)',
    r'(?:COPD|慢性阻塞性肺疾病|哮喘|支气管哮喘|肺炎|肺结核|肺癌|呼吸衰竭|呼衰|肺栓塞|肺心病)',
    r'(?:消化性溃疡|胃炎|胃癌|肝硬化|肝癌|胰腺炎|炎症性肠病|克罗恩|溃疡性结肠炎)',
    r'(?:肾小球肾炎|肾病综合征|肾衰竭|尿毒症|尿路感染|肾盂肾炎)',
    r'(?:糖尿病|甲亢|甲减|库欣|痛风)',
    r'(?:贫血|缺铁贫|巨幼贫|再障|溶血|白血病|淋巴瘤|骨髓瘤|DIC|ITP)',
    r'(?:脑梗死|脑出血|脑栓塞|TIA|蛛网膜下腔出血|帕金森|癫痫|偏头痛|阿尔茨海默)',
    r'(?:GBS|吉兰-巴雷|重症肌无力|MG|面神经|三叉神经|多发性硬化|MS)',
    r'(?:精神分裂症|抑郁障碍|抑郁症|双相障碍|躁狂|焦虑|强迫症|OCD|PTSD)',
    r'(?:阑尾炎|胆囊炎|胆结石|肠梗阻|疝|骨折|烧伤|休克|创伤)',
    r'(?:阴阳|五行|藏象|辨证|八纲|六经|卫气营血)',
    r'(?:麻黄汤|桂枝汤|小柴胡汤|四君子汤|四物汤|六味地黄丸)',
]

EXAM_DIMS = [
    '诊断标准', '鉴别诊断', '首选检查', '首选治疗', '治疗原则', '病因', '发病机制',
    '临床表现', '并发症', '分类', '分型', '分期', '分级', '预后', '禁忌症', '副作用',
    '药物相互作用', '解剖定位', '传导通路', '综合征', '方剂组成', '配伍',
]

def extract_knowledge_points(text):
    points = []
    for dp in DISEASE_PATTERNS:
        m = re.search(dp, text)
        if m:
            disease = m.group(0)
            for dim in EXAM_DIMS:
                if dim in text:
                    points.append((disease, dim))
    return points

def parse_goldenset_md(golden_dir):
    points = []
    gd = Path(golden_dir)
    if not gd.exists(): return points
    for f in gd.glob('*.md'):
        with open(f, 'r', encoding='utf-8') as fh:
            text = fh.read()
        for line in text.split('\n'):
            if re.match(r'^\d+[.、)]', line) or line.startswith('##'):
                points.extend(extract_knowledge_points(line))
    return points

def build_frequency_matrix(points):
    counter = Counter(points)
    hotspots = {'high': [], 'medium': [], 'cold': []}
    for (disease, dim), count in counter.most_common():
        if count >= 3: hotspots['high'].append({'disease': disease, 'dimension': dim, 'count': count})
        elif count >= 1: hotspots['medium'].append({'disease': disease, 'dimension': dim, 'count': count})
    return counter, hotspots

def main():
    parser = argparse.ArgumentParser(description='考点频率分析器')
    parser.add_argument('--golden', default='GoldenSet/', help='GoldenSet目录')
    parser.add_argument('--subject', default='all', help='科目名')
    parser.add_argument('--top', type=int, default=20, help='Top-N高频')
    parser.add_argument('--output', default=None, help='输出文件(JSON)')
    args = parser.parse_args()

    print(f"科目: {args.subject}")
    points = parse_goldenset_md(args.golden)
    print(f"提取考点: {len(points)} 个")
    counter, hotspots = build_frequency_matrix(points)
    print(f"高频(≥3次): {len(hotspots['high'])} | 中频: {len(hotspots['medium'])}")
    if hotspots['high']:
        print(f"\nTop {min(args.top, len(hotspots['high']))} 高频考点:")
        for item in hotspots['high'][:args.top]:
            print(f"  [{item['count']}次] {item['disease']} — {item['dimension']}")

    output_path = args.output or f'reports/frequency/{args.subject}_hotspots.json'
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'subject': args.subject,
            'generated_at': datetime.now().isoformat(),
            'total_points': len(points),
            'unique_points': len(counter),
            'high_frequency': hotspots['high'],
            'quota_advice': {'high_x1.5': len(hotspots['high']), 'cold_x0.5': 0}
        }, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已保存: {output_path}")

if __name__ == '__main__':
    main()
