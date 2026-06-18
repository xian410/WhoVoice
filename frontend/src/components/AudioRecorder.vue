<template>
  <div class="recorder">
    <!-- 歌词模板选择 -->
    <div class="lyrics-section">
      <p class="lyrics-title">想唱哪首歌？选一句开唱</p>
      <!-- 歌手筛选 -->
      <div class="singer-filter">
        <button
          v-for="s in singerList"
          :key="s"
          class="singer-tag"
          :class="{ active: selectedSinger === s }"
          @click="filterBySinger(s)"
        >{{ s }}</button>
        <button
          v-if="selectedSinger"
          class="singer-tag clear"
          @click="selectedSinger = ''"
        >清除</button>
      </div>
      <!-- 歌词卡片列表 -->
      <div class="lyrics-grid">
        <div
          v-for="item in filteredLyrics"
          :key="item.id"
          class="lyric-card"
          :class="{ selected: selectedLyric?.id === item.id }"
          @click="selectLyric(item)"
        >
          <span class="lyric-text">"{{ item.line }}"</span>
          <span class="lyric-meta">— {{ item.singer }} · {{ item.song }}</span>
        </div>
      </div>
    </div>
    <!-- 已选歌词提示 -->
    <div v-if="selectedLyric" class="selected-hint">
      <p>试试唱这句：<strong>「{{ selectedLyric.line }}」</strong></p>
      <p class="hint-src">— {{ selectedLyric.singer }}《{{ selectedLyric.song }}》</p>
    </div>
    <!-- 录音按钮 -->
    <button
      class="record-btn"
      :class="{ recording: isRecording }"
      @click="toggleRecording"
    >
      {{ isRecording ? "停止录音" : selectedLyric ? "唱这句吧！" : "开始录音" }}
    </button>
    <p class="divider-text">或</p>
    <!-- 文件上传 -->
    <label class="upload-label">
      上传音频文件
      <input type="file" accept="audio/*" class="file-input" @change="handleFileUpload" />
    </label>
    <!-- 波形可视化 -->
    <WaveformVisualizer v-if="isRecording" :analyser-node="analyserNode" />
    <!-- 录音完成后的操作 -->
    <div v-if="recordedBlob && !isRecording" class="actions">
      <audio :src="audioUrl" controls />
      <div class="action-buttons">
        <button class="upload-btn" @click="uploadAudio">声纹匹配</button>
        <button class="reset-btn" @click="resetRecording">重新选择</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import WaveformVisualizer from "./WaveformVisualizer.vue";
import api from "../api";

const emit = defineEmits(["audio-ready"]);

const isRecording = ref(false);
const recordedBlob = ref(null);
const audioUrl = ref("");
const analyserNode = ref(null);

const allLyrics = ref([]);
const selectedLyric = ref(null);
const selectedSinger = ref("");

const singerList = computed(() => {
  const singers = [...new Set(allLyrics.value.map((l) => l.singer))];
  return singers.sort();
});

const filteredLyrics = computed(() => {
  if (!selectedSinger.value) return allLyrics.value;
  return allLyrics.value.filter((l) => l.singer === selectedSinger.value);
});

onMounted(async () => {
  try {
    const res = await api.get("/celebrities/lyrics-templates/");
    allLyrics.value = res.data.lyrics || [];
  } catch {
    console.warn("歌词模板加载失败");
  }
});

function filterBySinger(singer) {
  selectedSinger.value = selectedSinger.value === singer ? "" : singer;
}

function selectLyric(item) {
  selectedLyric.value = selectedLyric.value?.id === item.id ? null : item;
}

let mediaRecorder = null;
let audioContext = null;
let stream = null;
let chunks = [];

async function toggleRecording() {
  if (isRecording.value) {
    stopRecording();
  } else {
    await startRecording();
  }
}

async function startRecording() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    chunks = [];
    audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    analyserNode.value = analyser;
    mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
    mediaRecorder.onstop = () => {
      const blob = new Blob(chunks, { type: "audio/webm" });
      recordedBlob.value = blob;
      audioUrl.value = URL.createObjectURL(blob);
      stream.getTracks().forEach((track) => track.stop());
      audioContext.close();
      analyserNode.value = null;
    };
    mediaRecorder.start();
    isRecording.value = true;
  } catch (err) {
    console.error("录音启动失败:", err);
    alert("请允许麦克风权限");
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
    isRecording.value = false;
  }
}

function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;
  recordedBlob.value = file;
  audioUrl.value = URL.createObjectURL(file);
}

function uploadAudio() {
  if (recordedBlob.value) {
    emit("audio-ready", recordedBlob.value, selectedLyric.value);
  }
}

function resetRecording() {
  recordedBlob.value = null;
  audioUrl.value = "";
  chunks = [];
}
</script>

<style scoped>
.recorder { text-align: center; padding: 2rem; background: white; border-radius: 16px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
.lyrics-section { margin-bottom: 1.5rem; text-align: left; }
.lyrics-title { font-size: 1rem; font-weight: 600; color: #1a1a2e; margin-bottom: 0.8rem; }
.singer-filter { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 0.8rem; }
.singer-tag { padding: 4px 12px; border: 1px solid #ddd; border-radius: 14px; background: #f8f8f8; color: #555; font-size: 0.8rem; cursor: pointer; transition: all 0.2s; }
.singer-tag:hover { border-color: #1a1a2e; color: #1a1a2e; }
.singer-tag.active { background: #1a1a2e; color: white; border-color: #1a1a2e; }
.singer-tag.clear { border-color: #e94560; color: #e94560; }
.lyrics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; max-height: 300px; overflow-y: auto; padding: 4px 0; }
.lyric-card { padding: 10px 12px; border: 1px solid #eee; border-radius: 10px; cursor: pointer; transition: all 0.2s; display: flex; flex-direction: column; gap: 4px; }
.lyric-card:hover { border-color: #c5cae9; background: #f8f9ff; transform: translateY(-1px); }
.lyric-card.selected { border-color: #1a1a2e; background: #e8eaf6; box-shadow: 0 2px 8px rgba(26,26,46,0.15); }
.lyric-text { font-size: 0.85rem; color: #333; line-height: 1.4; }
.lyric-meta { font-size: 0.7rem; color: #999; }
.selected-hint { margin-bottom: 1rem; padding: 10px 14px; background: #fff8e1; border-left: 3px solid #ffa000; border-radius: 8px; text-align: left; font-size: 0.9rem; color: #333; }
.selected-hint strong { color: #e94560; }
.hint-src { margin-top: 4px; font-size: 0.8rem; color: #888; }
.record-btn { padding: 1rem 2rem; font-size: 1.2rem; border: none; border-radius: 50px; background: #1a1a2e; color: white; cursor: pointer; transition: all 0.3s; }
.record-btn:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(26,26,46,0.3); }
.record-btn.recording { background: #e94560; animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100% { box-shadow: 0 0 0 0 rgba(233,69,96,0.4); } 50% { box-shadow: 0 0 0 15px rgba(233,69,96,0); } }
.divider-text { margin: 1rem 0; color: #999; font-size: 0.9rem; }
.upload-label { display: inline-block; padding: 0.8rem 1.5rem; background: #f5f5f5; border: 2px dashed #ccc; border-radius: 12px; color: #666; cursor: pointer; transition: all 0.3s; }
.upload-label:hover { border-color: #1a1a2e; color: #1a1a2e; background: #f0f0f5; }
.file-input { display: none; }
.actions { margin-top: 1.5rem; }
.actions audio { width: 100%; max-width: 400px; margin-bottom: 1rem; }
.action-buttons { display: flex; gap: 1rem; justify-content: center; }
.upload-btn,.reset-btn { padding: 0.7rem 1.5rem; border: none; border-radius: 25px; cursor: pointer; font-size: 1rem; transition: all 0.2s; }
.upload-btn { background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; }
.upload-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(26,26,46,0.3); }
.reset-btn { background: #eee; color: #666; }
.reset-btn:hover { background: #ddd; }
</style>
