"""冒烟测试：验证 skill 包在干净工作区可跑通核心链路。"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "skills" / "medagentwork"
SCRIPTS = (SKILL / "scripts").as_posix()
WS = Path(__file__).resolve().parent / "test_ws"

PASS = 0
FAIL = 0


def run(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {detail}")


# ── 准备干净工作区 ──
if WS.exists():
    shutil.rmtree(WS)
(WS / "输入素材" / "神经病学").mkdir(parents=True)
(WS / "中间产物" / "batch001").mkdir(parents=True)
(WS / "输入素材" / "神经病学" / "第1章.md").write_text(
    "# 第1章 脑血管疾病\n脑卒中分为缺血性和出血性两大类。", encoding="utf-8")

print("== 1. 初始化状态文件 ==")
r = run(f'python -c "import sys; sys.path.insert(0, \'{SCRIPTS}\'); '
        f'import workflow_state as ws; ws.save_state({{\'schema_version\': 2}})"', cwd=WS)
check("workflow_state.json 创建", (WS / "workflow_state.json").exists(), r.stderr[:200])

print("== 2. 登记批次 (ensure_batch + save_state) ==")
r = run(f'python -c "import sys; sys.path.insert(0, \'{SCRIPTS}\'); '
        f'import workflow_state as ws; s, err = ws.load_state(); '
        f'b, c = ws.ensure_batch(s, \'batch001\'); b.update(subject=\'脑血管疾病\', target=10); '
        f'ws.save_state(s); print(b[\'batch_id\'], \'created=\' + str(c))"', cwd=WS)
check("批次登记写盘", "batch001" in r.stdout and "created" in r.stdout, r.stdout + r.stderr[:300])

print("== 3. 写入测试题库（1 好 + 2 坏） ==")
questions = [
    {"question_id": "N-A1-001", "type": "A1", "stem": "缺血性脑卒中最常见的病因是下列哪一项？",
     "options": {"A": "大动脉粥样硬化性血栓形成所致", "B": "脑动静脉畸形血管破裂所致",
                 "C": "淀粉样脑血管病出血所致", "D": "蛛网膜下腔动脉瘤破裂",
                 "E": "脑静脉窦血栓形成所致"},
     "answer": "A", "analysis": "缺血性脑卒中以大动脉粥样硬化性血栓形成最常见。",
     "module": "M1", "bloom_level": "记忆"},
    # 坏题1：选项过短（R8）
    {"question_id": "N-A1-002", "type": "A1", "stem": "脑出血最好发部位是下列哪一项？",
     "options": {"A": "壳核", "B": "丘脑", "C": "桥脑", "D": "小脑", "E": "脑叶"},
     "answer": "A", "analysis": "基底节区壳核出血最常见。",
     "module": "M1", "bloom_level": "记忆"},
    # 坏题2：无解析
    {"question_id": "N-A1-003", "type": "A1", "stem": "蛛网膜下腔出血首选的检查是？",
     "options": {"A": "头颅CT平扫", "B": "头颅MRI平扫", "C": "脑电图检查", "D": "经颅多普勒", "E": "腰穿脑脊液"},
     "answer": "A",
     "module": "M1", "bloom_level": "理解"},
]
(WS / "中间产物" / "batch001" / "ALL_questions.json").write_text(
    json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")

print("== 4. GATE-A2 校验（应 FAIL>0 并 BLOCK） ==")
r = run(f'python "{SCRIPTS + "/validate_options.py"}" --batch batch001 --mode full', cwd=WS)
check("validate_options 可执行", r.returncode in (0, 1, 2), r.stderr[:300])
report_dir = WS / "reports" / "validate"
check("校验报告生成", any(report_dir.glob("*.json")), r.stdout[-300:])

print("== 5. gate_check 阶段门禁（应 HALT） ==")
r = run(f'python "{SCRIPTS + "/gate_check.py"}" --batch batch001 --stage agent2_done', cwd=WS)
check("gate_check 可执行", r.returncode in (0, 1, 2), r.stderr[:300])

print("== 6. Bloom 采样 ==")
r = run(f'python "{SCRIPTS + "/bloom_sampler.py"}" --batch batch001 --threshold 15', cwd=WS)
check("bloom_sampler 可执行", r.returncode in (0, 1, 2), r.stderr[:300])

print("== 7. 契约检查 ==")
r = run(f'python "{SCRIPTS + "/contract_check.py"}" --batch batch001', cwd=WS)
check("contract_check 可执行", r.returncode in (0, 1, 2), r.stderr[:300])

print("== 8. workflow_state CLI ==")
r = run(f'python "{SCRIPTS + "/workflow_state.py"}" --show batch001', cwd=WS)
check("workflow_state CLI 可执行", r.returncode == 0, r.stderr[:300])

print("== 9. 修复后重跑（修复坏题 → 应 FAIL==0 放行） ==")
questions[1]["options"] = {"A": "基底节区壳核（大脑中动脉深穿支）", "B": "丘脑（大脑后动脉深穿支）",
                            "C": "脑桥（基底动脉旁正中支）", "D": "小脑（小脑上动脉）", "E": "脑叶（皮质下白质）"}
questions[2]["analysis"] = "蛛网膜下腔出血首选头颅 CT 平扫，敏感性高且快速。"
(WS / "中间产物" / "batch001" / "ALL_questions.json").write_text(
    json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
r2 = run(f'python "{SCRIPTS + "/validate_options.py"}" --batch batch001 --mode full', cwd=WS)
summary_files = sorted(report_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
latest = json.loads(summary_files[-1].read_text(encoding="utf-8"))
fails = latest.get("summary", {}).get("fail", 0) if isinstance(latest, dict) else None
check("修复后 FAIL==0", fails == 0, f"summary.fail={fails}; stdout尾部: {r2.stdout[-200:]}")

print("== 10. MD 导出（qbank.py） ==")
r = run(f'python "{SCRIPTS + "/qbank.py"}" export-md --file 中间产物/batch001/ALL_questions.json '
        f'--out 中间产物/batch001/test_export.md --title "神经病学·冒烟测试"', cwd=WS)
check("export-md 生成", (WS / "中间产物" / "batch001" / "test_export.md").exists(),
      r.stdout[-200:] + r.stderr[:200])

print(f"\n{'=' * 40}\n结果: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
