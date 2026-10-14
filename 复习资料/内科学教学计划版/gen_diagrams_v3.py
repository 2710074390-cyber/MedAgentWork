# -*- coding: utf-8 -*-
"""
内科学文字类导图 v3 重新生成
规范：宽度2400px固定，字号按可读底线设计，比例按内容类型匹配
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import os

# ============ 全局配置 ============
DPI = 200
FIG_W = 12  # inches → 2400px at 200dpi
OUT_DIR = r"C:\Users\38063\Desktop\MedAgentWork\复习资料\内科学教学计划版\images_v3"

plt.rcParams['font.family'] = 'Microsoft YaHei'
plt.rcParams['axes.unicode_minus'] = False

# 字号体系 (pt) — 2400px宽
FS = {
    'title': 40,      # 主标题
    'section': 28,    # 分区/列标题
    'node': 24,       # 节点主文字
    'sub': 20,        # 节点辅助文字/表格内容
    'note': 18,       # 标注
}

# 系统配色
COLORS = {
    'digest': {'main': '#2563EB', 'light': '#DBEAFE', 'bg': '#EFF6FF'},
    'renal': {'main': '#EA580C', 'light': '#FED7AA', 'bg': '#FFF7ED'},
    'endo': {'main': '#DC2626', 'light': '#FECACA', 'bg': '#FEF2F2'},
    'rheum': {'main': '#7C3AED', 'light': '#DDD6FE', 'bg': '#F5F3FF'},
    'tox': {'main': '#16A34A', 'light': '#BBF7D0', 'bg': '#F0FDF4'},
}

def new_fig(fig_h_inches, title=None):
    """创建新画布，fig_h_inches为高度(英寸)，返回fig和ax(0-1坐标)"""
    fig = plt.figure(figsize=(FIG_W, fig_h_inches), dpi=DPI, facecolor='white')
    ax = fig.add_axes([0.02, 0.02, 0.96, 0.90])  # 留顶部10%给标题
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    if title:
        fs = FS['title']
        box_w_px = 0.92 * FIG_W * DPI
        text_w_px = _estimate_text_width(title, fs)
        if text_w_px > box_w_px:
            fs = fs * box_w_px / text_w_px
        fig.text(0.5, 0.955, title, ha='center', va='center',
                 fontsize=fs, fontweight='bold', color='#1F2937')
    return fig, ax

def _estimate_text_width(text, fs):
    """估算文字宽度（像素）：中文字符=fs*DPI/72，其他=fs*DPI/72*0.6，取最长行"""
    px_per_pt = DPI / 72
    max_w = 0
    for line in str(text).split('\n'):
        w = 0
        for ch in line:
            if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
                w += fs * px_per_pt
            else:
                w += fs * px_per_pt * 0.6
        max_w = max(max_w, w)
    return max_w

def rbox(ax, x, y, w, h, color, edge=None, lw=2, radius=0.02, alpha=1.0, text=None,
         text_color='white', fontsize=None, fontweight='bold', va='center'):
    """画圆角矩形，x,y为左下角坐标(0-1)，w,h为宽高"""
    edge = edge or color
    r = min(radius, w * 0.4, h * 0.4)  # 限制圆角不超过框的40%
    box = FancyBboxPatch((x, y), w, h,
                         boxstyle=f"round,pad=0,rounding_size={r}",
                         facecolor=color, edgecolor=edge, linewidth=lw, alpha=alpha)
    ax.add_patch(box)
    if text:
        fs = fontsize or FS['node']
        # 自动缩字号：文字宽度超过框宽90%时按比例缩小
        box_w_px = w * FIG_W * DPI
        text_w_px = _estimate_text_width(text, fs)
        if text_w_px > box_w_px * 0.90:
            fs = fs * (box_w_px * 0.90) / text_w_px
            fs = max(fs, 12)  # 最小12pt
        ax.text(x + w/2, y + h/2, text, ha='center', va=va,
                fontsize=fs, color=text_color, fontweight=fontweight, linespacing=1.4)
    return box

def text_auto(ax, x, y, text, max_w=0.92, fontsize=None, **kwargs):
    """ax.text 自动缩字号，使文字宽度不超过 max_w（0-1 比例，默认92%画布宽）"""
    fs = fontsize or FS['node']
    box_w_px = max_w * FIG_W * DPI
    text_w_px = _estimate_text_width(text, fs)
    if text_w_px > box_w_px:
        fs = fs * box_w_px / text_w_px
        fs = max(fs, 12)
    ax.text(x, y, text, fontsize=fs, **kwargs)

def multiline_box(ax, x, y, w, h, color, lines, edge=None, lw=2, radius=0.02):
    """画带多行文字的框，lines为[(text, fontsize, color, weight), ...]"""
    edge = edge or color
    r = min(radius, w * 0.4, h * 0.4)
    box = FancyBboxPatch((x, y), w, h,
                         boxstyle=f"round,pad=0,rounding_size={r}",
                         facecolor=color, edgecolor=edge, linewidth=lw)
    ax.add_patch(box)
    n = len(lines)
    fig_h_in = ax.figure.get_figheight()
    line_heights = [fs * 1.4 / 72 / fig_h_in for _, fs, _, _ in lines]
    total_lh = sum(line_heights)
    top_pad = h * 0.12
    usable_h = h - top_pad * 2
    if total_lh > usable_h:
        scale = usable_h / total_lh
        line_heights = [lh * scale for lh in line_heights]
        total_lh = sum(line_heights)
    gap = (usable_h - total_lh) / max(n - 1, 1) if n > 1 else 0
    cur_y = y + h - top_pad
    for i, (txt, fs, tc, fw) in enumerate(lines):
        ly = cur_y - line_heights[i] / 2
        ax.text(x + w/2, ly, txt, ha='center', va='center',
                fontsize=fs, color=tc, fontweight=fw, linespacing=1.3)
        cur_y -= line_heights[i] + gap
    return box

def arrow(ax, x1, y1, x2, y2, color='#6B7280', lw=2.5, style='->'):
    """画箭头"""
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style,
                        color=color, lw=lw, mutation_scale=20)
    ax.add_patch(a)

def save(fig, name):
    path = os.path.join(OUT_DIR, name)
    fig.savefig(path, dpi=DPI, facecolor='white')
    plt.close(fig)
    print(f"  saved: {name}")

# ============ 图01: 五大系统疾病谱系总览 ============
def fig_01():
    fig, ax = new_fig(8.0, "内科学五大系统疾病谱系总览")  # 2400x1600
    systems = [
        ('消化系统', COLORS['digest'], [
            ('GERD / 胃炎', '屏障功能异常'),
            ('消化性溃疡', '侵袭-防御失衡'),
            ('肝硬化失代偿', '结构不可逆重构'),
            ('肝性脑病\n/ 大出血', '门脉分流+肝衰'),
            ('肝癌', '恶性克隆'),
        ]),
        ('泌尿系统', COLORS['renal'], [
            ('无症状\n尿检异常', '隐匿性'),
            ('急性/急进性肾炎', '免疫复合物攻击'),
            ('肾病综合征', '大量蛋白尿'),
            ('慢性肾衰竭', '肾单位持续丢失'),
        ]),
        ('内分泌代谢', COLORS['endo'], [
            ('糖调节受损\n/ 亚临床甲亢', '亚临床'),
            ('糖尿病 / 甲亢', '激素失衡显性化'),
            ('DKA / 甲状腺危象', '急性失代偿'),
            ('糖尿病肾病\n/ 视网膜病变', '慢性靶器官损伤'),
        ]),
        ('风湿免疫', COLORS['rheum'], [
            ('自身抗体阳性\n/ 未分化CTD', '免疫耐受破坏'),
            ('类风湿关节炎', '滑膜慢性炎症'),
            ('SLE多系统损伤', '免疫复合物脏器损伤'),
        ]),
        ('理化因素', COLORS['tox'], [
            ('急性中毒\n（轻-中度）', '暴露'),
            ('有机磷中毒\n（重度）', 'ChE<30%'),
            ('中间型综合征\n/ 迟发性神经病', '病程反跳与神经并发症'),
        ]),
    ]
    n = len(systems)
    col_w = 0.17
    gap = (1 - 0.04 - n * col_w) / (n - 1)
    x_start = 0.02
    title_y = 0.88
    node_h = 0.12
    node_gap = 0.045

    for i, (name, c, stages) in enumerate(systems):
        x = x_start + i * (col_w + gap)
        # 列标题
        rbox(ax, x, title_y, col_w, 0.07, c['main'], text=name,
             text_color='white', fontsize=FS['section'], radius=0.012)
        # 节点
        for j, (label, note) in enumerate(stages):
            ny = title_y - 0.095 - j * (node_h + node_gap)
            rbox(ax, x, ny, col_w, node_h, 'white', edge=c['main'], lw=2.5,
                 text=label, text_color=c['main'], fontsize=FS['node'])
            # 转折点标注
            if j < len(stages) - 1:
                ax.text(x + col_w/2, ny - node_gap/2, f"↓ {note}",
                        ha='center', va='center', fontsize=FS['note'], color='#6B7280')
            # 箭头
            if j < len(stages) - 1:
                arrow(ax, x + col_w/2, ny, x + col_w/2, ny - node_gap + 0.006,
                      color=c['main'], lw=2)
    save(fig, "01_五大系统疾病谱系总览.png")

# ============ 图02: A型B型胃炎对比 ============
def fig_02():
    fig, ax = new_fig(7.0, "A型（胃体）胃炎 vs B型（胃窦）胃炎")  # 2400x1400
    rows = [
        ('别称', '自身免疫性胃炎', '慢性多灶萎缩性胃炎'),
        ('部位', '胃体、胃底（弥漫）', '胃窦（多灶）'),
        ('病因', '自身抗体（壁细胞/内因子）', '幽门螺杆菌（Hp）感染为主'),
        ('胃酸', '显著降低（壁细胞破坏）', '正常或轻度降低'),
        ('血清胃泌素', '升高（G细胞代偿）', '正常或降低'),
        ('恶性贫血', '常有（内因子缺乏→B12缺乏）', '无'),
        ('癌变风险', '较低', '较高（肠化→异型增生）'),
        ('伴随疾病', '桥本甲状腺炎、Addison病', '消化性溃疡'),
    ]
    col_x = [0.04, 0.28, 0.62]
    col_w = [0.20, 0.30, 0.34]
    header_y = 0.87
    row_h = 0.082
    # 表头
    rbox(ax, col_x[0], header_y, col_w[0], 0.06, '#374151', text='对比维度', fontsize=FS['section'])
    rbox(ax, col_x[1], header_y, col_w[1], 0.06, COLORS['digest']['main'], text='A型胃炎', fontsize=FS['section'])
    rbox(ax, col_x[2], header_y, col_w[2], 0.06, COLORS['endo']['main'], text='B型胃炎', fontsize=FS['section'])
    for i, (dim, a, b) in enumerate(rows):
        y = header_y - 0.08 - i * row_h
        bg = '#F9FAFB' if i % 2 == 0 else 'white'
        rbox(ax, col_x[0], y, col_w[0], row_h - 0.008, bg, edge='#D1D5DB', lw=1,
             text=dim, text_color='#374151', fontsize=FS['node'], fontweight='bold')
        rbox(ax, col_x[1], y, col_w[1], row_h - 0.008, bg, edge='#D1D5DB', lw=1,
             text=a, text_color='#1F2937', fontsize=FS['sub'])
        rbox(ax, col_x[2], y, col_w[2], row_h - 0.008, bg, edge='#D1D5DB', lw=1,
             text=b, text_color='#1F2937', fontsize=FS['sub'])
    save(fig, "02_A型B型胃炎对比.png")

# ============ 图03: GU与DU腹痛节律对比 ============
def fig_03():
    fig, ax = new_fig(6.5, "胃溃疡(GU) vs 十二指肠溃疡(DU)：腹痛节律对比")  # 2400x1300
    # 时间轴
    timeline_y = 0.55
    times = ['早餐\n07:00', '上午\n10:00', '午餐\n12:00', '下午\n15:00', '晚餐\n18:00', '夜间\n22:00-02:00']
    n = len(times)
    tx_start = 0.08
    tx_gap = 0.84 / (n - 1)
    ax.plot([0.06, 0.94], [timeline_y, timeline_y], color='#9CA3AF', lw=3)
    for i, t in enumerate(times):
        x = tx_start + i * tx_gap
        ax.plot(x, timeline_y, 'o', color='#6B7280', markersize=10)
        ax.text(x, timeline_y - 0.06, t, ha='center', va='top', fontsize=FS['sub'], color='#374151')

    # GU: 餐后痛（进食→疼痛→缓解）
    gu_color = COLORS['digest']['main']
    gu_pain_x = [tx_start + 0*tx_gap + tx_gap*0.3, tx_start + 2*tx_gap + tx_gap*0.3, tx_start + 4*tx_gap + tx_gap*0.3]
    for px in gu_pain_x:
        ax.annotate('', xy=(px, timeline_y + 0.12), xytext=(px, timeline_y + 0.02),
                    arrowprops=dict(arrowstyle='->', color=gu_color, lw=3))
    text_auto(ax, 0.5, 0.82, 'GU（胃溃疡）：餐后半小时~1小时痛 → 进食加重，空腹缓解',
              ha='center', fontsize=FS['section'], color=gu_color, fontweight='bold')
    text_auto(ax, 0.5, 0.76, '机制：食物刺激胃酸分泌 → 胃酸接触溃疡面 → 疼痛；胃排空后缓解',
              ha='center', fontsize=FS['sub'], color='#6B7280')

    # DU: 空腹痛/夜间痛（疼痛→进食→缓解）
    du_color = COLORS['endo']['main']
    du_pain_x = [tx_start + 1*tx_gap, tx_start + 3*tx_gap, tx_start + 5*tx_gap]
    for px in du_pain_x:
        ax.annotate('', xy=(px, timeline_y - 0.12), xytext=(px, timeline_y - 0.02),
                    arrowprops=dict(arrowstyle='->', color=du_color, lw=3))
    text_auto(ax, 0.5, 0.30, 'DU（十二指肠溃疡）：空腹痛、夜间痛 → 进食缓解，餐后3~4h发作',
              ha='center', fontsize=FS['section'], color=du_color, fontweight='bold')
    text_auto(ax, 0.5, 0.24, '机制：空腹时胃酸进入十二指肠 → 刺激溃疡面 → 疼痛；进食中和胃酸后缓解',
              ha='center', fontsize=FS['sub'], color='#6B7280')

    # 底部对比要点
    text_auto(ax, 0.5, 0.10, '记忆口诀：GU"吃饱痛"，DU"饿了痛"；GU进食-疼痛-缓解，DU疼痛-进食-缓解',
              ha='center', fontsize=FS['node'], color='#1F2937', fontweight='bold',
              bbox=dict(boxstyle='round,pad=0.5', facecolor='#FEF3C7', edgecolor='#F59E0B', lw=2))
    save(fig, "03_GU与DU腹痛节律对比.png")

# ============ 图04: 胃癌Borrmann分型与转移 ============
def fig_04():
    fig, ax = new_fig(8.0, "胃癌：Borrmann分型与转移途径")  # 2400x1600
    # 上半：Borrmann分型
    types = [
        ('I型', '息肉型/隆起型', '边界清楚\n突向胃腔', '#10B981'),
        ('II型', '局限溃疡型', '溃疡边缘隆起\n边界清楚', '#3B82F6'),
        ('III型', '浸润溃疡型', '溃疡边缘不清\n向周围浸润', '#F59E0B'),
        ('IV型', '弥漫浸润型', '全胃壁浸润\n皮革胃', '#EF4444'),
    ]
    bx_start = 0.04
    bw = 0.215
    bgap = 0.02
    by = 0.56
    bh = 0.28
    ax.text(0.5, 0.90, 'Borrmann 分型（进展期胃癌）', ha='center', fontsize=FS['section'],
            color='#1F2937', fontweight='bold')
    for i, (t, name, desc, c) in enumerate(types):
        x = bx_start + i * (bw + bgap)
        multiline_box(ax, x, by, bw, bh, c, [
            (t, 28, 'white', 'bold'),
            (name, 19, 'white', 'bold'),
            (desc, 15, 'white', 'normal'),
        ], radius=0.03)

    # 下半：转移途径
    ax.text(0.5, 0.48, '转移途径', ha='center', fontsize=FS['section'],
            color='#1F2937', fontweight='bold')
    routes = [
        ('直接蔓延', '侵犯食管、结肠\n胰腺、大网膜', '#2563EB'),
        ('淋巴转移', '最常见\n左锁骨上淋巴结\n(Virchow)', '#7C3AED'),
        ('血行转移', '晚期经门脉→肝\n最常见，其次肺/骨', '#EA580C'),
        ('种植转移', '脱落至腹腔→卵巢\n(Krukenberg瘤)', '#DC2626'),
    ]
    ry = 0.10
    rh = 0.30
    for i, (name, desc, c) in enumerate(routes):
        x = bx_start + i * (bw + bgap)
        multiline_box(ax, x, ry, bw, rh, 'white', [
            (name, 22, c, 'bold'),
            (desc, 15, '#374151', 'normal'),
        ], edge=c, lw=3, radius=0.03)
    arrow(ax, 0.5, by, 0.5, ry + rh + 0.02, color='#9CA3AF', lw=2)
    save(fig, "04_胃癌Borrmann分型与转移.png")

# ============ 图05: 消化道出血鉴别与出血量 ============
def fig_05():
    fig, ax = new_fig(8.0, "消化道出血：部位鉴别与出血量估计")
    # 上半：上下消化道鉴别
    ax.text(0.5, 0.90, '部位鉴别', ha='center', fontsize=FS['section'], color='#1F2937', fontweight='bold')
    multiline_box(ax, 0.04, 0.56, 0.44, 0.28, COLORS['digest']['bg'], [
        ('上消化道出血', 22, COLORS['digest']['main'], 'bold'),
        ('呕血（咖啡渣样）', 16, '#374151', 'normal'),
        ('黑便（柏油样、发亮）', 16, '#374151', 'normal'),
        ('部位：Treitz韧带以上', 16, '#374151', 'normal'),
        ('常见：消化性溃疡、食管胃底静脉曲张', 14, '#6B7280', 'normal'),
        ('急性胃黏膜病变、胃癌', 14, '#6B7280', 'normal'),
    ], edge=COLORS['digest']['main'], lw=2.5)
    multiline_box(ax, 0.52, 0.56, 0.44, 0.28, COLORS['tox']['bg'], [
        ('下消化道出血', 22, COLORS['tox']['main'], 'bold'),
        ('便血（暗红/鲜红）', 16, '#374151', 'normal'),
        ('可伴黏液脓血', 16, '#374151', 'normal'),
        ('部位：Treitz韧带以下', 16, '#374151', 'normal'),
        ('常见：结直肠癌、息肉、炎症性肠病', 14, '#6B7280', 'normal'),
        ('憩室炎、血管畸形', 14, '#6B7280', 'normal'),
    ], edge=COLORS['tox']['main'], lw=2.5)

    # 下半：出血量估计
    ax.text(0.5, 0.48, '出血量估计（成人）', ha='center', fontsize=FS['section'], color='#1F2937', fontweight='bold')
    levels = [
        ('粪便隐血阳性', '>5~10 ml/日', '#10B981'),
        ('黑便', '>50~100 ml/日', '#3B82F6'),
        ('呕血', '胃内积血\n>250~300 ml', '#F59E0B'),
        ('周围循环衰竭', '>1000 ml\n（20%血容量）', '#EF4444'),
    ]
    bx = 0.04
    bw = 0.215
    bgap = 0.02
    for i, (name, vol, c) in enumerate(levels):
        x = bx + i * (bw + bgap)
        multiline_box(ax, x, 0.10, bw, 0.32, c, [
            (name, 19, 'white', 'bold'),
            (vol, 17, 'white', 'bold'),
        ], radius=0.03)
    save(fig, "05_消化道出血鉴别与出血量.png")

# ============ 图06: CKD分期与慢性肾衰竭并发症 ============
def fig_06():
    fig, ax = new_fig(8.5, "慢性肾衰竭：CKD分期与多系统并发症")
    # 左侧：CKD分期阶梯
    ax.text(0.20, 0.92, 'CKD分期（K/DOQI，按GFR）', ha='center', fontsize=FS['section'], color='#1F2937', fontweight='bold')
    stages = [
        ('1期', 'GFR ≥90', '正常或升高\nml/(min·1.73m²)', '#16A34A'),
        ('2期', 'GFR 60-89', '轻度降低\nml/(min·1.73m²)', '#84CC16'),
        ('3期', 'GFR 30-59', '中度降低 (3a:45-59\n/ 3b:30-44)', '#EA580C'),
        ('4期', 'GFR 15-29', '重度降低\nml/(min·1.73m²)', '#DC2626'),
        ('5期', 'GFR <15', '终末期ESRD\n需透析', '#7F1D1D'),
    ]
    sx = 0.04
    sw = 0.32
    sh = 0.13
    sgap = 0.02
    for i, (t, gfr, desc, c) in enumerate(stages):
        y = 0.76 - i * (sh + sgap)
        multiline_box(ax, sx, y, sw, sh, c, [
            (f'{t}  {gfr}', 19, 'white', 'bold'),
            (desc, 14, 'white', 'normal'),
        ], radius=0.02)

    # 右侧：三大功能并发症
    ax.text(0.70, 0.92, '肾脏三大功能"断电"→全身并发症', ha='center', fontsize=FS['section'], color='#1F2937', fontweight='bold')
    comps = [
        ('① 排泄功能↓', '尿毒症毒素蓄积（小分子尿素/中分子PTH/大分子β2微球蛋白）\n高钾血症 · 代谢性酸中毒 · 低钙 · 高磷', '#DBEAFE', '#2563EB'),
        ('② 调节功能↓', '水钠潴留 → 高血压 → 左心室肥厚 → 心力衰竭（最常见死因）\n尿毒症性心包炎（血性） · 动脉粥样硬化', '#FEF3C7', '#D97706'),
        ('③ 内分泌功能↓', 'EPO↓ → 肾性贫血（正细胞正色素性）\n骨化三醇↓ + PTH↑ → 肾性骨营养不良\n肾素-血管紧张素系统激活', '#FEE2E2', '#DC2626'),
    ]
    cy = 0.74
    ch = 0.185
    cgap = 0.02
    for i, (title, desc, bg, c) in enumerate(comps):
        y = cy - i * (ch + cgap)
        multiline_box(ax, 0.42, y, 0.54, ch, bg, [
            (title, 19, c, 'bold'),
            (desc, 14, '#374151', 'normal'),
        ], edge=c, lw=2, radius=0.02)

    # 底部：病因与治疗
    multiline_box(ax, 0.04, 0.03, 0.92, 0.12, '#EFF6FF', [
        ('我国最常见病因：慢性肾小球肾炎  |  发达国家：糖尿病肾病  |  最早表现：消化系统（食欲不振、恶心、口腔尿味）', 13, '#1E40AF', 'normal'),
        ('治疗：低蛋白饮食0.6-0.8g/kg·d（CKD3期起，50%高生物价蛋白）+ EPO补铁 + 降钾 + 肾脏替代治疗（血透/腹透/肾移植）', 13, '#1E40AF', 'normal'),
        ('诊断要点：GFR<60 持续≥3个月 = CKD', 15, '#DC2626', 'bold'),
    ], edge='#3B82F6', lw=2, radius=0.02)
    save(fig, "06_CKD分期与慢性肾衰竭并发症.png")

# ============ 图07: DKA与HHS鉴别 ============
def fig_07():
    fig, ax = new_fig(7.5, "DKA vs HHS 鉴别诊断")
    rows = [
        ('好发人群', 'T1DM青少年', 'T2DM老年（>50岁）'),
        ('血糖', '16.7~33.3 mmol/L', '>33.3 mmol/L（常>55）'),
        ('酮体', '强阳性（血酮>3）', '阴性或弱阳性'),
        ('酸中毒', '明显（pH<7.3，HCO3<15）', '无或轻度'),
        ('血浆渗透压', '正常或轻度升高', '显著升高（>320 mOsm/L）'),
        ('脱水程度', '中度', '重度（失水量>10%体重）'),
        ('意识障碍', '嗜睡→昏迷', '更常见、更重（弥漫性脑损伤）'),
        ('诱因', '感染、胰岛素中断', '感染、脱水、利尿剂/糖皮质激素'),
        ('治疗首要', '补液（生理盐水）+ 小剂量胰岛素', '补液（等渗/低渗）+ 小剂量胰岛素'),
    ]
    col_x = [0.04, 0.26, 0.56]
    col_w = [0.18, 0.27, 0.40]
    header_y = 0.88
    row_h = 0.075
    rbox(ax, col_x[0], header_y, col_w[0], 0.055, '#374151', text='对比维度', fontsize=FS['section'], radius=0.01)
    rbox(ax, col_x[1], header_y, col_w[1], 0.055, COLORS['endo']['main'], text='DKA', fontsize=FS['section'], radius=0.01)
    rbox(ax, col_x[2], header_y, col_w[2], 0.055, '#7C3AED', text='HHS', fontsize=FS['section'], radius=0.01)
    for i, (dim, a, b) in enumerate(rows):
        y = header_y - 0.075 - i * row_h
        bg = '#F9FAFB' if i % 2 == 0 else 'white'
        rbox(ax, col_x[0], y, col_w[0], row_h - 0.005, bg, edge='#D1D5DB', lw=1,
             text=dim, text_color='#374151', fontsize=16, fontweight='bold', radius=0.01)
        rbox(ax, col_x[1], y, col_w[1], row_h - 0.005, bg, edge='#D1D5DB', lw=1,
             text=a, text_color='#1F2937', fontsize=15, radius=0.01)
        rbox(ax, col_x[2], y, col_w[2], row_h - 0.005, bg, edge='#D1D5DB', lw=1,
             text=b, text_color='#1F2937', fontsize=15, radius=0.01)
    save(fig, "07_DKA与HHS鉴别.png")

# ============ 图08: 糖尿病诊断标准四切点 ============
def fig_08():
    fig, ax = new_fig(6.5, "糖尿病诊断标准：四个切点")
    criteria = [
        ('典型症状\n+ 随机血糖', '≥ 11.1\nmmol/L', '多饮、多尿、多食\n体重下降', '#DC2626'),
        ('空腹血糖\n(FPG)', '≥ 7.0\nmmol/L', '空腹指至少8h\n无热量摄入', '#EA580C'),
        ('OGTT 2h血糖', '≥ 11.1\nmmol/L', '75g无水葡萄糖负荷', '#2563EB'),
        ('HbA1c', '≥ 6.5%', '反映近2~3个月\n平均血糖', '#7C3AED'),
    ]
    bx = 0.04
    bw = 0.215
    bgap = 0.02
    by = 0.22
    bh = 0.52
    for i, (name, cutoff, note, c) in enumerate(criteria):
        x = bx + i * (bw + bgap)
        multiline_box(ax, x, by, bw, bh, c, [
            (name, 19, 'white', 'bold'),
            (cutoff, 24, 'white', 'bold'),
            (note, 14, 'white', 'normal'),
        ], radius=0.03)
    # 底部说明
    multiline_box(ax, 0.04, 0.06, 0.92, 0.10, '#FEF3C7', [
        ('满足任一即可诊断；无典型症状者，需改日复查确认（同一指标或不同指标均可）', 15, '#92400E', 'bold'),
        ('糖调节受损（糖尿病前期）：FPG 6.1~7.0（IFG）或 OGTT2h 7.8~11.1（IGT）', 14, '#92400E', 'normal'),
    ], edge='#F59E0B', lw=2, radius=0.02)
    save(fig, "08_糖尿病诊断标准四切点.png")

# ============ 图09: 急性中毒急救处理流程 ============
def fig_09():
    fig, ax = new_fig(9.0, "急性中毒急救处理流程")
    steps = [
        ('1. 立即终止\n接触毒物', '脱离中毒现场\n脱去污染衣物\n清洗皮肤毛发', '#3B82F6'),
        ('2. 清除体内\n尚未吸收毒物', '催吐（清醒合作者）\n洗胃（1h内效果好）\n导泻、灌肠\n活性炭吸附', '#8B5CF6'),
        ('3. 促进已吸收\n毒物排出', '利尿（补液+呋塞米）\n供氧（CO中毒首选）\n血液净化（透析/灌流）', '#10B981'),
        ('4. 特效解毒剂', '有机磷：阿托品+解磷定\n阿片类：纳洛酮\n苯二氮䓬：氟马西尼\n对乙酰氨基酚：NAC', '#F59E0B'),
        ('5. 对症支持\n治疗', '维持呼吸循环\n防治脑水肿、肺水肿\n纠正水电解质紊乱\n预防感染', '#EF4444'),
    ]
    n = len(steps)
    bw = 0.165
    bgap = (1 - 0.06 - n * bw) / (n - 1)
    bx = 0.03
    by = 0.25
    bh = 0.55
    for i, (title, desc, c) in enumerate(steps):
        x = bx + i * (bw + bgap)
        multiline_box(ax, x, by, bw, bh, c, [
            (title, 18, 'white', 'bold'),
            (desc, 13, 'white', 'normal'),
        ], radius=0.025)
        if i < n - 1:
            arrow(ax, x + bw + 0.002, by + bh/2, x + bw + bgap - 0.002, by + bh/2,
                  color='#6B7280', lw=3)
    # 顶部原则
    multiline_box(ax, 0.04, 0.84, 0.92, 0.08, '#EFF6FF', [
        ('总原则：立即终止接触 → 清除毒物 → 促进排出 → 特效解毒 → 对症支持', 19, '#1E40AF', 'bold'),
        ('关键：生命体征优先！呼吸心跳停止者立即CPR，保持气道通畅', 16, '#DC2626', 'bold'),
    ], edge='#3B82F6', lw=2, radius=0.02)
    # 底部注意
    ax.text(0.5, 0.12, '洗胃禁忌：吞服腐蚀性毒物（强酸/强碱）、石油蒸馏物、食管静脉曲张、昏迷无气道保护',
            ha='center', fontsize=15, color='#6B7280')
    save(fig, "09_急性中毒急救处理流程.png")

# ============ 图10: 肾病综合征病理分型对比 ============
def fig_10():
    fig, ax = new_fig(8.5, "肾病综合征常见病理分型对比")
    rows = [
        ('微小病变型肾病\n(MCD)', '儿童最常见(80%)', '光镜正常，电镜足突融合', '激素敏感，90%可缓解，易复发', '#10B981'),
        ('系膜增生性肾炎\n(MsPGN)', '我国常见，青少年', '系膜细胞/基质增生', '激素+免疫抑制剂，疗效不一', '#3B82F6'),
        ('膜性肾病(MN)', '中老年最常见', 'GBM弥漫增厚，钉突形成', '激素+CTX/CNI，易血栓，自发缓解1/3', '#F59E0B'),
        ('局灶节段性肾小球硬化\n(FSGS)', '青少年，肥胖/反流相关', '局灶节段硬化+玻璃样变', '激素+CNI，疗效差，进展快', '#8B5CF6'),
        ('系膜毛细血管性肾炎\n(MPGN)', '青少年，低补体血症', '双轨征，系膜插入GBM', '激素+免疫抑制剂，疗效差', '#EF4444'),
    ]
    col_x = [0.03, 0.27, 0.47, 0.66]
    col_w = [0.22, 0.18, 0.17, 0.31]
    header_y = 0.84
    row_h = 0.125
    headers = ['病理类型', '好发人群', '病理特征', '治疗与预后']
    for i, h in enumerate(headers):
        rbox(ax, col_x[i], header_y, col_w[i], 0.07, '#374151', text=h,
             text_color='white', fontsize=FS['section'], radius=0.01)
    for i, (pt, age, patho, treat, c) in enumerate(rows):
        y = header_y - 0.13 - i * row_h
        bg = '#F9FAFB' if i % 2 == 0 else 'white'
        rbox(ax, col_x[0], y, col_w[0], row_h - 0.008, bg, edge=c, lw=2.5,
             text=pt, text_color=c, fontsize=FS['node'], fontweight='bold', radius=0.01)
        rbox(ax, col_x[1], y, col_w[1], row_h - 0.008, bg, edge='#D1D5DB', lw=1,
             text=age, text_color='#1F2937', fontsize=FS['sub'], radius=0.01)
        rbox(ax, col_x[2], y, col_w[2], row_h - 0.008, bg, edge='#D1D5DB', lw=1,
             text=patho, text_color='#1F2937', fontsize=FS['sub'], radius=0.01)
        rbox(ax, col_x[3], y, col_w[3], row_h - 0.008, bg, edge='#D1D5DB', lw=1,
             text=treat, text_color='#1F2937', fontsize=FS['sub'], radius=0.01)
    save(fig, "10_肾病综合征病理分型对比.png")

# ============ 图15: GERD反流机制与Barrett腺癌序列 ============
def fig_15():
    fig, ax = new_fig(6.5, "GERD：反流机制与Barrett食管→腺癌序列")
    # 机制部分
    ax.text(0.5, 0.88, '反流机制', ha='center', fontsize=FS['section'], color='#1F2937', fontweight='bold')
    mechs = [
        ('LES压力降低', '一过性LES松弛\n最主要机制', '#3B82F6'),
        ('食管清除能力↓', '蠕动减弱\n唾液分泌减少', '#8B5CF6'),
        ('胃排空延迟', '胃内压升高\n促进反流', '#F59E0B'),
        ('食管黏膜防御↓', '上皮屏障受损\n敏感化', '#EF4444'),
    ]
    bx = 0.04
    bw = 0.215
    bgap = 0.02
    for i, (title, desc, c) in enumerate(mechs):
        x = bx + i * (bw + bgap)
        multiline_box(ax, x, 0.58, bw, 0.22, c, [
            (title, 18, 'white', 'bold'),
            (desc, 14, 'white', 'normal'),
        ], radius=0.025)

    # 疾病进展序列
    ax.text(0.5, 0.48, '疾病进展序列', ha='center', fontsize=FS['section'], color='#1F2937', fontweight='bold')
    sequence = [
        ('正常食管\n鳞状上皮', '#10B981'),
        ('GERD\n反流性食管炎', '#3B82F6'),
        ('Barrett食管\n肠上皮化生', '#F59E0B'),
        ('异型增生\n（低级别→高级别）', '#EA580C'),
        ('食管腺癌', '#DC2626'),
    ]
    n = len(sequence)
    sw = 0.165
    sgap = (1 - 0.06 - n * sw) / (n - 1)
    for i, (label, c) in enumerate(sequence):
        x = 0.03 + i * (sw + sgap)
        rbox(ax, x, 0.20, sw, 0.18, c, text=label, text_color='white', fontsize=16, radius=0.025)
        if i < n - 1:
            arrow(ax, x + sw + 0.002, 0.29, x + sw + sgap - 0.002, 0.29, color='#6B7280', lw=3)
    # 底部
    multiline_box(ax, 0.04, 0.05, 0.92, 0.10, '#FEF3C7', [
        ('关键：Barrett食管是食管腺癌的癌前病变，需定期内镜随访', 17, '#92400E', 'bold'),
        ('PPI（质子泵抑制剂）是GERD治疗首选；Barrett伴异型增生需内镜下治疗或手术', 15, '#92400E', 'normal'),
    ], edge='#F59E0B', lw=2, radius=0.02)
    save(fig, "15_GERD反流机制与Barrett腺癌序列.png")

# ============ 图16: UC与CD对比 ============
def fig_16():
    fig, ax = new_fig(8.0, "溃疡性结肠炎(UC) vs 克罗恩病(CD)")
    rows = [
        ('病变分布', '连续性，从直肠逆行向上', '节段性（跳跃性），全消化道均可'),
        ('病变深度', '黏膜层、黏膜下层（浅）', '全层性（透壁性）'),
        ('典型部位', '直肠、乙状结肠（远端结肠）', '回肠末端、回盲部（右下腹）'),
        ('内镜表现', '弥漫充血水肿、颗粒状、糜烂溃疡', '纵行溃疡、鹅卵石样、裂隙样'),
        ('病理特征', '隐窝脓肿、杯状细胞减少', '非干酪样肉芽肿（特征性）'),
        ('腹痛特点', '左下腹痛，便后缓解', '右下腹痛，进食加重'),
        ('腹泻', '黏液脓血便（多见）', '糊状或水样，脓血少'),
        ('并发症', '中毒性巨结肠、癌变', '瘘管、脓肿、狭窄、肛周病变'),
        ('肠外表现', '关节炎、虹膜炎、结节性红斑', '同左，更常见胆结石、肾结石'),
        ('治疗首选', '5-ASA（美沙拉嗪）', '糖皮质激素 + 免疫抑制剂/生物制剂'),
    ]
    col_x = [0.04, 0.26, 0.56]
    col_w = [0.18, 0.27, 0.40]
    header_y = 0.90
    row_h = 0.072
    rbox(ax, col_x[0], header_y, col_w[0], 0.05, '#374151', text='对比维度', fontsize=FS['section'])
    rbox(ax, col_x[1], header_y, col_w[1], 0.05, COLORS['digest']['main'], text='UC', fontsize=FS['section'])
    rbox(ax, col_x[2], header_y, col_w[2], 0.05, COLORS['rheum']['main'], text='CD', fontsize=FS['section'])
    for i, (dim, a, b) in enumerate(rows):
        y = header_y - 0.07 - i * row_h
        bg = '#F9FAFB' if i % 2 == 0 else 'white'
        rbox(ax, col_x[0], y, col_w[0], row_h - 0.005, bg, edge='#D1D5DB', lw=1,
             text=dim, text_color='#374151', fontsize=16, fontweight='bold')
        rbox(ax, col_x[1], y, col_w[1], row_h - 0.005, bg, edge='#D1D5DB', lw=1,
             text=a, text_color='#1F2937', fontsize=15)
        rbox(ax, col_x[2], y, col_w[2], row_h - 0.005, bg, edge='#D1D5DB', lw=1,
             text=b, text_color='#1F2937', fontsize=15)
    save(fig, "16_UC与CD对比.png")

# ============ 图17: 肾病综合征病理生理链 ============
def fig_17():
    fig, ax = new_fig(6.5, "肾病综合征病理生理链")
    chain = [
        ('肾小球滤过膜损伤', '电荷屏障+机械\n屏障破坏', '#3B82F6'),
        ('大量蛋白尿', '>3.5g/d\n（最核心机制）', '#8B5CF6'),
        ('低白蛋白血症', '<30g/L\n（肝脏合成不足代偿）', '#F59E0B'),
        ('水肿', '低蛋白→血浆胶渗压↓\n→水钠潴留', '#EA580C'),
        ('高脂血症', '肝脏代偿合成\n脂蛋白↑', '#DC2626'),
    ]
    n = len(chain)
    bw = 0.175
    bgap = (1 - 0.06 - n * bw) / (n - 1)
    bx = 0.03
    by = 0.35
    bh = 0.35
    for i, (title, desc, c) in enumerate(chain):
        x = bx + i * (bw + bgap)
        multiline_box(ax, x, by, bw, bh, c, [
            (title, 17, 'white', 'bold'),
            (desc, 12, 'white', 'normal'),
        ], radius=0.025)
        if i < n - 1:
            arrow(ax, x + bw + 0.002, by + bh/2, x + bw + bgap - 0.002, by + bh/2,
                  color='#6B7280', lw=3)
    # 并发症
    ax.text(0.5, 0.25, '常见并发症', ha='center', fontsize=FS['section'], color='#1F2937', fontweight='bold')
    comps = ['感染（最常见死因）', '血栓栓塞（肾静脉血栓）', '急性肾损伤', '蛋白质及脂代谢紊乱']
    cw = 0.215
    cgap = 0.02
    for i, c in enumerate(comps):
        x = 0.04 + i * (cw + cgap)
        rbox(ax, x, 0.08, cw, 0.12, '#FEF3C7', edge='#F59E0B', lw=2,
             text=c, text_color='#92400E', fontsize=15, radius=0.02)
    save(fig, "17_肾病综合征病理生理链.png")

# ============ 图18: 甲亢下丘脑垂体甲状腺轴 ============
def fig_18():
    fig, ax = new_fig(7.0, "甲状腺功能亢进症：下丘脑-垂体-甲状腺轴")
    # 下丘脑
    multiline_box(ax, 0.35, 0.78, 0.30, 0.12, '#7C3AED', [
        ('下丘脑', 22, 'white', 'bold'),
        ('分泌 TRH（促甲状腺激素释放激素）', 15, 'white', 'normal'),
    ], radius=0.025)
    arrow(ax, 0.50, 0.78, 0.50, 0.70, color='#7C3AED', lw=3)
    ax.text(0.52, 0.74, 'TRH (+)', fontsize=16, color='#7C3AED', fontweight='bold')

    # 垂体
    multiline_box(ax, 0.35, 0.55, 0.30, 0.12, '#3B82F6', [
        ('腺垂体', 22, 'white', 'bold'),
        ('分泌 TSH（促甲状腺激素）', 15, 'white', 'normal'),
    ], radius=0.025)
    arrow(ax, 0.50, 0.55, 0.50, 0.47, color='#3B82F6', lw=3)
    ax.text(0.52, 0.51, 'TSH (+)', fontsize=16, color='#3B82F6', fontweight='bold')

    # 甲状腺
    multiline_box(ax, 0.35, 0.32, 0.30, 0.12, '#EA580C', [
        ('甲状腺', 22, 'white', 'bold'),
        ('分泌 T3、T4（甲状腺激素）', 15, 'white', 'normal'),
    ], radius=0.025)

    # 负反馈
    arrow(ax, 0.35, 0.38, 0.12, 0.38, color='#DC2626', lw=2.5, style='->')
    ax.text(0.20, 0.40, 'T3/T4 负反馈(-)', fontsize=15, color='#DC2626', fontweight='bold', ha='center')
    arrow(ax, 0.12, 0.38, 0.12, 0.61, color='#DC2626', lw=2.5)
    arrow(ax, 0.12, 0.61, 0.35, 0.61, color='#DC2626', lw=2.5)
    arrow(ax, 0.12, 0.61, 0.12, 0.84, color='#DC2626', lw=2.5)
    arrow(ax, 0.12, 0.84, 0.35, 0.84, color='#DC2626', lw=2.5)

    # 甲亢时的变化
    multiline_box(ax, 0.04, 0.08, 0.42, 0.18, '#FEE2E2', [
        ('Graves病（最常见）', 20, '#DC2626', 'bold'),
        ('TRAb（TSH受体抗体）模拟TSH作用', 15, '#374151', 'normal'),
        ('→ T3/T4 升高，TSH 降低（负反馈）', 15, '#374151', 'normal'),
        ('TRAb是Graves病的特异性指标', 14, '#6B7280', 'normal'),
    ], edge='#DC2626', lw=2.5, radius=0.025)

    # 临床表现
    multiline_box(ax, 0.54, 0.08, 0.42, 0.18, '#DBEAFE', [
        ('甲亢典型表现', 20, '#2563EB', 'bold'),
        ('高代谢：怕热多汗、多食易饥、体重↓', 15, '#374151', 'normal'),
        ('交感兴奋：心悸、手抖、易怒、失眠', 15, '#374151', 'normal'),
        ('体征：甲状腺肿大、突眼、胫前黏液水肿', 14, '#6B7280', 'normal'),
    ], edge='#2563EB', lw=2.5, radius=0.025)
    save(fig, "18_甲亢下丘脑垂体甲状腺轴.png")

# ============ 图19: 糖尿病分型与并发症总览 ============
def fig_19():
    fig, ax = new_fig(8.5, "糖尿病分型与并发症总览")
    # 上半：分型对比
    multiline_box(ax, 0.04, 0.62, 0.44, 0.26, COLORS['digest']['bg'], [
        ('1型糖尿病（T1DM）', 22, COLORS['digest']['main'], 'bold'),
        ('β细胞免疫破坏 → 胰岛素绝对缺乏', 16, '#374151', 'normal'),
        ('青少年起病、急、多消瘦', 16, '#374151', 'normal'),
        ('易DKA、依赖胰岛素', 16, '#374151', 'normal'),
        ('胰岛自身抗体(GADA/ICA)阳性、C肽低下', 14, '#6B7280', 'normal'),
    ], edge=COLORS['digest']['main'], lw=2.5)
    multiline_box(ax, 0.52, 0.62, 0.44, 0.26, COLORS['renal']['bg'], [
        ('2型糖尿病（T2DM）', 22, COLORS['renal']['main'], 'bold'),
        ('胰岛素抵抗 + β细胞功能缺陷 → 相对不足', 16, '#374151', 'normal'),
        ('40岁后起病、隐匿、多肥胖', 16, '#374151', 'normal'),
        ('不易酮症（>50岁易HHS）', 16, '#374151', 'normal'),
        ('占90-95%、可口服药、C肽峰值延迟', 14, '#6B7280', 'normal'),
    ], edge=COLORS['renal']['main'], lw=2.5)

    # 中间：急性并发症
    ax.text(0.25, 0.55, '急性并发症', ha='center', fontsize=20, color='#DC2626', fontweight='bold')
    acute = ['DKA\n(T1DM多见)', 'HHS\n(老年T2DM)', '感染\n(肾盂肾炎/皮肤)', '低血糖\n(药物过量)']
    for i, a in enumerate(acute):
        x = 0.04 + i * 0.115
        rbox(ax, x, 0.40, 0.105, 0.12, '#FEE2E2', edge='#DC2626', lw=2,
             text=a, text_color='#991B1B', fontsize=14, radius=0.02)

    # 慢性并发症
    ax.text(0.72, 0.55, '慢性并发症', ha='center', fontsize=20, color='#7C3AED', fontweight='bold')
    chronic = [
        ('微血管', '糖尿病肾病DKD\n视网膜病变', '#7C3AED'),
        ('大血管', '冠心病\n脑卒中（主要死因）', '#2563EB'),
        ('神经病变', '周围神经（袜套样）\n自主神经', '#16A34A'),
        ('糖尿病足', '神经+血管\n非创伤截肢首因', '#EA580C'),
    ]
    for i, (title, desc, c) in enumerate(chronic):
        x = 0.52 + i * 0.115
        multiline_box(ax, x, 0.40, 0.105, 0.12, 'white', [
            (title, 14, c, 'bold'),
            (desc, 12, '#374151', 'normal'),
        ], edge=c, lw=2, radius=0.02)

    # 底部：诊断与治疗
    multiline_box(ax, 0.04, 0.06, 0.92, 0.26, '#EFF6FF', [
        ('诊断标准（四选一）：典型症状+随机血糖≥11.1 | FPG≥7.0 | OGTT2h≥11.1 | HbA1c≥6.5%', 17, '#1E40AF', 'bold'),
        ('治疗基石（"五驾马车"）：糖尿病教育、医学营养治疗、运动治疗、血糖监测、药物治疗', 16, '#1E40AF', 'normal'),
        ('T2DM一线用药：二甲双胍（eGFR<30禁用）；T1DM必须胰岛素治疗', 16, '#1E40AF', 'normal'),
        ('控制目标：HbA1c<7%（个体化），血压<130/80，LDL-C<2.6（合并ASCVD<1.8）', 15, '#6B7280', 'normal'),
    ], edge='#3B82F6', lw=2, radius=0.02)
    save(fig, "19_糖尿病分型与并发症总览.png")

# ============ 图20: SLE自身抗体与多系统损伤 ============
def fig_20():
    fig, ax = new_fig(8.5, "系统性红斑狼疮：自身抗体与多系统损伤")
    # 左侧：自身抗体
    ax.text(0.20, 0.92, '关键自身抗体', ha='center', fontsize=FS['section'], color='#1F2937', fontweight='bold')
    antibodies = [
        ('ANA', '筛选试验，敏感性95%\n特异性低，滴度与活动度无关', '#3B82F6'),
        ('抗dsDNA', '标记性抗体，特异性95%\n滴度与活动度相关，累及肾脏', '#8B5CF6'),
        ('抗Sm', '标记性抗体，特异性99%\n敏感性低，与活动度无关', '#F59E0B'),
        ('抗磷脂抗体', '抗心磷脂/狼疮抗凝物\n→ 血栓、血小板减少、流产', '#EF4444'),
    ]
    for i, (name, desc, c) in enumerate(antibodies):
        y = 0.78 - i * 0.17
        multiline_box(ax, 0.04, y, 0.32, 0.14, c, [
            (name, 20, 'white', 'bold'),
            (desc, 14, 'white', 'normal'),
        ], radius=0.02)

    # 右侧：多系统损伤
    ax.text(0.70, 0.92, '多系统损伤', ha='center', fontsize=FS['section'], color='#1F2937', fontweight='bold')
    systems = [
        ('皮肤黏膜', '蝶形红斑、盘状红斑、口腔溃疡、光过敏、脱发', '#EC4899'),
        ('关节肌肉', '对称性多关节痛（非侵蚀性）、肌痛、肌炎', '#8B5CF6'),
        ('肾脏（狼疮肾）', '蛋白尿、血尿、管型尿→肾病综合征→肾衰竭（主要死因之一）', '#3B82F6'),
        ('心血管', '心包炎（最常见）、疣状心内膜炎(Libman-Sack)、冠脉炎', '#EF4444'),
        ('呼吸系统', '胸膜炎、间质性肺炎、肺泡出血', '#10B981'),
        ('神经系统', '神经精神狼疮（癫痫、精神病、脑血管病）', '#F59E0B'),
        ('血液系统', '溶血性贫血、白细胞减少、血小板减少', '#7C3AED'),
    ]
    for i, (name, desc, c) in enumerate(systems):
        y = 0.82 - i * 0.105
        multiline_box(ax, 0.42, y, 0.54, 0.085, 'white', [
            (f'{name}：{desc}', 13, '#1F2937', 'normal'),
        ], edge=c, lw=2, radius=0.015)

    # 底部：治疗
    multiline_box(ax, 0.04, 0.03, 0.92, 0.10, '#F5F3FF', [
        ('治疗：糖皮质激素（基础用药）+ 免疫抑制剂（环磷酰胺/吗替麦考酚酯，狼疮肾炎诱导缓解）', 14, '#5B21B6', 'bold'),
        ('抗疟药（羟氯喹）为背景治疗，可减少复发和器官损伤', 14, '#5B21B6', 'normal'),
    ], edge='#7C3AED', lw=2, radius=0.02)
    save(fig, "20_SLE自身抗体与多系统损伤.png")

# ============ 图21: 有机磷中毒分级与时间线 ============
def fig_21():
    fig, ax = new_fig(7.5, "有机磷中毒：分级与时间线")
    # 分级
    ax.text(0.5, 0.92, '中毒分级（按ChE活性+临床表现）', ha='center', fontsize=FS['section'], color='#1F2937', fontweight='bold')
    grades = [
        ('轻度中毒', 'ChE 50~70%', 'M样症状为主\n（毒蕈碱样）', '#10B981'),
        ('中度中毒', 'ChE 30~50%', 'M样 + N样症状\n（烟碱样：肌颤）', '#F59E0B'),
        ('重度中毒', 'ChE <30%', 'M + N + 中枢症状\n昏迷、肺水肿、呼衰', '#DC2626'),
    ]
    for i, (name, che, symp, c) in enumerate(grades):
        x = 0.04 + i * 0.31
        multiline_box(ax, x, 0.58, 0.29, 0.26, c, [
            (name, 22, 'white', 'bold'),
            (che, 20, 'white', 'bold'),
            (symp, 15, 'white', 'normal'),
        ], radius=0.025)

    # 时间线
    ax.text(0.5, 0.48, '病程时间线', ha='center', fontsize=FS['section'], color='#1F2937', fontweight='bold')
    timeline = [
        ('急性胆碱能危象', '接触后数分钟~数小时\nM+N+中枢症状', '#3B82F6'),
        ('中间型综合征', '中毒后1~4天\n屈颈肌/呼吸肌麻痹\n（ChE长期受抑制）', '#F59E0B'),
        ('迟发性神经病', '中毒后2~4周\n感觉运动型多发性神经病\n（轴索变性）', '#8B5CF6'),
    ]
    for i, (name, desc, c) in enumerate(timeline):
        x = 0.04 + i * 0.31
        multiline_box(ax, x, 0.14, 0.29, 0.28, 'white', [
            (name, 19, c, 'bold'),
            (desc, 14, '#374151', 'normal'),
        ], edge=c, lw=2.5, radius=0.025)
        if i < 2:
            arrow(ax, x + 0.29 + 0.005, 0.28, x + 0.31 - 0.005, 0.28, color='#9CA3AF', lw=2.5)

    # 治疗
    multiline_box(ax, 0.04, 0.04, 0.92, 0.07, '#FEE2E2', [
        ('特效解毒：阿托品（对抗M样，早期足量维持"阿托品化"）+ 氯解磷定/碘解磷定（ChE复能剂，对抗N样，越早越好）', 16, '#991B1B', 'bold'),
    ], edge='#DC2626', lw=2, radius=0.02)
    save(fig, "21_有机磷中毒分级与时间线.png")

if __name__ == '__main__':
    os.makedirs(OUT_DIR, exist_ok=True)
    print("Generating diagrams v3...")
    fig_01()
    fig_02()
    fig_03()
    fig_04()
    fig_05()
    fig_06()
    fig_07()
    fig_08()
    fig_09()
    fig_10()
    fig_15()
    fig_16()
    fig_17()
    fig_18()
    fig_19()
    fig_20()
    fig_21()
    print("All 17 text diagrams done.")
