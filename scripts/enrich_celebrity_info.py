#!/usr/bin/env python3
"""
名人信息富化脚本
从多源爬取歌手头像、简介、流派、国籍，更新 celebrities_info.json

用法:
  # 预览模式（不写文件）
  python scripts/enrich_celebrity_info.py --dry-run

  # 全量富化（默认只处理缺失字段的歌手）
  python scripts/enrich_celebrity_info.py

  # 强制刷新所有歌手（忽略缓存 & 已有数据）
  python scripts/enrich_celebrity_info.py --force-refresh

  # 只处理指定歌手
  python scripts/enrich_celebrity_info.py --singers 刘德华,周杰伦,Taylor Swift

  # 设置请求间隔（默认 1.5 秒）
  python scripts/enrich_celebrity_info.py --delay 2.0

  # 断点续传（从缓存中恢复未完成的）
  python scripts/enrich_celebrity_info.py --resume
"""

import argparse
import json
import os
import sys
from pathlib import Path

# 修复 Windows 终端编码
if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# 项目路径
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from crawler.celebrity_info_crawler import CelebrityInfoCrawler

INFO_PATH = BASE_DIR / "data" / "metadata" / "celebrities_info.json"
BACKUP_DIR = BASE_DIR / "data" / "metadata" / "backups"

# 需要富化的字段（包含缺失即处理）
REQUIRED_FIELDS = ["avatar_url", "bio"]


def load_celebrities() -> dict:
    """加载 celebrities_info.json"""
    if not INFO_PATH.exists():
        print(f"[ERROR] 文件不存在: {INFO_PATH}")
        sys.exit(1)
    with open(INFO_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_celebrities(data: dict, dry_run: bool = False) -> None:
    """保存 celebrities_info.json（先备份）"""
    if dry_run:
        print("\n[DRY RUN] 不会写入文件")
        return

    # 备份
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"celebrities_info_{timestamp}.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n[备份] {backup_path}")

    # 写入
    with open(INFO_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[保存] {INFO_PATH}")


def singer_needs_enrichment(singer: dict) -> bool:
    """判断歌手是否需要富化（任一必需字段缺失）"""
    for field in REQUIRED_FIELDS:
        if not singer.get(field):
            return True
    return False


def merge_info(singer: dict, enriched: dict) -> int:
    """
    将富化信息合并到歌手记录中

    返回: 更新的字段数
    """
    updated = 0
    for field in ["avatar_url", "bio", "genre", "nationality", "birth_date"]:
        value = enriched.get(field, "")
        if value and not singer.get(field):
            singer[field] = value
            updated += 1

    # 记录来源
    source = enriched.get("source", "")
    if source and source != "none":
        singer["info_source"] = source
        updated += 1

    return updated


def main():
    parser = argparse.ArgumentParser(
        description="名人信息富化 — 从多源获取头像、简介等",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="预览模式，不实际写入文件",
    )
    parser.add_argument(
        "--force-refresh", action="store_true",
        help="强制刷新所有歌手（忽略缓存和已有数据）",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="断点续传模式（从缓存恢复）",
    )
    parser.add_argument(
        "--singers", type=str, default="",
        help="指定要处理的歌手，逗号分隔（默认处理全部缺失的）",
    )
    parser.add_argument(
        "--delay", type=float, default=1.5,
        help="请求间隔秒数（默认 1.5）",
    )
    args = parser.parse_args()

    # 加载数据
    data = load_celebrities()
    singers = data.get("singers", [])
    total_count = len(singers)
    print(f"=" * 60)
    print(f"  WhoVoice - 名人信息富化")
    print(f"=" * 60)
    print(f"  总歌手数: {total_count}")

    # 确定处理目标
    if args.singers:
        target_names = set(n.strip() for n in args.singers.split(","))
        targets = [s for s in singers if s["name"] in target_names]
        print(f"  指定处理: {len(targets)} 位")
    elif args.force_refresh:
        targets = singers
        print(f"  强制刷新: {len(targets)} 位（全部）")
    else:
        targets = [s for s in singers if singer_needs_enrichment(s)]
        print(f"  待富化:   {len(targets)} 位（缺失 avatar_url/bio）")

    already_rich = total_count - len(targets)
    if already_rich > 0 and not args.force_refresh:
        print(f"  已完备:   {already_rich} 位（跳过）")

    if not targets:
        print("\n所有歌手信息已完备 ✅")
        return

    print(f"  请求间隔: {args.delay}s")
    if args.dry_run:
        print(f"  模式:     DRY RUN (预览)")
    print()

    # 初始化爬虫
    crawler = CelebrityInfoCrawler()
    names = [s["name"] for s in targets]

    # 批量富化
    enriched_map = crawler.enrich_batch(
        names,
        force_refresh=args.force_refresh,
        delay=args.delay,
    )

    # 合并结果
    total_updated = 0
    success_count = 0
    for singer in singers:
        name = singer["name"]
        enriched = enriched_map.get(name, {})
        if not enriched:
            continue

        updated = merge_info(singer, enriched)
        if updated > 0:
            success_count += 1
            total_updated += updated

        # 打印详情
        source = enriched.get("source", "none")
        avatar = "✓" if singer.get("avatar_url") else "✗"
        bio_len = len(singer.get("bio", ""))
        print(f"  [{source:14s}] {name:20s} avatar={avatar} bio={bio_len:4d}chars  +{updated}字段")

    # 更新 total
    data["total"] = len(singers)

    # 保存
    if not args.dry_run:
        save_celebrities(data, dry_run=args.dry_run)
    else:
        save_celebrities(data, dry_run=True)

    # 汇总
    print(f"\n{'=' * 60}")
    print(f"  富化完成!")
    print(f"  {'=' * 60}")
    print(f"  处理歌手: {len(targets)} 位")
    print(f"  成功富化: {success_count} 位")
    print(f"  更新字段: {total_updated} 个")
    print(f"  缓存位置: data/metadata/celebrity_info_cache.json")
    print(f"  数据文件: data/metadata/celebrities_info.json")

    if not args.dry_run and success_count > 0:
        print(f"\n  建议: 重启后端服务以生效")
        print(f"    python {BASE_DIR / 'backend' / 'manage.py'} runserver")


if __name__ == "__main__":
    main()
