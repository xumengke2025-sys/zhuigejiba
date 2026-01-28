/**
 * Toast 通知服务
 * 用法:
 *   import toast from '@/utils/toast'
 *   toast.success('操作成功')
 *   toast.error('操作失败', '请检查网络连接')
 */

// 触发 Toast 事件
const emit = (options) => {
  window.dispatchEvent(new CustomEvent('app-toast', { detail: options }))
}

const toast = {
  /**
   * 成功提示
   * @param {string} message - 消息内容
   * @param {string} description - 详细描述（可选）
   * @param {number} duration - 显示时长（毫秒），默认 3000
   */
  success(message, description = '', duration = 3000) {
    emit({ type: 'success', message, description, duration })
  },

  /**
   * 错误提示
   * @param {string} message - 错误消息
   * @param {string} description - 详细描述或解决方案（可选）
   * @param {number} duration - 显示时长（毫秒），默认 5000（错误提示停留更久）
   */
  error(message, description = '', duration = 5000) {
    emit({ type: 'error', message, description, duration })
  },

  /**
   * 警告提示
   * @param {string} message - 警告消息
   * @param {string} description - 详细描述（可选）
   * @param {number} duration - 显示时长（毫秒），默认 4000
   */
  warning(message, description = '', duration = 4000) {
    emit({ type: 'warning', message, description, duration })
  },

  /**
   * 信息提示
   * @param {string} message - 信息内容
   * @param {string} description - 详细描述（可选）
   * @param {number} duration - 显示时长（毫秒），默认 3000
   */
  info(message, description = '', duration = 3000) {
    emit({ type: 'info', message, description, duration })
  },

  /**
   * 自定义配置提示
   * @param {Object} options - 配置对象
   * @param {string} options.type - 类型: success/error/warning/info
   * @param {string} options.message - 消息内容
   * @param {string} options.description - 详细描述
   * @param {number} options.duration - 显示时长（毫秒），0 表示不自动关闭
   * @param {boolean} options.closable - 是否显示关闭按钮
   */
  show(options) {
    emit(options)
  },

  /**
   * 加载中提示（不自动关闭）
   * @param {string} message - 加载消息
   * @returns {Function} 关闭函数
   */
  loading(message) {
    const id = Date.now()
    emit({
      id,
      type: 'info',
      message,
      duration: 0,
      closable: false
    })
    // 返回关闭函数
    return () => {
      // 发送关闭事件
      window.dispatchEvent(new CustomEvent('app-toast-close', { detail: { id } }))
    }
  }
}

export default toast
