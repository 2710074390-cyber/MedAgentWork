# -*- coding: utf-8 -*-
"""重写 6 张标注 YAML：精确 anchor 引线 + 文字放空白区；m05 用 overlay 覆盖 AI 原生文字"""
import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = r'C:\Users\38063\Desktop\MedAgentWork'
d = os.path.join(BASE, '复习资料', '口腔科学教学计划版', 'annotate_configs')
os.makedirs(d, exist_ok=True)
F = r'C:\Windows\Fonts\msyhbd.ttc'

def yml(name, image, fixes, output=None):
    lines = [f'image: raw/{image}', '',
             f'output: annotated/{output or name}.png', '', f'font: {F}', '', 'fixes:']
    for fix in fixes:
        box, text, mode = fix[0], fix[1], fix[2]
        lines.append(f'  - box: [{box[0]}, {box[1]}, {box[2]}, {box[3]}]')
        lines.append(f'    text: "{text}"')
        lines.append(f'    mode: {mode}')
        if len(fix) > 3 and fix[3]:
            lines.append(f'    anchor: [{fix[3][0]}, {fix[3][1]}]')
    return '\n'.join(lines) + '\n'

cfgs = {
 # 图2 面神经五支：脸朝左，神经主干右（腮腺），分支左扇形
 'm01_facial_nerve.yaml': ('m01_facial_nerve_raw.jpg', [
   ([400,250,550,295],'颞支','label',[487,394]),
   ([250,360,380,405],'颧支','label',[397,453]),
   ([250,455,380,500],'颊支','label',[389,503]),
   ([250,570,380,615],'下颌缘支','label',[433,620]),
   ([300,710,430,755],'颈支','label',[481,756]),
   ([760,520,890,565],'腮腺','label',[712,573]),
 ]),
 # 图5 龈炎 vs 牙周炎：左健康、右病变（右牙颈根深色带=牙周袋，下=骨吸收）
 'm03_gvp.yaml': ('m03_gvp_raw.jpg', [
   ([140,300,280,345],'健康牙龈','label',[300,330]),
   ([140,370,280,415],'釉牙骨质界','label',[430,360]),
   ([730,490,880,535],'牙周袋','label',[660,530]),
   ([730,630,880,675],'牙槽骨吸收','label',[660,660]),
 ]),
 # 图7 RAU 三型：左颊大溃疡=重型、右颊小溃疡=轻型、舌面簇=疱疹样、下唇内侧
 'm04_rau.yaml': ('m04_rau_raw.jpg', [
   ([60,60,200,105],'重型（左颊大溃疡）','label',[330,470]),
   ([240,60,400,105],'轻型（右颊小溃疡群）','label',[690,470]),
   ([420,60,580,105],'疱疹样（舌背密簇）','label',[530,590]),
   ([620,60,800,105],'下唇内侧溃疡','label',[470,780]),
 ]),
 # 图8 癌前病变 v2：双侧颊黏膜白斑 + 扁桃体/咽侧红斑
 'm04_precancer.yaml': ('m04_precancer_raw_v2.jpg', [
   ([60,60,200,105],'白斑（颊黏膜）','label',[360,430]),
   ([240,60,380,105],'白斑（颊黏膜）','label',[640,430]),
   ([420,60,560,105],'红斑','label',[320,570]),
   ([600,60,740,105],'红斑','label',[680,570]),
 ]),
 # 图9 修复体种类谱：用 v1 底图（七级名称正确），overlay 覆盖 AI 原生文字重写
 'm05_prosthesis.yaml': ('m05_prosthesis_raw.jpg', [
   ([120,640,210,835],'嵌体','overlay'),
   ([200,580,290,775],'贴面','overlay'),
   ([280,520,385,725],'全冠','overlay'),
   ([370,465,470,675],'桩核冠','overlay'),
   ([450,410,590,625],'固定桥','overlay'),
   ([570,330,720,515],'可摘局部义齿','overlay'),
   ([710,250,895,485],'全口义齿','overlay'),
 ]),
 # 图15 面神经瘫：左健侧、右患侧
 'm09_facial_palsy.yaml': ('m09_facial_palsy_raw.jpg', [
   ([60,60,180,105],'健侧','label',[300,400]),
   ([220,60,340,105],'患侧','label',[700,400]),
   ([380,60,560,105],'口角下垂（患侧）','label',[700,690]),
 ]),
}

for name, (img, fixes) in cfgs.items():
    open(os.path.join(d, name), 'w', encoding='utf-8').write(yml(name, img, fixes))
    print('重写', name)
print('完成', len(cfgs), '份')
