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

  async function uploadAndMatch(audioBlob, selectedLyric = null) {
    isMatching.value = true
    currentLyric.value = selectedLyric
    posterData.value = null
    try {
      const formData = new FormData()
      formData.append('audio', audioBlob, 'recording.webm')
      formData.append('index', indexType.value)

      const response = await api.post('/voice-matching/match/', formData)
      matchResults.value = response.data.results
      totalCelebrities.value = response.data.total_celebrities || 0
      if (response.data.poster_data) {
        posterData.value = response.data.poster_data
      }
    } catch (err) {
      console.error('匹配失败:', err)
      throw err
    } finally {
      isMatching.value = false
    }
  }

  function switchIndex(type) {
    if (type !== indexType.value) {
      indexType.value = type
      matchResults.value = []
      posterData.value = null
    }
  }

  return {
    isRecording,
    isMatching,
    matchResults,
    posterData,
    totalCelebrities,
    indexType,
    uploadAndMatch,
    switchIndex,
  }
})
