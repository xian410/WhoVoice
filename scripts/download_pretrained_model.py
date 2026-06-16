#!/usr/bin/env python3
"""
下载 mvector 预训练模型脚本
支持多个镜像源：GitHub、Gitee、BaiduPan (解析)
"""

import os
import sys
import zipfile
import tempfile
from pathlib import Path

# 禁用系统代理，避免 GitHub 限速
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)

import requests

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
CACHE_DIR = MODELS_DIR / "CAMPPlus_Fbank" / "best_model"

# 模型来源列表（按优先级排列）
MODEL_SOURCES = [
    {
        "name": "GitHub Release (VoiceprintRecognition-Pytorch)",
        "url": "https://github.com/yeyupiaoling/VoiceprintRecognition-Pytorch/releases/download/v1.0/CAMPPlus_Fbank.zip",
        "type": "zip",
    },
    {
        "name": "Gitee Release",
        "url": "https://gitee.com/yeyupiaoling/VoiceprintRecognition-Pytorch/releases/download/v1.0/CAMPPlus_Fbank.zip",
        "type": "zip",
    },
]

# 直链下载（如果 GitHub/Gitee release 格式不同）
MODEL_DIRECT_LINKS = [
    {
        "name": "ModelScope CAM++",
        "url": "https://modelscope.cn/api/v1/models/damo/speech_campplus_sv_zh-cn_16k-common/repo?Revision=master&FilePath=pytorch_model.bin",
        "filename": "model.pth",
    },
]


def download_with_resume(url: str, save_path: Path, desc: str = "") -> bool:
    """带断点续传的下载"""
    try:
        session = requests.Session()
        session.trust_env = False  # 忽略系统代理
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })

        # 先 HEAD 请求获取文件大小
        head = session.head(url, timeout=30, allow_redirects=True)
        total_size = int(head.headers.get("content-length", 0))

        # 检查本地是否有部分下载
        first_byte = save_path.stat().st_size if save_path.exists() else 0

        if first_byte >= total_size > 0:
            print(f"  [已存在] {save_path.name} ({total_size / 1024 / 1024:.1f} MB)")
            return True

        headers = {"Range": f"bytes={first_byte}-"} if first_byte > 0 else {}
        resp = session.get(url, headers=headers, stream=True, timeout=60)

        if resp.status_code in (200, 206):
            mode = "ab" if first_byte > 0 else "wb"
            save_path.parent.mkdir(parents=True, exist_ok=True)
            downloaded = first_byte
            with open(save_path, mode) as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if desc:
                            pct = downloaded / total_size * 100 if total_size else 0
                            print(f"\r  {desc}: {downloaded / 1024 / 1024:.1f}/{total_size / 1024 / 1024:.1f} MB ({pct:.0f}%)", end="")
            if desc:
                print()
            return True

        print(f"  HTTP {resp.status_code}")
        return False

    except Exception as e:
        print(f"  Error: {e}")
        return False


def download_and_extract_zip(url: str, target_dir: Path) -> bool:
    """下载 zip 并解压到目标目录"""
    print(f"  从 {url} 下载模型...")
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        session = requests.Session()
        session.trust_env = False
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        resp = session.get(url, stream=True, timeout=120)
        if resp.status_code != 200:
            print(f"  下载失败: HTTP {resp.status_code}")
            os.unlink(tmp_path)
            return False

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(tmp_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        print(f"\r  下载: {downloaded / 1024 / 1024:.1f}/{total / 1024 / 1024:.1f} MB ({downloaded / total * 100:.0f}%)", end="")
        print()

        # 解压
        print("  解压中...")
        with zipfile.ZipFile(tmp_path, "r") as zf:
            # 找到 model.pth
            pth_files = [n for n in zf.namelist() if n.endswith("model.pth")]
            if not pth_files:
                # 尝试找 .pth 文件
                pth_files = [n for n in zf.namelist() if n.endswith(".pth")]
            if not pth_files:
                print("  zip 中未找到 model.pth 文件，列出所有文件:")
                for n in zf.namelist():
                    print(f"    {n}")
                return False

            # 解压 model.pth 到目标目录
            target_dir.mkdir(parents=True, exist_ok=True)
            for pth_file in pth_files:
                print(f"  找到: {pth_file}")
                zf.extract(pth_file, target_dir.parent.parent)
                # 如果解压路径不是直接到 best_model，移动过去
                extracted = target_dir.parent.parent / pth_file
                if extracted != target_dir / "model.pth":
                    target_dir.mkdir(parents=True, exist_ok=True)
                    import shutil
                    shutil.move(str(extracted), str(target_dir / "model.pth"))
                    print(f"  移动到: {target_dir / 'model.pth'}")
                else:
                    print(f"  已解压到: {extracted}")
                break

        os.unlink(tmp_path)
        return True

    except Exception as e:
        print(f"  Error: {e}")
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return False


def download_direct(url: str, filename: str, target_dir: Path) -> bool:
    """直接下载单个文件"""
    target_path = target_dir / filename
    if target_path.exists():
        print(f"  [已存在] {target_path}")
        return True

    print(f"  从 {url} 下载 {filename}...")
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        session = requests.Session()
        session.trust_env = False
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        resp = session.get(url, stream=True, timeout=120)
        if resp.status_code != 200:
            print(f"  下载失败: HTTP {resp.status_code}")
            return False

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(target_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        print(f"\r  下载: {downloaded / 1024 / 1024:.1f}/{total / 1024 / 1024:.1f} MB ({downloaded / total * 100:.0f}%)", end="")
        print()
        print(f"  保存到: {target_path}")
        return True

    except Exception as e:
        print(f"  Error: {e}")
        return False


def main():
    print("=" * 60)
    print("  WhoVoice - 下载预训练声纹模型 (CAM++)")
    print("=" * 60)

    # 检查是否已存在
    if (CACHE_DIR / "model.pth").exists():
        size_mb = (CACHE_DIR / "model.pth").stat().st_size / 1024 / 1024
        print(f"\n✅ 模型已存在: {CACHE_DIR / 'model.pth'} ({size_mb:.1f} MB)")
        return

    print(f"\n模型将保存到: {CACHE_DIR}")
    print()

    # 方案1: 下载 zip
    for source in MODEL_SOURCES:
        print(f"\n尝试 [{source['name']}] ...")
        if download_and_extract_zip(source["url"], CACHE_DIR):
            if (CACHE_DIR / "model.pth").exists():
                print(f"\n✅ 模型下载成功!")
                return
        else:
            print(f"  ❌ 失败")

    # 方案2: 直链下载
    for source in MODEL_DIRECT_LINKS:
        print(f"\n尝试 [{source['name']}] ...")
        if download_direct(source["url"], source["filename"], CACHE_DIR):
            # 如果下载的文件名不是 model.pth，重命名
            saved = CACHE_DIR / source["filename"]
            if saved.name != "model.pth":
                saved.rename(CACHE_DIR / "model.pth")
                print(f"  重命名为: model.pth")
            print(f"\n✅ 模型下载成功!")
            return

    print("\n" + "=" * 60)
    print("❌ 所有自动下载源均失败")
    print()
    print("请手动下载预训练模型:")
    print("  1. 访问 https://github.com/yeyupiaoling/mvector/releases")
    print("  2. 下载 CAMPPlus_Fbank.zip")
    print("  3. 解压后将 model.pth 放到:")
    print(f"     {CACHE_DIR / 'model.pth'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
