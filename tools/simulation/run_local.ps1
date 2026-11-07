param(
    [ValidateSet('engine','garment','fold')][string]$Stage = 'garment',
    [string]$RoboticsRoot = 'E:\Robotics',
    [string]$IsaacRoot = '',
    [string]$ProjectRoot = '',
    [string]$DependencyRoot = '',
    [string]$OutputRoot = '',
    [switch]$Headless,
    [switch]$KeepOpen,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
if ($Headless -and $KeepOpen) { throw 'KeepOpen requires a graphical session.' }
# Resolve against the caller's PowerShell location, before changing directories.
# Unlike Resolve-Path, this also supports an output directory not created yet.
$RoboticsRoot = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($RoboticsRoot)
if (-not $IsaacRoot) { $IsaacRoot = Join-Path $RoboticsRoot 'isaacsim-4.5.0' }
if (-not $ProjectRoot) { $ProjectRoot = Join-Path $RoboticsRoot 'DexGarmentLab' }
if (-not $DependencyRoot) { $DependencyRoot = Join-Path $RoboticsRoot 'python-deps' }
if (-not $OutputRoot) { $OutputRoot = Join-Path $RoboticsRoot 'handoff-results' }
$IsaacRoot = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($IsaacRoot)
$ProjectRoot = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ProjectRoot)
$DependencyRoot = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($DependencyRoot)
$OutputRoot = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputRoot)
$isaacPython = Join-Path $IsaacRoot 'python.bat'
foreach ($required in @($isaacPython, (Join-Path $ProjectRoot 'Env_StandAlone\Fold_Tops_Env.py'), $DependencyRoot)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required path is missing: $required" }
}
Write-Host "Isaac: $IsaacRoot`nProject: $ProjectRoot`nExtra dependencies: $DependencyRoot`nSmoke output: $OutputRoot"
Write-Host 'Fold output is written by upstream under ProjectRoot/Data/Fold_Tops, not OutputRoot.'
if ($CheckOnly) { Write-Host 'PATH_CHECK_PASSED (paths only; no simulator or imports tested)'; return }
$names = @('PYTHONPATH','HF_HOME','PIP_CACHE_DIR','ROBOTICS_PROJECT_ROOT','ROBOTICS_OUTPUT_ROOT','ROBOTICS_HEADLESS','ROBOTICS_KEEP_OPEN')
$old = @{}
foreach ($name in $names) { $old[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    $env:PYTHONPATH = "$DependencyRoot;$ProjectRoot;$($old['PYTHONPATH'])"
    $env:HF_HOME = Join-Path $RoboticsRoot 'cache\huggingface'
    $env:PIP_CACHE_DIR = Join-Path $RoboticsRoot 'cache\pip'
    $env:ROBOTICS_PROJECT_ROOT = $ProjectRoot
    $env:ROBOTICS_OUTPUT_ROOT = $OutputRoot
    $env:ROBOTICS_HEADLESS = if ($Headless) { '1' } else { '0' }
    $env:ROBOTICS_KEEP_OPEN = if ($KeepOpen) { '1' } else { '0' }
    Push-Location -LiteralPath $ProjectRoot
    try {
        if ($Stage -eq 'fold') {
            & $isaacPython -u (Join-Path $PSScriptRoot 'run_fold_local.py') --garment_random_flag False --record_video_flag False --data_collection_flag True
        } else {
            $arguments = @('-u', (Join-Path $PSScriptRoot 'smoke_test.py'), '--stage', $Stage)
            if ($Headless) { $arguments += '--headless' }
            if ($KeepOpen) { $arguments += '--keep-open' }
            & $isaacPython @arguments
        }
        if ($LASTEXITCODE -ne 0) { throw "Simulation exited with code $LASTEXITCODE; inspect its console and output." }
    } finally { Pop-Location }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $old[$name], 'Process') }
}
