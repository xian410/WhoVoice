import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api'

export const useVoiceStore = defineStore('voice', () => {
  const isRecording = ref(false)
  const isMatching = ref(false)
  const matchResults = ref([])
  const posterData = ref(null)
  const currentLyric = ref(null)
  const totalCelebrities = ref(0)
  const indexType = ref('clean')

  // ── 排队状态 ──
  const queueInfo = ref(null)
  const isQueued = ref(false)
  const currentTaskId = ref('')

  // ── 排行榜状态 ──
  const leaderboardEntries = ref([])
  const leaderboardGlobal = ref([])
  const submitResult = ref(null)
  const isSubmitting = ref(false)

  async function uploadAndMatch(audioBlob, selectedLyric = null) {
    isMatching.value = true
    currentLyric.value = selectedLyric
    posterData.value = null
    matchResults.value = []
    queueInfo.value = null
    isQueued.value = true

    const formData = new FormData()
    // 根据实际 blob 类型决定文件扩展名（iOS 为 mp4，桌面为 webm）
    const typeMap = { 'audio/webm': 'webm', 'audio/mp4': 'mp4', 'audio/ogg': 'ogg', 'audio/wav': 'wav' }
    const ext = typeMap[audioBlob.type] || 'webm'
    formData.append('audio', audioBlob, `recording.${ext}`)
    formData.append('index', indexType.value)

    try {
      const resp = await api.post('/voice-matching/match/', formData, {
        timeout: 30000,
      })
      const data = resp.data

      if (data.task_id) {
        currentTaskId.value = data.task_id
        await pollTask(data.task_id)
      } else if (data.results) {
        matchResults.value = data.results
        totalCelebrities.value = data.total_celebrities || 0
        if (data.poster_data) {
          posterData.value = data.poster_data
        }
      }
    } catch (err) {
      console.error('匹配失败:', err)
      isQueued.value = false
      throw err
    } finally {
      isMatching.value = false
    }
  }

  async function pollTask(taskId) {
    const maxWait = 300
    const startTime = Date.now()

    while (true) {
      if (Date.now() - startTime > maxWait * 1000) {
        queueInfo.value = { ...queueInfo.value, status: 'timeout' }
        throw new Error('排队超时，请稍后重试')
      }

      try {
        const resp = await api.get(`/voice-matching/status/${taskId}/`)
        const data = resp.data

        queueInfo.value = {
          taskId: data.task_id,
          status: data.status,
          position: data.position,
          estimatedWait: data.estimated_wait,
        }

        if (data.status === 'done') {
          matchResults.value = data.results || []
          totalCelebrities.value = data.total_celebrities || 0
          if (data.poster_data) {
            posterData.value = data.poster_data
          }
          isQueued.value = false
          queueInfo.value = null
          return
        } else if (data.status === 'error') {
          isQueued.value = false
          queueInfo.value = null
          throw new Error(data.error || '处理失败')
        }

        const interval = data.position === 1 ? 800 : 1500
        await sleep(interval)
      } catch (err) {
        if (err.response?.status === 404) {
          await sleep(500)
          continue
        }
        throw err
      }
    }
  }

  function switchIndex(type) {
    if (type !== indexType.value) {
      indexType.value = type
      matchResults.value = []
      posterData.value = null
      queueInfo.value = null
      isQueued.value = false
      currentTaskId.value = ''
    }
  }

  // ── 排行榜 ──

  async function submitToLeaderboard(celebrityName, score, audioBlob, nickname, taskId) {
    isSubmitting.value = true
    submitResult.value = null

    const formData = new FormData()
    formData.append('celebrity_name', celebrityName)
    formData.append('score', score)
    formData.append('audio', audioBlob, 'leaderboard_audio.webm')
    if (nickname) formData.append('nickname', nickname)
    if (taskId) formData.append('task_id', taskId)

    try {
      const resp = await api.post('/voice-matching/leaderboard/submit/', formData, {
        timeout: 30000,
      })
      submitResult.value = resp.data
      return resp.data
    } catch (err) {
      console.error('排行榜提交失败:', err)
      throw err
    } finally {
      isSubmitting.value = false
    }
  }

  async function fetchLeaderboard(celebrityName, top = 50) {
    try {
      const resp = await api.get(`/voice-matching/leaderboard/${encodeURIComponent(celebrityName)}/`, {
        params: { top },
      })
      leaderboardEntries.value = resp.data
      return resp.data
    } catch (err) {
      console.error('获取排行榜失败:', err)
      leaderboardEntries.value = { celebrity_name: celebrityName, total_entries: 0, entries: [] }
      throw err
    }
  }

  async function fetchGlobalLeaderboard(top = 100) {
    try {
      const resp = await api.get('/voice-matching/leaderboard/', {
        params: { top },
      })
      leaderboardGlobal.value = resp.data.leaderboard || []
      return resp.data
    } catch (err) {
      console.error('获取全局排行榜失败:', err)
      leaderboardGlobal.value = []
      throw err
    }
  }

  return {
    isRecording,
    isMatching,
    matchResults,
    posterData,
    totalCelebrities,
    indexType,
    queueInfo,
    isQueued,
    currentTaskId,
    leaderboardEntries,
    leaderboardGlobal,
    submitResult,
    isSubmitting,
    uploadAndMatch,
    switchIndex,
    submitToLeaderboard,
    fetchLeaderboard,
    fetchGlobalLeaderboard,
  }
})

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
