// ============ 通用 ============
export interface ApiEnvelope<T> {
  code: number
  message: string
  data: T
  request_id?: string | null
  timestamp: string
}

export interface PageMeta {
  page: number
  page_size: number
  total: number
  pages: number
}

export interface PageData<T> {
  items: T[]
  meta: PageMeta
}

export type DetectorStatus = 'UNLOADED' | 'LOADING' | 'READY' | 'MOCK' | 'ERROR' | 'DISABLED'
export type CameraStatus = 'CONNECTED' | 'SIMULATED' | 'DISCONNECTED' | 'OFF' | 'ERROR'
export type RuntimeState = 'IDLE' | 'RUNNING' | 'DEGRADED' | 'DISABLED'
export type SessionStatus = 'RUNNING' | 'COMPLETED' | 'FAILED' | 'ABORTED'
export type EventSeverity = 'INFO' | 'WARNING' | 'CRITICAL'
export type EventStatus = 'OPEN' | 'ACKED' | 'RESOLVED' | 'CLOSED'
export type ConnectionState = 'connecting' | 'online' | 'offline'

// ============ 监控 ============
export interface StationInfo {
  id: string
  name: string
}

export interface BoxInfo {
  x1: number
  y1: number
  x2: number
  y2: number
  confidence: number
  label: string
  gesture: string | null
}

export interface DetectionInfo {
  gesture: string | null
  label: string | null
  confidence: number
  simulated: boolean
  inference_ms: number
  boxes: BoxInfo[]
  at: string
}

export interface RuntimeInfo {
  state: RuntimeState
  simulated: boolean
  runtime_enabled?: boolean
  enabled?: boolean
  inference_fps_target: number
  measured_fps: number
  inference_latency_ms?: number | null
  last_detection_at?: string | null
}

export interface SessionInfo {
  id: string
  station_id: string
  status: SessionStatus
  trigger: string | null
  started_at: string
  finished_at: string | null
  total_steps: number
  completed_steps: number
  anomaly_count: number
  compliance: boolean | null
  end_reason: string | null
}

export type StepProgressStatus =
  | 'PENDING'
  | 'CURRENT'
  | 'COMPLETED'
  | 'TIMEOUT'
  | 'SKIPPED'

export interface StepProgress {
  order: number
  name: string
  gesture: string
  description: string
  timeout_seconds: number
  status: StepProgressStatus
  duration_ms: number | null
  confidence: number | null
}

export interface CurrentStep {
  order: number
  name: string
  gesture: string
  description: string
  timeout_seconds: number
  elapsed_seconds: number
  remaining_seconds: number
}

export interface MonitorSnapshot {
  station: StationInfo
  session: SessionInfo | null
  steps: StepProgress[]
  current_step: CurrentStep | null
  detection: DetectionInfo | null
  runtime: RuntimeInfo
  updated_at: string
}

// ============ SOP 配置 ============
export interface SopStepConfig {
  order: number
  name: string
  expected_gesture: string
  description: string
  timeout_seconds: number
  enabled: boolean
  required: boolean
}

export interface SopStepListResponse {
  items: SopStepConfig[]
  note: string
  pending_config: boolean
}

// ============ 异常 ============
export interface SopEvent {
  id: number
  session_id: string | null
  station_id: string
  event_type: string
  severity: EventSeverity
  step_order: number | null
  step_name: string | null
  message: string
  status: EventStatus
  created_at: string
  handled_at: string | null
  handled_by: string | null
}

// ============ 历史 ============
export interface SessionRecord {
  id: string
  station_id: string
  station_name: string
  status: SessionStatus
  trigger: string
  started_at: string
  finished_at: string | null
  total_steps: number
  completed_steps: number
  anomaly_count: number
  compliance: boolean | null
  end_reason: string | null
  duration_seconds: number | null
}

export interface StepRecord {
  id: number
  session_id: string
  step_order: number
  step_name: string
  gesture: string
  status: string
  confidence: number | null
  started_at: string
  finished_at: string
  duration_ms: number
}

export interface SessionDetail {
  session: SessionRecord
  steps: StepRecord[]
  events: SopEvent[]
}

// ============ 系统 ============
export interface ModelInfo {
  name: string
  status: DetectorStatus
  simulated: boolean
  error: string | null
  backend?: string
  notice?: string
  selection_reason?: string
  model_path?: string
  weights_exist?: boolean
  device?: string
  class_count?: number
  mapped_classes?: string[]
  class_map_path?: string
  confidence_threshold?: number
  scenario?: string
  sequence?: string[]
}

export interface CameraInfo {
  status: CameraStatus
  source: string
  simulated: boolean
  connected: boolean
  stale: boolean
  index: number
  resolution: string
  target_fps: number
  measured_fps: number
  last_frame_at: string | null
  message: string
}

export interface LogItem {
  time: string
  level: string
  logger: string
  message: string
}

export interface SystemStatus {
  backend: {
    status: string
    version: string
    environment: string
    started_at: string
    uptime_seconds: number
    pid: number
    python: string
  }
  runtime: RuntimeInfo
  model: ModelInfo
  camera: CameraInfo
  database: {
    status: string
    path: string
    size_bytes: number
  }
  realtime: {
    ws_clients: number
    telemetry_interval_ms: number
  }
  sop: {
    station_id: string
    station_name: string
    steps_total: number
    enabled_steps: number
    active_session_id: string | null
    session_status: string | null
    pending_config: boolean
    config_note: string
  }
  recent_errors: LogItem[]
  server_time?: string
  api_prefix?: string
}

export interface ConfigInfo {
  station_id: string
  station_name: string
  inference_mode: string
  model_path: string
  model_device: string
  model_conf: number
  camera_mode: string
  camera_index: number
  camera_resolution: string
  inference_fps: number
  detection_stable_frames: number
  detection_reset_ms: number
  fail_on_sequence_error: boolean
  fail_on_timeout: boolean
  session_max_seconds: number
  auto_start_session: boolean
  database_path: string
  log_dir: string
  telemetry_interval_ms: number
}

// ============ 仪表盘 ============
export interface DashboardStats {
  sessions_total: number
  sessions_completed: number
  sessions_failed: number
  compliant_sessions: number
  compliance_rate: number | null
  compliance_samples: number
  operations: number
  anomalies_today: number
  open_anomalies: number
  avg_cycle_seconds: number | null
}

export interface DashboardSummary {
  station: StationInfo
  stats: DashboardStats
  runtime: RuntimeInfo
  session: SessionInfo | null
  current_step: CurrentStep | null
  steps: StepProgress[]
  recent_events: SopEvent[]
  recent_sessions: SessionRecord[]
  system: {
    model_status: DetectorStatus
    model_simulated: boolean
    camera_status: CameraStatus
    camera_simulated: boolean
    simulated: boolean
    ws_clients: number
  }
  updated_at: string
}

// ============ WebSocket ============
export interface WsMessage {
  type: 'hello' | 'telemetry' | 'event' | 'session' | 'system' | 'pong'
  data?: unknown
  ts?: string
}

export interface HelloPayload {
  system: SystemStatus
  snapshot: MonitorSnapshot
}

export interface SimulationRequest {
  action: 'gesture' | 'skip' | 'repeat' | 'wrong_order' | 'timeout' | 'reset'
  gesture?: 'ONE' | 'TWO' | 'THREE' | 'FOUR' | 'FIVE'
}
