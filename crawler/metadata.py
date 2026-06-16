"""
元数据管理工具
用于查询、统计和导出已下载的音频元数据
"""

import json
import csv
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional


class MetadataManager:
    """元数据管理器"""

    def __init__(self, metadata_dir: str = "data/metadata"):
        self.metadata_dir = Path(metadata_dir)

    def list_celebrities(self) -> List[str]:
        """列出所有已爬取数据的明星"""
        celebrities = set()
        for f in self.metadata_dir.glob("*.json"):
            name = f.stem.split("_")[0]
            celebrities.add(name)
        return sorted(celebrities)

    def get_metadata(self, celebrity: str, platform: Optional[str] = None) -> List[Dict]:
        """获取指定明星的元数据"""
        if platform:
            files = [self.metadata_dir / f"{celebrity}_{platform}.json"]
        else:
            files = list(self.metadata_dir.glob(f"{celebrity}_*.json"))

        all_records = []
        for f in files:
            if f.exists():
                with open(f, "r", encoding="utf-8") as fh:
                    records = json.load(fh)
                    all_records.extend(records)
        return all_records

    def stats(self) -> pd.DataFrame:
        """生成爬取数据统计"""
        rows = []
        for f in self.metadata_dir.glob("*.json"):
            with open(f, "r", encoding="utf-8") as fh:
                records = json.load(fh)
            for r in records:
                rows.append({
                    "celebrity": f.stem.split("_")[0],
                    "platform": r.get("platform", ""),
                    "title": r.get("title", ""),
                    "duration": r.get("duration", 0),
                    "download_time": r.get("download_time", ""),
                })

        if rows:
            return pd.DataFrame(rows)
        return pd.DataFrame()

    def export_to_csv(self, output_path: str = "data/metadata/summary.csv"):
        """导出元数据汇总到 CSV"""
        df = self.stats()
        if not df.empty:
            df.to_csv(output_path, index=False, encoding="utf-8-sig")
            print(f"元数据已导出到 {output_path}")
        else:
            print("没有数据可导出")
