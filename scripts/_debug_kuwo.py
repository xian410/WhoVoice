#!/usr/bin/env python3
import ast, requests

r = requests.get("http://search.kuwo.cn/r.s", params={
    "client": "kt", "all": "周杰伦", "pn": 0, "rn": 30,
    "encoding": "utf8", "rformat": "json", "show_copyright_off": 1,
    "source": "kwplayer_ar_5.2.0.0_apk", "vipver": 1,
    "ft": "music"
}, timeout=15)
data = ast.literal_eval(r.text)
found = [s for s in data.get("abslist", []) if s["ARTIST"] == "周杰伦"]
print(f"Found 周杰伦 songs: {len(found)} out of {len(data.get('abslist',[]))}")
for s in found[:5]:
    print(f"  {s['NAME']} | id={s['MUSICRID']} | {s['DURATION']}s")
if not found:
    artists = set(s["ARTIST"] for s in data.get("abslist",[]))
    print(f"Artists in results: {list(artists)[:10]}")
