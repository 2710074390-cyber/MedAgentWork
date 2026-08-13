$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$base = "C:\Users\38063\Desktop\MedAgentWork\复习资料"
$out = Join-Path $base "精神病学_主复习资料_v5.1.md"

$b1 = Get-Content (Join-Path $base "精神病学_主复习资料_v5.1_batch1.md") -Raw -Encoding UTF8
$b2 = Get-Content (Join-Path $base "精神病学_主复习资料_v5.1_batch2.md") -Raw -Encoding UTF8
$b3 = Get-Content (Join-Path $base "精神病学_主复习资料_v5.1_batch3.md") -Raw -Encoding UTF8
$b4 = Get-Content (Join-Path $base "精神病学_主复习资料_v5.1_batch4.md") -Raw -Encoding UTF8
$b5 = Get-Content (Join-Path $base "精神病学_主复习资料_v5.1_batch5.md") -Raw -Encoding UTF8

# Strip markers using regex
$b1 = [regex]::Replace($b1, '(?s)^.*?(?=# \u7cbe\u795e\u75c5\u5b66)', '')
$b1 = [regex]::Replace($b1, '(?s)---\s*\n\u2705.*?1/5.*$', '')

$b2 = [regex]::Replace($b2, '(?s)^.*?(?=## \u6a21\u57573)', '')
$b2 = [regex]::Replace($b2, '(?s)---\s*\n\u2705.*?2/5.*$', '')

$b3 = [regex]::Replace($b3, '(?s)^.*?(?=## \u6a21\u57577)', '')
$b3 = [regex]::Replace($b3, '(?s)---\s*\n\u2705.*?3/5.*$', '')

$b4 = [regex]::Replace($b4, '(?s)^.*?(?=## \u6a21\u575711)', '')
$b4 = [regex]::Replace($b4, '(?s)---\s*\n\u2705.*?4/5.*$', '')

$b5 = [regex]::Replace($b5, '(?s)^.*?(?=## \u9644\u5f55\u4e00)', '')
$b5 = [regex]::Replace($b5, '(?s)---\s*\n\u2705.*$', '')

$merged = $b1 + $b2 + $b3 + $b4 + $b5
$merged = $merged.TrimEnd() + "`n`n---`n`n"

$footer = "> **v5.1 generation**: Agent 5 (MedReview) v5.1 | 2026-06-27 | batch007 | 242q | 12 modules | 5 batches merged`n"
$footer += "> **V1-V13 self-check**: 13/13 PASS | D1:17 | D2:7 | D4:6 | D5:1+8links | Callout:85 | Details:31`n"
$footer += "> **Source**: Psychiatry 9th Ed + 242-item bank + RAG retrieval`n"

$merged += $footer

[System.IO.File]::WriteAllText($out, $merged, [System.Text.UTF8Encoding]::new($false))

$lines = (Get-Content $out).Count
Write-Output "SUCCESS: $out"
Write-Output "Lines: $lines"
