# -*- coding: utf-8 -*-
"""answer_recovery.py — 从贺银成解析文本恢复真题答案。

背景：GoldenSet 下册的 `answer` 字段是行首选项前缀（ABCD / ABCDE），不是真实答案。
真实答案常写在解析里，形式包括：
  - 故答 D / 答案为 A / 答案：BC / 故选 C / 应选 E
  - D 对 / B 错 / 故不答 A
  - D 显然符合 / C 是正确的
本模块把「显式答案短语」和「逐项正误」两类证据结合，输出答案 + 置信度。

约束：
  - 只使用标准库；
  - 不猜测：证据不足返回 None；
  - 多字母答案按字母序输出（如 BCA -> ABC）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

LETTERS = "ABCDE"

# 显式答案短语（优先级从高到低）
PHRASE_PATTERNS = [
    re.compile(r"故答\s*([A-E]{1,5})(?![A-E])"),
    re.compile(r"答案为\s*([A-E]{1,5})(?![A-E])"),
    re.compile(r"答案\s*[是为:：]\s*([A-E]{1,5})(?![A-E])"),
    re.compile(r"故选\s*([A-E]{1,5})(?![A-E])"),
    re.compile(r"应选\s*([A-E]{1,5})(?![A-E])"),
    re.compile(r"本题选\s*([A-E]{1,5})(?![A-E])"),
    re.compile(r"正确选项\s*[是为:：]?\s*([A-E]{1,5})(?![A-E])"),
    re.compile(r"正确答案\s*[是为:：]?\s*([A-E]{1,5})(?![A-E])"),
]

# 逐项正误：正向
POSITIVE_PATTERNS = [
    re.compile(r"([A-E])\s*对(?!错)"),
    re.compile(r"([A-E])\s*正确"),
    re.compile(r"([A-E])\s*是正确的"),
    re.compile(r"([A-E])\s*显然符合"),
]

# 逐项正误：负向
NEGATIVE_PATTERNS = [
    re.compile(r"故不答\s*((?:[A-E][、,，和及\s]*){1,5})"),
    # A、B、C、D均不是 / 均错 / 均不正确 / 均不符合
    re.compile(r"((?:[A-E][、,，和及\s]*){1,5})\s*(?:均|都|全部)?\s*(?:不是|错|不正确|不符合)"),
    re.compile(r"([A-E])\s*错(?!误)"),
    re.compile(r"([A-E])\s*不正确"),
    re.compile(r"([A-E])\s*不符合"),
    re.compile(r"([A-E])\s*不是"),
]


@dataclass
class AnswerResult:
    answer: str | None
    confidence: str  # high | medium | low
    evidence: str
    method: str  # phrase | positive_inline | elimination | none


def _allowed_letters(raw_answer: str | None, n_options: int | None) -> set[str]:
    """允许的答案字母集合。

    raw_answer 若是纯前缀（如 ABCD），说明原卷是 4/5 选项，可用来限制范围；
    若不是纯前缀，则按选项数 A..E 限制。
    """
    raw = (raw_answer or "").strip()
    if raw and re.fullmatch(r"[A-E]{1,5}", raw):
        return set(raw)
    if n_options and 1 <= n_options <= 5:
        return set(LETTERS[:n_options])
    return set(LETTERS)


def _normalize(ans: str) -> str:
    return "".join(sorted(set(ans)))


def recover_answer(
    explanation: str,
    raw_answer: str | None = None,
    n_options: int | None = None,
) -> AnswerResult:
    """从解析文本恢复答案。

    优先级：
      1. 显式答案短语（high）
      2. 唯一的正向逐项证据（medium）
      3. 负向逐项证据排除到只剩一个（medium）
      4. 证据不足（none）
    """
    text = explanation or ""
    allowed = _allowed_letters(raw_answer, n_options)

    # 1) 显式答案短语
    for pattern in PHRASE_PATTERNS:
        hits = [m.group(1) for m in pattern.finditer(text)]
        if not hits:
            continue
        for hit in hits:
            ans = _normalize(hit)
            if set(ans) <= allowed and ans:
                return AnswerResult(
                    answer=ans,
                    confidence="high",
                    evidence=pattern.search(text).group(0),
                    method="phrase",
                )

    # 2) 逐项正向证据
    positives: list[str] = []
    for pattern in POSITIVE_PATTERNS:
        for m in pattern.finditer(text):
            letter = m.group(1)
            if letter not in positives:
                positives.append(letter)
    negatives: set[str] = set()
    for pattern in NEGATIVE_PATTERNS:
        for m in pattern.finditer(text):
            negatives.update(ch for ch in m.group(1) if ch in LETTERS)

    positives = [x for x in positives if x in allowed and x not in negatives]
    if len(positives) == 1:
        return AnswerResult(
            answer=positives[0],
            confidence="medium",
            evidence=f"正向逐项证据 {positives[0]}",
            method="positive_inline",
        )

    # 3) 负向排除：allowed 中只剩一个未被否定
    remaining = allowed - negatives
    if len(remaining) == 1:
        only = next(iter(remaining))
        return AnswerResult(
            answer=only,
            confidence="medium",
            evidence=f"排除 {''.join(sorted(negatives))} 后仅剩 {only}",
            method="elimination",
        )

    return AnswerResult(answer=None, confidence="low", evidence="", method="none")
