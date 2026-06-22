#!/usr/bin/env python3
"""
声纹模型测试评估脚本 (优化版: 预提取所有 embedding，内存计算相似度)
=============================================================
使用真实歌手数据评估 CAM++ 声纹模型的匹配效果

测试方法:
  - 正样本对: 同一歌手的两个不同音频文件（应匹配）→ cosine 相似度应高
  - 负样本对: 不同歌手的音频文件（应不匹配）→ cosine 相似度应低
  - FAISS 检索: 每个测试音频在整个声纹库中搜索，看正确歌手是否在 Top-K

输出指标:
  - Top-1 / Top-3 / Top-5 准确率
  - 正负样本相似度分布
  - EER (Equal Error Rate) — 等错误率，越低越好
  - 最佳阈值 (max F1)
  - 各阈值下的 Precision / Recall / F1 / TPR / FPR
  - Top-1 误匹配详情

用法:
  python scripts/evaluate_model.py --top-n 15
  python scripts/evaluate_model.py --singers 刘德华 张学友 周杰伦
"""

import sys, os, json, time, random, gc, hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np

RAW_DIR = Path("data/raw")
INDEX_FILE = Path("vector_database/faiss_index/celebrity.index")
META_FILE = Path("vector_database/faiss_index/celebrity_metadata.json")
EMBEDDING_CACHE = Path("vector_database/faiss_index/eval_cache")
TOP_K_EVAL = [1, 3, 5]

TEST_SINGERS = [
    "刘德华", "张学友", "周杰伦", "陈奕迅", "王力宏",
    "刘欢", "李宗盛", "孙楠", "陶喆", "刀郎",
    "莫文蔚", "田馥甄", "那英", "温岚", "韩红",
    "Usher", "PSY", "Tank", "雷·查尔斯", "安德烈·波切利",
    "王杰", "朴树", "张国荣",
]

BACKUP_SINGERS = [
    "汪峰", "双笙", "吉克隽逸", "卫兰", "VAVA", "刘柏辛",
]


def _stable_hash(s: str) -> str:
    """确定性哈希，用于缓存文件名"""
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:12]


def collect_test_data(singers_list, max_files=3):
    """收集测试数据，每个歌手取最多 max_files 个音频"""
    data = {}
    for name in singers_list:
        d = RAW_DIR / name
        if not d.is_dir():
            continue
        files = sorted([
            str(f.absolute()) for f in d.rglob("*")
            if f.suffix.lower() in (".wav", ".mp3", ".m4a")
            and "demucs_output" not in f.parts and "tmp" not in f.parts
        ])
        if len(files) >= 2:
            data[name] = files[:max_files]
    return data


def extract_all(recognizer, test_data):
    """
    预提取所有测试音频的 embedding，缓存到磁盘避免重复计算
    返回 {singer_name: [emb1, emb2, ...]}
    """
    EMBEDDING_CACHE.mkdir(parents=True, exist_ok=True)
    result = {}
    total_files = sum(len(files) for files in test_data.values())
    done = 0

    for name, files in test_data.items():
        embs = []
        for fpath in files:
            # 缓存键: 文件路径 + 文件修改时间
            fpath_obj = Path(fpath)
            stat_key = f"{fpath}|{fpath_obj.stat().st_size}|{int(fpath_obj.stat().st_mtime)}"
            cache_key = _stable_hash(stat_key)
            cache_path = EMBEDDING_CACHE / f"{cache_key}.npy"

            if cache_path.exists():
                emb = np.load(str(cache_path))
            else:
                emb = recognizer.extract_embedding(fpath)
                np.save(str(cache_path), emb)
            embs.append(emb)
            done += 1
            if done % 10 == 0:
                print(f"    特征提取进度: {done}/{total_files}")
        result[name] = embs

    print(f"    特征提取完成: {done}/{total_files}")
    return result


def evaluate_retrieval(embedding_dict, index, metadata):
    """
    评估 FAISS 检索 (Top-K 准确率)
    用每个测试 audio 的 embedding 查询索引
    """
    celebrities = metadata["celebrities"]
    name_to_idx = {name: i for i, name in enumerate(celebrities)}
    results = []

    for singer_name, embs in embedding_dict.items():
        if singer_name not in name_to_idx:
            continue
        for emb in embs:
            query = emb.reshape(1, -1).astype(np.float32)
            norm = np.linalg.norm(query)
            if norm > 0:
                query = query / norm

            distances, indices = index.search(query, max(TOP_K_EVAL))
            top_k_names = [celebrities[int(i)] for i in indices[0]
                           if i != -1 and i < len(celebrities)]
            rank = (top_k_names.index(singer_name) + 1
                    if singer_name in top_k_names else 999)

            results.append({
                "query_name": singer_name,
                "truth_rank": rank,
                "top1_name": top_k_names[0] if top_k_names else "N/A",
                "top1_score": float(distances[0][0]),
                "in_top1": rank == 1,
                "in_top3": rank <= 3,
                "in_top5": rank <= 5,
            })
    return results


def evaluate_pairs_fast(embedding_dict, test_data, max_neg=200):
    """
    快速评估正负样本对（使用预提取的 embedding，numpy 批量计算）
    """
    all_names = list(embedding_dict.keys())
    pos_scores, neg_scores = [], []
    pos_details, neg_details = [], []

    # ── 正样本对: 同一歌手不同音频 → cosine ──
    for name, embs in embedding_dict.items():
        files = test_data[name]
        for i in range(len(embs)):
            for j in range(i + 1, len(embs)):
                sim = float(np.dot(embs[i], embs[j]) /
                            (np.linalg.norm(embs[i]) * np.linalg.norm(embs[j])))
                pos_scores.append(sim)
                pos_details.append((name, Path(files[i]).name, Path(files[j]).name, sim))

    # ── 负样本对: 不同歌手 → 随机采样 ──
    neg_pairs = set()
    attempts = 0
    while len(neg_scores) < max_neg and attempts < max_neg * 5:
        attempts += 1
        a, b = random.sample(all_names, 2)
        if a == b or (a, b) in neg_pairs or (b, a) in neg_pairs:
            continue
        neg_pairs.add((a, b))

        emb_a = random.choice(embedding_dict[a])
        emb_b = random.choice(embedding_dict[b])
        sim = float(np.dot(emb_a, emb_b) /
                    (np.linalg.norm(emb_a) * np.linalg.norm(emb_b)))
        neg_scores.append(sim)
        neg_details.append((a, b, "", "", sim))

    return pos_scores, neg_scores, pos_details, neg_details


def compute_metrics(retrieval_results, pos_scores, neg_scores):
    """计算所有评估指标"""
    metrics = {}

    # Top-K accuracy
    total = len(retrieval_results)
    for k in TOP_K_EVAL:
        correct = sum(1 for r in retrieval_results if r[f"in_top{k}"])
        metrics[f"top{k}_accuracy"] = {
            "correct": correct, "total": total,
            "accuracy": correct / total if total > 0 else 0
        }

    # MRR
    mrr = sum(1.0 / r["truth_rank"] for r in retrieval_results
              if r["truth_rank"] != 999) / total if total > 0 else 0
    metrics["mrr"] = round(mrr, 4)

    # 正负样本统计
    pos_arr = np.array(pos_scores)
    neg_arr = np.array(neg_scores)

    def _stats(arr, label):
        if len(arr) == 0:
            return {"count": 0}
        h, _ = np.histogram(arr, bins=10, range=(0.0, 1.0))
        return {
            "count": len(arr), "mean": float(np.mean(arr)),
            "median": float(np.median(arr)), "std": float(np.std(arr)),
            "min": float(np.min(arr)), "max": float(np.max(arr)),
            "histogram": [{"range": f"{i/10:.1f}-{(i+1)/10:.1f}", "count": int(h[i])}
                          for i in range(10)],
        }

    metrics["positive_pairs"] = _stats(pos_arr, "positive")
    metrics["negative_pairs"] = _stats(neg_arr, "negative")

    # EER + 最佳阈值
    eer, best_t, best_f1 = _compute_eer(pos_arr, neg_arr)
    metrics["eer"] = round(eer, 4)
    metrics["best_threshold"] = round(best_t, 4)
    metrics["best_f1"] = round(best_f1, 4)

    # 各阈值性能
    thresholds = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.7]
    thresh_metrics = []
    for t in thresholds:
        tp = int(np.sum(pos_arr >= t))
        fn = int(np.sum(pos_arr < t))
        fp = int(np.sum(neg_arr >= t))
        tn = int(np.sum(neg_arr < t))
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        tpr = rec
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
        thresh_metrics.append({
            "threshold": t, "precision": round(prec, 4), "recall": round(rec, 4),
            "f1": round(f1, 4), "tpr": round(tpr, 4), "fpr": round(fpr, 4),
            "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        })
    metrics["threshold_analysis"] = thresh_metrics

    return metrics


def _compute_eer(pos_arr, neg_arr):
    """计算 EER 和最佳 F1 阈值"""
    if len(pos_arr) == 0 or len(neg_arr) == 0:
        return 1.0, 0.5, 0.0
    all_scores = np.concatenate([pos_arr, neg_arr])
    lo, hi = float(np.min(all_scores)), float(np.max(all_scores))
    search = np.linspace(lo, hi, 200)

    best_eer = 1.0
    best_thresh = 0.5
    best_f1_val = 0.0
    best_f1_thresh = 0.5

    for t in search:
        fn = int(np.sum(pos_arr < t))
        fp = int(np.sum(neg_arr >= t))
        tp = int(np.sum(pos_arr >= t))
        tn = int(np.sum(neg_arr < t))

        far = fp / (fp + tn) if (fp + tn) > 0 else 0
        frr = fn / (fn + tp) if (fn + tp) > 0 else 0
        delta = abs(far - frr)
        if delta < best_eer:
            best_eer = delta
            best_thresh = t

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        if f1 > best_f1_val:
            best_f1_val = f1
            best_f1_thresh = t

    eer_val = (float(np.sum(neg_arr >= best_thresh)) / len(neg_arr) +
               float(np.sum(pos_arr < best_thresh)) / len(pos_arr)) / 2
    return eer_val, best_f1_thresh, best_f1_val


def print_report(retrieval_results, metrics, elapsed):
    sep = "=" * 72
    print(f"\n{sep}")
    print(f"  WhoVoice 声纹模型评估报告")
    print(f"  {'='*30}")
    print(f"  测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  耗时: {elapsed:.1f}s")
    print(f"{sep}")

    # 一、检索准确率
    total_q = len(retrieval_results)
    print(f"\n一、FAISS 检索准确率 (共 {total_q} 次查询)")
    print("-" * 50)
    for k in TOP_K_EVAL:
        m = metrics[f"top{k}_accuracy"]
        bar = "█" * int(m["accuracy"] * 40) + "░" * (40 - int(m["accuracy"] * 40))
        print(f"  Top-{k}:  {m['accuracy']*100:5.1f}%  ({m['correct']}/{m['total']})  {bar}")
    print(f"  MRR:    {metrics['mrr']:.4f}")

    # 二、相似度分布
    print(f"\n二、正/负样本相似度分布")
    print("-" * 50)
    for label, key in [("正样本 (同歌手)", "positive_pairs"),
                        ("负样本 (不同歌手)", "negative_pairs")]:
        m = metrics[key]
        print(f"  {label}:")
        print(f"    数量={m['count']:4d}  均值={m['mean']:.4f}  中位数={m['median']:.4f}")
        print(f"    标准差={m['std']:.4f}  最小值={m['min']:.4f}  最大值={m['max']:.4f}")
        hist = m.get("histogram", [])
        if hist and m["count"] > 0:
            mx = max(h["count"] for h in hist)
            scale = 30 / mx if mx > 0 else 1
            for h in hist:
                bar_s = "█" * int(h["count"] * scale)
                print(f"    [{h['range']}] {bar_s} {h['count']}")

    # 三、EER
    print(f"\n三、EER & 最佳阈值")
    print("-" * 50)
    print(f"  EER (等错误率):       {metrics['eer']:.4f}")
    print(f"  最佳阈值 (max F1):    {metrics['best_threshold']:.4f}")
    print(f"  最佳 F1:              {metrics['best_f1']:.4f}")

    # 四、阈值分析
    print(f"\n四、各阈值下的分类性能")
    print("-" * 72)
    print(f"  {'阈值':>6s} | {'精确率':>7s} | {'召回率':>7s} | {'F1':>6s} | {'TPR':>5s} | {'FPR':>5s} | {'TP':>3s} {'FN':>3s} {'FP':>3s} {'TN':>3s}")
    print("-" * 72)
    for tm in metrics["threshold_analysis"]:
        bar_tpr = "█" * int(tm["tpr"] * 20)
        print(f"  {tm['threshold']:>6.2f} | {tm['precision']:>7.4f} | {tm['recall']:>7.4f} | {tm['f1']:>6.4f} | {bar_tpr:<20s} | {tm['tpr']:.2f} | {tm['tp']:3d} {tm['fn']:3d} {tm['fp']:3d} {tm['tn']:3d}")

    # 五、误匹配
    errors = [r for r in retrieval_results if not r["in_top1"]]
    print(f"\n五、Top-1 误匹配详情 ({len(errors)}/{total_q})")
    print("-" * 72)
    if errors:
        for r in errors[:10]:
            print(f"  ❌ [{r['query_name']}] rank=#{r['truth_rank']} top1={r['top1_name']} (score={r['top1_score']:.4f})")
        if len(errors) > 10:
            print(f"  ... 还有 {len(errors) - 10} 个")
    else:
        print(f"  ✅ 全部命中 Top-1！")

    # 六、正确案例
    corrects = [r for r in retrieval_results if r["in_top1"]]
    print(f"\n六、Top-1 正确示例 ({len(corrects)}/{total_q})")
    print("-" * 72)
    for r in corrects[:5]:
        print(f"  ✅ [{r['query_name']}] top1={r['top1_name']} (score={r['top1_score']:.4f})")

    # 总结
    print(f"\n{sep}")
    t1 = metrics["top1_accuracy"]["accuracy"]
    print(f"  综合评分 = {t1 * 40 + metrics['mrr'] * 30 + (1 - metrics['eer']) * 30:.1f}/100")
    print(f"  Top-1: {t1*100:.1f}% | MRR: {metrics['mrr']:.4f} | EER: {metrics['eer']:.4f} | F1@best: {metrics['best_f1']:.4f}")
    print(f"{sep}\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="声纹模型评估")
    parser.add_argument("--top-n", type=int, default=15, help="测试歌手数")
    parser.add_argument("--singers", nargs="+", default=None, help="指定测试歌手")
    args = parser.parse_args()

    test_names = args.singers or TEST_SINGERS[:args.top_n]
    print(f"收集测试数据 ({len(test_names)} 位歌手)...")
    test_data = collect_test_data(test_names)

    # 补充
    if len(test_data) < args.top_n:
        for name in BACKUP_SINGERS:
            if len(test_data) >= args.top_n:
                break
            if name not in test_data:
                test_data.update(collect_test_data([name]))

    print(f"  测试歌手: {len(test_data)} 位")
    for name, files in test_data.items():
        fnames = [Path(f).name for f in files]
        print(f"    {name}: {', '.join(fnames)}")

    # 加载模型
    print(f"\n加载声纹模型...")
    from voice_recognition.model_loader import VoiceprintRecognizer
    rec = VoiceprintRecognizer(use_gpu=None)
    t0 = time.time()

    # 预提取所有 embedding
    print(f"\n提取特征 ({sum(len(f) for f in test_data.values())} 个文件)...")
    embedding_dict = extract_all(rec, test_data)
    gc.collect()

    # FAISS 检索
    import faiss
    retrieval_results = []
    if INDEX_FILE.exists():
        index = faiss.read_index(str(INDEX_FILE))
        metadata = json.load(open(META_FILE, "r", encoding="utf-8"))
        print(f"\nFAISS 检索 ({sum(len(v) for v in embedding_dict.values())} 次查询)...")
        retrieval_results = evaluate_retrieval(embedding_dict, index, metadata)
        print(f"  完成: {len(retrieval_results)} 次")
    else:
        print(f"\nFAISS 索引不存在，跳过检索评估")

    # 正负样本对
    print(f"\n正负样本对评估...")
    pos_scores, neg_scores, pos_d, neg_d = evaluate_pairs_fast(embedding_dict, test_data)
    print(f"  正样本对: {len(pos_scores)} | 负样本对: {len(neg_scores)}")

    elapsed = time.time() - t0
    metrics = compute_metrics(retrieval_results, pos_scores, neg_scores)
    print_report(retrieval_results, metrics, elapsed)

    # 保存结果
    out = {
        "summary": {
            "test_singers": len(test_data), "retrieval_queries": len(retrieval_results),
            "positive_pairs": len(pos_scores), "negative_pairs": len(neg_scores),
            "elapsed_seconds": round(elapsed, 1),
        },
        "metrics": {
            "top1_accuracy": metrics["top1_accuracy"]["accuracy"],
            "top3_accuracy": metrics["top3_accuracy"]["accuracy"],
            "top5_accuracy": metrics["top5_accuracy"]["accuracy"],
            "mrr": metrics["mrr"],
            "positive_mean": metrics["positive_pairs"]["mean"],
            "negative_mean": metrics["negative_pairs"]["mean"],
            "eer": metrics["eer"],
            "best_threshold": metrics["best_threshold"],
            "best_f1": metrics["best_f1"],
        },
    }
    out_path = "evaluation_result.json"
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"详细结果已保存到: {out_path}")


if __name__ == "__main__":
    main()
