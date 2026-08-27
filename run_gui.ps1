$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }

Push-Location (Join-Path $repositoryRoot "software")
try {
    & $python -m control_app.ui.app
}
finally {
    Pop-Location
}
