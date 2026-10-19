<#
.SYNOPSIS
  MedAgentWork · 一键部署到 Cloudflare Pages（绕开本地大文件超限问题）

.DESCRIPTION
  GitHub Actions 的部署在干净 checkout 上运行；而本地工作区含有被 .gitignore
  排除的大文件（如 知识库素材/cmexam/bridges.npz 100MB），直接 `wrangler pages
  deploy` 会因 Pages 单文件 25MiB 上限失败。

  本脚本复刻 CI 环境：
    1) 从指定 commit（默认 HEAD）创建临时 git worktree —— 只含 git 跟踪文件
    2) 在 worktree 内执行 `wrangler pages deploy --branch <Branch>`
    3) 无论成败，finally 中清理临时 worktree

  注意：只有「已提交」的内容会被部署；未提交的修改请先 commit。

.EXAMPLE
  powershell scripts\deploy_site.ps1                  # 部署 HEAD 到 main（生产）
  powershell scripts\deploy_site.ps1 -Branch main -Keep   # 失败后保留 worktree 排查

.NOTES
  依赖：wrangler CLI（npm i -g wrangler@4.121.0 --registry=https://registry.npmmirror.com）
  部署配置来源：仓库根目录 wrangler.toml（name / pages_build_output_dir / VISITS KV 绑定）
#>
param(
  [string]$Branch = "main",
  [string]$Commit = "HEAD",
  [switch]$Keep,
  [switch]$Force,
  # -AllowAhead：允许在「本地领先 origin/<Branch>」时部署（默认拒绝）。
  # 见 HC-21：本地未推送的提交部署出去，会被他人/CI 从 origin 发起的部署顶掉
  # （batch040 实证：部署后 3 分钟被更晚的生产部署覆盖，线上回到旧版）。
  [switch]$AllowAhead
)

$ErrorActionPreference = "Stop"
$repo    = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$worktree = Join-Path (Split-Path $repo -Parent) "_medagentwork-deploy"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

# ---------- 0) 前置检查 ----------
if (-not (Get-Command wrangler -ErrorAction SilentlyContinue)) {
  Write-Host "[X] 未找到 wrangler 命令。请先执行：" -ForegroundColor Red
  Write-Host "    npm i -g wrangler@4.121.0 --registry=https://registry.npmmirror.com" -ForegroundColor Red
  exit 1
}
if (-not (Test-Path (Join-Path $repo ".git"))) {
  Write-Host "[X] 不是 git 仓库：$repo" -ForegroundColor Red
  exit 1
}
if (-not (Test-Path (Join-Path $repo "wrangler.toml"))) {
  Write-Host "[X] 缺少 wrangler.toml（Pages 配置源）" -ForegroundColor Red
  exit 1
}

# ---------- 0.5) 回退保护闸（2026-09-28）----------
# 本脚本部署的是**本地提交**（默认 HEAD）。若本地落后于 origin/<Branch>，
# 部署就会把线上打回旧版 —— 这是真事故，不是假设：
# 2026-09-28 本地 main 落后 6 个提交时，一次本地部署会把
# 「大四上分区下载 404 修复」与「人工导出版 PDF」一起退回成脚本打印件。
# 故默认拒绝（fail-closed）；确需强行部署时显式加 -Force。
$remoteSha = $null
git -C $repo fetch origin $Branch --quiet 2>$null
if ($LASTEXITCODE -eq 0) {
  $remoteSha = (git -C $repo rev-parse FETCH_HEAD 2>$null)
  if ($remoteSha) { $remoteSha = $remoteSha.Trim() }
}
$localSha = (git -C $repo rev-parse $Commit 2>$null)
if ($localSha) { $localSha = $localSha.Trim() }

if (-not $remoteSha -or -not $localSha) {
  # 查不到就不能放行 —— fail-closed，与仓库其它门禁一致
  if ($Force) {
    Write-Host "[!] 取不到 origin/$Branch 或本地 $Commit（离线 / git 不在 PATH）—— 已加 -Force，继续部署。" -ForegroundColor Yellow
  } else {
    Write-Host "[X] 拒绝部署：无法确认本地是否落后 origin/$Branch。" -ForegroundColor Red
    Write-Host "    原因可能是离线，或 git 不在 PATH（本脚本需要 git 建 worktree，本来就依赖它）。" -ForegroundColor Red
    Write-Host "    确认本地不落后、或就是要拿本地版本覆盖线上时，加 -Force。" -ForegroundColor Red
    exit 2
  }
} else {
  $behind = [int](git -C $repo rev-list --count "$localSha..$remoteSha" 2>$null)
  $ahead  = [int](git -C $repo rev-list --count "$remoteSha..$localSha" 2>$null)
  if ($localSha -ne $remoteSha) {
    Write-Host ("[!] 本地 {0} = {1}   vs   origin/{2} = {3}   （落后 {4} / 超前 {5}）" -f `
      $Commit, $localSha.Substring(0,7), $Branch, $remoteSha.Substring(0,7), $behind, $ahead) -ForegroundColor Yellow
  }
  if ($behind -gt 0 -and -not $Force) {
    Write-Host "[X] 拒绝部署：本地落后 origin/$Branch $behind 个提交，部署会把线上打回旧版。" -ForegroundColor Red
    Write-Host "    先把本地与远程对齐（git merge origin/$Branch，或 git checkout origin/$Branch 部署线上版）；" -ForegroundColor Red
    Write-Host "    确实要拿本地版本覆盖线上时，加 -Force。" -ForegroundColor Red
    exit 2
  }
  # ---------- HC-21：部署源必须与 origin 同源 ----------
  # 本地领先（ahead>0）说明这些提交还没 push。此时本地部署虽然内容是新的，
  # 但他人/CI 一旦从 origin 部署，就会把线上打回旧版（batch040 事故形态）。
  # 故默认拒绝；先 `git push` 令 ahead=0，再部署。
  if ($ahead -gt 0 -and -not $AllowAhead) {
    Write-Host "[X] 拒绝部署：本地领先 origin/$Branch $ahead 个提交（尚未 push）。" -ForegroundColor Red
    Write-Host "    未 push 的提交一旦部署，会被他人/CI 从 origin 的部署顶掉（HC-21，batch040 事故）。" -ForegroundColor Red
    Write-Host "    正确做法：先 git push，令本地与 origin 同源后再部署。" -ForegroundColor Red
    Write-Host "    确需仅本地部署（会被后续部署覆盖，风险自负）时，加 -AllowAhead。" -ForegroundColor Red
    exit 2
  }
  if ($ahead -gt 0 -and $AllowAhead) {
    Write-Host "[!] 已加 -AllowAhead：本次部署源领先 origin/$Branch $ahead 个提交，后续他人/CI 部署可能把线上顶回旧版。" -ForegroundColor Yellow
  }
}

# ---------- 1) 清理可能残留的旧 worktree ----------
if (Test-Path $worktree) {
  Write-Step "清理残留 worktree: $worktree"
  git -C $repo worktree remove $worktree --force 2>$null
  if (Test-Path $worktree) { Remove-Item -Recurse -Force $worktree -ErrorAction SilentlyContinue }
  git -C $repo worktree prune
}

# ---------- 2) 创建干净 worktree（只含 git 跟踪文件 = CI 场景） ----------
Write-Step "创建干净 worktree（$Commit）..."
git -C $repo worktree add $worktree $Commit
if ($LASTEXITCODE -ne 0) { Write-Host "[X] worktree 创建失败" -ForegroundColor Red; exit 1 }
Write-Host "    worktree: $worktree"

$failed = $false
$stage = $null
try {
  # ---------- 3) 组装站点上传目录（白名单） ----------
  # 背景（2026-10-15）：Cloudflare Pages 的 `wrangler pages deploy` 不识别根目录
  # .assetsignore（该机制仅 Workers 静态资产支持），把 scripts/ question_bank/
  # 中间产物/ 复习资料/ 等「已提交但非站点」文件一并上传，导致站点可直链下载。
  # 故部署前按白名单组装独立上传目录；CI 侧 deploy.yml 采用同一白名单，双通道一致。
  Write-Step "组装站点上传目录（白名单）..."
  $stage = Join-Path (Split-Path $repo -Parent) "_medagentwork-site"
  if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
  New-Item -ItemType Directory -Force -Path $stage | Out-Null
  foreach ($it in @('index.html', '_headers', '_redirects', 'functions', '大三下', '大四上', 'assets', 'sw.js', 'manifest.webmanifest', 'icon-192.png', 'icon-512.png')) {
    $s = Join-Path $worktree $it
    if (Test-Path $s) { Copy-Item $s (Join-Path $stage $it) -Recurse -Force }
  }
  Write-Host "    stage: $stage"

  # ---------- 4) 部署 ----------
  Write-Step "部署到 Cloudflare Pages（--branch $Branch）..."
  Push-Location $repo   # 保持仓库根（读取 wrangler.toml：name / KV 绑定）
  try {
    wrangler pages deploy $stage --branch $Branch
    if ($LASTEXITCODE -ne 0) { throw "wrangler pages deploy 失败（exit $LASTEXITCODE）" }
  } finally {
    Pop-Location
  }
  Write-Host "`n[OK] 部署完成：https://med-review-site.pages.dev" -ForegroundColor Green

  # ---------- 5) 部署后置校验（HC-21 最新性契约） ----------
  # 校验：① 本地 index.html 文案与数据一致；② 线上指纹与本地一致；
  #       ③ 线上「最新 Production 部署的 Source」== 本次提交（防被更晚的部署顶替）。
  Write-Step "部署后置校验（HC-21 站点最新性）..."
  $fresh = Join-Path $repo "scripts\check_site_freshness.py"
  if (Test-Path $fresh) {
    & python $fresh --expect-commit $localSha
    if ($LASTEXITCODE -ne 0) {
      throw "线上最新性校验未通过：可能已被更晚的部署顶替（HC-21）。请核对部署清单并重部署。"
    }
  } else {
    Write-Host "[!] 未找到 scripts/check_site_freshness.py，跳过最新性校验（HC-21 未生效）" -ForegroundColor Yellow
  }
}
catch {
  Write-Host "`n[X] 部署失败：$($_.Exception.Message)" -ForegroundColor Red
  $failed = $true
}
finally {
  if ($stage -and (Test-Path $stage)) {
    Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
  }
  if (-not $Keep) {
    Write-Step "清理 worktree..."
    git -C $repo worktree remove $worktree --force 2>$null
    if (Test-Path $worktree) { Remove-Item -Recurse -Force $worktree -ErrorAction SilentlyContinue }
    git -C $repo worktree prune
  } else {
    Write-Host "  （-Keep：worktree 保留在 $worktree 供排查）" -ForegroundColor Yellow
  }
}

if ($failed) { exit 1 }
