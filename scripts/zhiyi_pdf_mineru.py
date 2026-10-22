# -*- coding: utf-8 -*-
"""zhiyi_pdf_mineru.py — 双栏册（2017–2021）MinerU 解析通道。

RapidOCR 的检测器会把双栏页同一行的左右栏并成一条长行，题目与答案区都会被污染，
因此 2017–2021 五册走 MinerU API（版面还原正确）。产物 `<slug>.md` 存
`知识库素材/执业医师真题/_mineru/`，由 `scripts/zhiyi_pdf_parse.py` 自动优先采用。

用法：
  python scripts/zhiyi_pdf_mineru.py            # 处理默认 6 册（已存在则跳过）
  python scripts/zhiyi_pdf_mineru.py --force    # 强制重跑
Token：环境变量 MINERU_TOKEN 或本地文件 知识库素材/执业医师真题/_mineru_token.txt（不入库）。
"""
from __future__ import annotations

import argparse
import io
import sys
import time
import zipfile
from pathlib import Path

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = Path(__file__).resolve().parent.parent
DEFAULT_PDF_DIR = Path(r"C:/Users/38063/Desktop/27网盘/执业医师真题及答案（2010-2023年）")
OUT_DIR = BASE / "知识库素材" / "执业医师真题" / "_mineru"
# token 不入库：读环境变量 MINERU_TOKEN，或本地未跟踪文件 知识库素材/执业医师真题/_mineru_token.txt
LOCAL_TOKEN_FILE = BASE / "知识库素材" / "执业医师真题" / "_mineru_token.txt"


def _load_token() -> str:
    import os

    tok = os.environ.get("MINERU_TOKEN", "").strip()
    if tok:
        return tok
    if LOCAL_TOKEN_FILE.exists():
        tok = LOCAL_TOKEN_FILE.read_text(encoding="utf-8").strip()
        if tok:
            return tok
    raise SystemExit("缺少 MinerU token：请设置环境变量 MINERU_TOKEN，或把 token 写入 "
                     f"{LOCAL_TOKEN_FILE}（该路径已被 .gitignore 忽略）")
DEFAULT_FILES = [
    "2017年临床执业医师考试真题及答案.pdf",
    "2018年临床执业医师考试真题及答案.pdf",
    "2019年临床执业医师考试真题及答案.pdf",
    "2020年临床执业医师考试真题及答案（第一部分）.pdf",
    "2020年临床执业医师考试真题及答案（第二部分）.pdf",
    "2021年临床执业医师考试真题及答案.pdf",
]


def main(argv=None) -> int:
    sys.path.insert(0, str(BASE / "scripts"))
    from zhiyi_pdf_ocr import slugify

    ap = argparse.ArgumentParser(description="双栏册 MinerU 解析（→ _mineru/<slug>.md）")
    ap.add_argument("--pdf-dir", default=str(DEFAULT_PDF_DIR))
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--token", default="")
    args = ap.parse_args(argv)

    token = args.token or _load_token()
    H = {"Authorization": f"Bearer {token}"}
    pdf_dir = Path(args.pdf_dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = []
    for i, n in enumerate(DEFAULT_FILES):
        src = pdf_dir / n
        if not src.exists():
            print("miss", n)
            continue
        dst = out_dir / (slugify(n) + ".md")
        if dst.exists() and not args.force:
            print("skip", dst.name)
            continue
        files.append({"name": slugify(n) + ".pdf", "data_id": f"b{i}", "src": str(src), "dst": dst})
    if not files:
        print("无可处理文件")
        return 0

    r = requests.post("https://mineru.net/api/v4/file-urls/batch", headers=H, json={
        "enable_formula": False, "enable_table": True, "language": "ch",
        "model_version": "pipeline",
        "files": [{"name": f["name"], "data_id": f["data_id"]} for f in files],
    }, timeout=60)
    data = r.json()["data"]
    bid = data["batch_id"]
    for f, u in zip(files, data["file_urls"]):
        with open(f["src"], "rb") as fh:
            resp = requests.put(u, data=fh, timeout=600)
        print("upload", f["name"], resp.status_code)

    result = None
    for _ in range(180):
        time.sleep(10)
        s = requests.get(f"https://mineru.net/api/v4/extract-results/batch/{bid}", headers=H, timeout=30).json()
        res = s["data"]["extract_result"]
        if all(x.get("state") in ("done", "failed") for x in res):
            result = res
            break
    ok = 0
    for x in (result or []):
        print(x.get("data_id"), x.get("state"), x.get("err_msg"))
        if x.get("state") != "done":
            continue
        z = requests.get(x["full_zip_url"], timeout=300)
        md = zipfile.ZipFile(io.BytesIO(z.content)).read("full.md").decode("utf-8")
        dst = out_dir / Path(x["file_name"]).with_suffix(".md").name
        dst.write_text(md, encoding="utf-8")
        print("saved", dst, len(md))
        ok += 1
    print(f"✅ 完成 {ok}/{len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
