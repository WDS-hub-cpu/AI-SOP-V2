<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">
          <el-icon><Cpu /></el-icon>
        </div>
        <div class="brand-text">
          <strong>AI SOP</strong>
          <span>工业智能监控</span>
        </div>
      </div>

      <el-menu class="nav" :default-active="route.path" router>
        <el-menu-item v-for="item in menu" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span class="nav-label">{{ item.title }}</span>
        </el-menu-item>
      </el-menu>

      <div class="nav-foot">
        <div v-if="system.simulated" class="sim-note">
          <el-icon><WarningFilled /></el-icon>
          <span>模拟模式运行</span>
        </div>
        <a class="backend-console-link" :href="backendConsoleUrl" target="_blank" rel="noopener">
          <el-icon><Monitor /></el-icon>
          <span>后端控制台</span>
        </a>
        <span>v{{ version }} · {{ environment }}</span>
      </div>
    </aside>

    <div class="main">
      <header class="topbar">
        <div class="topbar-title">
          <h1>{{ pageTitle }}</h1>
          <p>{{ pageSubtitle }}</p>
        </div>
        <div class="topbar-right">
          <span class="status-chip" :class="system.online ? 'ok' : 'danger'">
            <i class="dot" />后端{{ system.online ? '在线' : '离线' }}
          </span>
          <span class="status-chip" :class="realtimeChip.cls">
            <i class="dot" />{{ realtimeChip.label }}
          </span>
          <span class="status-chip" :class="modelChip.cls">
            <i class="dot" />{{ modelChip.label }}
          </span>
          <span class="status-chip" :class="cameraChip.cls">
            <i class="dot" />{{ cameraChip.label }}
          </span>
          <span class="clock mono">{{ clock }}</span>
        </div>
      </header>

      <main class="content">
        <el-alert
          v-if="system.error && !system.online"
          class="backend-alert"
          type="error"
          :closable="false"
          show-icon
          title="无法连接后端服务"
          :description="system.error + '。请确认后端已启动：scripts\\start-backend.ps1'"
          style="margin-bottom: 14px"
        />
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, type Component } from 'vue'
import { useRoute } from 'vue-router'
import dayjs from 'dayjs'
import {
  Clock,
  Cpu,
  List,
  Monitor,
  Odometer,
  VideoCamera,
  Warning,
  WarningFilled,
} from '@element-plus/icons-vue'
import { useSystemStore } from '@/stores/system'
import { useMonitorStore } from '@/stores/monitor'

interface MenuItem {
  path: string
  title: string
  icon: Component
}

const route = useRoute()
const system = useSystemStore()
const monitor = useMonitorStore()

const menu: MenuItem[] = [
  { path: '/dashboard', title: '首页仪表盘', icon: Odometer },
  { path: '/monitor', title: '实时监控', icon: VideoCamera },
  { path: '/sop', title: 'SOP 配置', icon: List },
  { path: '/events', title: '异常记录', icon: Warning },
  { path: '/history', title: '历史记录', icon: Clock },
  { path: '/system', title: '系统状态', icon: Monitor },
]

const pageTitle = computed(() => (route.meta.title as string | undefined) ?? '工业 AI SOP')
const pageSubtitle = computed(() => (route.meta.subtitle as string | undefined) ?? '')
const version = computed(() => system.status?.backend.version ?? '2.0.0')
const environment = computed(() => (system.status?.backend.environment ?? 'DEV').toUpperCase())
const backendConsoleUrl = `${window.location.protocol}//${window.location.hostname}:8000/console`

const realtimeChip = computed(() => {
  if (monitor.connection === 'online') return { cls: 'ok', label: '实时已连接' }
  if (monitor.connection === 'connecting') return { cls: 'warn', label: '实时连接中' }
  return { cls: 'danger', label: '实时断开' }
})

const modelChip = computed(() => {
  switch (system.modelStatus) {
    case 'READY':
      return { cls: 'ok', label: '模型已加载' }
    case 'MOCK':
      return { cls: 'warn', label: '模型：模拟' }
    case 'ERROR':
      return { cls: 'danger', label: '模型异常' }
    case 'LOADING':
      return { cls: 'warn', label: '模型加载中' }
    default:
      return { cls: 'warn', label: '模型未加载' }
  }
})

const cameraChip = computed(() => {
  switch (system.cameraStatus) {
    case 'CONNECTED':
      return { cls: 'ok', label: '摄像头已连接' }
    case 'SIMULATED':
      return { cls: 'warn', label: '摄像头：模拟' }
    case 'DISCONNECTED':
      return { cls: 'danger', label: '摄像头中断' }
    case 'ERROR':
      return { cls: 'danger', label: '摄像头异常' }
    default:
      return { cls: 'warn', label: '摄像头关闭' }
  }
})

const clock = ref(dayjs().format('YYYY-MM-DD HH:mm:ss'))
let clockTimer: number | null = null

onMounted(() => {
  system.startPolling(5000)
  monitor.connect()
  clockTimer = window.setInterval(() => {
    clock.value = dayjs().format('YYYY-MM-DD HH:mm:ss')
  }, 1000)
})

onUnmounted(() => {
  system.stopPolling()
  monitor.disconnect()
  if (clockTimer !== null) window.clearInterval(clockTimer)
})
</script>
