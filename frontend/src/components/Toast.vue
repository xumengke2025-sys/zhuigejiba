<template>
  <Teleport to="body">
    <TransitionGroup 
      name="toast" 
      tag="div" 
      class="toast-container"
    >
      <div 
        v-for="toast in toasts" 
        :key="toast.id"
        class="toast-item"
        :class="[`toast-${toast.type}`, { 'toast-closable': toast.closable }]"
      >
        <div class="toast-icon">
          <!-- Success -->
          <svg v-if="toast.type === 'success'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
            <polyline points="22 4 12 14.01 9 11.01"/>
          </svg>
          <!-- Error -->
          <svg v-else-if="toast.type === 'error'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="15" y1="9" x2="9" y2="15"/>
            <line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
          <!-- Warning -->
          <svg v-else-if="toast.type === 'warning'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          <!-- Info -->
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="16" x2="12" y2="12"/>
            <line x1="12" y1="8" x2="12.01" y2="8"/>
          </svg>
        </div>
        
        <div class="toast-content">
          <div class="toast-message">{{ toast.message }}</div>
          <div v-if="toast.description" class="toast-description">{{ toast.description }}</div>
        </div>
        
        <button 
          v-if="toast.closable" 
          class="toast-close"
          @click="removeToast(toast.id)"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
    </TransitionGroup>
  </Teleport>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const toasts = ref([])

// 添加 Toast
const addToast = (options) => {
  const id = Date.now() + Math.random()
  const toast = {
    id,
    type: options.type || 'info',
    message: options.message || '',
    description: options.description || '',
    duration: options.duration ?? 3000,
    closable: options.closable ?? true
  }
  
  toasts.value.push(toast)
  
  // 自动消失
  if (toast.duration > 0) {
    setTimeout(() => {
      removeToast(id)
    }, toast.duration)
  }
  
  return id
}

// 移除 Toast
const removeToast = (id) => {
  const index = toasts.value.findIndex(t => t.id === id)
  if (index > -1) {
    toasts.value.splice(index, 1)
  }
}

// 清除所有
const clearAll = () => {
  toasts.value = []
}

// 全局事件监听
const handleToastEvent = (e) => {
  if (e.detail) {
    addToast(e.detail)
  }
}

onMounted(() => {
  window.addEventListener('app-toast', handleToastEvent)
})

onUnmounted(() => {
  window.removeEventListener('app-toast', handleToastEvent)
})

// 暴露方法
defineExpose({ addToast, removeToast, clearAll })
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 10000;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 400px;
  pointer-events: none;
}

.toast-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  border-left: 4px solid;
  pointer-events: auto;
  min-width: 300px;
}

/* 类型颜色 */
.toast-success {
  border-left-color: #52c41a;
}
.toast-success .toast-icon {
  color: #52c41a;
}

.toast-error {
  border-left-color: #ff4d4f;
}
.toast-error .toast-icon {
  color: #ff4d4f;
}

.toast-warning {
  border-left-color: #faad14;
}
.toast-warning .toast-icon {
  color: #faad14;
}

.toast-info {
  border-left-color: #1677ff;
}
.toast-info .toast-icon {
  color: #1677ff;
}

.toast-icon {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
}

.toast-icon svg {
  width: 100%;
  height: 100%;
}

.toast-content {
  flex: 1;
  min-width: 0;
}

.toast-message {
  font-size: 14px;
  font-weight: 500;
  color: #1f1f1f;
  line-height: 1.5;
  word-break: break-word;
}

.toast-description {
  margin-top: 4px;
  font-size: 13px;
  color: #666;
  line-height: 1.4;
}

.toast-close {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  padding: 0;
  border: none;
  background: transparent;
  color: #999;
  cursor: pointer;
  transition: color 0.2s;
}

.toast-close:hover {
  color: #333;
}

.toast-close svg {
  width: 100%;
  height: 100%;
}

/* 动画 */
.toast-enter-active {
  animation: toast-in 0.3s ease-out;
}

.toast-leave-active {
  animation: toast-out 0.25s ease-in forwards;
}

.toast-move {
  transition: transform 0.3s ease;
}

@keyframes toast-in {
  from {
    opacity: 0;
    transform: translateX(100%);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes toast-out {
  from {
    opacity: 1;
    transform: translateX(0);
  }
  to {
    opacity: 0;
    transform: translateX(100%);
  }
}
</style>
