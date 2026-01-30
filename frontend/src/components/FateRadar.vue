<template>
  <div class="radar-container" ref="container">
    <div class="radar-header">
      <div class="radar-legend">
        <div class="legend-item" title="标准：聚合 ≥6 位不同流派大师的共同推演结论">
          <span class="dot consensus"></span> 众师共识 <span class="info-icon">?</span>
        </div>
        <div class="legend-item" title="标准：单一大师的深度独家洞察">
          <span class="dot unique"></span> 独特视角 <span class="info-icon">?</span>
        </div>
        <div class="legend-item" title="标准：涉及重大转折或抉择的不确定性预测">
          <span class="dot variable"></span> 命理变数 <span class="info-icon">?</span>
        </div>
      </div>
      <div class="radar-controls">
        <button v-for="year in availableYears" 
                :key="year" 
                :class="['year-btn', { active: currentYear === year }]"
                @click="currentYear = year">
          {{ year }}
        </button>
      </div>
      <div class="radar-title">赛博天机仪 · 年度推演拟合</div>
    </div>
    
    <svg ref="svg" class="radar-svg" 
         :viewBox="viewBoxString" 
         preserveAspectRatio="xMidYMid meet" 
         @click="handleSvgClick"
         @wheel="handleWheel"
         @mousedown="startDrag"
         @mousemove="onDrag"
         @mouseup="stopDrag"
         @mouseleave="stopDrag">
      <defs>
        <!-- 基础发光 -->
        <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
        <!-- 强力核心发光 -->
        <filter id="sun-glow" x="-100%" y="-100%" width="300%" height="300%">
          <feGaussianBlur stdDeviation="15" result="blur" />
          <feColorMatrix type="matrix" values="0 0 0 0 1   0 0 0 0 0.8   0 0 0 0 0.2  0 0 0 1 0" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <!-- 扫描线渐变 -->
        <conicGradient id="radarSweep" cx="50%" cy="50%">
          <stop offset="0%" stop-color="rgba(255, 215, 0, 0.2)" />
          <stop offset="15%" stop-color="rgba(255, 215, 0, 0)" />
          <stop offset="100%" stop-color="rgba(255, 215, 0, 0)" />
        </conicGradient>
        <radialGradient id="sunGradient">
          <stop offset="0%" stop-color="#FFF" />
          <stop offset="30%" stop-color="#FFD700" />
          <stop offset="100%" stop-color="rgba(255, 215, 0, 0)" />
        </radialGradient>
      </defs>
      
      <!-- 背景星空粒子 -->
      <g class="starfield">
        <circle v-for="n in 50" :key="'star-'+n" 
                :cx="Math.random() * 600" 
                :cy="Math.random() * 600" 
                :r="Math.random() * 1.5" 
                fill="#FFF" 
                :opacity="Math.random() * 0.5">
          <animate attributeName="opacity" values="0.2;0.8;0.2" :dur="2+Math.random()*3+'s'" repeatCount="indefinite" />
        </circle>
      </g>

      <g class="main-group" transform="translate(300, 300)">
        <!-- 雷达背景 -->
        <circle r="280" fill="rgba(255, 215, 0, 0.02)" />
        
        <!-- 能量波纹扩散效果 -->
        <g class="energy-ripples">
          <circle class="ripple" r="60" />
          <circle class="ripple" r="60" style="animation-delay: 1s" />
          <circle class="ripple" r="60" style="animation-delay: 2s" />
          <circle class="ripple" r="60" style="animation-delay: 3s" />
        </g>
        
        <!-- 雷达扫描扫过效果 -->
        <circle r="280" fill="url(#radarSweep)" class="radar-sweep-area" />
        
        <!-- 轨道线 -->
        <circle class="orbit-line" r="80" stroke="#1F1F22" fill="none" />
        <circle class="orbit-line" r="160" stroke="#1F1F22" fill="none" />
        <circle class="orbit-line" r="240" stroke="#1F1F22" fill="none" />
        
        <!-- 象限分割线 -->
        <line class="axis-line" x1="-280" y1="0" x2="280" y2="0" stroke="#1F1F22" stroke-dasharray="4 4" />
        <line class="axis-line" x1="0" y1="-280" x2="0" y2="280" stroke="#1F1F22" stroke-dasharray="4 4" />
        
        <!-- 象限标签 -->
        <text class="axis-label" x="0" y="-260">天时 (HEAVEN)</text>
        <text class="axis-label" x="260" y="0" style="text-anchor: start;">地利 (EARTH)</text>
        <text class="axis-label" x="0" y="275">人和 (HUMAN)</text>
        
        <!-- 年度流向环 (Time Ring) -->
        <circle class="time-ring-bg" r="280" />
        
        <!-- 中心太阳 -->
        <g class="center-sun">
          <circle r="35" fill="url(#sunGradient)" filter="url(#sun-glow)" class="sun-core" />
          <circle r="45" fill="none" stroke="#FFD700" stroke-width="0.5" stroke-dasharray="2 6" class="sun-ring" />
          <circle r="55" fill="none" stroke="#FFD700" stroke-width="0.5" stroke-dasharray="1 10" class="sun-ring-outer" />
        </g>
        
        <!-- 扫描指针线 -->
        <line x1="0" y1="0" x2="0" y2="-280" stroke="#FFD700" stroke-width="1" class="radar-hand" />
        
        <!-- 节点 -->
        <g v-for="(node, nodeIndex) in filteredNodes" :key="node.id" 
           class="node-group" 
           :class="{ 'scan-triggered': isScanTriggered(nodeIndex) }"
           :transform="`translate(${node.x}, ${node.y})`"
           :style="{ animationDelay: nodeIndex * 0.05 + 's' }"
           @mouseenter="handleMouseOver($event, node)"
           @mouseleave="handleMouseLeave"
           @click.stop="selectedNode = node">
          <!-- 节点背景光晕 -->
          <circle :r="node.radius * 2.5" 
                  :fill="node.type === 'variable' ? 'rgba(255, 82, 82, 0.15)' : (node.type === 'consensus' ? 'rgba(255, 215, 0, 0.2)' : 'rgba(41, 182, 246, 0.15)')" 
                  class="node-glow" />
          
          <!-- 扫描触发光环 -->
          <circle :r="node.radius + 8" 
                  class="scan-ring"
                  fill="none"
                  stroke="rgba(255, 215, 0, 0.6)"
                  stroke-width="2" />
          
          <circle :r="node.radius" 
                  :class="['node-circle', node.type, { 'is-selected': selectedNode?.id === node.id }]" 
                  :filter="node.type === 'consensus' ? 'url(#glow)' : ''" />
          
          <text class="node-label" 
                :x="node.labelX" 
                :y="node.labelY"
                :style="{ textAnchor: node.textAnchor }">
            {{ node.name }}
          </text>
          
          <!-- 观点连线 -->
          <line class="source-line" x1="0" y1="0" :x2="-node.x*0.1" :y2="-node.y*0.1" />
        </g>
      </g>
    </svg>

    <!-- Tooltip -->
    <div v-if="hoveredNode && !selectedNode" class="radar-tooltip" :style="tooltipStyle">
      <div class="tooltip-header">
        <span :class="['type-tag', hoveredNode.type]">
          {{ getTypeText(hoveredNode.type) }}
        </span>
        <span class="impact-tag">强度: {{ hoveredNode.impact }}</span>
      </div>
      <div class="tooltip-title">{{ hoveredNode.name }}</div>
      <div class="tooltip-time">{{ hoveredNode.time }}</div>
      <div class="tooltip-desc">{{ hoveredNode.description?.substring(0, 60) }}...</div>
      <div class="tooltip-footer">点击查看各派大师深度解析</div>
    </div>

    <!-- Drill-down Detail Panel -->
    <Transition name="slide-fade">
      <div v-if="selectedNode" class="detail-panel" @click.stop>
        <div class="detail-header">
          <div class="detail-title-group">
            <span :class="['type-tag', selectedNode.type]">{{ getTypeText(selectedNode.type) }}</span>
            <h3>{{ selectedNode.name }}</h3>
          </div>
          <button class="close-panel" @click="selectedNode = null">&times;</button>
        </div>
        <div class="detail-body">
          <div class="detail-section" v-if="selectedNode.master_name">
            <label>推演大师</label>
            <div class="detail-val master-highlight">{{ selectedNode.master_name }}</div>
          </div>
          <div class="detail-section">
            <label>发生时间</label>
            <div class="detail-val highlight">{{ selectedNode.time }}</div>
          </div>
          <div class="detail-section">
            <label>命理深度解析</label>
            <div class="detail-val desc">{{ selectedNode.description }}</div>
          </div>
          <div class="detail-section">
            <label>推演流派来源</label>
            <div class="detail-val schools">
              <span v-for="school in selectedNode.school_source?.split(',')" :key="school" class="school-tag">
                {{ school.trim() }}
              </span>
            </div>
          </div>
          <div class="detail-section">
            <label>推演置信度</label>
            <div class="confidence-bar">
              <div class="confidence-fill" :style="{ width: (selectedNode.impact * 10) + '%' }"></div>
              <span class="confidence-text">{{ selectedNode.impact * 10 }}%</span>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'

const props = defineProps({
  data: {
    type: Object,
    default: () => ({ nodes: [], edges: [] })
  }
})

const width = ref(0)
const height = 600
const container = ref(null)
const hoveredNode = ref(null)
const selectedNode = ref(null)
const currentYear = ref(null)
const tooltipStyle = ref({ top: '0px', left: '0px' })

// --- Zoom & Pan Logic ---
const viewBox = ref({ x: 0, y: 0, w: 600, h: 600 })
const isDragging = ref(false)
const startPanPos = ref({ x: 0, y: 0 })
const wasDragging = ref(false)

const viewBoxString = computed(() => 
  `${viewBox.value.x} ${viewBox.value.y} ${viewBox.value.w} ${viewBox.value.h}`
)

const handleWheel = (e) => {
  e.preventDefault()
  const svgRect = e.currentTarget.getBoundingClientRect()
  const scale = e.deltaY > 0 ? 1.1 : 0.9
  
  // Limit zoom
  const newW = viewBox.value.w * scale
  const newH = viewBox.value.h * scale
  if (newW < 100 || newW > 2000) return

  // Mouse position relative to SVG element (0 to width/height)
  const mx = e.clientX - svgRect.left
  const my = e.clientY - svgRect.top
  
  // Convert mouse position to viewBox coordinates
  const mouseVbX = viewBox.value.x + (mx / svgRect.width) * viewBox.value.w
  const mouseVbY = viewBox.value.y + (my / svgRect.height) * viewBox.value.h
  
  // Calculate new viewBox x/y to keep mouse position stable
  viewBox.value.x = mouseVbX - (mx / svgRect.width) * newW
  viewBox.value.y = mouseVbY - (my / svgRect.height) * newH
  viewBox.value.w = newW
  viewBox.value.h = newH
}

const startDrag = (e) => {
  // Only left click
  if (e.button !== 0) return
  isDragging.value = true
  wasDragging.value = false
  startPanPos.value = { x: e.clientX, y: e.clientY }
  if (container.value) container.value.style.cursor = 'grabbing'
}

const onDrag = (e) => {
  if (!isDragging.value) return
  
  const dx = e.clientX - startPanPos.value.x
  const dy = e.clientY - startPanPos.value.y
  
  if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
    wasDragging.value = true
  }
  
  const svgElement = container.value.querySelector('svg')
  if (!svgElement) return
  const svgRect = svgElement.getBoundingClientRect()
  
  // Convert screen pixels to viewBox units
  const scaleX = viewBox.value.w / svgRect.width
  const scaleY = viewBox.value.h / svgRect.height
  
  viewBox.value.x -= dx * scaleX
  viewBox.value.y -= dy * scaleY
  
  startPanPos.value = { x: e.clientX, y: e.clientY }
}

const stopDrag = () => {
  isDragging.value = false
  if (container.value) {
    container.value.style.cursor = 'default'
  }
}

const handleSvgClick = () => {
  if (!wasDragging.value) {
    selectedNode.value = null
  }
}

const zoomIn = () => {
  const scale = 0.8
  const cx = viewBox.value.x + viewBox.value.w / 2
  const cy = viewBox.value.y + viewBox.value.h / 2
  const newW = viewBox.value.w * scale
  const newH = viewBox.value.h * scale
  viewBox.value.x = cx - newW / 2
  viewBox.value.y = cy - newH / 2
  viewBox.value.w = newW
  viewBox.value.h = newH
}

const zoomOut = () => {
  const scale = 1.25
  const cx = viewBox.value.x + viewBox.value.w / 2
  const cy = viewBox.value.y + viewBox.value.h / 2
  const newW = viewBox.value.w * scale
  const newH = viewBox.value.h * scale
  if (newW > 2000) return
  viewBox.value.x = cx - newW / 2
  viewBox.value.y = cy - newH / 2
  viewBox.value.w = newW
  viewBox.value.h = newH
}

const resetZoom = () => {
  viewBox.value = { x: 0, y: 0, w: 600, h: 600 }
}

const getTypeText = (type) => {
  const map = {
    consensus: '核心共识',
    unique: '独特视角',
    variable: '命理变数'
  }
  return map[type] || '预测事件'
}

// 提取所有可用的年份
const availableYears = computed(() => {
  if (!props.data?.nodes) return []
  const years = props.data.nodes
    .map(n => n.properties?.time)
    .filter(t => t) // 只要有值就行
    .map(t => {
      // 尝试提取年份数字
      const match = t.match(/\d{4}/)
      return match ? match[0] : null
    })
    .filter(Boolean)
  
  // 如果提取不到年份，给一个默认的 "全周期"
  if (years.length === 0 && props.data.nodes.length > 0) {
      return []
  }
  
  return Array.from(new Set(years)).sort()
})

// 初始化默认年份
watch(availableYears, (newYears) => {
  if (newYears.length > 0) {
     if (!currentYear.value || !newYears.includes(currentYear.value)) {
        currentYear.value = newYears[0]
     }
  } else if (props.data?.nodes?.length > 0) {
      // 如果没有年份但有节点，尝试强制显示所有（容错逻辑）
      // 这里可以考虑给一个特殊标记，但为了简单，我们先不做特殊处理，
      // 因为后端已经做了补全
  }
}, { immediate: true })

const filteredNodes = computed(() => {
  if (!props.data?.nodes) return []
  
  // 如果没有选中年份，尝试返回所有节点（兜底）
  let targetNodes = props.data.nodes
  if (currentYear.value) {
      targetNodes = targetNodes.filter(n => n.properties?.time?.includes(currentYear.value))
  }
  
  // 按类型分组排序：consensus 在内圈，unique 中圈，variable 外圈
  const typeOrder = { 'consensus': 0, 'unique': 1, 'normal': 1, 'variable': 2, 'conflict': 2 }
  const sortedNodes = [...targetNodes].sort((a, b) => {
    const typeA = typeOrder[a.properties?.type] ?? 1
    const typeB = typeOrder[b.properties?.type] ?? 1
    return typeA - typeB
  })
  
  // 螺旋排列算法参数
  const totalNodes = sortedNodes.length
  const spiralTurns = 2.5 // 螺旋圈数
  const innerRadius = 70 // 起始半径
  const outerRadius = 250 // 最大半径
  const goldenAngle = 137.508 * Math.PI / 180 // 黄金角度（弧度）
  
  return sortedNodes.map((node, index, arr) => {
      const p = node.properties || {}
      let impact = parseInt(p.impact)
      if (isNaN(impact)) impact = 5 // 默认值
      
      const type = p.type || 'normal'
      const normalizedType = (type === 'conflict' || type === 'variable') ? 'variable' : (type === 'consensus' ? 'consensus' : 'unique')
      const dimension = p.dimension || 'career'
      
      // 使用哈希保持位置稳定性
      const hash = node.id.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
      
      // 维度基础角度 - 将四个维度分布在四个象限
      const dimAngles = { career: 0, wealth: 90, emotion: 180, health: 270 }
      const baseDimAngle = (dimAngles[dimension] || 0) * Math.PI / 180
      
      // 在每个象限内，同类型节点的索引
      const sameTypeAndDimNodes = sortedNodes.filter(n => {
        const t = n.properties?.type || 'normal'
        const nt = (t === 'conflict' || t === 'variable') ? 'variable' : (t === 'consensus' ? 'consensus' : 'unique')
        const d = n.properties?.dimension || 'career'
        return nt === normalizedType && d === dimension
      })
      const localIndex = sameTypeAndDimNodes.findIndex(n => n.id === node.id)
      const localTotal = sameTypeAndDimNodes.length
      
      // 每种类型有自己的半径范围
      let baseRadiusMin, baseRadiusMax
      if (normalizedType === 'consensus') {
        baseRadiusMin = 70
        baseRadiusMax = 115
      } else if (normalizedType === 'unique') {
        baseRadiusMin = 125
        baseRadiusMax = 180
      } else { // variable
        baseRadiusMin = 190
        baseRadiusMax = 255
      }
      
      // 在该象限内的角度分布（每个象限占据 75°，预留间隙）
      const sectorSpan = 75 * Math.PI / 180  // 每个象限的有效角度范围
      const angleStep = localTotal > 1 ? sectorSpan / localTotal : 0
      const localAngle = angleStep * localIndex + angleStep * 0.5 - sectorSpan / 2
      const angle = baseDimAngle + localAngle + (hash % 20) * 0.005  // 微调
      
      // 半径：在范围内根据索引渐进分布
      const radiusProgress = localTotal > 1 ? localIndex / (localTotal - 1) : 0.5
      const spiralRadius = baseRadiusMin + (baseRadiusMax - baseRadiusMin) * radiusProgress
      const radiusJitter = ((hash % 20) - 10) * 0.25
      const radius = spiralRadius + radiusJitter

      // 计算标签位置：让标签沿半径方向向外偏移，并根据角度调整对齐方式
      const labelDist = node.radius + 12
      const labelX = Math.cos(angle) * labelDist
      const labelY = Math.sin(angle) * labelDist + 4 // 垂直微调

      // 根据象限决定文字锚点
      let textAnchor = 'middle'
      const angleDeg = (angle * 180 / Math.PI) % 360
      const normalizedAngle = angleDeg < 0 ? angleDeg + 360 : angleDeg

      if (normalizedAngle > 20 && normalizedAngle < 160) {
        // 下方区域
        textAnchor = 'middle'
      } else if (normalizedAngle >= 160 && normalizedAngle <= 200) {
        // 左侧
        textAnchor = 'end'
      } else if (normalizedAngle > 200 && normalizedAngle < 340) {
        // 上方
        textAnchor = 'middle'
      } else {
        // 右侧
        textAnchor = 'start'
      }

      // 额外的交错偏移逻辑，防止同角度的标签重叠
      const staggerY = (localIndex % 2 === 0) ? 0 : (normalizedAngle > 180 ? -12 : 12)
      
      return {
        id: node.id,
        name: p.name || '年度节点',
        time: p.time,
        description: p.description,
        master_name: p.master_name,
        school_source: p.school_source,
        impact: impact,
        type: normalizedType,
        dimension: dimension,
        radius: normalizedType === 'consensus' ? (impact * 0.8 + 5) : (impact * 0.6 + 4),
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
        labelX: labelX,
        labelY: labelY + staggerY,
        textAnchor: textAnchor
      }
    })
})

const handleMouseOver = (event, node) => {
  hoveredNode.value = node
  const rect = container.value.getBoundingClientRect()
  tooltipStyle.value = {
    left: (event.clientX - rect.left + 20) + 'px',
    top: (event.clientY - rect.top + 20) + 'px'
  }
}

const handleMouseLeave = () => {
  hoveredNode.value = null
}

// 扫描触发效果 - 根据节点角度判断是否被扫描线扫过
const scanAngle = ref(0)
let scanTimer = null

const isScanTriggered = (nodeIndex) => {
  if (!filteredNodes.value[nodeIndex]) return false
  const node = filteredNodes.value[nodeIndex]
  const nodeAngle = Math.atan2(node.y, node.x) * 180 / Math.PI + 180
  const angleDiff = Math.abs(nodeAngle - scanAngle.value)
  return angleDiff < 20 || angleDiff > 340
}

const startScanAnimation = () => {
  scanTimer = setInterval(() => {
    scanAngle.value = (scanAngle.value + 3.6) % 360 // 10秒一圈
  }, 100)
}

const stopScanAnimation = () => {
  if (scanTimer) clearInterval(scanTimer)
}

onMounted(() => {
  if (container.value) {
    width.value = container.value.clientWidth
  }
  startScanAnimation()
})

onUnmounted(() => {
  stopScanAnimation()
})
</script>

<style scoped>
.radar-container {
  width: 100%;
  height: 600px;
  background: #080809;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.radar-header {
  padding: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 10;
}

.radar-title {
  color: #FFF;
  font-family: 'JetBrains Mono', monospace;
  font-size: 14px;
  letter-spacing: 2px;
  opacity: 0.6;
}

.radar-legend {
  display: flex;
  gap: 20px;
  font-size: 12px;
  color: #888;
}

.radar-controls {
  display: flex;
  gap: 8px;
  background: rgba(255, 255, 255, 0.05);
  padding: 4px;
  border-radius: 8px;
  border: 1px solid #1F1F22;
}

.year-btn {
  background: transparent;
  border: none;
  color: #666;
  padding: 4px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  transition: all 0.3s;
}

.year-btn:hover {
  color: #AAA;
}

.year-btn.active {
  background: #FFD700;
  color: #000;
  font-weight: bold;
}

.zoom-controls {
  display: flex;
  gap: 4px;
  margin-left: 8px;
  border-left: 1px solid rgba(255, 255, 255, 0.1);
  padding-left: 8px;
}

.control-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #888;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'JetBrains Mono', monospace;
  font-size: 14px;
  transition: all 0.2s;
}

.control-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #FFF;
  border-color: rgba(255, 255, 255, 0.4);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: help;
  position: relative;
  transition: color 0.3s;
}

.legend-item:hover {
  color: #FFF;
}

.info-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.3);
  font-size: 10px;
  color: rgba(255, 255, 255, 0.5);
  margin-left: 2px;
}

.legend-item:hover .info-icon {
  border-color: #FFD700;
  color: #FFD700;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot.consensus { background: #FFD700; box-shadow: 0 0 10px #FFD700; }
.dot.unique { background: #29B6F6; box-shadow: 0 0 10px #29B6F6; }
.dot.variable { background: #FF5252; box-shadow: 0 0 10px #FF5252; }

.radar-svg {
  flex: 1;
  width: 100%;
  height: 100%;
  max-height: 100%;
}

.radar-sweep-area {
  animation: sweepRotate 10s linear infinite;
  transform-origin: center;
}

.radar-hand {
  animation: sweepRotate 10s linear infinite;
  transform-origin: 0 0;
  opacity: 0.5;
}

@keyframes sweepRotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 能量波纹扩散 */
.energy-ripples .ripple {
  fill: none;
  stroke: rgba(255, 215, 0, 0.4);
  stroke-width: 2;
  animation: rippleExpand 4s ease-out infinite;
}

@keyframes rippleExpand {
  0% { r: 50; opacity: 0.8; stroke-width: 3; }
  100% { r: 280; opacity: 0; stroke-width: 0.5; }
}

/* 扫描触发光环 */
.scan-ring {
  opacity: 0;
  transform-origin: center;
  transform-box: fill-box;
}

.node-group.scan-triggered .scan-ring {
  opacity: 1;
  animation: scanFlash 0.6s ease-out;
}

@keyframes scanFlash {
  0% { stroke-width: 4; opacity: 1; transform: scale(1); }
  50% { stroke-width: 2; opacity: 0.8; transform: scale(1.3); }
  100% { stroke-width: 0; opacity: 0; transform: scale(1.5); }
}

.node-group.scan-triggered .node-circle {
  filter: brightness(1.5) drop-shadow(0 0 10px currentColor);
}

.time-ring-bg {
  fill: none;
  stroke: rgba(255, 215, 0, 0.05);
  stroke-width: 1;
  stroke-dasharray: 4 4;
}

.source-line {
  stroke: rgba(255, 215, 0, 0.1);
  stroke-width: 0.5;
  pointer-events: none;
}

.node-glow {
  pointer-events: none;
  filter: blur(10px);
  opacity: 0.6;
  transition: all 0.3s ease;
  transform-origin: center;
}

.orbit-line {
  fill: none;
  stroke: #1F1F22;
  stroke-width: 1;
}

.axis-line {
  stroke: #1F1F22;
  stroke-width: 1;
  stroke-dasharray: 4 4;
}

.sector-line {
  stroke: #1F1F22;
  stroke-width: 1;
  stroke-dasharray: 2 4;
  opacity: 0.5;
}

.axis-label {
  fill: #444;
  font-size: 10px;
  text-anchor: middle;
  font-weight: bold;
}

.sector-label {
  fill: #555;
  font-size: 11px;
  text-anchor: middle;
  font-family: 'JetBrains Mono', monospace;
  font-weight: bold;
  letter-spacing: 1px;
  opacity: 0.7;
}

.ring-label {
  fill: #333;
  font-size: 9px;
  text-anchor: middle;
  pointer-events: none;
}

.sun-core {
  animation: sunPulse 4s infinite ease-in-out;
}

.sun-ring {
  animation: ringRotate 20s linear infinite;
  opacity: 0.3;
}

.sun-ring-outer {
  animation: ringRotate 30s linear reverse infinite;
  opacity: 0.2;
}

@keyframes sunPulse {
  0%, 100% { transform: scale(1); opacity: 0.8; }
  50% { transform: scale(1.1); opacity: 1; }
}

@keyframes ringRotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.node-group {
  cursor: pointer;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.node-group:hover {
  filter: brightness(1.8);
}

.node-group:hover .node-circle {
  transform: scale(1.2);
}

.node-group:hover .node-glow {
  transform: scale(1.2);
}

.node-circle {
  transition: all 0.3s ease;
  transform-origin: center;
  transform-box: fill-box;
}

.node-glow {
  pointer-events: none;
  filter: blur(10px);
  opacity: 0.6;
  transform-origin: center;
  transform-box: fill-box;
}

.node-circle.consensus {
  fill: #FFD700;
  stroke: #FFF;
  stroke-width: 1;
  box-shadow: 0 0 15px rgba(255, 215, 0, 0.8);
}

.node-circle.unique {
  fill: #29B6F6; /* 更亮的蓝色 */
  stroke: #E1F5FE;
  stroke-width: 1.5;
  box-shadow: 0 0 10px #29B6F6;
}

.node-circle.variable {
  fill: #FF5252;
  stroke: #FFEBEE;
  stroke-width: 1.5;
  box-shadow: 0 0 10px #FF5252;
  animation: variableGlitch 3s infinite;
}

@keyframes variableGlitch {
  0%, 100% { transform: translate(0, 0); opacity: 1; }
  5%, 15% { transform: translate(-1px, 1px); opacity: 0.9; }
  10%, 20% { transform: translate(1px, -1px); opacity: 1; }
}

.node-label {
  fill: #888;
  font-size: 9px;
  text-anchor: middle;
  pointer-events: none;
  font-weight: 500;
}

.node-group:hover .node-label {
  fill: #FFF;
  font-size: 11px;
}

.node-circle.is-selected {
  stroke: #FFF;
  stroke-width: 3px;
  filter: drop-shadow(0 0 10px #FFF);
}

/* Detail Panel Styles */
.detail-panel {
  position: absolute;
  top: 20px;
  right: 20px;
  width: 320px;
  background: rgba(13, 13, 15, 0.9);
  backdrop-filter: blur(20px);
  border: 1px solid #1F1F22;
  border-radius: 16px;
  z-index: 150;
  box-shadow: -10px 0 40px rgba(0,0,0,0.8);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-header {
  padding: 20px;
  border-bottom: 1px solid #1F1F22;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.detail-title-group h3 {
  margin: 8px 0 0;
  font-size: 20px;
  color: #FFF;
}

.close-panel {
  background: none;
  border: none;
  color: #666;
  font-size: 24px;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.detail-body {
  padding: 20px;
  overflow-y: auto;
  max-height: 400px;
}

.detail-section {
  margin-bottom: 20px;
}

.detail-section label {
  display: block;
  font-size: 10px;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 8px;
}

.detail-val {
  color: #AAA;
  font-size: 14px;
  line-height: 1.6;
}

.detail-val.highlight {
  color: #64B5F6;
  font-family: 'JetBrains Mono', monospace;
}

.detail-val.master-highlight {
  color: #FFD700;
  font-weight: bold;
  font-size: 15px;
}

.detail-val.desc {
  background: rgba(255, 255, 255, 0.03);
  padding: 12px;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.6;
}

.schools {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.school-tag {
  background: #1A1A1D;
  border: 1px solid #2A2A2F;
  color: #888;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}

.confidence-bar {
  height: 8px;
  background: #1A1A1D;
  border-radius: 4px;
  position: relative;
  overflow: hidden;
  margin-top: 8px;
}

.confidence-fill {
  height: 100%;
  background: linear-gradient(90deg, #444, #FFD700);
  border-radius: 4px;
}

.confidence-text {
  position: absolute;
  right: 0;
  top: -18px;
  font-size: 10px;
  color: #FFD700;
  font-family: 'JetBrains Mono', monospace;
}

/* Transitions */
.slide-fade-enter-active {
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.7, 0, 0.84, 0);
}

.slide-fade-enter-from,
.slide-fade-leave-to {
  transform: translateX(50px);
  opacity: 0;
}

/* Tooltip Styles */
.radar-tooltip {
  position: absolute;
  background: rgba(13, 13, 15, 0.95);
  border: 1px solid #1F1F22;
  padding: 16px;
  border-radius: 8px;
  z-index: 100;
  width: 240px;
  pointer-events: none;
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
}

.tooltip-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}

.type-tag {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 4px;
}

.type-tag.consensus { background: rgba(255, 215, 0, 0.1); color: #FFD700; border: 1px solid rgba(255, 215, 0, 0.3); }
.type-tag.variable { background: rgba(255, 82, 82, 0.1); color: #FF5252; border: 1px solid rgba(255, 82, 82, 0.3); }

.impact-tag {
  font-size: 10px;
  color: #666;
}

.tooltip-title {
  color: #FFF;
  font-size: 16px;
  font-weight: bold;
  margin-bottom: 4px;
}

.tooltip-time {
  color: #64B5F6;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  margin-bottom: 8px;
}

.tooltip-desc {
  color: #888;
  font-size: 12px;
  line-height: 1.6;
  margin-bottom: 12px;
}

.tooltip-footer {
  font-size: 10px;
  color: #444;
  border-top: 1px solid #1F1F22;
  padding-top: 8px;
}
</style>
