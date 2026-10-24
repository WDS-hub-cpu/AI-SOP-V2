import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: AppLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: '首页仪表盘', subtitle: '产线实时概览与今日合规指标' },
      },
      {
        path: 'monitor',
        name: 'monitor',
        component: () => import('@/views/MonitorView.vue'),
        meta: { title: '实时监控', subtitle: '视觉检测、SOP 步骤与合规状态' },
      },
      {
        path: 'sop',
        name: 'sop',
        component: () => import('@/views/SopConfigView.vue'),
        meta: { title: 'SOP 配置', subtitle: '步骤顺序、超时与启用策略' },
      },
      {
        path: 'events',
        name: 'events',
        component: () => import('@/views/EventsView.vue'),
        meta: { title: '异常记录', subtitle: '漏步骤、错序、重复与超时事件' },
      },
      {
        path: 'history',
        name: 'history',
        component: () => import('@/views/HistoryView.vue'),
        meta: { title: '历史记录', subtitle: '流程执行记录与异常明细' },
      },
      {
        path: 'system',
        name: 'system',
        component: () => import('@/views/SystemView.vue'),
        meta: { title: '系统状态', subtitle: '后端、模型、摄像头与日志' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.afterEach((to) => {
  const title = (to.meta.title as string | undefined) ?? '工业 AI SOP'
  document.title = `${title} · 工业 AI SOP 智能监控系统`
})

export default router
