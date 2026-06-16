"""
数据集构建模块
生成符合 mvector 格式的数据清单，用于模型训练/推理
"""

import os
import random
from pathlib import Path
from typing import List, Tuple, Optional


class DatasetBuilder:
    """数据集构建器"""

    def __init__(self, processed_dir: str = "data/processed", manifest_path: str = "data/metadata/train_manifest.txt"):
        self.processed_dir = Path(processed_dir)
        self.manifest_path = Path(manifest_path)

    def build_manifest(self, output_path: Optional[str] = None) -> str:
        """
        构建数据集清单文件
        格式: <音频文件绝对路径>\t<说话人ID>
        这是 mvector 模型训练/推理的标准输入格式

        Args:
            output_path: 输出清单路径

        Returns:
            清单文件路径
        """
        output_path = Path(output_path) if output_path else self.manifest_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        entries = []

        # 遍历 processed 目录，按明星组织
        for celeb_dir in sorted(self.processed_dir.iterdir()):
            if not celeb_dir.is_dir():
                continue

            celebrity = celeb_dir.name
            speaker_id = self._get_speaker_id(celebrity)

            # 查找所有 wav 文件
            wav_files = list(celeb_dir.rglob("*.wav"))
            for wav_file in wav_files:
                abs_path = str(wav_file.absolute())
                entries.append(f"{abs_path}\t{speaker_id}")

        # 写入文件
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(entries))

        print(f"数据集清单已生成: {output_path}")
        print(f"共 {len(entries)} 条数据")

        return str(output_path)

    def split_dataset(
        self,
        manifest_path: Optional[str] = None,
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
        seed: int = 42,
    ) -> Tuple[str, str, str]:
        """
        划分训练集/验证集/测试集
        Args:
            manifest_path: 总清单文件路径
            train_ratio: 训练集比例
            val_ratio: 验证集比例
            seed: 随机种子

        Returns:
            (train_path, val_path, test_path)
        """
        manifest_path = Path(manifest_path or self.manifest_path)
        if not manifest_path.exists():
            raise FileNotFoundError(f"清单文件不存在: {manifest_path}")

        with open(manifest_path, "r") as f:
            lines = [line.strip() for line in f if line.strip()]

        random.seed(seed)
        random.shuffle(lines)

        total = len(lines)
        train_end = int(total * train_ratio)
        val_end = train_end + int(total * val_ratio)

        train_lines = lines[:train_end]
        val_lines = lines[train_end:val_end]
        test_lines = lines[val_end:]

        base_dir = manifest_path.parent
        train_path = base_dir / "train_manifest.txt"
        val_path = base_dir / "val_manifest.txt"
        test_path = base_dir / "test_manifest.txt"

        self._write_lines(train_path, train_lines)
        self._write_lines(val_path, val_lines)
        self._write_lines(test_path, test_lines)

        print(f"数据集划分完成:")
        print(f"  训练集: {len(train_lines)} 条 -> {train_path}")
        print(f"  验证集: {len(val_lines)} 条 -> {val_path}")
        print(f"  测试集: {len(test_lines)} 条 -> {test_path}")

        return str(train_path), str(val_path), str(test_path)

    def _get_speaker_id(self, celebrity: str) -> str:
        """根据明星名称生成唯一说话人ID"""
        # 使用拼音或哈希映射，确保 ID 唯一
        id_map = self._load_speaker_id_map()
        if celebrity not in id_map:
            new_id = f"SPK{len(id_map):04d}"
            id_map[celebrity] = new_id
            self._save_speaker_id_map(id_map)
        return id_map[celebrity]

    def _load_speaker_id_map(self) -> dict:
        """加载说话人ID映射表"""
        map_path = self.processed_dir.parent / "metadata" / "speaker_id_map.txt"
        if map_path.exists():
            mapping = {}
            with open(map_path, "r") as f:
                for line in f:
                    if line.strip():
                        celeb, spk_id = line.strip().split("\t")
                        mapping[celeb] = spk_id
            return mapping
        return {}

    def _save_speaker_id_map(self, mapping: dict):
        """保存说话人ID映射表"""
        map_path = self.processed_dir.parent / "metadata" / "speaker_id_map.txt"
        map_path.parent.mkdir(parents=True, exist_ok=True)
        with open(map_path, "w") as f:
            for celeb, spk_id in sorted(mapping.items()):
                f.write(f"{celeb}\t{spk_id}\n")

    @staticmethod
    def _write_lines(path: Path, lines: List[str]):
        """写入行到文件"""
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
