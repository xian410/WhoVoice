<template>
  <div class="poster-wrapper">
    <div class="poster-actions">
      <button class="save-btn" @click="savePoster">
        <span>💾</span> 保存海报
      </button>
      <button class="copy-btn" @click="copyShareText">
        <span>{{ copied ? '✅' : '📋' }}</span>
        {{ copied ? '已复制' : '复制分享文案' }}
      </button>
    </div>
    <div class="canvas-container" ref="canvasContainer">
      <canvas ref="posterCanvas" width="750" height="1334"></canvas>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from "vue";

const props = defineProps({
  posterData: {
    type: Object,
    required: true,
  },
});

const posterCanvas = ref(null);
const canvasContainer = ref(null);
const copied = ref(false);

onMounted(() => {
  nextTick(() => drawPoster());
});

watch(() => props.posterData, () => {
  nextTick(() => drawPoster());
}, { deep: true });

function drawPoster() {
  const canvas = posterCanvas.value;
  if (!canvas || !props.posterData) return;

  const ctx = canvas.getContext("2d");
  const W = 750;
  const H = 1334;

  // ── 背景渐变 ──
  const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
  bgGrad.addColorStop(0, "#1a1a2e");
  bgGrad.addColorStop(0.5, "#16213e");
  bgGrad.addColorStop(1, "#2d1b69");
  ctx.fillStyle = bgGrad;
  ctx.fillRect(0, 0, W, H);

  // 装饰圆环
  ctx.beginPath();
  ctx.arc(W * 0.85, H * 0.08, 120, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(233, 69, 96, 0.08)";
  ctx.fill();
  ctx.beginPath();
  ctx.arc(W * 0.1, H * 0.92, 90, 0, Math.PI * 2);
  ctx.fillStyle = "rgba(108, 92, 231, 0.1)";
  ctx.fill();

  // ── 标题区 ──
  ctx.textAlign = "center";
  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 42px -apple-system, sans-serif";
  ctx.fillText("WhoVoice", W / 2, 80);
  ctx.font = "24px -apple-system, sans-serif";
  ctx.fillStyle = "rgba(255,255,255,0.7)";
  ctx.fillText("声 纹 身 份 证", W / 2, 118);

  // 分隔线
  const lineGrad = ctx.createLinearGradient(150, 145, 600, 145);
  lineGrad.addColorStop(0, "rgba(233,69,96,0)");
  lineGrad.addColorStop(0.5, "rgba(233,69,96,0.8)");
  lineGrad.addColorStop(1, "rgba(233,69,96,0)");
  ctx.strokeStyle = lineGrad;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(150, 145);
  ctx.lineTo(600, 145);
  ctx.stroke();

  // ── 雷达图 ──
  const radar = props.posterData.radar;
  const labels = props.posterData.radar_labels || ["磁性", "甜美", "力量", "清澈", "独特"];
  const dims = [radar.magnetic, radar.sweet, radar.power, radar.clear, radar.unique];
  drawRadarChart(ctx, W / 2, 340, 160, dims, labels);

  // ── 明星脸谱 ──
  const starMix = props.posterData.star_mix || [];
  drawStarMix(ctx, 80, 560, W - 160, starMix);

  // ── 声纹标签 ──
  const voiceTags = props.posterData.voice_tags || [];
  drawVoiceTags(ctx, W / 2, 820, voiceTags);

  // ── 趣味称号 ──
  const funTitle = props.posterData.fun_title || "声线有故事的人";
  drawFunTitle(ctx, W / 2, 930, funTitle);

  // ── 底部品牌 ──
  drawBranding(ctx, W, H);
}

function drawRadarChart(ctx, cx, cy, radius, values, labels) {
  const n = values.length;
  const angleStep = (Math.PI * 2) / n;
  const startAngle = -Math.PI / 2;

  // 绘制网格 (3层)
  for (let level = 1; level <= 4; level++) {
    const r = (radius * level) / 4;
    ctx.beginPath();
    for (let i = 0; i <= n; i++) {
      const angle = startAngle + i * angleStep;
      const x = cx + r * Math.cos(angle);
      const y = cy + r * Math.sin(angle);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.strokeStyle = `rgba(255,255,255,${level === 4 ? 0.3 : 0.12})`;
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  // 绘制轴线
  for (let i = 0; i < n; i++) {
    const angle = startAngle + i * angleStep;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + radius * Math.cos(angle), cy + radius * Math.sin(angle));
    ctx.strokeStyle = "rgba(255,255,255,0.15)";
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  // 绘制数据区域
  ctx.beginPath();
  for (let i = 0; i <= n; i++) {
    const idx = i % n;
    const angle = startAngle + idx * angleStep;
    const r = (values[idx] / 100) * radius;
    const x = cx + r * Math.cos(angle);
    const y = cy + r * Math.sin(angle);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.closePath();

  // 填充渐变
  const fillGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
  fillGrad.addColorStop(0, "rgba(233, 69, 96, 0.4)");
  fillGrad.addColorStop(1, "rgba(108, 92, 231, 0.3)");
  ctx.fillStyle = fillGrad;
  ctx.fill();
  ctx.strokeStyle = "rgba(233, 69, 96, 0.9)";
  ctx.lineWidth = 2.5;
  ctx.stroke();

  // 绘制数据点
  for (let i = 0; i < n; i++) {
    const angle = startAngle + i * angleStep;
    const r = (values[i] / 100) * radius;
    const x = cx + r * Math.cos(angle);
    const y = cy + r * Math.sin(angle);
    ctx.beginPath();
    ctx.arc(x, y, 5, 0, Math.PI * 2);
    ctx.fillStyle = "#e94560";
    ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  // 标签和数值
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  for (let i = 0; i < n; i++) {
    const angle = startAngle + i * angleStep;
    const labelR = radius + 35;
    const x = cx + labelR * Math.cos(angle);
    const y = cy + labelR * Math.sin(angle);

    ctx.font = "bold 18px -apple-system, sans-serif";
    ctx.fillStyle = "#ffffff";
    ctx.fillText(labels[i], x, y - 10);

    ctx.font = "14px -apple-system, sans-serif";
    ctx.fillStyle = "rgba(233, 69, 96, 0.9)";
    ctx.fillText(values[i], x, y + 12);
  }
}

function drawStarMix(ctx, x, y, width, starMix) {
  if (!starMix.length) return;

  ctx.textAlign = "left";
  ctx.font = "bold 22px -apple-system, sans-serif";
  ctx.fillStyle = "rgba(255,255,255,0.9)";
  ctx.fillText("你的声音像:", x, y);

  const barColors = ["#e94560", "#6c5ce7", "#00cec9", "#fdcb6e", "#00b894"];
  const barHeight = 36;
  const gap = 52;
  const startY = y + 35;
  const maxBarWidth = width - 140;

  starMix.slice(0, 4).forEach((star, i) => {
    const barY = startY + i * gap;
    const barW = (star.percent / 100) * maxBarWidth;

    // 进度条背景
    ctx.fillStyle = "rgba(255,255,255,0.08)";
    roundRect(ctx, x, barY, maxBarWidth, barHeight, 8);
    ctx.fill();

    // 进度条填充
    const barGrad = ctx.createLinearGradient(x, barY, x + barW, barY);
    barGrad.addColorStop(0, barColors[i % barColors.length]);
    barGrad.addColorStop(1, barColors[(i + 1) % barColors.length]);
    ctx.fillStyle = barGrad;
    roundRect(ctx, x, barY, Math.max(barW, 20), barHeight, 8);
    ctx.fill();

    // 百分比
    ctx.textAlign = "left";
    ctx.font = "bold 16px -apple-system, sans-serif";
    ctx.fillStyle = "#ffffff";
    ctx.fillText(`${star.percent}%`, x + maxBarWidth + 10, barY + barHeight / 2 + 5);

    // 名字
    ctx.textAlign = "right";
    ctx.font = "17px -apple-system, sans-serif";
    ctx.fillStyle = "rgba(255,255,255,0.9)";
    ctx.fillText(star.name, x + maxBarWidth - 5, barY + barHeight / 2 + 5);
  });
}

function drawVoiceTags(ctx, cx, y, tags) {
  if (!tags.length) return;

  ctx.font = "bold 18px -apple-system, sans-serif";
  ctx.fillStyle = "rgba(255,255,255,0.6)";
  ctx.textAlign = "center";
  ctx.fillText("声纹标签", cx, y - 30);

  const tagHeight = 40;
  const tagPadding = 20;
  const tagGap = 12;

  ctx.font = "18px -apple-system, sans-serif";
  const tagWidths = tags.map(t => ctx.measureText(t).width + tagPadding * 2);
  const totalWidth = tagWidths.reduce((a, b) => a + b, 0) + (tags.length - 1) * tagGap;
  let startX = cx - totalWidth / 2;

  const tagColors = [
    { bg: "rgba(233,69,96,0.2)", border: "rgba(233,69,96,0.6)", text: "#ff8a9e" },
    { bg: "rgba(108,92,231,0.2)", border: "rgba(108,92,231,0.6)", text: "#a29bfe" },
    { bg: "rgba(0,206,201,0.2)", border: "rgba(0,206,201,0.6)", text: "#81ecec" },
    { bg: "rgba(253,203,110,0.2)", border: "rgba(253,203,110,0.6)", text: "#fdcb6e" },
  ];

  tags.forEach((tag, i) => {
    const w = tagWidths[i];
    const color = tagColors[i % tagColors.length];

    ctx.fillStyle = color.bg;
    roundRect(ctx, startX, y, w, tagHeight, tagHeight / 2);
    ctx.fill();
    ctx.strokeStyle = color.border;
    ctx.lineWidth = 1.5;
    roundRect(ctx, startX, y, w, tagHeight, tagHeight / 2);
    ctx.stroke();

    ctx.textAlign = "center";
    ctx.fillStyle = color.text;
    ctx.font = "17px -apple-system, sans-serif";
    ctx.fillText(tag, startX + w / 2, y + tagHeight / 2 + 6);

    startX += w + tagGap;
  });
}

function drawFunTitle(ctx, cx, y, title) {
  // 引号装饰
  ctx.textAlign = "center";
  ctx.font = "20px -apple-system, sans-serif";
  ctx.fillStyle = "rgba(233,69,96,0.5)";
  ctx.fillText("「", cx - ctx.measureText(title).width / 2 - 18, y + 5);
  ctx.fillText("」", cx + ctx.measureText(title).width / 2 + 18, y + 5);

  // 主标题
  ctx.font = "bold 32px -apple-system, sans-serif";
  ctx.fillStyle = "#ffffff";
  ctx.fillText(title, cx, y + 8);

  // 底部装饰线
  const lineW = Math.min(ctx.measureText(title).width + 40, 400);
  const lineGrad = ctx.createLinearGradient(cx - lineW / 2, y + 30, cx + lineW / 2, y + 30);
  lineGrad.addColorStop(0, "rgba(233,69,96,0)");
  lineGrad.addColorStop(0.5, "rgba(233,69,96,0.5)");
  lineGrad.addColorStop(1, "rgba(233,69,96,0)");
  ctx.strokeStyle = lineGrad;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(cx - lineW / 2, y + 35);
  ctx.lineTo(cx + lineW / 2, y + 35);
  ctx.stroke();
}

function drawBranding(ctx, W, H) {
  ctx.textAlign = "center";
  ctx.font = "16px -apple-system, sans-serif";
  ctx.fillStyle = "rgba(255,255,255,0.35)";
  ctx.fillText("WhoVoice · 用 AI 发现你的声音 DNA", W / 2, H - 60);
  ctx.font = "13px -apple-system, sans-serif";
  ctx.fillStyle = "rgba(255,255,255,0.2)";
  ctx.fillText("whovoice.app", W / 2, H - 35);
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.arcTo(x + w, y, x + w, y + r, r);
  ctx.lineTo(x + w, y + h - r);
  ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h);
  ctx.arcTo(x, y + h, x, y + h - r, r);
  ctx.lineTo(x, y + r);
  ctx.arcTo(x, y, x + r, y, r);
  ctx.closePath();
}

function savePoster() {
  const canvas = posterCanvas.value;
  if (!canvas) return;
  canvas.toBlob((blob) => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `whovoice_poster_${Date.now()}.png`;
    a.click();
    URL.revokeObjectURL(url);
  }, "image/png");
}

async function copyShareText() {
  const text = props.posterData?.share_text || "";
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    copied.value = true;
    setTimeout(() => { copied.value = false; }, 2500);
  } catch {
    // fallback
    const ta = document.createElement("textarea");
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    copied.value = true;
    setTimeout(() => { copied.value = false; }, 2500);
  }
}
</script>

<style scoped>
.poster-wrapper {
  margin-top: 1.5rem;
  animation: slideUp 0.4s ease-out;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.poster-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-bottom: 1rem;
}

.save-btn, .copy-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 22px;
  border: none;
  border-radius: 25px;
  font-size: 0.95rem;
  cursor: pointer;
  transition: all 0.2s;
}

.save-btn {
  background: linear-gradient(135deg, #e94560, #6c5ce7);
  color: white;
}

.save-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(233, 69, 96, 0.4);
}

.copy-btn {
  background: rgba(108, 92, 231, 0.12);
  color: #6c5ce7;
  border: 1.5px solid rgba(108, 92, 231, 0.3);
}

.copy-btn:hover {
  background: rgba(108, 92, 231, 0.2);
  border-color: #6c5ce7;
}

.canvas-container {
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  max-width: 375px;
  margin: 0 auto;
}

.canvas-container canvas {
  width: 100%;
  height: auto;
  display: block;
}
</style>
