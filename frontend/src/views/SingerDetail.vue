<template>
  <div class="detail-page">
    <!-- 返回按钮 -->
    <button class="back-btn" @click="goBack">← 返回首页</button>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>加载中...</p>
    </div>

    <!-- 错误提示 -->
    <div v-else-if="errorMsg" class="error-state">
      <p>❌ {{ errorMsg }}</p>
      <button class="back-btn centered" @click="goBack">返回首页</button>
    </div>

    <!-- 歌手详情 -->
    <template v-else-if="singer">
      <!-- 头部信息 -->
      <div class="hero">
        <div
          class="avatar-large"
          :style="{ background: singer.avatar_color || '#1a1a2e' }"
        >
          <span class="avatar-letter">{{ singer.initial || singer.name?.charAt(0) || '?' }}</span>
        </div>
        <div class="hero-info">
          <h1>{{ singer.name }}</h1>
          <p class="spk-id">{{ singer.spk_id || '声纹编号' }}</p>
          <div class="stats">
            <span class="stat-item">
              <strong>{{ singer.video_count || 0 }}</strong> 个视频来源
            </span>
            <span class="stat-divider">|</span>
            <span class="stat-item">
              <strong>{{ singer.slice_count || 0 }}</strong> 条语音切片
            </span>
          </div>
          <!-- 试听按钮 -->
          <button class="preview-btn-big" @click="playSample" :disabled="previewLoading">
            <span v-if="previewLoading" class="spinner-sm"></span>
            <span v-else>{{ isPlaying ? '⏸ 暂停' : '▶ 试听声音' }}</span>
          </button>
        </div>
      </div>

      <!-- 代表作 -->
      <div v-if="singer.representative_songs?.length" class="section">
        <h2>🎵 代表歌曲</h2>
        <div class="song-tags">
          <span
            v-for="song in singer.representative_songs"
            :key="song"
            class="song-tag"
          >{{ song }}</span>
        </div>
      </div>

      <!-- B站下载的歌曲列表 -->
      <div v-if="singer.songs?.length" class="section">
        <h2>📂 已爬取歌曲 ({{ singer.songs.length }})</h2>
        <div class="song-list">
          <div
            v-for="(song, idx) in singer.songs"
            :key="idx"
            class="song-item"
            @click="playSpecific(song)"
          >
            <span class="song-idx">{{ idx + 1 }}</span>
            <div class="song-info">
              <p class="song-title">{{ song.title }}</p>
              <p class="song-meta">{{ formatDuration(song.duration) }} | B站</p>
            </div>
            <a
              v-if="song.url"
              :href="song.url"
              target="_blank"
              class="song-link"
              @click.stop
            >🔗</a>
          </div>
        </div>
      </div>

      <!-- 隐藏的音频播放器 -->
      <audio
        ref="audioPlayer"
        @ended="onAudioEnded"
        @error="onAudioError"
        style="display: none"
      ></audio>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import api from "../api";

const route = useRoute();
const router = useRouter();

const singer = ref(null);
const loading = ref(true);
const errorMsg = ref("");
const previewLoading = ref(false);
const isPlaying = ref(false);

const audioPlayer = ref(null);

onMounted(async () => {
  const name = route.params.name;
  if (!name) {
    errorMsg.value = "未指定歌手名称";
    loading.value = false;
    return;
  }

  try {
    const encodedName = encodeURIComponent(name);
    const res = await api.get(`/celebrities/${encodedName}/`);
    singer.value = res.data;
  } catch (err) {
    if (err.response?.status === 404) {
      errorMsg.value = `未找到歌手 [${route.params.name}]`;
    } else {
      errorMsg.value = "加载歌手详情失败: " + (err.response?.data?.error || err.message);
    }
  } finally {
    loading.value = false;
  }
});

function goBack() {
  router.push("/");
}

async function playSample() {
  if (!singer.value?.name) return;

  if (isPlaying.value && audioPlayer.value) {
    audioPlayer.value.pause();
    isPlaying.value = false;
    return;
  }

  previewLoading.value = true;
  const sampleUrl = `/api/voice-matching/sample/${encodeURIComponent(singer.value.name)}/`;

  try {
    const res = await fetch(sampleUrl);
    if (!res.ok) throw new Error(`状态码 ${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    audioPlayer.value.src = url;
    audioPlayer.value.play();
    isPlaying.value = true;
  } catch (err) {
    errorMsg.value = `获取试听音频失败: ${err.message}`;
  } finally {
    previewLoading.value = false;
  }
}

function playSpecific(song) {
  // 点击歌曲项打开 B站链接
  if (song.url) {
    window.open(song.url, "_blank");
  }
}

function onAudioEnded() {
  isPlaying.value = false;
  if (audioPlayer.value?.src) {
    URL.revokeObjectURL(audioPlayer.value.src);
    audioPlayer.value.src = "";
  }
}

function onAudioError() {
  isPlaying.value = false;
  errorMsg.value = "播放音频时出错";
}

function formatDuration(seconds) {
  if (!seconds) return "未知时长";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}
</script>

<style scoped>
.detail-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
  min-height: 100vh;
}

.back-btn {
  display: inline-block;
  padding: 0.5rem 1rem;
  background: #f5f5f5;
  border: 1px solid #ddd;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.9rem;
  color: #666;
  transition: all 0.2s;
  margin-bottom: 1.5rem;
}

.back-btn:hover {
  background: #e8e8e8;
  color: #333;
}

.back-btn.centered {
  display: block;
  margin: 1rem auto;
}

.loading-state,
.error-state {
  text-align: center;
  padding: 4rem 2rem;
  color: #666;
}

.spinner {
  width: 40px;
  height: 40px;
  margin: 0 auto 1rem;
  border: 3px solid #eee;
  border-top-color: #1a1a2e;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 头部 */
.hero {
  display: flex;
  gap: 1.5rem;
  align-items: center;
  padding: 2rem;
  background: white;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  margin-bottom: 1.5rem;
}

.avatar-large {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar-letter {
  color: white;
  font-size: 2.5rem;
  font-weight: bold;
}

.hero-info {
  flex: 1;
}

.hero-info h1 {
  font-size: 1.8rem;
  margin-bottom: 0.2rem;
  color: #1a1a2e;
}

.spk-id {
  font-size: 0.85rem;
  color: #999;
  font-family: monospace;
  margin-bottom: 0.5rem;
}

.stats {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  font-size: 0.9rem;
  color: #666;
  margin-bottom: 1rem;
}

.stat-divider {
  color: #ddd;
}

.preview-btn-big {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0.6rem 1.5rem;
  background: linear-gradient(135deg, #1a1a2e, #16213e);
  color: white;
  border: none;
  border-radius: 25px;
  cursor: pointer;
  font-size: 1rem;
  transition: all 0.2s;
}

.preview-btn-big:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(26,26,46,0.3);
}

.preview-btn-big:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.spinner-sm {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

/* 板块 */
.section {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 1rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.section h2 {
  font-size: 1.1rem;
  color: #1a1a2e;
  margin-bottom: 1rem;
}

/* 歌曲标签 */
.song-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.song-tag {
  display: inline-block;
  padding: 5px 14px;
  background: #e8eaf6;
  border-radius: 16px;
  font-size: 0.9rem;
  color: #283593;
}

/* 歌曲列表 */
.song-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.song-item {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 0.7rem 1rem;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.song-item:hover {
  background: #f5f5f5;
}

.song-idx {
  width: 24px;
  color: #bbb;
  font-size: 0.85rem;
  text-align: center;
  flex-shrink: 0;
}

.song-info {
  flex: 1;
  min-width: 0;
}

.song-title {
  font-size: 0.9rem;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.song-meta {
  font-size: 0.75rem;
  color: #999;
  margin-top: 2px;
}

.song-link {
  font-size: 0.9rem;
  text-decoration: none;
  color: #999;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s;
}

.song-link:hover {
  background: #e8eaf6;
  color: #1a1a2e;
}
</style>
