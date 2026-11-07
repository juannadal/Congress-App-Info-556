# One-time setup of the INFO 556 Congress app on Windows.
# Run by double-clicking windows\setup_windows.bat (or: powershell -ExecutionPolicy Bypass -File windows\setup_windows.ps1).
# The venv and the dense index go in %USERPROFILE%\.info556, outside Google Drive. Safe to rerun.
$ErrorActionPreference = "Stop"
$Project = Split-Path -Parent $PSScriptRoot
$Base = Join-Path $env:USERPROFILE ".info556"
$Venv = Join-Path $Base "venv"
$Py = Join-Path $Venv "Scripts\python.exe"
$env:PYTHONUTF8 = "1"
Set-Location $Project

function Step($msg) { Write-Host "`n== $msg ==" -ForegroundColor Cyan }
function Check($what) { if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE)" } }

Step "Finding Python 3.10-3.13"
$BasePy = $null
foreach ($v in "3.11", "3.12", "3.13", "3.10") {
    try { & py "-$v" -c "import sys" 2>$null; if ($LASTEXITCODE -eq 0) { $BasePy = @("py", "-$v"); break } } catch {}
}
if (-not $BasePy -and (Test-Path "C:\Python311\python.exe")) { $BasePy = @("C:\Python311\python.exe") }
if (-not $BasePy) { throw "No Python 3.10-3.13 found. Install Python 3.11 from python.org, then rerun." }
Write-Host "Using: $($BasePy -join ' ')"

if (-not (Test-Path $Py)) {
    Step "Creating venv at $Venv"
    New-Item -ItemType Directory -Force -Path $Base | Out-Null
    $exe = $BasePy[0]; $rest = @($BasePy | Select-Object -Skip 1)
    & $exe @rest -m venv $Venv; Check "Creating the venv"
}

Step "Installing packages (CPU PyTorch first; this takes a few minutes)"
& $Py -m pip install --upgrade pip; Check "pip upgrade"
& $Py -m pip install torch --index-url https://download.pytorch.org/whl/cpu; Check "Installing torch"
& $Py -m pip install -r requirements.txt; Check "Installing requirements.txt"

Step "Downloading NLTK stopwords"
& $Py -c "import certifi, os, nltk; os.environ['SSL_CERT_FILE'] = certifi.where(); nltk.download('stopwords', quiet=True)"; Check "NLTK stopwords"

Step "Building the dense index in $Base\chroma (downloads MiniLM the first time)"
& $Py -c "from retrieval.corpus import load_passages; from retrieval.dense import DenseIndex; DenseIndex(load_passages()).build()"; Check "Building the dense index"

Step "Quick check"
& $Py -c "from retrieval.corpus import load_passages; from retrieval.hybrid import HybridIndex; HybridIndex(load_passages()).search('former prosecutor', k=3, where={'state_code': 'CA'})"; Check "Test search"

Write-Host "`nSetup done. Start the app with windows\start_app.bat" -ForegroundColor Green
