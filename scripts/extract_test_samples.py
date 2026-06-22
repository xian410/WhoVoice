#!/usr/bin/env python3
"""
提取测试歌手的语音切片
========================
使用试听功能的副歌检测算法，从原始音频中截取 ~15 秒的人声片段
保存到 data/test_samples/ 目录，方便声纹测试和验证

用法:
  python scripts/extract_test_samples.py
  python scripts/extract_test_samples.py --singer 刘德华 张学友
  python scripts/extract_test_samples.py --duration 20
"""

import sys, os, json, time, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np

RAW_DIR = Path("data/raw")
OUTPUT_DIR = Path("data/test_samples")

TEST_SINGERS = [
    "刘德华", "张学友", "周杰伦", "陈奕迅", "王力宏",
    "刘欢", "李宗盛", "孙楠", "陶喆", "刀郎",
    "莫文蔚", "田馥甄", "那英", "温岚", "韩红",
    "Usher", "PSY", "Tank", "雷·查尔斯", "安德烈·波切利",
    "王杰", "朴树", "张国荣",
]


def find_ffmpeg():
    """查找可用的 ffmpeg 路径"""
    candidates = [
        r"C:\Users\17367\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe",
        r"D:\anaconda3\Library\bin\ffmpeg.exe",
        "ffmpeg", "ffmpeg.exe",
    ]
    for c in candidates:
        try:
            r = subprocess.run([c, "-version"], capture_output=True, timeout=5)
            if r.returncode == 0:
                return c
        except Exception:
            continue
    return ""


def detect_chorus_start(audio_path: str) -> float:
    """
    检测副歌起始位置（与试听功能相同的算法）
    返回起始秒数
    """
    try:
        import librosa
        sr = 16000
        y, sr = librosa.load(audio_path, sr=sr, mono=True, duration=120)

        hop_sec = 0.5
        hop_length = int(sr * hop_sec)
        rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]

        if len(rms) < 24:
            return 0.0

        # 3秒平滑
        window = max(1, int(3.0 / hop_sec))
        kernel = np.ones(window) / window
        energy = np.convolve(rms, kernel, mode="same")

        skip_frames = int(10.0 / hop_sec)
        if skip_frames >= len(energy):
            return 0.0

        global_max = np.max(energy)

        # 策略1: 能量跃升 (verse→chorus)
        lookahead = int(4.0 / hop_sec)
        baseline_range = int(8.0 / hop_sec)
        gap = max(1, int(2.0 / hop_sec))

        for i in range(skip_frames + baseline_range + gap, len(energy) - lookahead):
            baseline = np.median(energy[i - baseline_range - gap: i - gap])
            current = np.mean(energy[i: i + lookahead])
            if baseline > 1e-8 and current > baseline * 1.4 and current > global_max * 0.15:
                return max(0, i * hop_sec - 1.0)

        # 策略2: 第一个显著峰值回溯
        for i in range(skip_frames + int(5.0 / hop_sec), len(energy) - int(2.0 / hop_sec)):
            if energy[i] > global_max * 0.6:
                local_half = int(3.0 / hop_sec)
                start = max(skip_frames, i - local_half)
                end = min(len(energy), i + local_half)
                if energy[i] == np.max(energy[start:end]):
                    drop = energy[i] * 0.65
                    cs = i
                    for j in range(i, skip_frames, -1):
                        if energy[j] < drop:
                            cs = j + 1
                            break
                    return max(0, cs * hop_sec - 1.0)

        # 策略3: 持续高能段
        high_thresh = np.percentile(energy[skip_frames:], 75)
        if high_thresh > 1e-8:
            min_cons = max(1, int(3.0 / hop_sec))
            cons = 0
            si = None
            for i in range(skip_frames, len(energy)):
                if energy[i] > high_thresh:
                    if cons == 0: si = i
                    cons += 1
                    if cons >= min_cons:
                        return max(0, (skip_frames + si) * hop_sec - 1.0)
                else:
                    cons = 0; si = None

        # 策略4: 全局峰值
        peak = np.argmax(energy[skip_frames:]) + skip_frames
        return max(0, (peak - int(2.0 / hop_sec)) * hop_sec)

    except Exception:
        return 0.0


def extract_sample(input_path: str, output_path: str, duration: int = 15):
    """
    使用 ffmpeg 提取人声片段
    """
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print(f"    [WARN] ffmpeg 不可用，直接复制文件")
        import shutil
        shutil.copy2(input_path, output_path)
        return True

    # 检测副歌起始
    chorus_start = detect_chorus_start(input_path)

    # 如果检测失败，从第 5 秒开始（跳过前奏）
    if chorus_start <= 0:
        chorus_start = 5.0

    # 用 ffmpeg 截取
    try:
        r = subprocess.run(
            [ffmpeg, "-y", "-i", input_path, "-ss", str(chorus_start),
             "-t", str(duration), "-ar", "16000", "-ac", "1",
             "-sample_fmt", "s16", "-f", "wav", str(output_path)],
            capture_output=True, timeout=60,
        )
        if r.returncode != 0:
            print(f"    [ERR] ffmpeg 失败: {r.stderr.decode('utf-8','ignore')[:100]}")
            return False

        file_size = os.path.getsize(output_path)
        if file_size < 1000:
            print(f"    [ERR] 输出文件太小 ({file_size} bytes)")
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"    [ERR] ffmpeg 超时")
        return False
    except Exception as e:
        print(f"    [ERR] {e}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="提取测试歌手语音切片")
    parser.add_argument("--singer", nargs="+", default=None, help="指定歌手")
    parser.add_argument("--duration", type=int, default=15, help="切片时长(秒)")
    parser.add_argument("--all", action="store_true", help="处理所有歌手")
    args = parser.parse_args()

    if args.singer:
        singer_list = args.singer
    elif args.all:
        singer_list = sorted(d.name for d in RAW_DIR.iterdir() if d.is_dir())
    else:
        singer_list = TEST_SINGERS

    # 收集有效歌手
    singers = {}
    for name in singer_list:
        d = RAW_DIR / name
        if not d.is_dir():
            continue
        files = sorted([
            str(f.absolute()) for f in d.rglob("*")
            if f.suffix.lower() in (".wav", ".mp3", ".m4a")
            and "demucs_output" not in f.parts and "tmp" not in f.parts
        ])
        if files:
            singers[name] = files[:3]  # 最多取3个

    print(f"=" * 60)
    print(f"  提取 {len(singers)} 位歌手的语音切片")
    print(f"  切片时长: {args.duration}s")
    print(f"  输出目录: {OUTPUT_DIR}")
    print(f"=" * 60)

    ffmpeg_path = find_ffmpeg()
    print(f"  ffmpeg: {ffmpeg_path or '不可用'}")
    print()

    timer_start = time.time()
    total_ok = 0
    total_fail = 0

    for name in sorted(singers.keys()):
        files = singers[name]
        singer_out = OUTPUT_DIR / name
        singer_out.mkdir(parents=True, exist_ok=True)

        existing = list(singer_out.glob("*.wav"))
        if len(existing) >= len(files):
            sizes = [f.stat().st_size for f in existing]
            print(f"  ✅ [{name}] 已存在 {len(existing)} 个切片 (库存)")
            total_ok += len(existing)
            continue

        print(f"  [{name}] 处理中 ({len(files)} 文件)...")
        for idx, fpath in enumerate(files):
            out_path = singer_out / f"sample_{idx+1:02d}.wav"
            if out_path.exists():
                print(f"    ✅ sample_{idx+1:02d}.wav (已存在)")
                total_ok += 1
                continue

            ok = extract_sample(fpath, str(out_path), args.duration)
            if ok:
                kb = out_path.stat().st_size / 1024
                print(f"    ✅ sample_{idx+1:02d}.wav ({kb:.0f}KB)")
                total_ok += 1
            else:
                print(f"    ❌ sample_{idx+1:02d}.wav (失败)")
                total_fail += 1

    elapsed = time.time() - timer_start
    print()
    print(f"=" * 60)
    print(f"  完成！")
    print(f"  成功: {total_ok} 切片 | 失败: {total_fail} | 耗时: {elapsed:.1f}s")
    print(f"  位置: {OUTPUT_DIR.resolve()}")
    print(f"=" * 60)


if __name__ == "__main__":
    main()
