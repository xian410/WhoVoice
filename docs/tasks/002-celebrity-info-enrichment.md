# 002 — 名人信息富化：头像、简介、流派、国籍

> **创建时间**: 2026-06-23
> **关联模块**: `crawler/celebrity_info_crawler.py` `scripts/enrich_celebrity_info.py` `backend/apps/celebrities/views.py`

---

## 1. 背景与动机

当前 `celebrities_info.json` 仅存储歌手的**声纹注册元信息**（名称、颜色、音频数、代表作、spk_id），缺少面向用户展示的**富文本信息**：

| 缺失字段 | 用途 |
|----------|------|
| `avatar_url` | 歌手真实头像（列表页 & 详情页） |
| `bio` | 简介 / 生平描述（详情页展示） |
| `genre` | 音乐流派（分类筛选） |
| `nationality` | 国籍/地区（分类筛选） |
| `birth_date` | 出生日期（详情页） |

**当前头像方案**：后端用 DiceBear API 按首字母生成 SVG（`backend/apps/celebrities/views.py:158`），缺乏辨识度。

---

## 2. 方案设计

### 2.1 数据源优先级

```
┌──────────────────────────────────────────┐
│ 输入: 歌手名 (中文 / 英文 / 日文 / 韩文)    │
├──────────────────────────────────────────┤
│ ① 酷我音乐 Kuwo Music (国内歌手首选)       │
│   ├─ 搜索接口 → 提取 ARTISTID              │
│   └─ 艺人页接口 → 头像 pic300 / 简介 info   │
├──────────────────────────────────────────┤
│ ② Wikipedia REST API (国际歌手备选)        │
│   ├─ zh.wikipedia.org (中文维基)           │
│   ├─ en.wikipedia.org (英文维基)           │
│   └─ 返回 extract / thumbnail / description│
├──────────────────────────────────────────┤
│ ③ 本地缓存 (celebrity_info_cache.json)    │
│   └─ 已成功获取的信息缓存，避免重复请求      │
└──────────────────────────────────────────┘
```

### 2.2 新增文件

| 文件 | 说明 |
|------|------|
| `crawler/celebrity_info_crawler.py` | 核心爬虫模块 (Kuwo + Wikipedia) |
| `scripts/enrich_celebrity_info.py` | 批量执行脚本 |
| `data/metadata/celebrity_info_cache.json` | 运行时自动生成的缓存 |

### 2.3 修改文件

| 文件 | 修改内容 |
|------|----------|
| `backend/apps/celebrities/views.py` | 列表 API 增加 `avatar_url`, `bio`, `genre`, `nationality`；详情 API 增加 `bio`, `genre`, `nationality`, `birth_date`, `info_source`；头像优先用真实 URL |

### 2.4 数据模型变更

`celebrities_info.json` 中每个 singer 新增字段：

```json
{
  "name": "刘德华",
  "avatar_color": "#e17055",
  "avatar_url": "https://img1.kuwo.cn/star/starheads/300/xx/xx.jpg",
  "bio": "刘德华（Andy Lau），1961年9月27日出生于中国香港…",
  "genre": "Pop",
  "nationality": "中国香港",
  "birth_date": "1961-09-27",
  "info_source": "kuwo",
  "initial": "刘",
  "video_count": 2,
  "slice_count": 0,
  "representative_songs": ["..."]
}
```

> **向后兼容**：所有新字段均为可选，旧客户端忽略新字段不会出错。

---

## 3. 执行步骤

### Step 1: 预览模式（推荐首次执行）

```powershell
# Windows PowerShell
python scripts/enrich_celebrity_info.py --dry-run
```

输出示例：
```
============================================================
  WhoVoice - 名人信息富化
============================================================
  总歌手数: 421
  待富化:   421 位（缺失 avatar_url/bio）
  请求间隔: 1.5s
  模式:     DRY RUN (预览)

[1/421] 正在获取: 刘德华
  ✅ [kuwo] avatar=True bio=186chars  +5字段
[2/421] 正在获取: 那英
  ✅ [kuwo] avatar=True bio=120chars  +4字段
...
```

### Step 2: 全量富化

```powershell
# 处理所有缺失 avatar_url / bio 的歌手
python scripts/enrich_celebrity_info.py

# 可调整请求间隔（默认 1.5s）
python scripts/enrich_celebrity_info.py --delay 2.0
```

**预计耗时**：421 位歌手 × 1.5s 间隔 ≈ 10-15 分钟。

### Step 3: 验证结果

```powershell
# 检查缓存命中率
python -c "import json; c=json.load(open('data/metadata/celebrity_info_cache.json','r',encoding='utf-8')); print(f'缓存条目: {len(c)}')"

# 抽查富化结果
python -c "
import json
info = json.load(open('data/metadata/celebrities_info.json','r',encoding='utf-8'))
for s in info['singers'][:5]:
    print(f\"{s['name']}: avatar={bool(s.get('avatar_url'))} bio={len(s.get('bio',''))}chars\")
"
```

### Step 4: 重启后端

```powershell
# 重启 Django 服务以加载新数据
python backend/manage.py runserver
```

---

## 4. 完整参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--dry-run` | 预览模式，不写文件 | - |
| `--force-refresh` | 强制刷新所有歌手（忽略缓存 & 已有数据） | - |
| `--singers 刘德华,周杰伦` | 只处理指定歌手（逗号分隔） | 全部缺失的 |
| `--delay 2.0` | 请求间隔（秒） | 1.5 |
| `--resume` | 断点续传（从缓存恢复未完成的） | - |

### 常用组合

```powershell
# 只更新几个歌手
python scripts/enrich_celebrity_info.py --singers "刘德华,Taylor Swift,IU" --delay 2.0

# 全量强制刷新（慎用，耗时 15-20 分钟）
python scripts/enrich_celebrity_info.py --force-refresh --delay 2.0

# 断点续传（上次中断后继续）
python scripts/enrich_celebrity_info.py --resume
```

---

## 5. 技术细节

### 5.1 Kuwo 数据获取流程

```
搜索 "刘德华" → search.kuwo.cn/r.s
  ↓ 提取 ARTISTID
艺人页 API → www.kuwo.cn/api/www/artist/artistInfo?artistid=XX
  ↓ 解析 JSON
返回 { pic300, info, country, genre, birth }
```

### 5.2 Wikipedia 数据获取流程

```
中文名映射 → 英文名 (e.g. 刘德华 → Andy Lau)
  ↓
尝试 zh.wikipedia.org → 404?
  ↓ fallback
尝试 en.wikipedia.org → /api/rest_v1/page/summary/Andy_Lau
  ↓ 解析 JSON
返回 { thumbnail.source, extract, description }
```

### 5.3 缓存策略

- 缓存文件：`data/metadata/celebrity_info_cache.json`
- 键：歌手名的 MD5 前 12 位
- 值：富化信息 + `cached_at` 时间戳
- 未找到的歌手也缓存（`source: "none"`），避免重复失败请求

### 5.4 错误处理

- 单歌手请求失败不影响后续处理
- Kuwo 失败 → 自动降级到 Wikipedia
- 全部来源失败 → 记录 `source: "none"`，歌手信息保持不变
- 网络超时：每个请求 15 秒超时

---

## 6. 前端适配指引

后端 API 新增字段已通过 `CelebrityListView` 和 `CelebrityDetailView` 输出，前端可直接使用：

### 列表接口 `GET /api/celebrities/list/`

```json
{
  "celebrities": [
    {
      "name": "刘德华",
      "avatar_url": "https://img1.kuwo.cn/star/...",
      "bio": "刘德华（Andy Lau），1961年9月27日出生于中国香港…",
      "genre": "Pop",
      "nationality": "中国香港",
      ...
    }
  ]
}
```

### 详情接口 `GET /api/celebrities/<name>/`

新增字段：`bio`, `genre`, `nationality`, `birth_date`, `info_source`

### 前端建议

1. **头像显示**：优先使用 `avatar_url`（真实照片），回退到 DiceBear SVG
2. **列表页**：`bio` 已截取前 120 字符，可直接展示
3. **详情页**：展示完整 `bio` + `genre` / `nationality` 标签
4. **分类筛选**：可按 `genre` / `nationality` 分组过滤

---

## 7. 后续优化方向

| 方向 | 说明 |
|------|------|
| 百度百科爬虫 | 补充 Kuwo / Wikipedia 未覆盖的中文歌手 |
| 头像本地化 | 将远程头像下载到本地 CDN，避免外链失效 |
| 增量更新 | 定时任务（cron）每天检查新增歌手并补充信息 |
| 人工审核标记 | 为爬虫结果增加 `verified` 字段，支持人工修正 |
| 歌词富化 | 扩展抓取代表作歌词片段 |
