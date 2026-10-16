"""check_obsidian 的证伪测试：验证守卫「注入即红、不注入不红」。

⚠️ 本文件是**脚本式**证伪测试：直接跑断言，失败时 `sys.exit(1)`。
2026-10-16 修：原实现把执行体摊在模块顶层，`sys.exit` 发生在 **import 期** ⇒ pytest
收集阶段直接 INTERNALERROR（`0 tests ran`），把 CI 的 `Run tests` 整步炸掉——而该步骤
此前从未执行过（lint 一挂就中断），所以这个坑一直没被发现。
现把执行体收进 `main()` 并加 `__main__` 守卫：直接 `python tests/test_check_obsidian.py`
照旧可用，pytest 只导入、不执行，收集面不再被污染。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_obsidian as C  # noqa: E402


def main() -> int:
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
    # 机制判据，而不是数据判据：原先断言「_scratch 必须被当前 vault 排除」，那是在断言
    # vault 的 userIgnoreFilters（**会变的数据**）——2026-10-16 实测那份清单 68 条里已无
    # _scratch 规则，脚本因此假红。is_ignored 的语义（前缀命中 / 未命中返回 None）与
    # vault 当前配置无关，才是该测的东西。
    t("命中排除规则 -> 返回命中的规则", C.is_ignored("_scratch/x/a.md", ["_scratch/"]) == "_scratch/")
    t("未命中 -> None", C.is_ignored("大三下/复习资料/a.md", ["_scratch/"]) is None)
    # 现状只观察不断言：本机 vault 到底有没有排除 _scratch，是用户自己的配置选择
    print(f"  INFO  当前 vault 是否排除 _scratch："
          f"{'是' if C.is_ignored('_scratch/hyc_compile/out/a.md', filters) else '否'}")
    t("大三下 不在排除内", C.is_ignored("大三下/复习资料/a.md", filters) is None)

    print("--- E. wikilink 歧义检查（F6） ---")
    md_idx = C.build_md_index(vault)
    dup = {k: v for k, v in md_idx.items() if len(v) > 1}
    t("md 索引构建成功", len(md_idx) > 0, f"{len(md_idx)} 个唯一名")
    # 注意：vault 里存在同名 md 是常态（如多个 README.md），
    # 只有当它们被 wikilink 引用时才会造成歧义 —— 所以这里只报告，不做断言。
    # 真正的歧义检查由 F6 在被检查文件里逐个 wikilink 判定。
    print(f"  INFO  当前 vault 有 {len(dup)} 组同名 md（未被引用则无害）：{list(dup)[:4]}")
    # 注入一个必然歧义的场景，确认 F6 真的会红
    fake_idx = {"某同名文件.md": ["a/某同名文件.md", "b/某同名文件.md"],
                "唯一文件.md": ["c/唯一文件.md"]}
    findings, _ = C.check_file(Path("x.md"), vault, {}, [], "见 [[某同名文件]] 与 [[唯一文件]]\n",
                               fake_idx)
    codes = [f.code for f in findings]
    t("F6 能检出歧义（注入即红）", "F6" in codes, str(codes))

    print()
    if fails:
        print(f"✘ {len(fails)} 项失败: {fails}")
        return 1
    print("✅ 全部证伪测试通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
