<template>
  <div class="home">
    <header class="header">
      <h1>WhoVoice</h1>
      <p class="subtitle">上传你的声音，找到与你声线最相似的明星</p>
    </header>

    <!-- 使用说明 -->
    <div class="guide">
      <p><strong>🎤 如何使用</strong></p>
      <p>1. 点击录音按钮录制一段声音，或上传一个音频文件（WAV / MP3）</p>
      <p>2. 系统自动提取声纹特征，与明星库进行比对</p>
      <p>3. 查看匹配结果和相似度分数</p>
      <details>
        <summary>📖 相似度怎么看？</summary>
        <p class="guide-detail">
          相似度表示你的声纹与明星声纹的匹配程度。声纹库目前已注册 <strong>{{ celebCount }} 位明星</strong>，特征来自<strong>唱歌</strong>音频，所以说话声音很难匹配到。想测试效果，建议上传明星的歌曲片段。
          点击页脚「已注册明星」可查看完整列表。
        </p>
      </details>
    </div>

    <main class="main">
      <AudioRecorder @audio-ready="handleAudioReady" />

      <!-- 加载状态 / 排队状态 -->
      <div v-if="voiceStore.isMatching" class="loading">
        <!-- 有排队信息时显示排队进度 -->
        <template v-if="voiceStore.isQueued && voiceStore.queueInfo">
          <div class="queue-box">
            <div class="queue-icon">
              <span v-if="voiceStore.queueInfo.status === 'processing'" class="processing-anim">🧠</span>
              <span v-else-if="voiceStore.queueInfo.position <= 1" class="processing-anim">🎵</span>
              <span v-else class="queue-number">{{ voiceStore.queueInfo.position }}</span>
            </div>
            <p class="queue-title">
              <template v-if="voiceStore.queueInfo.status === 'processing'">
                正在匹配声纹...
              </template>
              <template v-else>
                排队中，您前面还有 <strong>{{ voiceStore.queueInfo.position - 1 }}</strong> 位
              </template>
            </p>
            <p class="queue-sub">
              <template v-if="voiceStore.queueInfo.estimatedWait">
                预计等待约 <strong>{{ Math.ceil(voiceStore.queueInfo.estimatedWait) }}</strong> 秒
              </template>
              <template v-else>
                即将开始匹配...
              </template>
            </p>
            <div class="queue-bar">
              <div
                class="queue-bar-fill"
                :style="{ width: voiceStore.queueInfo.status === 'processing' ? '80%' : Math.max(10, 100 / (voiceStore.queueInfo.position + 1)) + '%' }"
              ></div>
            </div>
          </div>
        </template>
        <!-- 无排队信息时显示默认加载 -->
        <template v-else>
          <div class="spinner"></div>
          <p>正在上传音频...</p>
        </template>
      </div>

      <!-- 匹配结果 -->
      <ResultCard
        v-if="voiceStore.matchResults.length && !voiceStore.isMatching"
        :results="voiceStore.matchResults"
        :poster-data="voiceStore.posterData"
        :total-celebrities="voiceStore.totalCelebrities"
        :task-id="voiceStore.currentTaskId"
        @error="handlePreviewError"
        @leaderboard-submit="handleLeaderboardSubmit"
      />

      <!-- 错误提示 -->
      <div v-if="errorMsg" class="error-msg">
        <p>❌ {{ errorMsg }}</p>
      </div>
    </main>

    <!-- 排行榜提交确认弹窗 -->
    <LeaderboardConfirmModal
      :visible="showLeaderboardModal"
      :celebrity-name="leaderboardData.name"
      :score="leaderboardData.score"
      :submitting="voiceStore.isSubmitting"
      @close="showLeaderboardModal = false"
      @confirm="handleLeaderboardConfirm"
    />

    <!-- 排行榜提交结果提示 -->
    <div v-if="voiceStore.submitResult" class="submit-result">
      <div class="result-card">
        <p class="result-icon">🎉</p>
        <p class="result-title">上榜成功！</p>
        <p>
          你在 <strong>{{ voiceStore.submitResult.celebrity_name }}</strong> 的
          排行榜中排名 <strong>#{{ voiceStore.submitResult.rank }}</strong>
          （共 {{ voiceStore.submitResult.total }} 人）
        </p>
        <div class="result-actions">
          <button class="btn-view" @click="goToLeaderboard(voiceStore.submitResult.celebrity_name)">
            📊 查看完整排行榜
          </button>
          <button class="btn-close" @click="voiceStore.submitResult = null">
            关闭
          </button>
        </div>
      </div>
    </div>

    <footer class="footer">
      <div class="footer-links">
        <a :href="visualizerUrl" class="footer-link" target="_blank">
          🔬 FAISS 可视化
        </a>
        <span class="footer-sep">|</span>
        <a :href="scatterUrl" class="footer-link" target="_blank">
          📊 声纹散点图
        </a>
        <span class="footer-sep">|</span>
        <p class="celeb-toggle" @click="showCelebList = !showCelebList">
          已注册明星: {{ celebCount }} 位 <span class="toggle-icon">{{ showCelebList ? '▲' : '▼' }}</span>
        </p>
        <span class="footer-sep">|</span>
        <router-link to="/leaderboard" class="footer-link">🏆 排行榜</router-link>
      </div>
      <div class="footer-info">
        <div class="index-selector">
          <span class="index-label">声纹库:</span>
          <button
            :class="['index-btn', { active: voiceStore.indexType === 'raw' }]"
            @click="voiceStore.switchIndex('raw')"
          >🎵 带伴奏</button>
          <button
            :class="['index-btn', { active: voiceStore.indexType === 'clean' }]"
            @click="voiceStore.switchIndex('clean')"
          >🎤 纯净人声</button>
        </div>
        <div class="footer-meta">
          <span class="version"  @click="showVersionInfo = !showVersionInfo" style="cursor:pointer">版本: v0.0.4</span>
          <span class="footer-sep"> | </span>
          <span>作者: ljx</span>
          <span class="footer-sep"> | </span>
          <span >邮箱: 1736728480@qq.com</span>
        </div>
      </div>
      <!-- 版本信息弹窗 -->
      <div v-if="showVersionInfo" class="version-popup" @click="showVersionInfo = false">
        <div class="version-popup-content" @click.stop>
          <button class="popup-close" @click="showVersionInfo = false">&times;</button>
          <h3>WhoVoice v0.0.4</h3>
          <p class="version-date">发布日期: 2026-06-23</p>
          <hr>
          <div class="version-log">
            <p><strong>本次更新</strong></p>
            <ul>
              <li>🏆 新增声纹挑战排行榜（明星榜 + 人气总榜）</li>
              <li>🎤 匹配后可上传音频参与明星挑战排行</li>
              <li>📊 全新排行榜页面，双 Tab 切换浏览</li>
              <li>🔐 匿名昵称保护隐私，低分门槛防刷榜</li>
            </ul>
          </div>
        </div>
      </div>
      <div v-if="showCelebList" class="celeb-list">
        <div
          v-for="item in celebList"
          :key="item.name"
          class="celeb-card"
          @click="goToSinger(item.name)"
        >
          <div
            class="celeb-avatar"
            :style="{ background: item.avatar_color || '#1a1a2e' }"
          >
            <span class="celeb-initial">{{ item.initial || item.name?.charAt(0) || '?' }}</span>
          </div>
          <span class="celeb-name">{{ item.name }}</span>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import AudioRecorder from "../components/AudioRecorder.vue";
import ResultCard from "../components/ResultCard.vue";
import LeaderboardConfirmModal from "../components/LeaderboardConfirmModal.vue";
import { useVoiceStore } from "../stores/voiceStore";
import api from "../api";

const voiceStore = useVoiceStore();
const router = useRouter();
const errorMsg = ref("");
const celebCount = ref(0);
const celebList = ref([]);
const showCelebList = ref(false);
const showVersionInfo = ref(false);
const visualizerUrl = ref("/api/voice-matching/faiss-visualizer/");
const scatterUrl = ref("/api/voice-matching/faiss-scatter/");

// ── 排行榜状态 ──
const showLeaderboardModal = ref(false);
const leaderboardData = ref({ name: "", score: 0, taskId: "" });
const lastAudioBlob = ref(null); // 保存最近一次录音，用于排行榜上传

onMounted(async () => {
  try {
    const res = await api.get("/celebrities/list/");
    celebCount.value = res.data.count || 0;
    celebList.value = (res.data.celebrities || []).filter(n => n.name !== "test");
  } catch {
    celebCount.value = 0;
  }
});

function goToSinger(name) {
  router.push(`/celebrities/${encodeURIComponent(name)}`);
}

function goToLeaderboard(name) {
  voiceStore.submitResult = null;
  router.push(`/leaderboard/${encodeURIComponent(name)}`);
}

function handleLeaderboardSubmit(data) {
  leaderboardData.value = {
    name: data.name,
    score: data.score,
    taskId: data.taskId || "",
  };
  showLeaderboardModal.value = true;
}

async function handleLeaderboardConfirm(nickname) {
  showLeaderboardModal.value = false;
  if (!lastAudioBlob.value) {
    errorMsg.value = "音频数据丢失，请重新录音后再试";
    return;
  }
  try {
    await voiceStore.submitToLeaderboard(
      leaderboardData.value.name,
      leaderboardData.value.score,
      lastAudioBlob.value,
      nickname,
      leaderboardData.value.taskId,
    );
  } catch (err) {
    errorMsg.value =
      err.response?.data?.error || "排行榜提交失败，请稍后重试";
    console.error("排行榜提交错误:", err);
  }
}

async function handleAudioReady(audioBlob, selectedLyric) {
  errorMsg.value = "";
  voiceStore.submitResult = null; // 清除上次排行榜结果
  lastAudioBlob.value = audioBlob; // 保存音频用于后续排行榜上传
  try {
    await voiceStore.uploadAndMatch(audioBlob, selectedLyric);
    if (voiceStore.matchResults.length === 0) {
      errorMsg.value = "未匹配到结果，请尝试其他音频";
    }
  } catch (err) {
    errorMsg.value =
      err.response?.data?.error || "声纹匹配失败，请检查后端服务";
    console.error("匹配错误:", err);
  }
}

function handlePreviewError(msg) {
  errorMsg.value = msg;
  // 3 秒后自动清除错误提示
  setTimeout(() => {
    if (errorMsg.value === msg) {
      errorMsg.value = "";
    }
  }, 5000);
}
</script>

<style scoped>
.home {
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  text-align: center;
  margin-bottom: 1.5rem;
}

.header h1 {
  font-size: 2.5rem;
  color: #1a1a2e;
  background: linear-gradient(135deg, #1a1a2e, #e94560);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  color: #666;
  margin-top: 0.5rem;
}

.guide {
  margin-bottom: 1.5rem;
  padding: 1rem 1.2rem;
  background: #e8f5e9;
  border-radius: 10px;
  border-left: 4px solid #4caf50;
  font-size: 0.9rem;
  line-height: 1.8;
  color: #333;
}

.guide details {
  margin-top: 0.3rem;
}

.guide summary {
  cursor: pointer;
  color: #1565c0;
  font-weight: 500;
}

.guide-detail {
  margin-top: 0.3rem;
  padding: 0.5rem 0.8rem;
  background: #fff;
  border-radius: 6px;
  color: #666;
  font-size: 0.85rem;
}

.main {
  flex: 1;
}

.loading {
  text-align: center;
  padding: 2rem;
  color: #666;
}

.queue-box {
  max-width: 340px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
  background: white;
  border-radius: 16px;
  box-shadow: 0 2px 16px rgba(0,0,0,0.08);
}

.queue-icon {
  font-size: 2.5rem;
  margin-bottom: 0.8rem;
  display: flex;
  justify-content: center;
}

.queue-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  background: linear-gradient(135deg, #1a1a2e, #16213e);
  color: white;
  font-size: 1.5rem;
  font-weight: bold;
  border-radius: 50%;
}

.processing-anim {
  font-size: 2.5rem;
  animation: pulse 1.5s infinite;
}

.queue-title {
  font-size: 1rem;
  font-weight: 600;
  color: #1a1a2e;
  margin-bottom: 0.3rem;
}

.queue-title strong {
  color: #e94560;
}

.queue-sub {
  font-size: 0.85rem;
  color: #888;
  margin-bottom: 1rem;
}

.queue-sub strong {
  color: #1a1a2e;
}

.queue-bar {
  height: 6px;
  background: #eee;
  border-radius: 3px;
  overflow: hidden;
}

.queue-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #1a1a2e, #e94560);
  border-radius: 3px;
  transition: width 1s ease;
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
  to {
    transform: rotate(360deg);
  }
}

.error-msg {
  margin-top: 1rem;
  padding: 1rem;
  background: #fff0f0;
  border: 1px solid #ffcdd2;
  border-radius: 8px;
  text-align: center;
  color: #d32f2f;
}

.footer {
  text-align: center;
  padding: 1rem;
  color: #999;
  font-size: 0.9rem;
}

.footer-links {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}

.footer-link {
  color: #1565c0;
  text-decoration: none;
  cursor: pointer;
  transition: color 0.2s;
}

.footer-link:hover {
  color: #e94560;
  text-decoration: underline;
}

.footer-sep {
  color: #ddd;
}

.celeb-toggle {
  cursor: pointer;
  user-select: none;
  transition: color 0.2s;
}

.celeb-toggle:hover {
  color: #e94560;
}

.footer-info {
  margin-top: 0.6rem;
}

.footer-info .version {
  color: #999;
}

.footer-meta {
  margin-top: 0.3rem;
  font-size: 0.8rem;
  color: #bbb;
}

/* 版本信息弹窗 */
.version-popup {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.version-popup-content {
  background: white;
  border-radius: 12px;
  padding: 2rem;
  max-width: 480px;
  width: 90%;
  max-height: 70vh;
  overflow-y: auto;
  position: relative;
  box-shadow: 0 8px 30px rgba(0,0,0,0.2);
}

.version-popup-content h3 {
  margin: 0 0 0.3rem;
  color: #1a1a2e;
}

.version-date {
  color: #999;
  font-size: 0.85rem;
  margin: 0 0 0.8rem;
}

.version-popup-content hr {
  border: none;
  border-top: 1px solid #eee;
  margin: 0.8rem 0;
}

.version-log {
  font-size: 0.85rem;
  line-height: 1.7;
  color: #555;
}

.version-log ul {
  padding-left: 1.2rem;
  margin: 0.3rem 0;
}

.version-log li {
  margin-bottom: 0.3rem;
}

.popup-close {
  position: absolute;
  top: 8px; right: 12px;
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #999;
  line-height: 1;
}

.popup-close:hover {
  color: #333;
}

/* 索引选择器 */
.index-selector {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 0.5rem;
}

.index-label {
  font-size: 0.8rem;
  color: #999;
}

.index-btn {
  padding: 3px 12px;
  font-size: 0.78rem;
  border: 1px solid #ddd;
  border-radius: 14px;
  background: #f5f5f5;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}

.index-btn:hover {
  border-color: #1565c0;
  color: #1565c0;
}

.index-btn.active {
  background: #1565c0;
  color: #fff;
  border-color: #1565c0;
}

.toggle-icon {
  font-size: 0.7rem;
  margin-left: 4px;
}

.celeb-list {
  margin-top: 0.8rem;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  max-height: 400px;
  overflow-y: auto;
  padding: 0.8rem;
  background: #fafafa;
  border-radius: 12px;
  border: 1px solid #eee;
}

.celeb-card {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px 6px 6px;
  background: white;
  border: 1px solid #e8e8e8;
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.celeb-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 3px 10px rgba(0,0,0,0.1);
  border-color: #c5cae9;
}

.celeb-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.celeb-initial {
  color: white;
  font-size: 0.75rem;
  font-weight: bold;
  line-height: 1;
}

.celeb-name {
  font-size: 0.8rem;
  color: #333;
  white-space: nowrap;
}

/* 排行榜提交结果 */
.submit-result {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.submit-result .result-card {
  background: white;
  border-radius: 16px;
  padding: 28px;
  max-width: 380px;
  width: 90%;
  text-align: center;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.submit-result .result-icon {
  font-size: 3rem;
  margin: 0 0 0.5rem;
}

.submit-result .result-title {
  font-size: 1.3rem;
  font-weight: bold;
  color: #1a1a2e;
  margin-bottom: 0.8rem;
}

.submit-result p {
  font-size: 0.95rem;
  color: #666;
  line-height: 1.6;
  margin-bottom: 1.2rem;
}

.submit-result strong {
  color: #1a1a2e;
}

.submit-result .result-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
  flex-wrap: wrap;
}

.btn-view {
  padding: 10px 22px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, #1a1a2e, #2d1b69);
  color: white;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-view:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(26, 26, 46, 0.3);
}

.btn-close {
  padding: 10px 22px;
  border-radius: 10px;
  border: 1px solid #ddd;
  background: #f5f5f5;
  color: #666;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-close:hover {
  background: #e0e0e0;
}
</style>
