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
| SA-B-F1 | TODO | 修 `gate_check.stage_sequence`：`== '2.0'` → `float(version) >= 2.0` | schema 2.1/2.2 批次 `--stage auto` 会漏 LV；driver 已补插并注释 |
| SA-B-F2 | TODO | `verify_produce_rules` / `fact_check` / `check_keypoint_coverage` 加可选 `--json-out` | 目前 driver 用退出码映射 + 人读兜底（解析失败进 unparsed） |
