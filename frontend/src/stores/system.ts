import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { systemApi } from '@/api'
import type { SystemStatus } from '@/types'

export const useSystemStore = defineStore('system', () => {
  const status = ref<SystemStatus | null>(null)
  const online = ref(false)
  const error = ref<string | null>(null)
  const loading = ref(false)
  const lastUpdated = ref<number | null>(null)

  let timer: number | null = null
  let inflight = false

  async function refresh(): Promise<void> {
    if (inflight) return
    inflight = true
    loading.value = true
    try {
      status.value = await systemApi.status()
      online.value = true
      error.value = null
      lastUpdated.value = Date.now()
    } catch (err) {
      online.value = false
      error.value = err instanceof Error ? err.message : '系统状态获取失败'
    } finally {
      loading.value = false
      inflight = false
    }
  }

  function startPolling(interval = 5000): void {
    stopPolling()
    void refresh()
    timer = window.setInterval(() => {
      void refresh()
    }, interval)
  }

  function stopPolling(): void {
    if (timer !== null) {
      window.clearInterval(timer)
      timer = null
    }
  }

  const simulated = computed(() => status.value?.runtime.simulated ?? false)
  const modelStatus = computed(() => status.value?.model.status ?? 'UNLOADED')
  const cameraStatus = computed(() => status.value?.camera.status ?? 'OFF')

  return {
    status,
    online,
    error,
    loading,
    lastUpdated,
    simulated,
    modelStatus,
    cameraStatus,
    refresh,
    startPolling,
    stopPolling,
  }
})
