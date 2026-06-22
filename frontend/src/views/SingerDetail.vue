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
      <!-- 头部信息卡片 -->
      <div class="hero">
        <div class="avatar-wrapper">
          <img
            v-if="singer.avatar_url"
            :src="singer.avatar_url"
            :alt="singer.name"
            class="avatar-img"
            @error="avatarFailed = true"
          />
          <div
            v-if="avatarFailed || !singer.avatar_url"
            class="avatar-fallback"
            :style="{ background: singer.avatar_color || '#1a1a2e' }"
          >
            <span class="avatar-letter">{{ singer.initial || singer.name?.charAt(0) || '?' }}</span>
          </div>
        </div>

        <div class="hero-info">
          <h1 class="singer-name">{{ singer.name }}</h1>
          <p class="spk-id">声纹编号: {{ singer.spk_id || '未分配' }}</p>

          <!-- 数据统计 -->
          <div class="stats-row">
            <div class="stat-card">
              <span class="stat-num">{{ singer.total_songs || 0 }}</span>
              <span class="stat-label">收录歌曲</span>
            </div>
            <div class="stat-card">
              <span class="stat-num">{{ singer.video_count || 0 }}</span>
              <span class="stat-label">视频来源</span>
            </div>
            <div class="stat-card">
              <span class="stat-num">{{ singer.slice_count || 0 }}</span>
              <span class="stat-label">语音切片</span>
            </div>
          </div>

          <!-- 试听按钮 -->
          <button class="preview-btn-big" @click="playSample" :disabled="previewLoading">
            <span v-if="previewLoading" class="spinner-sm"></span>
            <span v-else class="play-icon">{{ isPlaying ? '⏸' : '▶' }}</span>
            {{ isPlaying ? '暂停试听' : '试听声音' }}
          </button>
        </div>
      </div>

      <!-- 数据来源平台 -->
      <div v-if="singer.platforms?.length" class="section platforms-section">
        <h2 class="section-title">
          <span class="section-icon">📡</span>
          数据来源
        </h2>
        <div class="platform-badges">
          <span
            v-for="p in singer.platforms"
            :key="p.key"
            class="platform-badge"
            :style="{ borderColor: p.color, color: p.color }"
          >
            <span class="platform-icon">{{ p.icon }}</span>
            {{ p.label }}
            <span class="platform-count">{{ p.count }}首</span>
          </span>
        </div>
      </div>

      <!-- 代表作 -->
      <div v-if="singer.representative_songs?.length" class="section">
        <h2 class="section-title">
          <span class="section-icon">⭐</span>
          代表作品
        </h2>
        <div class="rep-songs">
          <div
            v-for="(song, idx) in singer.representative_songs"
            :key="idx"
            class="rep-song-card"
          >
            <span class="rep-rank">{{ idx + 1 }}</span>
            <span class="rep-title">{{ cleanSongTitle(song) }}</span>
          </div>
        </div>
      </div>

      <!-- 收录歌曲列表 -->
      <div v-if="singer.songs?.length" class="section">
        <h2 class="section-title">
          <span class="section-icon">📂</span>
          收录歌曲
          <span class="song-count-badge">{{ singer.songs.length }}首</span>
        </h2>
        <div class="song-list">
          <div
            v-for="song in singer.songs"
            :key="song.index"
            class="song-item"
          >
            <span class="song-idx">{{ song.index + 1 }}</span>
            <div class="song-info">
              <p class="song-title">{{ song.title }}</p>
              <p class="song-meta">
                <span
                  class="platform-tag"
                  :style="{ background: song.platform_color + '20', color: song.platform_color }"
                >{{ song.platform_icon }} {{ song.platform_label }}</span>
                <span class="duration">{{ formatDuration(song.duration) }}</span>
              </p>
            </div>
            <a
              v-if="song.url"
              :href="song.url"
              target="_blank"
              rel="noopener noreferrer"
              class="song-link"
              @click.stop
              title="在平台中打开"
            >🔗</a>
          </div>
        </div>
      </div>

      <!-- 外部链接 -->
      <div v-if="singer.external_links?.length" class="section">
        <h2 class="section-title">
          <span class="section-icon">🌐</span>
          在音乐平台搜索
        </h2>
        <div class="ext-links">
          <a
            v-for="link in singer.external_links"
            :key="link.platform"
            :href="link.url"
            target="_blank"
            rel="noopener noreferrer"
            class="ext-link-card"
          >
            <span class="ext-icon">{{ getPlatformIcon(link.platform) }}</span>
            <span class="ext-label">{{ link.label }}</span>
            <span class="ext-arrow">→</span>
          </a>
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
const avatarFailed = ref(false);

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

function cleanSongTitle(title) {
  // 去掉 "歌手名 - " 前缀
  if (title && title.includes(" - ")) {
    return title.split(" - ").slice(1).join(" - ");
  }
  return title;
}

function getPlatformIcon(platform) {
  const icons = {
    kuwo: "🎵",
    bilibili: "📺",
    qq_music: "🎶",
    netease: "☁️",
  };
  return icons[platform] || "🔍";
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

/* ===== 头部卡片 ===== */
.hero {
  display: flex;
  gap: 2rem;
  align-items: flex-start;
  padding: 2rem;
  background: white;
  border-radius: 16px;
  box-shadow: 0 2px 16px rgba(0,0,0,0.08);
  margin-bottom: 1.2rem;
}

.avatar-wrapper {
  flex-shrink: 0;
}

.avatar-img {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  object-fit: cover;
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
}

.avatar-fallback {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
}

.avatar-letter {
  color: white;
  font-size: 3rem;
  font-weight: bold;
  text-transform: uppercase;
}

.hero-info {
  flex: 1;
  min-width: 0;
}

.singer-name {
  font-size: 2rem;
  font-weight: 700;
  color: #1a1a2e;
  margin-bottom: 0.3rem;
  line-height: 1.2;
}

.spk-id {
  font-size: 0.82rem;
  color: #aaa;
  font-family: 'Courier New', monospace;
  margin-bottom: 1rem;
}

/* 统计数字 */
.stats-row {
  display: flex;
  gap: 0.8rem;
  margin-bottom: 1.2rem;
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.6rem 1rem;
  background: #f8f9fa;
  border-radius: 10px;
  min-width: 72px;
}

.stat-num {
  font-size: 1.3rem;
  font-weight: 700;
  color: #1a1a2e;
}

.stat-label {
  font-size: 0.72rem;
  color: #888;
  margin-top: 2px;
}

/* 试听按钮 */
.preview-btn-big {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0.7rem 1.8rem;
  background: linear-gradient(135deg, #1a1a2e, #16213e);
  color: white;
  border: none;
  border-radius: 25px;
  cursor: pointer;
  font-size: 1rem;
  font-weight: 500;
  transition: all 0.2s;
}

.preview-btn-big:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(26,26,46,0.3);
}

.preview-btn-big:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.play-icon {
  font-size: 0.9rem;
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

/* ===== 通用板块 ===== */
.section {
  background: white;
  border-radius: 14px;
  padding: 1.5rem;
  margin-bottom: 1rem;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
}

.section-title {
  font-size: 1.1rem;
  color: #1a1a2e;
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.section-icon {
  font-size: 1.2rem;
}

.song-count-badge {
  font-size: 0.75rem;
  font-weight: 500;
  color: #888;
  background: #f0f0f0;
  padding: 2px 8px;
  border-radius: 10px;
  margin-left: auto;
}

/* ===== 平台标签 ===== */
.platform-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.platform-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1.5px solid;
  border-radius: 20px;
  font-size: 0.88rem;
  font-weight: 500;
  background: white;
}

.platform-icon {
  font-size: 1rem;
}

.platform-count {
  font-size: 0.75rem;
  opacity: 0.7;
}

/* ===== 代表作 ===== */
.rep-songs {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}

.rep-song-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: linear-gradient(135deg, #fff9e6, #fff3cc);
  border-radius: 10px;
  border: 1px solid #ffe082;
}

.rep-rank {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ffc107;
  color: white;
  border-radius: 50%;
  font-size: 0.75rem;
  font-weight: 700;
  flex-shrink: 0;
}

.rep-title {
  font-size: 0.9rem;
  color: #5d4037;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ===== 歌曲列表 ===== */
.song-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.song-item {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 0.7rem 1rem;
  border-radius: 8px;
  transition: background 0.2s;
}

.song-item:hover {
  background: #f8f9fa;
}

.song-idx {
  width: 26px;
  color: #bbb;
  font-size: 0.82rem;
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
  line-height: 1.4;
}

.song-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 3px;
}

.platform-tag {
  font-size: 0.7rem;
  padding: 1px 7px;
  border-radius: 8px;
  font-weight: 500;
}

.duration {
  font-size: 0.72rem;
  color: #aaa;
}

.song-link {
  font-size: 0.9rem;
  text-decoration: none;
  color: #ccc;
  padding: 4px 6px;
  border-radius: 6px;
  transition: all 0.2s;
  flex-shrink: 0;
}

.song-link:hover {
  background: #e8eaf6;
  color: #1a1a2e;
}

/* ===== 外部链接 ===== */
.ext-links {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 10px;
}

.ext-link-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #f8f9fa;
  border-radius: 10px;
  text-decoration: none;
  color: #333;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.ext-link-card:hover {
  background: #e8eaf6;
  border-color: #c5cae9;
  transform: translateY(-1px);
  box-shadow: 0 3px 8px rgba(0,0,0,0.08);
}

.ext-icon {
  font-size: 1.2rem;
}

.ext-label {
  font-size: 0.88rem;
  font-weight: 500;
  flex: 1;
}

.ext-arrow {
  color: #bbb;
  font-size: 0.9rem;
}

/* ===== 响应式 ===== */
@media (max-width: 600px) {
  .detail-page {
    padding: 1rem;
  }

  .hero {
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 1.2rem;
  }

  .stats-row {
    justify-content: center;
  }

  .singer-name {
    font-size: 1.6rem;
  }

  .rep-songs {
    grid-template-columns: 1fr;
  }

  .ext-links {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
