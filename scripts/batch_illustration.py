#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_illustration.py — MedIllustration 最小脚本闭环（P1-5）

「配图需求清单 → prompt JSON 清单 → （AI 批量出图，人工复检）→ 门禁验收」

用法：
  # 1) 由 v2 需求清单生成批量出图 manifest（覆盖 ①示意 / ②卡通 通道）
  python scripts/batch_illustration.py --out 复习资料/_配图需求/prompt_batch.json

  # 2) 出图后验收：对五科合订本统一跑 GATE-A6 门禁并输出汇总
  python scripts/batch_illustration.py --verify

说明：
  - 本脚本负责「清单行 → prompt JSON」与「门禁」两端；中间的批量出图由 Doubao 图片
    Agent 按 manifest（items[].prompt / golden / ratio / model）逐张生成并人工复检
    （解剖是安全线，人工 Read 复核不可省）。
  - prompt 由 medillustration_config.yaml 的 style.prefix 拼接主体与视觉要点；标注类
    文字（程序标注）不会进入底图 prompt（底图永远无字）。
  - 门禁即 scripts/check_inline_images.py（唯一验收标准，GATE-A6）。
"""
import sys
import io
import re
import json
import argparse
import subprocess
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = Path(__file__).resolve().parent.parent          # MedAgentWork 项目根
V2 = BASE / "复习资料" / "_配图需求" / "大四上复习资料_配图需求清单_v2_三通道打标.md"
GATE = BASE / "scripts" / "check_inline_images.py"
REG = BASE / "复习资料" / "_配图需求" / "存量与占位登记.md"

SUBJECTS = [
    ("内科学教学计划版", "内科学_主复习资料_合订本.md", None),
    ("外科学教学计划版", "外科学（二）_主复习资料.md", "外科学（二）_配图清单.md"),
    ("妇产科学教学计划版", "妇产科学_主复习资料.md", "妇产科学_配图清单.md"),
    ("急诊与灾难医学教学计划版", "急诊与灾难医学_主复习资料.md", None),
    ("耳鼻咽喉头颈外科学教学计划版", "耳鼻咽喉头颈外科学_主复习资料.md", "耳鼻咽喉头颈外科学_配图清单.md"),
]

STYLE = """扁平矢量风格医学科普卡通插画（flat vector medical illustration），柔和平涂色块，统一粗细的深色描边，造型极简概括，纯白色背景，居中单一主视图，构图简洁、四周留白充足；无渐变、无阴影、无照片质感、无纹理；画面中不出现任何文字、字母、数字、箭头、指示线、编号、图例、局部放大图或辅助小图。主体："""

GOLDEN = {
    "解剖": "复习资料/_试点插图/raw/金样_眼球结构_扁平卡通_raw.png",
    "机制": "复习资料/_试点插图/raw/金样_突触机制_扁平卡通_raw.png",
}

# 视觉要求提炼：去掉标注/文字类指令（底图无字，标注走程序）
ANNOT_WORDS = re.compile(r"(程序)?标注|overlay|label|中文|图注|引导线|引线|箭头指示|百分比")


def parse_v2() -> list[dict]:
    """解析 v2 需求清单，返回 ①示意/②卡通 通道的行（含科目与序号）。"""
    lines = V2.read_text(encoding="utf-8").splitlines()
    rows = []
    subject = None
    for line in lines:
        h = re.match(r"^##\s*\d+\.\s*(.+)$", line)
        if h:
            subject = h.group(1).split("张")[0].strip()   # "外科学（二） 20" → "外科学（二）"
            continue
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        seq, title, channel = cells[0], cells[1], cells[2]
        if not seq.isdigit() or not title:
            continue
        if not (channel.startswith("①示意") or channel.startswith("②卡通")):
            continue
        rows.append({
            "subject": subject, "fig_no": seq.zfill(2), "title": title,
            "channel": channel, "note": cells[3] if len(cells) > 3 else "",
        })
    return rows


def build_prompt(row: dict) -> str:
    note = ANNOT_WORDS.sub("", row["note"]).strip("；;，, ")
    body = f"{row['title']}：{note}" if note else row["title"]
    return STYLE + body


def gen_manifest() -> dict:
    rows = parse_v2()
    items = []
    for r in rows:
        kind = "解剖" if r["channel"].startswith("①") else "机制"
        items.append({
            "id": f"{r['subject']}-{r['fig_no']}",
            "subject": r["subject"],
            "fig_no": r["fig_no"],
            "title": r["title"],
            "channel": r["channel"],
            "note": r["note"],
            "prompt": build_prompt(r),
            "model": "seedream_5.0_pro",        # 实际由 medillustration_config.yaml model.default 决定
            "golden_reference": GOLDEN[kind],   # image_edit 参考图（风格锁定）
            "ratio": "1:1",
            "generate_mode": "image_edit" if False else "image_gen",  # 有金样时建议 image_edit
        })
    return {
        "generated": "2026-09-10",
        "source": str(V2),
        "model_source": "medillustration_config.yaml -> model.default",
        "style_prefix": STYLE,
        "count": len(items),
        "items": items,
    }


def run_verify() -> int:
    fails = 0
    print("GATE-A6 五科验收（check_inline_images.py）")
    for subj, md, lst in SUBJECTS:
        args = [sys.executable, str(GATE), "--md", str(BASE / "复习资料" / subj / md)]
        if lst:
            args += ["--list", str(BASE / "复习资料" / subj / lst)]
        cp = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
        tail = [l for l in cp.stdout.splitlines() if l.startswith(("缺失文件", "FAIL"))]
        ok = cp.returncode == 0
        fails += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {subj}: {' | '.join(tail)}")
        if not ok:
            print(cp.stdout)
    print(f"汇总：{'全部通过' if fails == 0 else f'{fails} 科 FAIL'}")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="MedIllustration 最小脚本闭环（清单→prompt→门禁）")
    ap.add_argument("--out", default=str(BASE / "复习资料" / "_配图需求" / "prompt_batch.json"),
                    help="prompt manifest 输出路径")
    ap.add_argument("--verify", action="store_true", help="只跑五科 GATE-A6 门禁验收")
    args = ap.parse_args()

    if args.verify:
        return run_verify()

    if not V2.exists():
        print(f"FAIL 需求清单不存在：{V2}")
        return 1
    manifest = gen_manifest()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    by_chan = {}
    for it in manifest["items"]:
        by_chan[it["channel"]] = by_chan.get(it["channel"], 0) + 1
    print(f"已生成 {out}")
    print(f"共 {manifest['count']} 张（①示意/②卡通）：" + ", ".join(f"{k} {v}" for k, v in sorted(by_chan.items())))
    print("下一步：图片 Agent 按 items[].prompt 逐张出图（金样参考 image_edit）→ 人工复检 → 同名落入 images_webp/ → 运行 --verify。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
