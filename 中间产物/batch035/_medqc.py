"""
MedQC: Review and categorize GATE-A2 failures for batch035.
Reads the validate report and categorizes each failure by severity and fix approach.
"""
import json, sys, os
sys.stdout.reconfigure(encoding='utf-8')

base = r'c:\Users\38063\Desktop\MedAgentWork\中间产物\batch035'
report_path = r'c:\Users\38063\Desktop\MedAgentWork\reports\validate\validate_options_report_batch035.json'

with open(report_path, 'r', encoding='utf-8') as f:
    report = json.load(f)

with open(f'{base}/ALL_questions.json', 'r', encoding='utf-8') as f:
    questions = json.load(f)
q_by_id = {q['id']: q for q in questions}

# Categorize issues
categories = {
    'R2_length_ratio': {'count': 0, 'ids': [], 'fix': 'shorten longest option or lengthen shortest'},
    'R13_option_too_long': {'count': 0, 'ids': [], 'fix': 'shorten options to ≤20 chars'},
    'R10_keyword_repetition': {'count': 0, 'ids': [], 'fix': 'add keyword to at least one distractor'},
    'R6_numerical_ratio': {'count': 0, 'ids': [], 'fix': 'adjust distractor values to be closer'},
    'R8_missing_unit': {'count': 0, 'ids': [], 'fix': 'add units to numerical values'},
    'R3_not_sorted': {'count': 0, 'ids': [], 'fix': 'sort numerical options'},
    'R4_negation_not_bold': {'count': 0, 'ids': [], 'fix': 'bold negation words'},
    'R1_absolute_language': {'count': 0, 'ids': [], 'fix': 'remove absolute words'},
    'R11_convergence': {'count': 0, 'ids': [], 'fix': 'adjust distractors'},
    'S4_absolute': {'count': 0, 'ids': [], 'fix': 'remove absolute qualifiers'},
    'other': {'count': 0, 'ids': [], 'fix': 'review manually'}
}

failure_ids = set()
for item in report.get('results', report.get('items', [])):
    qid = item.get('question_id', item.get('id', ''))
    if not qid:
        continue
    failure_ids.add(qid)
    # Categorize based on issue type
    issues = item.get('issues', item.get('failures', item.get('warnings', [])))
    for issue in issues:
        rule = issue.get('rule', '')
        mapped = False
        for cat in ['R2', 'R13', 'R10', 'R6', 'R8', 'R3', 'R4', 'R1', 'R11', 'S4']:
            if rule.startswith(cat):
                categories[cat if cat in categories else 'other']['count'] += 1
                categories[cat if cat in categories else 'other']['ids'].append(qid)
                mapped = True
                break
        if not mapped:
            categories['other']['count'] += 1
            categories['other']['ids'].append(qid)

# Deduplicate ids
for cat in categories:
    categories[cat]['ids'] = list(set(categories[cat]['ids']))

print('=' * 60)
print('MedQC REPORT: batch035 急诊与灾难医学')
print('=' * 60)
print(f'Total questions with failures: {len(failure_ids)}')
print(f'Total questions: {len(questions)}')
print(f'Pass rate: {(len(questions)-len(failure_ids))/len(questions)*100:.1f}%')
print()

print('--- Failure Categories ---')
for cat, info in sorted(categories.items(), key=lambda x: -x[1]['count']):
    if info['count'] > 0:
        print(f'  {cat}: {info["count"]} occurrences, {len(info["ids"])} questions affected')
        print(f'    Fix: {info["fix"]}')

# Module-level failure rate
module_failures = {}
for q in questions:
    m = q['module']
    if m not in module_failures:
        module_failures[m] = {'total': 0, 'failed': 0}
    module_failures[m]['total'] += 1
    if q['id'] in failure_ids:
        module_failures[m]['failed'] += 1

print()
print('--- Module Failure Rates ---')
for m in sorted(module_failures.keys()):
    info = module_failures[m]
    rate = info['failed']/info['total']*100
    bar = '█' * int(rate/10) + '░' * (10-int(rate/10))
    print(f'  {m}: {info["failed"]}/{info["total"]} ({rate:.0f}%) {bar}')
print()

# Kaoyan assessment
ko_count = sum(1 for q in questions if 'kaoyan_origin' in q)
print(f'--- Kaoyan Origin Assessment ---')
print(f'  Current: {ko_count}/{len(questions)} ({ko_count/len(questions)*100:.1f}%)')
print(f'  Target: 15-25% (33-55 questions)')
print(f'  Shortfall: {max(0, 33-ko_count)} questions')
print(f'  Note: M10(灾难医学) and M11(灾难现场医学救援) have no kaoyan candidates available')
print(f'  HC-18: "无真题覆盖章节以原创补齐并如实标注"')

print()
print('--- QC Summary ---')
print(f'Overall assessment: FAIL (GATE-A2 failures = {len(failure_ids)}, need 0)')
print(f'Recommendation: Proceed to MedFix with focus on R2 and R13 issues')
print(f'  R2+R13 account for {categories["R2_length_ratio"]["count"] + categories["R13_option_too_long"]["count"]} of {sum(c["count"] for c in categories.values())} issues')
print(f'  These are mechanical fixes suitable for batch processing')