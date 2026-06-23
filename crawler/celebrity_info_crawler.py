"""
名人信息爬虫
从多源获取歌手头像、简介、流派、国籍等富文本信息

数据源优先级:
  1. 酷我音乐 (Kuwo Music) — 中文歌手首选，含头像 & 简介
  2. Wikipedia REST API — 国际歌手备选，结构化 JSON 返回
  3. 本地缓存 — 已获取信息缓存至 celebrity_info_cache.json

输出字段:
  - avatar_url      : 头像图片 URL
  - bio             : 简介 / 生平描述
  - genre           : 音乐流派
  - nationality     : 国籍 / 地区
  - source          : 数据来源标识 (kuwo / wikipedia)
"""

import ast
import hashlib
import json
import logging
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Optional

import requests

# Windows 终端编码修复
if os.name == "nt":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# 项目路径
BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_PATH = BASE_DIR / "data" / "metadata" / "celebrity_info_cache.json"

# ── Kuwo 用户代理 ────────────────────────────
KUWO_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# ── 中文名 → 英文名映射（用于 Wikipedia 查询）──
CN_TO_EN_NAME_MAP = {
    "刘德华": "Andy Lau",
    "张学友": "Jacky Cheung",
    "郭富城": "Aaron Kwok",
    "黎明": "Leon Lai",
    "周杰伦": "Jay Chou",
    "王力宏": "Leehom Wang",
    "林俊杰": "JJ Lin",
    "周华健": "Emil Chau",
    "李宗盛": "Jonathan Lee",
    "罗大佑": "Lo Ta-yu",
    "张雨生": "Chang Yu-sheng",
    "王杰": "Dave Wang",
    "齐秦": "Chyi Chin",
    "伍佰": "Wu Bai",
    "任贤齐": "Richie Jen",
    "张宇": "Phil Chang",
    "陶喆": "David Tao",
    "林志炫": "Terry Lin",
    "费玉清": "Fei Yu-ching",
    "蔡琴": "Tsai Chin",
    "邓丽君": "Teresa Teng",
    "张惠妹": "A-Mei",
    "蔡依林": "Jolin Tsai",
    "李玟": "CoCo Lee",
    "孙燕姿": "Stefanie Sun",
    "梁静茹": "Fish Leong",
    "莫文蔚": "Karen Mok",
    "刘若英": "Rene Liu",
    "张韶涵": "Angela Chang",
    "田馥甄": "Hebe Tien",
    "王心凌": "Cyndi Wang",
    "杨丞琳": "Rainie Yang",
    "蔡健雅": "Tanya Chua",
    "萧亚轩": "Elva Hsiao",
    "徐怀钰": "Yuki Hsu",
    "范玮琪": "Christine Fan",
    "徐佳莹": "Lala Hsu",
    "张靓颖": "Jane Zhang",
    "李宇春": "Chris Lee",
    "周笔畅": "Bibi Zhou",
    "张碧晨": "Diamond Zhang",
    "谭维维": "Tan Weiwei",
    "袁娅维": "Tia Ray",
    "吉克隽逸": "Jike Junyi",
    "华晨宇": "Hua Chenyu",
    "周深": "Zhou Shen",
    "毛不易": "Mao Buyi",
    "薛之谦": "Joker Xue",
    "李荣浩": "Li Ronghao",
    "张杰": "Jason Zhang",
    "许嵩": "Vae Xu",
    "汪苏泷": "Silence Wang",
    "胡彦斌": "Anson Hu",
    "陈奕迅": "Eason Chan",
    "古巨基": "Leo Ku",
    "容祖儿": "Joey Yung",
    "杨千嬅": "Miriam Yeung",
    "卫兰": "Janice Vidal",
    "谢霆锋": "Nicholas Tse",
    "陈小春": "Jordan Chan",
    "张敬轩": "Hins Cheung",
    "林峯": "Raymond Lam",
    "张国荣": "Leslie Cheung",
    "谭咏麟": "Alan Tam",
    "梅艳芳": "Anita Mui",
    "王菲": "Faye Wong",
    "郑秀文": "Sammi Cheng",
    "林忆莲": "Sandy Lam",
    "陈慧琳": "Kelly Chen",
    "梁咏琪": "Gigi Leung",
    "宇多田ヒカル": "Hikaru Utada",
    "倉木麻衣": "Mai Kuraki",
    "浜崎あゆみ": "Ayumi Hamasaki",
    "中島美嘉": "Mika Nakashima",
    "米津玄師": "Kenshi Yonezu",
    "福山雅治": "Masaharu Fukuyama",
    "IU": "IU (singer)",
    "BoA": "BoA",
    "PSY": "Psy",
}


class CelebrityInfoCrawler:
    """歌手信息爬虫 — 多源聚合头像、简介、流派、国籍"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": KUWO_UA,
        })
        self._cache: dict = {}
        self._load_cache()

    # ── 缓存管理 ──────────────────────────────

    def _load_cache(self) -> None:
        """加载本地缓存"""
        if CACHE_PATH.exists():
            try:
                with open(CACHE_PATH, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
                logger.info(f"加载缓存: {len(self._cache)} 条已缓存")
            except Exception:
                self._cache = {}
        else:
            self._cache = {}

    def _save_cache(self) -> None:
        """保存缓存到文件"""
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2)

    def _cache_key(self, name: str) -> str:
        """生成缓存键"""
        return hashlib.md5(name.encode("utf-8")).hexdigest()[:12]

    def _cached(self, name: str) -> Optional[dict]:
        """读取缓存"""
        key = self._cache_key(name)
        return self._cache.get(key)

    def _set_cache(self, name: str, info: dict) -> None:
        """写入缓存"""
        key = self._cache_key(name)
        self._cache[key] = {
            "name": name,
            **info,
            "cached_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._save_cache()

    # ── Kuwo Music ─────────────────────────────

    def _search_kuwo_artist_info(self, name: str) -> Optional[dict]:
        """
        通过酷我搜索接口获取歌手头像 & ARTISTID

        搜索接口 (search.kuwo.cn/r.s) 返回的歌曲结果中包含:
          - web_artistpic_short : 歌手头像路径 (如 "120/65/42/2631374422.jpg")
          - ARTISTID           : 歌手 ID

        头像 URL 拼接规则:
          https://img1.kuwo.cn/star/starheads/{size}/{path}
          将路径前缀 120 替换为 300 获取大图
        """
        url = "http://search.kuwo.cn/r.s"
        params = {
            "client": "kt",
            "all": name,
            "pn": 0,
            "rn": 5,
            "encoding": "utf8",
            "rformat": "json",
            "show_copyright_off": 1,
            "source": "kwplayer_ar_5.2.0.0_apk",
            "vipver": 1,
            "ft": "music",
        }
        try:
            resp = self.session.get(url, params=params, timeout=15)
            data = ast.literal_eval(resp.text)
            for item in data.get("abslist", []):
                artist_name = item.get("ARTIST", "")
                # 歌手名匹配
                if artist_name != name and name not in artist_name and artist_name not in name:
                    continue

                info = {}

                # 1. 头像 — 从搜索结果提取
                artist_pic_path = item.get("web_artistpic_short", "")
                if artist_pic_path:
                    # 路径格式: "120/65/42/2631374422.jpg" → 替换尺寸为 300
                    if artist_pic_path.startswith("120/"):
                        pic_path_300 = "300/" + artist_pic_path[4:]
                    else:
                        pic_path_300 = artist_pic_path
                    info["avatar_url"] = f"https://img1.kuwo.cn/star/starheads/{pic_path_300}"

                # 2. ARTISTID — 用于后续获取简介
                artist_id = item.get("ARTISTID", "")
                if artist_id:
                    info["artist_id"] = str(artist_id)

                if info:
                    info["source"] = "kuwo_search"
                    return info

        except Exception as e:
            logger.debug(f"  Kuwo 搜索失败 [{name}]: {e}")
        return None

    def _fetch_kuwo_artist_bio(self, artist_id: str, name: str) -> Optional[dict]:
        """
        通过酷我艺人页面接口获取简介 (需要有效 CSRF token)

        注意: 此接口有 CSRF 保护，可能不可用。
        不可用时自动回退到 Wikipedia。
        """
        # 先尝试获取 CSRF token
        try:
            resp = self.session.get(
                "https://www.kuwo.cn/",
                headers={
                    "User-Agent": KUWO_UA,
                },
                timeout=10,
            )
            csrf_token = self.session.cookies.get("kw_token", "")
        except Exception:
            csrf_token = ""

        if not csrf_token:
            logger.debug(f"  Kuwo CSRF token 缺失，跳过艺人详情")
            return None

        url = "https://www.kuwo.cn/api/www/artist/artistInfo"
        params = {"artistid": artist_id, "httpsStatus": "1"}
        headers = {
            "User-Agent": KUWO_UA,
            "Referer": "https://www.kuwo.cn/",
            "csrf": csrf_token,
        }
        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("code") != 200:
                return None

            artist_data = data.get("data", {})
            if not artist_data:
                return None

            info = {}
            desc = artist_data.get("info") or artist_data.get("desc") or ""
            if desc and len(desc) > 10:
                info["bio"] = desc.strip()

            country = artist_data.get("country") or ""
            if country:
                info["nationality"] = country

            genre = artist_data.get("genre") or ""
            if genre:
                info["genre"] = genre

            birth = artist_data.get("birth") or artist_data.get("birthday") or ""
            if birth:
                info["birth_date"] = birth

            if info:
                info["source"] = "kuwo_artist"
                return info

        except Exception as e:
            logger.debug(f"  Kuwo 艺人详情失败 [{name}]: {e}")
        return None

    def get_kuwo_info(self, name: str) -> Optional[dict]:
        """从酷我音乐获取歌手信息（入口方法）"""
        # Step 1: 从搜索获取头像
        search_info = self._search_kuwo_artist_info(name)
        if not search_info:
            logger.debug(f"  Kuwo: 搜索无结果 [{name}]")
            return None

        result = {"avatar_url": search_info.get("avatar_url", ""), "source": "kuwo"}

        # Step 2: 尝试从艺人详情页获取简介
        artist_id = search_info.get("artist_id", "")
        if artist_id:
            bio_info = self._fetch_kuwo_artist_bio(artist_id, name)
            if bio_info:
                result.update(bio_info)

        return result if (result.get("avatar_url") or result.get("bio")) else None

    # ── Wikipedia ──────────────────────────────

    def _get_wikipedia_name(self, name: str) -> str:
        """将中文名映射为 Wikipedia 查询名"""
        if name in CN_TO_EN_NAME_MAP:
            return CN_TO_EN_NAME_MAP[name]
        # 非中文名直接使用
        if not re.search(r'[\u4e00-\u9fff]', name):
            return name
        return name  # 中文名直接查中文维基

    def get_wikipedia_info(self, name: str) -> Optional[dict]:
        """
        从 Wikipedia REST API 获取摘要信息

        API: https://en.wikipedia.org/api/rest_v1/page/summary/{title}
        中文: https://zh.wikipedia.org/api/rest_v1/page/summary/{title}

        策略: 同时查询中英文 Wikipedia，优先返回 bio 更长的结果
        """
        wp_name = self._get_wikipedia_name(name)
        candidates = []

        # 尝试中/英文两个 Wikipedia
        for lang, base_url in [
            ("zh", "https://zh.wikipedia.org/api/rest_v1/page/summary"),
            ("en", "https://en.wikipedia.org/api/rest_v1/page/summary"),
        ]:
            try:
                encoded = urllib.parse.quote(wp_name.replace(" ", "_"))
                url = f"{base_url}/{encoded}"
                headers = {
                    "User-Agent": "WhoVoice/1.0 (celebrity-info-crawler; contact@whovoice.app)",
                    "Accept": "application/json",
                }
                resp = self.session.get(url, headers=headers, timeout=15)
                if resp.status_code == 404:
                    continue
                if resp.status_code != 200:
                    continue

                data = resp.json()
                if "title" not in data or data.get("type") == "disambiguation":
                    continue

                info = {}

                # 头像
                thumbnail = data.get("thumbnail", {})
                if thumbnail and thumbnail.get("source"):
                    info["avatar_url"] = thumbnail["source"]

                # 简介 — extract 字段
                extract = data.get("extract", "")
                if extract:
                    info["bio"] = extract[:500].strip()
                    if len(extract) > 500:
                        info["bio"] += "\u2026"

                # 描述
                description = data.get("description", "")
                if description:
                    desc_lower = description.lower()

                    if not info.get("genre"):
                        genre_keywords = [
                            "singer", "rapper", "rock", "pop", "jazz",
                            "folk", "electronic", "hip hop", "r&b",
                            "country", "classical", "indie",
                        ]
                        for kw in genre_keywords:
                            if kw in desc_lower:
                                info["genre"] = kw.title()
                                break

                    if not info.get("nationality"):
                        nationality_keywords = [
                            "chinese", "taiwanese", "hong kong", "japanese",
                            "korean", "american", "british", "canadian",
                            "australian", "french", "german", "italian",
                            "singapore", "malaysian", "indian",
                        ]
                        for kw in nationality_keywords:
                            if kw in desc_lower:
                                info["nationality"] = kw.title()
                                break

                if info:
                    info["source"] = f"wikipedia_{lang}"
                    info["_bio_len"] = len(extract)
                    candidates.append(info)

            except Exception as e:
                logger.debug(f"  Wikipedia ({lang}) 失败 [{name}]: {e}")
                continue

        # 返回 bio 最长的候选结果
        if candidates:
            candidates.sort(key=lambda x: x.get("_bio_len", 0), reverse=True)
            best = candidates[0]
            # 如果英文结果有头像而中文没有，合并头像
            if len(candidates) > 1 and not best.get("avatar_url"):
                for c in candidates[1:]:
                    if c.get("avatar_url"):
                        best["avatar_url"] = c["avatar_url"]
                        best["source"] += "+merged"
                        break
            best.pop("_bio_len", None)  # 移除内部字段
            return best

        return None

    # ── 聚合入口 ──────────────────────────────

    def enrich(self, name: str, force_refresh: bool = False) -> dict:
        """
        聚合多源信息，返回富化后的歌手信息

        策略:
          1. Kuwo 搜索 → 获取头像 (avatar_url)
          2. Kuwo 艺人页 → 尝试获取简介 (需要 CSRF token)
          3. Wikipedia → 获取简介 & 头像 (作为 Kuwo 的补充/回退)

        参数:
          name          : 歌手名
          force_refresh : 是否强制刷新（忽略缓存）

        返回:
          {
            "avatar_url": "https://...",
            "bio": "...",
            "genre": "Pop",
            "nationality": "Chinese",
            "source": "kuwo+wikipedia",
          }
        """
        # 1. 尝试缓存
        if not force_refresh:
            cached = self._cached(name)
            if cached:
                result = {k: v for k, v in cached.items()
                          if k not in ("name", "cached_at")}
                if result.get("avatar_url") or result.get("bio"):
                    return result

        # 2. 聚合: Kuwo (头像优先) + Wikipedia (简介优先)
        kuwo_info = self.get_kuwo_info(name)
        wiki_info = None

        # 只有在 Kuwo 缺 bio 时才查 Wikipedia
        need_bio = not kuwo_info or not kuwo_info.get("bio")
        need_avatar = not kuwo_info or not kuwo_info.get("avatar_url")

        if need_bio or need_avatar:
            wiki_info = self.get_wikipedia_info(name)

        # 合并结果: Kuwo 头像 > Wikipedia 头像
        result = {}
        sources = []

        if kuwo_info:
            if kuwo_info.get("avatar_url"):
                result["avatar_url"] = kuwo_info["avatar_url"]
                sources.append("kuwo")
            if kuwo_info.get("bio"):
                result["bio"] = kuwo_info["bio"]
            if kuwo_info.get("nationality"):
                result["nationality"] = kuwo_info["nationality"]
            if kuwo_info.get("genre"):
                result["genre"] = kuwo_info["genre"]
            if kuwo_info.get("birth_date"):
                result["birth_date"] = kuwo_info["birth_date"]

        if wiki_info:
            if not result.get("avatar_url") and wiki_info.get("avatar_url"):
                result["avatar_url"] = wiki_info["avatar_url"]
                sources.append("wikipedia")
            if not result.get("bio") and wiki_info.get("bio"):
                result["bio"] = wiki_info["bio"]
                sources.append("wikipedia")
            if not result.get("nationality") and wiki_info.get("nationality"):
                result["nationality"] = wiki_info["nationality"]
            if not result.get("genre") and wiki_info.get("genre"):
                result["genre"] = wiki_info["genre"]

        if result:
            result["source"] = "+".join(sources) if sources else "unknown"
            self._set_cache(name, result)
            return result

        # 4. 返回空结果
        empty = {"source": "none"}
        self._set_cache(name, empty)
        return empty

    def enrich_batch(self, names: list[str], force_refresh: bool = False,
                     delay: float = 1.5) -> dict[str, dict]:
        """
        批量富化歌手信息

        参数:
          names         : 歌手名列表
          force_refresh : 是否强制刷新
          delay         : 请求间隔（秒）

        返回:
          {name: {avatar_url, bio, ...}, ...}
        """
        results = {}
        total = len(names)
        for i, name in enumerate(names):
            logger.info(f"[{i+1}/{total}] 正在获取: {name}")
            try:
                info = self.enrich(name, force_refresh=force_refresh)
                results[name] = info
                status = "✅" if info.get("avatar_url") or info.get("bio") else "❌"
                source = info.get("source", "none")
                logger.info(f"  {status} [{source}] avatar={bool(info.get('avatar_url'))} bio={len(info.get('bio',''))}")
            except Exception as e:
                logger.error(f"  ❌ [{name}] 异常: {e}")
                results[name] = {"source": "error", "error": str(e)}

            # 请求间隔
            if i < total - 1:
                time.sleep(delay)

        # 统计
        success = sum(1 for v in results.values() if v.get("source") not in ("none", "error"))
        logger.info(f"\n批量富化完成: {success}/{total} 成功")
        return results


# ── 快速测试 ────────────────────────────────────

if __name__ == "__main__":
    crawler = CelebrityInfoCrawler()

    # 测试几个代表性歌手
    test_names = [
        "刘德华",       # 中文歌手 (Kuwo)
        "周杰伦",       # 中文歌手 (Kuwo)
        "Taylor Swift", # 国际歌手 (Wikipedia)
        "Adele",        # 国际歌手 (Wikipedia)
        "IU",           # 韩国歌手 (Wikipedia)
        "宇多田ヒカル",  # 日本歌手 (Wikipedia)
    ]

    for name in test_names:
        print(f"\n{'='*60}")
        print(f"  测试: {name}")
        print(f"{'='*60}")
        info = crawler.enrich(name, force_refresh=True)
        for k, v in info.items():
            val = v[:80] + "…" if isinstance(v, str) and len(v) > 80 else v
            print(f"  {k:16s}: {val}")
        time.sleep(2)
