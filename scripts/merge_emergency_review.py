#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_emergency_review.py — 拼接急诊与灾难医学主复习资料

- 顺序: 00_主头 → 块1 → 块2 → 块3 → 块4 → 00_主尾 → 附录一(自动提取 教材P##) → 附录二(术语表) → 附录三(口诀集)
- 自动统计 callout/details/表格/决策树 数量并写入报告（不写入交付物）
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PARTS = ROOT / "复习资料" / "_parts"
OUT = ROOT / "复习资料" / "急诊与灾难医学_主复习资料.md"

ORDER = [
    "00_主头_导航_谱系.md",
    "块1_绪论_急性中毒_呼吸困难_意识障碍与抽搐.md",
    "块2_休克_环境及理化因素损伤.md",
    "块3_MODS_心肺脑复苏.md",
    "块4_创伤急救_灾难医学_灾难现场医学救援.md",
    "00_主尾_概念地图.md",
]


def read(name: str) -> str:
    p = PARTS / name
    if not p.exists():
        sys.exit(f"[FATAL] 缺少分片文件: {p}")
    t = p.read_text(encoding="utf-8")
    # 去掉分片注释行（<!-- BLOCK_X ... -->）
    t = re.sub(r"^<!--.*?-->\s*\n", "", t, flags=re.M)
    # 去掉分片头尾多余的空行
    return t.strip("\n") + "\n\n"


def extract_appendix1(merged: str) -> str:
    """附录一：从正文提取（教材P##）引用，考点名取最近的前置标题行，按（标题,页码）去重。"""
    lines = merged.split("\n")
    heading = ""
    seen, rows = set(), []
    for ln in lines:
        if re.match(r"^#{2,5}\s", ln):
            heading = re.sub(r"^#{2,5}\s+", "", ln).strip()
            heading = re.sub(r"\*\*|\*|`", "", heading)
            continue
        for m in re.finditer(r"（教材P(\d+)(?:-\d+)?）", ln):
            pg = m.group(1)
            key = (heading, pg)
            if key in seen:
                continue
            seen.add(key)
            rows.append((heading, pg))
    return (
        "## 附录一：教材知识点页码索引（HC-10 · 真实页码）\n\n"
        f"> 页码取自《急诊与灾难医学（第4版）》（人民卫生出版社 2024），对应 {len(rows)} 个（考点·页码）条目，"
        "均由正文引文机器提取，无占位符。\n\n"
        "| 知识点（考点标题） | 教材页码 |\n|--------|:---:|\n"
        + "\n".join(f"| {h[:40]} | P{pg} |" for h, pg in rows)
        + "\n"
    )


def extract_appendix3(merged: str) -> str:
    """附录三：从各模块「💡 记忆口诀」区收集口诀（收集至下一标题/分隔线为止）。"""
    lines = merged.split("\n")
    in_mn = False
    items = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("### 💡 记忆口诀"):
            in_mn = True
            continue
        if in_mn:
            if re.match(r"^#{2,5}\s", s) or re.match(r"^---+\s*$", s):
                in_mn = False
                continue
            if s.startswith("- "):
                items.append(s[2:].strip())
            elif re.match(r"^[0-9]+\.\s", s):
                items.append(re.sub(r"^[0-9]+\.\s+", "", s).strip())
    return (
        "## 附录三：必背记忆口诀汇总\n\n"
        + "\n".join(f"{i}. {it}" for i, it in enumerate(sorted(set(items)), 1))
        + "\n"
    )


def stats(merged: str) -> dict:
    return {
        "模块数": len(re.findall(r"^## 模块\d+：", merged, re.M)),
        "callout": len(re.findall(r"^> \[!(WARNING|TIP|INFO|SUCCESS|NOTE)\]", merged, re.M)),
        "details_open": len(re.findall(r"<details open>", merged)),
        "details_plain(违规)": len(re.findall(r"<details(?![^>]*open)>", merged)),
        "表格数": merged.count("\n|"),
        "决策树(D4)": len(re.findall(r"### 🌳", merged)),
        "因果链(D2)": len(re.findall(r"### 🔗", merged)),
        "行数": len(merged.split("\n")),
        "字符数": len(merged),
    }


def main() -> None:
    parts = [read(n) for n in ORDER]
    merged = "".join(parts)

    app1 = extract_appendix1(merged)
    app2 = (
        "## 附录二：术语同意异名对照表（HC-9）\n\n"
        "| 术语 | 同意异名/缩写 | 说明 |\n|------|--------------|------|\n"
        "| 急救医疗服务体系 | EMSS | 院前急救+医院急诊+危重症监护三位一体 |\n"
        "| 急诊科 | ED | 24 小时开放的首诊场所 |\n"
        "| 危重症监护室 | EICU | 急诊内监护 |\n"
        "| 黄金时间 | 时间窗 | 从致伤/发病起计的救治窗口 |\n"
        "| 全身炎症反应综合征 | SIRS | ≥2 项标准 |\n"
        "| 多器官功能障碍综合征 | MODS | 器官序贯障碍 |\n"
        "| 多器官功能衰竭 | MOF | MODS 终末期 |\n"
        "| 序贯器官衰竭评估 | SOFA | 脓毒症评分基线 |\n"
        "| 格拉斯哥昏迷量表 | GCS | 睁眼/语言/运动 4-5-6 分 |\n"
        "| 基础生命支持 | BLS | CAB 三步骤 |\n"
        "| 高级心血管生命支持 | ACLS | 药物+气道+除颤 |\n"
        "| 自主循环恢复 | ROSC | 复苏成功标志 |\n"
        "| 急性呼吸窘迫综合征 | ARDS | P/F<300 |\n"
        "| 心搏骤停 | CA | 心脏泵血功能骤停 |\n"
        "| 急性肾损伤 | AKI | 少尿/肌酐升标准 |\n"
        "| 乙酰胆碱 | ACh | 胆碱能递质 |\n"
        "| 胆碱酯酶 | ChE | 有机磷靶酶 |\n"
        "| M样症状 | 毒蕈碱样症状 | 副交感亢进 |\n"
        "| N样症状 | 烟碱样症状 | 骨骼肌/神经节 |\n"
        "| 中间型综合征 | IMS | 24-96h 呼吸肌无力 |\n"
        "| 迟发性多发神经病 | OPIDP | 2-3 周 NTE 老化 |\n"
        "| 伤害控制外科 | DCS | 简化手术+复苏 |\n"
        "| 创伤评分 | ISS | 多发伤严重度 |\n"
        "| 大规模伤亡事件 | MCI | 灾害救援场景 |\n"
        "| 突发公共卫生事件 | PHE | Ⅰ-Ⅳ 级响应 |\n"
        "| 检伤分类 | 分拣/分诊 | 四色系统 |\n"
        "| 检伤分类标签 | 伤情卡 | 红黄绿黑四色 |\n"
        "| 高原肺水肿 | HAPE | 急性高原病 |\n"
        "| 高原脑水肿 | HACE | 急性高原病 |\n"
    )
    app3 = extract_appendix3(merged)

    final = merged + "---\n\n" + app1 + "\n---\n\n" + app2 + "\n---\n\n" + app3
    final = re.sub(r"\n{3,}", "\n\n", final).rstrip() + "\n"
    OUT.write_text(final, encoding="utf-8")
    print(f"[OK] 已写 {OUT}")
    for k, v in stats(merged).items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
