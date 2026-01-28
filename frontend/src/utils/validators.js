/**
 * 表单验证工具
 * 提供通用的验证规则和实时验证功能
 */

// 验证结果类型
export const createValidationResult = (isValid, message = '') => ({
  isValid,
  message
})

// 内置验证规则
export const rules = {
  /**
   * 必填验证
   * @param {string} fieldName - 字段名称（用于错误消息）
   */
  required: (fieldName = '此字段') => (value) => {
    if (value === null || value === undefined || value === '') {
      return createValidationResult(false, `${fieldName}不能为空`)
    }
    if (Array.isArray(value) && value.length === 0) {
      return createValidationResult(false, `请至少选择一个${fieldName}`)
    }
    return createValidationResult(true)
  },

  /**
   * 最小长度验证
   * @param {number} min - 最小长度
   * @param {string} fieldName - 字段名称
   */
  minLength: (min, fieldName = '输入内容') => (value) => {
    if (!value || value.length < min) {
      return createValidationResult(false, `${fieldName}至少需要${min}个字符`)
    }
    return createValidationResult(true)
  },

  /**
   * 最大长度验证
   * @param {number} max - 最大长度
   * @param {string} fieldName - 字段名称
   */
  maxLength: (max, fieldName = '输入内容') => (value) => {
    if (value && value.length > max) {
      return createValidationResult(false, `${fieldName}不能超过${max}个字符`)
    }
    return createValidationResult(true)
  },

  /**
   * 数字范围验证
   * @param {number} min - 最小值
   * @param {number} max - 最大值
   * @param {string} fieldName - 字段名称
   */
  numberRange: (min, max, fieldName = '数值') => (value) => {
    const num = Number(value)
    if (isNaN(num)) {
      return createValidationResult(false, `${fieldName}必须是数字`)
    }
    if (num < min || num > max) {
      return createValidationResult(false, `${fieldName}应在${min}到${max}之间`)
    }
    return createValidationResult(true)
  },

  /**
   * 整数验证
   * @param {string} fieldName - 字段名称
   */
  integer: (fieldName = '数值') => (value) => {
    if (value === '' || value === null || value === undefined) {
      return createValidationResult(true) // 空值由 required 规则处理
    }
    if (!Number.isInteger(Number(value))) {
      return createValidationResult(false, `${fieldName}必须是整数`)
    }
    return createValidationResult(true)
  },

  /**
   * 正数验证
   * @param {string} fieldName - 字段名称
   */
  positive: (fieldName = '数值') => (value) => {
    if (value === '' || value === null || value === undefined) {
      return createValidationResult(true)
    }
    if (Number(value) <= 0) {
      return createValidationResult(false, `${fieldName}必须大于0`)
    }
    return createValidationResult(true)
  },

  /**
   * 邮箱格式验证
   */
  email: () => (value) => {
    if (!value) return createValidationResult(true)
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(value)) {
      return createValidationResult(false, '请输入有效的邮箱地址')
    }
    return createValidationResult(true)
  },

  /**
   * URL 格式验证
   */
  url: () => (value) => {
    if (!value) return createValidationResult(true)
    try {
      new URL(value)
      return createValidationResult(true)
    } catch {
      return createValidationResult(false, '请输入有效的URL地址')
    }
  },

  /**
   * 正则表达式验证
   * @param {RegExp} pattern - 正则表达式
   * @param {string} message - 错误消息
   */
  pattern: (pattern, message = '格式不正确') => (value) => {
    if (!value) return createValidationResult(true)
    if (!pattern.test(value)) {
      return createValidationResult(false, message)
    }
    return createValidationResult(true)
  },

  /**
   * 文件类型验证
   * @param {string[]} allowedTypes - 允许的文件扩展名
   */
  fileType: (allowedTypes) => (files) => {
    if (!files || files.length === 0) return createValidationResult(true)
    
    const fileList = Array.isArray(files) ? files : [files]
    for (const file of fileList) {
      const ext = file.name.split('.').pop().toLowerCase()
      if (!allowedTypes.includes(ext)) {
        return createValidationResult(
          false, 
          `不支持的文件类型: .${ext}，请上传 ${allowedTypes.map(t => `.${t}`).join(', ')} 格式的文件`
        )
      }
    }
    return createValidationResult(true)
  },

  /**
   * 文件大小验证
   * @param {number} maxSizeBytes - 最大文件大小（字节）
   */
  fileSize: (maxSizeBytes) => (files) => {
    if (!files || files.length === 0) return createValidationResult(true)
    
    const fileList = Array.isArray(files) ? files : [files]
    const maxSizeMB = (maxSizeBytes / (1024 * 1024)).toFixed(1)
    
    for (const file of fileList) {
      if (file.size > maxSizeBytes) {
        const fileSizeMB = (file.size / (1024 * 1024)).toFixed(1)
        return createValidationResult(
          false,
          `文件 "${file.name}" 大小为 ${fileSizeMB}MB，超过最大限制 ${maxSizeMB}MB`
        )
      }
    }
    return createValidationResult(true)
  }
}

/**
 * 创建表单验证器
 * @param {Object} schema - 验证规则 schema
 * @returns {Object} 验证器对象
 * 
 * @example
 * const validator = createFormValidator({
 *   name: [rules.required('名称'), rules.maxLength(50, '名称')],
 *   age: [rules.required('年龄'), rules.numberRange(1, 150, '年龄')]
 * })
 * 
 * // 验证单个字段
 * const result = validator.validateField('name', 'John')
 * 
 * // 验证整个表单
 * const { isValid, errors } = validator.validateForm({ name: 'John', age: 25 })
 */
export function createFormValidator(schema) {
  return {
    /**
     * 验证单个字段
     * @param {string} fieldName - 字段名
     * @param {any} value - 字段值
     * @returns {Object} { isValid, message }
     */
    validateField(fieldName, value) {
      const fieldRules = schema[fieldName]
      if (!fieldRules || fieldRules.length === 0) {
        return createValidationResult(true)
      }

      for (const rule of fieldRules) {
        const result = rule(value)
        if (!result.isValid) {
          return result
        }
      }
      return createValidationResult(true)
    },

    /**
     * 验证整个表单
     * @param {Object} formData - 表单数据
     * @returns {Object} { isValid, errors }
     */
    validateForm(formData) {
      const errors = {}
      let isValid = true

      for (const fieldName of Object.keys(schema)) {
        const result = this.validateField(fieldName, formData[fieldName])
        if (!result.isValid) {
          errors[fieldName] = result.message
          isValid = false
        }
      }

      return { isValid, errors }
    },

    /**
     * 检查表单是否完整（所有必填字段都已填写）
     * @param {Object} formData - 表单数据
     * @returns {boolean}
     */
    isComplete(formData) {
      const { isValid } = this.validateForm(formData)
      return isValid
    }
  }
}

/**
 * 用于 Vue 组件的响应式表单验证 composable
 * @param {Object} schema - 验证规则
 * @param {Object} formData - 响应式表单数据 (ref 或 reactive)
 */
export function useFormValidation(schema, formData) {
  const validator = createFormValidator(schema)
  
  return {
    /**
     * 验证单个字段
     */
    validateField(fieldName) {
      const value = typeof formData.value !== 'undefined' 
        ? formData.value[fieldName] 
        : formData[fieldName]
      return validator.validateField(fieldName, value)
    },

    /**
     * 验证整个表单
     */
    validateForm() {
      const data = typeof formData.value !== 'undefined' 
        ? formData.value 
        : formData
      return validator.validateForm(data)
    },

    /**
     * 检查表单是否有效
     */
    isFormValid() {
      const { isValid } = this.validateForm()
      return isValid
    }
  }
}

export default {
  rules,
  createFormValidator,
  useFormValidation,
  createValidationResult
}
