"""
存储空间清理脚本

清理 crawler/preprocessing 产生的中间文件和缓存数据。
支持 dry-run 预览和分级清理策略。

用法:
    # 预览将释放的空间（不删除）
    python scripts/cleanup.py --dry-run

    # 仅清理 Demucs 分离产物 (±42GB)，保留原始音频
    python scripts/cleanup.py --keep-raw

    # 激进清理：删除原始音频 + Demucs 产物，只保留切片
    python scripts/cleanup.py --aggressive

    # 指定明星
    python scripts/cleanup.py --celebrity 周杰伦 --keep-raw

    # 清理所有明星的 tmp 中间文件
    python scripts/cleanup.py --keep-raw --clean-tmp
"""

import os
import shutil
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def human_size(bytes_val: int) -> str:
    """将字节数转为可读格式"""
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"


def scan_celebrity_dirs(celebrity: str = None):
    """扫描明星目录"""
    if celebrity:
        celeb_dir = RAW_DIR / celebrity
        return [celeb_dir] if celeb_dir.exists() else []
    return sorted([d for d in RAW_DIR.iterdir() if d.is_dir()]) if RAW_DIR.exists() else []


def calc_demucs_output_size(celeb_dir: Path) -> tuple:
    """计算 Demucs 分离产物大小和文件数"""
    total_size = 0
    file_count = 0
    for f in celeb_dir.rglob("*.wav"):
        # Demucs 输出在 demucs_output/ 目录下
        if "demucs_output" in str(f):
            total_size += f.stat().st_size
            file_count += 1
    return total_size, file_count


def calc_tmp_size() -> tuple:
    """计算 tmp 中间文件大小"""
    total_size = 0
    file_count = 0
    for f in PROCESSED_DIR.rglob("tmp/*"):
        if f.is_file():
            total_size += f.stat().st_size
            file_count += 1
    return total_size, file_count


def calc_raw_audio_size(celeb_dir: Path) -> tuple:
    """计算原始音频文件大小（排除 Demucs 产物）"""
    total_size = 0
    file_count = 0
    for f in celeb_dir.rglob("*.wav"):
        if "demucs_output" not in str(f):
            total_size += f.stat().st_size
            file_count += 1
    for f in celeb_dir.rglob("*.mp3"):
        if "demucs_output" not in str(f):
            total_size += f.stat().st_size
            file_count += 1
    return total_size, file_count


def clean_demucs_output(celeb_dir: Path, dry_run: bool) -> tuple:
    """清理 Demucs 分离产物"""
    freed = 0
    count = 0
    for f in celeb_dir.rglob("*.wav"):
        if "demucs_output" in str(f):
            freed += f.stat().st_size
            count += 1
            if not dry_run:
                f.unlink()

    for d in celeb_dir.rglob("demucs_output"):
        if d.is_dir() and not dry_run:
            try:
                shutil.rmtree(str(d))
            except OSError:
                pass
        count_remaining = len(list(d.rglob("*"))) if d.exists() else 0
        if count_remaining == 0 and d.exists() and not dry_run:
            try:
                d.rmdir()
            except OSError:
                pass

    return freed, count


def clean_raw_audio(celeb_dir: Path, dry_run: bool) -> tuple:
    """清理原始音频文件（保留目录结构）"""
    freed = 0
    count = 0
    for ext in ("*.wav", "*.mp3"):
        for f in celeb_dir.rglob(ext):
            if "demucs_output" not in str(f):
                freed += f.stat().st_size
                count += 1
                if not dry_run:
                    f.unlink()

    # 清理空目录
    if not dry_run:
        for d in sorted(celeb_dir.rglob("*"), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                try:
                    d.rmdir()
                except OSError:
                    pass

    return freed, count


def clean_tmp_files(dry_run: bool) -> tuple:
    """清理所有 tmp 中间文件"""
    freed = 0
    count = 0
    for tmp_dir in PROCESSED_DIR.rglob("tmp"):
        if tmp_dir.is_dir():
            for f in tmp_dir.rglob("*"):
                if f.is_file():
                    freed += f.stat().st_size
                    count += 1
            if not dry_run:
                shutil.rmtree(str(tmp_dir))
    return freed, count


def main():
    parser = argparse.ArgumentParser(description="WhoVoice 存储空间清理工具")
    parser.add_argument("--dry-run", action="store_true", help="预览模式：统计但不删除")
    parser.add_argument("--keep-raw", action="store_true", help="保留原始音频，仅清理 Demucs 产物")
    parser.add_argument("--aggressive", action="store_true", help="激进清理：删除原始音频 + Demucs 产物")
    parser.add_argument("--celebrity", type=str, default=None, help="指定明星（默认全量）")
    parser.add_argument("--clean-tmp", action="store_true", help="同时清理 tmp 中间文件")
    args = parser.parse_args()

    if not args.keep_raw and not args.aggressive and not args.clean_tmp:
        parser.print_help()
        print("\n请指定清理模式: --keep-raw 或 --aggressive 或 --clean-tmp")
        return

    if args.keep_raw and args.aggressive:
        print("错误: --keep-raw 和 --aggressive 不能同时使用")
        return

    mode = "🔍 DRY-RUN（预览）" if args.dry_run else "执行"
    print(f"{'='*60}")
    print(f"  WhoVoice 存储清理 - {mode}")
    print(f"{'='*60}")

    celeb_dirs = scan_celebrity_dirs(args.celebrity)
    if not celeb_dirs:
        print("没有找到明星数据目录")
        return

    total_freed = 0
    total_files = 0

    # ── 清理 Demucs 产物（所有模式都清理） ──
    print(f"\n📦 清理 Demucs 分离产物...")
    for celeb_dir in celeb_dirs:
        demucs_size, demucs_count = calc_demucs_output_size(celeb_dir)
        if demucs_count == 0:
            continue
        print(f"  [{celeb_dir.name}] Demucs 产物: {demucs_count} 个文件, {human_size(demucs_size)}")
        freed, count = clean_demucs_output(celeb_dir, args.dry_run)
        total_freed += freed
        total_files += count

    # ── 清理原始音频（激进模式） ──
    if args.aggressive:
        print(f"\n🗑️  清理原始音频（激进模式）...")
        for celeb_dir in celeb_dirs:
            raw_size, raw_count = calc_raw_audio_size(celeb_dir)
            if raw_count == 0:
                continue
            print(f"  [{celeb_dir.name}] 原始音频: {raw_count} 个文件, {human_size(raw_size)}")
            freed, count = clean_raw_audio(celeb_dir, args.dry_run)
            total_freed += freed
            total_files += count

    # ── 清理 tmp 中间文件 ──
    if args.clean_tmp:
        print(f"\n🧹 清理 tmp 中间文件...")
        tmp_size, tmp_count = calc_tmp_size()
        if tmp_count > 0:
            print(f"  tmp 文件: {tmp_count} 个, {human_size(tmp_size)}")
            freed, count = clean_tmp_files(args.dry_run)
            total_freed += freed
            total_files += count

    # ── 结果 ──
    print(f"\n{'='*60}")
    if args.dry_run:
        print(f"  🔍 预览完成 — 可释放: {human_size(total_freed)} ({total_files} 个文件)")
        print(f"  运行不加 --dry-run 以执行清理")
    else:
        print(f"  ✅ 清理完成 — 已释放: {human_size(total_freed)} ({total_files} 个文件)")


if __name__ == "__main__":
    main()
