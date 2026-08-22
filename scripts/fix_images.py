"""
修复v3 HTML中的图集错位问题 v2
策略：
  1. 删除与教学内容无关的错位图
  2. 修正图注以描述实际图像内容
  3. 跨章节交换Fig291(锥体外系)和Fig302(视觉传导路)
"""
import re

HTML_PATH = r"C:\Users\38063\Desktop\MedAgentWork\输入素材\神经解剖图谱\神经病学解剖补课手册_v3.html"
OUT_PATH = r"C:\Users\38063\Desktop\MedAgentWork\输入素材\神经解剖图谱\神经病学解剖补课手册_v4.html"

with open(HTML_PATH, 'r', encoding='utf-8') as f:
    html = f.read()

# ====== PART 1: 删除与教学内容无关的错位图 ======
deletions = [
    ('694fe630f4b4f31913ee81faf39ad133002604a2ef38847e3371fc2a8f3cedfd', 'Fig211-神经元电镜（与脊髓位置无关）'),
    ('e3da3e2d9facf551bac1b3298d53da332c29147aaed127c1ea7e31791b26d24b', 'Fig223-脑桥横切面（非腹面观）'),
    ('7592f6a41f1fce2a225db7fcfd6a2459cea445cf2e1ccde06778b3a25401e640', 'Fig230-脑干动脉（非延髓横切面）'),
    ('6d843734ca6fc2a35f545dd39af7223725bdbd5d078d2d617026108250233bbe', 'Fig242-小脑分叶（非间脑）'),
    ('d868e8cdc19bc232aad55234e54fd030b97ed3d0dffbc9c34348e982a5e0a2a2', 'Fig246-中脑上丘横切面（与B章重复）'),
    ('c68d02450dda94d17fcf8e0de2728b512cc0df676ae2f249b4093a2a18564ff2', 'Fig248-大脑内侧面（D-1讲外侧面）'),
    ('860bdb7c8f888e87d11870764ca6071191c23a283c388490d07c3a8a68fc52f7', 'Fig260-大脑动脉（非冠状切面）'),
    ('6748217472bbc93dd6178c3d99c232df8a2163558d35fa663c237dda7cad726e', 'Fig279-眶内容（非CSF循环）'),
    # Fig 291 不删除——将其移动到J章
    # Fig 302 不删除——将其保留在H章并修正图注
]

removed_count = 0
for hash_prefix, reason in deletions:
    pattern = r'\n?<div class="figure"><img src="images_small/' + re.escape(hash_prefix) + r'[^"]*"[^>]*>.*?</div>\n?'
    match = re.search(pattern, html, re.DOTALL)
    if match:
        html = html[:match.start()] + html[match.end():]
        removed_count += 1
        print(f"[DEL] {reason}")
    else:
        print(f"[MISS] {reason} - pattern not found!")

print(f"\n删除: {removed_count}/{len(deletions)}")

# ====== PART 2: 修正图注 ======
caption_fixes = [
    # Fig 227 -> 延髓经蜗神经核水平
    ('c7fdff03f89e97a4e700eca3be259da0234e43cecce5c4e4cf719542e307cfaa',
     '<span class="figure-number">图227</span> 延髓横切面（经蜗神经核水平）— 前庭神经核群+面神经膝+三叉神经脊束核+蜗神经核+锥体束+绳状体+内侧纵束。注意面神经在此断面绕过展神经核形成「面神经膝」，再向前外走行'),

    # Fig 244 -> 小脑皮质细胞结构
    ('b6c5e6247419edfc719f11ad1aedd9ca5338dc8d983633a919ea63c5e2949f64',
     '<span class="figure-number">图245</span> 小脑皮质细胞结构——分子层（篮细胞+星状细胞）→梨状细胞层（Purkinje细胞，小脑皮质唯一传出神经元）→颗粒层（颗粒细胞+高尔基细胞）。传入：苔藓纤维→颗粒细胞→平行纤维→Purkinje；攀爬纤维→Purkinje（强兴奋，来自下橄榄核）'),

    # Fig 266 -> MCA中央支基底节水平
    ('e2346ef4c7ed569648800cc7350d90151fd561a6909edb58780f5befbdbdc6d0',
     '<span class="figure-number">图266</span> 大脑冠状切面（经基底节）示MCA中央支——豆纹动脉从MCA M1段发出→穿入壳核+苍白球+内囊后肢前2/3。高血压脑出血好发于此（豆纹动脉破裂→内囊出血→三偏综合征）'),

    # Fig 277 -> 硬脑膜静脉窦
    ('f789b78cff8a262ccd5629eef3aa2d26f8b6943db1456ce031eac14dd34f0402',
     '<span class="figure-number">图278</span> 硬脑膜及硬脑膜窦（冠状切面）——硬脑膜双层分离形成静脉窦：上矢状窦+横窦+直窦+乙状窦+窦汇+岩上窦+海绵窦。小脑幕分隔大脑枕叶与小脑，幕切迹处可发生脑疝'),

    # Fig 280 -> 眶内容外侧面
    ('2b5b3e9470913b54aabf9baead1b43cc4d7bd25eceb7c6c16f4d684f1b7bafbd',
     '<span class="figure-number">图281</span> 眶及眶内容（外侧面）——III动眼神经（上/下/内直肌+下斜肌+提上睑肌+瞳孔括约肌）、IV滑车神经（上斜肌）、VI展神经（外直肌）、V1眼神经（眶内感觉）。眶上裂=III/IV/V1/VI共同出颅通道，眶尖综合征=全部受累'),

    # Fig 302 (保留在H章) -> 视觉传导路
    ('4066f22a30ca1e2046f114fdbab205bc14e3f022408703718228986daa58ca46',
     '<span class="figure-number">图292</span> 视觉传导路及视野缺损——视网膜鼻侧纤维在视交叉交叉→对侧视束→外侧膝状体→视辐射→距状裂BA17视皮层。缺损模式：①视神经断=同侧全盲 ②视交叉中部断（垂体瘤）=双颞侧偏盲 ③视束/视辐射/视皮层断=对侧同向偏盲'),

    # Fig 300 -> 脑神经概览
    ('1c0dd35c888f91474552e6d2802676c26b0ee87adfc2f07c4c6cdb733e945b1f',
     '<span class="figure-number">脑神经概览</span> 12对脑神经分布全貌——I嗅(筛孔)→II视(视神经管)→III/IV(中脑→眶上裂)→V(脑桥→眶上裂/圆孔/卵圆孔)→VI(脑桥延髓沟→眶上裂)→VII/VIII(脑桥延髓沟→内耳门)→IX/X/XI(延髓→颈静脉孔)→XII(延髓→舌下神经管)'),

    # Fig 291 (移动到J章) -> 锥体外系
    # 注意：这个需要先提取，然后在J章插入
]

fixed_count = 0
for hash_prefix, new_caption in caption_fixes:
    old_pattern = r'(<div class="figure"><img src="images_small/' + re.escape(hash_prefix) + r'[^"]*"[^>]*><div class="figure-caption">)(.*?)(</div></div>)'
    match = re.search(old_pattern, html, re.DOTALL)
    if match:
        html = html[:match.start()] + match.group(1) + new_caption + match.group(3) + html[match.end():]
        fixed_count += 1
        print(f"[FIX] hash={hash_prefix[:16]}...")
    else:
        print(f"[MISS] hash={hash_prefix[:16]}...")

print(f"\n修正图注: {fixed_count}/{len(caption_fixes)}")

# ====== PART 3: 跨章交换 Fig291(锥体外系) <-> Fig302(视觉传导路) ======
# Fig 302 已修正图注保留在H章 ✅
# Fig 291 需要从H章移到J章

fig291_hash = '4a9380099584d716eb0d0f19cc0c88b2442f4e215db484fdc426e83a3d024282'
fig291_block_pattern = r'\n?<div class="figure"><img src="images_small/' + re.escape(fig291_hash) + r'[^"]*"[^>]*>.*?</div>\n?'
fig291_match = re.search(fig291_block_pattern, html, re.DOTALL)

if fig291_match:
    # 提取Fig 291完整块
    fig291_block = fig291_match.group()
    print(f"\n[MOVE] 提取Fig291块（{len(fig291_block)}字符）")

    # 从H章删除
    html = html[:fig291_match.start()] + html[fig291_match.end():]

    # 修正图注
    new_caption = '<span class="figure-number">图302</span> 锥体外系（纹状体-苍白球系）——纹状体→苍白球→丘脑→皮质的反馈环路。直接通路（纹状体D1→GPi/SNr→丘脑→皮质）易化运动；间接通路（纹状体D2→GPe→STN→GPi→丘脑→皮质）抑制运动。DA对D1兴奋、对D2抑制→总效果=促运动'
    fig291_block = re.sub(
        r'(<div class="figure-caption">)(.*?)(</div></div>)',
        r'\1' + new_caption + r'\3',
        fig291_block,
        flags=re.DOTALL
    )

    # 插入J章 J-2标题之后
    j2_marker = '<h2>J-2 直接通路 vs 间接通路——运动「油门」与「刹车」</h2>'
    if j2_marker in html:
        insert_pos = html.index(j2_marker) + len(j2_marker)
        html = html[:insert_pos] + '\n' + fig291_block + html[insert_pos:]
        print("[MOVE] Fig291(锥体外系)已移至J章J-2节")
    else:
        print("[WARN] J-2 marker not found, cannot insert Fig291")
else:
    print("\n[WARN] Fig291 block not found in H chapter")

# ====== PART 4: 版本信息更新 ======
html = html.replace('v3 · 讲解优先 · 图片点缀 · 2026-06-23', 'v4 · 图集错位修正版 · 2026-06-23')

# ====== 写入 ======
with open(OUT_PATH, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\n{'='*50}")
print(f"输出: {OUT_PATH}")
print(f"删除 {removed_count} 张错位图")
print(f"修正 {fixed_count} 张图注")
print(f"移动 1 张图跨章节 (Fig291: H→J)")
print(f"{'='*50}")
