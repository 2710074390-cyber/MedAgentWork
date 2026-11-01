# 混合医学证据包与校验器设计

## 目标

为后续题库批次建立可复现的外部医学证据包，先完成来源落盘、内容哈希、主张绑定和完整性校验；本阶段不把联网来源接入 MedGen 出题，也不改变 batch045 或旧批次题目答案与来源字段。

## 范围

包含：

- `中间产物/{batch}/evidence/` 证据包目录契约；
- `manifest.json`、`sources.jsonl`、`claims.jsonl`、`conflicts.json` 的结构校验；
- 来源快照/抽取文本的路径安全检查和 SHA-256 校验；
- 主张与来源、证据片段的可定位关系检查；
- 批次绑定、证据包整体指纹和 JSON 校验报告；
- 临时目录隔离测试。

不包含：

- 自动联网搜索或网页抓取；
- 修改 MedGen/MedQC 的出题输入契约；
- 用联网来源改变现有题目答案；
- 修改旧批次产物；
- 将证据包纳入现有 R0–R4 的必需发布门禁。

## 目录与数据契约

```text
中间产物/{batch}/evidence/
├─ manifest.json
├─ sources.jsonl
├─ claims.jsonl
├─ snapshots/
└─ extracted/
```

`manifest.json` 必须包含：

- `schema_version`；
- `batch`；
- `status`；
- `sources_file`、`claims_file`、`conflicts_file`；
- `created_at`；
- `bundle_sha256`（可选；校验器只读，不回写 manifest；填写时必须与计算值一致）；
- `enabled_for_generation: false`。

每条 `sources.jsonl` 记录必须有：`source_id`、`source_type`、`publisher`、`title`、`url`、`accessed_at`、`status`。若有本地快照或抽取文本，必须使用证据包内相对路径并提供对应 SHA-256；路径不得越出证据包目录。

每条 `claims.jsonl` 记录必须有：`claim_id`、`batch`、`claim`、`source_ids`、`support_quote`、`support_scope`、`evidence_level`、`conflict_status`、`review_status`。引用的 `source_id` 必须存在，`support_quote` 必须能在对应抽取文本中定位；无抽取文本的来源不能声称已完成引文定位。

`conflicts.json` 必须是数组。未解决冲突不能被标记为 `resolved`；高风险主张若冲突未解决，校验结果为 BLOCKED。

## 校验状态

- `PASS`：结构完整、路径安全、哈希匹配、来源引用存在、证据片段可定位。
- `WARN`：存在待人工复核但不阻断的低风险问题。
- `BLOCKED`：批次不匹配、文件缺失、哈希不匹配、引用不存在、路径越界、证据片段无法定位、未解决的高风险冲突或声明已启用出题但证据契约不完整。
- 空证据包在当前阶段返回 `SKIPPED_NOT_ENABLED`，因为联网证据尚未接入出题；一旦 `enabled_for_generation=true`，同样情况必须 BLOCKED。

## 校验入口

```powershell
python scripts/check_evidence_bundle.py --batch batch045 --evidence-dir "中间产物/batch045/evidence" --out "reports/validate/evidence_bundle_batch045.json"
```

校验器只读证据包并写指定报告，不修改题库、复习资料或工作流状态。报告包含 `batch`、`status`、`issues`、`files`、`bundle_sha256` 和 `generated_at`；`files` 映射规范化相对路径到实际文件 SHA-256。整体哈希为路径到哈希的映射按键排序、紧凑 JSON、UTF-8 编码后的 SHA-256；其中 manifest 使用去除 `bundle_sha256` 字段后的规范 JSON 的 SHA-256。来源文件使用 `snapshot_path`/`snapshot_sha256` 与 `extracted_path`/`extracted_sha256` 字段。主张以 `risk_level: high` 标记高风险；冲突记录包含 `claim_id` 和 `status`。引文至少须在一个被引用来源的抽取文本中逐字出现。报告路径必须在证据包之外；BLOCKED 退出码为 1，其余状态为 0。

## 兼容与安全

证据包仅作为独立基础设施，不接入现有 R0–R4 必需检查。现有题库即使没有证据包，也不应被本阶段改判。校验器必须拒绝绝对路径、`..` 穿越路径、证据包外部文件和重复 ID；不得把 URL 可访问等同于医学事实已验证。

## 验收标准

- 正常最小证据包 PASS；
- 文件内容变化导致 HASH_MISMATCH/BLOCKED；
- 重复 ID、跨批次、缺来源、路径越界、片段不命中分别被识别；
- 高风险未解决冲突 BLOCKED；
- 未启用联网出题时空包返回 SKIPPED_NOT_ENABLED；
- 校验器不修改现有题库及工作流状态；
- 所有新增测试在临时目录通过。
