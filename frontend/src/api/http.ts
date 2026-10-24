import axios, { type AxiosRequestConfig } from 'axios'
import type { ApiEnvelope } from '@/types'

export class ApiError extends Error {
  code: number
  requestId: string | null

  constructor(message: string, code: number, requestId: string | null = null) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.requestId = requestId
  }
}

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 20000,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.response.use(
  (response) => {
    const body = response.data as ApiEnvelope<unknown>
    if (body && typeof body === 'object' && typeof body.code === 'number') {
      if (body.code !== 0) {
        throw new ApiError(body.message || '请求失败', body.code, body.request_id ?? null)
      }
      response.data = body.data
    }
    return response
  },
  (error) => {
    if (axios.isAxiosError(error)) {
      if (error.code === 'ECONNABORTED') {
        return Promise.reject(new ApiError('请求超时，请检查后端服务是否正常', 40800))
      }
      const body = error.response?.data as Partial<ApiEnvelope<unknown>> | undefined
      if (body?.message) {
        return Promise.reject(
          new ApiError(body.message, body.code ?? error.response?.status ?? 50000, body.request_id ?? null),
        )
      }
      if (!error.response) {
        return Promise.reject(new ApiError('无法连接后端服务（http://127.0.0.1:8000）', 50300))
      }
      return Promise.reject(
        new ApiError(`请求失败（HTTP ${error.response.status}）`, error.response.status * 100),
      )
    }
    return Promise.reject(error)
  },
)

export async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const response = await client.get(url, { params })
  return response.data as T
}

export async function post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  const response = await client.post(url, data, config)
  return response.data as T
}

export async function put<T>(url: string, data?: unknown): Promise<T> {
  const response = await client.put(url, data)
  return response.data as T
}

export default client
