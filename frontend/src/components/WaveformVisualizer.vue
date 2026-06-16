<template>
  <canvas ref="canvas" class="waveform"></canvas>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  analyserNode: {
    type: Object,
    default: null,
  },
})

const canvas = ref(null)
let animationId = null

function draw() {
  if (!canvas.value || !props.analyserNode) return

  const ctx = canvas.value.getContext('2d')
  const bufferLength = props.analyserNode.frequencyBinCount
  const dataArray = new Uint8Array(bufferLength)

  function render() {
    animationId = requestAnimationFrame(render)
    props.analyserNode.getByteTimeDomainData(dataArray)

    ctx.fillStyle = '#f5f5f5'
    ctx.fillRect(0, 0, canvas.value.width, canvas.value.height)

    ctx.lineWidth = 2
    ctx.strokeStyle = '#1a1a2e'
    ctx.beginPath()

    const sliceWidth = canvas.value.width / bufferLength
    let x = 0

    for (let i = 0; i < bufferLength; i++) {
      const v = dataArray[i] / 128.0
      const y = (v * canvas.value.height) / 2

      if (i === 0) {
        ctx.moveTo(x, y)
      } else {
        ctx.lineTo(x, y)
      }
      x += sliceWidth
    }

    ctx.lineTo(canvas.value.width, canvas.value.height / 2)
    ctx.stroke()
  }

  render()
}

onMounted(() => {
  if (canvas.value) {
    canvas.value.width = canvas.value.offsetWidth
    canvas.value.height = canvas.value.offsetHeight
  }
  draw()
})

onUnmounted(() => {
  if (animationId) {
    cancelAnimationFrame(animationId)
  }
})
</script>

<style scoped>
.waveform {
  width: 100%;
  height: 120px;
  margin-top: 1rem;
  border-radius: 8px;
  background: #f5f5f5;
}
</style>
