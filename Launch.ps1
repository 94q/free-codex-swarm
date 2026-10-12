$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    & (Join-Path $PSScriptRoot 'install_requirements.bat') --no-pause
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
& $python main.py @args
