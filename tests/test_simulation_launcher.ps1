# Lightweight Windows regression test. Uses a fake python.bat; Isaac Sim is not started.
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot '..\tools\simulation\run_local.ps1'
$launcher = (Resolve-Path -LiteralPath $launcher).Path
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('launcher-test-' + [guid]::NewGuid().ToString('N'))
$names = @('PYTHONPATH','HF_HOME','PIP_CACHE_DIR','ROBOTICS_PROJECT_ROOT','ROBOTICS_OUTPUT_ROOT','ROBOTICS_HEADLESS','ROBOTICS_KEEP_OPEN','ROBOTICS_PROBE_MARKER','HANDOFF_CAPTURE','HANDOFF_EXIT','HANDOFF_WRITE_MARKER')
$original = @{}
foreach ($name in $names) { $original[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }

function Assert-Equal($actual, $expected, $label) {
    if ($actual -cne $expected) { throw "$label mismatch. Expected [$expected], got [$actual]" }
}
function Make-Fixture($root, $isaacName, $projectName, $depsName) {
    $isaac = Join-Path $root $isaacName
    $project = Join-Path $root $projectName
    $deps = Join-Path $root $depsName
    New-Item -ItemType Directory -Force -Path $isaac,(Join-Path $project 'Env_StandAlone'),$deps | Out-Null
    Set-Content -LiteralPath (Join-Path $project 'Env_StandAlone\Fold_Tops_Env.py') -Value '# fixture' -Encoding Ascii
    @'
@echo off
> "%HANDOFF_CAPTURE%" echo CWD=%CD%
>> "%HANDOFF_CAPTURE%" echo PYTHONPATH=%PYTHONPATH%
>> "%HANDOFF_CAPTURE%" echo HF_HOME=%HF_HOME%
>> "%HANDOFF_CAPTURE%" echo PIP_CACHE_DIR=%PIP_CACHE_DIR%
>> "%HANDOFF_CAPTURE%" echo ROBOTICS_PROJECT_ROOT=%ROBOTICS_PROJECT_ROOT%
>> "%HANDOFF_CAPTURE%" echo ROBOTICS_OUTPUT_ROOT=%ROBOTICS_OUTPUT_ROOT%
>> "%HANDOFF_CAPTURE%" echo ROBOTICS_HEADLESS=%ROBOTICS_HEADLESS%
>> "%HANDOFF_CAPTURE%" echo ROBOTICS_KEEP_OPEN=%ROBOTICS_KEEP_OPEN%
if "%HANDOFF_WRITE_MARKER%"=="1" > "%ROBOTICS_PROBE_MARKER%" echo fixture
exit /b %HANDOFF_EXIT%
'@ | Set-Content -LiteralPath (Join-Path $isaac 'python.bat') -Encoding Ascii
}
function Check-Capture($project, $deps, $robotics, $output, $priorPythonPath) {
    $lines = Get-Content -LiteralPath $env:HANDOFF_CAPTURE
    foreach ($line in @("CWD=$project", "PYTHONPATH=$deps;$project;$priorPythonPath", "HF_HOME=$robotics\cache\huggingface", "PIP_CACHE_DIR=$robotics\cache\pip", "ROBOTICS_PROJECT_ROOT=$project", "ROBOTICS_OUTPUT_ROOT=$output", 'ROBOTICS_HEADLESS=1', 'ROBOTICS_KEEP_OPEN=0')) {
        if ($line -notin $lines) { throw "Missing expected fixture output: $line" }
    }
}
try {
    New-Item -ItemType Directory -Path $fixture | Out-Null
    $root = Join-Path $fixture 'robotics root with spaces'
    Make-Fixture $root 'isaacsim-4.5.0' 'DexGarmentLab' 'python-deps'
    Make-Fixture $fixture 'other isaac' 'other project' 'other deps'
    $env:HANDOFF_CAPTURE = Join-Path $fixture 'captured.txt'
    $env:HANDOFF_EXIT = '0'
    foreach ($name in $names[0..6]) { [Environment]::SetEnvironmentVariable($name, "original-$name", 'Process') }
    Push-Location -LiteralPath $fixture
    try {
        $cwd = (Get-Location).Path
        # Reproduce the reported relative RoboticsRoot, including a space in the path.
        & $launcher -RoboticsRoot '.\robotics root with spaces' -Stage engine -Headless -CheckOnly
        if (Test-Path -LiteralPath $env:HANDOFF_CAPTURE) { throw 'CheckOnly launched the fixture' }
        & $launcher -RoboticsRoot '.\robotics root with spaces' -Stage engine -Headless
        Check-Capture (Join-Path $root 'DexGarmentLab') (Join-Path $root 'python-deps') $root (Join-Path $root 'handoff-results') 'original-PYTHONPATH'
        Push-Location -LiteralPath $root
        try {
            & $launcher -RoboticsRoot '.' -Stage engine -Headless
            Check-Capture (Join-Path $root 'DexGarmentLab') (Join-Path $root 'python-deps') $root (Join-Path $root 'handoff-results') 'original-PYTHONPATH'
        } finally { Pop-Location }
        # Explicit relative overrides are relative to the caller, including a nonexistent output.
        $output = Join-Path $fixture 'new output\nested'
        & $launcher -RoboticsRoot '.\robotics root with spaces' -IsaacRoot '.\other isaac' -ProjectRoot '.\other project' -DependencyRoot '.\other deps' -OutputRoot '.\new output\nested' -Stage fold -Headless
        Check-Capture (Join-Path $fixture 'other project') (Join-Path $fixture 'other deps') $root $output 'original-PYTHONPATH'
        if (Test-Path -LiteralPath $output) { throw 'Launcher unexpectedly created output in fake run' }
        # Failure after Push-Location must restore cwd and every modified environment variable.
        $env:HANDOFF_EXIT = '7'
        $caught = $false
        try { & $launcher -RoboticsRoot '.\robotics root with spaces' -Stage engine -Headless } catch { $caught = $_.Exception.Message -like '*code 7*' }
        if (-not $caught) { throw 'Expected the fixture exit code 7 to fail the launcher' }
        # A zero exit from Isaac is not proof that a sample was written.
        $env:HANDOFF_EXIT = '0'
        $env:HANDOFF_WRITE_MARKER = '0'
        $env:ROBOTICS_PROBE_MARKER = 'prior-marker'
        $caught = $false
        try { & $launcher -RoboticsRoot '.\robotics root with spaces' -Stage runtime-io -Headless } catch { $caught = $_.Exception.Message -like '*sample was not completed*' }
        if (-not $caught) { throw 'Expected a missing completion marker to fail the launcher' }
        Assert-Equal $env:ROBOTICS_PROBE_MARKER 'prior-marker' 'marker environment after failure'
        $env:HANDOFF_WRITE_MARKER = '1'
        & $launcher -RoboticsRoot '.\robotics root with spaces' -Stage runtime-io -Headless
        Assert-Equal $env:ROBOTICS_PROBE_MARKER 'prior-marker' 'marker environment after success'
        Assert-Equal (Get-Location).Path $cwd 'working directory'
        foreach ($name in $names[0..6]) { Assert-Equal ([Environment]::GetEnvironmentVariable($name, 'Process')) "original-$name" $name }
        Write-Host 'SIMULATION_LAUNCHER_TESTS_PASSED'
    } finally { Pop-Location }
} finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $original[$name], 'Process') }
    if (Test-Path -LiteralPath $fixture) { Remove-Item -LiteralPath $fixture -Recurse -Force }
}
