"""
预处理模块配置
"""

# 音频标准化参数
TARGET_SAMPLE_RATE = 16000  # 目标采样率 (Hz)
TARGET_CHANNELS = 1         # 目标声道数 (单声道)
TARGET_BIT_DEPTH = 16       # 目标位深度 (16-bit PCM)

# 音频切片参数
SLICE_DURATION_MIN = 5.0    # 最小切片时长 (秒)
SLICE_DURATION_MAX = 10.0   # 最大切片时长 (秒)
MIN_SILENCE_DURATION = 0.3  # VAD 最小静音段时长 (秒)
MIN_SPEECH_DURATION = 1.0   # 最小有效语音段时长 (秒)

# VAD 配置
VAD_METHOD = "silero"       # 可选: "silero", "webrtc"
SILERO_VAD_THRESHOLD = 0.5  # Silero VAD 置信度阈值
WEBRTC_VAD_MODE = 3        # WebRTC VAD 模式 (0-3, 3=最激进)

# 人声分离配置
SEPARATION_METHOD = "demucs"  # 可选: "spleeter", "demucs" (demucs 质量更高)
SPLEETER_MODEL = "spleeter:2stems"  # 2stems = 人声+伴奏
DEMUCS_MODEL = "htdemucs"         # Demucs 模型

# 输入输出路径
RAW_DATA_DIR = "data/raw"
PROCESSED_DATA_DIR = "data/processed"
DATASET_MANIFEST_PATH = "data/metadata/train_manifest.txt"
