/**
 * 统一错误处理工具
 * 根据错误类型生成用户友好消息，并提供解决方案建议
 */
import toast from './toast'

// HTTP 状态码映射
const HTTP_ERROR_MESSAGES = {
  400: { message: '请求参数错误', suggestion: '请检查输入数据是否正确' },
  401: { message: '未授权访问', suggestion: '请重新登录后重试' },
  403: { message: '访问被拒绝', suggestion: '您没有权限执行此操作' },
  404: { message: '请求的资源不存在', suggestion: '请检查请求地址是否正确' },
  408: { message: '请求超时', suggestion: '请检查网络连接后重试' },
  409: { message: '资源冲突', suggestion: '请刷新页面后重试' },
  422: { message: '数据验证失败', suggestion: '请检查输入数据格式' },
  429: { message: '请求过于频繁', suggestion: '请稍后再试' },
  500: { message: '服务器内部错误', suggestion: '请稍后重试，或联系管理员' },
  502: { message: '网关错误', suggestion: '后端服务可能暂时不可用' },
  503: { message: '服务暂不可用', suggestion: '请稍后重试' },
  504: { message: '网关超时', suggestion: '请检查网络连接后重试' }
}

// 业务错误码映射（根据后端返回的 error_code）
const BUSINESS_ERROR_MESSAGES = {
  'PROJECT_NOT_FOUND': { message: '项目不存在', suggestion: '请检查项目ID是否正确' },
  'GRAPH_BUILD_FAILED': { message: '图谱构建失败', suggestion: '请检查文档格式是否正确' },
  'ONTOLOGY_GENERATION_FAILED': { message: '本体生成失败', suggestion: '请检查文档内容是否完整' },
  'SIMULATION_FAILED': { message: '模拟运行失败', suggestion: '请检查配置参数是否正确' },
  'LLM_API_ERROR': { message: 'AI 服务调用失败', suggestion: '请稍后重试' },
  'NEO4J_CONNECTION_ERROR': { message: '数据库连接失败', suggestion: '请检查数据库服务状态' },
  'FILE_PARSE_ERROR': { message: '文件解析失败', suggestion: '请确保文件格式正确（支持 PDF、Word、TXT）' },
  'INVALID_CONFIG': { message: '配置无效', suggestion: '请检查配置参数' }
}

/**
 * 处理 Axios 错误
 * @param {Error} error - Axios 错误对象
 * @param {Object} options - 配置选项
 * @param {boolean} options.showToast - 是否显示 Toast 提示，默认 true
 * @param {boolean} options.silent - 静默模式，不显示任何提示
 * @returns {Object} 格式化后的错误信息 { message, suggestion, code }
 */
export function handleAxiosError(error, options = {}) {
  const { showToast = true, silent = false } = options
  let result = {
    message: '未知错误',
    suggestion: '请稍后重试',
    code: null,
    originalError: error
  }

  // 网络错误
  if (error.message === 'Network Error') {
    result = {
      ...result,
      message: '网络连接失败',
      suggestion: '请检查网络连接，确保后端服务正在运行',
      code: 'NETWORK_ERROR'
    }
  }
  // 超时错误
  else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
    result = {
      ...result,
      message: '请求超时',
      suggestion: '操作耗时较长，请耐心等待或稍后重试',
      code: 'TIMEOUT'
    }
  }
  // HTTP 响应错误
  else if (error.response) {
    const { status, data } = error.response
    result.code = status

    // 优先使用后端返回的错误信息
    if (data?.error) {
      result.message = data.error
      
      // 检查是否有业务错误码
      if (data.error_code && BUSINESS_ERROR_MESSAGES[data.error_code]) {
        const businessError = BUSINESS_ERROR_MESSAGES[data.error_code]
        result.suggestion = businessError.suggestion
      }
    }
    // 使用 HTTP 状态码映射
    else if (HTTP_ERROR_MESSAGES[status]) {
      const httpError = HTTP_ERROR_MESSAGES[status]
      result.message = httpError.message
      result.suggestion = httpError.suggestion
    }

    // 补充后端返回的详细信息
    if (data?.detail) {
      result.suggestion = data.detail
    }
  }
  // 请求配置错误
  else if (error.request) {
    result = {
      ...result,
      message: '请求发送失败',
      suggestion: '请检查网络连接',
      code: 'REQUEST_ERROR'
    }
  }

  // 显示 Toast 提示
  if (!silent && showToast) {
    toast.error(result.message, result.suggestion)
  }

  return result
}

/**
 * 处理业务逻辑错误（非 HTTP 错误）
 * @param {string} errorCode - 错误码
 * @param {string} fallbackMessage - 备用消息
 * @param {Object} options - 配置选项
 */
export function handleBusinessError(errorCode, fallbackMessage = '', options = {}) {
  const { showToast = true } = options
  
  let result = {
    message: fallbackMessage || '操作失败',
    suggestion: '请稍后重试',
    code: errorCode
  }

  if (BUSINESS_ERROR_MESSAGES[errorCode]) {
    const errorInfo = BUSINESS_ERROR_MESSAGES[errorCode]
    result.message = errorInfo.message
    result.suggestion = errorInfo.suggestion
  }

  if (showToast) {
    toast.error(result.message, result.suggestion)
  }

  return result
}

/**
 * 创建带重试机制的错误处理
 * @param {Function} fn - 要执行的异步函数
 * @param {Object} options - 配置选项
 * @param {number} options.maxRetries - 最大重试次数，默认 2
 * @param {number} options.retryDelay - 重试延迟（毫秒），默认 1000
 * @param {Function} options.onRetry - 重试时的回调
 */
export async function withRetry(fn, options = {}) {
  const { maxRetries = 2, retryDelay = 1000, onRetry } = options
  let lastError

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn()
    } catch (error) {
      lastError = error
      
      // 某些错误不应重试
      if (error.response?.status >= 400 && error.response?.status < 500) {
        throw error
      }

      if (attempt < maxRetries) {
        if (onRetry) {
          onRetry(attempt + 1, maxRetries)
        }
        await new Promise(resolve => setTimeout(resolve, retryDelay * (attempt + 1)))
      }
    }
  }

  throw lastError
}

export default {
  handleAxiosError,
  handleBusinessError,
  withRetry
}
