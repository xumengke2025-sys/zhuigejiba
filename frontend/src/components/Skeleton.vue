<template>
  <div class="skeleton-wrapper" :class="{ 'skeleton-animated': animated }">
    <!-- 卡片骨架 -->
    <template v-if="type === 'card'">
      <div class="skeleton-card" v-for="i in count" :key="i">
        <div class="skeleton-card-header">
          <div class="skeleton-avatar"></div>
          <div class="skeleton-title-group">
            <div class="skeleton-title"></div>
            <div class="skeleton-subtitle"></div>
          </div>
        </div>
        <div class="skeleton-card-body">
          <div class="skeleton-line" style="width: 100%"></div>
          <div class="skeleton-line" style="width: 80%"></div>
          <div class="skeleton-line" style="width: 60%"></div>
        </div>
      </div>
    </template>

    <!-- 列表骨架 -->
    <template v-else-if="type === 'list'">
      <div class="skeleton-list-item" v-for="i in count" :key="i">
        <div class="skeleton-bullet"></div>
        <div class="skeleton-list-content">
          <div class="skeleton-line" style="width: 70%"></div>
          <div class="skeleton-line short" style="width: 40%"></div>
        </div>
      </div>
    </template>

    <!-- 表格骨架 -->
    <template v-else-if="type === 'table'">
      <div class="skeleton-table">
        <div class="skeleton-table-header">
          <div class="skeleton-cell" v-for="i in columns" :key="'h'+i"></div>
        </div>
        <div class="skeleton-table-row" v-for="i in count" :key="i">
          <div class="skeleton-cell" v-for="j in columns" :key="'c'+j"></div>
        </div>
      </div>
    </template>

    <!-- 表单骨架 -->
    <template v-else-if="type === 'form'">
      <div class="skeleton-form-item" v-for="i in count" :key="i">
        <div class="skeleton-label"></div>
        <div class="skeleton-input"></div>
      </div>
      <div class="skeleton-form-actions">
        <div class="skeleton-button"></div>
      </div>
    </template>

    <!-- 图谱骨架 -->
    <template v-else-if="type === 'graph'">
      <div class="skeleton-graph">
        <div class="skeleton-graph-node" v-for="i in 5" :key="i" :style="getNodeStyle(i)"></div>
        <svg class="skeleton-graph-lines">
          <line x1="50%" y1="30%" x2="25%" y2="60%" />
          <line x1="50%" y1="30%" x2="75%" y2="60%" />
          <line x1="25%" y1="60%" x2="40%" y2="80%" />
          <line x1="75%" y1="60%" x2="60%" y2="80%" />
        </svg>
      </div>
    </template>

    <!-- 文本行骨架 -->
    <template v-else-if="type === 'text'">
      <div class="skeleton-text">
        <div class="skeleton-line" v-for="i in count" :key="i" :style="{ width: getLineWidth(i) }"></div>
      </div>
    </template>

    <!-- 默认/自定义骨架 -->
    <template v-else>
      <slot>
        <div class="skeleton-line" :style="{ width, height }"></div>
      </slot>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  // 骨架类型: card | list | table | form | graph | text | custom
  type: {
    type: String,
    default: 'text'
  },
  // 数量
  count: {
    type: Number,
    default: 3
  },
  // 表格列数
  columns: {
    type: Number,
    default: 4
  },
  // 是否动画
  animated: {
    type: Boolean,
    default: true
  },
  // 自定义宽度
  width: {
    type: String,
    default: '100%'
  },
  // 自定义高度
  height: {
    type: String,
    default: '20px'
  }
})

// 图谱节点位置
const getNodeStyle = (index) => {
  const positions = [
    { top: '20%', left: '50%' },
    { top: '50%', left: '20%' },
    { top: '50%', left: '80%' },
    { top: '80%', left: '35%' },
    { top: '80%', left: '65%' }
  ]
  return {
    top: positions[index - 1]?.top || '50%',
    left: positions[index - 1]?.left || '50%'
  }
}

// 文本行宽度
const getLineWidth = (index) => {
  const widths = ['100%', '90%', '95%', '75%', '85%', '60%']
  return widths[(index - 1) % widths.length]
}
</script>

<style scoped>
.skeleton-wrapper {
  width: 100%;
}

/* 基础骨架元素 */
.skeleton-line,
.skeleton-avatar,
.skeleton-title,
.skeleton-subtitle,
.skeleton-bullet,
.skeleton-cell,
.skeleton-label,
.skeleton-input,
.skeleton-button,
.skeleton-graph-node {
  background: linear-gradient(90deg, #f0f0f0 25%, #e8e8e8 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  border-radius: 4px;
}

/* 动画 */
.skeleton-animated .skeleton-line,
.skeleton-animated .skeleton-avatar,
.skeleton-animated .skeleton-title,
.skeleton-animated .skeleton-subtitle,
.skeleton-animated .skeleton-bullet,
.skeleton-animated .skeleton-cell,
.skeleton-animated .skeleton-label,
.skeleton-animated .skeleton-input,
.skeleton-animated .skeleton-button,
.skeleton-animated .skeleton-graph-node {
  animation: skeleton-pulse 1.5s ease-in-out infinite;
}

@keyframes skeleton-pulse {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

/* 文本行 */
.skeleton-line {
  height: 16px;
  margin-bottom: 12px;
}

.skeleton-line.short {
  height: 12px;
}

.skeleton-line:last-child {
  margin-bottom: 0;
}

/* 卡片骨架 */
.skeleton-card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  border: 1px solid #f0f0f0;
}

.skeleton-card:last-child {
  margin-bottom: 0;
}

.skeleton-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.skeleton-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  flex-shrink: 0;
}

.skeleton-title-group {
  flex: 1;
}

.skeleton-title {
  height: 18px;
  width: 60%;
  margin-bottom: 8px;
}

.skeleton-subtitle {
  height: 14px;
  width: 40%;
}

.skeleton-card-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* 列表骨架 */
.skeleton-list-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid #f5f5f5;
}

.skeleton-list-item:last-child {
  border-bottom: none;
}

.skeleton-bullet {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 4px;
  flex-shrink: 0;
}

.skeleton-list-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 表格骨架 */
.skeleton-table {
  width: 100%;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  overflow: hidden;
}

.skeleton-table-header {
  display: flex;
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;
}

.skeleton-table-row {
  display: flex;
  border-bottom: 1px solid #f5f5f5;
}

.skeleton-table-row:last-child {
  border-bottom: none;
}

.skeleton-cell {
  flex: 1;
  height: 20px;
  margin: 12px 16px;
}

.skeleton-table-header .skeleton-cell {
  height: 16px;
}

/* 表单骨架 */
.skeleton-form-item {
  margin-bottom: 20px;
}

.skeleton-label {
  height: 14px;
  width: 80px;
  margin-bottom: 8px;
}

.skeleton-input {
  height: 40px;
  width: 100%;
  border-radius: 6px;
}

.skeleton-form-actions {
  margin-top: 24px;
  display: flex;
  justify-content: flex-end;
}

.skeleton-button {
  height: 40px;
  width: 120px;
  border-radius: 6px;
}

/* 图谱骨架 */
.skeleton-graph {
  position: relative;
  width: 100%;
  height: 300px;
  background: #fafafa;
  border-radius: 8px;
}

.skeleton-graph-node {
  position: absolute;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  transform: translate(-50%, -50%);
}

.skeleton-graph-lines {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.skeleton-graph-lines line {
  stroke: #e8e8e8;
  stroke-width: 2;
}

/* 文本骨架 */
.skeleton-text {
  display: flex;
  flex-direction: column;
}
</style>
