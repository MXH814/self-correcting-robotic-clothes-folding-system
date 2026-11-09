param(
    [Parameter(Mandatory=$true)][string]$Package,
    [Parameter(Mandatory=$true)][string]$Encoder,
    [Parameter(Mandatory=$true)][string]$OutputRoot,
    [Parameter(Mandatory=$true)][string]$AuditPython
)
$ErrorActionPreference='Stop'
if (Test-Path -LiteralPath $OutputRoot) { throw 'Use a new paired output directory.' }
New-Item -ItemType Directory -Path $OutputRoot | Out-Null
$results=@()
foreach ($scenario in @('normal-a','fault-b')) {
    $caseOutput=Join-Path $OutputRoot $scenario
    & (Join-Path $PSScriptRoot 'run_official_ab.ps1') -Scenario $scenario -SeparateSleeves -Package $Package -Encoder $Encoder -OutputRoot $caseOutput *> (Join-Path $OutputRoot ($scenario+'.log'))
    $trials=@(Get-ChildItem -LiteralPath $caseOutput -Directory -Filter 'fold-recovery-*')
    if ($trials.Count -ne 1) { throw 'Expected one recorded trial.' }
    $auditPath=Join-Path $OutputRoot ($scenario+'-audit.json')
    & $AuditPython (Join-Path $PSScriptRoot 'verify_official_ab.py') $trials[0].FullName --output $auditPath *> (Join-Path $OutputRoot ($scenario+'-audit.log'))
    if ($LASTEXITCODE -ne 0) { throw "Audit failed for $scenario" }
    $audit=Get-Content -LiteralPath $auditPath -Raw | ConvertFrom-Json
    $results+=$audit
    $results | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $OutputRoot 'pair-results.json') -Encoding utf8
    Write-Output ("CASE_RESULT $scenario expected="+$audit.expected_case_automatic_checks_passed)
    if (-not $audit.expected_case_automatic_checks_passed) { throw "Expected behavior was not observed for $scenario" }
}
Write-Output 'BOTH_CASES_COMPLETED_AND_VERIFIED'
