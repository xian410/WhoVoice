<#
.SYNOPSIS
    WhoVoice 外网访问 — ngrok 隧道启动
.DESCRIPTION
    在本地服务器基础上，启动 ngrok 隧道，生成公网 HTTPS URL
    首次使用需要免费注册 ngrok 账号并配置 token

    准备工作（首次使用）:
        1. 打开 https://dashboard.ngrok.com/signup
        2. 用 GitHub/Google 登录，免费注册
        3. 打开 https://dashboard.ngrok.com/get-started/your-authtoken
        4. 复制你的 Authtoken
        5. 运行: ngrok config add-authtoken <你的token>

.PARAMETER Port
    本地服务端口（默认 8000）
.EXAMPLE
    .\serve_public.ps1
    .\serve_public.ps1 -Port 8000
#>
param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSCommandPath

Write-Host "`n" -NoNewline
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║    WhoVoice 外网隧道启动              ║" -ForegroundColor Magenta
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Magenta

# 查找 ngrok
$NgrokPaths = @(
    "$env:LOCALAPPDATA\Microsoft\WinGet\Links\ngrok.exe"
    "C:\Program Files\ngrok\ngrok.exe"
    "$env:USERPROFILE\scoop\apps\ngrok\current\ngrok.exe"
)
$NgrokExe = $null
foreach ($p in $NgrokPaths) {
    if (Test-Path $p) { $NgrokExe = $p; break }
}
if (-not $NgrokExe) {
    Write-Host "[ERROR] 未找到 ngrok，请先安装:" -ForegroundColor Red
    Write-Host "  winget install Ngrok.Ngrok" -ForegroundColor Yellow
    exit 1
}

# 检查 ngrok 是否已配置 authtoken
$NgrokConfig = "$env:USERPROFILE\AppData\Local\ngrok\ngrok.yml"
$Configured = $false
if (Test-Path $NgrokConfig) {
    $ConfigContent = Get-Content $NgrokConfig -Raw
    if ($ConfigContent -match "authtoken:\s*\S+") {
        $Configured = $true
    }
}

if (-not $Configured) {
    Write-Host "`n⚠️  ngrok 未配置 Authtoken" -ForegroundColor Yellow
    Write-Host "`n首次使用需要免费注册 ngrok 账号:" -ForegroundColor Yellow
    Write-Host "  1. 打开 https://dashboard.ngrok.com/signup" -ForegroundColor White
    Write-Host "  2. 用 GitHub/Google 登录，免费注册" -ForegroundColor White
    Write-Host "  3. 打开 https://dashboard.ngrok.com/get-started/your-authtoken" -ForegroundColor White
    Write-Host "  4. 复制你的 Authtoken" -ForegroundColor White
    Write-Host "  5. 运行: ngrok config add-authtoken <你的token>" -ForegroundColor Cyan
    Write-Host "`n    或直接运行下面命令（替换 YOUR_TOKEN）:" -ForegroundColor Yellow
    Write-Host "    & '$NgrokExe' config add-authtoken YOUR_TOKEN`n" -ForegroundColor Cyan

    # 询问是否已经有 token
    $Answer = Read-Host "已获得 Authtoken？直接粘贴在此（留空则退出）"
    if ([string]::IsNullOrWhiteSpace($Answer)) {
        Write-Host "取消启动。配置好 token 后再试。" -ForegroundColor Yellow
        exit 0
    }

    # 配置 token
    & $NgrokExe config add-authtoken $Answer
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Authtoken 配置失败" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Authtoken 配置成功" -ForegroundColor Green
}

Write-Host "`n启动 ngrok 隧道 (本地 :$Port → 公网 HTTPS)..." -ForegroundColor Yellow
Write-Host "按 Ctrl+C 停止隧道`n" -ForegroundColor Gray

Write-Host "`nngrok 隧道启动中，生成公网地址... (按 Ctrl+C 停止)`n" -ForegroundColor Gray
& $NgrokExe http $Port
