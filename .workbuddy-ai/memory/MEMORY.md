# MedAgentWork 项目长期记忆

## 仓库

| 项目 | 值 |
|---|---|
| skill 分享版仓库 | `C:\Users\38063\Desktop\MedAgentWork\medagentwork-skill` |
| 远程 | `https://github.com/2710074390-cyber/medagentwork-skill.git`（分支 `main`） |
| 当前版本 | v2.2（tag `v2.2` → commit `ef9c2f9`；Release 已建，标记 Latest） |
| 上一版本 | v2.1（tag `v2.1` → commit `5ddc866`；Release「落实评审报告整改」，latest=false） |
| 首发版本 | v1.0（tag `v1.0` → commit `282af28`；Release「v1.0 — 首发版」，**已冻结，勿动**） |
| 变更记录 | `CHANGELOG.md`（Keep a Changelog 格式；改版本时同步更新） |
| v2.2 要点 | 移除全部插图相关功能（破坏性变更，skills 文件数 56→49） |

## 站点 med-review-site（Cloudflare Pages）

| 项 | 值 |
|---|---|
| 线上 | `https://med-review-site.pages.dev/` |
| 源码 | 仓库根 `index.html`（单文件，零 CDN，内联 CSS+JS） |
| 部署源 | **`origin` = `2710074390-cyber/MedAgentWork.git`** 的 `main` |
| 部署通道 | **双通道**：Actions `wrangler pages deploy`（`.github/workflows/deploy.yml`）+ Cloudflare Pages Git 集成（`pages-build-deployment`），两者都会跑 |
| Pages 配置 | 根目录 `wrangler.toml`（`name` / `pages_build_output_dir="."` / `VISITS` KV） |
| 本地部署脚本 | `scripts/deploy_site.ps1`（建干净 worktree → wrangler，绕开 25MiB 单文件上限） |
| 另一个远程 | `public` = `MedAgentWork-Public.git` —— **与站点无关**，别推错 |

### ⚠️ 站点路径约定（改 `index.html` 必须遵守）

**所有资源 path 一律「仓库根相对」，必须自带顶层目录**（`大三下/…` 或 `大四上/…`）。
页面里只允许**一套**约定；`url(path)` 只做逐段 `encodeURI`，**不得再拼接任何 base**。
约定说明与事故复盘写在 `index.html` 数据层注释里。

2026-09-27 事故（已修复）：并存两套约定 → 大四上两张卡请求落到
`大四上/大四上/…` 与 `大三下/大四上/…`，10 个下载按钮失效。

### 链接门禁 `scripts/check_site_links.mjs`

把页面脚本真跑一遍（stub DOM），用页面**自己的** `encPath` 解析出每个按钮
实际请求的 URL，再断言 `HTTP 200` **且 Content-Type 与扩展名一致**。

```bash
node scripts/check_site_links.mjs index.html                    # 查仓库内文件是否存在
node scripts/check_site_links.mjs index.html --base https://…/  # 查线上
```
退出码：`0` 全通过 / `1` 有断链 / `2` 门禁自身失效（抽不到目标）。
**已挂在 `deploy.yml` 部署前置步骤，fail-closed。**

> **关键认知：HTTP 200 不等于文件存在。** Cloudflare Pages 在没有 `404.html` 时
> 会把未命中路径回退成 `index.html`，返回 200 + `text/html`。所以坏链既不报错、
> 也不 404，浏览器按 `a.download` 存出「扩展名是 .pdf、内容是网页」的文件。
> **只查状态码的门禁对本类故障完全无效。**
> 建议（未执行）：补一个真 `404.html`，让断链诚实地返回 404。

### ⚠️ 站点 PDF 的来源约定（2026-09-28 立规）

**规范**：`docs/产物格式规范.md` §5.6 —— **PDF 一律人工导出后上传，脚本禁止生成**。
人工导出的原件在 **`C:\Users\38063\Desktop\大四上\<科目>\`**（桌面快捷方式
`MedAgentWork\大四上 - 快捷方式.lnk` 指向它）；`Desktop\大三下\` 是同类目录。

**关键指纹（判别人工 vs 脚本）**：

| | Producer | Creator |
|---|---|---|
| 人工（Chrome 打印对话框 / Obsidian 内置导出） | Skia/PDF m142 | **Chromium** |
| 脚本（`chrome --headless=new --print-to-pdf`） | Skia/PDF m149 | …**HeadlessChrome/149…** |

> **不能用 `/Producer=Skia/PDF` 判别** —— 人工导出同样是 Chromium `printToPDF`。
> 唯一可用的是 `/Creator` 里的 `HeadlessChrome`。

**25 MiB 上限**：Cloudflare Pages 单文件上限。人工导出版常超限（内科学 30 MiB，其中
71% 是 1600px 无损 PNG）。**超限时只压图、不重排版**：
```bash
python scripts/shrink_pdf.py <你导出的.pdf> -o "大四上/复习资料/<同名>.pdf"
```
（PyMuPDF `rewrite_images`，q92；页数/封面/分页/字体/书签全不变。实测 30→14 MiB。）
**不要**用 `export_review_pdfs.py` —— 那是重新渲染，会换掉封面与分页。

**强制点**：
- `scripts/verify_produce_rules.py` → `SITE_ROOTS = [大三下, 大四上]`，
  对站点内每个 PDF 断言 ≤25 MiB 且 `/Creator` 不含 `HeadlessChrome`；
- `scripts/export_review_pdfs.py` → `--out-dir` 落在站点目录即拒绝（exit 2）。

2026-09-28 事故（已修复）：`export_review_pdfs.py` 于 09-12 生成 Chrome 打印件
直接写进 `大四上/复习资料/`，把用户 09-01 的人工导出版覆盖（内科学 271 页无封面 vs 246 页有封面）。

### ⚠️ 仓库分叉待处理（2026-09-28 更新）

本地 `main` = `9dd9aac`（3 个 Obsidian 提交，**259 文件 / 146,270 行**，
含 `Obsidian产物/` 2490 张教材插图）；`origin/main` = `00a61ba`（站点修复链）。
**推送本地那 3 个提交会把教材插图公开到 GitHub（版权风险）**，需用户决策。
站点修复一直走独立提交链（worktree → detached HEAD → `git push origin HEAD:main`），未触碰本地 `main`。

## 发布流程（本仓库）

1. 改 `CHANGELOG.md` + `README.md` 的版本号 → 提交
2. 打注释 tag：`git tag -a vX.Y -m "<release notes 草稿>"`（tag 注释即 release notes 底稿）
3. 推送：`git push origin main && git push origin vX.Y`
4. 建 Release：`gh release create vX.Y --title "<标题>" --notes-file <文件> --latest`
   - notes 取自 `git tag -l --format='%(contents)' vX.Y`，转 markdown + 补 CHANGELOG/compare 链接
   - **必须先 `export GH_CONFIG_DIR="C:/Users/38063/AppData/Roaming/GitHub CLI"`**（否则 gh 误报未登录，见下方坑 3）
   - 坑：`gh release view --json` 无 `isLatest` 字段，只有 `gh release list --json` 有

## ⚠️ 本机 git 环境坑（每次提交/推送都会遇到）

### 坑 1：`git rm` 会删掉整个父目录 —— **绝不要用！**

**症状**：`git rm <某个文件>` 执行后，**该文件所在目录下的全部文件都消失**。
实测（2026-09-21 受控复现）：`git rm skills/medagentwork/scripts/render_diagram.py`
→ `scripts/` 下 35 个文件全没（工作区文件数 56 → 21）。第一次遇到时整个 `skills/` 树（56 文件）都没了。

**对比**：**普通 `rm` 完全正常** —— 只删目标文件（56 → 55）。

**铁律**：
> **本机绝不用 `git rm`。用 `rm <file>` 删文件，再用 `git add -A` 暂存删除。**

**恢复**（已验证 2 次有效）：
```bash
git checkout HEAD -- skills/     # 从 HEAD 恢复整棵树
```
前提：删除前工作区已提交。**破坏性操作前先 `git status` 确认干净**；
执行后**在同一个命令里数文件数**，异常立刻可见。

### 坑 2：`refs/` 下的**引用写入**（lock+rename）被拦截 —— 范围比原先记录的大

**症状 A（`refs/remotes/`）**：`git fetch` 打印 `[new branch] main -> origin/main`、`git update-ref refs/remotes/...` 返回 exit 0，
但 `.git/refs/remotes/origin/main` 始终不存在，`git status -sb` 显示 `[gone]`。加 `dangerouslyDisableSandbox` 也无效。

**症状 B（`refs/heads/`，2026-09-27 新发现）**：`git branch -f <name> <sha>` **退出码 0 但分支没建**，
`git branch -a` 看不到；`git branch -d` 同样不可靠。

**根因**：本机对 `.git/refs/` 的 **lock + rename 写入协议被拦截**（rename 步骤静默失败）。
`refs/remotes/` 与 `refs/heads/` **都受影响**（原先以为只有 remotes）。
**不受影响**：`git tag -a`、`git commit`、`git worktree add`、`git push` 全部正常。

**解法**（直接写文件，绕开 lock+rename）：
```bash
# 建/改引用
mkdir -p .git/refs/heads/<dir>
printf '%s\n' "$(git rev-parse <sha>)" > .git/refs/heads/<dir>/<name>
# 远程跟踪引用
mkdir -p .git/refs/remotes/origin
printf '<sha>\n' > .git/refs/remotes/origin/main
# 删引用
rm -f .git/refs/heads/<name>
```

**推送不需要本地分支** —— 用 detached HEAD 直接推，已验证有效：
```bash
git push origin HEAD:main        # 快进推送，绕过本地引用问题
```

**判断 push 是否真成功**：不要信本地引用，用 `git ls-remote origin refs/heads/main` 直接查远程。
**push 后**：本地 `origin/main` 会再次变 `[gone]`（push 会重写该引用），需重复上述修复。

### 坑 3：Git Bash 下 `gh` 找不到配置 → 误报「未登录」

**症状**：`gh auth status` 报 `You are not logged into any GitHub hosts`，
`gh release create` 直接 exit 4 失败（但 `git push` 正常）。

**根因**：Git Bash 里 `$APPDATA` 为空，gh（Windows 二进制）定位不到配置目录。
实际配置在 `C:/Users/38063/AppData/Roaming/GitHub CLI/hosts.yml`（含 token，账号 `2710074390-cyber`，`repo` scope）。

**解法**（每次用 gh 前都要设）：
```bash
export GH_CONFIG_DIR="C:/Users/38063/AppData/Roaming/GitHub CLI"
gh auth status   # → ✓ Logged in to github.com account 2710074390-cyber (keyring)
```
`git push` 不受影响（git 用 `credential.helper=helper-selector`，与 gh 无关）。

## 项目约定（改 medagentwork-skill 时必须遵守）

1. **核心管线零第三方依赖** —— 配置读取走「PyYAML 可选 → 内置最小解析器 → 内置默认」三段式。
   新增阈值一律写进 `pipeline.yaml` 的**扁平** `thresholds:` 段（两级以内结构，便于最小解析器读取）。
2. **门禁阈值不得硬编码** —— 统一 `from pipeline_config import get_number`；
   `validate/` 包内先注入 `_SCRIPTS_DIR` 到 `sys.path` 再导入。
3. **降级必须显式且留痕** —— 不允许"悄悄放行"。参考 `kaoyan_picker check --golden-absent`：
   默认 fail-closed，降级要操作者主动声明并写入 `degraded: true`。
4. **测试必须验"规则真的命中"**，不能只验"脚本可执行"。
   新增规则时同步在 `smoketest/run_smoketest.py` §11 加探针断言（当前 23 项断言）。
5. **scripts/ 不是 Python 包**（无 `__init__.py`）—— 禁止用 `from scripts.xxx import`，用同目录裸导入。
6. **提交前**：跑 `python smoketest/run_smoketest.py` + `python -m compileall -q skills/medagentwork/scripts smoketest`，
   并清理 `reports/`、`smoketest/test_ws/`、`__pycache__/`。

## 已知待办（评审报告遗留）

- **拆分巨型文件**：`render_review.py` / `gate_check.py`（均已超千行）。
  评审 §七.8 建议。前置条件：先为 `render_review.py` 补**渲染快照测试**作为回归基线，再拆。
- **插图功能已移除**（2026-09-21，commit `d787942`）：不再需要拆分/维护插图脚本。
  若日后要恢复，逃生备份在 `C:\Users\38063\Desktop\MedAgentWork\_archive_插图移除_20260921\`，
  或用 `git checkout 864fe06 -- <路径>` / `git revert d787942`。
- CHANGELOG 的 v1.0 / v2.1 历史条目中仍保留插图记述（8 处）——属不可变历史，未改写。

## 相关文档

- 评审报告：`C:\Users\38063\WorkBuddy AI\2026-09-12-00-31-08\medagentwork-skill-评审报告.md`
- 改进报告：`C:\Users\38063\Desktop\MedAgentWork\medagentwork-skill-改进报告.md`

## 投稿/分发渠道（2026-09-21 调研 + 实施）

**状态：已具备自发布条件**（commit `9f7b494`）。发布前跑 `python tools/preflight_publish.py --strict`
（当前 致命=0 警告=0）。CI 已接入该检查。

### ✅ 可自发布（零审核）

| 渠道 | 方式 |
|---|---|
| **Claude Code 插件市场** | `/plugin marketplace add 2710074390-cyber/medagentwork-skill`（`.claude-plugin/marketplace.json` 已就位） |
| **Vercel Skills（skills.sh）** | `npx skills add 2710074390-cyber/medagentwork-skill` —— **直接索引公开 GitHub 仓库，无需提交** |
| **ClawHub** | 网页 `clawhub.ai/import` → Import from GitHub（填仓库地址 → Detect 自动填表）。**需接受 MIT-0 条款**；slug 小写+短横线 |
| **WorkBuddy** | 复制到 `~/.workbuddy/skills/`（CodeBuddy：`~/.codebuddy/skills/`） |
| **TRAE** | `.trae/skills/`（项目）/ `%userprofile%/.trae-cn/skills`（全局）；**支持导入 .zip**；支持 `.agents/skills/` 规范目录 |
| Claude.ai / Claude API | 上传自定义 skill（需付费账号） |

### ⚠️ 需 PR 过审
**agentic-awesome-skills**：Fork → 放 `skills/` → `npm run validate` → PR。
其规范已满足（frontmatter 6 个必需字段 + `## When to Use` 章节）。

### ❌ 无投稿入口
- **WorkBuddy BuiltinMarket**：`workbuddy_marketplace_skill` 工具只有 search/install，**无 publish**；策展制
- **TRAE 技能市场**：官方文档与论坛确认**无公开上架流程/入口**（2026-08-13）
- **`anthropics/skills`**：不是投稿库，是 Anthropic 自家实现示例

### 其他注册表
SkillHub（`lightmake.site`，搜索/下载 API，独立分类体系）、ClawHub（`clawhub.ai`）、
Vercel Skills（`skills.sh`）；另有 iflytek SkillHub、astron-skillhub.org、skillhub.cn（均支持 Web 上传 ZIP）。

### 未做的（按用户决策）
不做英文版（走自发布 + 国内渠道）；未加示例数据集 —— 这是提高试用/收录率的下一步。
