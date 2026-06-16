import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api'

export const useVoiceStore = defineStore('voice', () => {
  const isRecording = ref(false)
  const isMatching = ref(false)
  const matchResults = ref([])

  async function uploadAndMatch(audioBlob) {
    isMatching.value = true
    try {
      const formData = new FormData()
      formData.append('audio', audioBlob, 'recording.webm')

      const response = await api.post('/voice-matching/match/', formData)
      matchResults.value = response.data.results
    } catch (err) {
      console.error('匹配失败:', err)
      throw err
    } finally {
      isMatching.value = false
    }
  }

  return {
    isRecording,
    isMatching,
    matchResults,
    uploadAndMatch,
  }
})
