import sys
sys.stdout.reconfigure(encoding='utf-8')

txt_path = r'c:\Users\38063\Desktop\MedAgentWork\输入素材\大四上\急诊与灾难医学\急诊与灾难医学_第4版_v1.txt'
out_dir = r'c:\Users\38063\Desktop\MedAgentWork\中间产物\batch035'

with open(txt_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

sections = {
    'M1': (533, 733),
    'M2': (7857, 8873),
    'M7': (10406, 11592),
    'M8': (11592, 12366),
    'M9': (12366, 13327),
    'M10': (13327, 13926),
    'M11': (13926, 14535),
}

for mod, (start, end) in sections.items():
    out_path = f'{out_dir}/_text_{mod}.txt'
    with open(out_path, 'w', encoding='utf-8') as out:
        out.writelines(lines[start:end])
    print(f'{mod}: {end-start} lines -> {out_path}')