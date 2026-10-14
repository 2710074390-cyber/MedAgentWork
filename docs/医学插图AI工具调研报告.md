# 批量生成"写实医学插图"AI工具调研与可复现操作流程

> 调研日期：2026-09-07 | 适用环境：Windows + Python 3.12 + 中国大陆网络
> 项目：MedAgentWork — 15学科医学复习资料批量插图（解剖/病理/超微结构/机制图）

---

## 一、执行摘要

**核心结论：**

1. **"无标注原图 + 后期PIL叠加中文标注"是目前唯一可靠的工业级方案。** 所有文生图模型（包括最新的Ideogram 4、GPT Image 2）在中文长文本标注上均无法达到100%准确，医学术语零容错要求必须走"图-文分离"工作流。这一点已成为视觉文字研究领域的明确共识["https://juejin.cn/post/7660776101882609718"]。

2. **医学写实生成能力排名：** DALL-E 3/GPT Image ≥ Midjourney v7 > Flux.1 > Stable Diffusion 3.5。一项针对颅面解剖插图的同行评审研究（4名评审者，ICC=0.858）发现：**DALL-E 3在解剖细节和可用性上得分最高，Midjourney v6在美学和性价比上最优，但所有模型均存在显著解剖错误**["https://pdfs.semanticscholar.org/dc11/cae0ca1ea712d167b495f247ef081544b563.pdf"]。

3. **国内工具链推荐：即梦（Seedream 4.0）做底图 + Pillow叠加标注。** 即梦API约0.18元/张（火山引擎10万次包18000元），支持2K直出、中文提示词理解好、国内直连稳定。通义万相Wan2.7在文字渲染和可控编辑上有突破，但医学写实能力尚需验证["https://www.volcengine.com/docs/85621/1544714","http://news.qq.com/rain/a/20260401A06XJ900"]。

4. **不存在成熟的"医学插图专用文生图模型"。** BioRender和MedPeer是**素材库+拖拽编辑**平台（非AI生成），BiomedCLIP/MONAI/Med-PaLM M是医学影像分析模型而非插图生成模型。HuggingFace上有少量医学微调LoRA但质量参差。

5. **总成本估算（750-1500张）：** 纯API路线约 ¥150-500；订阅制路线约 ¥200-800；混合路线（底图API+人工筛选+自动标注）约 ¥300-600 + 人工时间。

---

## 二、通用文生图工具逐一评估

### 2.1 评估总表

| 工具 | 入口URL | 价格档位 | 医学写实能力(1-5) | 文字渲染 | 中文支持 | 批量能力 | 图生图/Inpainting |
|------|---------|----------|-------------------|----------|----------|----------|-------------------|
| **Midjourney v7/v8** | midjourney.com | $10-120/月订阅 | ★★★★☆ | 差(41%准确率) | 弱 | 中(Discord/无API) | 有(Vary Region) |
| **DALL-E 3 / GPT Image 1.5** | platform.openai.com | API $0.04-0.08/张 | ★★★★☆ | 中(50-65%) | 中 | 强(API) | 有(编辑API) |
| **Stable Diffusion 3.5/XL** | huggingface.co / 本地 | 本地免费/API $0.01-0.05 | ★★★☆☆ | 差(20-30%) | 弱(需中文LoRA) | 极强(本地/ComfyUI) | 有(ControlNet/Inpaint) |
| **Flux.1 (dev/pro)** | fal.ai / replicate.com | API $0.003-0.055/张 | ★★★★☆ | 差(20%) | 弱 | 强(API/本地) | 有(Kontext) |
| **Ideogram 3/4** | ideogram.ai | $8-60/月 / API | ★★★☆☆ | **极佳(90-95%英文)** | **一般(中文易错)** | 中(API) | 有 |
| **Recraft V3/V4** | recraft.ai | $12-40/月 / API | ★★★☆☆ | 中(58%) | 弱 | 中(API) | 有(矢量输出) |
| **即梦 (Seedream 4.0)** | jimeng.jianying.com | 免费额度/API ~0.18元/张 | ★★★☆☆ | 中 | **强** | 强(火山API) | 有(智能画布) |
| **文心一格** | yige.baidu.com | 积分制/API | ★★★☆☆ | 中 | 强 | 中(API) | 有 |
| **通义万相 (Wan2.7)** | tongyi.aliyun.com/wan | 免费额度/API ~0.2-0.3元/张 | ★★★☆☆ | **较强(文字渲染优化)** | 强 | 强(百炼API) | 有(局部编辑) |
| **可灵 (Kling)** | kling.kuaishou.com | 积分制 | ★★☆☆☆ | 差 | 中 | 中 | 有(偏视频) |

### 2.2 各工具详细点评

#### Midjourney v7/v8
- **医学写实能力：** 美学质量全场最佳，光影和构图专业，但解剖准确性不稳定——"更像艺术品而非医学教材图"["https://ailog.page/midjourney-vs-dall-e-3-vs-stable-diffusion-i-tested-all-three-for-200-hours/"]。
- **文字渲染：** 长文本准确率仅约41%，中文几乎不可用["https://apatero.com/blog/recraft-v4-vs-ideogram-3-graphic-design-2026"]。
- **致命短板：** 无官方API，只能通过Discord或网页操作，批量自动化困难；国内访问需代理。
- **价格：** Basic $10/月(~200张)，Standard $30/月(15h快时+无限Relax)，Pro $60/月["https://nesyona.com/articles/midjourney-pricing-2026"]。
- **适用场景：** 少量高质量封面图、机制示意图的美学底图。

#### DALL-E 3 / GPT Image 1.5/2
- **医学写实能力：** 解剖细节和提示词遵循度最佳。颅面解剖研究中DALL-E 3在"解剖细节"和"可用性"两项均排名第一["https://pdfs.semanticscholar.org/dc11/cae0ca1ea712d167b495f247ef081544b563.pdf"]。
- **文字渲染：** 约50-65%准确率，优于Midjourney但仍不可靠["https://apatero.com/blog/recraft-v4-vs-ideogram-3-graphic-design-2026"]。
- **API：** 完善的REST API，支持批量调用、图生图编辑。
- **价格：** Standard 1024×1024 $0.04/张，HD $0.08/张；GPT Image 1 Mini约$0.015/张["https://intuitionlabs.ai/pdfs/ai-image-pricing-2026-google-gemini-vs-openai-gpt-cost-analysis.pdf","https://awesomeagents.ai/pricing/image-generation-pricing/"]。
- **国内访问：** 需代理，API直连不稳定。
- **适用场景：** 国际工具链首选底图生成器，解剖准确性要求高的场景。

#### Stable Diffusion 3.5 / XL
- **医学写实能力：** 基础模型一般，但**可通过LoRA微调医学风格**，社区有AnatomyFix等骨骼一致性LoRA["https://ask.csdn.net/questions/9587593"]。
- **文字渲染：** 最差，长文本仅20-30%准确率["https://techunfoldedai.com/ideogram-ai/"]。
- **最大优势：** 完全本地运行（免费）、ComfyUI节点式工作流支持批量自动化、ControlNet精确控制构图、可加载医学专用LoRA。
- **硬件要求：** 8GB+ VRAM推荐；Flux级别需12GB+。
- **适用场景：** 有GPU资源、需要最大可控性和批量自动化、预算极低的团队。

#### Flux.1 (Black Forest Labs)
- **医学写实能力：** 整体质量接近Midjourney，提示词遵循度好，细节丰富。
- **文字渲染：** 差，约20%准确率["https://techunfoldedai.com/ideogram-ai/"]。
- **开源权重：** dev版权重开放，可本地运行和微调；pro版仅API。
- **价格：** schnell $0.003/张，dev $0.025-0.03/张，pro $0.055/张（按百万像素计费）["https://fal.ai/docs/model-api-reference/image-generation-api/flux-dev","https://flux-1.ai/flux-pro-api-pricing-and-code-examples/"]。
- **适用场景：** 开源生态中的高质量选择，可本地部署避免网络问题。

#### Ideogram 3/4
- **文字渲染：** 全场最佳，英文短文本90-95%准确率，长文本68.5%["https://techunfoldedai.com/ideogram-ai/","https://aitoolradar.io/guides/ideogram"]。
- **中文：** **官方和社区均反馈"表现一般"**，中文场景仍出现缺笔少画和乱码["https://blog.csdn.net/qq_40999403/article/details/162399255","https://www.iesdouyin.com/share/video/7649789934659816730"]。
- **医学写实：** 中等，设计类图形强于写实解剖。
- **价格：** 免费层有限，Plus $8/月，Pro $20+/月；API按量。
- **适用场景：** 英文标注的医学海报/信息图；不适合中文标注直接生成。

#### 即梦 (字节跳动 / Seedream 4.0)
- **医学写实能力：** 3.0模型影视质感强，4.0在4K清晰度和亚洲人脸一致性上突破；解剖准确性中等，需精细提示词引导["http://m.toutiao.com/group/7549011804555444787/"]。
- **中文支持：** **全场最强**，中文提示词理解和中文元素渲染优秀。
- **API：** 火山引擎即梦AI图像生成3.0系列，10万次包¥18,000（约0.18元/张），50万次包¥80,000（0.16元/张）["https://www.volcengine.com/docs/85621/1544714"]。
- **批量：** API支持高并发，Agent模式可自然语言批量生成["http://m.toutiao.com/group/7549011804555444787/"]。
- **图生图：** 智能画布支持局部编辑、参考图。
- **适用场景：** **国内工具链首选**，中文提示词+稳定直连+合理API价格。

#### 通义万相 (阿里 / Wan2.7 / Qwen-Image)
- **最新进展：** Wan2.7-Image（2026年4月发布）重点突破了**文字渲染**和**局部精准编辑**，支持4K分辨率，文生图人类偏好盲测得分高["http://news.qq.com/rain/a/20260402A03BJZ00","http://news.qq.com/rain/a/20260401A06XJ900"]。
- **Qwen-Image-2512：** 开源模型，文本编码器基于Qwen3-VL，中文理解好，X-Omni英文OCR准确率0.97，中文持续优化中["https://post.m.smzdm.com/p/awwrgk7g/"]。
- **API：** 阿里云百炼平台，公测期有免费额度，商业化后约0.2-0.3元/张["https://help.aliyun.com/zh/model-studio/text-to-image-api-reference"]。
- **适用场景：** 文字渲染要求高的场景可作为即梦的备选/补充；开源版可本地部署。

#### 文心一格 (百度)
- 国风生成能力突出，医学写实能力中等，中文支持好。
- 每日登录送60-100积分，免费版可满足少量需求["https://t.cj.sina.cn/articles/view/7879848900/1d5acf3c401902rvuo"]。
- API通过百度智能云调用，价格按量。
- **适用场景：** 补充工具，非首选。

#### 可灵 (快手)
- 核心能力在视频生成，图像生成非主打，医学写实能力较弱。
- **适用场景：** 不推荐用于医学插图批量生产。

---

## 三、医学专用AI模型/工具调研

### 3.1 关键发现：不存在成熟的"医学插图专用文生图模型"

| 名称 | 类型 | 是否能生成医学插图 | 说明 |
|------|------|-------------------|------|
| **BioRender** | 素材库+拖拽编辑平台 | 间接（非AI生成） | 50000+生命科学矢量图标，手动拼装；2025年新增AI辅助生成流程图/时间线初稿，但核心仍是素材库 |
| **MedPeer** | 国内科研绘图平台 | 间接（AI辅助+素材库） | 10万+医学矢量素材，AI输入自然语言生成机制图初稿后手动调整；非写实解剖生成 |
| **BiomedCLIP** | 医学视觉-语言模型 | ❌ 不能 | 用于医学图像分类/检索，不是生成模型 |
| **MONAI** | 医学影像分析框架 | ❌ 不能 | 基于PyTorch的医学影像分割/分类/生成框架，面向MRI/CT等真实影像，非教学插图 |
| **Med-PaLM M** | 多模态医学大模型 | ❌ 不能（未开放） | Google的医学多模态模型，主要做影像理解和问答，未公开发布生成能力 |
| **HuggingFace医学LoRA** | 社区微调模型 | 部分可用 | 有少量针对解剖图/医学插画的SD/Flux LoRA，但质量参差、无权威认证，需自行筛选 |

### 3.2 BioRender 详细评估

- **本质：** 不是AI文生图工具，而是**科学插图素材库 + 在线编辑器**。用户从50000+矢量图标中拖拽拼装，覆盖分子生物学、免疫学、神经科学等30+细分领域["https://3g.dxy.cn/bbs/topic/52750913"]。
- **AI功能（2025年新增）：** AI Credits附加包，可从文本提示词生成可编辑的流程图/时间线/协议图初稿（1 credit/次），免费用户一次性赠送20 credits["https://help.biorender.com/hc/en-gb/articles/36112007097501-How-to-access-and-manage-the-AI-Credits-Add-on-in-BioRender"]。
- **价格：** 个人版$99/月，学术折扣；免费版仅96dpi带水印，最多5个项目["https://sci-draw.com/blog/best-scientific-illustration-software-2025","https://www.biorender.net.cn/rumen/bior-asjda.html"]。
- **国内使用：** 访问卡顿，需代理["https://3g.dxy.cn/bbs/topic/52778234"]。
- **与本项目的关系：** BioRender擅长**机制示意图和细胞分子图**（矢量风格），但不擅长**写实解剖图和病理图**。且其素材为矢量风格，与项目需要的"写实"风格不符。可作为机制图的参考/补充工具。

### 3.3 MedPeer 详细评估

- **国内定位：** 专为科研工作者定制的绘图平台，生物医药领域深耕多年["https://www.aitop100.cn/tools/product-medpeer"]。
- **AI绘图：** 输入自然语言（如"PD-1/PD-L1信号通路抑制T细胞活化机制"），AI调用内置素材库生成初稿，可自定义调整颜色/布局，输出1200dpi["https://3g.dxy.cn/bbs/topic/52940973"]。
- **价格：** 月度基础会员¥78，年度高级会员¥2,648；研值充值制（1000研值¥15）["https://apps.apple.com/cn/app/medpeer-ai%E7%A7%91%E7%A0%94%E5%85%A8%E5%AE%B6%E6%A1%B6/id1491133645"]。
- **外包精修：** 每张图¥100（绘图师用自有版权素材重绘为可编辑格式）["https://3g.dxy.cn/bbs/topic/53139819"]。
- **与本项目的关系：** 同BioRender，擅长**机制示意图**（矢量风格），不擅长写实解剖/病理。国内访问稳定，可作为机制图的备选工具。

---

## 四、文字渲染问题的解决方案

### 4.1 问题本质

AI文生图模型在像素空间中"画"文字，而非排版引擎渲染文字。这导致：
- 长文本拼写错误率高（Midjourney 41%，SD3 30%，Flux 20%）["https://apatero.com/blog/recraft-v4-vs-ideogram-3-graphic-design-2026","https://techunfoldedai.com/ideogram-ai/"]
- 中文等CJK文字因字形复杂，错误率更高
- 医学术语（长拉丁名、缩写）零容错要求下，直接生成不可接受

**行业共识："先生成无字背景，再渲染文字"是视觉文字研究领域的明确结论**——控制更准确，实际可用性更强["https://juejin.cn/post/7660776101882609718"]。

### 4.2 三套解决方案对比

| 方案 | 文字准确性 | 实现难度 | 批量友好度 | 推荐度 |
|------|-----------|---------|-----------|--------|
| **A. 无字底图 + PIL后期叠加** | 100% | 中（需写标注脚本） | 极高 | ★★★★★ |
| **B. 文字友好模型直接生成** | 英文90%/中文60% | 低 | 中 | ★★★☆☆ |
| **C. ControlNet控构图 + 后期叠加** | 100% | 高（需ComfyUI） | 高 | ★★★★☆ |

### 4.3 方案A详解：无字底图 + 后期叠加（推荐）

**工作流：**
1. 提示词中明确加入 `no text, no labels, no words, clean illustration`（无文字、无标注、干净插图）
2. AI生成纯视觉底图（raw_*.png）
3. Python脚本用Pillow读取底图，在指定位置叠加中文标注
4. 标注信息以JSON/YAML配置驱动，批量处理

**开源工具参考：GenImageText**（https://github.com/stephenlzc/GenImageText）
- 专门解决"AI图文字乱码"问题，分离图像生成和文字叠加
- 支持CJK文字，内置医学机制图预设（medical_mechanism, 1600×2000）
- 自动分析底图亮度和安全区域，智能调整文字位置和对比度
- 支持阴影、描边、发光、半透明背景等文字效果
- 依赖：Pillow + numpy，Python 3.8+["https://github.com/stephenlzc/GenImageText"]

### 4.4 方案B：文字友好模型直接生成

- **Ideogram 3/4：** 英文短文本90-95%准确，但中文"表现一般"，不适合中文医学标注["https://aitoolradar.io/guides/ideogram","https://blog.csdn.net/qq_40999403/article/details/162399255"]
- **通义万相Wan2.7：** 2026年重点优化文字渲染，中文能力较强，可尝试短标注直接生成，但长医学术语仍建议后期叠加["http://news.qq.com/rain/a/20260401A06XJ900"]
- **GPT Image 2：** 65%准确率，英文短标注可尝试

### 4.5 方案C：ControlNet控构图 + 后期叠加

- 用Canny/Depth/OpenPose等ControlNet预处理器从参考解剖图提取结构
- SD/Flux在结构约束下生成风格化底图
- 再用PIL叠加标注
- 优势：构图可控性最高，可保证解剖结构位置正确
- 劣势：需要准备参考图、搭建ComfyUI工作流、硬件要求高
- 医学场景可用AnatomyFix LoRA增强骨骼一致性["https://ask.csdn.net/questions/9587593"]

---

## 五、四类医学插图提示词模板

> 以下模板均按"无字底图"设计，标注由后期叠加。使用时替换 `{}` 中的具体内容。

### 5.1 写实解剖图

**模板A（器官整体解剖）：**
```
English:
Photorealistic medical illustration of {human heart, anterior view}, 
detailed anatomical dissection showing {coronary arteries, ventricles, atria}, 
scientifically accurate, textbook quality, soft diffused lighting, 
neutral gray background, high resolution 2048px, 
no text no labels no words, clean illustration, 
professional medical atlas style

Negative: cartoon, anime, abstract, blurry, low quality, text, labels, watermark, distorted anatomy, extra organs
```

```
中文（即梦/通义万相用）：
写实医学插图，{人体心脏，前面观}，精细解剖展示{冠状动脉、心室、心房}，
科学准确，教科书级质量，柔和漫射光，中性灰色背景，
高分辨率2048px，无文字无标注，干净插图，专业医学图谱风格
负面提示：卡通、动漫、抽象、模糊、低质量、文字、标注、水印、解剖变形、多余器官
```

**模板B（系统解剖）：**
```
English:
Full body anatomical illustration of {human nervous system}, 
central and peripheral nerves highlighted in {yellow}, 
surrounding tissues semi-transparent, photorealistic 3D render, 
medical textbook style, even lighting, white background, 
no text no labels, ultra detailed, 8k quality

Negative: text, labels, cartoon, stylized, low resolution, muscular build, clothing
```

### 5.2 写实病理图

**模板A（大体病理标本）：**
```
English:
Photorealistic gross pathology specimen of {cirrhotic liver}, 
showing {nodular surface, fatty degeneration, fibrotic bands}, 
fresh tissue texture, clinical photography style, 
scale-appropriate, neutral background, soft side lighting, 
no text no labels no ruler, high detail medical photography

Negative: text, labels, cartoon, illustration style, healthy organ, plastic texture, oversaturated
```

**模板B（组织病理镜下）：**
```
English:
Photorealistic histopathology micrograph, {H&E stained lung tissue with adenocarcinoma}, 
showing {glandular structures, atypical nuclei, mitotic figures}, 
400x magnification view, professional pathology slide photography, 
vibrant eosin and hematoxylin colors, no text no labels, 
ultra sharp focus, medical publication quality

Negative: text, labels, cartoon, blurry, low contrast, immunohistochemistry stain, gross specimen
```

### 5.3 超微结构图

**模板A（透射电镜）：**
```
English:
Transmission electron micrograph (TEM) style illustration of {mitochondria in cardiac muscle cell}, 
showing {cristae, double membrane, matrix granules}, 
ultrastructural detail, grayscale with subtle sepia tone, 
high magnification scientific image, realistic electron microscopy texture, 
no text no labels, clean background, research publication quality

Negative: text, labels, color, cartoon, 3D render style, blurry, SEM style, light microscope
```

**模板B（扫描电镜/3D超微）：**
```
English:
Scanning electron micrograph (SEM) style 3D illustration of {glomerular podocytes with foot processes}, 
ultrastructural surface detail, false color {golden brown}, 
dramatic angled lighting, scientific visualization, 
no text no labels, ultra detailed, high magnification, 
medical research journal cover quality

Negative: text, labels, cartoon, TEM style, flat 2D, blurry, low resolution
```

### 5.4 机制示意图

**模板A（分子机制）：**
```
English:
Clean scientific mechanism diagram, {insulin signaling pathway in cell}, 
showing {receptor binding, phosphorylation cascade, GLUT4 translocation, glucose uptake}, 
3D render style with semi-transparent cell membrane, 
molecules as detailed 3D shapes, arrows showing direction, 
color-coded components, white background, professional journal figure style, 
no text no labels, high resolution, minimalist composition

Negative: text, labels, cartoon, busy background, photorealistic photography, watercolor, oil painting
```

**模板B（病理生理机制）：**
```
English:
Medical pathophysiology mechanism illustration, {atherosclerosis plaque development in artery}, 
cross-section view showing {endothelial dysfunction, LDL accumulation, foam cell formation, plaque rupture}, 
3D medical illustration style, layered tissue detail, 
color-coded cell types, clear spatial progression, 
neutral background, soft lighting, no text no labels, 
textbook quality, high detail

Negative: text, labels, cartoon, abstract, healthy artery, photography style, blurry
```

---

## 六、两套可直接复现的端到端操作流程

### 6.1 流程一：国际工具链（DALL-E 3 API + Pillow标注）

**适用：** 有稳定代理、追求最高解剖准确性、预算中等

**前置准备：**
- OpenAI API Key（需海外支付方式）
- Python 3.12 + `pip install openai Pillow pyyaml`
- 系统安装中文字体（推荐思源黑体 NotoSansCJKsc-Bold.otf）

**步骤1：准备标注配置文件（annotations.yaml）**
```yaml
- id: heart_anatomy_01
  prompt: "Photorealistic medical illustration of human heart anterior view, detailed anatomical dissection showing coronary arteries ventricles atria, scientifically accurate, textbook quality, soft diffused lighting, neutral gray background, no text no labels no words, clean illustration, professional medical atlas style"
  negative: "cartoon, anime, abstract, blurry, text, labels, watermark, distorted anatomy"
  size: "1024x1024"
  annotations:
    - text: "主动脉"
      x: 0.52
      y: 0.15
      font_size: 28
      color: "#FFFFFF"
      stroke: "#000000"
    - text: "左冠状动脉"
      x: 0.30
      y: 0.35
      font_size: 24
      color: "#FFFFFF"
      stroke: "#000000"
```

**步骤2：批量生成无字底图（generate_base.py）**
```python
import yaml, os, requests
from openai import OpenAI

client = OpenAI(api_key="your-key")
os.makedirs("raw_images", exist_ok=True)

with open("annotations.yaml", "r", encoding="utf-8") as f:
    items = yaml.safe_load(f)

for item in items:
    response = client.images.generate(
        model="dall-e-3",
        prompt=item["prompt"],
        n=1,
        size=item.get("size", "1024x1024"),
        quality="hd",
    )
    img_url = response.data[0].url
    img_data = requests.get(img_url).content
    with open(f"raw_images/{item['id']}.png", "wb") as f:
        f.write(img_data)
    print(f"Generated: {item['id']}")
```

**步骤3：批量叠加中文标注（annotate.py）**
```python
from PIL import Image, ImageDraw, ImageFont
import yaml, os

FONT_PATH = "C:/Windows/Fonts/simhei.ttf"  # 或 NotoSansCJKsc-Bold.otf

def draw_text_with_stroke(draw, pos, text, font, fill, stroke_fill, stroke_width=2):
    x, y = pos
    for dx in range(-stroke_width, stroke_width+1):
        for dy in range(-stroke_width, stroke_width+1):
            if dx*dx + dy*dy <= stroke_width*stroke_width:
                draw.text((x+dx, y+dy), text, font=font, fill=stroke_fill)
    draw.text(pos, text, font=font, fill=fill)

with open("annotations.yaml", "r", encoding="utf-8") as f:
    items = yaml.safe_load(f)

os.makedirs("final_images", exist_ok=True)

for item in items:
    img = Image.open(f"raw_images/{item['id']}.png").convert("RGBA")
    draw = ImageDraw.Draw(img)
    W, H = img.size
    
    for ann in item.get("annotations", []):
        font = ImageFont.truetype(FONT_PATH, ann.get("font_size", 24))
        x = int(ann["x"] * W)
        y = int(ann["y"] * H)
        draw_text_with_stroke(
            draw, (x, y), ann["text"], font,
            fill=ann.get("color", "#FFFFFF"),
            stroke_fill=ann.get("stroke", "#000000"),
            stroke_width=ann.get("stroke_width", 2)
        )
    
    img = img.convert("RGB")
    img.save(f"final_images/{item['id']}.jpg", quality=95)
    print(f"Annotated: {item['id']}")
```

**步骤4：质检与筛选**
- 人工逐张检查解剖准确性（建议学科专家或对照教材）
- 不合格的重新生成（修改提示词或换seed）
- 标注位置微调（修改YAML中x/y坐标）

**时间估算：** 配置1小时 + 生成（750张×~15秒/张≈3小时，可并发）+ 标注（自动，分钟级）+ 质检（750张×1分钟/张≈12.5小时）

---

### 6.2 流程二：国内工具链（即梦API + Pillow标注）

**适用：** 国内直连、中文提示词、稳定可靠、成本可控

**前置准备：**
- 火山引擎账号，开通即梦AI图像生成服务
- 获取API Key（火山方舟控制台）
- Python 3.12 + `pip install volcengine Pillow pyyaml`
- 中文字体（Windows自带simhei.ttf即可）

**步骤1：开通服务与获取密钥**
1. 访问 https://www.volcengine.com/ 注册并实名认证
2. 进入"火山方舟"→"模型广场"→"即梦AI-图像生成3.0"
3. 开通服务，购买次数包（10万次¥18,000，或先按量测试）
4. 在"API Key管理"中创建密钥

**步骤2：批量生成底图（jimeng_generate.py）**
```python
import yaml, os, base64, json
from volcengine.visual.VisualService import VisualService

visual_service = VisualService()
visual_service.set_ak("your-access-key")
visual_service.set_sk("your-secret-key")

os.makedirs("raw_images", exist_ok=True)

with open("annotations.yaml", "r", encoding="utf-8") as f:
    items = yaml.safe_load(f)

for item in items:
    req = {
        "req_key": "high_aes",  # 即梦图像生成
        "prompt": item["prompt"],  # 中文提示词
        "width": 1024,
        "height": 1024,
        "return_url": True,
        "algorithm_base_resp": {"model_version": "3.0"},
    }
    resp = visual_service.cv_process(req)
    # 解析返回的图片URL并下载
    img_url = resp["data"]["image_urls"][0]
    import requests
    img_data = requests.get(img_url).content
    with open(f"raw_images/{item['id']}.png", "wb") as f:
        f.write(img_data)
    print(f"Generated: {item['id']}")
```

> **注意：** 即梦API的具体调用参数以火山引擎官方文档为准（https://www.volcengine.com/docs/85621/1995636），上述为示例结构。也可通过火山方舟的OpenAI兼容接口调用。

**步骤3：叠加标注** — 同流程一的annotate.py，无需修改

**步骤4：利用即梦智能画布做局部重绘（可选）**
- 对解剖结构错误但整体构图好的图，使用即梦"智能画布"的局部重绘功能
- 框选错误区域，输入修正提示词（如"correct the coronary artery branching pattern"）
- 重绘后重新叠加标注

**时间估算：** 同流程一，但生成速度更快（国内服务器），网络零故障

---

## 七、"无标注原图 + 后期叠加中文标注"Python方案要点

### 7.1 技术栈选择

| 组件 | 推荐库 | 理由 |
|------|--------|------|
| 图像读写 | **Pillow (PIL)** | 轻量、稳定、中文ttf支持好 |
| 标注配置 | **YAML / JSON** | 人类可读，便于人工调整坐标 |
| 批量处理 | **concurrent.futures** | 多进程/多线程加速IO |
| 字体 | **思源黑体 (Noto Sans CJK SC)** | 开源免费商用，字形清晰，多字重 |
| 可选：标注线 | **Pillow ImageDraw.line** | 绘制从标注文字到解剖结构的引导线 |
| 可选：自动布局 | **GenImageText** | 开源工具，自动分析底图安全区域 |

### 7.2 标注布局策略

**策略1：固定坐标（推荐用于批量生产）**
- 每张图的标注位置在YAML中手动指定（相对坐标0-1）
- 优点：精确可控，医学标注必须指向正确结构
- 缺点：每张图需人工确认坐标

**策略2：侧边标注栏（推荐用于解剖图）**
- 在图片右侧或底部预留20%空白区域作为标注栏
- 标注文字+引导线从侧边指向结构
- 提示词中加入 `leave blank space on right side for labels`
- 优点：标注不遮挡解剖结构，布局统一
- 缺点：需要调整构图

**策略3：编号标注（推荐用于复杂解剖图）**
- 底图上用PIL叠加数字编号（1, 2, 3...）
- 图片下方或单独的图注中列出编号对应中文名称
- 优点：图面干净，适合结构密集的图
- 缺点：读者需对照图注

**策略4：GenImageText自动布局**
- 使用开源工具自动分析底图亮度分布，在低亮度/高对比度区域放置文字
- 内置medical_mechanism预设
- 适合机制图，不太适合需要精确指向的解剖图["https://github.com/stephenlzc/GenImageText"]

### 7.3 标注视觉规范

```python
# 推荐标注样式参数
ANNOTATION_STYLE = {
    "font": "NotoSansCJKsc-Medium.otf",  # 中等字重，清晰易读
    "font_size": 24,  # 2048px图上约占1.2%高度
    "color": "#FFFFFF",  # 白色文字
    "stroke_color": "#000000",  # 黑色描边
    "stroke_width": 2,  # 2px描边确保在任何背景上可读
    "leader_line": True,  # 绘制引导线
    "leader_color": "#FFFFFF",
    "leader_width": 1,
    "dot_radius": 3,  # 引导线端点圆点
}
```

### 7.4 批量标注脚本核心逻辑

```python
# 伪代码：批量标注主流程
def batch_annotate(config_path, raw_dir, output_dir, font_path):
    config = load_yaml(config_path)
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        for item in config:
            futures.append(executor.submit(
                annotate_single,
                raw_image=f"{raw_dir}/{item['id']}.png",
                annotations=item['annotations'],
                output=f"{output_dir}/{item['id']}.jpg",
                font_path=font_path
            ))
        for f in as_completed(futures):
            f.result()  # 异常会在此抛出
```

---

## 八、批量生产工作流设计

### 8.1 完整流水线

```
知识点清单 → 提示词生成 → 底图批量生成 → 自动初筛 → 人工质检 → 标注叠加 → 终检 → 入库
   (1)         (2)          (3)           (4)        (5)       (6)       (7)     (8)
```

| 步骤 | 工具 | 耗时(750张) | 说明 |
|------|------|-------------|------|
| **1. 知识点清单** | 人工/LLM辅助 | 4-8小时 | 从复习资料中提取需要配图的知识点，确定图类型（解剖/病理/超微/机制） |
| **2. 提示词生成** | GPT-4/豆包 + 模板 | 2-4小时 | 用五类模板批量生成提示词，LLM辅助填充具体解剖结构名称 |
| **3. 底图批量生成** | 即梦API/DALL-E 3 API | 2-4小时 | API并发调用，每知识点生成2-3张候选（提高筛选通过率） |
| **4. 自动初筛** | Python脚本 | 分钟级 | 过滤纯黑/纯白/明显崩坏图；可用CLIP评分排序 |
| **5. 人工质检** | 学科专家/医学生 | 12-20小时 | 核心瓶颈！逐张检查解剖准确性，通过率预计40-60%，不合格重新生成 |
| **6. 标注叠加** | Pillow脚本 | 分钟级 | 自动批量叠加中文标注，坐标从YAML读取 |
| **7. 终检** | 人工 | 2-4小时 | 检查标注位置准确性、文字可读性、引导线指向 |
| **8. 入库** | 文件管理 | 分钟级 | 按学科/知识点命名，嵌入Markdown |

### 8.2 关键效率优化

1. **提示词模板化：** 五类模板覆盖80%场景，每类只替换具体结构名称
2. **批量生成2-3张候选：** 虽然增加生成成本，但大幅提高质检通过率，总体更省时间
3. **质检分级：** 先由AI/医学生初筛（检查明显错误），再由专家终审关键图
4. **标注坐标复用：** 同类型图（如都是心脏前面观）的标注坐标可复用模板
5. **并发生成：** API调用支持10-20并发，750张底图可在1小时内完成

### 8.3 质检标准清单

- [ ] 解剖结构数量正确（无多余/缺失）
- [ ] 结构位置和比例符合教材
- [ ] 左右侧正确（心脏左右、肺左右等）
- [ ] 无文字乱码残留（底图应为纯无字）
- [ ] 标注文字清晰可读（描边/对比度足够）
- [ ] 标注引导线指向正确结构
- [ ] 无AI伪影（多余手指、融合结构、扭曲血管）
- [ ] 分辨率≥1024px（打印PDF需≥150dpi）

---

## 九、成本估算

### 9.1 假设条件
- 15学科 × 50-100张 = **750-1500张最终图**
- 每知识点生成2-3张候选 → 实际生成 **1500-4500张**
- 质检通过率约50%

### 9.2 各工具总成本对比（人民币）

| 工具/方案 | 单价 | 生成量(张) | 生成总成本 | 标注成本 | 总计 | 备注 |
|-----------|------|-----------|-----------|---------|------|------|
| **即梦API** | ¥0.18/张 | 3000 | ¥540 | ¥0 | **¥540** | 国内首选，10万次包 |
| **DALL-E 3 API (HD)** | $0.08(¥0.58)/张 | 3000 | ¥1,740 | ¥0 | **¥1,740** | 解剖最准，但需代理 |
| **DALL-E 3 API (Standard)** | $0.04(¥0.29)/张 | 3000 | ¥870 | ¥0 | **¥870** | 性价比之选 |
| **Flux Dev API** | $0.03(¥0.22)/张 | 3000 | ¥660 | ¥0 | **¥660** | 开源生态 |
| **Midjourney Standard** | $30/月(¥217) | 不限(Relax) | ¥434(2月) | ¥0 | **¥434** | 无API，批量慢 |
| **Stable Diffusion本地** | ¥0(电费) | 不限 | ¥0-50 | ¥0 | **¥50** | 需GPU，质量依赖模型 |
| **通义万相API** | ~¥0.25/张 | 3000 | ¥750 | ¥0 | **¥750** | 文字渲染好 |
| **BioRender个人版** | $99/月(¥715) | - | ¥1,430(2月) | - | **¥1,430** | 矢量风格，非写实 |
| **MedPeer年度高级** | ¥2,648/年 | - | ¥2,648 | - | **¥2,648** | 矢量风格，国内 |
| **MedPeer外包精修** | ¥100/张 | 750 | ¥75,000 | - | **¥75,000** | 人工绘制，最贵但最准 |

### 9.3 推荐方案成本

**推荐方案：即梦API做底图 + Pillow自动标注 + 人工质检**
- 生成成本：¥540（3000张候选）
- 标注成本：¥0（自动化）
- 人工成本：15-25小时 × 时薪（自估）
- **总计：约¥540 + 人工**

**备选方案：DALL-E 3 Standard API + Pillow标注（追求最高解剖准确性）**
- 生成成本：¥870
- **总计：约¥870 + 人工 + 代理费用**

---

## 十、结论与建议

### 10.1 核心建议

1. **立即采用"无字底图 + PIL后期标注"工作流**，不要再尝试让AI直接渲染中文医学标注。这是经过行业验证的唯一可靠方案。

2. **底图生成器选择：**
   - 国内环境优先用**即梦API**（稳定、便宜、中文好）
   - 解剖准确性要求极高的图，用**DALL-E 3 API**补充
   - 有GPU资源且预算极紧，用**Stable Diffusion + 医学LoRA**本地部署

3. **医学准确性无法完全依赖AI**——所有生成图必须经过人工质检。建议建立"医学生初筛 + 专家终审"两级质检体系。预计50%的生成图需要重做。

4. **机制示意图可考虑BioRender/MedPeer**作为补充工具（矢量风格、素材准确），但写实解剖/病理图必须用文生图工具。

5. **标注布局优先用"侧边标注栏"或"编号标注"策略**，避免标注文字遮挡解剖结构。引导线+描边文字是医学插图的标准样式。

### 10.2 风险提示

- **AI生成的解剖图可能存在微妙但严重的错误**（如血管分支模式错误、神经走向错误），非专业人士难以察觉。用于复习资料时，关键图必须由学科专家确认。
- **AI生成图的版权归属**在中国大陆尚不明确，用于出版/商业用途需谨慎。建议保留生成记录，并在资料中注明"AI辅助生成"。
- **API价格可能变动**，以上价格为2026年9月调研时的价格，实际以官方页面为准。

### 10.3 下一步行动清单

- [ ] 注册火山引擎账号，开通即梦图像生成API，购买小额次数包测试
- [ ] 用五类提示词模板各生成5张测试图，评估即梦的医学写实质量
- [ ] 编写Pillow标注脚本，实现YAML驱动的批量标注
- [ ] 选择1个学科（如解剖学）的20个知识点做端到端试点
- [ ] 建立质检标准文档和返工流程
- [ ] 试点验证后推广到全部15学科

---

## 附录：关键来源URL

### 工具评估
- Midjourney定价: https://nesyona.com/articles/midjourney-pricing-2026
- DALL-E 3 API定价: https://intuitionlabs.ai/pdfs/ai-image-pricing-2026-google-gemini-vs-openai-gpt-cost-analysis.pdf
- Flux API定价: https://fal.ai/docs/model-api-reference/image-generation-api/flux-dev
- Ideogram文字准确率: https://techunfoldedai.com/ideogram-ai/
- 即梦API定价: https://www.volcengine.com/docs/85621/1544714
- 通义万相Wan2.7: http://news.qq.com/rain/a/20260402A03BJZ00

### 医学准确性研究
- 颅面解剖插图AI模型有效性分析: https://pdfs.semanticscholar.org/dc11/cae0ca1ea712d167b495f247ef081544b563.pdf

### 文字渲染解决方案
- 工业级文字渲染方案: https://juejin.cn/post/7660776101882609718
- GenImageText开源工具: https://github.com/stephenlzc/GenImageText
- AI生图文字乱码修复: https://m.sohu.com/a/1023515217_122618923/
- 2026中文文字渲染模型实测: https://post.m.smzdm.com/p/az84x0mo/

### 医学专用工具
- BioRender定价: https://www.biorender.com/pricing
- BioRender AI Credits: https://help.biorender.com/hc/en-gb/articles/36112007097501
- MedPeer介绍: https://www.aitop100.cn/tools/product-medpeer
- 科研绘图软件对比: https://sci-draw.com/blog/best-scientific-illustration-software-2025

### ControlNet/批量工作流
- ComfyUI ControlNet指南: https://docs.comfy.org/zh/tutorials/controlnet/controlnet
- AnatomyFix LoRA: https://ask.csdn.net/questions/9587593

---

*报告完成于2026-09-07 | 所有价格和功能信息以各工具官方最新公告为准*
