import { ref } from 'vue'
import { defineStore } from 'pinia'
import { monitorApi } from '@/api'
import type {
  ConnectionState,
  HelloPayload,
  MonitorSnapshot,
  SessionInfo,
  SopEvent,
  WsMessage,
} from '@/types'

export const useMonitorStore = defineStore('monitor', () => {
  const snapshot = ref<MonitorSnapshot | null>(null)
  const events = ref<SopEvent[]>([])
  const connection = ref<ConnectionState>('offline')
  const lastMessageAt = ref<number | null>(null)

  let socket: WebSocket | null = null
  let reconnectTimer: number | null = null
  let pollTimer: number | null = null
  let pingTimer: number | null = null
  let attempts = 0
  let wantConnection = false

  function wsUrl(): string {
    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${scheme}://${window.location.host}/api/v1/ws/monitor`
  }

  function handleMessage(raw: string): void {
    let message: WsMessage
    try {
      message = JSON.parse(raw) as WsMessage
    } catch {
      return
    }
    lastMessageAt.value = Date.now()
    switch (message.type) {
      case 'hello': {
        const payload = message.data as HelloPayload
        if (payload?.snapshot) snapshot.value = payload.snapshot
        break
      }
      case 'telemetry': {
        snapshot.value = message.data as MonitorSnapshot
        break
      }
      case 'event': {
        const event = message.data as SopEvent
        events.value = [event, ...events.value].slice(0, 40)
        break
      }
      case 'session': {
        if (snapshot.value) {
          snapshot.value = { ...snapshot.value, session: message.data as SessionInfo }
        }
        break
      }
      default:
        break
    }
  }

  function openSocket(): void {
    if (socket && (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN)) {
      return
    }
    connection.value = 'connecting'
    socket = new WebSocket(wsUrl())
    socket.onopen = () => {
      attempts = 0
      connection.value = 'online'
      stopPolling()
      startPing()
    }
    socket.onmessage = (event) => handleMessage(event.data as string)
    socket.onerror = () => {
      socket?.close()
    }
    socket.onclose = () => {
      connection.value = 'offline'
      stopPing()
      socket = null
      if (!wantConnection) return
      startPolling()
      scheduleReconnect()
    }
  }

  function scheduleReconnect(): void {
    if (reconnectTimer !== null) return
    const delay = Math.min(1000 * 2 ** attempts, 8000)
    attempts += 1
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null
      if (wantConnection) openSocket()
    }, delay)
  }

  function startPing(): void {
    stopPing()
    pingTimer = window.setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'ping' }))
      }
    }, 20000)
  }

  function stopPing(): void {
    if (pingTimer !== null) {
      window.clearInterval(pingTimer)
      pingTimer = null
    }
  }

  async function poll(): Promise<void> {
    try {
      snapshot.value = await monitorApi.current()
      lastMessageAt.value = Date.now()
    } catch {
      // 保留最后一次快照，连接状态由 system store 提示
    }
  }

  function startPolling(): void {
    if (pollTimer !== null) return
    void poll()
    pollTimer = window.setInterval(() => {
      void poll()
    }, 2500)
  }

  function stopPolling(): void {
    if (pollTimer !== null) {
      window.clearInterval(pollTimer)
      pollTimer = null
    }
  }

  function connect(): void {
    wantConnection = true
    openSocket()
    if (!snapshot.value) void poll()
  }

  function disconnect(): void {
    wantConnection = false
    stopPing()
    stopPolling()
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (socket) {
      socket.onclose = null
      socket.close()
      socket = null
    }
    connection.value = 'offline'
  }

  async function refresh(): Promise<void> {
    await poll()
  }

  function clearEvents(): void {
    events.value = []
  }

  return {
    snapshot,
    events,
    connection,
    lastMessageAt,
    connect,
    disconnect,
    refresh,
    clearEvents,
  }
})
