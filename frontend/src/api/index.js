import axios from 'axios'
import { handleAxiosError } from '../utils/errorHandler'
import toast from '../utils/toast'

// 创建axios实例
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 300000, // 5分钟超时（本体生成可能需要较长时间）
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
service.interceptors.request.use(
  config => {
    // 添加请求时间戳用于性能监控
    config.metadata = { startTime: Date.now() }
    return config
  },
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器（增强错误处理）
service.interceptors.response.use(
  response => {
    const res = response.data
    
    // 记录请求耗时
    const duration = Date.now() - (response.config.metadata?.startTime || Date.now())
    if (duration > 5000) {
      console.warn(`Slow API request: ${response.config.url} took ${duration}ms`)
    }
    
    // 如果返回的状态码不是success，则处理错误
    if (!res.success && res.success !== undefined) {
      const errorMsg = res.error || res.message || '操作失败'
      console.error('API Error:', errorMsg)
      
      // 自动显示错误提示（可通过 config.skipErrorToast 跳过）
      if (!response.config.skipErrorToast) {
        toast.error(errorMsg, res.suggestion || '')
      }
      
      return Promise.reject(new Error(errorMsg))
    }
    
    return res
  },
  error => {
    console.error('Response error:', error)
    
    // 使用统一错误处理，但允许调用方通过 config 控制是否显示 Toast
    const showToast = !error.config?.skipErrorToast
    handleAxiosError(error, { showToast })
    
    return Promise.reject(error)
  }
)

// 带重试的请求函数（增强版）
export const requestWithRetry = async (requestFn, options = {}) => {
  const { 
    maxRetries = 3, 
    delay = 1000,
    showRetryToast = true,
    retryCondition = (error) => {
      // 默认只重试网络错误和超时
      return error.message === 'Network Error' || 
             error.code === 'ECONNABORTED' ||
             (error.response?.status >= 500)
    }
  } = options
  
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn()
    } catch (error) {
      // 检查是否满足重试条件
      if (!retryCondition(error)) {
        throw error
      }
      
      if (i === maxRetries - 1) throw error
      
      const retryNum = i + 1
      console.warn(`Request failed, retrying (${retryNum}/${maxRetries})...`)
      
      if (showRetryToast) {
        toast.warning(`请求失败，正在重试 (${retryNum}/${maxRetries})...`)
      }
      
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
}

// 创建一个静默请求实例（不自动显示错误提示）
export const silentRequest = (config) => {
  return service({ ...config, skipErrorToast: true })
}

export default service
