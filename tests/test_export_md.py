"""export-md / rehome / 归档感知 单元测试（pytest 兼容，纯 assert）。

覆盖 2026-08-20 改进:
  1. export-md: 题库 JSON → 可读 Markdown（✅ 答案标记/判断题原文答案/模块分组）
  2. rehome: 归档后失效注册路径重写为 archive/ 实际位置
  3. check 归档感知: 文件已归档时完整性检查不误报

运行: python scripts/run_tests.py  或  python -m pytest tests/ -q
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / 'scripts'))
sys.path.insert(0, str(BASE))  # gate_check.py 在根目录
import qbank


def _mk(tmp, name, questions):
    p = Path(tmp) / name
    p.write_text(json.dumps(questions, ensure_ascii=False), encoding='utf-8')
    return p


# ── export-md ──

def test_export_md_basic_format():
    with tempfile.TemporaryDirectory() as tmp:
        questions = [
            {'id': 'T1', 'module': 'M1', 'type': 'A1', 'bloom_level': '记忆',
             'stem': '语音震颤增强最常见于？',
             'options': [{'label': 'A', 'text': '胸腔积液'}, {'label': 'B', 'text': '气胸'},
                         {'label': 'C', 'text': '肺实变'}, {'label': 'D', 'text': '肺水肿'},
                         {'label': 'E', 'text': '肺不张'}],
             'answer': 'C', 'explanation': '实变传导增强。', 'source_pages': 'P20'},
            {'id': 'T2', 'module': 'M2', 'type': '判断', 'bloom_level': '理解',
             'stem': 'COPD 属于阻塞性通气障碍。',
             'options': {}, 'answer': '正确', 'explanation': '正确。'},
        ]
        src = _mk(tmp, 'q.json', questions)
        out = str(Path(tmp) / 'q.md')
        outpath, n = qbank.export_md(str(src), out, title='测试题库')
        assert n == 2
        md = Path(outpath).read_text(encoding='utf-8')
        # 头部统计
        assert '测试题库' in md and '（2题）' in md
        assert 'A1×1' in md and '判断×1' in md
        # 模块分组
        assert '## M1（1题）' in md and '## M2（1题）' in md
        # 题干/选项/✅答案标记
        assert '**语音震颤增强最常见于？**' in md
        assert '**C. 肺实变** ✅' in md
        assert '- A. 胸腔积液' in md
        assert '**答案：C**' in md
        # 判断题保留原文答案（非字母）
        assert '**答案：正确**' in md
        assert '> 解析：实变传导增强。' in md
        # 页码
        assert '页码：P20' in md


def test_export_md_non_bank_file():
    with tempfile.TemporaryDirectory() as tmp:
        p = _mk(tmp, 'notbank.json', {'report_metadata': {}})
        out, n = qbank.export_md(str(p))
        assert out is None and n == 0


# ── rehome / 归档感知 ──

def _mk_question(tmp, rel):
    """在 tmp 下创建题库文件（相对路径 rel），返回 Path。"""
    p = Path(tmp) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([{'stem': '题A', 'options': {'A': 'a', 'B': 'b'}, 'answer': 'A'}]),
                 encoding='utf-8')
    return p


def _archive_it(tmp, rel):
    """把 tmp/rel 移入 tmp/archive/rel（模拟学期切换归档）。"""
    src = Path(tmp) / rel
    dst = Path(tmp) / 'archive' / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))


def test_check_archive_aware():
    """check() 对已归档文件不误报缺失（resolve_entry_path 回退 archive/）。"""
    with tempfile.TemporaryDirectory() as tmp:
        qbank._set_registry_base(tmp)
        try:
            qbank.init_registry_for_test()
            rel = '中间产物/batchT/ALL_questions.json'
            p = _mk_question(tmp, rel)
            qbank.register_file(p, 'batchT')   # 注册时文件在原位
            _archive_it(tmp, rel)              # 随后归档
            issues, warns, infos = qbank.check()
            assert not any('注册文件不存在' in i for i in issues)
        finally:
            qbank._set_registry_base(None)


def test_rehome_rewrites_path():
    """rehome() 将失效路径重写为 archive/ 实际位置。"""
    with tempfile.TemporaryDirectory() as tmp:
        qbank._set_registry_base(tmp)
        try:
            qbank.init_registry_for_test()
            rel = '中间产物/batchT/ALL_questions.json'
            p = _mk_question(tmp, rel)
            qbank.register_file(p, 'batchT')
            _archive_it(tmp, rel)
            rewritten, missing = qbank.rehome()
            assert rewritten == 1 and missing == 0
            entries = [json.loads(l) for l in
                       (Path(tmp) / 'question_bank' / 'registry.jsonl').read_text(encoding='utf-8').splitlines()
                       if l.strip()]
            assert 'archive' in entries[0]['file']
            # 重写后 check 通过
            issues, _, _ = qbank.check()
            assert not any('注册文件不存在' in i for i in issues)
        finally:
            qbank._set_registry_base(None)


def test_rehome_dry_run_no_write():
    with tempfile.TemporaryDirectory() as tmp:
        qbank._set_registry_base(tmp)
        try:
            qbank.init_registry_for_test()
            rel = '中间产物/batchT/ALL_questions.json'
            p = _mk_question(tmp, rel)
            qbank.register_file(p, 'batchT')
            _archive_it(tmp, rel)
            rewritten, _ = qbank.rehome(dry_run=True)
            assert rewritten == 1
            entries = [json.loads(l) for l in
                       (Path(tmp) / 'question_bank' / 'registry.jsonl').read_text(encoding='utf-8').splitlines()
                       if l.strip()]
            assert 'archive' not in entries[0]['file']  # 未写入
        finally:
            qbank._set_registry_base(None)


# ── GATE-A4-MD（gate_check.py 最终交付 MD 门禁）──

def test_gate_a4_md_blocks_without_md():
    """GATE-A4: JSON 存在但 MD 缺失 → BLOCKED（GATE-A4-MD 子项）。"""
    import gate_check
    with tempfile.TemporaryDirectory() as tmp:
        orig_base = gate_check.BASE
        gate_check.BASE = Path(tmp)
        try:
            final_dir = Path(tmp) / '最终产物' / 'batchMDT'
            final_dir.mkdir(parents=True, exist_ok=True)
            (final_dir / 'AGENT4_追溯日志.json').write_text(
                json.dumps([{'patch': 'x', 'source_file_synced': True}], ensure_ascii=False),
                encoding='utf-8')
            (final_dir / 'ALL_questions_FIXED.json').write_text(
                json.dumps([{'id': 'T1', 'module': 'M1', 'type': 'A1', 'stem': '测试题',
                             'options': [{'label': 'A', 'text': 'a'}, {'label': 'B', 'text': 'b'}],
                             'answer': 'A'}], ensure_ascii=False),
                encoding='utf-8')
            batch_data = {'steps': {'AGENT4': {'output': 'AGENT4_追溯日志.json', 'trace_log': 'y'}},
                          'status': 'IN_PROGRESS'}
            r = gate_check.gate_agent4('batchMDT', batch_data)
            assert r['status'] == 'BLOCKED'
            assert any(g.get('gate_sub') == 'GATE-A4-MD' for g in r.get('sub_gates', []))
        finally:
            gate_check.BASE = orig_base


def test_gate_a4_md_passes_with_md():
    """GATE-A4: JSON + MD 齐全且含 ✅ 答案标记 → PASS。"""
    import gate_check
    with tempfile.TemporaryDirectory() as tmp:
        orig_base = gate_check.BASE
        gate_check.BASE = Path(tmp)
        try:
            final_dir = Path(tmp) / '最终产物' / 'batchMDT'
            final_dir.mkdir(parents=True, exist_ok=True)
            (final_dir / 'AGENT4_追溯日志.json').write_text(
                json.dumps([{'patch': 'x', 'source_file_synced': True}], ensure_ascii=False),
                encoding='utf-8')
            json_path = final_dir / 'ALL_questions_FIXED.json'
            json_path.write_text(
                json.dumps([{'id': 'T1', 'module': 'M1', 'type': 'A1', 'stem': '测试题',
                             'options': [{'label': 'A', 'text': 'a'}, {'label': 'B', 'text': 'b'}],
                             'answer': 'A'}], ensure_ascii=False),
                encoding='utf-8')
            out, n = qbank.export_md(str(json_path), str(final_dir / 'ALL_questions_FIXED.md'), title='测试')
            assert n == 1
            batch_data = {'steps': {'AGENT4': {'output': 'AGENT4_追溯日志.json', 'trace_log': 'y'}},
                          'status': 'IN_PROGRESS'}
            r = gate_check.gate_agent4('batchMDT', batch_data)
            assert r['status'] == 'PASS', r
        finally:
            gate_check.BASE = orig_base
