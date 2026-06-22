"""
音频特征分析模块 — 声纹身份证海报数据生成

基于 librosa 从原始音频提取物理特征，映射到 5 个感知维度：
  磁性 / 甜美 / 力量 / 清澈 / 独特

并基于规则生成声纹画像标签和趣味称号。
"""

import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple


def _sigmoid_scale(x: float, center: float, scale: float = 1.0) -> float:
    """Sigmoid 归一化到 0-100"""
    val = 100.0 / (1.0 + np.exp(-(x - center) * scale))
    return float(np.clip(val, 0, 100))


def _linear_scale(x: float, low: float, high: float) -> float:
    """线性归一化到 0-100"""
    if high <= low:
        return 50.0
    val = (x - low) / (high - low) * 100.0
    return float(np.clip(val, 0, 100))


def analyze_audio(audio_path: str) -> Dict:
    """
    分析音频文件，返回雷达维度 + 声纹标签 + 趣味称号

    Args:
        audio_path: 音频文件路径 (.wav / .mp3)

    Returns:
        {
            "radar": {"magnetic": int, "sweet": int, "power": int, "clear": int, "unique": int},
            "voice_tags": [str, ...],
            "fun_title": str,
        }
    """
    import librosa

    # 加载音频 (单声道, 16kHz)
    y, sr = librosa.load(audio_path, sr=16000, mono=True)

    # 限制分析时长 (取前 30 秒，足够提取特征且避免大文件慢)
    max_samples = sr * 30
    if len(y) > max_samples:
        y = y[:max_samples]

    # ── 提取物理特征 ──────────────────────────────────────
    # 基频 F0 (pyin)
    f0, voiced_flag, voiced_probs = librosa.pyin(
        y, fmin=50, fmax=800, sr=sr, frame_length=2048, hop_length=512
    )
    f0_valid = f0[~np.isnan(f0)] if f0 is not None else np.array([])
    f0_mean = float(np.mean(f0_valid)) if len(f0_valid) > 0 else 200.0
    f0_std = float(np.std(f0_valid)) if len(f0_valid) > 0 else 50.0

    # 频谱特征
    spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
    spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
    spectral_flatness = librosa.feature.spectral_flatness(y=y)[0]

    centroid_mean = float(np.mean(spectral_centroids))
    bandwidth_mean = float(np.mean(spectral_bandwidth))
    rolloff_mean = float(np.mean(spectral_rolloff))
    flatness_mean = float(np.mean(spectral_flatness))

    # 能量特征
    rms = librosa.feature.rms(y=y)[0]
    rms_mean = float(np.mean(rms))
    rms_max = float(np.max(rms))
    rms_min = float(np.min(rms[rms > 0])) if np.any(rms > 0) else 0.001
    dynamic_range = rms_max / (rms_min + 1e-8)

    # 过零率
    zcr = librosa.feature.zero_crossing_rate(y)[0]
    zcr_mean = float(np.mean(zcr))

    # 谐波/打击分离
    y_harmonic, y_percussive = librosa.effects.hpss(y)
    harmonic_energy = float(np.mean(y_harmonic ** 2))
    percussive_energy = float(np.mean(y_percussive ** 2))
    harmonic_ratio = harmonic_energy / (harmonic_energy + percussive_energy + 1e-8)

    # MFCC (用于独特性)
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc_variance = float(np.mean(np.var(mfccs, axis=1)))

    # ── 映射到 5 个维度 ──────────────────────────────────

    # 磁性: 低 F0 + 低 spectral_centroid + 高 harmonic_ratio
    magnetic = (
        _sigmoid_scale(-f0_mean, center=-180, scale=0.02) * 0.4 +
        _sigmoid_scale(-centroid_mean, center=-2000, scale=0.001) * 0.35 +
        _sigmoid_scale(harmonic_ratio, center=0.6, scale=8) * 0.25
    )

    # 甜美: 高 F0 + 高 spectral_centroid + 适中 bandwidth
    sweet = (
        _sigmoid_scale(f0_mean, center=250, scale=0.015) * 0.4 +
        _sigmoid_scale(centroid_mean, center=2500, scale=0.001) * 0.35 +
        _sigmoid_scale(-abs(bandwidth_mean - 1500), center=-500, scale=0.003) * 0.25
    )

    # 力量: 高 rms + 高 dynamic_range + 高 ZCR
    power = (
        _sigmoid_scale(rms_mean, center=0.05, scale=30) * 0.35 +
        _sigmoid_scale(np.log10(dynamic_range + 1e-8), center=1.5, scale=2) * 0.35 +
        _sigmoid_scale(zcr_mean, center=0.08, scale=15) * 0.30
    )

    # 清澈: 高 harmonic_ratio + 低 spectral_flatness + 低 ZCR
    clear = (
        _sigmoid_scale(harmonic_ratio, center=0.65, scale=10) * 0.4 +
        _sigmoid_scale(-flatness_mean, center=-0.05, scale=30) * 0.35 +
        _sigmoid_scale(-zcr_mean, center=-0.06, scale=15) * 0.25
    )

    # 独特: 高 MFCC variance + 高 F0 std + 高 rolloff variance
    rolloff_std = float(np.std(spectral_rolloff))
    unique = (
        _sigmoid_scale(mfcc_variance, center=100, scale=0.01) * 0.4 +
        _sigmoid_scale(f0_std, center=60, scale=0.02) * 0.35 +
        _sigmoid_scale(rolloff_std, center=1000, scale=0.001) * 0.25
    )

    # 取整到 0-100
    radar = {
        "magnetic": int(np.clip(round(magnetic), 5, 95)),
        "sweet": int(np.clip(round(sweet), 5, 95)),
        "power": int(np.clip(round(power), 5, 95)),
        "clear": int(np.clip(round(clear), 5, 95)),
        "unique": int(np.clip(round(unique), 5, 95)),
    }

    # ── 生成声纹标签 ──────────────────────────────────────
    voice_tags = _generate_voice_tags(radar)

    # ── 生成趣味称号 ──────────────────────────────────────
    fun_title = _generate_fun_title(radar, voice_tags)

    return {
        "radar": radar,
        "voice_tags": voice_tags,
        "fun_title": fun_title,
    }


def _generate_voice_tags(radar: Dict[str, int]) -> List[str]:
    """基于雷达维度生成 2-4 个声纹画像标签（多档位 + 多组合 + 趣味性）"""
    tags = []
    m, s, p, c, u = radar["magnetic"], radar["sweet"], radar["power"], radar["clear"], radar["unique"]

    # ── 单维度高值标签 ──
    if m > 80:
        tags.append("行走的低音炮")
    elif m > 65:
        tags.append("质感低音")
    if s > 80:
        tags.append("甜度超标")
    elif s > 65:
        tags.append("治愈系甜嗓")
    if p > 80:
        tags.append("铁肺唱将")
    elif p > 65:
        tags.append("能量满满")
    if c > 80:
        tags.append("水晶嗓")
    elif c > 65:
        tags.append("通透清亮")
    if u > 80:
        tags.append("辨识度满分")
    elif u > 65:
        tags.append("自带记忆点")

    # ── 双高组合标签 ──
    # 磁性 + X
    if m > 65 and p > 65:
        tags.append("烟嗓")
    if m > 60 and u > 65:
        tags.append("让人过耳不忘")
    if m > 60 and c > 65:
        tags.append("磁性质感声线")
    # 甜美 + X
    if s > 65 and c > 65:
        tags.append("清甜治愈系")
    if s > 60 and p > 60:
        tags.append("甜酷双面派")
    if s > 60 and m > 50:
        tags.append("又甜又飒")
    # 力量 + X
    if p > 65 and u > 60:
        tags.append("爆发力选手")
    if p > 65 and c > 60:
        tags.append("穿透力MAX")
    # 清澈 + X
    if c > 60 and u > 60:
        tags.append("自带混响")
    if c > 60 and m > 50 and m < 70:
        tags.append("清冷质感声")
    # 独特 + X
    if u > 65 and s > 55:
        tags.append("独一无二的甜")
    if u > 65 and p > 55:
        tags.append("个性爆发嗓")

    # ── 均值型/反差型标签 ──
    avg_all = (m + s + p + c + u) / 5
    if avg_all > 70:
        tags.append("六边形战士")
    if m > 60 and s > 60 and p < 50:
        tags.append("温柔狙击手")
    if p > 70 and s < 40:
        tags.append("硬核嗓")
    if s > 70 and p > 50:
        tags.append("甜心轰炸机")

    # ── 去重并限制数量 (2-4个) ──
    seen = set()
    unique_tags = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            unique_tags.append(t)
        if len(unique_tags) >= 4:
            break

    # ── 如果标签太少，兜底补充 ──
    if len(unique_tags) < 2:
        fallbacks = ["KTV隐藏歌神", "好声音潜力股", "声线有故事", "被生活耽误的歌手", "开口跪选手"]
        for fb in fallbacks:
            if fb not in seen:
                unique_tags.append(fb)
                seen.add(fb)
            if len(unique_tags) >= 2:
                break

    return unique_tags


def _generate_fun_title(radar: Dict[str, int], voice_tags: List[str]) -> str:
    """基于雷达维度和标签组合生成趣味称号（更丰富的映射）"""
    m, s, p, c, u = radar["magnetic"], radar["sweet"], radar["power"], radar["clear"], radar["unique"]
    avg_all = (m + s + p + c + u) / 5

    # 找到 Top-2 维度
    dims = [("magnetic", m), ("sweet", s), ("power", p), ("clear", c), ("unique", u)]
    dims_sorted = sorted(dims, key=lambda x: x[1], reverse=True)
    top1_name, top1_val = dims_sorted[0]
    top2_name, top2_val = dims_sorted[1]

    # ── 特例：超高单项专属称号 ──
    special_titles = [
        (80, "magnetic", "声带是低频振荡器"),
        (80, "sweet", "行走的棒棒糖"),
        (80, "power", "人体小钢炮"),
        (80, "clear", "被天使吻过的嗓音"),
        (80, "unique", "整个宇宙你最特别"),
    ]
    for threshold, dim_name, title in special_titles:
        if radar[dim_name] >= threshold:
            return title

    # ── 组合称号模板 ──
    title_map = {
        ("magnetic", "power"): "深夜电台DJ嗓",
        ("magnetic", "sweet"): "温柔杀手",
        ("magnetic", "clear"): "低音水晶",
        ("magnetic", "unique"): "辨识度拉满的低音炮",
        ("power", "magnetic"): "摇滚硬汉嗓",
        ("power", "sweet"): "甜酷双面嗓",
        ("power", "clear"): "穿透力满分的铁肺",
        ("power", "unique"): "舞台炸裂型选手",
        ("sweet", "magnetic"): "温柔治愈系",
        ("sweet", "power"): "甜心炸弹",
        ("sweet", "clear"): "邻家好声音",
        ("sweet", "unique"): "甜而不腻的独特嗓",
        ("clear", "magnetic"): "自带混响的低音",
        ("clear", "sweet"): "清泉般的声音",
        ("clear", "power"): "高亢嘹亮型",
        ("clear", "unique"): "天籁之音",
        ("unique", "magnetic"): "让人过耳不忘的声音",
        ("unique", "power"): "个性十足的爆发嗓",
        ("unique", "sweet"): "独一无二的甜",
        ("unique", "clear"): "自带混响的好声音",
    }

    title = title_map.get((top1_name, top2_name), "声线有故事的人")

    # ── 修饰增强 ──
    if "烟嗓" in voice_tags and "烟" not in title:
        title = f"被天使吻过的烟嗓"
    if avg_all > 70 and "六边" not in title and "满分" not in title and "小钢炮" not in title:
        title = f"全能声线战士"
    if top1_val > 70 and top2_val > 60:
        # 双高加修饰
        intensifiers = {
            "magnetic": "低音",
            "sweet": "甜嗓",
        }
        prefix = intensifiers.get(top1_name, "")
        if prefix and prefix not in title:
            title = f"{prefix}{title}"

    return title


def compute_star_mix(results: List[Dict]) -> List[Dict]:
    """
    将 Top-K 匹配结果转换为明星脸谱 (百分比归一化)

    Args:
        results: [{"name": "周杰伦", "score": 0.659, ...}, ...]

    Returns:
        [{"name": "周杰伦", "percent": 52}, {"name": "陈奕迅", "percent": 25}, ...]
    """
    if not results:
        return []

    scores = np.array([r["score"] for r in results], dtype=np.float64)

    # 将 cosine similarity 从 [-1, 1] 映射到 [0, 1] 再做 softmax-like 归一化
    shifted = scores + 1.0  # -> [0, 2]
    exp_scores = np.exp(shifted * 3)  # temperature scaling
    total = np.sum(exp_scores)

    if total <= 0:
        percents = np.ones(len(scores)) / len(scores)
    else:
        percents = exp_scores / total

    star_mix = []
    for i, r in enumerate(results):
        pct = int(round(percents[i] * 100))
        if pct >= 1:  # 只显示 >= 1% 的
            star_mix.append({"name": r["name"], "percent": pct})

    # 确保百分比之和为 100 (调整最大的那个)
    total_pct = sum(s["percent"] for s in star_mix)
    if star_mix and total_pct != 100:
        star_mix[0]["percent"] += (100 - total_pct)

    return star_mix


SHARE_LINK = "https://whovoice.online/"


def build_share_text(star_mix: List[Dict], fun_title: str) -> str:
    """
    生成分享文案

    Args:
        star_mix: [{"name": "周杰伦", "percent": 52}, ...]
        fun_title: "被天使吻过的烟嗓"

    Returns:
        "我的声音像 52% 的周杰伦 + 25% 的陈奕迅！WhoVoice 说我是「被天使吻过的烟嗓」，快来测测你的声纹身份证 https://whovoice.online/"
    """
    if not star_mix:
        return f"WhoVoice 说我是「{fun_title}」，快来测测你的声纹身份证 {SHARE_LINK}"

    mix_parts = []
    for s in star_mix[:3]:  # 最多 3 个
        mix_parts.append(f"{s['percent']}% 的{s['name']}")

    mix_str = " + ".join(mix_parts)
    return f"我的声音像 {mix_str}！WhoVoice 说我是「{fun_title}」，快来测测你的声纹身份证 {SHARE_LINK}"
