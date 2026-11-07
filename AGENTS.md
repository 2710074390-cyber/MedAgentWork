# AGENTS.md — 任何 Agent 接手本仓库的第一份文件

> 本文件**与宿主无关**（Claude Code / Codex / DSH / WorkBuddy / 其他都一样）。
> 它不定义业务规则，只做两件事：告诉你规则在哪，告诉你哪些红线是**脚本判定**的。
> 规则原文真源是 `SOUL.md` 的 `HC-*`；本文件只做路由，不新增规则。

## 0. 宿主自检（DSH / WorkBuddy / Trae 三通用）

开工第一条命令：

```bash
python scripts/host_bootstrap.py check     # exit 0 = 三个宿主入口都就绪
```

缺入口 → `python scripts/host_bootstrap.py install`（幂等；只写**路由桩**，不复制规则正文）。
默认装**项目级**（Trae 规则 + WorkBuddy 项目技能，随仓库入库，换机器零步骤）；想同时装用户级 WorkBuddy 技能就加 `--scope both`。
源文件（`AGENTS.md` / `.dsh/skills/*/SKILL.md`）改过而没重生成 → `check` 判 `STALE`，重跑 install 即可。

| 宿主 | 自动加载什么 | 入口从哪来 |
|---|---|---|
| **DSH**（DeepSeek Harness） | 仓库根 `AGENTS.md` + `.dsh/skills/<name>/SKILL.md` | 原生，无需生成 |
| **WorkBuddy**（腾讯） | 项目级 `.workbuddy/skills/<name>/SKILL.md`（或用户级 `~/.workbuddy/skills/`） | 本脚本生成（项目级入库；`--scope both` 追加用户级） |
| **Trae**（字节） | 项目级 `.trae/rules/*.md`（`alwaysApply: true`） | 本脚本生成（项目级，随仓库入库） |

三宿主执行的是**同一套脚本门禁**（`batch_driver` / `gate_stamp` / `gate_audit`）与同一个 git 钩子，
所以「跳过门禁」在任何宿主上都会在 downstream / 提交 / CI 处被拦——入口只负责让 Agent 找到规则。

## 1. 跑批次之前读什么

按顺序读（都是文件，直接 `read` 即可，不需要特定宿主的 skill 加载器）：

1. `.dsh/skills/medmaster/SKILL.md` — 编排入口（谁调谁、门禁在哪一步）
2. `.dsh/skills/medbatch/SKILL.md` — 批次生命周期、目录命名、故障处置
3. 你的角色：`.dsh/skills/{medgen,medqc,medfix,medreview}/SKILL.md`

**不要整份读** `CONTEXT.md` / `SOUL.md`（各 50 KB 以上，上下文一长规则必然衰减）。
需要某条规则时按指针取：

```bash
python scripts/ctx_fetch.py --id '§SOUL#HC-22'
```

## 2. 四条硬约束（脚本判定，不是纪律）

| 约束 | 判定者 | 违反后你会看到 |
|---|---|---|
| 门禁只能通过 `batch_driver.py` 执行 | driver（唯一执行面） | 产物没有对应回执 |
| 产物必须与一次门禁执行字节绑定 | `gate_stamp` 回执链 | `ARTIFACT_MISMATCH` / `CHAIN_BROKEN` |
| 消费上游前先验上游回执 | driver `preflight` / `gate_verify` | `STAGE_MISSING` → `BLOCKED` |
| 签收批次的产物与回执链必须入库 | `gate_audit --require-tracked` | `ARTIFACT_UNTRACKED` → CI 红 |

这四条**不依赖你是否读了规则**：跳过门禁，下游就拒收；伪造回执，CI 重跑门禁就会红。
「写了规则」≠「会执行」——本仓库只信能机械判定的东西。

## 3. 四个自检命令

```bash
# 上游门禁真的跑过吗（消费上游产物之前）
python scripts/gate_verify.py --batch batchNNN --stage a3 --quiet

# 我这阶段的门禁过没过（唯一正确入口，不要直接跑 validate/gate_check）
python scripts/batch_driver.py check --batch batchNNN --stage auto

# 这批产物入库了吗（batch048+ 签收后必须 exit 0）
python scripts/batch_artifacts.py check --batch batchNNN

# 即将提交的内容里，批次证据是否完整（pre-commit 同款口径）
python scripts/gate_audit.py --staged --require-tracked
```

退出码 `0` 才继续；`1` 表示有具体阻断项，按输出的「下一步命令」处理；`2` 是参数/环境错误。

> `gate_verify` 对「不属于本批计划」的阶段返回 `SKIP NOT_APPLICABLE`（exit 0）——这是机械判定的
> 「本批没有这个阶段」（如纯复习资料批次无 a2–a4/lv），不是漏检；新批次缺回执仍然是 exit 1。
> 判断依据是 `batch_driver.plan_boundaries`，不需要你自己按 `product_types` 推断。

本机已安装 pre-commit 钩子（`.git/hooks/pre-commit`，由 `scripts/install_git_hooks.py` 写入），
提交批次产物时自动跑最后一条。换机器后重新执行一次 `python scripts/install_git_hooks.py`。

## 3.5 跨宿主编排（H1–H5 · 2026-11-07）

`batch_driver.py check` 在 PASS 时按 `plan` 确定性给出 `next_stage / next_action / next_bundle`，并为下一阶段写
`中间产物/{batch}/_handoff/{stage}.json`。交接包**只描述数据与命令、不含任何宿主工具名**；DSH / WorkBuddy / Trae / 人工
消费同一份包，门禁回执因此是同一份字节。

| 想做什么 | 命令 |
|---|---|
| 查当前宿主能力等级（`L2` 可派生隔离子代理 / `L1` 单会话 / `L0` 手工） | `python scripts/host_bootstrap.py check` |
| 推进一个阶段（PASS 后自动生成下一阶段交接包） | `python scripts/batch_driver.py check --batch batchNNN --stage auto` |
| 打印人读交接单（L0 / 人工接力） | `python scripts/batch_driver.py brief --batch batchNNN --stage a3` |
| 三档回归矩阵 | `python scripts/host_matrix_check.py --matrix` |

三条纪律：① 不要把宿主工具名写进交接包或任务描述；② `write_scope=question_bank`（`parallel_safe=false`）的阶段
**任何宿主都不许并发写**；③ 包里 `inputs_fingerprint` 与当前产物不符即视为过期，必须重跑 `check` 后再用。

## 4. 不要做的事

- 不要手写 `最终产物/{batch}/_gate_ledger.json`——回执只能由 `batch_driver.py` 在 PASS 后写，
  伪造会在 `gate_audit --recheck` 重跑门禁时暴露。
- 不要用 `--no-preflight` / `--no-stamp` 绕过——payload 会留 `preflight.enabled=false`，事后可追。
- 不要把未经 `batch_artifacts.py check` 的批次产物直接 commit。
- 不要修改 `archive/`（已归档批次只读）、`GoldenSet/`（只允许用户手动移入）。

## 5. 怎么推到 main（2026-11-05 起 branch protection 已启用）

main 受保护：required check = `batch-gate`，`enforce_admins=true` —— **直接 `git push origin main` 会被拒（管理员也一样）**。

正确姿势（走 PR，让 CI 在合并前跑一遍）：

```bash
git checkout -b <branch> && git push -u origin <branch>
gh pr create --fill
gh pr merge --squash --delete-branch        # 等 batch-gate 绿再合
```

紧急直推（需临时解除保护、事后立即恢复）的命令见 `memory/TODO_ACTIVE.md` 的 SA-P1-4。
**不要用 `--admin` 强合、也不要在 batch-gate 红时合**：红 = 批次证据有问题，先修批次再推。

## 6. 规则冲突怎么办

`SOUL.md` 的 `HC-*` 原文 > `CONTEXT.md` > SKILL > 本文件。
冲突时按左边的执行，并把冲突写进 `memory/FACT.md`，不要自行折中。

---

**维护**：改门禁脚本时同步本文件的命令；新增硬约束时补进第 2 节表格。
历史背景见 `reports/P0_防跳过门禁_实施记录_20261105.md` 与 `reports/P1_防跳过_消费方验真_实施记录_20261105.md`。
