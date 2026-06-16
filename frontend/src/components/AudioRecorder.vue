<template>
  <div class="recorder">
    <!-- 录音按钮 -->
    <button
      class="record-btn"
      :class="{ recording: isRecording }"
      @click="toggleRecording"
    >
      {{ isRecording ? "⏹ 停止录音" : "🎤 开始录音" }}
    </button>

    <p class="divider-text">或</p>

    <!-- 文件上传 -->
    <label class="upload-label">
      📁 上传音频文件
      <input
        type="file"
        accept="audio/*"
        class="file-input"
        @change="handleFileUpload"
      />
    </label>

    <!-- 波形可视化 -->
    <WaveformVisualizer v-if="isRecording" :analyser-node="analyserNode" />

    <!-- 录音完成后的操作 -->
    <div v-if="recordedBlob && !isRecording" class="actions">
      <audio :src="audioUrl" controls />
      <div class="action-buttons">
        <button class="upload-btn" @click="uploadAudio">🔍 声纹匹配</button>
        <button class="reset-btn" @click="resetRecording">重新选择</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import WaveformVisualizer from "./WaveformVisualizer.vue";

const emit = defineEmits(["audio-ready"]);

const isRecording = ref(false);
const recordedBlob = ref(null);
const audioUrl = ref("");
const analyserNode = ref(null);

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
    emit("audio-ready", recordedBlob.value);
  }
}

function resetRecording() {
  recordedBlob.value = null;
  audioUrl.value = "";
  chunks = [];
}
</script>

<style scoped>
.recorder {
  text-align: center;
  padding: 2rem;
  background: white;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.record-btn {
  padding: 1rem 2rem;
  font-size: 1.2rem;
  border: none;
  border-radius: 50px;
  background: #1a1a2e;
  color: white;
  cursor: pointer;
  transition: all 0.3s;
}

.record-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(26, 26, 46, 0.3);
}

.record-btn.recording {
  background: #e94560;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(233, 69, 96, 0.4);
  }
  50% {
    box-shadow: 0 0 0 15px rgba(233, 69, 96, 0);
  }
}

.divider-text {
  margin: 1rem 0;
  color: #999;
  font-size: 0.9rem;
}

.upload-label {
  display: inline-block;
  padding: 0.8rem 1.5rem;
  background: #f5f5f5;
  border: 2px dashed #ccc;
  border-radius: 12px;
  color: #666;
  cursor: pointer;
  transition: all 0.3s;
}

.upload-label:hover {
  border-color: #1a1a2e;
  color: #1a1a2e;
  background: #f0f0f5;
}

.file-input {
  display: none;
}

.actions {
  margin-top: 1.5rem;
}

.actions audio {
  width: 100%;
  max-width: 400px;
  margin-bottom: 1rem;
}

.action-buttons {
  display: flex;
  gap: 1rem;
  justify-content: center;
}

.upload-btn,
.reset-btn {
  padding: 0.7rem 1.5rem;
  border: none;
  border-radius: 25px;
  cursor: pointer;
  font-size: 1rem;
  transition: all 0.2s;
}

.upload-btn {
  background: linear-gradient(135deg, #1a1a2e, #16213e);
  color: white;
}

.upload-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(26, 26, 46, 0.3);
}

.reset-btn {
  background: #eee;
  color: #666;
}

.reset-btn:hover {
  background: #ddd;
}
</style>
