# TODO_ACTIVE — 唯一待办板

> **历史待办**见 `docs/archive/2026-11/TODO.md`（已归档，**不再追加**）。
> 规则：一行一项；认领后填「认领」；完成时在「提交」写 commit sha；超期项在证据里注明原因。
> 关联契约：`reports/实施步骤与验收标准_调度与上下文层_20261104.md`（SA-1…SA-11）。

## 调度与上下文层（SA 系列）

| ID | 状态 | 认领 | 任务 | 落点 | 验收 | 提交 |
|---|---|---|---|---|---|---|
| SA-A-1 | DONE | MedMaster | SA-3 治理修漏（FACT / 待办板 / 数字 / HC-12 预告） | `memory/`、`SOUL.md`、`CONTEXT.md`、2 个 SKILL | AC-SA3-01..04 | 阶段 A |
| SA-A-2 | DONE | MedMaster | SA-1 直读规则（9 处编辑点） | 5 个 SKILL、`MedMaster_current_prompt.md` | AC-SA1-01..05 | 阶段 A |
| SA-A-3 | DONE | MedMaster | SA-2 输出模板（HC-28 三行/四行） | `SOUL.md`、`medmaster/SKILL.md` | AC-SA2-01..03 | 阶段 A |
| SA-B-1 | DONE | MedMaster | SA-4 driver 骨架：CLI / boundary 图 / 退出码 / schema | `scripts/batch_driver.py`、`schemas/batch_driver.schema.json` | AC-SA4-01..03 | 阶段 B |
| SA-B-2 | DONE | MedMaster | SA-4 适配器层（17 脚本 + 4 处 `--json-out`） | 同上 + `gate_check.py` | AC-SA4-08..10 | 阶段 B |
| SA-B-3 | DONE | MedMaster | SA-4 归一化 + SA-5 形状契约 + 7 夹具 | `scripts/batch_driver.py`、`tests/fixtures/gates/` | AC-SA4-02/09、AC-SA5-01..03 | 阶段 B |
| SA-B-4 | DONE | MedMaster | SA-4 SKILL 接线（唯一执行面 + 禁用清单） | `{medmaster,medbatch}/SKILL.md` | AC-SA4-11 | 阶段 B |
| SA-B-5 | DONE | MedMaster | SA-4 测试与回归 | `tests/test_batch_driver.py` | AC-SA4-06/07 | 阶段 B |
| SA-C-1 | DONE | MedMaster | SA-6 `build_batch_context.py` + `_ctx.md` 模板 | `scripts/build_batch_context.py` | AC-SA6-01/02 | 阶段 C |
| SA-C-2 | DONE | MedMaster | SA-6 `_kpidx.jsonl` + `ctx_fetch.py` | `scripts/ctx_fetch.py` | AC-SA6-03/04 | 阶段 C |
| SA-C-3 | DONE | MedMaster | SA-6 必读清单改写（7 处） | 5 个 SKILL、`MedMaster_current_prompt.md` | AC-SA6-05 | 阶段 C |
| SA-C-4 | DONE-STATIC | MedMaster | SA-6 MedMaster 起步读入实测（≤32k tok） | `reports/implementation/` | AC-SA6-06 | |
| SA-D-1 | DONE | MedMaster | SA-7 `qbank.py subselect` | `scripts/qbank.py`、`tests/test_qbank.py` | AC-SA7-01..03 | 阶段 C |

## 防跳过门禁（P0 · 2026-11-05）

> 问题：别的 Agent 会「跳过门禁直接写产物」。方案见 `reports/P0_防跳过门禁_实施记录_20261105.md`。
> AC 定义：AC-P0-01..10（同上文档 §4）。

| ID | 状态 | 认领 | 任务 | 落点 | 验收 | 提交 |
|---|---|---|---|---|---|---|
| SA-P0-1 | DONE | MedMaster | 回执链原语（产物字节绑定 + chain_prev + 原子写） | `scripts/gate_stamp.py`、`tests/test_gate_bypass.py` | AC-P0-01..03 | 2026-11-05 |
| SA-P0-2 | DONE | MedMaster | driver 接线：PASS 写回执 + preflight 验全部前置阶段 | `scripts/batch_driver.py` | AC-P0-04..06 | 2026-11-05 |
| SA-P0-3 | DONE | verify-builder | 消费方验真 CLI（exit 0/1/2 + 「下一步命令」） | `scripts/gate_verify.py`、`tests/test_gate_verify.py` | AC-P0-07 | 2026-11-05 |
| SA-P0-4 | DONE | audit-builder | 中央审计 + STAGE_MISSING 覆盖检查 + CI `batch-gate` job | `scripts/gate_audit.py`、`.github/workflows/ci.yml`、`tests/test_gate_audit.py` | AC-P0-08..09 | 2026-11-05 |
| SA-P1-1 | TODO | — | 4 个 worker SKILL 第一步改为「先 `gate_verify` 上游回执」 | `{medqc,medfix,medgen,medreview}/SKILL.md` | AC-P1-01 | |
| SA-P1-2 | TODO | — | 发布前追加 `gate_audit --changed-only --recheck`；分支保护要求 `batch-gate` 必绿 | `.github/workflows/deploy.yml`、仓库设置 | AC-P1-02 | |
| SA-P1-3 | TODO | — | 签收批次的「产物 + 回执链」入库策略（否则 CI 只能看已提交部分） | 入库边界决策 | AC-P1-03 | |
| SA-P2-1 | TODO | — | hooks 层拦截（仅可控宿主：DSH / Claude Code PreToolUse 拦 `最终产物/` 写入） | — | AC-P2-01 | |

## 条件项（触发后再认领）

| ID | 触发条件 | 任务 |
|---|---|---|
| SA-8 | ✅ 已做（2026-11-04） | watchdog 进展判据 → `scripts/batch_watchdog.py`（证据：sa_8_watchdog_验收证据） |
| SA-9 | 用户确认允许后台只读预演 | 投机候选包（先给两脚本加 `--dry-run`） |
| SA-10 | 决定 `reports/` ignore 策略 | run_id（合并归档改造） |
| SA-11 | 用户明确要无人值守 | `check --once` 集成 |

## 维护

- 「完成项 → 更新 TODO」的旧指向已从 `medbatch/SKILL.md:149` 改为本文件（2026-11-04）。
- 本板只增不改历史行；作废项标 `CANCELLED` + 一句原因。

## 阶段 B 执行期发现的后续项

| ID | 状态 | 任务 | 说明 |
|---|---|---|---|
| SA-B-F1 | DONE | 修 `gate_check.stage_sequence`：`== '2.0'` → `float(version) >= 2.0` | 已修（2026-11-04，回归见 `tests/test_batch_driver.py::test_stage_sequence_lv_for_schema_2x`） |
| SA-B-F2 | TODO | `verify_produce_rules` / `fact_check` / `check_keypoint_coverage` 加可选 `--json-out` | 目前 driver 用退出码映射 + 人读兜底（解析失败进 unparsed） |
