<template>
  <div class="results">
    <h2>匹配结果</h2>
    <div class="card-list">
      <div
        v-for="(item, index) in results"
        :key="index"
        class="card"
        :class="{
          top: index === 0 && item.likely_match,
          low: index === 0 && !item.likely_match,
        }"
        @click="goToSinger(item.name)"
        style="cursor: pointer"
      >
        <div class="rank">#{{ index + 1 }}</div>
        <div
          class="avatar"
          :style="{ background: nameToColor(item.name) }"
        >
          <span class="avatar-text">
            {{ item.name?.charAt(0) || "?" }}
          </span>
        </div>
        <div class="info">
          <h3>{{ item.name }}</h3>
          <p class="similarity">相似度: {{ (item.score * 100).toFixed(1) }}%</p>
          <div class="progress-bar">
            <div
              class="progress"
              :class="progressClass(item.score)"
              :style="{ width: Math.min((item.score + 1) * 50, 100) + '%' }"
            ></div>
          </div>
          <!-- 匹配说明 -->
          <p v-if="item.note" class="match-note" :class="noteClass(item.score)">
            {{ item.note }}
          </p>
          <p v-if="!item.likely_match && index === 0" class="hint">
            💡 当前声纹库仅注册了 <strong>{{ results.length }}</strong> 位明星，
            且特征来自<strong>唱歌</strong>音频，说话声很难匹配到。
            建议上传明星的歌曲片段测试。
          </p>
          <!-- 试听按钮 -->
          <div class="preview-row">
            <button
              class="preview-btn"
              :class="{ playing: playingIndex === index }"
              @click="togglePreview(index, item.name)"
              :disabled="loadingIndex === index"
            >
              <span v-if="loadingIndex === index" class="spinner"></span>
              <span v-else>{{ playingIndex === index ? "⏸" : "▶" }}</span>
              {{ playingIndex === index ? "暂停" : "试听" }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 音频播放器（隐藏） -->
    <audio
      ref="audioPlayer"
      @ended="onAudioEnded"
      @error="onAudioError"
      style="display: none"
    ></audio>

    <!-- 分数参考说明 -->
    <div class="score-guide">
      <p><strong>相似度参考：</strong></p>
      <p>✅ &gt; 50% → 高度相似，很可能是同一个人</p>
      <p>⚠️ 30%~50% → 有一定相似度</p>
      <p>🔶 10%~30% → 略微相似</p>
      <p>❌ &lt; 10% → 差异很大，不是同一个人</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";

const props = defineProps({
  results: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["error"]);
const router = useRouter();

const AVATAR_COLORS = [
  "#1a1a2e", "#e94560", "#0f3460", "#16213e",
  "#2d3436", "#6c5ce7", "#00b894", "#e17055",
  "#0984e3", "#fdcb6e", "#00cec9", "#fd79a8",
  "#636e72", "#a29bfe", "#55efc4", "#fab1a0",
  "#81ecec", "#ff7675", "#74b9ff", "#dfe6e9",
];

function nameToColor(name) {
  if (!name) return "#1a1a2e";
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function goToSinger(name) {
  if (!name) return;
  router.push(`/celebrities/${encodeURIComponent(name)}`);
}

const audioPlayer = ref(null);
const playingIndex = ref(-1);
const loadingIndex = ref(-1);

function progressClass(score) {
  if (score >= 0.5) return "high";
  if (score >= 0.3) return "mid";
  return "low";
}

function noteClass(score) {
  if (score >= 0.5) return "note-ok";
  if (score >= 0.3) return "note-warn";
  return "note-bad";
}

function togglePreview(index, name) {
  if (!name) return;

  // 如果点击的是当前正在播放的，切换暂停/继续
  if (playingIndex.value === index) {
    if (audioPlayer.value.paused) {
      audioPlayer.value.play();
    } else {
      audioPlayer.value.pause();
    }
    return;
  }

  // 停止当前播放
  if (audioPlayer.value) {
    audioPlayer.value.pause();
    audioPlayer.value.src = "";
  }

  // 加载新的音频
  loadingIndex.value = index;
  const sampleUrl = `/api/voice-matching/sample/${encodeURIComponent(name)}/`;

  // 用 fetch 先验证是否能获取到（避免 404 的静默失败）
  fetch(sampleUrl)
    .then((res) => {
      if (!res.ok) {
        throw new Error(`状态码 ${res.status}`);
      }
      return res.blob();
    })
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      audioPlayer.value.src = url;
      audioPlayer.value.play();
      playingIndex.value = index;
      loadingIndex.value = -1;
    })
    .catch((err) => {
      loadingIndex.value = -1;
      emit("error", `获取 [${name}] 的音频样本失败: ${err.message}`);
    });
}

function onAudioEnded() {
  playingIndex.value = -1;
  // 释放 Blob URL
  if (audioPlayer.value?.src) {
    URL.revokeObjectURL(audioPlayer.value.src);
    audioPlayer.value.src = "";
  }
}

function onAudioError() {
  if (playingIndex.value >= 0) {
    const name = props.results[playingIndex.value]?.name || "未知";
    emit("error", `播放 [${name}] 的音频时出错`);
    playingIndex.value = -1;
    loadingIndex.value = -1;
    if (audioPlayer.value?.src) {
      URL.revokeObjectURL(audioPlayer.value.src);
      audioPlayer.value.src = "";
    }
  }
}
</script>

<style scoped>
.results {
  margin-top: 2rem;
}

.card-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 1rem;
}

.card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: transform 0.2s;
}

.card.top {
  border: 2px solid #4caf50;
  transform: scale(1.02);
}

.card.low {
  border: 1px solid #ffcdd2;
  background: #fff8f8;
}

.rank {
  font-size: 1.5rem;
  font-weight: bold;
  color: #999;
  min-width: 40px;
}

.card.top .rank {
  color: #4caf50;
}

.avatar {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-text {
  color: white;
  font-size: 1.5rem;
  font-weight: bold;
}

.info {
  flex: 1;
}

.info h3 {
  margin-bottom: 0.3rem;
}

.similarity {
  color: #666;
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
}

.progress-bar {
  height: 6px;
  background: #eee;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 0.5rem;
}

.progress {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.progress.high {
  background: linear-gradient(90deg, #4caf50, #8bc34a);
}

.progress.mid {
  background: linear-gradient(90deg, #ff9800, #ffc107);
}

.progress.low {
  background: linear-gradient(90deg, #f44336, #ff9800);
}

.match-note {
  font-size: 0.85rem;
  font-weight: 500;
  margin-top: 0.2rem;
}

.note-ok {
  color: #2e7d32;
}
.note-warn {
  color: #e65100;
}
.note-bad {
  color: #c62828;
}

.hint {
  margin-top: 0.4rem;
  font-size: 0.8rem;
  color: #888;
  line-height: 1.4;
  padding: 0.5rem;
  background: #fff8e1;
  border-radius: 6px;
  border-left: 3px solid #ffc107;
}

.score-guide {
  margin-top: 1.5rem;
  padding: 1rem;
  background: #f5f5f5;
  border-radius: 8px;
  font-size: 0.85rem;
  color: #666;
  line-height: 1.8;
}

/* 试听按钮 */
.preview-row {
  margin-top: 0.5rem;
}

.preview-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 14px;
  font-size: 0.8rem;
  color: #1a1a2e;
  background: #e8eaf6;
  border: 1px solid #c5cae9;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.preview-btn:hover:not(:disabled) {
  background: #c5cae9;
  border-color: #9fa8da;
}

.preview-btn.playing {
  color: #fff;
  background: #e94560;
  border-color: #e94560;
}

.preview-btn.playing:hover:not(:disabled) {
  background: #d63851;
}

.preview-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 加载旋转动画 */
.spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid #999;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
