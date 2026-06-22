<template>
  <div class="leaderboard-page">
    <header class="lb-header">
      <button class="back-btn" @click="$router.push('/')">← 返回首页</button>
      <h1>🏆 声纹挑战排行榜</h1>
    </header>

    <!-- Tab 切换 -->
    <div class="tab-bar">
      <button
        :class="['tab-btn', { active: activeTab === 'celebrity' }]"
        @click="activeTab = 'celebrity'"
      >
        🎤 明星挑战榜
      </button>
      <button
        :class="['tab-btn', { active: activeTab === 'global' }]"
        @click="activeTab = 'global'"
      >
        🔥 人气总榜
      </button>
    </div>

    <!-- 明星挑战榜 -->
    <div v-if="activeTab === 'celebrity'" class="tab-content">
      <div class="search-box">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="🔍 搜索明星名称..."
          @input="filterCelebList"
        />
      </div>

      <!-- 明星选择下拉 -->
      <div v-if="!selectedCelebrity" class="celeb-grid">
        <div
          v-for="item in filteredCelebs"
          :key="item"
          class="celeb-chip"
          @click="selectCelebrity(item)"
        >
          {{ item }}
        </div>
        <p v-if="filteredCelebs.length === 0" class="empty-hint">
          未找到匹配的明星
        </p>
      </div>

      <!-- 排行榜展示 -->
      <div v-if="selectedCelebrity" class="ranking-section">
        <div class="ranking-header">
          <button class="back-btn-small" @click="selectedCelebrity = ''">
            ← 换明星
          </button>
          <h2>{{ selectedCelebrity }}</h2>
          <span class="entry-count">
            {{ leaderboardEntries.total_entries || 0 }} 人参与
          </span>
        </div>

        <div v-if="loading" class="loading-state">
          <div class="spinner"></div>
          <p>加载中...</p>
        </div>

        <div v-else-if="leaderboardEntries.entries?.length" class="ranking-list">
          <div
            v-for="(entry, index) in leaderboardEntries.entries"
            :key="index"
            class="ranking-item"
            :class="{ top3: entry.rank <= 3 }"
          >
            <div class="rank-col">
              <span v-if="entry.rank === 1" class="medal">🥇</span>
              <span v-else-if="entry.rank === 2" class="medal">🥈</span>
              <span v-else-if="entry.rank === 3" class="medal">🥉</span>
              <span v-else class="rank-num">#{{ entry.rank }}</span>
            </div>
            <div class="user-col">
              <span class="nickname">{{ entry.nickname }}</span>
              <span class="time">{{ formatTime(entry.created_at) }}</span>
            </div>
            <div class="score-col">
              <div class="score-bar">
                <div
                  class="score-fill"
                  :style="{ width: Math.min((entry.score + 0.5) * 66, 100) + '%' }"
                ></div>
              </div>
              <span class="score-text">{{ (entry.score * 100).toFixed(1) }}%</span>
            </div>
          </div>
        </div>

        <div v-else class="empty-state">
          <p>🎵 暂无挑战记录</p>
          <p class="empty-sub">成为第一位挑战者吧！</p>
        </div>
      </div>
    </div>

    <!-- 人气总榜 -->
    <div v-if="activeTab === 'global'" class="tab-content">
      <div v-if="loadingGlobal" class="loading-state">
        <div class="spinner"></div>
        <p>加载中...</p>
      </div>

      <div v-else-if="leaderboardGlobal.length" class="global-list">
        <div
          v-for="(item, index) in leaderboardGlobal"
          :key="item.celebrity_name"
          class="global-item"
          @click="selectCelebrity(item.celebrity_name); activeTab = 'celebrity'"
        >
          <div class="global-rank">#{{ index + 1 }}</div>
          <div class="global-info">
            <span class="global-name">{{ item.celebrity_name }}</span>
            <span class="global-count">{{ item.entry_count }} 人挑战</span>
          </div>
          <div class="global-best">
            <span class="best-label">最高</span>
            <span class="best-score">{{ (item.best_score * 100).toFixed(1) }}%</span>
          </div>
        </div>
      </div>

      <div v-else class="empty-state">
        <p>🔥 暂无排行数据</p>
        <p class="empty-sub">快去参与声纹匹配，挑战排行榜吧！</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from "vue";
import { useRoute } from "vue-router";
import { useVoiceStore } from "../stores/voiceStore";

const route = useRoute();
const voiceStore = useVoiceStore();

const activeTab = ref("celebrity");
const searchQuery = ref("");
const selectedCelebrity = ref("");
const celebList = ref([]);
const loading = ref(false);
const loadingGlobal = ref(false);

// 从路由参数读取明星名
onMounted(async () => {
  const nameFromRoute = route.params.name;
  if (nameFromRoute) {
    selectedCelebrity.value = decodeURIComponent(nameFromRoute);
    await loadLeaderboard();
  }

  // 加载明星列表用于搜索
  try {
    const { default: api } = await import("../api");
    const res = await api.get("/celebrities/list/");
    celebList.value = (res.data.celebrities || [])
      .map((c) => c.name)
      .filter((n) => n !== "test");
  } catch {
    celebList.value = [];
  }
});

const filteredCelebs = computed(() => {
  if (!searchQuery.value) return celebList.value.slice(0, 50);
  const q = searchQuery.value.toLowerCase();
  return celebList.value
    .filter((n) => n.toLowerCase().includes(q))
    .slice(0, 50);
});

const leaderboardEntries = computed(() => {
  return voiceStore.leaderboardEntries;
});

const leaderboardGlobal = computed(() => {
  return voiceStore.leaderboardGlobal;
});

function filterCelebList() {
  // computed 自动响应
}

async function selectCelebrity(name) {
  selectedCelebrity.value = name;
  searchQuery.value = "";
  await loadLeaderboard();
}

async function loadLeaderboard() {
  if (!selectedCelebrity.value) return;
  loading.value = true;
  try {
    await voiceStore.fetchLeaderboard(selectedCelebrity.value);
  } finally {
    loading.value = false;
  }
}

// 监听 tab 切换到人气总榜时自动加载
watch(activeTab, async (tab) => {
  if (tab === "global" && voiceStore.leaderboardGlobal.length === 0) {
    loadingGlobal.value = true;
    try {
      await voiceStore.fetchGlobalLeaderboard();
    } finally {
      loadingGlobal.value = false;
    }
  }
});

function formatTime(isoStr) {
  if (!isoStr) return "";
  const d = new Date(isoStr);
  const now = new Date();
  const diff = now - d;
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
  return d.toLocaleDateString("zh-CN");
}
</script>

<style scoped>
.leaderboard-page {
  max-width: 700px;
  margin: 0 auto;
  padding: 1.5rem;
  min-height: 100vh;
}

.lb-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 1.5rem;
}

.lb-header h1 {
  margin: 0;
  font-size: 1.6rem;
  color: #1a1a2e;
}

.back-btn {
  padding: 6px 14px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background: #f5f5f5;
  color: #666;
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.2s;
  white-space: nowrap;
}

.back-btn:hover {
  background: #e0e0e0;
}

.tab-bar {
  display: flex;
  gap: 0;
  margin-bottom: 1.5rem;
  background: #f5f5f5;
  border-radius: 12px;
  padding: 4px;
}

.tab-btn {
  flex: 1;
  padding: 10px 16px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: #888;
  font-size: 0.95rem;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn.active {
  background: white;
  color: #1a1a2e;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.search-box input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  font-size: 0.95rem;
  box-sizing: border-box;
  transition: border-color 0.2s;
}

.search-box input:focus {
  outline: none;
  border-color: #f9a825;
}

.celeb-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 1rem;
  max-height: 400px;
  overflow-y: auto;
}

.celeb-chip {
  padding: 8px 18px;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 20px;
  cursor: pointer;
  font-size: 0.9rem;
  color: #333;
  transition: all 0.2s;
}

.celeb-chip:hover {
  background: #fff8e1;
  border-color: #f9a825;
  transform: translateY(-1px);
}

.empty-hint {
  width: 100%;
  text-align: center;
  color: #999;
  padding: 1rem;
}

.back-btn-small {
  padding: 4px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: #f5f5f5;
  color: #666;
  cursor: pointer;
  font-size: 0.8rem;
  transition: all 0.2s;
}

.back-btn-small:hover {
  background: #e0e0e0;
}

.ranking-section {
  margin-top: 1rem;
}

.ranking-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.ranking-header h2 {
  margin: 0;
  font-size: 1.3rem;
  color: #1a1a2e;
}

.entry-count {
  font-size: 0.85rem;
  color: #999;
}

.ranking-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ranking-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  transition: transform 0.2s;
}

.ranking-item.top3 {
  border: 1px solid #ffe082;
  background: linear-gradient(135deg, #fffde7, #fff8e1);
}

.ranking-item:hover {
  transform: translateX(4px);
}

.rank-col {
  min-width: 40px;
  text-align: center;
}

.medal {
  font-size: 1.5rem;
}

.rank-num {
  font-size: 0.95rem;
  font-weight: 600;
  color: #bbb;
}

.user-col {
  flex: 1;
  min-width: 0;
}

.nickname {
  display: block;
  font-size: 0.95rem;
  color: #1a1a2e;
  font-weight: 500;
}

.time {
  display: block;
  font-size: 0.75rem;
  color: #bbb;
  margin-top: 2px;
}

.score-col {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 120px;
}

.score-bar {
  width: 60px;
  height: 6px;
  background: #eee;
  border-radius: 3px;
  overflow: hidden;
}

.score-fill {
  height: 100%;
  background: linear-gradient(90deg, #f9a825, #ff8f00);
  border-radius: 3px;
  transition: width 0.5s ease;
}

.score-text {
  font-size: 0.95rem;
  font-weight: 600;
  color: #e65100;
  min-width: 50px;
  text-align: right;
}

/* 人气总榜 */
.global-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.global-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  cursor: pointer;
  transition: all 0.2s;
}

.global-item:hover {
  transform: translateX(4px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.global-rank {
  font-size: 1.2rem;
  font-weight: bold;
  color: #999;
  min-width: 40px;
}

.global-info {
  flex: 1;
}

.global-name {
  display: block;
  font-size: 1rem;
  font-weight: 600;
  color: #1a1a2e;
}

.global-count {
  display: block;
  font-size: 0.8rem;
  color: #999;
  margin-top: 2px;
}

.global-best {
  text-align: right;
}

.best-label {
  display: block;
  font-size: 0.7rem;
  color: #bbb;
}

.best-score {
  font-size: 1rem;
  font-weight: 600;
  color: #e65100;
}

/* 通用状态 */
.loading-state {
  text-align: center;
  padding: 3rem;
  color: #999;
}

.spinner {
  width: 36px;
  height: 36px;
  margin: 0 auto 1rem;
  border: 3px solid #eee;
  border-top-color: #f9a825;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-state {
  text-align: center;
  padding: 3rem;
  color: #999;
}

.empty-sub {
  font-size: 0.85rem;
  color: #bbb;
  margin-top: 0.3rem;
}
</style>
