# Git Commit Quality Gate Check
# Exit 0 = allow commit, Exit 2 = block commit

$ResultsDir = ".claude/results"
$TesterFile = Join-Path $ResultsDir "tester-result.txt"
$QualityFile = Join-Path $ResultsDir "quality-result.txt"

$testerExists = Test-Path $TesterFile -PathType Leaf
$qualityExists = Test-Path $QualityFile -PathType Leaf

if (-not $testerExists -or -not $qualityExists) {
    Write-Output "=============================================="
    Write-Output "  QUALITY GATE: BLOCKED - Missing pass markers"
    Write-Output "=============================================="
    Write-Output ""
    Write-Output "  Both tester-result.txt and quality-result.txt"
    Write-Output "  must exist in .claude/results/ before commit."
    Write-Output ""
    Write-Output "  Run gitcommit-agent first to generate them."
    Write-Output "=============================================="
    exit 2
}

$testerResult = (Get-Content $TesterFile -First 1).Trim()
$qualityResult = (Get-Content $QualityFile -First 1).Trim()

if ($testerResult -eq "PASS" -and $qualityResult -eq "PASS") {
    Write-Output "=============================================="
    Write-Output "  QUALITY GATE: PASS"
    Write-Output "=============================================="
    Write-Output "  Unit tests  : PASS"
    Write-Output "  Code quality: PASS"
    Write-Output "=============================================="
    exit 0
}
else {
    Write-Output "=============================================="
    Write-Output "  QUALITY GATE: BLOCKED"
    Write-Output "=============================================="
    Write-Output ""
    Write-Output "  [Unit tests] $testerResult"
    Write-Output "  ----------------------------------------"
    Get-Content $TesterFile | ForEach-Object { Write-Output "  $_" }
    Write-Output ""
    Write-Output "  [Code quality] $qualityResult"
    Write-Output "  ----------------------------------------"
    Get-Content $QualityFile | ForEach-Object { Write-Output "  $_" }
    Write-Output ""
    Write-Output "  Fix the issues above, then re-run gitcommit-agent."
    Write-Output "=============================================="
    exit 2
}
