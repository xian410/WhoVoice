#!/usr/bin/env pwsh
<#
.SYNOPSIS
    WhoVoice 本地服务器一键启动
.DESCRIPTION
    1. 构建前端（如需要）
    2. 启动 Django 服务（API + 前端），端口 8000
    3. 显示访问地址
.PARAMETER Port
    监听端口（默认 8000）
.PARAMETER Device
    推理设备：auto/gpu/cpu（默认 auto，有CUDA则GPU否则CPU）
.EXAMPLE
    .\serve.ps1              # 默认启动
    .\serve.ps1 -Device cpu  # 强制 CPU 推理
#>
param(
    [int]$Port = 8000,
    [ValidateSet("auto","gpu","cpu")]
    [string]$Device = "auto"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSCommandPath

Write-Host "`n" -NoNewline
Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║       WhoVoice 本地服务器启动        ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan

# 环境变量
$env:INFERENCE_DEVICE = $Device
$env:DJANGO_DEBUG = "True"

# 1. 构建前端（如果 dist 不存在或 package.json 更新）
$DistDir = Join-Path $ProjectRoot "frontend" "dist"
$PkgJson = Join-Path $ProjectRoot "frontend" "package.json"
$NeedBuild = $true
if (Test-Path $DistDir) {
    $DistTime = (Get-Item $DistDir).LastWriteTime
    $PkgTime = (Get-Item $PkgJson).LastWriteTime
    if ($DistTime -gt $PkgTime) {
        $NeedBuild = $false
    }
}

if ($NeedBuild) {
    Write-Host "`n[1/2] 构建前端..." -ForegroundColor Yellow
    $env:Path = "C:\Program Files\nodejs;$env:Path"
    Set-Location (Join-Path $ProjectRoot "frontend")
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] 前端构建失败" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] 前端构建完成" -ForegroundColor Green
} else {
    Write-Host "`n[1/2] 前端已是最新，跳过构建" -ForegroundColor Green
}

# 2. 启动后端
Write-Host "[2/2] 启动 WhoVoice 服务..." -ForegroundColor Yellow

# 获取本机局域网 IP
$LocalIP = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.IPAddress -notlike "169.*" -and $_.IPAddress -notlike "127.*" } |
    Select-Object -First 1).IPAddress

Set-Location $ProjectRoot

Write-Host "`n══════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  访问地址:" -ForegroundColor Cyan
Write-Host "  本机:     http://127.0.0.1:$Port" -ForegroundColor White
if ($LocalIP) {
    Write-Host "  局域网:   http://${LocalIP}:${Port}" -ForegroundColor White
}
Write-Host "  推理设备: $Device → $(if ($Device -eq 'cpu') {'CPU'} elseif ($Device -eq 'gpu') {'GPU'} else {'自动检测'})" -ForegroundColor White
Write-Host "══════════════════════════════════════`n" -ForegroundColor Cyan

python backend/manage.py runserver 0.0.0.0:$Port --noreload

# 如果进程退出（按 Ctrl+C），打印提示
Write-Host "`n服务器已停止" -ForegroundColor Yellow
