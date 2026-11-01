# -*- coding: utf-8 -*-
"""分片合并器测试：合并必须成单一文件且附录不得丢失（D6.8）。"""
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

CARD = """#### 🔴 K-M01-001｜示例考点（教师重点第1条｜P1）

📌 重点原文（第1条）：示例原文。
<b>🎯 定位</b>：示例。
<b>🔄 自测</b>：①问题？（答案见附录五）
"""


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _build_fixture(root: Path) -> tuple[Path, Path, Path]:
    shards = root / "shards"
    _write(shards / "head.md", "# 示例科目 · 教师重点版\n\n> 说明\n")
    _write(shards / "M01.md", "## 模块1：总论\n\n" + CARD)
    _write(shards / "M02.md", "## 模块2：复苏\n\n" + CARD.replace("M01", "M02"))
    _write(shards / "answers" / "M01.md", "| 1 | 示例答案 | K-M01-001 |")
    _write(shards / "answers" / "M02.md", "| 1 | 示例答案 | K-M02-001 |")
    appendix = root / "appendix.md"
    _write(appendix, "# 附录\n\n## 附录一 页码索引\n\n| 模块 | 页 |\n|---|---|\n| M01 | P1 |\n\n"
                     "## 附录二 术语\n\n| 名 | 注 |\n|---|---|\n| A | B |\n\n"
                     "## 附录五 主动回忆答案\n\n- 旧格式\n")
    out = root / "out" / "主复习资料.md"
    return shards, appendix, out


def test_merge_produces_single_file_with_appendices():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        shards, appendix, out = _build_fixture(root)
        r = subprocess.run(
            [sys.executable, "scripts/merge_review_shards.py",
             "--shards", str(shards), "--appendix", str(appendix), "--out", str(out)],
            cwd=BASE, capture_output=True, text=True, encoding="utf-8",
        )
        assert r.returncode == 0, r.stderr
        text = out.read_text(encoding="utf-8")
        assert len([ln for ln in text.splitlines() if ln.startswith("# ")]) == 1
        assert "## 附录一 页码索引" in text and "## 附录二 术语" in text
        assert text.count("## 附录五：主动回忆答案") == 1
        assert "| 1 | 示例答案 | K-M01-001 |" in text
        assert "## 模块1：总论" in text and "## 模块2：复苏" in text


def test_merge_rejects_missing_module_heading():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        shards, appendix, out = _build_fixture(root)
        _write(shards / "M02.md", "缺少标题的正文\n")
        r = subprocess.run(
            [sys.executable, "scripts/merge_review_shards.py",
             "--shards", str(shards), "--appendix", str(appendix), "--out", str(out)],
            cwd=BASE, capture_output=True, text=True, encoding="utf-8",
        )
        assert r.returncode == 1
        assert "缺少" in r.stderr


def test_adaptive_preserves_content_and_order():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        shards = root / "shards"
        _write(shards / "head.md", "# 总标题\n")
        _write(shards / "M01.md", "## 第一章\n\n第一章正文\n")
        _write(shards / "M02.md", "## 第二章\n\n第二章正文\n")
        appendix = root / "appendix.md"
        _write(appendix, "## 自定义附录\n\n附录正文\n")
        _write(shards / "answers" / "M01.md", "答案内容\n")
        out = root / "out.md"
        r = subprocess.run([sys.executable, "scripts/merge_review_shards.py", "--mode", "adaptive",
                            "--shards", str(shards), "--appendix", str(appendix), "--out", str(out)],
                           cwd=BASE, capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr
        text = out.read_text(encoding="utf-8")
        items = ["# 总标题", "第一章正文", "第二章正文", "附录正文", "答案内容"]
        assert [text.index(item) for item in items] == sorted(text.index(item) for item in items)


def test_adaptive_rejects_invalid_inputs_without_overwriting():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        shards = root / "shards"
        _write(shards / "head.md", "# 标题\n")
        _write(shards / "M01.md", "## 第一章\n\n正文\n")
        out = root / "out.md"
        _write(out, "原有内容")
        cmd = [sys.executable, "scripts/merge_review_shards.py", "--mode", "adaptive",
               "--shards", str(shards), "--out", str(out)]
        for extra in (["--expect-modules", "2"], ["--appendix", str(root / "missing.md")]):
            r = subprocess.run(cmd + extra, cwd=BASE, capture_output=True, text=True, encoding="utf-8")
            assert r.returncode == 1
            assert out.read_text(encoding="utf-8") == "原有内容"
        _write(shards / "M01.md", "## 只有标题\n")
        r = subprocess.run(cmd, cwd=BASE, capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 1
        assert out.read_text(encoding="utf-8") == "原有内容"
        _write(shards / "M01.md", "# 第二个标题\n正文\n")
        r = subprocess.run(cmd, cwd=BASE, capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 1
        assert out.read_text(encoding="utf-8") == "原有内容"
