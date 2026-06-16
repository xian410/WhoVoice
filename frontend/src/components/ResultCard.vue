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
      >
        <div class="rank">#{{ index + 1 }}</div>
        <div class="avatar">
          <span v-if="!item.avatar" class="avatar-text">
            {{ item.name?.charAt(0) || "?" }}
          </span>
          <img v-else :src="item.avatar" :alt="item.name" />
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
        </div>
      </div>
    </div>

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
defineProps({
  results: {
    type: Array,
    default: () => [],
  },
});

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
  background: linear-gradient(135deg, #1a1a2e, #e94560);
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
</style>
