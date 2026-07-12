$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$OUTPUT = Join-Path $ROOT "ssh-audit-skill.zip"

if (Test-Path $OUTPUT) { Remove-Item $OUTPUT -Force }

$fileList = @(
    "SKILL.md",
    "install.ps1",
    "requirements.txt",
    "package.ps1",
    "demo.py",
    "test_shell.py",
    "bin\agent-ssh-run.py",
    "bin\agent-ssh-shell.py",
    "bin\agent-ssh-replay.py",
    "agent_ssh_audit\__init__.py",
    "agent_ssh_audit\client.py",
    "agent_ssh_audit\rules.py",
    "agent_ssh_audit\storage.py",
    "agent_ssh_audit\recorder.py",
    "agent_ssh_audit\replay.py"
)

# 收集 wheels 目录下的 .whl 文件
$wheelsDir = Join-Path $ROOT "wheels"
$wheelsList = @()
if (Test-Path $wheelsDir) {
    Get-ChildItem -Path $wheelsDir -Filter "*.whl" | ForEach-Object {
        $wheelsList += "wheels\" + $_.Name
    }
    Write-Host "Found $($wheelsList.Count) wheel(s) in wheels/" -ForegroundColor Cyan
}

# 收集嵌入式 Python 运行时（python/ 目录所有文件，排除临时文件）
$pythonDir = Join-Path $ROOT "python"
$pythonList = @()
if (Test-Path $pythonDir) {
    $pythonFiles = Get-ChildItem -Path $pythonDir -Recurse -File |
        Where-Object { $_.FullName -notmatch "\\__pycache__\\" }
    foreach ($pf in $pythonFiles) {
        $pythonList += $pf.FullName.Substring($ROOT.Length + 1)
    }
    $pythonSize = [math]::Round(($pythonFiles | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
    Write-Host "Found $($pythonList.Count) files in python/ ($pythonSize MB)" -ForegroundColor Cyan
} else {
    Write-Warning "python/ directory not found, skill will require system Python"
}

$allFiles = $fileList + $wheelsList + $pythonList

Write-Host "SSH Audit Skill - Package" -ForegroundColor Cyan

$missingArr = @()
foreach ($f in $allFiles) {
    $fp = Join-Path $ROOT $f
    if (-not (Test-Path $fp)) {
        $missingArr += $f
    }
}

if ($missingArr.Count -gt 0) {
    Write-Host "Missing files:" -ForegroundColor Red
    foreach ($m in $missingArr) { Write-Host "  $m" -ForegroundColor Red }
    exit 1
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::Open($OUTPUT, "Create")

foreach ($f in $allFiles) {
    $fp = Join-Path $ROOT $f
    $en = $f.Replace("\", "/")
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive, $fp, $en)
}

$entry = $archive.CreateEntry("logs/sessions/.gitkeep")
$entry.Open().Close()

$archive.Dispose()

$sz = [math]::Round((Get-Item $OUTPUT).Length / 1MB, 1)
Write-Host ""
Write-Host "Done: $OUTPUT ($sz MB, $($allFiles.Count) files)" -ForegroundColor Green
