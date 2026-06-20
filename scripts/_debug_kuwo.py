#!/usr/bin/env python3
"""尝试不同关键词搜索邓紫棋"""
import ast, requests
import sys
sys.stdout.reconfigure(encoding="utf-8")

def search(keyword, use_ft=False):
    params = {
        "client": "kt", "all": keyword, "pn": 0, "rn": 5,
        "encoding": "utf8", "rformat": "json", "show_copyright_off": 1,
        "source": "kwplayer_ar_5.2.0.0_apk", "vipver": 1,
    }
    if use_ft:
        params["ft"] = "music"
    r = requests.get("http://search.kuwo.cn/r.s", params=params, timeout=15)
    data = ast.literal_eval(r.text)
    items = data.get("abslist", [])
    matched = [s for s in items if "邓紫棋" in s["ARTIST"] or "G.E.M" in s["ARTIST"].upper()]
    print(f"  [{keyword}] ft={use_ft}: total={data.get('TOTAL')}, matched={len(matched)}")
    for s in items[:3]:
        print(f"    {s['ARTIST']} - {s['NAME']}")
    return matched

for kw in ["邓紫棋", "G.E.M.", "GEM", "邓紫棋 歌曲"]:
    matched = search(kw, use_ft=False)
    if not matched:
        search(kw, use_ft=True)
    print()

# Also try to search directly by kuwo web API
print("=== 尝试 www.kuwo.cn 歌手搜索 ===")
import requests as req2
s = req2.Session()
s.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://www.kuwo.cn/"})
s.get("https://www.kuwo.cn/", timeout=10)
csrf = s.cookies.get("kw_token", "")
s.headers["csrf"] = csrf
r = s.get("https://www.kuwo.cn/api/www/search/searchMusicBykeyWord",
         params={"key": "邓紫棋", "pn": 1, "rn": 3}, timeout=15)
print(f"  code: {r.json().get('code')}, msg: {r.json().get('message', '')[:100]}")
