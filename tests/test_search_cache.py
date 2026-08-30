"""search_kb.py 检索缓存层 单元测试（pytest 兼容，纯 assert，零 API 调用）。

覆盖 2026-08-20 成本优化:
  1. embed 缓存命中 → 不触发 API 调用
  2. 检索结果缓存读写 + 参数区分（不同 subject/参数 → 不同 key）
  3. --no-rerank 降级模式参数传递（search 签名兼容）

运行: python scripts/run_tests.py  或  python -m pytest tests/ -q
"""
import sys
import tempfile
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / 'scripts'))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    'search_kb', BASE / '知识库素材' / 'search_kb.py')
search_kb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(search_kb)


def _use_tmp_cache(tmp):
    """把缓存目录重定向到临时目录（不污染真实 知识库素材/cache/）。"""
    search_kb.CACHE_DIR = Path(tmp) / 'cache'
    search_kb.CACHE_ENABLED = True
    search_kb.CACHE_EMBED = True


def test_embed_cache_hit_skips_api():
    """embed 命中缓存 → 返回向量且不调用 api_request。"""
    with tempfile.TemporaryDirectory() as tmp:
        _use_tmp_cache(tmp)
        # 预写缓存（模拟首次调用已落盘）
        vec = [0.1, 0.2, 0.3] * 8
        search_kb._cache_write(["embed", search_kb.EMBED_MODEL, "心衰治疗"],
                               {"embedding": vec})
        # api_key=None → 若触发 API 必然抛错；命中缓存则安全返回
        out = search_kb.embed_query("心衰治疗", None)
        assert isinstance(out, np.ndarray)
        assert out.shape == (24,)
        assert abs(float(out[0]) - 0.1) < 1e-6


def test_embed_cache_key_differs_by_query():
    with tempfile.TemporaryDirectory() as tmp:
        _use_tmp_cache(tmp)
        k1 = search_kb._cache_key(["embed", search_kb.EMBED_MODEL, "心衰"])
        k2 = search_kb._cache_key(["embed", search_kb.EMBED_MODEL, "肺癌"])
        assert k1 != k2


def test_search_result_cache_roundtrip():
    """检索结果缓存：写入后可读回，且 subject/参数 不同则 key 不同。"""
    with tempfile.TemporaryDirectory() as tmp:
        _use_tmp_cache(tmp)
        parts_a = ["search", "internal-med", "心衰", 20, 5, 0.7, True, 0.3, False, "sig1"]
        parts_b = ["search", "surgery", "心衰", 20, 5, 0.7, True, 0.3, False, "sig1"]
        data = {"query": "心衰", "results": [{"score": 0.9, "text": "x"}], "cached": True}
        search_kb._cache_write(parts_a, data)
        got = search_kb._cache_read(parts_a)
        assert got is not None and got["results"][0]["score"] == 0.9
        # 不同 subject → 未命中
        assert search_kb._cache_read(parts_b) is None


def test_cache_disabled_no_read():
    """--no-cache 关闭后：缓存不读不写。"""
    with tempfile.TemporaryDirectory() as tmp:
        _use_tmp_cache(tmp)
        search_kb._cache_write(["embed", "m", "q"], {"embedding": [1.0]})
        search_kb.CACHE_ENABLED = False
        assert search_kb._cache_read(["embed", "m", "q"]) is None
        search_kb.CACHE_ENABLED = True


def test_no_rerank_search_signature():
    """search() 接受 no_rerank 参数（降级模式签名兼容，不破坏旧调用）。"""
    import inspect
    sig = inspect.signature(search_kb.search)
    assert 'no_rerank' in sig.parameters
    assert sig.parameters['no_rerank'].default is False
