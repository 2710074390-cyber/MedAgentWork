# batch049 签收回执

| 项 | 内容 |
|---|---|
| 签收人 | 2710074390-cyber（项目负责人） |
| 签收时间 | 2026-11-16T19:34:54 |
| 签收范围 | 250 题（batch049） |
| 签收依据 | HC-28 发布底线：证据 A / 风险 high/low/medium / 四道确定性门禁 PASS（2026-11-03 起不再要求逐题人工核验） |
| 签收说明 | 用户确认签收；本批已重跑 a2/a3/a4/lv/a5/final，记忆要点已清理并重新绑定回执。 |

## 交付物

| 文件 | SHA256 | 大小 |
|---|---|---|
| `_gate_ledger.json` | `428e3724844da902…` | 14,058 B |
| `AGENT4_修改声明.md` | `ef819caa1ccd5b33…` | 602 B |
| `AGENT4_追溯日志.json` | `bb943bec9fc27ee2…` | 2,066 B |
| `ALL_questions_FIXED.json` | `fcf9ea37c6057658…` | 1,374,123 B |
| `ALL_questions_FIXED.md` | `11b9872e3f382f8b…` | 389,808 B |
| `escalations_for_human.md` | `150b3c859720aed7…` | 367 B |
| `review_queue.json` | `8e0473776f732313…` | 418 B |
| `review_queue.md` | `12fc4c3b734bce86…` | 540 B |
| `眼科学重点题库.md` | `11b9872e3f382f8b…` | 389,808 B |

## 门禁结论

| 门禁 | 状态 | 说明 |
|---|---|---|
| GATE-A2 | PASS | 产出门禁通过 (FAIL=0, PASS=107, WARN=143) |
| GATE-A3 | PASS | 质检门禁通过 (gate_decision=PASS_WITH_FIXES, D20 OK, Bloom OK) |
| GATE-A4 | PASS | 修复门禁通过 (追溯日志存在, HC-13 source_file_synced OK, JSON纯净, MD交付齐全) |
| GATE-FINAL | PASS | 终审门禁通过 (HC-9/10/11 OK, JSON有效) |

## 证据链

- 血缘记录 3 条：agent2_DONE（2d7b7a38e08f…）、agent3_DONE（fb862c4151a4…）、agent4_DONE（2d7b7a38e08f…）
- 签收前交付 sha：`e92d2179e98215e0c558fd0a469dcd029be2ceb11018026cf2dbe6510029be05`
- 签收后交付 sha：`fcf9ea37c60576588db113dc0055c925b6c06fa2b1ff9384919e2227302d149a`
- 签收前备份：`.tmp/batch049_fixed_before_signoff.json`
- 证据等级：A（签收不升级等级）｜风险：high、low、medium

## 未完成项（签收不覆盖）

- 第二评分者盲评（κ 不可计算）
- 由此 AC-P3-02（κ≥0.61）仍为开项，签收不改变该结论。

> 本回执证明的是**发布授权**，不是医学正确性背书。HC-28：`release_status=READY` 仅表示发布门槛已过；临床使用中如发现错误，应回溯本回执的签收人与交付 sha，按修订流程处理，不得就地改文件。
