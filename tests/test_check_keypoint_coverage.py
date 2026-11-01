import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_keypoint_coverage.py"


def run_check(tmp_path, sources=(), md=None, keypoints="重点 2周", extra=()):
    kp = tmp_path / "keypoints.txt"
    review = tmp_path / "review.md"
    kp.write_text(keypoints, encoding="utf-8")
    review.write_text(md if md is not None else "2周\n📌 重点原文（第9条）：原文内容", encoding="utf-8")
    command = [sys.executable, str(SCRIPT), "--keypoints", str(kp), "--md", str(review), "--json"]
    command.extend(extra)
    for source in sources:
        command.extend(["--source-text", str(source)])
    proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    output = json.loads(proc.stdout[proc.stdout.index('{'):])
    return proc, output


def test_optional_audit_preserves_legacy_output_and_exit(tmp_path):
    proc, result = run_check(tmp_path)
    assert proc.returncode == 0
    assert result["verdict"] == "PASS"
    assert "source_audit" not in result
    assert "来源审计" not in proc.stdout


def test_audit_matches_separate_sources_without_number_alignment(tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("第88条：精确文字\n另一 段文字", encoding="utf-8")
    second.write_text("拆分", encoding="utf-8")
    md = ("2周\n📌 重点原文（第1条）：精确文字\n"
          "📌 重点原文（第2条）：另一段文字\n"
          "📌 重点原文（第3条）：不存在\n"
          "📌 重点原文（第4条）：文字拆分\n"
          "📌 重点原文（第5条）：")
    proc, result = run_check(tmp_path, [first, second], md)
    audit = result["source_audit"]
    assert proc.returncode == 0
    assert [item["status"] for item in audit["results"]] == [
        "exact", "formatting_only", "not_found", "not_found", "unverified"]
    assert audit["results"][0]["sources"] == [str(first)]
    assert "不判断医学正确性" in proc.stdout
    assert "截取" in proc.stdout


def test_missing_or_empty_source_is_unverified_nonblocking(tmp_path):
    missing = tmp_path / "missing.txt"
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    proc, result = run_check(tmp_path, [missing, empty])
    assert proc.returncode == 0
    assert len(result["source_audit"]["errors"]) == 2
    assert result["source_audit"]["results"][0]["status"] == "unverified"


def test_unreadable_source_does_not_hide_positive_match(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("原文内容", encoding="utf-8")
    proc, result = run_check(tmp_path, [source, tmp_path / "missing"])
    assert proc.returncode == 0
    assert result["source_audit"]["results"][0]["status"] == "exact"


def test_audit_does_not_change_existing_failure(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("原文内容", encoding="utf-8")
    proc, result = run_check(tmp_path, [source], keypoints="重点 3周")
    assert proc.returncode == 1
    assert result["verdict"] == "FAIL"
    assert result["source_audit"]["results"][0]["status"] == "exact"


def adaptive_fixture(tmp_path):
    source = tmp_path / "teacher.txt"
    source.write_text("\n".join(f"{i}. 原文{i}" + (" 2周" if i == 1 else "") for i in range(1, 6)), encoding="utf-8")
    old = "\n".join(f"{i}. 原文{i}" + (" 2周 补充3周" if i == 1 else "") for i in range(1, 6))
    md = "\n".join(f"📌 重点原文（第{i}条）：原文{i}" + (" 2周" if i == 1 else "") for i in range(1, 6))
    return source, old, md


def test_adaptive_separates_original_and_supplement(tmp_path):
    source, old, md = adaptive_fixture(tmp_path)
    proc, result = run_check(tmp_path, [source], md + "\n📚 教材补写（第1条）：3周", old, ["--adaptive"])
    assert proc.returncode == 0
    assert result["verdict"] == "PASS"
    assert "不证明语义完整" in result["scope"]
    assert "不证明语义完整" in proc.stdout


def test_adaptive_rejects_cross_item_and_global_matches(tmp_path):
    source, old, md = adaptive_fixture(tmp_path)
    proc, result = run_check(tmp_path, [source], md + "\n3周\n📚 教材补写（第2条）：3周", old, ["--adaptive"])
    assert proc.returncode == 1
    assert result["partial_facts"] == [[1, "3周"]]


def test_adaptive_original_cannot_be_replaced_or_contaminated(tmp_path):
    source, old, md = adaptive_fixture(tmp_path)
    md = md.replace("原文1 2周", "原文1 3周") + "\n📚 教材补写（第1条）：2周 3周"
    proc, result = run_check(tmp_path, [source], md, old, ["--adaptive"])
    assert proc.returncode == 1
    assert any("原文锚点" in error for error in result["errors"])


def test_adaptive_requires_reliable_source_and_scope(tmp_path):
    source, old, md = adaptive_fixture(tmp_path)
    for sources, keypoints, extra in [([], old, []), ([tmp_path / "missing"], old, []),
                                      ([source], old + "\n\n额外3周", []),
                                      ([source], old, ["--no-anchors"]),
                                      ([source, source], old, [])]:
        proc, result = run_check(tmp_path, sources, md + "\n📚 教材补写（第1条）：3周", keypoints, ["--adaptive", *extra])
        assert proc.returncode == 1
        assert result["errors"]


def test_adaptive_rejects_ambiguous_source_and_old_blocks(tmp_path):
    source, old, md = adaptive_fixture(tmp_path)
    original = source.read_text(encoding="utf-8")
    review = md + "\n📚 教材补写（第1条）：3周"
    for value in [original + "\n\n" + original, original + "\n额外事实 4周",
                  original.replace("2. 原文2", "续行不含数字\n2. 原文2"),
                  original + "\n无数字的附加内容", "# 标题 3周\n" + original]:
        source.write_text(value, encoding="utf-8")
        proc, result = run_check(tmp_path, [source], review, old, ["--adaptive"])
        assert proc.returncode == 1
        assert result["errors"]
    source.write_text(original, encoding="utf-8")
    for value in [old + "\n\n" + old, old.replace("2. 原文2", "续行\n2. 原文2")]:
        proc, result = run_check(tmp_path, [source], review, value, ["--adaptive"])
        assert proc.returncode == 1
        assert result["errors"]


def test_adaptive_allows_titles_and_blank_lines(tmp_path):
    source, old, md = adaptive_fixture(tmp_path)
    source.write_text("# 教师重点\n\n" + source.read_text(encoding="utf-8") + "\n\n## 完", encoding="utf-8")
    proc, _ = run_check(tmp_path, [source], md + "\n📚 教材补写（第1条）：3周", "# 旧清单\n\n" + old, ["--adaptive"])
    assert proc.returncode == 0


def test_adaptive_ignores_hidden_anchors_and_supplements(tmp_path):
    source, old, md = adaptive_fixture(tmp_path)
    anchor = "📌 重点原文（第1条）：原文1 2周"
    supplement = "📚 教材补写（第1条）：3周"
    for wrap in [lambda s: "<!--\n" + s + "\n-->",
                 lambda s: "```markdown\n" + s + "\n```",
                 lambda s: "~~~\n" + s + "\n~~~",
                 lambda s: "    " + s]:
        proc, _ = run_check(tmp_path, [source], md.replace(anchor, wrap(anchor)) + "\n" + supplement, old, ["--adaptive"])
        assert proc.returncode == 1
        proc, result = run_check(tmp_path, [source], md + "\n" + wrap(supplement), old, ["--adaptive"])
        assert proc.returncode == 1
        assert result["partial_facts"] == [[1, "3周"]]
