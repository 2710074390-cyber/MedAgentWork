# AI医学插图生态调研与工程集成方案

> MedAgentWork v5.2 | 2026-09-07
> 调研范围：中文社区教程、国内工具生态、标注叠加工程、render_review.py扩展、批量生产、Cloudflare Pages优化

---

## 一、中文社区AI医学插图高质量教程

### 1.1 教程清单（按推荐度排序）

| # | 标题 | 平台 | URL | 核心方法 |
|---|------|------|-----|----------|
| 1 | Qwen-Image-2512-SDNQ在医疗科普中的应用：人体器官示意图+病理变化对比图 | CSDN | https://blog.csdn.net/weixin_42514540/article/details/156960562 | 用Qwen-Image生成标准解剖结构+病理对比图；提示词模板："人体胃的解剖结构示意图，正面观，标注贲门、胃底、胃体、幽门…黑白线条图，无背景，医学教科书风格，高清线稿"；负向提示词排除艺术风格和不准确结构 |
| 2 | 造相Z-Image模型在医疗可视化中的应用：解剖图谱自动生成 | CSDN | https://blog.csdn.net/weixin_35916518/article/details/159100000 | 精确解剖细节约束法：在提示词中逐条列出结构位置关系（如"前交叉韧带应从股骨外侧髁后方延伸至胫骨髁间隆起前方，呈紧绷状态，用红色标示"）；用颜色编码区分结构；干净浅灰背景 |
| 3 | AI画科研插图，别瞎写提示词！ | 丁香园 | https://3g.dxy.cn/bbs/topic/53646264 | 七大核心要素法：①绘图主题（明确研究对象）②图类型（机制图/流程图/通路图）③视觉层级（主/次/背景）④配色方案⑤标注规范⑥比例尺/方向⑦输出格式；强调通用模型缺乏专业知识库，模糊指令易产生科学错误 |
| 4 | 教材插图与医学信息图怎么做：把复杂科学概念讲给非专业读者的AI工作流 | 掘金 | https://juejin.cn/post/7635480534215442484 | 风格统一法：将"配色/线条粗细/标签字号/留白比例"写成固定style prompt，每张图都拼在前面；医学传播配色原则：蓝色/青绿色/暖灰色为安全色，红色仅用于最关键警示；面向临床医生用详细版，面向患者用简化版 |
| 5 | 人体解剖图怎么画？全身、器官与系统的标注画法 | 掘金 | https://juejin.cn/post/7651793209824542772 | 三步法：①定范围和视角（器官/系统+前面观/侧面观/剖面）②列出需要的标签（逐个写，不碰运气）③选风格（线稿/彩色/3D渲染）；强调"人体全身骨骼前面观"和"单个心脏剖面"是完全不同的需求 |
| 6 | 医疗影像新范式：用Stable Diffusion生成高精度医学图像的完整指南 | CSDN | https://blog.csdn.net/gitblog_00294/article/details/152588704 | SD医学图像生成全流程：按影像模态加关键词（MRI加"magnetic resonance imaging, soft tissue contrast"；超声加"ultrasound, Doppler effect"）；器官解剖教学图命令行示例；推荐负向提示词排除模糊和伪影 |
| 7 | GPT-Image-2做科研绘图，提示词怎么写？ | 腾讯云 | https://cloud.tencent.com/developer/article/2665990 | 科研绘图vs普通AI绘图的本质区别：不是追求好看，而是把科学逻辑、机制路径和视觉层级表达清楚；提示词需解决：图类型、核心机制、视觉层级、标注位置、配色、输出规格 |
| 8 | 用AI解放双手：3分钟打造专业级医学解剖插画 | CSDN | https://blog.csdn.net/JetFalcon67/article/details/153892737 | 系统交互四步：①输入解剖部位名称+详细程度（基础/进阶/专业级）②文生图生成符合解剖学标准的线稿③风格转换（水彩/矢量/素描）④标注叠加；适合批量生产工作流参考 |

### 1.2 教程提炼的通用提示词模板

综合以上教程，医学插图提示词应包含以下结构化要素：

```
[主体+视角]：人体[器官/系统]，[前面观/侧面观/冠状切面/矢状切面/横切面]
[核心结构清单]：显示[结构1]、[结构2]、[结构3]…，[结构1]用[颜色]标示
[解剖关系约束]：[结构A]位于[结构B]的[方位]，呈[紧绷/松弛/扩张]状态
[风格]：医学教科书风格 / 黑白线条图 / 干净白色背景 / 无多余器官
[质量]：高清线稿 / 锐利对焦 / 8K分辨率
[负向]：艺术风格, 卡通效果, 不准确的结构, 模糊, 文字, 水印
```

**关键共识**：所有高质量教程都强调——**不要让AI生成文字标注**。AI生成的中文标注错误率高（传统模型37%，即使Qwen-Image也有8.2%错误率），正确做法是生成无标注原图，再用程序叠加标注。

---

## 二、国内AI绘图工具医学能力深度评估

### 2.1 综合对比表

| 工具 | 厂商 | 医学写实能力 | 中文文字渲染 | API | 价格(元/张) | 免费额度 | 推荐场景 |
|------|------|-------------|-------------|-----|-------------|---------|---------|
| **通义万相 (Qwen-Image-3.0)** | 阿里 | ★★★★☆ | ★★★★★ SOTA | 有 | 0.18起 | 500张/模型 | **医学插图首选**，中文标注可直接生成 |
| **即梦AI (Seedream 5.0)** | 字节/火山 | ★★★★☆ | ★★★★☆ | 有 | 0.22~0.259 | 登录送积分≈10次 | 写实风格强，智能画布支持局部编辑 |
| **可灵AI (Kling v3)** | 快手 | ★★★★★ | ★★★☆☆ | 有 | 0.2~0.4 | 有限 | 影视级写实，人像/场景质感最佳 |
| **文心一格 (ERNIE iRAG)** | 百度 | ★★★☆☆ | ★★★★☆ | 有 | 0.12~0.14 | 每日10~15张 | 中文prompt理解96%，国风强，医学一般 |
| **LiblibAI (SD生态)** | 社区 | ★★★★☆ (选对模型) | ★★☆☆☆ | 有 | 免费/按量 | 在线WebUI免费 | 可控性最强，需自行筛选医学模型 |
| **美图设计室** | 美图 | ★★☆☆☆ | ★★★☆☆ | 有(企业) | 0.9~1.65 | 有限 | 电商定位，不适合医学插图 |

### 2.2 各工具详细评估

#### 2.2.1 通义万相 / Qwen-Image-3.0 — **综合首选**

- **医学能力**：Qwen-Image系列在医疗科普场景有大量验证案例。能精准绘制已知解剖结构（心脏四腔、肾单位、脑干核团、脊髓节段），表现典型病理改变（脂肪变性、玻璃样变、淀粉样变、肿瘤形态），生成教学级示意图（黑白线稿、标注图、对比图、流程图）["https://blog.csdn.net/weixin_42514540/article/details/156960562"]
- **中文文字渲染**：**当前国内SOTA**。ChineseWord测试集中文一级字准确率97.29%（GPT Image 1为68.37%，Seedream 3.0为53.48%）；LongText-Bench中英文长文本渲染第1名；支持12种语言原生渲染，10px小字清晰可辨["https://blog.csdn.net/lifetragedy/article/details/149932802","https://qwen.ai/blog?id=qwen-image-3.0&utm_source=Securitylab.ru"]
- **API**：阿里云百炼平台，`wanx-v1` 0.16元/张，`wanx2.1-t2i-turbo` 0.14元/张，`qwen-image-2.0-pro` 约0.12元/张，Qwen-Image-3.0-Pro/Standard 0.18元/张起；每模型500张免费额度；任务下发接口QPS限制2，同时处理中任务数1["https://help.aliyun.com/zh/model-studio/text-to-image-api-reference","https://view.inews.qq.com/a/20260805A05EAD00"]
- **结论**：如果希望AI直接生成带中文标注的图，Qwen-Image-3.0是唯一可靠选择。但即使97%准确率，医学术语标注仍建议程序叠加以确保100%准确。

#### 2.2.2 即梦AI (Seedream) — **写实风格+局部编辑**

- **医学能力**：Seedream 5.0 Preview主打"联网检索+逻辑推理+精准编辑"，支持图表文字清晰渲染及像素级局部修改；4.6模型聚焦人像质量。中文语义理解出色，日常风景、国风创意、日常配图都能轻松驾驭["https://post.m.smzdm.com/p/a3mn3mw7/","https://www.iesdouyin.com/share/video/7641921070594129649"]
- **中文文字渲染**：Seedream 5.0支持图表文字清晰渲染，但未达到Qwen-Image的SOTA水平
- **API**：火山引擎即梦AI图像生成，定价约0.22元/张（部分渠道0.259元/张）；限流500 IPM（每分钟最多500张）；支持ComfyUI节点集成["https://www.volcengine.com/docs/85621/1544714?lang=zh","https://github.com/Yunwuxin-666/Comfyui-Jimeng-api"]
- **特色**：智能画布支持图生图、局部重绘、消除笔，适合对生成图进行迭代修改；Agent记忆功能支持连续分镜、系列图风格统一
- **结论**：适合生成高质量无标注原图，再用程序叠加标注。智能画布的局部编辑能力对修正解剖错误很有价值。

#### 2.2.3 可灵AI (Kling) — **影视级写实**

- **医学能力**：深耕影视级画面质感，在写实人像、剧情分镜、氛围感场景创作上表现突出；人物神态自然统一，画面光影层次高级["https://www.iesdouyin.com/share/video/7641921070594129649"]
- **中文文字渲染**：v2.0支持近300种图片比例，多图参考生图（主体参考、背景参考、风格参考），但文字渲染非其强项
- **API**：官方API图像生成1K/2K均0.2元/次（部分模型0.4元/次）；kling-v3-image-generation已上架阿里云百炼；支持最多10张参考图锁定主体、元素和色调["https://app.klingai.com/cn/dev/document-api/apiReference/updateNotice","https://help.aliyun.com/zh/model-studio/kling-v3-image-generation"]
- **结论**：如果需要照片级写实的医学场景图（如手术场景、临床表现），可灵是最佳选择。纯解剖结构示意图并非其最优场景。

#### 2.2.4 文心一格 (ERNIE) — **中文理解+低成本**

- **医学能力**：基于ERNIE-ViLG 2.0，擅长国风、写实风格；中文prompt理解准确率96%，但医学专业结构的准确性一般["https://blog.csdn.net/xinlinliu/article/details/152725023"]
- **中文文字渲染**：中文提示词理解精准，但图内文字渲染能力中等
- **API**：百度AI开放平台，ERNIE iRAG 0.14元/张（prompt长度不超过220字符）；B端标准接口单价约0.12元/次；个人认证免费10张，企业认证20张["https://blog.csdn.net/IQAiqa/article/details/148748536","https://www.docin.com/touch_new/preview_new.do?id=4994792928"]
- **结论**：适合低成本批量试错和非关键插图。医学专业图不建议作为主力。

#### 2.2.5 LiblibAI (Stable Diffusion生态) — **最高可控性**

- **医学能力**：社区有10w+模型，可筛选医学/解剖专用Checkpoint和LoRA；SD 3.5有医疗应用案例（解剖图生成系统部署）["https://wenku.csdn.net/answer/x6eg1gsiho2","https://pc.liblib.art/"]
- **中文文字渲染**：SD原生架构缺乏文本专项优化，需额外插件才能实现基础文本渲染，中文渲染准确率低（约76.3%），**不适合直接生成标注**["https://blog.csdn.net/gitblog_00856/article/details/152096373"]
- **API**：提供官方JavaScript/TypeScript SDK（npm `liblibai`）；在线WebUI免费使用；客户端支持WebUI+ComfyUI双启动器一键安装["https://www.npmjs.com/package/liblibai","https://www.liblib.art/teaching/38fa8df3ccac414d92af002b7ccb32a4"]
- **结论**：如果团队有SD经验且需要极致可控性（特定医学风格LoRA微调），LiblibAI是最佳选择。学习曲线较陡，不适合快速起步。

#### 2.2.6 美图设计室 — **不推荐**

- 定位电商设计AI工作流（电商商品Agent、服饰穿戴Agent、海报Agent），医学插图非其目标场景
- 美豆制计费：单张0.9~1.65元（美豆单价0.06~0.11元），远高于其他工具；API千次150~300元["https://www.designkit.cn/help/125","https://prompt.cn/sites/10491.html"]
- 场景生成能力有限，仅支持5种固定比例，娱乐化定位明显

### 2.3 工具选型建议

**主力方案**：通义万相 Qwen-Image-3.0（生成无标注原图，中文理解最准，API最便宜）
**备选方案**：即梦AI Seedream 5.0（写实风格更强，智能画布支持局部修正）
**标注方案**：**所有工具都不直接生成中文标注**，统一用Python Pillow程序叠加（详见第三章）
**批量生产**：通义万相API（0.14元/张turbo版，500张免费额度/模型）

---

## 三、标注叠加工程方案（Pillow实现）

### 3.1 设计原则

1. **原图无标注**：AI只生成干净的解剖结构图，所有文字、编号、引导线由程序叠加
2. **数据驱动**：标注信息存储在JSON/YAML中，与图片文件分离，修改标注不需要重新生成图
3. **分辨率无关**：标注坐标使用相对比例（0~1），适配不同分辨率输出
4. **自动避让**：标注框自动检测重叠，调整位置避免遮挡关键结构

### 3.2 标注数据结构设计

```yaml
# annotations/heart_coronary.yaml
image: images_raw/heart_coronary.png
output: images/heart_coronary_annotated.png
style:
  font: "Microsoft YaHei"      # 或 "SimHei", "Source Han Sans SC"
  font_size: 28
  number_circle_radius: 18
  line_width: 2
  text_color: "#1a1a2e"
  number_bg: "#dc2626"          # 编号圆圈背景（核心结构用红色）
  number_fg: "#ffffff"
  line_color: "#4a5568"
  box_bg: "#ffffff"              # 文字背景框
  box_padding: 8
  box_radius: 6
legend:
  position: "bottom-right"       # top-left / top-right / bottom-left / bottom-right
  title: "图例"
  items:
    - { color: "#dc2626", label: "动脉" }
    - { color: "#2563eb", label: "静脉" }
    - { color: "#059669", label: "神经" }
annotations:
  - id: 1
    point: [0.35, 0.42]         # 标注点相对坐标 (x, y)，0~1
    label: "左冠状动脉"
    label_pos: [0.05, 0.35]     # 文字框位置（可选，不填则自动计算）
    side: "left"                 # 引导线方向 left/right/top/bottom/auto
  - id: 2
    point: [0.62, 0.38]
    label: "右冠状动脉"
    side: "right"
  - id: 3
    point: [0.48, 0.55]
    label: "前降支"
    side: "bottom"
  - id: 4
    point: [0.40, 0.70]
    label: "心尖"
    side: "bottom"
```

### 3.3 核心实现代码

```python
#!/usr/bin/env python3
"""
MedAgentWork — 医学图标注叠加工具
用法: python annotate_image.py annotations/heart_coronary.yaml
依赖: pip install pillow pyyaml
"""

import yaml
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


class MedicalImageAnnotator:
    """在无标注医学原图上叠加编号圆圈、引导线、中文标注和图例"""

    # Windows 系统中文字体路径
    FONT_CANDIDATES = [
        "C:/Windows/Fonts/msyh.ttc",       # 微软雅黑
        "C:/Windows/Fonts/msyhbd.ttc",     # 微软雅黑粗体
        "C:/Windows/Fonts/simhei.ttf",     # 黑体
        "C:/Windows/Fonts/simsun.ttc",     # 宋体
        "/System/Library/Fonts/PingFang.ttc",  # macOS
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",  # Linux
    ]

    def __init__(self, config: dict):
        self.config = config
        self.style = config.get("style", {})
        self.font_path = self._find_font()
        self.font_size = self.style.get("font_size", 28)
        self.font = ImageFont.truetype(self.font_path, self.font_size)
        self.small_font = ImageFont.truetype(self.font_path, int(self.font_size * 0.75))

    def _find_font(self) -> str:
        """查找可用的中文字体"""
        for path in self.FONT_CANDIDATES:
            if Path(path).exists():
                return path
        raise FileNotFoundError("未找到中文字体，请安装微软雅黑或思源黑体")

    def _hex_to_rgb(self, hex_color: str, alpha: int = 255) -> tuple:
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (alpha,)

    def _to_abs(self, rel_point: tuple[float, float], img_size: tuple[int, int]) -> tuple[int, int]:
        """相对坐标(0~1)转绝对像素坐标"""
        w, h = img_size
        return int(rel_point[0] * w), int(rel_point[1] * h)

    def _draw_number_circle(self, draw: ImageDraw.Draw, pos: tuple[int, int],
                             number: int, radius: int, bg_color: str, fg_color: str):
        """绘制编号圆圈"""
        bg = self._hex_to_rgb(bg_color)
        fg = self._hex_to_rgb(fg_color)
        x, y = pos
        # 圆圈背景
        draw.ellipse([x - radius, y - radius, x + radius, y + radius],
                     fill=bg, outline=fg, width=2)
        # 编号文字
        text = str(number)
        bbox = draw.textbbox((0, 0), text, font=self.small_font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((x - tw // 2, y - th // 2 - bbox[1]), text,
                  font=self.small_font, fill=fg)

    def _draw_leader_line(self, draw: ImageDraw.Draw,
                           point: tuple[int, int], label_pos: tuple[int, int],
                           color: str, width: int):
        """绘制引导线（带折线的标注线）"""
        line_color = self._hex_to_rgb(color)
        px, py = point
        lx, ly = label_pos

        # 计算折线拐点：先水平/垂直走一段，再连到标注点
        if abs(px - lx) > abs(py - ly):
            # 水平为主：先水平到标注点x附近，再垂直
            mid_x = lx + (20 if px > lx else -20)
            draw.line([(lx, ly), (mid_x, ly)], fill=line_color, width=width)
            draw.line([(mid_x, ly), (mid_x, py)], fill=line_color, width=width)
            draw.line([(mid_x, py), (px, py)], fill=line_color, width=width)
        else:
            # 垂直为主
            mid_y = ly + (20 if py > ly else -20)
            draw.line([(lx, ly), (lx, mid_y)], fill=line_color, width=width)
            draw.line([(lx, mid_y), (px, mid_y)], fill=line_color, width=width)
            draw.line([(px, mid_y), (px, py)], fill=line_color, width=width)

        # 标注点处小圆点
        dot_r = 4
        draw.ellipse([px - dot_r, py - dot_r, px + dot_r, py + dot_r],
                     fill=line_color)

    def _draw_label_box(self, draw: ImageDraw.Draw, text: str,
                        pos: tuple[int, int], bg_color: str, text_color: str,
                        padding: int = 8, radius: int = 6) -> tuple[int, int, int, int]:
        """绘制带圆角背景的文字标注框，返回框的bbox"""
        x, y = pos
        bbox = draw.textbbox((0, 0), text, font=self.font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

        box_x0 = x - padding
        box_y0 = y - padding
        box_x1 = x + tw + padding
        box_y1 = y + th + padding

        # 圆角矩形背景
        draw.rounded_rectangle([box_x0, box_y0, box_x1, box_y1],
                               radius=radius, fill=self._hex_to_rgb(bg_color, 230),
                               outline=self._hex_to_rgb("#e2e8f0"))
        # 文字
        draw.text((x - bbox[0], y - bbox[1]), text, font=self.font,
                  fill=self._hex_to_rgb(text_color))

        return (box_x0, box_y0, box_x1, box_y1)

    def _auto_label_position(self, point: tuple[int, int], side: str,
                              img_size: tuple[int, int],
                              text: str) -> tuple[int, int]:
        """根据side参数自动计算标注框位置"""
        w, h = img_size
        px, py = point
        bbox = self.font.getbbox(text)
        tw = bbox[2] - bbox[0]
        margin = 60  # 标注框离标注点的距离

        if side == "left":
            return (max(10, px - tw - margin - 40), py - 14)
        elif side == "right":
            return (min(w - tw - 40, px + margin), py - 14)
        elif side == "top":
            return (px - tw // 2, max(10, py - margin - 30))
        elif side == "bottom":
            return (px - tw // 2, min(h - 50, py + margin))
        else:  # auto：选择离图像边缘更远的一侧
            if px < w * 0.4:
                return (min(w - tw - 40, px + margin), py - 14)
            else:
                return (max(10, px - tw - margin - 40), py - 14)

    def _draw_legend(self, draw: ImageDraw.Draw, img_size: tuple[int, int]):
        """绘制图例"""
        legend = self.config.get("legend")
        if not legend:
            return

        items = legend.get("items", [])
        if not items:
            return

        w, h = img_size
        position = legend.get("position", "bottom-right")
        title = legend.get("title", "图例")

        # 计算图例尺寸
        item_height = self.font_size + 10
        title_height = self.font_size + 8
        legend_w = 160
        legend_h = title_height + item_height * len(items) + 16
        padding = 20

        # 根据位置计算坐标
        if "top" in position:
            ly = padding
        else:
            ly = h - legend_h - padding
        if "left" in position:
            lx = padding
        else:
            lx = w - legend_w - padding

        # 背景
        draw.rounded_rectangle([lx, ly, lx + legend_w, ly + legend_h],
                               radius=8, fill=self._hex_to_rgb("#ffffff", 235),
                               outline=self._hex_to_rgb("#e2e8f0"))
        # 标题
        draw.text((lx + 12, ly + 8), title, font=self.small_font,
                  fill=self._hex_to_rgb("#4a5568"))

        # 图例项
        for i, item in enumerate(items):
            iy = ly + title_height + i * item_height + 4
            color = self._hex_to_rgb(item["color"])
            # 颜色方块
            draw.rectangle([lx + 14, iy + 4, lx + 30, iy + 20], fill=color)
            # 标签
            draw.text((lx + 38, iy), item["label"], font=self.small_font,
                      fill=self._hex_to_rgb("#1a1a2e"))

    def annotate(self, input_path: str, output_path: str):
        """执行标注叠加"""
        img = Image.open(input_path).convert("RGBA")
        w, h = img.size

        # 创建标注层（独立图层，方便后续调整）
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        annotations = self.config.get("annotations", [])
        radius = self.style.get("number_circle_radius", 18)
        line_width = self.style.get("line_width", 2)
        line_color = self.style.get("line_color", "#4a5568")
        number_bg = self.style.get("number_bg", "#dc2626")
        number_fg = self.style.get("number_fg", "#ffffff")
        box_bg = self.style.get("box_bg", "#ffffff")
        text_color = self.style.get("text_color", "#1a1a2e")

        for ann in annotations:
            # 标注点（绝对坐标）
            point = self._to_abs(tuple(ann["point"]), (w, h))

            # 标注文字位置
            label = ann["label"]
            if "label_pos" in ann:
                label_pos = self._to_abs(tuple(ann["label_pos"]), (w, h))
            else:
                side = ann.get("side", "auto")
                label_pos = self._auto_label_position(point, side, (w, h), label)

            # 1. 引导线
            self._draw_leader_line(draw, point, label_pos, line_color, line_width)

            # 2. 编号圆圈（在标注点处）
            self._draw_number_circle(draw, point, ann["id"], radius,
                                      number_bg, number_fg)

            # 3. 文字标注框
            self._draw_label_box(draw, label, label_pos, box_bg, text_color)

        # 4. 图例
        self._draw_legend(draw, (w, h))

        # 合并图层
        result = Image.alpha_composite(img, overlay)
        result = result.convert("RGB")
        result.save(output_path, "PNG", optimize=True)
        print(f"✅ 标注完成: {output_path} ({w}x{h})")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="医学图标注叠加工具")
    parser.add_argument("config", help="标注配置YAML文件路径")
    parser.add_argument("--input", help="覆盖配置中的输入图片路径")
    parser.add_argument("--output", help="覆盖配置中的输出路径")
    args = parser.parse_args()

    with open(args.config, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if args.input:
        config["image"] = args.input
    if args.output:
        config["output"] = args.output

    annotator = MedicalImageAnnotator(config)
    annotator.annotate(config["image"], config["output"])


if __name__ == "__main__":
    main()
```

### 3.4 字体选择建议

| 字体 | 适用场景 | Windows路径 | 特点 |
|------|---------|------------|------|
| 微软雅黑 (Microsoft YaHei) | **默认推荐** | `C:/Windows/Fonts/msyh.ttc` | 屏幕显示清晰，医学术语渲染好，系统自带 |
| 黑体 (SimHei) | 标题/编号 | `C:/Windows/Fonts/simhei.ttf` | 笔画粗，适合编号圆圈内的数字 |
| 思源黑体 (Source Han Sans SC) | 开源/跨平台 | 需下载 | 开源免费，字重丰富，适合商业发布 |
| 宋体 (SimSun) | 传统教材风格 | `C:/Windows/Fonts/simsun.ttc` | 教科书风格，但屏幕显示不如雅黑清晰 |

**关键**：Pillow默认字体不支持中文，必须显式加载`.ttf`/`.ttc`文件。Windows环境下微软雅黑是最稳妥的选择。

### 3.5 布局策略：避免遮挡

1. **side参数**：每个标注指定`left/right/top/bottom/auto`，将文字框放在结构外侧
2. **自动避让**：`auto`模式下，标注点在图像左半部分则文字放右侧，反之亦然
3. **编号+文字分离**：编号圆圈放在解剖结构上（小面积遮挡），文字框放在空白区域，通过引导线连接
4. **图例固定角落**：图例放在`bottom-right`，不遮挡中心结构
5. **标注框半透明背景**：`box_bg`使用230 alpha，即使轻微重叠也能看清底图

---

## 四、render_review.py 图片支持扩展方案

### 4.1 问题定位

当前`render_review.py`中，图片语法`![alt](path)`的处理流程：

1. `convert_block()`逐行解析，图片行不匹配任何特殊块（heading/list/table/code/blockquote等）
2. 落入最后的**普通段落**分支：`return f'<p>...{self.parse_inline(line)}</p>'`
3. `parse_inline()`中的链接正则 `r'\[([^\]]+)\]\(([^)]+)\)'` 会把`![alt](path)`中的`[alt](path)`部分匹配成`<a>`标签
4. 结果：图片变成了一段带链接的文字，`!`被保留为普通字符，图片不显示

**根因**：`parse_inline()`中链接正则没有排除`!`前缀，且`convert_block()`没有图片块的检测分支。

### 4.2 修改方案

需要修改两处：

#### 修改1：`parse_inline()` — 在链接正则之前先处理图片

在`parse_inline()`方法中，在链接处理之前添加图片语法处理：

```python
def parse_inline(self, text: str) -> str:
    """解析行内 Markdown 标记"""
    # === 新增：图片语法 !必须在链接之前处理 ===
    text = re.sub(
        r'!\[([^\]]*)\]\(([^)]+)\)',
        self._replace_image,
        text
    )

    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # ... 其余不变
```

#### 修改2：新增`_replace_image()`回调方法

```python
def _replace_image(self, match: re.Match) -> str:
    """将 ![alt](path) 替换为 <figure><img> 结构
    
    支持：
    - 外部引用（默认）：<img src="path">
    - base64内联（--embed-images模式）：<img src="data:image/png;base64,...">
    - 自动WebP转换（如果存在.webp版本）
    """
    alt = match.group(1)
    src = match.group(2)

    # 解析图片编号（从alt中提取"图N：标题"格式）
    fig_num = ""
    fig_caption = alt
    m_fig = re.match(r'图(\d+)[：:]\s*(.+)', alt)
    if m_fig:
        fig_num = m_fig.group(1)
        fig_caption = m_fig.group(2)

    # 处理图片路径（相对于MD文件所在目录）
    img_path = self.md_path.parent / src
    img_src = src  # 默认外部引用

    # base64内联模式
    if self.embed_images and img_path.exists():
        img_data = img_path.read_bytes()
        import base64
        b64 = base64.b64encode(img_data).decode('ascii')
        ext = img_path.suffix.lower().lstrip('.')
        mime_map = {'png': 'image/png', 'jpg': 'image/jpeg',
                     'jpeg': 'image/jpeg', 'webp': 'image/webp',
                     'gif': 'image/gif', 'avif': 'image/avif'}
        mime = mime_map.get(ext, 'image/png')
        img_src = f'data:{mime};base64,{b64}'

    # 构建 figure 结构
    caption_html = ""
    if fig_caption:
        caption_class = "fig-caption"
        num_html = f'<span class="fig-number">图{fig_num}</span> ' if fig_num else ""
        caption_html = f'<figcaption class="{caption_class}">{num_html}{html_module.escape(fig_caption)}</figcaption>'

    return (f'<figure class="med-figure">'
            f'<img src="{img_src}" alt="{html_module.escape(alt)}" '
            f'loading="lazy" decoding="async">'
            f'{caption_html}'
            f'</figure>')
```

#### 修改3：`convert_block()` — 独立图片行作为块级元素

当图片单独占一行时（前后有空行），应作为块级`<figure>`处理，而不是包裹在`<p>`中。在`convert_block()`的普通段落分支之前添加：

```python
# === 新增：块级图片（单独一行的 ![...](...)）===
image_block_match = re.match(r'^\s*!\[([^\]]*)\]\(([^)]+)\)\s*$', line)
if image_block_match:
    return self.parse_inline(line), i + 1
```

这段代码要放在`convert_block()`中，在"Paragraph (non-empty, non-special)"分支之前、所有其他块检测之后。

#### 修改4：`__init__()` — 添加embed_images参数

```python
def __init__(self, md_path: Path, embed_images: bool = False):
    self.md_path = md_path
    self.embed_images = embed_images
    # ... 其余不变
```

#### 修改5：CSS — 添加图片样式

在`CSS`变量中添加：

```css
/* ===== 医学插图 ===== */
.med-figure {
  margin: 24px 0;
  text-align: center;
  break-inside: avoid;  /* 打印时不跨页 */
}
.med-figure img {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border);
}
.fig-caption {
  margin-top: 10px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}
.fig-number {
  font-weight: 700;
  color: var(--accent);
}

/* 打印优化 */
@media print {
  .med-figure {
    margin: 12px 0;
  }
  .med-figure img {
    max-width: 90%;
    box-shadow: none;
  }
}
```

#### 修改6：`main()` — 添加命令行参数

```python
parser.add_argument('--embed-images', action='store_true',
                    help='将图片base64内联到HTML中（生成完全自包含文件）')
# ...
renderer = ReviewRenderer(input_path, embed_images=args.embed_images)
```

### 4.3 base64内联 vs 外部引用权衡

| 维度 | base64内联 | 外部引用 |
|------|-----------|---------|
| **自包含性** | ✅ 单个HTML文件包含一切 | ❌ 需要图片文件同目录 |
| **HTML体积** | 24.4MB图片 → base64后约**32.5MB**（膨胀33%） | HTML仅几KB |
| **加载速度** | 首次加载慢（32MB HTML解析），但无额外请求 | 懒加载，首屏快 |
| **PDF打印** | ✅ 离线可用，打印不依赖网络 | 浏览器打印时需图片已缓存 |
| **Cloudflare Pages** | ❌ 单文件25MiB限制，32.5MB超限 | ✅ 图片单独部署，单张<25MiB |
| **修改图片** | ❌ 需重新渲染整个HTML | ✅ 替换图片文件即可 |
| **缓存友好** | ❌ HTML变更即全部失效 | ✅ 图片可独立CDN缓存 |

**体积计算**：
- 当前27张图共24.4MB
- base64编码膨胀率 = 4/3 ≈ 33.3%
- base64后总体积 ≈ 24.4 × 1.333 ≈ **32.5MB**
- 加上HTML本身（CSS+JS+文本约200KB），最终HTML约**32.7MB**
- **超过Cloudflare Pages单文件25MiB限制**，无法直接部署

**结论**：
- **本地分发/离线PDF打印**：使用`--embed-images`生成自包含HTML
- **Cloudflare Pages上线**：使用外部引用，图片单独放在`images/`目录部署
- **推荐默认**：外部引用 + 图片压缩（详见4.4），打印时浏览器已缓存图片

### 4.4 图片压缩/格式转换方案

#### 压缩策略

```python
# 批量压缩脚本思路（使用Pillow）
from PIL import Image
import os

def optimize_image(input_path, output_path, max_width=1600, quality=82):
    """
    医学插图优化：
    1. 限制最大宽度1600px（复习资料内容区720px，2x屏够用）
    2. PNG → WebP（有损quality=82，肉眼无损）
    3. 保留原图备份
    """
    img = Image.open(input_path)

    # 分辨率优化
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # 转换为WebP
    if img.mode in ('RGBA', 'LA', 'P'):
        img = img.convert('RGB')

    img.save(output_path, 'WebP', quality=quality, method=6)
```

#### 预期体积 reduction

基于公开基准数据（腾讯云图片压缩测试、AVIF vs WebP对比评测）：

| 格式 | 质量参数 | 27张图预期总体积 | 相对PNG reduction | 备注 |
|------|---------|-----------------|-------------------|------|
| PNG (原图) | - | 24.4 MB | 0% | 当前状态，3.5MB/张 |
| PNG (缩至1600px) | optimize | ~12 MB | ~51% | 分辨率优化是最大收益来源 |
| WebP (q=82) | 1600px | **~3.5 MB** | **~86%** | 推荐，浏览器兼容性好 |
| WebP (q=75) | 1600px | ~2.5 MB | ~90% | 更激进，线稿图可接受 |
| AVIF (q=60) | 1600px | ~2.2 MB | ~91% | 体积最小，但编码慢，Safari 16+才支持 |

**关键发现**：
- 分辨率从AI生成的2K/4K缩至1600px是**最大单项收益**（约50% reduction），因为复习资料内容区仅720px宽
- WebP q=82在医学线稿/插图上肉眼几乎无损，体积减少约86%
- 27张图从24.4MB降至**~3.5MB**，平均130KB/张，完全适合Web部署
- AVIF比WebP再小约20-30%，但编码速度慢5-10倍，且旧浏览器不支持，建议作为`<picture>`的可选格式

#### 推荐输出结构

```
images/
├── raw/                    # AI生成的原图（PNG，备份，不部署）
│   ├── heart_coronary.png
│   └── ...
├── webp/                   # 压缩后的WebP（部署用）
│   ├── heart_coronary.webp
│   └── ...
└── avif/                   # 可选：AVIF版本（现代浏览器用）
    ├── heart_coronary.avif
    └── ...
```

MD中引用路径使用`images/webp/heart_coronary.webp`。

### 4.5 打印PDF时的图片DPI和清晰度保障

1. **源图分辨率**：压缩后的WebP保持1600px宽，在A4纸（210mm宽，打印区域约180mm）上相当于 **225 DPI**（1600px / 7.09in = 225dpi），满足打印质量要求（印刷标准300dpi，屏幕打印150dpi即可）
2. **浏览器打印设置**：Chrome打印时选择"更多设置 → 背景图形 ✓"、"缩放 默认"、"纸张大小 A4"
3. **CSS打印优化**：`.med-figure { break-inside: avoid; }` 确保图片不被跨页截断；`img { max-width: 90%; }` 留出页边距
4. **图片格式**：打印时浏览器会自动解码WebP，无需特殊处理；如果遇到旧版浏览器打印WebP有问题，可在打印时临时切换PNG版本

---

## 五、批量生产工程化

### 5.1 从知识点列表批量生成提示词

```python
#!/usr/bin/env python3
"""
MedAgentWork — 医学插图批量提示词生成器
从知识点YAML列表生成结构化提示词，供通义万相API批量调用
"""

import yaml
import json
from pathlib import Path

# 医学插图风格模板（固定前缀，保证系列图风格统一）
STYLE_PROMPT = (
    "医学教科书风格插图，干净白色背景，无文字无标注无水印， "
    "高清线稿与淡彩结合，专业医学插画，解剖结构准确， "
    "锐利对焦，细节清晰，8K分辨率"
)

NEGATIVE_PROMPT = (
    "文字, 标注, 数字, 水印, logo, 艺术风格, 卡通, 漫画, "
    "模糊, 低质量, 变形, 不准确的解剖结构, 多余器官, 照片, 真人"
)

# 视角映射
VIEW_MAP = {
    "前面观": "anterior view, frontal view",
    "后面观": "posterior view",
    "侧面观": "lateral view",
    "冠状切面": "coronal section, frontal plane",
    "矢状切面": "sagittal section",
    "横切面": "transverse section, cross-section",
    "剖面": "cross-section, cutaway view",
}


def build_prompt(knowledge: dict) -> dict:
    """从单个知识点构建完整的提示词"""
    subject = knowledge["subject"]           # 如 "心脏"
    view = knowledge.get("view", "前面观")   # 如 "冠状切面"
    structures = knowledge.get("structures", [])  # 如 ["左心房", "左心室", "二尖瓣"]
    pathology = knowledge.get("pathology", "")    # 如 "心肌梗死"
    emphasis = knowledge.get("emphasis", "")      # 如 "冠状动脉狭窄处用红色标示"

    # 构建结构清单
    struct_str = "、".join(structures) if structures else ""

    # 主体描述
    parts = [f"人体{subject}"]
    parts.append(VIEW_MAP.get(view, view))
    if struct_str:
        parts.append(f"清晰显示{struct_str}")
    if pathology:
        parts.append(f"显示{pathology}的病理变化")
    if emphasis:
        parts.append(emphasis)

    main_prompt = "，".join(parts)
    full_prompt = f"{main_prompt}，{STYLE_PROMPT}"

    return {
        "id": knowledge["id"],
        "filename": knowledge["filename"],
        "prompt": full_prompt,
        "negative_prompt": NEGATIVE_PROMPT,
        "size": knowledge.get("size", "1440*1024"),  # 通义万相支持的尺寸
        "n": 1,
    }


def batch_generate_prompts(knowledge_file: str, output_file: str):
    """从知识点列表批量生成提示词JSON"""
    with open(knowledge_file, "r", encoding="utf-8") as f:
        knowledge_list = yaml.safe_load(f)

    prompts = [build_prompt(k) for k in knowledge_list]

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(prompts, f, ensure_ascii=False, indent=2)

    print(f"✅ 已生成 {len(prompts)} 条提示词 → {output_file}")
    return prompts


if __name__ == "__main__":
    batch_generate_prompts("knowledge_points.yaml", "prompts_batch.json")
```

知识点列表示例（`knowledge_points.yaml`）：

```yaml
- id: 1
  subject: "心脏冠状动脉"
  view: "前面观"
  structures: ["左冠状动脉", "右冠状动脉", "前降支", "回旋支"]
  pathology: ""
  emphasis: "动脉用红色标示"
  filename: "heart_coronary"

- id: 2
  subject: "心脏传导系统"
  view: "前面观"
  structures: ["窦房结", "房室结", "希氏束", "左右束支", "浦肯野纤维"]
  pathology: ""
  emphasis: "传导通路用黄色高亮"
  filename: "heart_conduction"

- id: 3
  subject: "肾小球"
  view: "横切面"
  structures: ["毛细血管丛", "肾小囊", "脏层上皮细胞", "壁层上皮细胞"]
  pathology: "糖尿病肾病：肾小球基底膜增厚"
  emphasis: "增厚的基底膜用蓝色标示"
  filename: "kidney_glomerulus_diabetic"
```

### 5.2 图片命名规范与目录结构

```
MedAgentWork/
├── 知识库素材/
│   ├── render_review.py          # 已有
│   ├── annotate_image.py         # 新增：标注叠加工具
│   ├── batch_prompts.py          # 新增：批量提示词生成
│   ├── optimize_images.py        # 新增：批量压缩转换
│   └── call_tongyi_api.py        # 新增：通义万相API批量调用
├── 复习资料/
│   ├── 内科学_主复习资料.md       # MD中引用 images/webp/xxx.webp
│   └── ...
├── images/
│   ├── raw/                       # AI生成原图（PNG，不部署）
│   │   ├── heart_coronary_raw.png
│   │   └── ...
│   ├── annotated/                 # 标注后图片（PNG，中间产物）
│   │   ├── heart_coronary.png
│   │   └── ...
│   ├── webp/                      # 压缩WebP（部署用，MD引用此目录）
│   │   ├── heart_coronary.webp
│   │   └── ...
│   └── avif/                      # 可选AVIF（现代浏览器）
│       ├── heart_coronary.avif
│       └── ...
├── annotations/                   # 标注配置YAML（与图片一一对应）
│   ├── heart_coronary.yaml
│   └── ...
└── prompts/
    ├── knowledge_points.yaml      # 知识点列表
    └── prompts_batch.json         # 生成的批量提示词
```

**命名规范**：
- 格式：`{器官/系统}_{主题}_{病理/状态}.{ext}`
- 全小写，下划线分隔，不使用中文文件名（避免URL编码问题）
- 示例：`heart_coronary.webp`、`kidney_glomerulus_diabetic.webp`、`lung_tb_cavity.webp`
- MD中引用：`![图1：心脏冠状动脉前面观](images/webp/heart_coronary.webp)`

### 5.3 版本管理和更新策略

1. **原图不可变**：`images/raw/`中的AI生成图一旦确认合格，不再修改。需要更新时生成新图，文件名加版本号`_v2`
2. **标注可迭代**：`annotations/*.yaml`可以随时修改坐标和文字，重新运行标注工具即可更新`images/annotated/`和`images/webp/`
3. **MD引用稳定**：MD中始终引用`images/webp/{name}.webp`，底层图片更新不影响MD
4. **Git管理**：
   - `annotations/`和`prompts/`纳入Git（文本文件，可diff）
   - `images/raw/`和`images/annotated/`建议用Git LFS或单独管理（大文件）
   - `images/webp/`可以从raw重新生成，不纳入Git（在CI中构建）
5. **更新流程**：修改标注YAML → 运行`annotate_image.py` → 运行`optimize_images.py` → 重新渲染HTML → 部署

### 5.4 与5-Agent管线的集成点

现有管线：MedMaster → MedGen → MedQC → MedFix → MedReview

| Agent | 集成点 | 具体操作 |
|-------|--------|---------|
| **MedMaster** (知识大纲) | 在大纲中标注"需要插图"的知识点 | 每个模块输出时，标记需要配图的知识点（如"心脏解剖需要冠状切面图"），生成`knowledge_points.yaml`的雏形 |
| **MedGen** (内容生成) | 生成MD时插入图片占位符 | 在MD对应位置插入`![图N：标题](images/webp/{filename}.webp)`，同时在`prompts/knowledge_points.yaml`中追加该图的知识点描述 |
| **MedQC** (质量检查) | 检查图片引用完整性 | 新增检查项：①MD中引用的图片文件是否存在 ②图片alt文本是否符合"图N：标题"格式 ③标注YAML是否与图片一一对应 ④图片体积是否超标（单张>500KB警告） |
| **MedFix** (修正) | 修正图片相关问题 | 修复缺失的图片引用、修正标注YAML中的坐标错误、重新生成不合格的AI图 |
| **MedReview** (渲染) | 渲染含图HTML | 调用已扩展的`render_review.py`（支持图片语法），可选`--embed-images`生成自包含HTML用于PDF打印 |

**新增独立步骤（建议在MedGen和MedQC之间）**：
- **MedIllustrator**（插图Agent）：读取`knowledge_points.yaml` → 调用通义万相API批量生成原图 → 人工审核/修正 → 生成标注YAML初稿 → 运行标注叠加 → 压缩转换为WebP

---

## 六、Cloudflare Pages 图片优化

### 6.1 Pages限制

| 限制项 | Free Plan | Pro Plan |
|--------|-----------|----------|
| 站点文件数 | 20,000 | 20,000 |
| 单文件大小 | **25 MiB** | 25 MiB |
| 构建时长 | 500次/月 | 5,000次/月 |
| 带宽 | 无限 | 无限 |
| 构建输出大小 | 建议<20MB | 建议<20MB |

["https://developers.cloudflare.com/pages/platform/limits/"]

**关键约束**：
- 单文件25MiB：当前24.4MB的PNG图片单张3.5MB不超限，但base64内联的HTML 32.7MB会超限
- 20,000文件：27张图+标注YAML+HTML远低于限制
- 大文件（>25MiB）需用R2存储

### 6.2 优化策略

#### 策略1：图片压缩（最高优先级）

按第四章4.4节方案，将27张图从24.4MB压缩至~3.5MB（WebP q=82, 1600px）。这是最根本的优化。

#### 策略2：懒加载

`render_review.py`生成的`<img>`标签已包含`loading="lazy"`和`decoding="async"`：

```html
<img src="images/webp/heart_coronary.webp" alt="图1：心脏冠状动脉"
     loading="lazy" decoding="async">
```

- `loading="lazy"`：图片进入视口前不加载，首屏加载时间大幅减少
- `decoding="async"`：图片解码不阻塞主线程
- Cloudflare官方推荐使用懒加载优化移动端体验["https://developers.cloudflare.com/images/tutorials/optimize-mobile-viewing/"]

#### 策略3：响应式图片（可选进阶）

使用`<picture>`元素提供多分辨率/多格式：

```html
<picture>
  <source type="image/avif" srcset="images/avif/heart_coronary.avif">
  <source type="image/webp" srcset="images/webp/heart_coronary.webp">
  <img src="images/webp/heart_coronary.webp" alt="图1：心脏冠状动脉"
       loading="lazy" decoding="async">
</picture>
```

- 支持AVIF的浏览器（Chrome 85+, Firefox 93+, Safari 16+）加载更小的AVIF
- 不支持的浏览器回退到WebP
- 预期再减少20-30%图片流量

#### 策略4：Cloudflare Image Resizing（边缘实时优化）

Cloudflare提供Image Resizing服务，可在边缘节点实时调整图片尺寸和格式：

- 免费额度：5,000次转换/月
- 用法：在图片URL后加参数，如`/cdn-cgi/image/width=720,format=webp/images/raw/heart_coronary.png`
- Cloudflare自动缓存转换结果，后续请求直接命中缓存
- 适合不想提前批量压缩的场景，但5,000次/月对高流量站点可能不够["https://yureiblog.com/cloudflare-image-resizing","https://eastondev.com/blog/en/posts/dev/20251203-astro-image-optimization-guide/"]

**建议**：提前批量压缩为WebP（策略1）比依赖Image Resizing更可控、更省钱。Image Resizing作为补充，用于用户上传的动态图片。

#### 策略5：CDN缓存配置

在`_headers`文件中为图片设置长缓存：

```
# 部署根目录的 _headers 文件
/images/*
  Cache-Control: public, max-age=31536000, immutable
  Access-Control-Allow-Origin: *

/*.html
  Cache-Control: public, max-age=300
```

- 图片文件名包含内容hash或版本号时，用`immutable`缓存1年
- HTML文件缓存5分钟，确保更新及时生效
- Cloudflare CDN全球节点缓存图片，用户访问延迟<100ms

#### 策略6：构建时排除原图

在`_redirects`或构建配置中，确保只部署`images/webp/`（和可选`images/avif/`），不部署`images/raw/`和`images/annotated/`：

```
# .gitignore 或构建排除
images/raw/
images/annotated/
*.png
```

部署产物仅包含：HTML + CSS/JS（内联） + `images/webp/*.webp`，总计约4MB。

### 6.3 优化效果汇总

| 优化项 | 效果 |
|--------|------|
| PNG→WebP q=82 + 1600px | 24.4MB → ~3.5MB（-86%） |
| 懒加载 | 首屏加载时间减少60%+（仅加载视口内图片） |
| CDN缓存 | 重复访问图片延迟<100ms，回源流量接近0 |
| 排除原图部署 | 部署产物从~25MB降至~4MB |
| AVIF可选格式 | 现代浏览器再减20-30%流量 |
| base64内联HTML | ❌ 不用于Pages部署（32.7MB超限），仅用于本地PDF打印 |

---

## 七、行动建议总结

### 立即执行（1-2天）

1. **扩展render_review.py**：按第四章4.2节修改，添加`![alt](path)`图片支持，添加`--embed-images`参数
2. **压缩现有27张图**：用Pillow批量缩至1600px + WebP q=82，预期从24.4MB降至~3.5MB
3. **更新MD引用路径**：将`images_v2/xxx.png`改为`images/webp/xxx.webp`

### 短期执行（1周）

4. **搭建标注工具链**：实现第三章的`annotate_image.py`，为现有27张图创建标注YAML
5. **注册通义万相API**：获取API Key，测试Qwen-Image-3.0生成医学原图
6. **编写批量提示词生成器**：按第五章5.1节实现，从知识点列表生成结构化提示词

### 中期规划（2-4周）

7. **新增MedIllustrator Agent**：在5-Agent管线中插入插图生成步骤
8. **Cloudflare Pages部署优化**：配置`_headers`缓存、排除原图、测试懒加载效果
9. **建立图片审核流程**：AI生成图需人工审核解剖准确性，标注YAML需医学专业人员确认

### 关键决策

| 决策点 | 推荐选择 | 理由 |
|--------|---------|------|
| 主力绘图工具 | 通义万相 Qwen-Image-3.0 | 中文理解最准，API最便宜(0.14-0.18元/张)，医学验证案例多 |
| 标注方式 | Python Pillow程序叠加 | AI生成中文标注错误率高(8.2%-37%)，程序叠加100%准确且可迭代 |
| 图片格式 | WebP q=82, 1600px | 浏览器兼容性好，-86%体积，肉眼无损 |
| HTML图片模式 | 外部引用(部署) + base64内联(打印) | Pages部署用外部引用，本地PDF打印用自包含HTML |
| 标注坐标 | 相对比例(0~1) + YAML配置 | 分辨率无关，与图片分离，修改不需重新生成图 |
