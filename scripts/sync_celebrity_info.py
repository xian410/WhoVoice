#!/usr/bin/env python3
"""
同步 celebrities_info.json 与 FAISS 声纹注册状态

问题诊断:
  - FAISS 元数据 (celebrity_metadata.json): {count} 位已注册明星
  - celebrities_info.json: 仅 78 位，且含 12 位已移除的团体艺人
  - 前端显示数量来自 FAISS 元数据(正确)，但缺少 377 位明星的详细信息

修复内容:
  1. 移除 celebrities_info.json 中已不在 FAISS 的过时条目
  2. 为 FAISS 中已注册但 celebrities_info.json 缺失的明星补充信息
  3. 同步 speaker_id_map.txt
"""
import sys
import os
import json
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 项目路径
BASE_DIR = Path(__file__).resolve().parent.parent
FAISS_METADATA = BASE_DIR / "vector_database" / "faiss_index" / "celebrity_metadata.json"
INFO_PATH = BASE_DIR / "data" / "metadata" / "celebrities_info.json"
SPEAKER_ID_MAP = BASE_DIR / "data" / "metadata" / "speaker_id_map.txt"
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
METADATA_DIR = BASE_DIR / "data" / "metadata"

# 预定义的色彩板（用于无 avatar_color 的明星）
COLOR_PALETTE = [
    "#1a1a2e", "#16213e", "#0f3460", "#e94560",
    "#2d3436", "#636e72", "#b2bec3", "#dfe6e9",
    "#6c5ce7", "#a29bfe", "#fd79a8", "#e84393",
    "#00b894", "#00cec9", "#0984e3", "#74b9ff",
    "#fdcb6e", "#e17055", "#d63031", "#2ecc71",
]


def _deterministic_color(name: str) -> str:
    """基于名称哈希确定颜色"""
    h = int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16)
    return COLOR_PALETTE[h % len(COLOR_PALETTE)]


def _load_speaker_id_map() -> dict:
    """加载 spk_id 映射"""
    mapping = {}
    if SPEAKER_ID_MAP.exists():
        with open(SPEAKER_ID_MAP, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and "\t" in line:
                    celeb, spk_id = line.split("\t", 1)
                    mapping[celeb] = spk_id
    return mapping


def _save_speaker_id_map(mapping: dict):
    """保存 spk_id 映射"""
    SPEAKER_ID_MAP.parent.mkdir(parents=True, exist_ok=True)
    with open(SPEAKER_ID_MAP, "w", encoding="utf-8") as f:
        for celeb, spk_id in sorted(mapping.items(), key=lambda x: x[0]):
            f.write(f"{celeb}\t{spk_id}\n")
    print(f"  speaker_id_map.txt 已更新: {len(mapping)} 条")


def _get_representative_songs(name: str) -> list:
    """从元数据文件中提取代表性歌曲标题（去重）"""
    songs = []
    seen = set()
    for meta_file in sorted(METADATA_DIR.glob(f"{name}_*.json")):
        try:
            records = json.load(open(meta_file, "r", encoding="utf-8"))
            for rec in records:
                title = rec.get("title", "")
                if title and title not in seen:
                    # 去掉 "歌手名 - " 前缀
                    clean = title.split(" - ", 1)[-1] if " - " in title else title
                    seen.add(title)
                    songs.append(clean)
        except Exception:
            continue

    # 去重
    unique = list(dict.fromkeys(songs))
    return unique[:5]  # 最多 5 首


def _count_raw_videos(name: str) -> int:
    """统计原始音频文件数量"""
    celeb_dir = RAW_DIR / name
    if not celeb_dir.is_dir():
        return 0
    count = 0
    for f in celeb_dir.rglob("*"):
        if f.suffix.lower() in (".wav", ".mp3") and "demucs_output" not in str(f) and "tmp" not in str(f):
            count += 1
    return count


def _count_processed_slices(name: str) -> int:
    """统计已预处理切片数量"""
    celeb_dir = PROCESSED_DIR / name
    if not celeb_dir.is_dir():
        return 0
    return len(list(celeb_dir.rglob("*.wav")))


def sync_celebrities_info():
    """同步 celebrities_info.json"""
    print("=" * 60)
    print("  WhoVoice - 同步明星注册信息")
    print("=" * 60)

    # 1. 加载 FAISS 注册列表（数据源）
    if not FAISS_METADATA.exists():
        print(f"[ERROR] FAISS 元数据不存在: {FAISS_METADATA}")
        print("请先运行 python scripts/extract_embeddings.py 构建声纹索引")
        sys.exit(1)

    faiss_meta = json.load(open(FAISS_METADATA, "r", encoding="utf-8"))
    faiss_celebrities = faiss_meta.get("celebrities", [])
    faiss_set = set(faiss_celebrities)
    print(f"\n[FAISS 声纹库] 已注册: {len(faiss_celebrities)} 位明星")

    # 2. 加载现有 celebrities_info.json
    current_info = {"singers": []}
    if INFO_PATH.exists():
        try:
            current_info = json.load(open(INFO_PATH, "r", encoding="utf-8"))
        except Exception:
            pass

    current_singers = current_info.get("singers", [])
    current_names = {s["name"] for s in current_singers}
    print(f"[现有信息]   celebrities_info.json: {len(current_singers)} 位")

    # 3. 加载 spk_id 映射
    spk_map = _load_speaker_id_map()
    print(f"[spk_id映射] speaker_id_map.txt: {len(spk_map)} 条")

    # 4. 找出变更
    stale = current_names - faiss_set
    missing = faiss_set - current_names
    print(f"\n[诊断]")
    print(f"  待移除（在 info 但不在 FAISS）: {len(stale)} 位")
    if stale:
        for n in sorted(stale):
            print(f"    - {n}")
    print(f"  待补充（在 FAISS 但不在 info）: {len(missing)} 位")

    # 5. 构建新 singer 列表
    name_to_info = {}

    # 5a. 保留有效的现有条目
    kept_from_old = 0
    for s in current_singers:
        if s["name"] in faiss_set:
            name_to_info[s["name"]] = s
            kept_from_old += 1

    print(f"\n[执行]")
    print(f"  保留现有有效条目: {kept_from_old} 位")

    # 5b. 为缺失的明星补充信息
    new_count = 0
    for name in sorted(faiss_celebrities):
        if name in name_to_info:
            continue

        # 从现有映射获取 spk_id，不存在则生成
        spk_id = spk_map.get(name, "")
        if not spk_id:
            # 按 FAISS 顺序生成新的 spk_id
            spk_id = f"SPK{len(spk_map):04d}"
            spk_map[name] = spk_id

        info = {
            "name": name,
            "avatar_color": name_to_info.get(name, {}).get("avatar_color", _deterministic_color(name)),
            "initial": name[0] if name else "?",
            "video_count": _count_raw_videos(name),
            "slice_count": _count_processed_slices(name),
            "representative_songs": _get_representative_songs(name),
            "spk_id": spk_id,
        }
        name_to_info[name] = info
        new_count += 1

    print(f"  新增补充信息: {new_count} 位")

    # 6. 按 FAISS 顺序输出
    final_singers = [name_to_info[name] for name in faiss_celebrities]

    result = {"singers": final_singers, "total": len(final_singers)}
    INFO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INFO_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✅ celebrities_info.json 已同步: {len(final_singers)} 位")
    print(f"     路径: {INFO_PATH}")

    # 7. 同步 speaker_id_map.txt（添加新生成的 spk_id）
    _save_speaker_id_map(spk_map)
    print(f"✅ speaker_id_map.txt 已同步: {len(spk_map)} 条")


def sync_speaker_id_map():
    """同步 speaker_id_map.txt 与 FAISS（去除不在 FAISS 的条目）"""
    print("\n" + "=" * 60)
    print("  同步 speaker_id_map.txt")
    print("=" * 60)

    if not FAISS_METADATA.exists():
        return

    faiss_meta = json.load(open(FAISS_METADATA, "r", encoding="utf-8"))
    faiss_set = set(faiss_meta.get("celebrities", []))

    spk_map = _load_speaker_id_map()
    old_count = len(spk_map)
    # 只保留在 FAISS 中的条目
    spk_map = {k: v for k, v in spk_map.items() if k in faiss_set}
    removed = old_count - len(spk_map)

    if removed > 0:
        _save_speaker_id_map(spk_map)
        print(f"  已移除 {removed} 条过时 spk_id")
    else:
        print(f"  无需清理")

    # 补充 FAISS 中有但映射中缺少的
    added = 0
    for name in sorted(faiss_set):
        if name not in spk_map:
            spk_id = f"SPK{len(spk_map):04d}"
            spk_map[name] = spk_id
            added += 1
    if added > 0:
        _save_speaker_id_map(spk_map)
        print(f"  已补充 {added} 条缺失 spk_id")
    else:
        print(f"  无需补充")

    print(f"  speaker_id_map.txt: {len(spk_map)} 条")


def print_summary():
    """打印所有数据源的同步状态"""
    print("\n" + "=" * 60)
    print("  最终同步状态")
    print("=" * 60)

    # FAISS
    if FAISS_METADATA.exists():
        meta = json.load(open(FAISS_METADATA, "r", encoding="utf-8"))
        faiss_count = len(meta.get("celebrities", []))
        print(f"  FAISS 声纹库        : {faiss_count} 位已注册")
    else:
        print(f"  FAISS 声纹库        : 未构建")
        faiss_count = 0

    # celebrities_info.json
    if INFO_PATH.exists():
        info = json.load(open(INFO_PATH, "r", encoding="utf-8"))
        info_count = len(info.get("singers", []))
        info_set = {s["name"] for s in info.get("singers", [])}
        print(f"  celebrities_info.json : {info_count} 位", end="")
        if faiss_count > 0 and info_set == set(meta.get("celebrities", [])):
            print(" ✅ 与 FAISS 一致")
        else:
            only_info = info_set - set(meta.get("celebrities", []))
            only_faiss = set(meta.get("celebrities", [])) - info_set
            diff = []
            if only_info:
                diff.append(f"多出{len(only_info)}位")
            if only_faiss:
                diff.append(f"缺少{len(only_faiss)}位")
            print(f" ⚠️ 不同步 ({', '.join(diff)})")

    # speaker_id_map.txt
    if SPEAKER_ID_MAP.exists():
        spk_map = _load_speaker_id_map()
        spk_count = len(spk_map)
        spk_set = set(spk_map.keys())
        print(f"  speaker_id_map.txt   : {spk_count} 条", end="")
        if faiss_count > 0:
            if spk_set == set(meta.get("celebrities", [])):
                print(" ✅ 与 FAISS 一致")
            else:
                only_spk = spk_set - set(meta.get("celebrities", []))
                only_faiss = set(meta.get("celebrities", [])) - spk_set
                diff = []
                if only_spk:
                    diff.append(f"多出{len(only_spk)}位")
                if only_faiss:
                    diff.append(f"缺少{len(only_faiss)}位")
                print(f" ⚠️ 不同步 ({', '.join(diff)})")

    # CELEBRITY_LIST 配置
    try:
        from crawler.config import CELEBRITY_LIST
        print(f"  CELEBRITY_LIST       : {len(CELEBRITY_LIST)} 位（爬虫目标）")
    except Exception:
        pass

    # data/raw 目录统计
    if RAW_DIR.is_dir():
        raw_count = sum(1 for d in RAW_DIR.iterdir() if d.is_dir())
        print(f"  data/raw/           : {raw_count} 位（有原始音频）")

    # data/processed 目录统计
    if PROCESSED_DIR.is_dir():
        proc_count = sum(1 for d in PROCESSED_DIR.iterdir() if d.is_dir())
        print(f"  data/processed/     : {proc_count} 位（已预处理）")


def main():
    print("WhoVoice 注册歌手信息同步工具")
    print("-" * 60)

    # Step 1: 同步 celebrities_info.json
    sync_celebrities_info()

    # Step 2: 同步 speaker_id_map.txt
    sync_speaker_id_map()

    # Step 3: 打印最终状态
    print_summary()

    print("\n" + "=" * 60)
    print("  ✅ 同步完成!")
    print("  " + "=" * 60)
    print("  建议: 重启后端服务以生效")
    print(f"    python {BASE_DIR / 'backend' / 'manage.py'} runserver")
    print("=" * 60)


if __name__ == "__main__":
    main()
