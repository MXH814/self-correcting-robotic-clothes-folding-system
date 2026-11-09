param([Parameter(Mandatory=$true)][string]$OutputRoot,
      [ValidateSet('official-missing-inputs','missing-inputs')][string]$Scenario = 'official-missing-inputs')
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $OutputRoot) { throw 'Use a new output directory to preserve existing evidence.' }
$oldFiperScenario = $env:ROBOTICS_FIPER_PRE_SCENARIO
try {
    $env:ROBOTICS_FIPER_PRE_SCENARIO = $Scenario
    try {
        & (Join-Path $PSScriptRoot 'run_local.ps1') -Stage fold-recovery -Headless -OutputRoot $OutputRoot
    } catch {
        $records = @(Get-ChildItem -LiteralPath $OutputRoot -Filter 'full-fold-recovery.json' -Recurse -File -ErrorAction SilentlyContinue)
        if ($records.Count -ne 1) { throw }
        $record = Get-Content -Raw -LiteralPath $records[0].FullName | ConvertFrom-Json
        if ($record.final_control_state -ne 'HELP_REQUESTED_AUTOMATIC_DISPATCH_DISABLED' -or
            $record.fiper_report.status -ne 'UNKNOWN' -or
            $record.dispatch_count_at_help -ne $record.dispatch_count_at_exit -or
            $record.recovery_attempts -ne 0) { throw }
        if ($Scenario -eq 'official-missing-inputs' -and
            ($record.pre_scenario -ne 'C_official_missing_package' -or
             $record.detection_entry -ne 'OfficialPreAdapter/DetectionRuntime')) { throw }
        Write-Output ('EXPECTED_UNKNOWN_EXIT ' + $records[0].DirectoryName)
    }
} finally {
    $env:ROBOTICS_FIPER_PRE_SCENARIO = $oldFiperScenario
}
