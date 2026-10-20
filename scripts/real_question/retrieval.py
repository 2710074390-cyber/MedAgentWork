# -*- coding: utf-8 -*-
"""retrieval.py — 题目级 BM25 检索、查询构造与 RRF 融合。"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import jieba
from rank_bm25 import BM25Okapi

from .schema import RealQuestion, norm_text

# 医学术语同义词（查询扩展）
SYNONYMS = {
    "心衰": ["心力衰竭", "心功能不全"],
    "心力衰竭": ["心衰", "心功能不全"],
    "心梗": ["心肌梗死", "急性心肌梗死"],
    "心肌梗死": ["心梗", "AMI"],
    "脑梗": ["脑梗死", "缺血性脑卒中"],
    "脑梗死": ["脑梗", "脑血栓形成"],
    "甲亢": ["甲状腺功能亢进", "甲状腺功能亢进症"],
    "甲状腺功能亢进": ["甲亢", "Graves病"],
    "甲减": ["甲状腺功能减退"],
    "慢阻肺": ["慢性阻塞性肺疾病", "COPD"],
    "慢性阻塞性肺疾病": ["慢阻肺", "COPD"],
    "乙肝": ["乙型病毒性肝炎", "HBV"],
    "丙肝": ["丙型病毒性肝炎", "HCV"],
    "SLE": ["系统性红斑狼疮"],
    "系统性红斑狼疮": ["SLE", "狼疮"],
    "类风湿": ["类风湿关节炎", "RA"],
    "BPPV": ["良性阵发性位置性眩晕", "耳石症"],
    "良性阵发性位置性眩晕": ["BPPV", "耳石症"],
    "梅尼埃病": ["美尼尔病", "内淋巴积水"],
    "突发性聋": ["突发性耳聋", "特发性突聋"],
    "突发性耳聋": ["突发性聋"],
    "扁桃体炎": ["扁桃体"],
    "鼻窦炎": ["鼻窦"],
    "中耳炎": ["中耳"],
    "青光眼": ["眼压升高"],
    "白内障": ["晶状体混浊"],
    "异位妊娠": ["宫外孕"],
    "子宫肌瘤": ["肌瘤"],
    "糖尿病": ["DM", "高血糖"],
    "高血压": ["血压升高"],
    "休克": ["循环衰竭"],
    "CPR": ["心肺复苏"],
    "COPD": ["慢性阻塞性肺疾病"],
}

STOPWORDS = {
    "的", "了", "是", "在", "和", "与", "及", "或", "其", "为", "对", "从", "中",
    "可", "能", "有", "无", "不", "均", "应", "需", "并", "且", "等", "下列",
    "关于", "主要", "常见", "表现", "特点", "原则", "方法", "检查", "治疗",
}

DIMENSIONS = [
    "诊断", "鉴别诊断", "临床表现", "辅助检查", "实验室检查", "影像学",
    "治疗", "治疗原则", "首选治疗", "手术", "适应证", "禁忌证", "并发症",
    "病因", "发病机制", "病理", "分型", "分期", "分级", "预后", "预防",
]


def tokenize(text: str) -> list[str]:
    tokens = []
    for tok in jieba.lcut_for_search(text or ""):
        tok = tok.strip().lower()
        if not tok or tok in STOPWORDS:
            continue
        if re.fullmatch(r"[\W_]+", tok):
            continue
        if len(tok) == 1 and not tok.isdigit() and not re.match(r"[a-z]", tok):
            continue
        tokens.append(tok)
    return tokens


def expand_query(text: str) -> list[str]:
    """返回查询变体：原文 + 同义词扩展。"""
    variants = [text]
    extra = []
    for term, syns in SYNONYMS.items():
        if term.lower() in text.lower():
            extra.extend(s for s in syns if s.lower() not in text.lower())
    if extra:
        variants.append(text + " " + " ".join(dict.fromkeys(extra)))
    return variants


@dataclass
class KeyPoint:
    ref: str
    text: str
    weight: float = 1.0


def parse_keypoints(path: str | Path) -> list[KeyPoint]:
    """解析 HC-20 锚定清单。

    优先解析「## 四、统一锚定清单」下的 `N. 【源…】正文〔源…〕` 行；
    若没有该节，则解析全文 `第N条：...` 或 `N. ...` 行。
    """
    path = Path(path)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("## 四") or "统一锚定清单" in line:
            start = i
            break
    out: list[KeyPoint] = []
    seen: set[str] = set()
    for line in lines[start:]:
        s = line.strip()
        m = re.match(r"^(\d+)\.\s+(.+)$", s)
        if not m:
            m = re.match(r"^第\s*(\d+)\s*条\s*[：:]\s*(.+)$", s)
        if not m:
            continue
        ref = f"第{m.group(1)}条"
        text = m.group(2).strip()
        if ref in seen or not text:
            continue
        text = re.sub(r"〔[^〕]*〕", "", text).strip()
        text = re.sub(r"【[^】]*】", "", text).strip()
        if not text:
            continue
        seen.add(ref)
        weight = 1.0
        out.append(KeyPoint(ref=ref, text=text, weight=weight))
    return out


def keypoint_queries(kp: KeyPoint) -> list[str]:
    """为单个考点生成 2–4 条查询。"""
    text = kp.text
    queries = [text]
    # 去掉页码/括号/来源标记，保留名词短语
    cleaned = re.sub(r"（[^）]*P\d{2,3}[^）]*）|\([^)]*P\d{2,3}[^)]*\)", " ", text)
    cleaned = re.sub(r"[（(][^）)]{0,20}[）)]", " ", cleaned)
    cleaned = re.sub(r"〔[^〕]*〕|【[^】]*】", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned and cleaned != text:
        queries.append(cleaned)
    # 疾病/操作 + 维度
    dims = [d for d in DIMENSIONS if d in text]
    if dims:
        queries.append(" ".join(dims[:3]))
    # 同义词变体
    for q in list(queries):
        queries.extend(expand_query(q))
    # 去重 + 长度限制
    out: list[str] = []
    for q in queries:
        q = q.strip()
        if q and q not in out:
            out.append(q)
    return out[:6]


class ItemRetriever:
    def __init__(self, items: Iterable[RealQuestion]):
        self.items = [x for x in items if x.selectable]
        self.corpus_tokens = [tokenize(self._doc_text(x)) for x in self.items]
        self.bm25 = BM25Okapi(self.corpus_tokens) if self.corpus_tokens else None

    @staticmethod
    def _doc_text(item: RealQuestion) -> str:
        return " ".join([
            item.stem,
            " ".join(item.options),
            item.explanation[:800],
            " ".join(item.keypoints),
        ])

    @staticmethod
    def _matches_subject(item: RealQuestion, subject: str | None) -> bool:
        if not subject:
            return True
        # 严格相等：避免「耳鼻咽喉头颈外科学」被「外科学」子串命中
        aliases = set(item.subject_aliases or [])
        return item.subject == subject or subject in aliases or item.department == subject

    def search(
        self,
        query: str,
        top_k: int = 50,
        subject: str | None = None,
        source: str | None = None,
        question_types: set[str] | None = None,
    ) -> list[tuple[float, RealQuestion]]:
        if not self.bm25 or not query.strip():
            return []
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self.bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: -x[1])
        out: list[tuple[float, RealQuestion]] = []
        for idx, score in ranked:
            item = self.items[idx]
            if score <= 0:
                break
            if not self._matches_subject(item, subject):
                continue
            if source and item.source != source:
                continue
            if question_types and item.question_type and item.question_type not in question_types:
                continue
            out.append((float(score), item))
            if len(out) >= top_k:
                break
        return out

    def search_multi(
        self,
        queries: list[str],
        top_k: int = 50,
        subject: str | None = None,
        source: str | None = None,
        question_types: set[str] | None = None,
        rrf_k: int = 60,
    ) -> list[tuple[float, RealQuestion, list[str]]]:
        """多查询召回 + RRF 融合。"""
        fused: dict[str, float] = {}
        by_id: dict[str, RealQuestion] = {}
        matched: dict[str, list[str]] = {}
        for q in queries:
            for rank, (_, item) in enumerate(
                self.search(q, top_k=top_k, subject=subject, source=source, question_types=question_types),
                start=1,
            ):
                key = item.item_id
                fused[key] = fused.get(key, 0.0) + 1.0 / (rrf_k + rank)
                by_id[key] = item
                matched.setdefault(key, []).append(q)
        return [
            (score, by_id[key], matched[key])
            for key, score in sorted(fused.items(), key=lambda x: -x[1])[:top_k]
        ]


def year_bonus(year: int | None) -> float:
    if not year:
        return 0.0
    # 近 5 年略加权，避免只选老题
    return max(0.0, (year - 2000) / 1000.0)


def answer_bonus(confidence: str) -> float:
    return {"high": 0.08, "medium": 0.03}.get(confidence, 0.0)


GENERIC_QUERY_TERMS = STOPWORDS | set(DIMENSIONS) | {
    "患者", "男性", "女性", "下列", "哪项", "叙述", "正确", "错误", "不包括",
    "属于", "主要", "最常见", "首选", "可能", "首先", "最", "应", "可", "包括",
    "发生", "出现", "引起", "导致", "有关", "相关", "特点", "表现",
}


def keypoint_relevance(item: RealQuestion, kp_text: str) -> float:
    """考点相关性闸门：至少 2 个共享实词，或 1 个 ≥4 字实词。

    用于过滤 BM25 的泛化误命中（例如用「耳」匹配到「耳毒性药物」）。
    """
    kp_tokens = {
        t for t in tokenize(kp_text)
        if t not in GENERIC_QUERY_TERMS and len(t) >= 2
    }
    if not kp_tokens:
        return 0.0
    doc = item.stem + " " + " ".join(item.options)
    doc_tokens = set(tokenize(doc))
    doc_norm = norm_text(doc)
    hits = {t for t in kp_tokens if t in doc_tokens or t in doc_norm}
    if not hits:
        return 0.0
    if len(hits) < 2 and not any(len(t) >= 4 for t in hits):
        return 0.0
    # 归一化：命中数 / min(考点实词数, 8)
    return min(1.0, len(hits) / max(1, min(len(kp_tokens), 8)))


def exact_keypoint_bonus(item: RealQuestion, kp_text: str) -> float:
    doc = norm_text(item.stem + " " + " ".join(item.options))
    kp = norm_text(kp_text)
    if not doc or not kp:
        return 0.0
    # 取考点文本中的连续 4 字片段，命中越多加分越高
    grams = [kp[i:i + 4] for i in range(0, max(1, len(kp) - 3), 2)]
    if not grams:
        return 0.0
    hit = sum(1 for g in grams if g and g in doc)
    return min(0.25, hit / max(1, len(grams)) * 0.25)
