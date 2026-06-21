#!/usr/bin/env python3
"""测试酷狗音乐 Kugou API"""
import requests, hashlib, sys
sys.stdout.reconfigure(encoding="utf-8")

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "http://www.kugou.com/"})
s.get("http://www.kugou.com/", timeout=10)

# 搜索
r = s.get("http://mobilecdn.kugou.com/api/v3/search/song", params={
    "format": "json", "keyword": "周杰伦", "page": 1, "pagesize": 3
}, timeout=10)
data = r.json()
print(f"搜索状态: {data.get('status')}")

for s_info in data.get("data", {}).get("info", []):
    name = s_info.get("songname", "")
    singer = s_info.get("singername", "")
    h = s_info.get("hash", "").upper()
    album_id = s_info.get("album_id", "")
    duration = s_info.get("duration", 0)
    print(f"\n{singer} - {name} | {duration}s | hash={h[:16]}...")
    
    # 尝试获取下载URL - 方法1: play/getdata with album_id
    r2 = s.get("http://www.kugou.com/yy/index.php", params={
        "r": "play/getdata", "hash": h,
        "album_id": album_id, "mid": "1234567890"
    }, timeout=10)
    d2 = r2.json()
    if d2.get("data"):
        play_url = d2["data"].get("play_url", "")
        if play_url:
            print(f"  play_url: {play_url[:100]} (可下载)")
            break
        else:
            print(f"  status={d2.get('status')}, msg: 无play_url")
    else:
        print(f"  响应: {r2.text[:150]}")

print("\n测试完成")
