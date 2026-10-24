<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>异常记录</h2>
        <p>记录由后端规则引擎生成，包含漏步骤、错序、重复、超时与流程终止。</p>
      </div>
      <div class="page-actions">
        <el-tag type="info" effect="plain">共 {{ meta.total }} 条</el-tag>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>

    <section class="panel">
      <div class="toolbar filters">
        <el-date-picker
          v-model="dateRange"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          value-format="YYYY-MM-DDTHH:mm:ssZ"
          style="width: 380px"
        />
        <el-select v-model="status" placeholder="处理状态" clearable style="width: 130px">
          <el-option label="待处理" value="OPEN" />
          <el-option label="已确认" value="ACKED" />
          <el-option label="已解决" value="RESOLVED" />
        </el-select>
        <el-select v-model="severity" placeholder="级别" clearable style="width: 120px">
          <el-option label="严重" value="CRITICAL" />
          <el-option label="告警" value="WARNING" />
        </el-select>
        <el-select v-model="eventType" placeholder="异常类型" clearable style="width: 150px">
          <el-option
            v-for="(label, value) in eventTypeOptions"
            :key="value"
            :label="label"
            :value="value"
          />
        </el-select>
        <el-switch v-model="includeInfo" active-text="包含流程事件" />
        <el-button :icon="RefreshLeft" @click="resetFilters">重置</el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="items"
        size="small"
        row-key="id"
        :row-class-name="rowClassName"
        style="margin-top: 14px"
      >
        <el-table-column label="事件时间" width="142">
          <template #default="{ row }">
            <span class="mono">{{ formatDateTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="station_id" label="工位" width="82" />
        <el-table-column label="异常类型" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="severityTagType(row.severity)" effect="plain">
              {{ EVENT_TYPE_LABELS[row.event_type] ?? row.event_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="级别" width="82">
          <template #default="{ row }">
            <span :class="row.severity === 'CRITICAL' ? 'text-danger' : row.severity === 'WARNING' ? 'text-warn' : 'text-muted'">
              {{ row.severity }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="当前步骤" width="130" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.step_order" class="mono">{{ row.step_order }}</span>
            <span v-if="row.step_name"> · {{ row.step_name }}</span>
            <span v-if="!row.step_order && !row.step_name" class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="描述" min-width="260" show-overflow-tooltip />
        <el-table-column label="处理状态" width="96">
          <template #default="{ row }">
            <el-tag size="small" :type="eventStatusTagType(row.status)" effect="dark">
              {{ EVENT_STATUS_LABELS[row.status] ?? row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="132" align="center">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'OPEN'"
              text
              size="small"
              :loading="handlingId === row.id"
              @click="updateStatus(row, 'ACKED')"
            >
              确认
            </el-button>
            <el-button
              v-if="row.status !== 'RESOLVED' && row.status !== 'CLOSED'"
              text
              size="small"
              type="success"
              :loading="handlingId === row.id"
              @click="updateStatus(row, 'RESOLVED')"
            >
              解决
            </el-button>
            <span v-if="row.status === 'RESOLVED' || row.status === 'CLOSED'" class="text-muted">
              已闭环
            </span>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && items.length === 0" class="empty-state">当前筛选条件下没有异常记录</div>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="meta.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        background
        @current-change="load"
        @size-change="onSizeChange"
      />
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { Refresh, RefreshLeft } from '@element-plus/icons-vue'
import { eventsApi } from '@/api'
import type { PageMeta, SopEvent } from '@/types'
import {
  EVENT_STATUS_LABELS,
  EVENT_TYPE_LABELS,
  eventStatusTagType,
  formatDateTime,
  severityTagType,
} from '@/utils/format'

const items = ref<SopEvent[]>([])
const meta = reactive<PageMeta>({ page: 1, page_size: 20, total: 0, pages: 0 })
const loading = ref(false)
const handlingId = ref<number | null>(null)

const page = ref(1)
const pageSize = ref(20)
const status = ref<string>('')
const severity = ref<string>('')
const eventType = ref<string>('')
const includeInfo = ref(false)
const dateRange = ref<[string, string] | null>([
  dayjs().startOf('day').format('YYYY-MM-DDTHH:mm:ssZ'),
  dayjs().endOf('day').format('YYYY-MM-DDTHH:mm:ssZ'),
])

const eventTypeOptions: Record<string, string> = {
  SKIPPED_STEP: '漏步骤',
  REPEATED_STEP: '重复步骤',
  ORDER_ERROR: '顺序错误',
  STEP_TIMEOUT: '步骤超时',
  SESSION_TIMEOUT: '流程超时',
  SESSION_ABORTED: '流程终止',
  FLOW_FAILED: '流程失败',
}

let timer: number | null = null

function rowClassName({ row }: { row: SopEvent }): string {
  return row.severity === 'CRITICAL' && row.status === 'OPEN' ? 'critical-row' : ''
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await eventsApi.list({
      page: page.value,
      page_size: pageSize.value,
      status: status.value || undefined,
      severity: severity.value || undefined,
      event_type: eventType.value || undefined,
      include_info: includeInfo.value,
      date_from: dateRange.value?.[0] || undefined,
      date_to: dateRange.value?.[1] || undefined,
    })
    items.value = data.items
    Object.assign(meta, data.meta)
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '异常记录加载失败')
  } finally {
    loading.value = false
  }
}

function resetFilters(): void {
  status.value = ''
  severity.value = ''
  eventType.value = ''
  includeInfo.value = false
  dateRange.value = [
    dayjs().startOf('day').format('YYYY-MM-DDTHH:mm:ssZ'),
    dayjs().endOf('day').format('YYYY-MM-DDTHH:mm:ssZ'),
  ]
  page.value = 1
  void load()
}

function onSizeChange(): void {
  page.value = 1
  void load()
}

async function updateStatus(row: SopEvent, next: 'ACKED' | 'RESOLVED'): Promise<void> {
  handlingId.value = row.id
  try {
    await eventsApi.updateStatus(row.id, next)
    ElMessage.success(next === 'ACKED' ? '异常已确认' : '异常已解决')
    await load()
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '更新处理状态失败')
  } finally {
    handlingId.value = null
  }
}

onMounted(() => {
  void load()
  timer = window.setInterval(() => {
    void load()
  }, 15000)
})

onUnmounted(() => {
  if (timer !== null) window.clearInterval(timer)
})
</script>

<style scoped>
.filters {
  gap: 10px;
}
.filters :deep(.el-date-editor) {
  max-width: 100%;
}

:deep(.critical-row) {
  background: rgba(239, 68, 68, 0.06);
}

@media (max-width: 900px) {
  .filters :deep(.el-date-editor) {
    width: 100% !important;
  }
}
</style>
