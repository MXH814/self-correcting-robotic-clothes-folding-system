param(
    [Parameter(Mandatory=$true)][ValidateSet('normal-a','fault-b')][string]$Scenario,
    [Parameter(Mandatory=$true)][string]$Package,
    [Parameter(Mandatory=$true)][string]$Encoder,
    [Parameter(Mandatory=$true)][string]$OutputRoot,
    [switch]$SeparateSleeves
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $OutputRoot) { throw 'Use a new output directory.' }
foreach ($path in @((Join-Path $Package 'manifest.json'),(Join-Path $Package 'detector.pt'),$Encoder)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing detector input: $path" }
}
$names = @('ROBOTICS_FIPER_PRE_SCENARIO','ROBOTICS_PRE_PACKAGE','ROBOTICS_PRE_ENCODER','ROBOTICS_PRE_NORMAL_COLLECTION','ROBOTICS_PRE_SEPARATE_SLEEVES')
$old = @{}
foreach ($name in $names) { $old[$name] = [Environment]::GetEnvironmentVariable($name,'Process') }
try {
    $env:ROBOTICS_FIPER_PRE_SCENARIO=$Scenario
    $env:ROBOTICS_PRE_PACKAGE=(Resolve-Path -LiteralPath $Package).Path
    $env:ROBOTICS_PRE_ENCODER=(Resolve-Path -LiteralPath $Encoder).Path
    $env:ROBOTICS_PRE_NORMAL_COLLECTION='0'
    $env:ROBOTICS_PRE_SEPARATE_SLEEVES=if ($SeparateSleeves) { '1' } else { '0' }
    New-Item -ItemType Directory -Path $OutputRoot | Out-Null
    [ordered]@{
        schema='official-ab-invocation/1'
        scenario=$Scenario
        separate_sleeves=[bool]$SeparateSleeves
        package=$env:ROBOTICS_PRE_PACKAGE
        encoder=$env:ROBOTICS_PRE_ENCODER
        output=$ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputRoot)
        recorded_utc=[DateTime]::UtcNow.ToString('o')
        launcher_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
        checkpoint_sha256=(Get-FileHash -LiteralPath (Join-Path $Package 'detector.pt') -Algorithm SHA256).Hash.ToLowerInvariant()
        encoder_sha256=(Get-FileHash -LiteralPath $Encoder -Algorithm SHA256).Hash.ToLowerInvariant()
    } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $OutputRoot 'ab-invocation.json') -Encoding utf8
    try {
        & (Join-Path $PSScriptRoot 'run_local.ps1') -Stage fold-recovery -Headless -OutputRoot $OutputRoot
    } catch {
        $records=@(Get-ChildItem -LiteralPath $OutputRoot -Filter full-fold-recovery.json -File -Recurse -ErrorAction SilentlyContinue)
        if ($records.Count -ne 1) { throw }
        $record=Get-Content -LiteralPath $records[0].FullName -Raw | ConvertFrom-Json
        if ($record.pre_scenario -ne $Scenario -or
            $record.final_control_state -ne 'HELP_REQUESTED_AUTOMATIC_DISPATCH_DISABLED' -or
            $record.dispatch_count_at_help -ne $record.dispatch_count_at_exit) { throw }
        Write-Output ('OFFICIAL_AB_HELP_OUTCOME '+$records[0].DirectoryName)
    }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name,$old[$name],'Process') }
}
