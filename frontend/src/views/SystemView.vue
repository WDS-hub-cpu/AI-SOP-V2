<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>系统运行状态</h2>
        <p>后端服务、推理模型、摄像头、数据库与实时通道的实时健康信息。</p>
      </div>
      <div class="page-actions">
        <a class="console-link" :href="consoleUrl" target="_blank" rel="noopener">
          <el-icon><Monitor /></el-icon>
          后端控制台
        </a>
        <el-button :icon="Refresh" :loading="system.loading" @click="refreshAll">刷新</el-button>
        <el-button :icon="RefreshRight" :loading="reloading" @click="reloadModel">重新加载模型</el-button>
        <el-button :icon="VideoCamera" :loading="reconnecting" @click="reconnectCamera">重连摄像头</el-button>
      </div>
    </div>

    <el-alert
      v-if="!system.online"
      type="error"
      :closable="false"
      show-icon
      title="后端服务不可用"
      :description="system.error ?? '请启动后端：scripts\\start-backend.ps1'"
    />

    <el-alert
      v-if="status?.runtime.simulated"
      type="warning"
      :closable="false"
      show-icon
      title="系统当前处于模拟模式"
      description="检测器或摄像头为模拟来源，界面与数据均带 simulated 标记；不代表真实 AI 识别结果。"
    />

    <div class="grid cols-3">
      <section class="panel">
        <div class="panel-head">
          <div class="panel-title">后端服务</div>
          <el-tag :type="system.online ? 'success' : 'danger'" effect="dark" size="small">
            {{ system.online ? 'UP' : 'DOWN' }}
          </el-tag>
        </div>
        <div v-if="status" class="kv-list">
          <div class="kv-row"><span class="kv-key">版本</span><span class="kv-val mono">v{{ status.backend.version }}</span></div>
          <div class="kv-row"><span class="kv-key">运行环境</span><span class="kv-val">{{ status.backend.environment }}</span></div>
          <div class="kv-row"><span class="kv-key">启动时间</span><span class="kv-val mono">{{ formatDateTime(status.backend.started_at) }}</span></div>
          <div class="kv-row"><span class="kv-key">已运行</span><span class="kv-val">{{ formatDuration(status.backend.uptime_seconds) }}</span></div>
          <div class="kv-row"><span class="kv-key">进程 PID</span><span class="kv-val mono">{{ status.backend.pid }}</span></div>
          <div class="kv-row"><span class="kv-key">Python</span><span class="kv-val mono">{{ status.backend.python }}</span></div>
        </div>
        <div v-else class="empty-state">等待后端状态…</div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div class="panel-title">推理模型</div>
          <el-tag :type="modelTagType" effect="dark" size="small">
            {{ DETECTOR_STATUS_LABELS[status?.model.status ?? 'UNLOADED'] ?? '未知' }}
          </el-tag>
        </div>
        <div v-if="status" class="kv-list">
          <div class="kv-row"><span class="kv-key">检测器</span><span class="kv-val">{{ status.model.name }}</span></div>
          <div class="kv-row">
            <span class="kv-key">数据来源</span>
            <span class="kv-val" :class="status.model.simulated ? 'text-warn' : 'text-ok'">
              {{ status.model.simulated ? '模拟检测（非真实 AI）' : '真实 YOLO 推理' }}
            </span>
          </div>
          <div class="kv-row"><span class="kv-key">推理设备</span><span class="kv-val mono">{{ status.model.device ?? '—' }}</span></div>
          <div class="kv-row"><span class="kv-key">权重文件</span><span class="kv-val mono small">{{ status.model.model_path ?? '—' }}</span></div>
          <div class="kv-row"><span class="kv-key">类别数量</span><span class="kv-val mono">{{ status.model.class_count ?? '—' }}</span></div>
          <div class="kv-row"><span class="kv-key">置信度阈值</span><span class="kv-val mono">{{ status.model.confidence_threshold ?? '—' }}</span></div>
        </div>
        <div v-if="status?.model.mapped_classes?.length" class="class-tags">
          <el-tag v-for="name in status.model.mapped_classes" :key="name" size="small" effect="plain">
            {{ name }}
          </el-tag>
        </div>
        <el-alert
          v-if="status?.model.error"
          class="inline-alert"
          type="error"
          :closable="false"
          show-icon
          :title="status.model.error"
        />
        <div v-else-if="status && !status.model.weights_exist" class="inline-note">
          未发现模型权重。将训练好的 `.pt` 放入 `models/weights/` 并配置 `SOP_MODEL_PATH` 后，点击「重新加载模型」。
        </div>
        <div v-if="status?.model.selection_reason" class="inline-note muted">
          选择原因：{{ status.model.selection_reason }}
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div class="panel-title">摄像头</div>
          <el-tag :type="cameraTagType" effect="dark" size="small">
            {{ CAMERA_STATUS_LABELS[status?.camera.status ?? 'OFF'] ?? '未知' }}
          </el-tag>
        </div>
        <div v-if="status" class="kv-list">
          <div class="kv-row"><span class="kv-key">来源</span><span class="kv-val">{{ status.camera.source }}</span></div>
          <div class="kv-row">
            <span class="kv-key">画面类型</span>
            <span class="kv-val" :class="status.camera.simulated ? 'text-warn' : 'text-ok'">
              {{ status.camera.simulated ? '模拟画面' : '真实画面' }}
            </span>
          </div>
          <div class="kv-row"><span class="kv-key">分辨率</span><span class="kv-val mono">{{ status.camera.resolution }}</span></div>
          <div class="kv-row"><span class="kv-key">采集帧率</span><span class="kv-val mono">{{ status.camera.measured_fps.toFixed(1) }} / {{ status.camera.target_fps }} FPS</span></div>
          <div class="kv-row"><span class="kv-key">最后帧</span><span class="kv-val mono">{{ formatDateTime(status.camera.last_frame_at) }}</span></div>
          <div class="kv-row"><span class="kv-key">设备索引</span><span class="kv-val mono">{{ status.camera.index }}</span></div>
        </div>
        <div v-if="status" class="inline-note" :class="status.camera.connected ? '' : 'warn-text'">
          {{ status.camera.message }}
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div class="panel-title">数据库</div>
          <el-tag type="success" effect="dark" size="small">{{ status?.database.status ?? '—' }}</el-tag>
        </div>
        <div v-if="status" class="kv-list">
          <div class="kv-row"><span class="kv-key">类型</span><span class="kv-val">SQLite (WAL)</span></div>
          <div class="kv-row"><span class="kv-key">文件大小</span><span class="kv-val mono">{{ formatBytes(status.database.size_bytes) }}</span></div>
          <div class="kv-row"><span class="kv-key">路径</span><span class="kv-val mono small">{{ status.database.path }}</span></div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div class="panel-title">实时通道</div>
          <el-tag :type="monitor.connection === 'online' ? 'success' : 'warning'" effect="dark" size="small">
            {{ monitor.connection === 'online' ? 'WebSocket 在线' : '轮询降级' }}
          </el-tag>
        </div>
        <div v-if="status" class="kv-list">
          <div class="kv-row"><span class="kv-key">WS 客户端</span><span class="kv-val mono">{{ status.realtime.ws_clients }}</span></div>
          <div class="kv-row"><span class="kv-key">推送周期</span><span class="kv-val mono">{{ status.realtime.telemetry_interval_ms }} ms</span></div>
          <div class="kv-row"><span class="kv-key">运行时状态</span><span class="kv-val">{{ RUNTIME_LABELS[status.runtime.state] ?? status.runtime.state }}</span></div>
          <div class="kv-row"><span class="kv-key">实测推理帧率</span><span class="kv-val mono">{{ status.runtime.measured_fps.toFixed(1) }} FPS</span></div>
          <div class="kv-row"><span class="kv-key">最后检测</span><span class="kv-val mono">{{ formatDateTime(status.runtime.last_detection_at) }}</span></div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div class="panel-title">SOP 运行时</div>
          <el-tag v-if="status?.sop.pending_config" type="warning" effect="dark" size="small">配置待生效</el-tag>
          <el-tag v-else type="info" effect="plain" size="small">配置已生效</el-tag>
        </div>
        <div v-if="status" class="kv-list">
          <div class="kv-row"><span class="kv-key">工位</span><span class="kv-val">{{ status.sop.station_id }} · {{ status.sop.station_name }}</span></div>
          <div class="kv-row"><span class="kv-key">步骤总数</span><span class="kv-val mono">{{ status.sop.steps_total }}</span></div>
          <div class="kv-row"><span class="kv-key">启用步骤</span><span class="kv-val mono">{{ status.sop.enabled_steps }}</span></div>
          <div class="kv-row"><span class="kv-key">活动会话</span><span class="kv-val mono small">{{ status.sop.active_session_id ?? '无' }}</span></div>
          <div class="kv-row"><span class="kv-key">会话状态</span><span class="kv-val">{{ status.sop.session_status ?? '—' }}</span></div>
        </div>
        <div v-if="status?.sop.config_note" class="inline-note muted">{{ status.sop.config_note }}</div>
      </section>
    </div>

    <div class="grid cols-2 bottom-grid">
      <section class="panel">
        <div class="panel-head">
          <div>
            <div class="panel-title">最近错误日志</div>
            <div class="panel-sub">来自后端内存日志缓冲（WARNING 及以上）</div>
          </div>
          <el-button text size="small" :icon="Refresh" @click="loadLogs">刷新</el-button>
        </div>
        <el-table v-if="logs.length > 0" :data="logs" size="small" max-height="330">
          <el-table-column label="时间" width="142">
            <template #default="{ row }">
              <span class="mono">{{ formatDateTime(row.time) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="级别" width="82">
            <template #default="{ row }">
              <span :class="row.level === 'ERROR' || row.level === 'CRITICAL' ? 'text-danger' : 'text-warn'">
                {{ row.level }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="message" label="内容" min-width="260" show-overflow-tooltip />
        </el-table>
        <div v-else class="empty-state">暂无错误日志</div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div>
            <div class="panel-title">运行配置</div>
            <div class="panel-sub">敏感信息不会通过接口暴露</div>
          </div>
        </div>
        <div v-if="config" class="config-grid">
          <div v-for="item in configItems" :key="item.label" class="config-item">
            <span class="kv-key">{{ item.label }}</span>
            <span class="config-value mono">{{ item.value }}</span>
          </div>
        </div>
        <div v-else class="empty-state">配置加载中…</div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Monitor, Refresh, RefreshRight, VideoCamera } from '@element-plus/icons-vue'
import { systemApi } from '@/api'
import { useMonitorStore } from '@/stores/monitor'
import { useSystemStore } from '@/stores/system'
import type { ConfigInfo, LogItem } from '@/types'
import {
  CAMERA_STATUS_LABELS,
  DETECTOR_STATUS_LABELS,
  formatBytes,
  formatDateTime,
  formatDuration,
} from '@/utils/format'

const RUNTIME_LABELS: Record<string, string> = {
  IDLE: '待机',
  RUNNING: '运行中',
  DEGRADED: '降级运行',
  DISABLED: '已禁用',
}

const system = useSystemStore()
const monitor = useMonitorStore()
const consoleUrl = `${window.location.protocol}//${window.location.hostname}:8000/console`
const config = ref<ConfigInfo | null>(null)
const logs = ref<LogItem[]>([])
const reloading = ref(false)
const reconnecting = ref(false)

const status = computed(() => system.status)

const modelTagType = computed(() => {
  switch (status.value?.model.status) {
    case 'READY':
      return 'success'
    case 'MOCK':
      return 'warning'
    case 'ERROR':
      return 'danger'
    default:
      return 'info'
  }
})

const cameraTagType = computed(() => {
  switch (status.value?.camera.status) {
    case 'CONNECTED':
      return 'success'
    case 'SIMULATED':
    case 'DISCONNECTED':
      return 'warning'
    case 'ERROR':
      return 'danger'
    default:
      return 'info'
  }
})

const configItems = computed(() => {
  if (!config.value) return []
  const c = config.value
  return [
    { label: '工位', value: `${c.station_id} / ${c.station_name}` },
    { label: '推理模式', value: c.inference_mode },
    { label: '模型设备', value: c.model_device },
    { label: '置信度阈值', value: String(c.model_conf) },
    { label: '摄像头模式', value: c.camera_mode },
    { label: '摄像头索引', value: String(c.camera_index) },
    { label: '画面分辨率', value: c.camera_resolution },
    { label: '推理帧率', value: `${c.inference_fps} FPS` },
    { label: '稳定帧数', value: String(c.detection_stable_frames) },
    { label: '稳定重置', value: `${c.detection_reset_ms} ms` },
    { label: '错序判失败', value: c.fail_on_sequence_error ? '是' : '否' },
    { label: '超时判失败', value: c.fail_on_timeout ? '是' : '否' },
    { label: '会话最长时长', value: `${c.session_max_seconds} s` },
    { label: '自动开始会话', value: c.auto_start_session ? '是' : '否' },
    { label: '数据库', value: c.database_path },
    { label: '日志目录', value: c.log_dir },
  ]
})

async function loadConfig(): Promise<void> {
  try {
    config.value = await systemApi.config()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '配置加载失败')
  }
}

async function loadLogs(): Promise<void> {
  try {
    const data = await systemApi.logs(50)
    logs.value = data.items
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '日志加载失败')
  }
}

async function refreshAll(): Promise<void> {
  await Promise.all([system.refresh(), loadConfig(), loadLogs()])
}

async function reloadModel(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '将重新读取权重文件并初始化推理设备，期间检测会短暂停止。是否继续？',
      '重新加载模型',
      { type: 'warning', confirmButtonText: '重新加载', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  reloading.value = true
  try {
    const info = await systemApi.reloadModel()
    await system.refresh()
    if (info.status === 'ERROR') {
      ElMessage.warning(`模型加载失败：${info.error ?? '未知错误'}`)
    } else {
      ElMessage.success('模型已重新加载')
    }
    await loadLogs()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '模型重新加载失败')
  } finally {
    reloading.value = false
  }
}

async function reconnectCamera(): Promise<void> {
  reconnecting.value = true
  try {
    await systemApi.reconnectCamera()
    await system.refresh()
    ElMessage.success('摄像头已重新连接')
    await loadLogs()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '摄像头重连失败')
  } finally {
    reconnecting.value = false
  }
}

onMounted(() => {
  void refreshAll()
})
</script>

<style scoped>
.console-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 13px;
  border-radius: 6px;
  border: 1px solid rgba(34, 211, 238, 0.45);
  background: rgba(34, 211, 238, 0.08);
  color: #a5f3fc;
  font-size: 12px;
  white-space: nowrap;
}

.console-link:hover {
  border-color: rgba(34, 211, 238, 0.8);
  background: rgba(34, 211, 238, 0.14);
  color: #cffafe;
}

.kv-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.kv-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  font-size: 12px;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--border-soft);
}
.kv-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}
.kv-key {
  color: var(--muted);
  font-size: 11px;
  white-space: nowrap;
}
.kv-val {
  text-align: right;
  color: var(--text-soft);
  word-break: break-all;
}
.kv-val.small {
  font-size: 10px;
  max-width: 220px;
}

.class-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}

.inline-note {
  margin-top: 12px;
  padding: 9px 11px;
  border-radius: 8px;
  background: rgba(10, 21, 37, 0.65);
  border: 1px solid var(--border-soft);
  font-size: 11px;
  color: var(--text-soft);
  line-height: 1.55;
}
.inline-note.muted {
  color: var(--muted);
}
.inline-note.warn-text {
  color: #fbbf24;
  border-color: rgba(245, 158, 11, 0.35);
}

.inline-alert {
  margin-top: 12px;
}

.bottom-grid {
  align-items: start;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px 18px;
}

.config-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 11px;
  padding-bottom: 7px;
  border-bottom: 1px dashed var(--border-soft);
}

.config-value {
  color: var(--text-soft);
  text-align: right;
  word-break: break-all;
  font-size: 10px;
}

@media (max-width: 1100px) {
  .config-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
