# WhoVoice - 声纹识别系统

上传你的声音，找到与你声线最相似的明星。WhoVoice 是一个基于深度学习声纹识别技术的娱乐性项目，通过分析语音特征向量，匹配最相似的名人声音。

## 功能特性

- **多平台数据爬取**：支持从 B站、QQ音乐、YouTube、喜马拉雅等平台自动搜索和下载明星语音素材
- **智能音频预处理**：**人声分离（Demucs）→ VAD 语音端点检测（纯净人声）→ 音频标准化 → VAD 智能切片**，确保每个切片都包含有效人声
- **预训练模型直接推理**：基于 [mvector](https://github.com/yeyupiaoling/VoiceprintRecognition-Pytorch)，直接加载 CAM++ / ECAPA-TDNN / ERes2Net 预训练权重提取 192 维声纹 embedding，**无需训练**
- **大规模向量检索**：FAISS 高维向量索引，支持千万级明星声纹的毫秒级相似度搜索
- **全栈 Web 系统**：Django REST Framework 后端 + Vue.js 3 前端，支持实时录音、文件上传、波形可视化和 Top-K 匹配结果展示
- **声纹测试工具**：内置自测脚本，支持交叉验证和自定义音频识别

## 项目结构

```
WhoVoice/
├── crawler/                        # 爬虫模块
│   ├── base_crawler.py             # 爬虫基类（search/download 接口）
│   ├── bilibili_crawler.py         # B站爬虫
│   ├── youtube_crawler.py          # YouTube爬虫
│   ├── qq_music_crawler.py         # QQ音乐爬虫
│   ├── audio_platform_crawler.py   # 音频平台爬虫（喜马拉雅等）
│   ├── scheduler.py                # 爬虫调度器
│   └── config.py                   # 爬虫配置
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
│   └── model_loader.py             # MVectorPredictor 封装（自动定位项目根目录）
│
├── backend/                        # Django 后端
│   ├── manage.py                   # Django 管理脚本
│   ├── whovoice/                   # Django 项目配置（支持 SQLite/MySQL）
│   └── apps/                       # 业务应用
│       ├── voice_matching/         #   声纹匹配 API（POST match/）
│       └── celebrities/            #   明星列表 API（GET list/）
│
├── frontend/                       # Vue.js 3 前端
│   ├── src/components/             # 组件：录音器/波形/结果卡片
│   ├── src/views/                  # 页面：首页
│   ├── src/stores/                 # Pinia 状态管理
│   └── src/api/                    # Axios API 封装（自动处理 FormData）
│
├── vector_database/                # 向量数据库
│   ├── build_index.py              # FAISS 索引构建（Flat/IVF）
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
│   ├── extract_embeddings.py       # 批量提取声纹 + 构建 FAISS 索引
│   ├── test_recognition.py         # 声纹识别测试（自测/交叉验证/自定义音频）
│   ├── download_pretrained_model.py# 多源自动下载预训练模型
│   └── run_pipeline.sh             # 全流程一键脚本
│
└── data/                           # 数据存储
    ├── raw/                        # 爬取的原始音频（按明星分目录）
    ├── processed/                  # 预处理后的纯净人声切片
    └── metadata/                   # 数据集清单
```

## 安装指南

### 1. 创建虚拟环境

```bash
cd WhoVoice
python3 -m venv venv
source venv/bin/activate
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt

# 额外核心依赖
pip install mvector silero-vad demucs faiss-cpu -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 安装系统工具

```bash
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

### 快速体验（已有预处理数据）

```bash
# 1. 提取声纹特征 + 构建索引
python scripts/extract_embeddings.py

# 2. 启动后端
cd backend && python manage.py runserver

# 3. 新开终端，启动前端
cd frontend && npm run dev

# 4. 浏览器访问 http://localhost:5173
```

### 完整流程（从爬虫到识别）

```bash

# 步骤 1：爬取明星音频
python scripts/run_crawler.py --celebrities 周杰伦

# 步骤 2：预处理（人声分离 → VAD → 切片）
python scripts/run_preprocessing.py --celebrities 周杰伦

# 步骤 3：提取声纹 + 构建索引
python scripts/extract_embeddings.py

# 步骤 4：测试识别效果
python scripts/test_recognition.py --self-test

# 步骤 5：启动 Web 服务
cd backend && python manage.py runserver   # 终端1
cd frontend && npm run dev                 # 终端2
```

### 详细命令说明

**爬虫** — `scripts/run_crawler.py`

```bash
# 爬取所有配置的明星
python scripts/run_crawler.py

# 指定明星爬取（从 B站/QQ音乐/YouTube 搜索下载）
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

# 使用其他模型
python scripts/extract_embeddings.py --model ecapa_tdnn
```

**声纹测试** — `scripts/test_recognition.py`

```bash
# 默认：抽 10 条切片快速自测
python scripts/test_recognition.py

# 完整交叉验证：21 条切片全部测试，统计准确率和相似度分布
python scripts/test_recognition.py --self-test

# 自定义音频识别
python scripts/test_recognition.py --audio /path/to/test.wav

```

**全流程一键运行**

```bash
./scripts/run_pipeline.sh
```

## 声纹匹配原理

```
你的音频 → 16kHz标准化 → CAM++神经网络 → 192维声纹向量
                                                    ↓
                                         与FAISS库中所有明星比较
                                         余弦相似度（内积距离）
                                                    ↓
                                         最高分 > 10% → 返回匹配结果
                                         最高分 ≤ 10% → 返回"未匹配到"
```

### 声纹注册方式

每位明星注册时，对其所有 VAD 切片的 embedding **取平均值**作为声纹中心，消除单次录音的随机噪声，得到更稳定的声纹特征：

```
周杰伦切片1 → [0.12, -0.34, 0.87, ...]  \
周杰伦切片2 → [0.15, -0.31, 0.82, ...]   → 平均 → 周杰伦声纹中心 (192维)
周杰伦切片3 → [0.09, -0.36, 0.90, ...]  /
```

# 终端1 - 后端

cd backend && python3 manage.py runserver 8000

# 终端2 - 前端

cd frontend && npx vite --host 127.0.0.1

## API 接口

| 方法 | 路径                         | 说明                                           |
| ---- | ---------------------------- | ---------------------------------------------- |
| POST | `/api/voice-matching/match/` | 上传音频（字段: `audio`），返回 Top-K 匹配明星 |
| GET  | `/api/celebrities/list/`     | 获取已注册声纹的明星列表                       |

### 匹配示例

```bash
curl -X POST http://localhost:8000/api/voice-matching/match/ \
  -F "audio=@test.wav" \
  -F "top_k=3"

# 响应
{"results": [
  {"name":"周杰伦", "score":0.659, "rank":1},
  {"name":"林俊杰", "score":0.312, "rank":2}
]}
```

## 数据存储

| 数据类型       | 路径                                                  | 说明                           |
| -------------- | ----------------------------------------------------- | ------------------------------ |
| 原始音频       | `data/raw/{明星名}/`                                  | 爬取下载的原始文件             |
| 纯净人声切片   | `data/processed/{明星名}/`                            | Demucs 分离 + VAD 切片后的 WAV |
| FAISS 向量索引 | `vector_database/faiss_index/celebrity.index`         | 二进制向量索引                 |
| 明星元数据     | `vector_database/faiss_index/celebrity_metadata.json` | 明星名 ↔ FAISS ID 映射         |
| 预处理日志     | `data/metadata/train_manifest.txt`                    | 数据集清单                     |

## 技术栈

| 组件     | 技术                                                         |
| -------- | ------------------------------------------------------------ |
| 声纹模型 | CAM++ / ECAPA-TDNN / ERes2Net（via mvector，预训练直接推理） |
| VAD 检测 | Silero VAD（推荐）/ WebRTC VAD                               |
| 人声分离 | **Demucs（推荐，质量更高）** / Spleeter                      |
| 后端框架 | Django 4.0 + Django REST Framework                           |
| 前端框架 | Vue.js 3 + Vite + Pinia + Axios                              |
| 向量检索 | **FAISS**（CPU，Flat / IVF 索引）                            |
| 数据库   | **SQLite**（默认，零配置）/ MySQL 8.0                        |
| 音频处理 | FFmpeg, librosa, torchaudio, soundfile                       |

## 许可证

本项目仅供学习和娱乐用途。
