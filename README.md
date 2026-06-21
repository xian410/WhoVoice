# WhoVoice - 声纹识别系统

上传你的声音，找到与你声线最相似的明星。WhoVoice 是一个基于深度学习声纹识别技术的娱乐性项目，通过分析语音特征向量，匹配最相似的名人声音。

## 功能特性

- **多平台数据爬取**：支持从酷我音乐、酷狗音乐、B站、QQ音乐、YouTube 等平台自动搜索和下载明星音频素材，智能调度优先级（酷我 > 酷狗 > B站）
- **智能音频预处理**：**人声分离（Demucs）→ VAD 语音端点检测（Silero）→ 音频标准化 → VAD 智能切片**，确保每个切片都包含有效人声
- **预训练模型直接推理**：基于 [mvector](https://github.com/yeyupiaoling/VoiceprintRecognition-Pytorch)，直接加载 CAM++ 预训练权重提取 192 维声纹 embedding，**无需训练**
- **大规模向量检索**：FAISS 高维向量索引，支持千万级明星声纹的毫秒级余弦相似度搜索
- **全栈 Web 系统**：Django REST Framework 后端 + Vue.js 3 前端，支持实时录音、文件上传、波形可视化、Top-K 匹配结果展示和歌手详情页
- **声音试听**：匹配结果和歌手详情页均支持在线试听明星声音样本
- **热门歌词模板**：提供经典歌词句子，支持按歌手/情绪筛选，方便用户录音时选曲
- **全量流水线**：一键完成 500+ 位歌手的爬取→预处理→声纹提取→入库全流程（支持断点续跑）
- **增量更新**：FAISS 索引支持增量添加新歌手，无需全量重建
- **灵活部署**：支持 GPU/CPU 自动切换，提供 PowerShell 一键启动脚本

## 项目结构

```
WhoVoice/
├── crawler/                        # 爬虫模块
│   ├── base_crawler.py             # 爬虫基类（search/download 接口）
│   ├── bilibili_crawler.py         # B站爬虫
│   ├── youtube_crawler.py          # YouTube爬虫
│   ├── qq_music_crawler.py         # QQ音乐爬虫
│   ├── kuwo_music_crawler.py       # 酷我音乐爬虫（主要音源）
│   ├── kugou_music_crawler.py      # 酷狗音乐爬虫
│   ├── audio_platform_crawler.py   # 音频平台爬虫（喜马拉雅等）
│   ├── scheduler.py                # 多源爬虫调度器
│   ├── metadata.py                 # 爬取元数据管理
│   └── config.py                   # 爬虫配置（歌手名单、平台参数）
│
├── preprocessing/                  # 预处理模块
│   ├── pipeline.py                 # 全流程流水线（分离→VAD→标准化→切片）
│   ├── config.py                   # 预处理配置
│   ├── vad/                        # VAD端点检测
│   │   ├── silero_vad.py           #   Silero VAD（推荐）
│   │   └── webrtc_vad.py           #   WebRTC VAD
│   ├── separation/                 # 人声分离
│   │   ├── demucs_separator.py     #   Demucs（推荐，质量更高）
│   │   └── spleeter_separator.py   #   Spleeter（备选）
│   ├── standardization.py          # 音频标准化（16kHz/单声道/16-bit）
│   ├── slicer.py                   # VAD 智能切片（合并/过滤/切割）
│   └── dataset_builder.py          # 数据集清单构建
│
├── voice_recognition/              # 声纹识别
│   └── model_loader.py             # MVectorPredictor 封装（支持 GPU/CPU 自动切换）
│
├── backend/                        # Django 后端
│   ├── manage.py                   # Django 管理脚本
│   ├── whovoice/                   # Django 项目配置（SQLite + SPA 兜底路由）
│   └── apps/                       # 业务应用
│       ├── voice_matching/         #   声纹匹配 API + 音频样本试听
│       ├── celebrities/            #   明星列表/详情/歌词模板 API
│       └── accounts/               #   账户模块（预留）
│
├── frontend/                       # Vue.js 3 前端
│   ├── src/views/                  # 页面：首页 / 歌手详情页
│   ├── src/components/             # 组件：录音器 / 波形可视化 / 结果卡片
│   ├── src/stores/                 # Pinia 状态管理
│   ├── src/api/                    # Axios API 封装
│   └── src/router.js               # Vue Router 路由配置
│
├── vector_database/                # 向量数据库
│   ├── build_index.py              # FAISS 索引构建（Flat/IVF + 增量更新）
│   ├── faiss_index/                # 构建好的索引文件
│   │   ├── celebrity.index         #   FAISS 向量索引（二进制）
│   │   └── celebrity_metadata.json #   明星映射元数据
│   └── config.py                   # 配置
│
├── models/                         # 预训练模型权重
│   └── CAMPPlus_Fbank/best_model/  # CAM++ 模型（~29MB）
│
├── scripts/                        # 运行脚本
│   ├── run_crawler.py              # 启动爬虫
│   ├── run_preprocessing.py        # 启动预处理
│   ├── extract_embeddings.py       # 批量提取声纹 + 构建/增量 FAISS 索引
│   ├── batch_pipeline.py           # 全量流水线（爬取→预处理→声纹提取→入库）
│   ├── generate_celebrity_list.py  # 生成歌手名单与详情信息
│   ├── download_pretrained_model.py# 多源自动下载预训练模型
│   └── cleanup.py                  # 数据清理工具
│
├── data/                           # 数据存储
│   ├── raw/                        # 爬取的原始音频（按明星分目录）
│   ├── processed/                  # 预处理后的纯净人声切片
│   ├── metadata/                   # 爬取元数据与歌手信息
│   └── lyrics/                     # 热门歌词模板（经典歌词句子）
│
├── serve.ps1                       # Windows 一键启动脚本（构建前端 + 启动服务）
└── serve_public.ps1                # 局域网公开访问启动脚本
```

## 安装指南

### 1. 创建虚拟环境

```bash
cd WhoVoice
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt

# 额外核心依赖
pip install mvector silero-vad demucs faiss-cpu -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> **GPU 加速**：如需 GPU 推理，安装 CUDA 版 PyTorch：
> ```bash
> pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
> ```

### 3. 安装系统工具

```bash
# Windows（推荐 scoop）
scoop install ffmpeg yt-dlp

# macOS
brew install ffmpeg yt-dlp

# Ubuntu
sudo apt install ffmpeg
pip install yt-dlp
```

### 4. 前端依赖

```bash
cd frontend
npm install
cd ..
```

### 5. 下载预训练模型

```bash
# 自动下载（多源备用：GitHub → Gitee → ModelScope）
python scripts/download_pretrained_model.py

# 或手动放置：将 CAMPPlus_Fbank.zip 解压到 models/CAMPPlus_Fbank/best_model/model.pth
```

## 使用说明

### 一键启动（推荐）

```powershell
# Windows PowerShell — 自动构建前端 + 启动后端服务
.\serve.ps1                    # 默认启动（自动检测 GPU/CPU）
.\serve.ps1 -Device cpu        # 强制 CPU 推理
.\serve.ps1 -Port 8080         # 自定义端口
```

启动后访问 `http://localhost:8000` 即可使用。

### 快速体验（已有预处理数据）

```bash
# 1. 提取声纹特征 + 构建索引
python scripts/extract_embeddings.py

# 2. 启动服务
cd backend && python manage.py runserver

# 3. 浏览器访问 http://localhost:8000
```

### 完整流程（从爬虫到识别）

```bash
# 步骤 1：爬取明星音频
python scripts/run_crawler.py --celebrities 周杰伦

# 步骤 2：预处理（人声分离 → VAD → 切片）
python scripts/run_preprocessing.py --celebrities 周杰伦

# 步骤 3：提取声纹 + 构建索引
python scripts/extract_embeddings.py --celebrity 周杰伦

# 步骤 4：启动 Web 服务
python backend/manage.py runserver
```

### 全量流水线（500+ 位歌手）

```bash
# 全量重建（爬取→预处理→声纹提取→入库，逐位歌手自动完成）
python scripts/batch_pipeline.py --rebuild

# 断点续跑（从第 100 位开始）
python scripts/batch_pipeline.py --start-from 100

# 预览模式（不执行，仅查看）
python scripts/batch_pipeline.py --dry-run
```

### 详细命令说明

**爬虫** — `scripts/run_crawler.py`

```bash
# 爬取所有配置的明星
python scripts/run_crawler.py

# 指定明星爬取（多源自动调度）
python scripts/run_crawler.py --celebrities 周杰伦 林俊杰

# 限制每个明星下载数量
python scripts/run_crawler.py --max 5
```

**预处理** — `scripts/run_preprocessing.py`

```bash
# 处理所有明星
python scripts/run_preprocessing.py

# 指定明星（推荐先单测）
python scripts/run_preprocessing.py --celebrities 周杰伦

# 处理单个文件
python scripts/run_preprocessing.py --single input.wav 周杰伦
```

**特征提取 + 建索引** — `scripts/extract_embeddings.py`

```bash
# 提取所有明星的声纹特征，构建 FAISS 索引
python scripts/extract_embeddings.py

# 只提取指定明星
python scripts/extract_embeddings.py --celebrity 周杰伦

# 增量模式（只处理新歌手，追加到已有索引）
python scripts/extract_embeddings.py --append

# 使用 GPU 加速
python scripts/extract_embeddings.py --gpu
```

## 声纹匹配原理

```
你的音频 → 16kHz标准化 → CAM++神经网络 → 192维声纹向量
                                                    ↓
                                         与FAISS库中所有明星比较
                                         余弦相似度（内积距离）
                                                    ↓
                                         返回 Top-K 最相似明星 + 相似度分数
```

### 声纹注册方式

每位明星注册时，对其所有 VAD 切片的 embedding **取平均值**作为声纹中心，消除单次录音的随机噪声，得到更稳定的声纹特征：

```
周杰伦切片1 → [0.12, -0.34, 0.87, ...]  \
周杰伦切片2 → [0.15, -0.31, 0.82, ...]   → 平均 → 周杰伦声纹中心 (192维)
周杰伦切片3 → [0.09, -0.36, 0.90, ...]  /
```

## API 接口

| 方法 | 路径                                      | 说明                                   |
| ---- | ----------------------------------------- | -------------------------------------- |
| POST | `/api/voice-matching/match/`              | 上传音频，返回 Top-K 匹配明星          |
| GET  | `/api/voice-matching/sample/<name>/`      | 获取歌手音频样本（随机切片，支持试听） |
| GET  | `/api/celebrities/list/`                  | 获取已注册声纹的明星列表（含头像信息） |
| GET  | `/api/celebrities/<name>/`                | 获取单个明星详情（歌曲、切片统计等）   |
| GET  | `/api/celebrities/lyrics-templates/`      | 获取热门歌词模板（支持按歌手/情绪筛选）|

### 匹配示例

```bash
curl -X POST http://localhost:8000/api/voice-matching/match/ \
  -F "audio=@test.wav" \
  -F "top_k=3"

# 响应
{"results": [
  {"name":"周杰伦", "score":0.659, "rank":1, "likely_match":true, "note":"✅ 声音非常相似！很可能是同一个人"},
  {"name":"林俊杰", "score":0.312, "rank":2, "likely_match":true},
  {"name":"王力宏", "score":0.185, "rank":3, "likely_match":false}
]}
```

### 相似度说明

| 相似度范围    | 含义                       |
| ------------- | -------------------------- |
| ≥ 50%         | 声音非常相似，很可能同一人 |
| 30% ~ 50%     | 有一定相似度，需更多确认   |
| 10% ~ 30%     | 略微相似，基本不同人       |
| < 10%         | 声纹差异很大，不是同一人   |

## 环境配置

通过环境变量控制推理行为：

| 环境变量           | 可选值           | 说明                                     |
| ------------------ | ---------------- | ---------------------------------------- |
| `INFERENCE_DEVICE` | `auto`（默认）   | 自动检测 CUDA，有则 GPU，无则 CPU        |
|                    | `gpu`            | 强制 GPU，不可用时回退 CPU               |
|                    | `cpu`            | 强制 CPU，适合无 GPU 的云服务器部署      |

## 数据存储

| 数据类型       | 路径                                                  | 说明                           |
| -------------- | ----------------------------------------------------- | ------------------------------ |
| 原始音频       | `data/raw/{明星名}/`                                  | 爬取下载的原始文件             |
| 纯净人声切片   | `data/processed/{明星名}/`                            | Demucs 分离 + VAD 切片后的 WAV |
| FAISS 向量索引 | `vector_database/faiss_index/celebrity.index`         | 二进制向量索引                 |
| 明星元数据     | `vector_database/faiss_index/celebrity_metadata.json` | 明星名 ↔ FAISS ID 映射         |
| 歌手信息       | `data/metadata/celebrities_info.json`                 | 歌手头像、代表作等展示信息     |
| 歌词模板       | `data/lyrics/famous_lines.json`                       | 热门歌曲经典歌词句子           |

## 技术栈

| 组件     | 技术                                                         |
| -------- | ------------------------------------------------------------ |
| 声纹模型 | CAM++（via mvector，预训练直接推理，192 维 embedding）        |
| VAD 检测 | Silero VAD（推荐）/ WebRTC VAD                               |
| 人声分离 | Demucs（推荐）/ Spleeter                                     |
| 后端框架 | Django 4.0 + Django REST Framework                           |
| 前端框架 | Vue.js 3 + Vite + Pinia + Vue Router + Axios                 |
| 向量检索 | FAISS（Flat / IVF 索引，支持增量更新）                       |
| 数据库   | SQLite（默认，零配置）                                       |
| 音频处理 | FFmpeg, librosa, torchaudio, soundfile                       |
| 爬虫     | 酷我音乐 / 酷狗音乐 / B站 / QQ音乐 / YouTube 多源调度        |

## 许可证

本项目仅供学习和娱乐用途。
