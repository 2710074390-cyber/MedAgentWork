# -*- coding: utf-8 -*-
"""check_obsidian 的证伪测试：验证守卫「注入即红、不注入不红」。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_obsidian as C  # noqa: E402

fails = []

def t(name, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {name}  {detail}")
    if not cond:
        fails.append(name)

print("--- A. mask_code 是否真的屏蔽代码区域 ---")
t("行内代码被屏蔽", "图片" not in C.mask_code("用 `![](图片)` 表示相对路径"))
m = C.mask_code("```\n![](不存在.jpg)\n```\n![](真引用.jpg)")
t("围栏内引用被屏蔽", "不存在" not in m)
t("围栏外引用保留", "真引用.jpg" in m)
src = "行1\n```py\ncode here\n```\n行5\n`inline`"
t("mask 保持长度", len(C.mask_code(src)) == len(src), f"{len(src)} -> {len(C.mask_code(src))}")
t("mask 保持行数", C.mask_code(src).count("\n") == src.count("\n"))
t("~~~ 围栏也屏蔽", "x.jpg" not in C.mask_code("~~~\n![](x.jpg)\n~~~"))
t("单行自闭围栏不吞后续内容",
  "真引用.jpg" in C.mask_code("```mermaid ／ graph TD ／ A-->B ／ ```\n![](真引用.jpg)"))

print("--- B. details HTML block 边界判定 ---")
d = C.analyze_details("<details><summary>**粗**</summary>\n\n正常\n\n</details>")
t("标签行内 md 被检出", len(d["md_in_html"]) == 1, str(d["md_in_html"]))
d = C.analyze_details("<details>\n<summary>标题</summary>\n\n**粗体**\n\n</details>")
t("空行之后的 md 不误报", len(d["md_in_html"]) == 0, str(d["md_in_html"]))
d = C.analyze_details("<details>\n<summary>x</summary>\n\n| a | b | ／ | --- | --- |\n\n</details>")
t("压成单行的表格被检出", len(d["flattened"]) == 1, str(d["flattened"]))
d = C.analyze_details("<details>\n<summary>x</summary>\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n</details>")
t("正常三行表格不误报", len(d["flattened"]) == 0, str(d["flattened"]))
t("未加 open 被检出", C.analyze_details("<details>\n<summary>x</summary>\n\n</details>")["no_open"] == 1)
t("加了 open 不误报", C.analyze_details("<details open>\n<summary>x</summary>\n\n</details>")["no_open"] == 0)

print("--- C. 图片链接解析 ---")
vault = Path(__file__).resolve().parent.parent   # 项目根即 vault 根
idx = C.build_image_index(vault)
st, _ = C.resolve_image("绝对不存在的图.jpg", "x.md", vault, idx)
t("不存在的图 -> broken", st == "broken", st)
st, d = C.resolve_image(
    "p01_109d89e63b7dd8acf1d9ea988aa69669902955d2cd5cf2787298ac7416c02b11.jpg",
    "x.md", vault, idx)
t("64位hash文件名 -> ok-byname", st == "ok-byname", f"{st} {d[:50]}")
st, d = C.resolve_image("images/p01_109d89e63b7dd8acf1d9ea988aa69669902955d2cd5cf2787298ac7416c02b11.jpg",
                        "Obsidian产物/讲义上册/01-一、西医综合难考的原因.md", vault, idx)
t("md 同级 images/ -> ok-mdrel", st == "ok-mdrel", st)

print("--- D. vault 排除规则 ---")
filters = C.load_ignore_filters(vault)
t("读到排除规则", len(filters) > 0, f"{len(filters)} 条")
t("_scratch 被识别为排除", C.is_ignored("_scratch/hyc_compile/out/a.md", filters) is not None)
t("大三下 不在排除内", C.is_ignored("大三下/复习资料/a.md", filters) is None)

print()
if fails:
    print(f"✘ {len(fails)} 项失败: {fails}")
    sys.exit(1)
print("✅ 全部证伪测试通过")
