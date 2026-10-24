import dayjs from 'dayjs'

export function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('YYYY-MM-DD HH:mm:ss') : value
}

export function formatTime(value?: string | null): string {
  if (!value) return '—'
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('HH:mm:ss') : value
}

export function formatDuration(seconds?: number | null): string {
  if (seconds === null || seconds === undefined) return '—'
  const total = Math.max(0, Math.round(seconds))
  if (total < 60) return `${total} 秒`
  const minutes = Math.floor(total / 60)
  const rest = total % 60
  if (minutes < 60) return `${minutes} 分 ${rest} 秒`
  const hours = Math.floor(minutes / 60)
  return `${hours} 小时 ${minutes % 60} 分`
}

export function formatMs(value?: number | null): string {
  if (value === null || value === undefined) return '—'
  return `${Math.round(value)} ms`
}

export function formatBytes(value?: number | null): string {
  if (!value) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = value
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

export function formatPercent(value?: number | null): string {
  if (value === null || value === undefined) return '—'
  return `${value.toFixed(1)}%`
}

export function withOffsetIso(value: dayjs.Dayjs): string {
  return value.format('YYYY-MM-DDTHH:mm:ssZ')
}

export const GESTURE_LABELS: Record<string, string> = {
  ONE: '1 根手指',
  TWO: '2 根手指',
  THREE: '3 根手指',
  FOUR: '4 根手指',
  FIVE: '5 根手指',
}

export const SESSION_STATUS_LABELS: Record<string, string> = {
  RUNNING: '执行中',
  COMPLETED: '已完成',
  FAILED: '判定失败',
  ABORTED: '已终止',
}

export const STEP_STATUS_LABELS: Record<string, string> = {
  PENDING: '待执行',
  CURRENT: '执行中',
  COMPLETED: '已完成',
  TIMEOUT: '超时',
  SKIPPED: '已跳过',
}

export const EVENT_TYPE_LABELS: Record<string, string> = {
  FLOW_STARTED: '流程开始',
  STEP_COMPLETED: '步骤完成',
  FLOW_COMPLETED: '流程完成',
  FLOW_FAILED: '流程失败',
  SKIPPED_STEP: '漏步骤',
  REPEATED_STEP: '重复步骤',
  ORDER_ERROR: '顺序错误',
  STEP_TIMEOUT: '步骤超时',
  SESSION_TIMEOUT: '流程超时',
  SESSION_ABORTED: '流程终止',
}

export const EVENT_STATUS_LABELS: Record<string, string> = {
  OPEN: '待处理',
  ACKED: '已确认',
  RESOLVED: '已解决',
  CLOSED: '已归档',
}

export const DETECTOR_STATUS_LABELS: Record<string, string> = {
  UNLOADED: '未加载',
  LOADING: '加载中',
  READY: '已加载',
  MOCK: '模拟检测器',
  ERROR: '加载失败',
  DISABLED: '已禁用',
}

export const CAMERA_STATUS_LABELS: Record<string, string> = {
  CONNECTED: '已连接',
  SIMULATED: '模拟画面',
  DISCONNECTED: '信号中断',
  OFF: '已关闭',
  ERROR: '异常',
}

export function sessionTagType(status?: string | null): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  switch (status) {
    case 'COMPLETED':
      return 'success'
    case 'RUNNING':
      return 'primary'
    case 'FAILED':
      return 'danger'
    case 'ABORTED':
      return 'warning'
    default:
      return 'info'
  }
}

export function severityTagType(severity?: string | null): 'success' | 'warning' | 'danger' | 'info' {
  switch (severity) {
    case 'CRITICAL':
      return 'danger'
    case 'WARNING':
      return 'warning'
    case 'INFO':
      return 'info'
    default:
      return 'info'
  }
}

export function eventStatusTagType(status?: string | null): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  switch (status) {
    case 'OPEN':
      return 'danger'
    case 'ACKED':
      return 'warning'
    case 'RESOLVED':
      return 'success'
    default:
      return 'info'
  }
}

export function stepStatusTagType(status?: string | null): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  switch (status) {
    case 'COMPLETED':
      return 'success'
    case 'CURRENT':
      return 'primary'
    case 'TIMEOUT':
    case 'SKIPPED':
      return 'danger'
    default:
      return 'info'
  }
}
