# -*- coding: utf-8 -*-
"""schema.py — 统一真题记录、去重与 JSONL 读写。"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

LETTERS = "ABCDE"

# 公开构建允许的 license 值。用户已确认：非商业个人刷题、原题公开。
PUBLIC_LICENSES = {"public", "public_noncommercial"}
INTERNAL_LICENSES = {"internal_only", "research_only"}


@dataclass
class RealQuestion:
    item_id: str
    source: str                     # kaoyan | zhiyi | licensed | original
    source_id: str
    exam: str                       # 306西综 | 执业医师 | ...
    year: int | None
    question_no: int | None
    subject: str
    subject_aliases: list[str] = field(default_factory=list)
    department: str = ""
    module: str = ""
    chapter: str = ""
    keypoints: list[str] = field(default_factory=list)
    teacher_keypoint_refs: list[str] = field(default_factory=list)
    stem: str = ""
    options: list[str] = field(default_factory=list)
    answer: str = ""
    explanation: str = ""
    question_type: str = ""
    bloom: str = ""
    difficulty_p: float | None = None
    answer_confidence: str = "low"  # high | medium | low
    answer_evidence: str = ""
    license: str = "unknown"
    license_note: str = ""
    dedup_hash: str = ""
    simhash: int = 0
    selectable: bool = True
    quality_flags: list[str] = field(default_factory=list)
    source_file: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RealQuestion":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def norm_text(text: str) -> str:
    """规范化文本：去空白/标点/LaTeX 残留，用于哈希与匹配。"""
    if not isinstance(text, str):
        return ""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"[\\$\\^_{}()（）\[\]【】·:,，。、；;：！？!?\s\"'“”‘’—\-]", "", text)
    return text.lower()


def exact_hash(stem: str, options: Iterable[str] | None = None) -> str:
    text = norm_text(stem) + "|" + "|".join(norm_text(o) for o in (options or []))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _char_ngrams(text: str, n: int = 3) -> list[str]:
    text = norm_text(text)
    if len(text) <= n:
        return [text] if text else []
    return [text[i:i + n] for i in range(len(text) - n + 1)]


def simhash64(text: str) -> int:
    """64 位 SimHash（字符 3-gram，标准库实现）。"""
    weights = [0] * 64
    for gram in _char_ngrams(text, 3):
        h = int(hashlib.md5(gram.encode("utf-8")).hexdigest()[:16], 16)
        for i in range(64):
            weights[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(64):
        if weights[i] > 0:
            out |= (1 << i)
    return out


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def prepare_item(item: RealQuestion) -> RealQuestion:
    """补齐哈希、可选择性、答案合法性。"""
    item.stem = (item.stem or "").strip()
    item.options = [str(o).strip() for o in (item.options or []) if str(o).strip()]
    item.answer = (item.answer or "").strip().upper()
    item.keypoints = [k.strip() for k in (item.keypoints or []) if k and k.strip()]
    item.teacher_keypoint_refs = [k.strip() for k in (item.teacher_keypoint_refs or []) if k and k.strip()]
    item.dedup_hash = item.dedup_hash or exact_hash(item.stem, item.options)
    item.simhash = item.simhash or simhash64(item.stem + " " + " ".join(item.options))

    if not item.stem or not item.options:
        item.selectable = False
        item.quality_flags.append("missing_stem_or_options")
    if len(item.options) > 5:
        item.selectable = False
        item.quality_flags.append("too_many_options")
    if any(re.match(r"^\s*\d{1,3}\s*[\.、]", o) for o in item.options):
        item.selectable = False
        item.quality_flags.append("option_contains_next_question")
    if not item.answer:
        item.selectable = False
        item.quality_flags.append("missing_answer")
    elif any(ch not in LETTERS for ch in item.answer):
        item.selectable = False
        item.quality_flags.append("invalid_answer_letters")
    elif item.options and max(ord(ch) - 64 for ch in item.answer) > len(item.options):
        item.selectable = False
        item.quality_flags.append("answer_out_of_option_range")
    if item.answer_confidence not in {"high", "medium"}:
        item.selectable = False
        item.quality_flags.append("low_answer_confidence")
    return item


def dedupe_items(items: Iterable[RealQuestion], max_hamming: int = 3) -> tuple[list[RealQuestion], int]:
    """精确 + SimHash 近重复去重。

    保留优先级：source=kaoyan > zhiyi test（有标签）> zhiyi train；
    同来源时 answer_confidence=high 优先。
    """
    def _priority(x: RealQuestion) -> int:
        if x.source == "kaoyan":
            return 0
        if x.source_file == "CMExam-test":
            return 1
        return 2

    ordered = sorted(
        items,
        key=lambda x: (
            _priority(x),
            0 if x.answer_confidence == "high" else 1,
            -(x.year or 0),
        ),
    )
    kept: list[RealQuestion] = []
    hashes: set[str] = set()
    # SimHash LSH：4 个 16 位 band，避免 5 万题两两比较
    band_buckets: list[dict[int, list[int]]] = [{} for _ in range(4)]
    removed = 0
    for item in ordered:
        if item.dedup_hash in hashes:
            removed += 1
            continue
        candidates: set[int] = set()
        for band in range(4):
            key = (item.simhash >> (band * 16)) & 0xFFFF
            candidates.update(band_buckets[band].get(key, []))
        if any(hamming(item.simhash, kept[i].simhash) <= max_hamming for i in candidates):
            removed += 1
            continue
        hashes.add(item.dedup_hash)
        idx = len(kept)
        kept.append(item)
        for band in range(4):
            key = (item.simhash >> (band * 16)) & 0xFFFF
            band_buckets[band].setdefault(key, []).append(idx)
    return kept, removed


def write_jsonl(path: Path, items: Iterable[RealQuestion]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")
            n += 1
    return n


def read_jsonl(path: Path) -> list[RealQuestion]:
    out: list[RealQuestion] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(RealQuestion.from_dict(json.loads(line)))
    return out
