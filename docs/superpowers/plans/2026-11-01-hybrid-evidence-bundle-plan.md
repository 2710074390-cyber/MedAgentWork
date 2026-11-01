# 混合医学证据包校验器实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为批次建立独立、可复现的医学证据包校验能力，验证来源、快照、主张、哈希和冲突，但暂不影响题目生成与既有 R0–R4 门禁。

**Architecture:** 新增一个只读证据包校验器，接收批次号、证据包目录和报告输出路径；校验器只读取证据包，计算文件哈希并输出 JSON 报告。所有测试使用临时目录，避免写入真实批次、题库或 workflow_state。

**Tech Stack:** Python 3 标准库、argparse、json、hashlib、pathlib、pytest。

---

### Task 1: 固化证据包数据契约与校验状态

**Files:**
- Create: `schemas/evidence_bundle.schema.json`
- Create: `scripts/check_evidence_bundle.py`
- Test: `tests/test_evidence_bundle.py`

- [ ] **Step 1: 写失败测试，覆盖正常包和空包状态**

测试构造临时目录，生成 `manifest.json`、`sources.jsonl`、`claims.jsonl`、`conflicts.json` 和 `extracted/source.md`；正常包断言 CLI 返回 0、报告为 `PASS`。另构造只有 `enabled_for_generation=false` 且无来源的包，断言报告为 `SKIPPED_NOT_ENABLED`。

- [ ] **Step 2: 运行测试确认失败**

运行：`python -m pytest tests/test_evidence_bundle.py -q -p no:cacheprovider`
预期：因 `scripts/check_evidence_bundle.py` 不存在而失败。

- [ ] **Step 3: 实现最小读取与状态聚合**

实现函数：`sha256_file(path)`、`read_json(path)`、`read_jsonl(path)`、`validate_bundle(batch, evidence_dir)` 和 `main()`。支持 `--batch`、`--evidence-dir`、`--out`；报告包含 `batch`、`status`、`issues`、`files`、`generated_at`。

- [ ] **Step 4: 运行测试确认通过**

运行：`python -m pytest tests/test_evidence_bundle.py -q -p no:cacheprovider`
预期：正常包和未启用空包测试通过。

### Task 2: 实现来源元数据、路径安全和哈希校验

**Files:**
- Modify: `scripts/check_evidence_bundle.py`
- Modify: `tests/test_evidence_bundle.py`

- [ ] **Step 1: 写失败测试**

增加测试：重复 `source_id`、绝对路径、`..` 路径、快照缺失、内容哈希不匹配、跨批次 manifest；每个场景断言状态为 `BLOCKED`，并存在稳定的问题代码。

- [ ] **Step 2: 运行测试确认失败**

运行：`python -m pytest tests/test_evidence_bundle.py -q -p no:cacheprovider`
预期：新增场景失败。

- [ ] **Step 3: 实现来源校验**

要求来源具备 `source_id`、`source_type`、`publisher`、`title`、`url`、`accessed_at`、`status`；source ID 唯一；快照和抽取路径必须是证据包内相对路径；记录文件 SHA-256 并与声明值比较；拒绝目录外路径和不存在文件。

- [ ] **Step 4: 运行测试确认通过**

运行同一命令，预期所有来源路径和哈希测试通过。

### Task 3: 实现主张绑定、证据片段和冲突校验

**Files:**
- Modify: `scripts/check_evidence_bundle.py`
- Modify: `tests/test_evidence_bundle.py`

- [ ] **Step 1: 写失败测试**

增加测试：重复 `claim_id`、引用不存在的 `source_id`、跨批次 claim、空 `support_quote`、证据片段未出现在抽取文本、未解决高风险冲突。断言分别产生对应问题代码；高风险未解决冲突必须 `BLOCKED`。

- [ ] **Step 2: 运行测试确认失败**

运行：`python -m pytest tests/test_evidence_bundle.py -q -p no:cacheprovider`
预期：新增场景失败。

- [ ] **Step 3: 实现主张和冲突校验**

要求 claim 具备 `claim_id`、`batch`、`claim`、`source_ids`、`support_quote`、`support_scope`、`evidence_level`、`conflict_status`、`review_status`；引用必须存在；有抽取文本时逐字定位支持片段；冲突文件必须为数组；高风险主张引用未解决冲突时阻断。

- [ ] **Step 4: 运行测试确认通过**

运行同一命令，预期所有主张、片段和冲突测试通过。

### Task 4: 完善报告指纹、文档和回归验证

**Files:**
- Modify: `scripts/check_evidence_bundle.py`
- Modify: `tests/test_evidence_bundle.py`
- Modify: `docs/superpowers/specs/2026-11-01-hybrid-evidence-bundle-design.md`

- [ ] **Step 1: 写失败测试**

增加测试：报告包含每个输入文件的路径和 SHA-256、证据包整体指纹；修改抽取文件后再次运行，断言报告发现哈希变化；校验器不修改题库和 `workflow_state.json`。

- [ ] **Step 2: 实现报告指纹和只读保证**

对证据包内参与校验的文件按规范化相对路径排序后计算整体摘要；报告写入 `--out` 指定位置；不回写 manifest，不更新题库和工作流状态。将问题分类为 `BLOCKED`、`WARN`、`SKIPPED_NOT_ENABLED`。

- [ ] **Step 3: 更新规格文档**

补充实际问题代码、报告字段和 CLI 行为，确保规格与实现一致；删除含糊表述。

- [ ] **Step 4: 运行完整验证**

运行：
- `python -m pytest tests/test_evidence_bundle.py -q -p no:cacheprovider`
- `python -m py_compile scripts/check_evidence_bundle.py`
- `git diff --check`

预期：新增测试全部通过、脚本编译通过、无空白错误；不运行会改写旧批次报告的命令。

### Task 5: 复核范围与兼容性

**Files:**
- Read-only review of `gate_check.py`, `scripts/quality_gate.py`, `scripts/check_learning_value.py`

- [ ] **Step 1: 确认未接入出题**

检查 MedGen/MedQC 提示词和现有 R0–R4 调用链未被新增校验器自动调用；证据包报告仅通过显式 CLI 生成。

- [ ] **Step 2: 确认旧产物未变更**

运行 `git status --short` 和 `git diff --stat`，确认只出现证据包 schema、校验器、测试、规格/计划文档及用户已存在的改动。

- [ ] **Step 3: 记录边界**

最终报告明确：本阶段没有联网抓取、没有医学事实自动裁决、没有接入题目生成、没有将证据包设为现有发布门禁必需项。
