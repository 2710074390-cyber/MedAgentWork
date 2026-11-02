# 插图管线退役留档（RETIRED · 2026-11-02）

**状态：已下线，禁止重新启用。**

用户 2026-11-02 明确「以后不需要插图相关」。原 HC-19 插图契约（生图阶段 6 / 配图清单 /
GATE-A5 配图项 / GATE-A6 / `medillustration` skill / 豆包图片 Agent 交接）整体退役。

## 为什么留在这里而不是删除

这些文件是历史工程证据（2026-09 ~ 2026-10 的配图试点、标注坐标量化教训、批量生图脚本），
删除会让历史报告与 JOURNAL 中的门禁记录失去可追溯对象。归档保留、移出活跃目录即可。

## 内含

| 文件 | 原路径 | 原用途 |
|------|--------|--------|
| `batch_illustration.py` | `scripts/` | 批量生图编排 |
| `annotate_image.py` | `scripts/` | YAML 驱动中文标注（label/overlay 双模式） |
| `_analyze_annot_pos.py` | `scripts/` | 标注坐标量化（颜色掩膜网格热区） |
| `check_inline_images.py` | `scripts/` | GATE-A6 占位符/清单一致性门禁 |
| `compose_atlas.py` | `scripts/` | 出版图谱多面板拼接 + 小标题带 + 程序标注 |
| `render_diagram.py` | `scripts/` | 确定性图示渲染（flow/compare/grid，Pillow 自绘） |
| `export_webp.py` | `scripts/` | annotated PNG → 1600px q82 WebP 批量导出 |
| `webp_to_png.py` | `scripts/` | images_webp → PNG 转换（Obsidian 显示兼容） |
| `medillustration_config.py` | `scripts/` | 跨平台字体探测 |
| `medillustration_config.yaml` | 仓库根 | 上述脚本的路径与样式配置 |
| `_write_stomato_annotate_yamls.py` | `scripts/` | 一次性标注 YAML 重写（口腔 6 张） |

skill 全文见 `archive/retired_skills/medillustration/`。

## 现行口径

- 复习资料、题库、解析一律**纯文本**：不写 `![图N：…](images_webp/…)` 占位、不出 `*_配图清单.md`、不建 `images_webp/`。
- 已交付历史产物中的图片与清单**不追溯、不回改、不删除**。
- `scripts/render_review.py` 仍保留 `![]()` 渲染兼容（老 MD 可导出），这只是渲染兼容，不构成插图能力。
- 规则定义以 `SOUL.md § HC-19（已下线）` 为准。

## 若要复活

需用户明确重新授权，并同步恢复：SOUL.md 条款、`.dsh/skills/medbatch|medmaster|medreview` 阶段与门禁、
`Prompt版本/` 三个提示词条款。只恢复脚本而不恢复规则视为无效。
