#Requires -RunAsAdministrator
<#
.SYNOPSIS
    SSH 审计技能包安装脚本
.DESCRIPTION
    一键完成：
    1. 检测系统 Python 3（自动安装指引）
    2. 安装 paramiko 依赖
    3. 设置 AGENT_SSH_AUDIT_HOME 环境变量（优先 Machine 级，失败自动降级 User 级）
    4. 创建 logs 目录结构
    5. 初始化 credentials.txt 模板
    6. 验证安装完整性

    不需要管理员权限（Machine 级写入失败时自动降级 User 级）。
.NOTES
    pip 依赖：paramiko（SSH 客户端）
#>
param(
    [switch]$Uninstall  # 卸载：移除环境变量
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2

# === 颜色输出 ===
function Write-Step($msg) { Write-Host "  [+] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [!] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "  [X] $msg" -ForegroundColor Red }

$INSTALL_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SSH 审计技能包 - 安装" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  安装目录: $INSTALL_DIR"
Write-Host ""

# ========== 卸载模式 ==========
if ($Uninstall) {
    Write-Step "卸载：移除 AGENT_SSH_AUDIT_HOME 环境变量..."

    $machineKey = "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
    try {
        $currentMachine = [Environment]::GetEnvironmentVariable("AGENT_SSH_AUDIT_HOME", "Machine")
        if ($currentMachine) {
            [Environment]::SetEnvironmentVariable("AGENT_SSH_AUDIT_HOME", $null, "Machine")
            Write-Step "已移除 Machine 级 AGENT_SSH_AUDIT_HOME"
        }
        Remove-ItemProperty -Path $machineKey -Name "AGENT_SSH_AUDIT_HOME" -ErrorAction SilentlyContinue
    } catch {
        Write-Warn "移除 Machine 级注册表失败: $_"
    }

    try {
        $currentUser = [Environment]::GetEnvironmentVariable("AGENT_SSH_AUDIT_HOME", "User")
        if ($currentUser) {
            [Environment]::SetEnvironmentVariable("AGENT_SSH_AUDIT_HOME", $null, "User")
            Write-Step "已移除 User 级 AGENT_SSH_AUDIT_HOME"
        }
    } catch {
        Write-Warn "移除 User 级环境变量失败: $_"
    }

    # 广播环境变量变更
    try {
        $HWND_BROADCAST = 0xFFFF
        $WM_SETTINGCHANGE = 0x001A
        Add-Type -Name "NativeMethods" -Namespace "Win32" -MemberDefinition @"
            [DllImport("user32.dll", SetLastError = true)]
            public static extern IntPtr SendMessageTimeout(
                IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam,
                uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);
"@
        $null = [Win32.NativeMethods]::SendMessageTimeout(
            $HWND_BROADCAST, $WM_SETTINGCHANGE, [UIntPtr]::Zero, "Environment",
            0x0002, 5000, [ref] [UIntPtr]::Zero)
        Write-Step "已广播环境变量变更"
    } catch {
        Write-Warn "广播变更失败（需重启终端生效）: $_"
    }

    Write-Host ""
    Write-Host "卸载完成。如需重新安装，请去掉 -Uninstall 参数重新运行。" -ForegroundColor Cyan
    exit 0
}

# ========== 安装模式 ==========

# 1. 检测系统 Python
Write-Step "检测系统 Python..."
$PYTHON_EXE = $null

# 优先找 python3，其次 python
foreach ($cmd in @("python3", "python")) {
    try {
        $out = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $PYTHON_EXE = (Get-Command $cmd -ErrorAction SilentlyContinue).Source
            Write-Step "找到 Python: $PYTHON_EXE  ($out)"
            break
        }
    } catch { }
}

if (-not $PYTHON_EXE) {
    Write-Err "未找到 Python 3，请先安装 Python 3.8+"
    Write-Host ""
    Write-Host "  安装方式：" -ForegroundColor Yellow
    Write-Host "    方式一（推荐）：Microsoft Store → 搜索 'Python 3.11' → 安装" -ForegroundColor White
    Write-Host "    方式二：https://www.python.org/downloads/ 下载安装包" -ForegroundColor White
    Write-Host ""
    Write-Host "  安装后请重新运行本脚本。" -ForegroundColor Cyan
    exit 1
}

# 2. 安装 paramiko 依赖
Write-Step "安装 paramiko 依赖..."
$pipResult = & $PYTHON_EXE -m pip install paramiko --quiet 2>&1
if ($LASTEXITCODE -eq 0) {
    $pVersion = & $PYTHON_EXE -c "import paramiko; print(paramiko.__version__)" 2>&1
    Write-Step "paramiko $pVersion 安装成功"
} else {
    Write-Err "paramiko 安装失败: $pipResult"
    exit 1
}

# 3. 创建 logs 目录结构
Write-Step "创建 logs 目录结构..."
$logsDir     = Join-Path $INSTALL_DIR "logs"
$sessionsDir = Join-Path $logsDir "sessions"
$cmdsDir     = Join-Path $logsDir "cmds_learn"
New-Item -ItemType Directory -Force -Path $sessionsDir | Out-Null
New-Item -ItemType Directory -Force -Path $cmdsDir | Out-Null
Write-Step "  logs/"
Write-Step "    sessions/"
Write-Step "    cmds_learn/"

# 4. 初始化 credentials.txt（如不存在）
$credFile = Join-Path $INSTALL_DIR "credentials.txt"
if (-not (Test-Path $credFile)) {
    Write-Step "创建 credentials.txt 模板..."
    @"
# SSH 凭据文件（key=value 格式，一行一条，value 为 Base64 编码的密文）
# 示例: 192.168.1.100=YXBwZW4=
# 本文件由 AI 自动管理，请勿手动编辑。
"@ | Out-File -FilePath $credFile -Encoding UTF8
    Write-Step "  credentials.txt（模板）"
} else {
    Write-Step "credentials.txt 已存在，跳过"
}

# 5. 设置环境变量（优先 Machine 级，失败自动降级 User 级）
Write-Step "设置环境变量 AGENT_SSH_AUDIT_HOME=$INSTALL_DIR ..."
$envSetOK = $false

try {
    [Environment]::SetEnvironmentVariable("AGENT_SSH_AUDIT_HOME", $INSTALL_DIR, "Machine")
    Write-Step "已写入 Machine 级环境变量"
    $envSetOK = $true
} catch {
    Write-Warn "Machine 级写入失败（需要管理员权限），降级到 User 级..."
}

if (-not $envSetOK) {
    try {
        [Environment]::SetEnvironmentVariable("AGENT_SSH_AUDIT_HOME", $INSTALL_DIR, "User")
        Write-Step "已写入 User 级环境变量"
        $envSetOK = $true
    } catch {
        Write-Err "User 级写入也失败: $_"
    }
}

# 无论如何写入当前进程
$env:AGENT_SSH_AUDIT_HOME = $INSTALL_DIR
Write-Step "已写入当前进程环境变量"

# 6. 广播环境变量变更
try {
    $HWND_BROADCAST = 0xFFFF
    $WM_SETTINGCHANGE = 0x001A
    Add-Type -Name "NativeMethods" -Namespace "Win32" -MemberDefinition @"
        [DllImport("user32.dll", SetLastError = true)]
        public static extern IntPtr SendMessageTimeout(
            IntPtr hWnd, uint Msg, UIntPtr wParam, string lParam,
            uint fuFlags, uint uTimeout, out UIntPtr lpdwResult);
"@
    $null = [Win32.NativeMethods]::SendMessageTimeout(
        $HWND_BROADCAST, $WM_SETTINGCHANGE, [UIntPtr]::Zero, "Environment",
        0x0002, 5000, [ref] [UIntPtr]::Zero)
    Write-Step "已广播环境变量变更"
} catch {
    Write-Warn "广播变更失败（需重启终端后生效）: $_"
}

# 7. 验证安装
Write-Step "验证安装完整性..."
$checks = @(
    @{Label="SKILL.md";                     Path=Join-Path $INSTALL_DIR "SKILL.md"},
    @{Label="requirements.txt";             Path=Join-Path $INSTALL_DIR "requirements.txt"},
    @{Label=".gitignore";                   Path=Join-Path $INSTALL_DIR ".gitignore"},
    @{Label="agent_ssh_audit/__init__.py";  Path=Join-Path $INSTALL_DIR "agent_ssh_audit\__init__.py"},
    @{Label="agent_ssh_audit/client.py";    Path=Join-Path $INSTALL_DIR "agent_ssh_audit\client.py"},
    @{Label="agent_ssh_audit/rules.py";     Path=Join-Path $INSTALL_DIR "agent_ssh_audit\rules.py"},
    @{Label="agent_ssh_audit/crypto.py";     Path=Join-Path $INSTALL_DIR "agent_ssh_audit\crypto.py"},
    @{Label="bin/agent-ssh-run.py";         Path=Join-Path $INSTALL_DIR "bin\agent-ssh-run.py"},
    @{Label="bin/agent-ssh-shell.py";       Path=Join-Path $INSTALL_DIR "bin\agent-ssh-shell.py"},
    @{Label="bin/agent-ssh-replay.py";      Path=Join-Path $INSTALL_DIR "bin\agent-ssh-replay.py"},
    @{Label="bin/agent-ssh-cred.py";        Path=Join-Path $INSTALL_DIR "bin\agent-ssh-cred.py"}
)

$allOK = $true
foreach ($c in $checks) {
    if (Test-Path $c.Path) {
        Write-Step $c.Label
    } else {
        Write-Err "缺失: $($c.Label)"
        $allOK = $false
    }
}

Write-Host ""
if ($allOK) {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  安装完成！" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  环境变量: AGENT_SSH_AUDIT_HOME=$INSTALL_DIR"
    Write-Host "  日志目录: $logsDir"
    Write-Host "  凭据文件: $credFile"
    Write-Host ""
    Write-Host "  快速验证（请打开新终端）:"
    Write-Host "    python bin/agent-ssh-cred.py list"
    Write-Host ""
    Write-Host "  卸载: .\install.ps1 -Uninstall"
} else {
    Write-Err "安装不完整，请检查缺失文件后重新运行。"
    exit 1
}
