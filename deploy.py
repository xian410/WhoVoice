#!/usr/bin/env python3
"""
WhoVoice 服务部署打包脚本
打包可直接在服务器运行的版本
"""
import os, sys, shutil, subprocess, zipfile, time
from pathlib import Path

BASE = Path(__file__).resolve().parent
TIMESTAMP = time.strftime("%Y%m%d_%H%M%S")
ZIP_NAME = f"WhoVoice_{TIMESTAMP}.zip"
TEMP_DIR = BASE / f"deploy_tmp_{TIMESTAMP}"

# 需要打包的目录
DIRS = [
    "backend",
    "frontend/dist",
    "vector_database/faiss_index",
    "data/metadata",
    "voice_recognition",
    "models/CAMPPlus_Fbank",
    "preprocessing",
    "scripts",
    "crawler",
]

# 需要打包的根文件
FILES = [
    "requirements.txt",
]


def build_frontend():
    """构建前端"""
    print("[1/3] 构建前端...")
    frontend_dir = BASE / "frontend"
    dist_dir = frontend_dir / "dist"

    if dist_dir.exists():
        shutil.rmtree(str(dist_dir))
    subprocess.run(["npx", "vite", "build"], cwd=str(frontend_dir), check=True, shell=True)
    print("  OK")


def create_package():
    """创建部署包"""
    print("[2/3] 生成部署包...")
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # 复制目录
    for d in DIRS:
        src = BASE / d
        dst = TEMP_DIR / d
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(str(src), str(dst))
            print(f"  OK  {d}")

    # 复制文件
    for f in FILES:
        src = BASE / f
        if src.exists():
            shutil.copy2(str(src), str(TEMP_DIR / f))
            print(f"  OK  {f}")

    # 生成启动脚本
    _write_start_script()

    # 打包
    print(f"\n[3/3] 打包为 {ZIP_NAME}...")
    with zipfile.ZipFile(str(BASE / ZIP_NAME), "w", zipfile.ZIP_DEFLATED) as zf:
        for f in TEMP_DIR.rglob("*"):
            if f.is_file():
                zf.write(str(f), str(f.relative_to(TEMP_DIR)))

    # 清理
    shutil.rmtree(str(TEMP_DIR))

    size_mb = (BASE / ZIP_NAME).stat().st_size / 1024 / 1024
    print(f"  完成! 包大小: {size_mb:.1f} MB")
    return ZIP_NAME


def _write_start_script():
    """生成生产环境启动脚本"""
    content = r"""#!/usr/bin/env pwsh
param(
    [int]$Port = 8000,
    [switch]$Service,
    [switch]$Public,
    [ValidateSet("auto","gpu","cpu")]
    [string]$Device = "auto"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSCommandPath
$env:INFERENCE_DEVICE = $Device
$env:DJANGO_DEBUG = "False"

Write-Host "WhoVoice Server Starting..."
Write-Host "  Device: $Device"
Write-Host "  Port: $Port"

Set-Location $ProjectRoot
$bind = "0.0.0.0:$Port"
Write-Host "  Listen: http://${bind}"

if ($Service) {
    $log = Join-Path $ProjectRoot "server.log"
    Start-Transcript -Path $log -Append | Out-Null
}

try {
    python backend/manage.py runserver $bind --noreload
} catch {
    Write-Host "Server error: $_"
    Read-Host "Press Enter to exit"
}
"""
    (TEMP_DIR / "start.ps1").write_text(content, encoding="utf-8")
    print("  OK  start.ps1")


if __name__ == "__main__":
    print("=" * 50)
    print("  WhoVoice Deploy Package Builder")
    print("=" * 50)
    build_frontend()
    zip_name = create_package()
    print("\n" + "=" * 50)
    print(f"  Package: {zip_name}")
    print("=" * 50)
    print("\nDeploy steps:")
    print(f"  1. Upload {zip_name} to server")
    print("  2. Extract to any directory")
    print("  3. pip install -r requirements.txt")
    print("  4. Copy data/raw/ to the server (for audio preview)")
    print("     robocopy <source>\\data\\raw <target>\\data\\raw /E")
    print("  5. .\\start.ps1")
    print("\nFor Windows Service (NSSM):")
    print("  1. Download NSSM: https://nssm.cc/download")
    print('  2. nssm install WhoVoice "powershell" "-File .\\start.ps1 -Service"')
    print("  3. nssm start WhoVoice")
    print()
