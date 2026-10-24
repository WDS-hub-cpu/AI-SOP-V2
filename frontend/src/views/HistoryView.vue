<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>流程执行历史</h2>
        <p>查询会话级执行结果、步骤耗时与关联异常，数据来自 SQLite 持久化。</p>
      </div>
      <div class="page-actions">
        <el-tag type="info" effect="plain">共 {{ meta.total }} 个会话</el-tag>
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
        <el-select v-model="status" placeholder="会话状态" clearable style="width: 140px">
          <el-option label="执行中" value="RUNNING" />
          <el-option label="已完成" value="COMPLETED" />
          <el-option label="判定失败" value="FAILED" />
          <el-option label="已终止" value="ABORTED" />
        </el-select>
        <el-button :icon="RefreshLeft" @click="resetFilters">重置</el-button>
      </div>

      <el-table v-loading="loading" :data="items" size="small" row-key="id" style="margin-top: 14px">
        <el-table-column label="会话 ID" width="132">
          <template #default="{ row }">
            <span class="mono">{{ row.id.slice(0, 10) }}…</span>
          </template>
        </el-table-column>
        <el-table-column prop="station_id" label="工位" width="80" />
        <el-table-column label="开始时间" width="142">
          <template #default="{ row }">
            <span class="mono">{{ formatDateTime(row.started_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="结束时间" width="142">
          <template #default="{ row }">
            <span class="mono">{{ formatDateTime(row.finished_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="用时" width="92">
          <template #default="{ row }">{{ formatDuration(row.duration_seconds) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="92">
          <template #default="{ row }">
            <el-tag size="small" :type="sessionTagType(row.status)" effect="dark">
              {{ SESSION_STATUS_LABELS[row.status] ?? row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="步骤" width="80">
          <template #default="{ row }">
            <span class="mono">{{ row.completed_steps }}/{{ row.total_steps }}</span>
          </template>
        </el-table-column>
        <el-table-column label="异常" width="70">
          <template #default="{ row }">
            <span class="mono" :class="row.anomaly_count > 0 ? 'text-danger' : 'text-ok'">
              {{ row.anomaly_count }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="合规" width="82">
          <template #default="{ row }">
            <span v-if="row.compliance === null" class="text-muted">—</span>
            <el-tag v-else size="small" :type="row.compliance ? 'success' : 'danger'" effect="plain">
              {{ row.compliance ? '合规' : '不合规' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="触发" width="72">
          <template #default="{ row }">{{ row.trigger === 'manual' ? '手动' : '自动' }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="86" align="center">
          <template #default="{ row }">
            <el-button text size="small" type="primary" @click="openDetail(row)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && items.length === 0" class="empty-state">当前筛选条件下没有会话记录</div>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="meta.total"
        :page-sizes="[10, 15, 30, 50]"
        layout="total, sizes, prev, pager, next"
        background
        @current-change="load"
        @size-change="onSizeChange"
      />
    </section>

    <el-drawer v-model="drawerVisible" size="760px" :title="drawerTitle">
      <div v-loading="detailLoading" class="detail-wrap">
        <template v-if="detail">
          <div class="detail-grid">
            <div class="detail-item">
              <span class="kv-key">状态</span>
              <el-tag :type="sessionTagType(detail.session.status)" effect="dark" size="small">
                {{ SESSION_STATUS_LABELS[detail.session.status] ?? detail.session.status }}
              </el-tag>
            </div>
            <div class="detail-item">
              <span class="kv-key">合规判定</span>
              <el-tag
                v-if="detail.session.compliance !== null"
                :type="detail.session.compliance ? 'success' : 'danger'"
                effect="plain"
                size="small"
              >
                {{ detail.session.compliance ? '合规' : '不合规' }}
              </el-tag>
              <span v-else class="text-muted">未判定</span>
            </div>
            <div class="detail-item">
              <span class="kv-key">开始时间</span>
              <span class="mono">{{ formatDateTime(detail.session.started_at) }}</span>
            </div>
            <div class="detail-item">
              <span class="kv-key">结束时间</span>
              <span class="mono">{{ formatDateTime(detail.session.finished_at) }}</span>
            </div>
            <div class="detail-item">
              <span class="kv-key">总用时</span>
              <span>{{ formatDuration(detail.session.duration_seconds) }}</span>
            </div>
            <div class="detail-item">
              <span class="kv-key">步骤进度</span>
              <span class="mono">{{ detail.session.completed_steps }}/{{ detail.session.total_steps }}</span>
            </div>
            <div class="detail-item">
              <span class="kv-key">异常数量</span>
              <span class="mono" :class="detail.session.anomaly_count > 0 ? 'text-danger' : 'text-ok'">
                {{ detail.session.anomaly_count }}
              </span>
            </div>
            <div class="detail-item">
              <span class="kv-key">触发方式</span>
              <span>{{ detail.session.trigger === 'manual' ? '手动' : '自动' }}</span>
            </div>
          </div>

          <el-alert
            v-if="detail.session.end_reason"
            class="end-reason"
            type="info"
            :closable="false"
            show-icon
            :title="`结束原因：${detail.session.end_reason}`"
          />

          <h4 class="detail-title">步骤明细</h4>
          <el-table :data="detail.steps" size="small">
            <el-table-column label="#" width="52" align="center">
              <template #default="{ row }">
                <span class="mono">{{ row.step_order }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="step_name" label="步骤名称" min-width="140" />
            <el-table-column prop="gesture" label="手势" width="80" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="stepStatusTagType(row.status)" effect="plain">
                  {{ STEP_STATUS_LABELS[row.status] ?? row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="耗时" width="86">
              <template #default="{ row }">
                <span class="mono">{{ (row.duration_ms / 1000).toFixed(1) }}s</span>
              </template>
            </el-table-column>
            <el-table-column label="置信度" width="90">
              <template #default="{ row }">
                <span v-if="row.confidence !== null" class="mono">
                  {{ (row.confidence * 100).toFixed(1) }}%
                </span>
                <span v-else class="text-muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="完成时间" min-width="140">
              <template #default="{ row }">
                <span class="mono">{{ formatDateTime(row.finished_at) }}</span>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="detail.steps.length === 0" class="empty-state">没有步骤执行记录</div>

          <h4 class="detail-title">异常明细</h4>
          <el-table v-if="detail.events.length > 0" :data="detail.events" size="small">
            <el-table-column label="时间" width="142">
              <template #default="{ row }">
                <span class="mono">{{ formatDateTime(row.created_at) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="104">
              <template #default="{ row }">
                <el-tag size="small" :type="severityTagType(row.severity)" effect="plain">
                  {{ EVENT_TYPE_LABELS[row.event_type] ?? row.event_type }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="message" label="描述" min-width="220" show-overflow-tooltip />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="eventStatusTagType(row.status)" effect="dark">
                  {{ EVENT_STATUS_LABELS[row.status] ?? row.status }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="empty-state">该会话没有异常事件</div>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { Refresh, RefreshLeft } from '@element-plus/icons-vue'
import { historyApi } from '@/api'
import type { PageMeta, SessionDetail, SessionRecord } from '@/types'
import {
  EVENT_STATUS_LABELS,
  EVENT_TYPE_LABELS,
  SESSION_STATUS_LABELS,
  STEP_STATUS_LABELS,
  eventStatusTagType,
  formatDateTime,
  formatDuration,
  sessionTagType,
  severityTagType,
  stepStatusTagType,
} from '@/utils/format'

const items = ref<SessionRecord[]>([])
const meta = reactive<PageMeta>({ page: 1, page_size: 15, total: 0, pages: 0 })
const loading = ref(false)
const page = ref(1)
const pageSize = ref(15)
const status = ref<string>('')
const dateRange = ref<[string, string] | null>([
  dayjs().subtract(6, 'day').startOf('day').format('YYYY-MM-DDTHH:mm:ssZ'),
  dayjs().endOf('day').format('YYYY-MM-DDTHH:mm:ssZ'),
])

const drawerVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<SessionDetail | null>(null)

const drawerTitle = computed(() => {
  if (!detail.value) return '会话详情'
  return `会话详情 · ${detail.value.session.id.slice(0, 12)}…`
})

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await historyApi.sessions({
      page: page.value,
      page_size: pageSize.value,
      status: status.value || undefined,
      date_from: dateRange.value?.[0] || undefined,
      date_to: dateRange.value?.[1] || undefined,
    })
    items.value = data.items
    Object.assign(meta, data.meta)
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '历史记录加载失败')
  } finally {
    loading.value = false
  }
}

function resetFilters(): void {
  status.value = ''
  dateRange.value = [
    dayjs().subtract(6, 'day').startOf('day').format('YYYY-MM-DDTHH:mm:ssZ'),
    dayjs().endOf('day').format('YYYY-MM-DDTHH:mm:ssZ'),
  ]
  page.value = 1
  void load()
}

function onSizeChange(): void {
  page.value = 1
  void load()
}

async function openDetail(row: SessionRecord): Promise<void> {
  drawerVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await historyApi.detail(row.id)
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '会话详情加载失败')
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<style scoped>
.filters {
  gap: 10px;
}

.detail-wrap {
  min-height: 220px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 20px;
  padding: 14px;
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  background: rgba(10, 21, 37, 0.5);
}

.detail-item {
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

.end-reason {
  margin-top: 14px;
}

.detail-title {
  margin: 20px 0 10px;
  font-size: 13px;
  color: #cfe8ff;
  font-weight: 600;
  padding-left: 9px;
  border-left: 3px solid #22d3ee;
}

:deep(.el-drawer__body) {
  padding-top: 8px;
}

@media (max-width: 900px) {
  .detail-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
