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

      <!-- 加载状态 -->
      <div v-if="voiceStore.isMatching" class="loading">
        <div class="spinner"></div>
        <p>正在分析声纹特征...</p>
      </div>

      <!-- 匹配结果 -->
      <ResultCard
        v-if="voiceStore.matchResults.length && !voiceStore.isMatching"
        :results="voiceStore.matchResults"
        :poster-data="voiceStore.posterData"
        @error="handlePreviewError"
      />

      <!-- 错误提示 -->
      <div v-if="errorMsg" class="error-msg">
        <p>❌ {{ errorMsg }}</p>
      </div>
    </main>

    <footer class="footer">
      <p class="celeb-toggle" @click="showCelebList = !showCelebList">
        已注册明星: {{ celebCount }} 位 <span class="toggle-icon">{{ showCelebList ? '▲' : '▼' }}</span>
      </p>
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
import { useVoiceStore } from "../stores/voiceStore";
import api from "../api";

const voiceStore = useVoiceStore();
const router = useRouter();
const errorMsg = ref("");
const celebCount = ref(0);
const celebList = ref([]);
const showCelebList = ref(false);

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

async function handleAudioReady(audioBlob, selectedLyric) {
  errorMsg.value = "";
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

.celeb-toggle {
  cursor: pointer;
  user-select: none;
  transition: color 0.2s;
}

.celeb-toggle:hover {
  color: #e94560;
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
</style>
