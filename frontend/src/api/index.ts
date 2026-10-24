import { get, post, put } from '@/api/http'
import type {
  ConfigInfo,
  DashboardSummary,
  LogItem,
  ModelInfo,
  MonitorSnapshot,
  PageData,
  SessionDetail,
  SessionRecord,
  SimulationRequest,
  SopEvent,
  SopStepConfig,
  SopStepListResponse,
  SystemStatus,
} from '@/types'

export const dashboardApi = {
  summary: () => get<DashboardSummary>('/dashboard/summary'),
}

export const monitorApi = {
  current: () => get<MonitorSnapshot>('/monitor/current'),
  startSession: () => post<MonitorSnapshot>('/monitor/session/start'),
  stopSession: (reason = '操作员手动终止') =>
    post<MonitorSnapshot>('/monitor/session/stop', { reason }),
  streamUrl: (token: number) => `/api/v1/monitor/stream?t=${token}`,
}

export const sopApi = {
  list: () => get<SopStepListResponse>('/sop/steps'),
  save: (steps: SopStepConfig[]) =>
    put<SopStepListResponse>('/sop/steps', {
      steps: steps.map((step) => ({
        order: step.order,
        name: step.name,
        expected_gesture: step.expected_gesture,
        description: step.description,
        timeout_seconds: step.timeout_seconds,
        enabled: step.enabled,
        required: step.required,
      })),
    }),
  reset: () => post<SopStepListResponse>('/sop/steps/reset'),
}

export const eventsApi = {
  list: (params: Record<string, unknown>) => get<PageData<SopEvent>>('/events', params),
  updateStatus: (id: number, status: 'ACKED' | 'RESOLVED') =>
    post<SopEvent>(`/events/${id}/status`, { status }),
}

export const historyApi = {
  sessions: (params: Record<string, unknown>) =>
    get<PageData<SessionRecord>>('/history/sessions', params),
  detail: (id: string) => get<SessionDetail>(`/history/sessions/${id}`),
}

export const systemApi = {
  status: () => get<SystemStatus>('/system/status'),
  config: () => get<ConfigInfo>('/system/config'),
  logs: (limit = 50) => get<{ items: LogItem[] }>('/system/logs', { limit }),
  reloadModel: () => post<ModelInfo>('/system/model/reload'),
  reconnectCamera: () => post<Record<string, unknown>>('/system/camera/reconnect'),
  simulate: (payload: SimulationRequest) =>
    post<{ action: string; message: string; gesture?: string }>('/system/simulation', payload),
}
