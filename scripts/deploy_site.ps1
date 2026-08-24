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
  [switch]$Keep
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
try {
  # ---------- 3) 部署 ----------
  Write-Step "部署到 Cloudflare Pages（--branch $Branch）..."
  Push-Location $worktree
  try {
    wrangler pages deploy --branch $Branch
    if ($LASTEXITCODE -ne 0) { throw "wrangler pages deploy 失败（exit $LASTEXITCODE）" }
  } finally {
    Pop-Location
  }
  Write-Host "`n[OK] 部署完成：https://med-review-site.pages.dev" -ForegroundColor Green
}
catch {
  Write-Host "`n[X] 部署失败：$($_.Exception.Message)" -ForegroundColor Red
  $failed = $true
}
finally {
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
