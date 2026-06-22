<template>
  <div v-if="visible" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-card">
      <div class="modal-header">
        <h3>🏆 挑战排行榜</h3>
        <button class="close-btn" @click="$emit('close')">✕</button>
      </div>
      <div class="modal-body">
        <p class="confirm-text">
          将你的声音加入 <strong>{{ celebrityName }}</strong> 的挑战排行榜？
        </p>
        <div class="score-badge">
          <span class="score-label">你的相似度</span>
          <span class="score-value">{{ (score * 100).toFixed(1) }}%</span>
        </div>
        <div class="nickname-input">
          <label>昵称（可选，默认匿名）</label>
          <input
            v-model="nickname"
            type="text"
            maxlength="20"
            placeholder="声纹探险家#1234"
            @keyup.enter="handleSubmit"
          />
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn-cancel" @click="$emit('close')" :disabled="submitting">
          取消
        </button>
        <button class="btn-confirm" @click="handleSubmit" :disabled="submitting">
          <span v-if="submitting" class="spinner"></span>
          <span v-else>🚀 确认上传</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";

const props = defineProps({
  visible: { type: Boolean, default: false },
  celebrityName: { type: String, default: "" },
  score: { type: Number, default: 0 },
  submitting: { type: Boolean, default: false },
});

const emit = defineEmits(["close", "confirm"]);

const nickname = ref("");

function handleSubmit() {
  emit("confirm", nickname.value.trim());
  nickname.value = "";
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
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

.modal-card {
  background: #fff;
  border-radius: 16px;
  padding: 24px;
  max-width: 400px;
  width: 90%;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.2rem;
  color: #1a1a2e;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  color: #999;
  padding: 4px 8px;
  border-radius: 4px;
}

.close-btn:hover {
  background: #f5f5f5;
  color: #333;
}

.modal-body {
  margin-bottom: 20px;
}

.confirm-text {
  font-size: 0.95rem;
  color: #555;
  margin-bottom: 16px;
  line-height: 1.5;
}

.score-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 12px;
  background: linear-gradient(135deg, #fff8e1, #fff3e0);
  border-radius: 10px;
  margin-bottom: 16px;
}

.score-label {
  font-size: 0.9rem;
  color: #666;
}

.score-value {
  font-size: 1.4rem;
  font-weight: bold;
  color: #e65100;
}

.nickname-input label {
  display: block;
  font-size: 0.85rem;
  color: #888;
  margin-bottom: 6px;
}

.nickname-input input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #ddd;
  border-radius: 10px;
  font-size: 0.95rem;
  box-sizing: border-box;
  transition: border-color 0.2s;
}

.nickname-input input:focus {
  outline: none;
  border-color: #f9a825;
}

.modal-footer {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.btn-cancel,
.btn-confirm {
  padding: 10px 24px;
  border-radius: 10px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-cancel {
  background: #f5f5f5;
  color: #666;
}

.btn-cancel:hover:not(:disabled) {
  background: #e0e0e0;
}

.btn-confirm {
  background: linear-gradient(135deg, #f9a825, #ff8f00);
  color: #fff;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.btn-confirm:hover:not(:disabled) {
  background: linear-gradient(135deg, #ff8f00, #f57f17);
  transform: scale(1.03);
}

.btn-confirm:disabled,
.btn-cancel:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.5);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
