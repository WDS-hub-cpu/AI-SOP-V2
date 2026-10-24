<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>生产概览</h2>
        <p>数据每 5 秒自动刷新，合规判定以服务端规则引擎为准。</p>
      </div>
      <div class="page-actions">
        <span v-if="simulated" class="tag-sim">SIMULATION · 模拟数据</span>
        <el-button :icon="Refresh" :loading="loading" @click="load(true)">刷新</el-button>
      </div>
    </div>

    <el-alert
      v-if="error"
      type="error"
      :closable="false"
      show-icon
      :title="error"
      description="请确认后端服务已启动，并检查数据库与运行时状态。"
    />

    <div class="grid cols-5">
      <div class="metric">
        <div class="metric-label"><el-icon><Location /></el-icon>当前工位</div>
        <div class="metric-value station-value">{{ summary?.station.id ?? '—' }}</div>
        <div class="metric-foot">{{ summary?.station.name ?? '等待后端数据' }}</div>
      </div>

      <div class="metric" :class="runtimeClass">
        <div class="metric-label"><el-icon><Cpu /></el-icon>运行状态</div>
        <div class="metric-value">{{ runtimeLabel }}</div>
        <div class="metric-foot">
          {{ modelStatusText }} · {{ cameraStatusText }}
        </div>
      </div>

      <div class="metric">
        <div class="metric-label"><el-icon><DataLine /></el-icon>今日操作次数</div>
        <div class="metric-value mono">{{ summary?.stats.operations ?? 0 }}<small>次</small></div>
        <div class="metric-foot">已完成步骤记录 {{ summary?.stats.sessions_completed ?? 0 }} 个流程</div>
      </div>

      <div class="metric" :class="complianceClass">
        <div class="metric-label"><el-icon><CircleCheck /></el-icon>今日合规率</div>
        <div class="metric-value mono">{{ formatPercent(complianceRate) }}</div>
        <div class="metric-foot">样本：{{ summary?.stats.compliance_samples ?? 0 }} 个已完成会话</div>
      </div>

      <div class="metric" :class="openAnomalies > 0 ? 'danger' : 'ok'">
        <div class="metric-label"><el-icon><WarningFilled /></el-icon>异常数量</div>
        <div class="metric-value mono">{{ openAnomalies }}<small>待处理</small></div>
        <div class="metric-foot">今日新增 {{ todayAnomalies }} 条 · 失败 {{ summary?.stats.sessions_failed ?? 0 }} 次</div>
      </div>
    </div>

    <div class="grid dashboard-main">
      <section class="panel">
        <div class="panel-head">
          <div>
            <div class="panel-title">当前 SOP 流程</div>
            <div class="panel-sub">
              {{ session ? `会话 ${shortId(session.id)} · ${session.trigger === 'manual' ? '手动触发' : '自动触发'}` : '等待检测到第一个有效动作' }}
            </div>
          </div>
          <div class="toolbar">
            <el-tag v-if="session" :type="sessionTagType(session.status)" effect="dark">
              {{ SESSION_STATUS_LABELS[session.status] ?? session.status }}
            </el-tag>
            <el-tag v-else type="info" effect="dark">空闲</el-tag>
            <el-tag
              v-if="session && session.compliance !== null"
              :type="session.compliance ? 'success' : 'danger'"
              effect="plain"
            >
              {{ session.compliance ? '合规' : '不合规' }}
            </el-tag>
          </div>
        </div>

        <div class="session-banner">
          <div>
            <div class="kv-key">执行进度</div>
            <div class="progress-text mono">
              {{ session?.completed_steps ?? 0 }} / {{ session?.total_steps ?? steps.length }}
              <span class="text-muted">步骤</span>
            </div>
          </div>
          <div>
            <div class="kv-key">当前步骤</div>
            <div class="current-step-text">
              {{ currentStep ? `${currentStep.order}. ${currentStep.name}` : '—' }}
            </div>
          </div>
          <div>
            <div class="kv-key">剩余时间</div>
            <div class="mono" :class="remaining <= 5 ? 'text-danger' : ''">
              {{ currentStep ? `${currentStep.remaining_seconds.toFixed(0)} s` : '—' }}
            </div>
          </div>
          <div>
            <div class="kv-key">异常计数</div>
            <div class="mono" :class="(session?.anomaly_count ?? 0) > 0 ? 'text-danger' : 'text-ok'">
              {{ session?.anomaly_count ?? 0 }}
            </div>
          </div>
        </div>

        <div class="progress-thin">
          <div class="progress-thin-fill" :style="{ width: `${progress}%` }"></div>
        </div>

        <div class="step-list dashboard-steps">
          <div
            v-for="step in steps"
            :key="step.order"
            class="step-item"
            :class="stepClass(step.status)"
          >
            <div class="step-index mono">{{ step.order }}</div>
            <div class="step-main">
              <div class="step-name">
                {{ step.name }}
                <span class="gesture-chip mono">{{ step.gesture }}</span>
              </div>
              <div class="step-desc">{{ step.description || '—' }}</div>
            </div>
            <div class="step-side">
              <el-tag size="small" :type="stepStatusTagType(step.status)" effect="plain">
                {{ STEP_STATUS_LABELS[step.status] ?? step.status }}
              </el-tag>
              <span v-if="step.duration_ms" class="mono">
                {{ (step.duration_ms / 1000).toFixed(1) }} s
              </span>
            </div>
          </div>
          <div v-if="steps.length === 0" class="empty-state">尚未配置 SOP 步骤</div>
        </div>
      </section>

      <div class="side-stack">
        <section class="panel">
          <div class="panel-head">
            <div>
              <div class="panel-title">实时识别</div>
              <div class="panel-sub">最新一次模型输出（后端推送）</div>
            </div>
            <span v-if="simulated" class="tag-sim">SIMULATION</span>
          </div>
          <div v-if="detection" class="detection-panel">
            <div class="gesture-value">{{ detection.gesture ?? '—' }}</div>
            <div class="text-muted">
              {{ detection.gesture ? GESTURE_LABELS[detection.gesture] ?? detection.gesture : '未检测到手势' }}
              <span class="mono"> · {{ (detection.confidence * 100).toFixed(1) }}%</span>
            </div>
            <div class="confidence-track">
              <div class="confidence-fill" :style="{ width: `${Math.min(detection.confidence * 100, 100)}%` }"></div>
            </div>
            <div class="detection-meta">
              <span>推理延迟 <b class="mono">{{ detection.inference_ms.toFixed(1) }} ms</b></span>
              <span v-if="detection.simulated" class="text-warn">模拟数据，非真实 AI 结果</span>
            </div>
          </div>
          <div v-else class="empty-state">等待检测数据…</div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div class="panel-title">系统连通性</div>
            <el-button text size="small" :icon="Refresh" @click="load(true)">刷新</el-button>
          </div>
          <div class="kv-list">
            <div class="kv-row">
              <span class="kv-key">后端服务</span>
              <span class="kv-val">
                <i class="dot" :class="systemOnline ? 'ok' : 'danger'"></i>
                {{ systemOnline ? '在线' : '不可用' }}
              </span>
            </div>
            <div class="kv-row">
              <span class="kv-key">模型状态</span>
              <span class="kv-val">{{ modelStatusText }}</span>
            </div>
            <div class="kv-row">
              <span class="kv-key">摄像头</span>
              <span class="kv-val">{{ cameraStatusText }}</span>
            </div>
            <div class="kv-row">
              <span class="kv-key">实时客户端</span>
              <span class="kv-val mono">{{ summary?.system.ws_clients ?? 0 }} 个</span>
            </div>
            <div class="kv-row">
              <span class="kv-key">更新于</span>
              <span class="kv-val mono">{{ formatTime(summary?.updated_at) }}</span>
            </div>
          </div>
        </section>
      </div>
    </div>

    <div class="grid cols-2">
      <section class="panel">
        <div class="panel-head">
          <div>
            <div class="panel-title">最近异常</div>
            <div class="panel-sub">仅显示告警与严重级别事件</div>
          </div>
          <router-link to="/events" class="panel-link">查看全部 →</router-link>
        </div>
        <el-table v-if="(summary?.recent_events.length ?? 0) > 0" :data="summary?.recent_events" size="small">
          <el-table-column label="时间" width="92">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="类型" width="104">
            <template #default="{ row }">
              <el-tag size="small" :type="severityTagType(row.severity)" effect="plain">
                {{ EVENT_TYPE_LABELS[row.event_type] ?? row.event_type }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="描述" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">{{ row.message }}</template>
          </el-table-column>
          <el-table-column label="状态" width="82">
            <template #default="{ row }">
              <el-tag size="small" :type="eventStatusTagType(row.status)" effect="dark">
                {{ EVENT_STATUS_LABELS[row.status] ?? row.status }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
        <div v-else class="empty-state">今日暂无异常，流程运行正常</div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div>
            <div class="panel-title">最近会话</div>
            <div class="panel-sub">最近 5 次流程执行结果</div>
          </div>
          <router-link to="/history" class="panel-link">查看全部 →</router-link>
        </div>
        <el-table v-if="(summary?.recent_sessions.length ?? 0) > 0" :data="summary?.recent_sessions" size="small">
          <el-table-column label="开始时间" width="140">
            <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="92">
            <template #default="{ row }">
              <el-tag size="small" :type="sessionTagType(row.status)" effect="dark">
                {{ SESSION_STATUS_LABELS[row.status] ?? row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="步骤" width="76">
            <template #default="{ row }">
              <span class="mono">{{ row.completed_steps }}/{{ row.total_steps }}</span>
            </template>
          </el-table-column>
          <el-table-column label="异常" width="64">
            <template #default="{ row }">
              <span class="mono" :class="row.anomaly_count > 0 ? 'text-danger' : 'text-ok'">
                {{ row.anomaly_count }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="合规" min-width="72">
            <template #default="{ row }">
              <span v-if="row.compliance === null || row.compliance === undefined" class="text-muted">—</span>
              <span v-else :class="Number(row.compliance) === 1 ? 'text-ok' : 'text-danger'">
                {{ Number(row.compliance) === 1 ? '合规' : '不合规' }}
              </span>
            </template>
          </el-table-column>
        </el-table>
        <div v-else class="empty-state">暂无历史会话</div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  CircleCheck,
  Cpu,
  DataLine,
  Location,
  Refresh,
  WarningFilled,
} from '@element-plus/icons-vue'
import { dashboardApi } from '@/api'
import { useMonitorStore } from '@/stores/monitor'
import type { DashboardSummary, StepProgressStatus } from '@/types'
import {
  CAMERA_STATUS_LABELS,
  DETECTOR_STATUS_LABELS,
  EVENT_STATUS_LABELS,
  EVENT_TYPE_LABELS,
  GESTURE_LABELS,
  SESSION_STATUS_LABELS,
  STEP_STATUS_LABELS,
  eventStatusTagType,
  formatDateTime,
  formatPercent,
  formatTime,
  sessionTagType,
  severityTagType,
  stepStatusTagType,
} from '@/utils/format'

const RUNTIME_LABELS: Record<string, string> = {
  IDLE: '待机',
  RUNNING: '生产中',
  DEGRADED: '降级运行',
  DISABLED: '已禁用',
}

const summary = ref<DashboardSummary | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const monitor = useMonitorStore()
let timer: number | null = null

const simulated = computed(() => summary.value?.runtime.simulated ?? false)
const systemOnline = computed(() => !error.value && summary.value !== null)
const runtimeLabel = computed(() => RUNTIME_LABELS[summary.value?.runtime.state ?? 'IDLE'] ?? '未知')
const runtimeClass = computed(() => {
  const state = summary.value?.runtime.state
  if (state === 'DEGRADED') return 'danger'
  if (state === 'RUNNING') return 'ok'
  return ''
})
const complianceRate = computed(() => summary.value?.stats.compliance_rate ?? null)
const complianceClass = computed(() => {
  if (complianceRate.value === null) return ''
  return complianceRate.value >= 95 ? 'ok' : complianceRate.value >= 80 ? 'warn' : 'danger'
})
const openAnomalies = computed(() => summary.value?.stats.open_anomalies ?? 0)
const todayAnomalies = computed(() => summary.value?.stats.anomalies_today ?? 0)
const session = computed(() => summary.value?.session ?? null)
const steps = computed(() => summary.value?.steps ?? [])
const currentStep = computed(() => summary.value?.current_step ?? null)
const remaining = computed(() => currentStep.value?.remaining_seconds ?? 0)
const detection = computed(() => monitor.snapshot?.detection ?? null)
const progress = computed(() => {
  const total = session.value?.total_steps ?? steps.value.length
  if (!total) return 0
  return Math.min(((session.value?.completed_steps ?? 0) / total) * 100, 100)
})
const modelStatusText = computed(
  () => DETECTOR_STATUS_LABELS[summary.value?.system.model_status ?? 'UNLOADED'] ?? '—',
)
const cameraStatusText = computed(
  () => CAMERA_STATUS_LABELS[summary.value?.system.camera_status ?? 'OFF'] ?? '—',
)

function stepClass(status: StepProgressStatus): string {
  if (status === 'CURRENT') return 'current'
  if (status === 'COMPLETED') return 'done'
  if (status === 'TIMEOUT' || status === 'SKIPPED') return 'bad'
  return ''
}

function shortId(id: string): string {
  return id.length > 12 ? `${id.slice(0, 12)}…` : id
}

async function load(showLoading = false): Promise<void> {
  if (showLoading) loading.value = true
  try {
    summary.value = await dashboardApi.summary()
    error.value = null
  } catch (err) {
    error.value = err instanceof Error ? err.message : '仪表盘数据加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load(true)
  timer = window.setInterval(() => {
    void load()
  }, 5000)
})

onUnmounted(() => {
  if (timer !== null) window.clearInterval(timer)
})
</script>

<style scoped>
.station-value {
  font-size: 26px;
  letter-spacing: 0.02em;
}

.dashboard-main {
  grid-template-columns: minmax(0, 1.6fr) minmax(320px, 1fr);
  align-items: start;
}

.side-stack {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.session-banner {
  display: grid;
  grid-template-columns: 1fr 1.4fr 0.8fr 0.8fr;
}

.progress-text {
  font-size: 20px;
  margin-top: 2px;
}

.current-step-text {
  margin-top: 2px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.progress-thin {
  height: 4px;
  border-radius: 999px;
  background: #0a1728;
  margin: 12px 0 14px;
  overflow: hidden;
}

.progress-thin-fill {
  height: 100%;
  background: linear-gradient(90deg, #0ea5e9, #22d3ee);
  transition: width 0.4s ease;
}

.dashboard-steps {
  max-height: 330px;
  overflow-y: auto;
  padding-right: 4px;
}

.gesture-chip {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  color: #7dd3fc;
  background: rgba(56, 189, 248, 0.1);
  border: 1px solid rgba(56, 189, 248, 0.28);
}

.detection-meta {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 11px;
  color: var(--muted);
  flex-wrap: wrap;
}

.kv-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.kv-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  padding-bottom: 9px;
  border-bottom: 1px dashed var(--border-soft);
}
.kv-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}
.kv-key {
  color: var(--muted);
  font-size: 11px;
}
.kv-val {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-soft);
}

.panel-link {
  font-size: 12px;
  color: var(--accent);
  white-space: nowrap;
}

@media (max-width: 1200px) {
  .dashboard-main {
    grid-template-columns: minmax(0, 1fr);
  }
  .session-banner {
    grid-template-columns: 1fr 1fr;
    row-gap: 12px;
  }
}
</style>
