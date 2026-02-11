<template>
  <div class="progress-wrapper" :class="[`progress-${status}`, { 'has-steps': steps.length > 0 }]">
    <!-- 步骤指示器 -->
    <div v-if="steps.length > 0" class="step-indicators">
      <div 
        v-for="(step, index) in steps" 
        :key="index"
        class="step-item"
        :class="{ 
          'completed': index < currentStep,
          'active': index === currentStep,
          'pending': index > currentStep
        }"
      >
        <div class="step-dot">
          <svg v-if="index < currentStep" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          <span v-else>{{ index + 1 }}</span>
        </div>
        <span class="step-label">{{ step }}</span>
      </div>
    </div>

    <!-- 进度条 -->
    <div class="progress-bar-container">
      <div class="progress-bar">
        <div 
          class="progress-fill" 
          :class="{ 'striped': showStripes && status === 'processing' }"
          :style="{ width: `${clampedProgress}%` }"
        />
      </div>
      
      <!-- 进度信息 -->
      <div class="progress-info">
        <span class="progress-message" v-if="message">{{ message }}</span>
        <span class="progress-stats">
          <span class="progress-percent">{{ Math.round(clampedProgress) }}%</span>
          <span v-if="showTime && estimatedTime" class="progress-time">
            预计剩余 {{ formatTime(estimatedTime) }}
          </span>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  // 进度值 0-100
  progress: {
    type: Number,
    default: 0
  },
  // 状态: processing | completed | error | paused
  status: {
    type: String,
    default: 'processing'
  },
  // 消息文本
  message: {
    type: String,
    default: ''
  },
  // 步骤列表
  steps: {
    type: Array,
    default: () => []
  },
  // 当前步骤索引
  currentStep: {
    type: Number,
    default: 0
  },
  // 是否显示条纹动画
  showStripes: {
    type: Boolean,
    default: true
  },
  // 是否显示预估时间
  showTime: {
    type: Boolean,
    default: false
  },
  // 预估剩余时间（秒）
  estimatedTime: {
    type: Number,
    default: 0
  }
})

// 限制进度值在 0-100 之间
const clampedProgress = computed(() => {
  return Math.min(100, Math.max(0, props.progress))
})

// 格式化时间
const formatTime = (seconds) => {
  if (seconds < 60) {
    return `${Math.round(seconds)}秒`
  } else if (seconds < 3600) {
    const mins = Math.floor(seconds / 60)
    const secs = Math.round(seconds % 60)
    return secs > 0 ? `${mins}分${secs}秒` : `${mins}分钟`
  } else {
    const hours = Math.floor(seconds / 3600)
    const mins = Math.round((seconds % 3600) / 60)
    return mins > 0 ? `${hours}小时${mins}分` : `${hours}小时`
  }
}
</script>

<style scoped>
.progress-wrapper {
  width: 100%;
}

/* 步骤指示器 */
.step-indicators {
  display: flex;
  justify-content: space-between;
  margin-bottom: 16px;
  position: relative;
}

.step-indicators::before {
  content: '';
  position: absolute;
  top: 14px;
  left: 28px;
  right: 28px;
  height: 2px;
  background: #E8E8E8;
  z-index: 0;
}

.step-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  position: relative;
  z-index: 1;
}

.step-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  background: #fff;
  border: 2px solid #E8E8E8;
  color: #999;
  transition: all 0.3s ease;
}

.step-dot svg {
  width: 14px;
  height: 14px;
}

.step-item.completed .step-dot {
  background: #52c41a;
  border-color: #52c41a;
  color: #fff;
}

.step-item.active .step-dot {
  background: #1677ff;
  border-color: #1677ff;
  color: #fff;
  box-shadow: 0 0 0 4px rgba(22, 119, 255, 0.2);
}

.step-label {
  font-size: 12px;
  color: #999;
  white-space: nowrap;
}

.step-item.completed .step-label,
.step-item.active .step-label {
  color: #333;
  font-weight: 500;
}

/* 进度条 */
.progress-bar-container {
  width: 100%;
}

.progress-bar {
  height: 8px;
  background: #F0F0F0;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
  background: #1677ff;
}

/* 状态颜色 */
.progress-processing .progress-fill {
  background: linear-gradient(90deg, #1677ff, #4096ff);
}

.progress-completed .progress-fill {
  background: linear-gradient(90deg, #52c41a, #73d13d);
}

.progress-error .progress-fill {
  background: linear-gradient(90deg, #ff4d4f, #ff7875);
}

.progress-paused .progress-fill {
  background: linear-gradient(90deg, #faad14, #ffc53d);
}

/* 条纹动画 */
.progress-fill.striped {
  background-image: linear-gradient(
    45deg,
    rgba(255, 255, 255, 0.15) 25%,
    transparent 25%,
    transparent 50%,
    rgba(255, 255, 255, 0.15) 50%,
    rgba(255, 255, 255, 0.15) 75%,
    transparent 75%,
    transparent
  );
  background-size: 20px 20px;
  animation: stripe-move 1s linear infinite;
}

@keyframes stripe-move {
  0% {
    background-position: 0 0;
  }
  100% {
    background-position: 20px 0;
  }
}

/* 进度信息 */
.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  font-size: 13px;
}

.progress-message {
  color: #666;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-right: 12px;
}

.progress-stats {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.progress-percent {
  font-weight: 600;
  color: #1677ff;
  font-family: 'Consolas', 'Monaco', monospace;
}

.progress-completed .progress-percent {
  color: #52c41a;
}

.progress-error .progress-percent {
  color: #ff4d4f;
}

.progress-time {
  color: #999;
  font-size: 12px;
}
</style>
