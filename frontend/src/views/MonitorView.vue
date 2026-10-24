<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>实时工位画面</h2>
        <p>
          {{ monitor.snapshot?.station.id ?? '—' }} ·
          {{ monitor.snapshot?.station.name ?? '等待连接' }}
          <span class="text-muted">· 视频由后端 MJPEG 推送，识别结果由后端规则引擎判定</span>
        </p>
      </div>
      <div class="page-actions">
        <span v-if="simulated" class="tag-sim">SIMULATION · 模拟检测</span>
        <el-tag :type="connectionTagType" effect="dark" size="small">
          {{ connectionLabel }}
        </el-tag>
        <el-button :icon="Refresh" @click="refreshAll">刷新</el-button>
      </div>
    </div>

    <el-alert
      v-if="monitor.connection !== 'online'"
      type="warning"
      :closable="false"
      show-icon
      title="实时通道未连接，已降级为 2.5 秒轮询"
      description="请检查后端 WebSocket 是否可用；页面数据仍会持续刷新。"
    />

    <div class="monitor-grid">
      <div class="left-stack">
        <section class="panel video-panel">
          <div class="video-shell">
            <img
              v-if="!videoError"
              :key="streamToken"
              class="video-feed"
              :src="streamUrl"
              alt="工位实时画面"
              @error="videoError = true"
            />
            <div v-else class="video-placeholder">
              <el-icon><VideoCamera /></el-icon>
              <span>{{ cameraMessage }}</span>
              <el-button size="small" :icon="RefreshRight" @click="retryVideo">重连画面</el-button>
            </div>

            <div class="video-overlay-top">
              <span class="badge-live"><i class="dot"></i>LIVE</span>
              <span v-if="cameraSimulated" class="tag-sim">SIMULATED FEED</span>
              <span v-else-if="cameraConnected" class="tag-live-ok">CAMERA ONLINE</span>
            </div>

            <div class="video-overlay-bottom">
              <span>
                识别动作：
                <b class="mono text-accent">{{ detection?.gesture ?? '—' }}</b>
                <span class="text-muted">
                  {{ detection?.gesture ? GESTURE_LABELS[detection.gesture] ?? '' : '未检测到' }}
                </span>
              </span>
              <span>
                置信度
                <b class="mono"> {{ detection ? (detection.confidence * 100).toFixed(1) : '0.0' }}%</b>
              </span>
              <span class="text-muted">
                推理 {{ detection ? detection.inference_ms.toFixed(1) : '0.0' }} ms
              </span>
            </div>
          </div>
          <div class="video-foot">
            <span>
              <i class="dot" :class="cameraConnected ? 'ok' : cameraSimulated ? 'warn' : 'danger'"></i>
              {{ cameraStatusText }}
            </span>
            <span class="mono">FPS {{ monitor.snapshot?.runtime.measured_fps?.toFixed(1) ?? '0.0' }}</span>
            <span class="mono">检测延迟 {{ monitor.snapshot?.runtime.inference_latency_ms?.toFixed(1) ?? '—' }} ms</span>
            <span class="spacer"></span>
            <span class="text-muted">会话 {{ sessionShortId }}</span>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <div class="panel-title">SOP 步骤执行</div>
              <div class="panel-sub">顺序与合规结果完全由后端状态机判定</div>
            </div>
            <div class="toolbar">
              <el-tag v-if="session" :type="sessionTagType(session.status)" effect="dark">
                {{ SESSION_STATUS_LABELS[session.status] ?? session.status }}
              </el-tag>
              <el-tag v-else type="info" effect="dark">空闲</el-tag>
            </div>
          </div>

          <div class="session-banner">
            <div>
              <div class="kv-key">进度</div>
              <div class="mono banner-value">
                {{ session?.completed_steps ?? 0 }}/{{ session?.total_steps ?? steps.length }}
              </div>
            </div>
            <div>
              <div class="kv-key">当前步骤</div>
              <div class="banner-step">{{ currentStep ? `${currentStep.order}. ${currentStep.name}` : '—' }}</div>
            </div>
            <div>
              <div class="kv-key">异常</div>
              <div class="mono banner-value" :class="(session?.anomaly_count ?? 0) > 0 ? 'text-danger' : 'text-ok'">
                {{ session?.anomaly_count ?? 0 }}
              </div>
            </div>
            <div>
              <div class="kv-key">合规判定</div>
              <div>
                <el-tag v-if="session?.compliance === null || session?.compliance === undefined" type="info" effect="plain" size="small">
                  判定中
                </el-tag>
                <el-tag v-else :type="session.compliance ? 'success' : 'danger'" effect="plain" size="small">
                  {{ session.compliance ? '合规' : '不合规' }}
                </el-tag>
              </div>
            </div>
          </div>

          <div v-if="currentStep" class="timeout-block">
            <div class="timeout-head">
              <span class="text-muted">步骤计时</span>
              <span class="mono" :class="currentStep.remaining_seconds <= 5 ? 'text-danger' : ''">
                {{ currentStep.elapsed_seconds.toFixed(1) }}s / {{ currentStep.timeout_seconds }}s
              </span>
            </div>
            <div class="timeout-track">
              <div
                class="timeout-fill"
                :class="{ danger: currentStep.remaining_seconds <= 5 }"
                :style="{ width: `${timeoutPercent}%` }"
              ></div>
            </div>
          </div>

          <div class="step-list">
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
                  <span class="text-muted gesture-label">{{ GESTURE_LABELS[step.gesture] ?? '' }}</span>
                </div>
                <div class="step-desc">{{ step.description || '—' }}</div>
              </div>
              <div class="step-side">
                <el-tag size="small" :type="stepStatusTagType(step.status)" effect="plain">
                  {{ STEP_STATUS_LABELS[step.status] ?? step.status }}
                </el-tag>
                <span v-if="step.duration_ms !== null" class="mono">
                  {{ (step.duration_ms / 1000).toFixed(1) }}s
                </span>
              </div>
            </div>
            <div v-if="steps.length === 0" class="empty-state">尚未配置可执行的 SOP 步骤</div>
          </div>
        </section>
      </div>

      <div class="right-stack">
        <section class="panel">
          <div class="panel-head">
            <div>
              <div class="panel-title">识别结果</div>
              <div class="panel-sub">{{ detection?.label ?? '等待模型输出' }}</div>
            </div>
            <span v-if="detection?.simulated" class="tag-sim">模拟</span>
          </div>
          <div class="gesture-block">
            <div class="gesture-value">{{ detection?.gesture ?? '—' }}</div>
            <div class="gesture-sub">
              {{ detection?.gesture ? GESTURE_LABELS[detection.gesture] ?? detection.gesture : '未检测到有效手势' }}
            </div>
          </div>
          <div class="conf-head">
            <span class="text-muted">模型置信度</span>
            <span class="mono">{{ detection ? (detection.confidence * 100).toFixed(1) : '0.0' }}%</span>
          </div>
          <div class="confidence-track">
            <div class="confidence-fill" :style="{ width: `${Math.min((detection?.confidence ?? 0) * 100, 100)}%` }"></div>
          </div>
          <div class="detect-meta">
            <span>更新时间 <b class="mono">{{ formatTime(detection?.at) }}</b></span>
            <span v-if="detection?.boxes.length">目标数 <b class="mono">{{ detection.boxes.length }}</b></span>
          </div>
          <el-alert
            v-if="detection?.simulated"
            class="sim-alert"
            type="warning"
            :closable="false"
            show-icon
            title="当前为模拟识别数据"
            description="未接入真实权重时，模拟检测器不读取画面内容，结果仅用于规则与联调演示。"
          />
        </section>

        <section class="panel">
          <div class="panel-head">
            <div class="panel-title">会话控制</div>
            <span class="mono text-muted">{{ sessionShortId }}</span>
          </div>
          <div class="session-info">
            <div class="kv-row">
              <span class="kv-key">状态</span>
              <span class="kv-val">{{ session ? SESSION_STATUS_LABELS[session.status] ?? session.status : '无活动会话' }}</span>
            </div>
            <div class="kv-row">
              <span class="kv-key">开始时间</span>
              <span class="kv-val mono">{{ formatDateTime(session?.started_at) }}</span>
            </div>
            <div class="kv-row">
              <span class="kv-key">触发方式</span>
              <span class="kv-val">{{ session?.trigger === 'manual' ? '手动' : session?.trigger === 'auto' ? '自动' : '—' }}</span>
            </div>
            <div class="kv-row">
              <span class="kv-key">结束原因</span>
              <span class="kv-val">{{ session?.end_reason ?? '—' }}</span>
            </div>
          </div>
          <div class="session-actions">
            <el-button
              v-if="!isRunning"
              type="primary"
              :icon="VideoPlay"
              :loading="actionLoading"
              @click="startSession"
            >
              开始新会话
            </el-button>
            <el-button
              v-else
              type="danger"
              plain
              :icon="VideoPause"
              :loading="actionLoading"
              @click="stopSession"
            >
              终止会话
            </el-button>
            <span class="text-muted hint">手动开始后，等待模拟/真实动作输入</span>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <div class="panel-title">规则演示（模拟模式）</div>
              <div class="panel-sub">直接向后端注入动作或场景，验证规则引擎</div>
            </div>
            <el-icon class="panel-icon"><MagicStick /></el-icon>
          </div>

          <template v-if="simulated">
            <div class="sim-row">
              <el-select v-model="gestureToInject" size="default" style="flex: 1">
                <el-option
                  v-for="gesture in gestureOptions"
                  :key="gesture"
                  :label="`${gesture} · ${GESTURE_LABELS[gesture]}`"
                  :value="gesture"
                />
              </el-select>
              <el-button :loading="simulationBusy" @click="injectGesture">注入手势</el-button>
            </div>
            <div class="sim-grid">
              <el-button size="small" :loading="simulationBusy" @click="runScenario('skip')">演示漏步骤</el-button>
              <el-button size="small" :loading="simulationBusy" @click="runScenario('repeat')">演示重复步骤</el-button>
              <el-button size="small" :loading="simulationBusy" @click="runScenario('wrong_order')">演示错误顺序</el-button>
              <el-button size="small" :loading="simulationBusy" @click="runScenario('timeout')">演示步骤超时</el-button>
              <el-button size="small" :loading="simulationBusy" @click="runScenario('reset')">重置模拟序列</el-button>
            </div>
            <el-alert
              class="sim-alert"
              type="info"
              :closable="false"
              title="注入动作会标记 simulated=true，仅用于演示后端规则，不代表真实识别。"
            />
          </template>
          <div v-else class="empty-state">
            当前为真实 YOLO 模型模式，模拟注入已禁用；请通过实际手势驱动流程。
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div class="panel-title">实时事件</div>
            <el-button text size="small" @click="monitor.clearEvents()">清空</el-button>
          </div>
          <div v-if="monitor.events.length" class="event-feed">
            <div v-for="event in monitor.events.slice(0, 8)" :key="event.id" class="feed-item">
              <div class="feed-top">
                <el-tag size="small" :type="severityTagType(event.severity)" effect="plain">
                  {{ EVENT_TYPE_LABELS[event.event_type] ?? event.event_type }}
                </el-tag>
                <span class="mono text-muted">{{ formatTime(event.created_at) }}</span>
              </div>
              <div class="feed-msg">{{ event.message }}</div>
            </div>
          </div>
          <div v-else class="empty-state">暂无实时事件</div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import {
  MagicStick,
  Refresh,
  RefreshRight,
  VideoCamera,
  VideoPause,
  VideoPlay,
} from '@element-plus/icons-vue'
import { monitorApi, systemApi } from '@/api'
import { useMonitorStore } from '@/stores/monitor'
import { useSystemStore } from '@/stores/system'
import type { SopEvent } from '@/types'
import {
  CAMERA_STATUS_LABELS,
  EVENT_TYPE_LABELS,
  GESTURE_LABELS,
  SESSION_STATUS_LABELS,
  STEP_STATUS_LABELS,
  formatDateTime,
  formatTime,
  sessionTagType,
  severityTagType,
  stepStatusTagType,
} from '@/utils/format'

const monitor = useMonitorStore()
const system = useSystemStore()

const streamToken = ref(Date.now())
const videoError = ref(false)
const actionLoading = ref(false)
const simulationBusy = ref(false)
const gestureToInject = ref<'ONE' | 'TWO' | 'THREE' | 'FOUR' | 'FIVE'>('ONE')
const gestureOptions = ['ONE', 'TWO', 'THREE', 'FOUR', 'FIVE'] as const
const seenEvents = new Set<number>()

const snapshot = computed(() => monitor.snapshot)
const session = computed(() => snapshot.value?.session ?? null)
const steps = computed(() => snapshot.value?.steps ?? [])
const currentStep = computed(() => snapshot.value?.current_step ?? null)
const detection = computed(() => snapshot.value?.detection ?? null)
const simulated = computed(() => snapshot.value?.runtime.simulated ?? system.simulated)
const isRunning = computed(() => session.value?.status === 'RUNNING')

const connectionLabel = computed(() => {
  if (monitor.connection === 'online') return '实时已连接'
  if (monitor.connection === 'connecting') return '连接中'
  return '实时断开'
})
const connectionTagType = computed(() =>
  monitor.connection === 'online' ? 'success' : monitor.connection === 'connecting' ? 'warning' : 'danger',
)

const cameraStatus = computed(() => system.status?.camera.status ?? 'OFF')
const cameraStatusText = computed(() => CAMERA_STATUS_LABELS[cameraStatus.value] ?? cameraStatus.value)
const cameraConnected = computed(() => cameraStatus.value === 'CONNECTED')
const cameraSimulated = computed(() => cameraStatus.value === 'SIMULATED')
const cameraMessage = computed(
  () => system.status?.camera.message ?? '摄像头不可用，请检查设备或切换到模拟画面',
)

const streamUrl = computed(() => monitorApi.streamUrl(streamToken.value))
const sessionShortId = computed(() => (session.value ? `${session.value.id.slice(0, 10)}…` : '—'))
const timeoutPercent = computed(() => {
  if (!currentStep.value || currentStep.value.timeout_seconds === 0) return 0
  return Math.min((currentStep.value.elapsed_seconds / currentStep.value.timeout_seconds) * 100, 100)
})

function stepClass(status: string): string {
  if (status === 'CURRENT') return 'current'
  if (status === 'COMPLETED') return 'done'
  if (status === 'TIMEOUT' || status === 'SKIPPED') return 'bad'
  return ''
}

function retryVideo(): void {
  videoError.value = false
  streamToken.value = Date.now()
  ElMessage.info('正在重新连接视频流…')
}

async function refreshAll(): Promise<void> {
  await Promise.all([monitor.refresh(), system.refresh()])
}

async function startSession(): Promise<void> {
  actionLoading.value = true
  try {
    await monitorApi.startSession()
    await monitor.refresh()
    ElMessage.success('已开始新的 SOP 会话')
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '开始会话失败')
  } finally {
    actionLoading.value = false
  }
}

async function stopSession(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '终止后当前会话会被判定为「已终止」，且计入异常统计。是否继续？',
      '终止会话',
      { type: 'warning', confirmButtonText: '终止', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  actionLoading.value = true
  try {
    await monitorApi.stopSession('操作员在监控页手动终止')
    await monitor.refresh()
    ElMessage.warning('会话已终止')
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '终止会话失败')
  } finally {
    actionLoading.value = false
  }
}

async function injectGesture(): Promise<void> {
  simulationBusy.value = true
  try {
    const result = await systemApi.simulate({ action: 'gesture', gesture: gestureToInject.value })
    ElMessage.success(result.message)
    await monitor.refresh()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '注入失败')
  } finally {
    simulationBusy.value = false
  }
}

async function runScenario(
  action: 'skip' | 'repeat' | 'wrong_order' | 'timeout' | 'reset',
): Promise<void> {
  simulationBusy.value = true
  try {
    const result = await systemApi.simulate({ action })
    ElMessage.success(result.message)
    await monitor.refresh()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '演示操作失败')
  } finally {
    simulationBusy.value = false
  }
}

watch(
  () => monitor.events,
  (list: SopEvent[]) => {
    for (const event of [...list].reverse()) {
      if (seenEvents.has(event.id)) continue
      seenEvents.add(event.id)
      if (event.severity === 'INFO') continue
      ElNotification({
        title: EVENT_TYPE_LABELS[event.event_type] ?? event.event_type,
        message: event.message,
        type: event.severity === 'CRITICAL' ? 'error' : 'warning',
        duration: 4500,
        position: 'bottom-right',
      })
    }
  },
)

watch(cameraStatus, (status) => {
  if (status === 'CONNECTED' || status === 'SIMULATED') {
    videoError.value = false
    streamToken.value = Date.now()
  }
})

onMounted(() => {
  void refreshAll()
})
</script>

<style scoped>
.left-stack,
.right-stack {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.video-panel {
  padding: 14px;
}

.video-foot {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 10px;
  font-size: 11px;
  color: var(--muted);
}

.video-foot .dot {
  margin-right: 4px;
}

.tag-live-ok {
  display: inline-flex;
  align-items: center;
  padding: 3px 9px;
  border-radius: 999px;
  border: 1px solid rgba(34, 197, 94, 0.4);
  background: rgba(34, 197, 94, 0.12);
  color: #86efac;
  font-size: 10px;
  letter-spacing: 0.12em;
}

.banner-value {
  font-size: 20px;
  margin-top: 2px;
}

.banner-step {
  margin-top: 2px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.timeout-block {
  margin-bottom: 14px;
}
.timeout-head {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  margin-bottom: 6px;
}
.timeout-track {
  height: 5px;
  border-radius: 999px;
  background: #0a1728;
  overflow: hidden;
}
.timeout-fill {
  height: 100%;
  background: linear-gradient(90deg, #0ea5e9, #22d3ee);
  transition: width 0.3s linear;
}
.timeout-fill.danger {
  background: linear-gradient(90deg, #f97316, #ef4444);
}

.gesture-block {
  padding: 6px 0 10px;
}
.gesture-sub {
  margin-top: 6px;
  color: var(--muted);
  font-size: 12px;
}
.conf-head {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  margin-bottom: 6px;
}
.detect-meta {
  display: flex;
  justify-content: space-between;
  margin-top: 10px;
  font-size: 11px;
  color: var(--muted);
}
.sim-alert {
  margin-top: 12px;
}

.session-info {
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.session-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 14px;
}
.session-actions .el-button {
  width: 100%;
  margin-left: 0;
}
.hint {
  font-size: 11px;
}

.sim-row {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.sim-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.sim-grid .el-button {
  margin-left: 0;
}

.panel-icon {
  color: #7dd3fc;
  font-size: 18px;
}

.event-feed {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 260px;
  overflow-y: auto;
}
.feed-item {
  padding: 9px 10px;
  border-radius: 8px;
  border: 1px solid var(--border-soft);
  background: rgba(10, 21, 37, 0.6);
}
.feed-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
}
.feed-msg {
  margin-top: 5px;
  font-size: 12px;
  color: var(--text-soft);
  line-height: 1.5;
}

.gesture-chip {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  color: #7dd3fc;
  background: rgba(56, 189, 248, 0.1);
  border: 1px solid rgba(56, 189, 248, 0.28);
}
.gesture-label {
  font-size: 10px;
}

.session-banner {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.kv-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
}
.kv-key {
  color: var(--muted);
  font-size: 11px;
}
.kv-val {
  color: var(--text-soft);
  text-align: right;
}

@media (max-width: 1280px) {
  .session-banner {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    row-gap: 12px;
  }
}
</style>
