#!/bin/bash
# ============================================================
# WhoVoice 腾讯云服务器一键部署脚本
# 目标服务器: 82.156.119.33  (Ubuntu, 用户: ubuntu)
# 用法: bash deploy.sh
# ============================================================
set -e

PROJECT_DIR="/home/ubuntu/ljx/WhoVoice"
DATA_DIR="/home/ubuntu/ljx/data"
VENV_DIR="$PROJECT_DIR/venv"
PORT=8000

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║    WhoVoice 腾讯云服务器部署             ║"
echo "╚══════════════════════════════════════════╝"

# ─────────────────────────────────────────
# 1. 系统依赖安装
# ─────────────────────────────────────────
echo ""
echo "[1/6] 安装系统依赖..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv ffmpeg git curl

# 安装 Node.js 18.x (用于前端构建)
if ! command -v node &> /dev/null; then
    echo "  安装 Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt-get install -y -qq nodejs
else
    echo "  Node.js 已安装: $(node --version)"
fi

echo "  [OK] 系统依赖安装完成"

# ─────────────────────────────────────────
# 2. 项目文件部署
# ─────────────────────────────────────────
echo ""
echo "[2/6] 检查项目文件..."

if [ ! -d "$PROJECT_DIR" ]; then
    echo "  [ERROR] 项目目录 $PROJECT_DIR 不存在！"
    echo "  请先将项目代码上传到服务器:"
    echo "    # 在本地执行 (Windows PowerShell):"
    echo "    tar -czf whovoice_code.tar.gz --exclude=venv --exclude=node_modules --exclude=data --exclude='*.zip' WhoVoice/"
    echo "    scp whovoice_code.tar.gz ubuntu@82.156.119.33:/home/ubuntu/ljx/"
    echo "    # 然后在服务器上:"
    echo "    cd /home/ubuntu/ljx && tar -xzf whovoice_code.tar.gz"
    exit 1
fi

# 确认 data 目录已链接或存在
if [ ! -d "$PROJECT_DIR/data" ]; then
    if [ -d "$DATA_DIR" ]; then
        echo "  创建 data 软链接: $PROJECT_DIR/data -> $DATA_DIR"
        ln -s "$DATA_DIR" "$PROJECT_DIR/data"
    else
        echo "  [WARN] data 目录不存在: $DATA_DIR"
    fi
else
    echo "  data 目录已存在"
fi

echo "  [OK] 项目文件检查完成"

# ─────────────────────────────────────────
# 3. Python 虚拟环境 + 依赖安装
# ─────────────────────────────────────────
echo ""
echo "[3/6] 配置 Python 虚拟环境..."

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "  虚拟环境已创建"
fi

source "$VENV_DIR/bin/activate"

echo "  升级 pip..."
pip install --upgrade pip -q

echo "  安装 PyTorch (CPU 版，服务器无 GPU)..."
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu -q

echo "  安装项目依赖..."
pip install django djangorestframework django-cors-headers gunicorn -q
pip install numpy pandas librosa soundfile audioread webrtcvad requests -q

echo "  安装声纹识别依赖..."
pip install mvector -i https://pypi.tuna.tsinghua.edu.cn/simple -q

echo "  安装 FAISS..."
pip install faiss-cpu -q

echo "  [OK] Python 依赖安装完成"

# ─────────────────────────────────────────
# 4. 前端构建
# ─────────────────────────────────────────
echo ""
echo "[4/6] 构建前端..."

cd "$PROJECT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    npm install
fi

# 如果 dist 不存在或 package.json 比 dist 新
NEED_BUILD=true
if [ -d "dist" ] && [ "dist" -nt "package.json" ]; then
    NEED_BUILD=false
    echo "  前端已是最新，跳过构建"
fi

if [ "$NEED_BUILD" = true ]; then
    npm run build
    echo "  [OK] 前端构建完成"
fi

# ─────────────────────────────────────────
# 5. Django 数据库迁移
# ─────────────────────────────────────────
echo ""
echo "[5/6] 初始化数据库..."

cd "$PROJECT_DIR"
export INFERENCE_DEVICE=cpu
python backend/manage.py migrate --run-syncdb -v 0
echo "  [OK] 数据库初始化完成"

# ─────────────────────────────────────────
# 6. 启动服务
# ─────────────────────────────────────────
echo ""
echo "[6/6] 启动 WhoVoice 服务..."

# 获取服务器公网 IP
PUBLIC_IP="82.156.119.33"

echo ""
echo "════════════════════════════════════════════"
echo "  WhoVoice 部署完成！"
echo ""
echo "  访问地址:"
echo "    公网:   http://${PUBLIC_IP}:${PORT}"
echo "    本机:   http://127.0.0.1:${PORT}"
echo ""
echo "  推理设备: CPU (服务器无 GPU)"
echo "  项目路径: ${PROJECT_DIR}"
echo "  数据路径: ${DATA_DIR}"
echo "════════════════════════════════════════════"
echo ""

# 使用 gunicorn 启动生产服务 (后台运行)
cd "$PROJECT_DIR"
export INFERENCE_DEVICE=cpu

# 先杀掉旧进程
pkill -f "gunicorn.*whovoice" 2>/dev/null || true
sleep 1

# 启动 gunicorn
nohup gunicorn whovoice.wsgi:application \
    --chdir backend \
    --bind 0.0.0.0:${PORT} \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    > /home/ubuntu/ljx/whovoice.log 2>&1 &

echo "  服务已启动 (PID: $!)"
echo "  日志文件: /home/ubuntu/ljx/whovoice.log"
echo ""
echo "  查看状态:  ps aux | grep gunicorn"
echo "  查看日志:  tail -f /home/ubuntu/ljx/whovoice.log"
echo "  停止服务:  pkill -f gunicorn"
echo ""
