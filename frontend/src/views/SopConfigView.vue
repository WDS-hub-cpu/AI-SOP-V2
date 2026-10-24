<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>SOP 步骤配置</h2>
        <p>配置由后端持久化并可热更新；规则判定不在前端执行。</p>
      </div>
      <div class="page-actions">
        <el-button :icon="RefreshLeft" :loading="loading" @click="resetDefaults">恢复默认</el-button>
        <el-button type="primary" :icon="Check" :loading="saving" :disabled="rows.length === 0" @click="save">
          保存配置
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="note"
      :type="pendingConfig ? 'warning' : 'success'"
      :closable="false"
      show-icon
      :title="pendingConfig ? '配置已保存，等待当前会话结束后生效' : '配置已生效'"
      :description="note"
    />

    <div class="sop-layout">
      <section class="panel">
        <div class="panel-head">
          <div>
            <div class="panel-title">步骤定义</div>
            <div class="panel-sub">共 {{ rows.length }} 个步骤，启用手势需唯一</div>
          </div>
          <el-button size="small" :icon="Plus" :disabled="rows.length >= 10" @click="addStep">新增步骤</el-button>
        </div>

        <el-table :data="rows" size="small" row-key="key" v-loading="loading">
          <el-table-column label="#" width="44" align="center">
            <template #default="{ $index }">
              <span class="mono order-badge">{{ $index + 1 }}</span>
            </template>
          </el-table-column>

          <el-table-column label="步骤名称" min-width="150">
            <template #default="{ row }">
              <el-input v-model="row.name" size="small" maxlength="64" placeholder="例如：扫码核对物料" />
            </template>
          </el-table-column>

          <el-table-column label="期望手势" width="126">
            <template #default="{ row }">
              <el-select v-model="row.expected_gesture" size="small" style="width: 100%">
                <el-option
                  v-for="gesture in gestureOptions"
                  :key="gesture.value"
                  :label="gesture.label"
                  :value="gesture.value"
                />
              </el-select>
            </template>
          </el-table-column>

          <el-table-column label="超时(秒)" width="88">
            <template #default="{ row }">
              <el-input-number
                v-model="row.timeout_seconds"
                size="small"
                :min="5"
                :max="600"
                :step="5"
                controls-position="right"
                style="width: 100%"
              />
            </template>
          </el-table-column>

          <el-table-column label="启用" width="54" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" size="small" />
            </template>
          </el-table-column>

          <el-table-column label="必做" width="54" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.required" size="small" :disabled="!row.enabled" />
            </template>
          </el-table-column>

          <el-table-column label="作业说明" min-width="220">
            <template #default="{ row }">
              <el-input v-model="row.description" size="small" maxlength="200" placeholder="可选，用于指导操作员" />
            </template>
          </el-table-column>

          <el-table-column label="操作" width="50" align="center">
            <template #default="{ $index }">
              <el-button
                text
                type="danger"
                :icon="Delete"
                :disabled="rows.length <= 1"
                @click="removeStep($index)"
              />
            </template>
          </el-table-column>
        </el-table>

        <div class="table-hint">
          <span><i class="dot ok"></i>顺序由行号自动维护，保存时会校验连续性与手势唯一性。</span>
          <span class="text-muted">最多 10 个步骤，至少启用 1 个。</span>
        </div>
      </section>

      <div class="grid cols-2">
        <section class="panel">
          <div class="panel-head">
            <div>
              <div class="panel-title">规则引擎策略</div>
              <div class="panel-sub">由后端环境变量控制</div>
            </div>
            <el-icon class="panel-icon"><InfoFilled /></el-icon>
          </div>
          <div v-if="config" class="kv-list">
            <div class="kv-row">
              <span class="kv-key">错序/漏步骤</span>
              <span class="kv-val" :class="config.fail_on_sequence_error ? 'text-danger' : 'text-warn'">
                {{ config.fail_on_sequence_error ? '立即判定失败' : '仅记录异常' }}
              </span>
            </div>
            <div class="kv-row">
              <span class="kv-key">步骤超时</span>
              <span class="kv-val" :class="config.fail_on_timeout ? 'text-danger' : 'text-warn'">
                {{ config.fail_on_timeout ? '立即判定失败' : '记录后继续' }}
              </span>
            </div>
            <div class="kv-row">
              <span class="kv-key">会话最大时长</span>
              <span class="kv-val mono">{{ config.session_max_seconds }} 秒</span>
            </div>
            <div class="kv-row">
              <span class="kv-key">自动开始会话</span>
              <span class="kv-val">{{ config.auto_start_session ? '开启' : '关闭' }}</span>
            </div>
            <div class="kv-row">
              <span class="kv-key">检测稳定帧</span>
              <span class="kv-val mono">{{ config.detection_stable_frames }} 帧</span>
            </div>
          </div>
          <div v-else class="empty-state">策略信息加载中…</div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div class="panel-title">判定规则说明</div>
          </div>
          <div class="rule-list">
            <div class="rule-item">
              <b>顺序执行</b>
              <span>只接受当前步骤对应的手势，完成后推进到下一步。</span>
            </div>
            <div class="rule-item">
              <b>漏步骤 / 错序</b>
              <span>检测到后续步骤手势时，当前步骤记为跳过并产生严重异常。</span>
            </div>
            <div class="rule-item">
              <b>重复步骤</b>
              <span>再次检测到已完成步骤手势，产生告警但不推进流程。</span>
            </div>
            <div class="rule-item">
              <b>超时</b>
              <span>步骤计时超过配置值，按策略判定失败或记录后继续。</span>
            </div>
            <div class="rule-item">
              <b>合规判定</b>
              <span>仅当会话正常完成且异常数为 0 时，判定为合规。</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Delete, InfoFilled, Plus, RefreshLeft } from '@element-plus/icons-vue'
import { sopApi, systemApi } from '@/api'
import type { ConfigInfo, SopStepConfig } from '@/types'

interface EditableStep extends SopStepConfig {
  key: number
}

const gestureOptions = [
  { value: 'ONE', label: '1 根手指 (ONE)' },
  { value: 'TWO', label: '2 根手指 (TWO)' },
  { value: 'THREE', label: '3 根手指 (THREE)' },
  { value: 'FOUR', label: '4 根手指 (FOUR)' },
  { value: 'FIVE', label: '5 根手指 (FIVE)' },
]

const rows = ref<EditableStep[]>([])
const config = ref<ConfigInfo | null>(null)
const loading = ref(false)
const saving = ref(false)
const note = ref('')
const pendingConfig = ref(false)
let keySeed = 1

function toEditable(items: SopStepConfig[]): EditableStep[] {
  return items
    .slice()
    .sort((a, b) => a.order - b.order)
    .map((item, index) => ({
      ...item,
      order: index + 1,
      key: keySeed++,
    }))
}

function nextGesture(): string {
  const used = new Set(rows.value.filter((row) => row.enabled).map((row) => row.expected_gesture))
  const available = gestureOptions.find((option) => !used.has(option.value))
  return available?.value ?? 'ONE'
}

function addStep(): void {
  if (rows.value.length >= 10) {
    ElMessage.warning('最多配置 10 个步骤')
    return
  }
  rows.value.push({
    key: keySeed++,
    order: rows.value.length + 1,
    name: `步骤 ${rows.value.length + 1}`,
    expected_gesture: nextGesture(),
    description: '',
    timeout_seconds: 20,
    enabled: true,
    required: true,
  })
}

function removeStep(index: number): void {
  if (rows.value.length <= 1) return
  rows.value.splice(index, 1)
  rows.value.forEach((row, i) => {
    row.order = i + 1
  })
}

function validate(): string | null {
  if (rows.value.length === 0) return '至少需要配置一个步骤'
  if (rows.value.some((row) => !row.name.trim())) return '步骤名称不能为空'
  const enabled = rows.value.filter((row) => row.enabled)
  if (enabled.length === 0) return '至少需要启用一个步骤'
  const gestures = enabled.map((row) => row.expected_gesture)
  const duplicates = gestures.filter((gesture, index) => gestures.indexOf(gesture) !== index)
  if (duplicates.length > 0) return `启用的步骤中手势重复：${[...new Set(duplicates)].join(', ')}`
  if (rows.value.some((row) => row.timeout_seconds < 5 || row.timeout_seconds > 600)) {
    return '超时时间必须在 5 ~ 600 秒之间'
  }
  return null
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const [list, cfg] = await Promise.all([sopApi.list(), systemApi.config()])
    rows.value = toEditable(list.items)
    note.value = list.note
    pendingConfig.value = list.pending_config
    config.value = cfg
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : 'SOP 配置加载失败')
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  const message = validate()
  if (message) {
    ElMessage.error(message)
    return
  }
  saving.value = true
  try {
    const payload: SopStepConfig[] = rows.value.map((row, index) => ({
      order: index + 1,
      name: row.name.trim(),
      expected_gesture: row.expected_gesture,
      description: row.description.trim(),
      timeout_seconds: row.timeout_seconds,
      enabled: row.enabled,
      required: row.required,
    }))
    const result = await sopApi.save(payload)
    rows.value = toEditable(result.items)
    note.value = result.note
    pendingConfig.value = result.pending_config
    if (result.pending_config) {
      ElMessage.warning(result.note)
    } else {
      ElMessage.success('SOP 配置已保存并生效')
    }
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function resetDefaults(): Promise<void> {
  try {
    await ElMessageBox.confirm('恢复为系统内置的五个手势步骤，当前配置将被覆盖。是否继续？', '恢复默认配置', {
      type: 'warning',
      confirmButtonText: '恢复默认',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  loading.value = true
  try {
    const result = await sopApi.reset()
    rows.value = toEditable(result.items)
    note.value = result.note
    pendingConfig.value = result.pending_config
    ElMessage.success('已恢复默认 SOP 配置')
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '恢复默认失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<style scoped>
.sop-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sop-layout .grid {
  align-items: start;
}

.order-badge {
  display: inline-grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: #122440;
  border: 1px solid var(--border);
  color: #9fb4cf;
  font-size: 12px;
}

.table-hint {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 12px;
  font-size: 11px;
  color: var(--muted);
}
.table-hint .dot {
  margin-right: 5px;
}

.kv-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.kv-row {
  display: flex;
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
  text-align: right;
}

.rule-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.rule-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding-left: 10px;
  border-left: 2px solid rgba(34, 211, 238, 0.35);
}
.rule-item b {
  font-size: 12px;
  color: #d8f7ff;
}
.rule-item span {
  font-size: 11px;
  color: var(--muted);
  line-height: 1.55;
}

.panel-icon {
  color: #7dd3fc;
  font-size: 18px;
}


</style>
