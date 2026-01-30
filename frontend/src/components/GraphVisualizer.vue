<template>
  <div class="cosmos-container" ref="container">
    <!-- Canvas Layer -->
    <canvas 
      ref="canvasRef" 
      class="cosmos-canvas"
      @mousedown="handleMouseDown"
      @mousemove="handleMouseMove"
      @mouseup="handleMouseUp"
      @mouseleave="handleMouseUp"
      @wheel="handleWheel"
    ></canvas>
    
    <!-- UI Overlay (HUD) -->
    <div class="hud-layer">
      <div class="hud-header">
        <div class="hud-title">CHRONO_NEBULA // <span class="accent">命运星云</span></div>
        <div class="hud-subtitle">ASSOCIATIVE DEDUCTION ENGINE</div>
      </div>

      <div class="hud-controls">
        <div class="control-group">
          <label>TIMELINE FOCUS</label>
          <input 
            type="range" 
            :min="minYearRef" 
            :max="maxYearRef" 
            step="0.1" 
            v-model.number="timelineFocus"
            class="cyber-slider"
          />
          <div class="value-display">{{ Math.floor(timelineFocus) }}</div>
        </div>
      </div>

      <!-- Legend Overlay (Top Left) -->
      <div class="legend-overlay">
        <div class="legend-header">NEBULA_LEGEND // 图例</div>
        <div class="legend-items">
          <div v-for="(config, type) in TYPE_CONFIG" :key="type" class="legend-item">
            <div class="dot-container">
              <div class="legend-dot" :style="{ backgroundColor: config.color, boxShadow: `0 0 10px ${config.color}` }"></div>
              <div class="legend-glow" :style="{ backgroundColor: config.color }"></div>
            </div>
            <div class="legend-info">
              <div class="legend-label">{{ config.label }}</div>
              <div class="legend-desc">{{ config.desc }}</div>
            </div>
          </div>
          <div class="legend-separator"></div>
          
          <!-- Dimension Legend -->
          <div v-for="(config, dim) in DIMENSION_CONFIG" :key="dim" class="legend-item">
            <div class="legend-icon" :style="{ color: '#FFF' }">{{ config.icon }}</div>
            <div class="legend-info">
              <div class="legend-label">{{ config.label }}</div>
            </div>
          </div>

          <div class="legend-separator"></div>

          <!-- Edge Legend -->
          <div class="legend-item">
            <div class="legend-line-icon"></div>
            <div class="legend-info">
              <div class="legend-label">推演关联</div>
              <div class="legend-desc">事件间的逻辑与因果连线</div>
            </div>
          </div>
          
          <div class="legend-item size-legend">
            <div class="size-dots">
              <div class="dot d1"></div>
              <div class="dot d2"></div>
              <div class="dot d3"></div>
            </div>
            <div class="legend-info">
              <div class="legend-label">因果权重</div>
              <div class="legend-desc">节点越大，关联因果越密集</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Detail Panel (Right) -->
      <transition name="slide-right">
        <div v-if="selectedNode" class="detail-panel">
          <div class="panel-header">
            <div class="node-id">#{{ selectedNode.id.substring(0,4) }}</div>
            <div class="node-year">{{ selectedNode.year }}</div>
          </div>
          <h2 class="node-title">{{ selectedNode.label }}</h2>
          <div class="node-type" :class="selectedNode.type.toLowerCase()">
            {{ getTypeLabel(selectedNode.type) }}
          </div>
          <p class="node-desc">{{ selectedNode.description }}</p>
          <div class="panel-footer">
            <div class="stat-row">
              <span>CONFIDENCE</span>
              <div class="bar"><div class="fill" style="width: 85%"></div></div>
            </div>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'

const props = defineProps({
  data: {
    type: Object,
    default: () => ({ nodes: [], edges: [] })
  },
  minYear: {
    type: Number,
    default: null
  },
  maxYear: {
    type: Number,
    default: null
  }
})

// --- Refs & State ---
const container = ref(null)
const canvasRef = ref(null)
const selectedNode = ref(null)
const timelineFocus = ref(2025)
const minYearRef = ref(2025)
const maxYearRef = ref(2035)

// Physics World
let nodes = []
let edges = []
let particles = [] // Visual particles flowing on links
let stars = [] // Background stars
let nebulaClouds = [] // Large colorful gas clouds

// Camera / Interaction
let camera = { x: 0, y: 0, targetX: 0, targetY: 0, zoom: 1, targetZoom: 1 }
let isDragging = false
let lastMouse = { x: 0, y: 0 }
let hoverNode = null
let animationFrameId = null

// Constants
const COLORS = {
  bg: '#030508',
  nodeDefault: '#4a9eff',
  nodeConsensus: '#00f2ff', // 共识
  nodeUnique: '#ffd700',    // 独特
  nodeVariable: '#bf7aff',  // 变数
  edge: 'rgba(74, 158, 255, 0.15)',
  text: '#ffffff'
}

const TYPE_CONFIG = {
  consensus: { label: '核心共识', color: COLORS.nodeConsensus, desc: '聚合 ≥6 位不同流派大师的共同推演结论' },
  unique: { label: '独特洞察', color: COLORS.nodeUnique, desc: '单一大师的深度独家洞察' },
  variable: { label: '命理变数', color: COLORS.nodeVariable, desc: '涉及重大转折或抉择的不确定性预测' }
}

const DIMENSION_CONFIG = {
  career: { label: '事业', icon: '▲' }, // Triangle
  wealth: { label: '财富', icon: '◆' }, // Diamond
  emotion: { label: '情感', icon: '♥' }, // Heart
  health: { label: '健康', icon: '■' }, // Square
  default: { label: '综合', icon: '★' }  // Star
}

// --- Animal Nebula Shapes ---
  // High-fidelity point maps. Coordinates are relative grid units.
  // "Phantom Nebula" particles will flesh these out to make them instantly recognizable.
  const ANIMAL_SHAPES = {
    phoenix: [
      // --- PHOENIX (Centered Y-0.65) ---
      // Head & Crest
      { x: 0, y: -2.65 }, { x: 0.3, y: -2.85 }, { x: -0.2, y: -2.75 }, 
      { x: 0, y: -2.15 }, { x: 0.5, y: -2.25 },
      // Neck
      { x: 0, y: -1.65 },
      // Body Core
      { x: 0, y: -0.65 }, { x: 0.4, y: -0.85 }, { x: -0.4, y: -0.85 }, { x: 0, y: -0.15 },
      // Left Wing
      { x: -0.8, y: -1.45 }, { x: -1.5, y: -1.85 }, { x: -2.5, y: -2.15 }, { x: -3.2, y: -2.45 },
      { x: -1.2, y: -0.85 }, { x: -2.0, y: -1.15 }, { x: -2.8, y: -1.45 },
      { x: -0.8, y: -0.45 }, { x: -1.5, y: -0.15 }, { x: -2.2, y: 0.15 },
      // Right Wing
      { x: 0.8, y: -1.45 }, { x: 1.5, y: -1.85 }, { x: 2.5, y: -2.15 }, { x: 3.2, y: -2.45 },
      { x: 1.2, y: -0.85 }, { x: 2.0, y: -1.15 }, { x: 2.8, y: -1.45 },
      { x: 0.8, y: -0.45 }, { x: 1.5, y: -0.15 }, { x: 2.2, y: 0.15 },
      // Tail
      { x: 0, y: 0.55 }, 
      { x: -0.3, y: 1.15 }, { x: -0.8, y: 1.85 }, { x: -1.2, y: 2.35 },
      { x: 0.3, y: 1.15 }, { x: 0.8, y: 1.85 }, { x: 1.2, y: 2.35 },
      { x: 0, y: 1.35 }, { x: 0, y: 2.15 }, { x: 0, y: 2.85 }
    ],
    butterfly: [
      // --- BUTTERFLY (Centered Y-0.35) ---
      // Body Axis
      { x: 0, y: -0.85 }, { x: 0, y: -0.35 }, { x: 0, y: 0.15 }, { x: 0, y: 0.65 },
      // Head & Antennae
      { x: 0, y: -1.15 }, 
      { x: -0.3, y: -1.55 }, { x: -0.6, y: -1.95 }, { x: -0.7, y: -2.15 },
      { x: 0.3, y: -1.55 }, { x: 0.6, y: -1.95 }, { x: 0.7, y: -2.15 },
      // Top Left Wing
      { x: -0.5, y: -1.15 }, { x: -1.2, y: -1.85 }, { x: -2.0, y: -2.15 }, { x: -2.8, y: -1.85 },
      { x: -2.5, y: -0.85 }, { x: -1.5, y: -0.55 },
      // Top Right Wing
      { x: 0.5, y: -1.15 }, { x: 1.2, y: -1.85 }, { x: 2.0, y: -2.15 }, { x: 2.8, y: -1.85 },
      { x: 2.5, y: -0.85 }, { x: 1.5, y: -0.55 },
      // Bottom Left Wing
      { x: -0.5, y: 0.15 }, { x: -1.5, y: 0.45 }, { x: -2.2, y: 1.15 }, { x: -1.8, y: 1.85 },
      { x: -1.0, y: 2.15 }, { x: -0.5, y: 1.15 },
      // Bottom Right Wing
      { x: 0.5, y: 0.15 }, { x: 1.5, y: 0.45 }, { x: 2.2, y: 1.15 }, { x: 1.8, y: 1.85 },
      { x: 1.0, y: 2.15 }, { x: 0.5, y: 1.15 }
    ],
    rabbit: [
      // --- RABBIT (Centered Y+0.65) ---
      // Head
      { x: -1.0, y: 0.15 }, { x: -1.4, y: 0.45 }, { x: -0.8, y: 0.45 },
      // Ears
      { x: -1.2, y: -0.35 }, { x: -1.4, y: -1.15 }, { x: -1.5, y: -1.85 },
      { x: -0.8, y: -0.35 }, { x: -0.6, y: -1.15 }, { x: -0.5, y: -1.85 },
      // Body
      { x: -0.5, y: 0.85 }, { x: 0, y: 0.45 }, { x: 0.5, y: 0.35 }, { x: 1.0, y: 0.65 },
      { x: 1.2, y: 1.15 }, { x: 0.8, y: 1.45 }, { x: 0.2, y: 1.45 },
      // Front Paws
      { x: -0.8, y: 1.45 }, { x: -1.0, y: 1.85 },
      // Hind Legs
      { x: 1.0, y: 1.65 }, { x: 1.4, y: 1.85 }, { x: 1.4, y: 1.15 },
      // Tail
      { x: 1.6, y: 0.85 }, { x: 1.8, y: 1.05 }
    ],
    sheep: [
      // --- SHEEP HEAD (Centered Y+0.15) ---
      // Face
      { x: 0, y: 1.35 }, // Chin
      { x: -0.5, y: -0.35 }, { x: 0.5, y: -0.35 }, // Forehead
      { x: -0.3, y: 0.65 }, { x: 0.3, y: 0.65 }, // Muzzle
      { x: 0, y: -0.05 }, // Nose bridge
      // Eyes
      { x: -0.6, y: -0.05 }, { x: 0.6, y: -0.05 },
      // Horns
      { x: -0.6, y: -0.65 }, { x: -1.0, y: -1.35 }, { x: -1.8, y: -1.05 },
      { x: -2.2, y: -0.35 }, { x: -2.0, y: 0.35 }, { x: -1.5, y: 0.65 },
      
      { x: 0.6, y: -0.65 }, { x: 1.0, y: -1.35 }, { x: 1.8, y: -1.05 },
      { x: 2.2, y: -0.35 }, { x: 2.0, y: 0.35 }, { x: 1.5, y: 0.65 },
      // Ears
      { x: -1.2, y: -0.05 }, { x: -1.6, y: 0.15 },
      { x: 1.2, y: -0.05 }, { x: 1.6, y: 0.15 }
    ],
    dolphin: [
      // --- DOLPHIN (Centered Y-0.2) ---
      // Body Arc
      { x: -1.5, y: 0.3 }, { x: -0.5, y: -0.2 }, { x: 0.5, y: -0.4 }, { x: 1.5, y: -0.2 }, { x: 2.2, y: 0.3 },
      // Belly Line
      { x: -0.5, y: 0.3 }, { x: 0.5, y: 0.3 }, { x: 1.2, y: 0.2 },
      // Dorsal Fin
      { x: 0, y: -0.4 }, { x: 0.2, y: -1.2 }, { x: 0.5, y: -0.4 },
      // Head
      { x: -1.8, y: 0.5 }, { x: -2.2, y: 0.7 }, { x: -2.5, y: 0.8 },
      { x: -1.8, y: 0.1 },
      // Pectoral Fin
      { x: -0.8, y: 0.6 }, { x: -0.6, y: 1.2 },
      // Tail Flukes
      { x: 2.8, y: 0.0 }, 
      { x: 3.3, y: -0.5 }, 
      { x: 3.3, y: 0.5 }
    ]
  }

const getTypeLabel = (rawType) => {
  const t = rawType?.toLowerCase() || ''
  if (t === 'insight') return TYPE_CONFIG.unique.label
  return TYPE_CONFIG[t]?.label || rawType
}

// --- Physics Engine ---

const initWorld = () => {
  if (!props.data || !props.data.nodes) return

  const width = container.value.clientWidth
  const height = container.value.clientHeight

  // Initialize Nodes with Time-River Layout
  const YEAR_SPACING = 1000 // Pixels per year
  
  // Calculate dynamic time range
  if (props.minYear && props.maxYear) {
    minYearRef.value = props.minYear
    maxYearRef.value = props.maxYear
  } else {
    const years = props.data.nodes.map(n => {
      const m = String(n.properties?.time || '').match(/20\d{2}/)
      return m ? parseInt(m[0]) : null
    }).filter(y => y !== null)

    if (years.length > 0) {
      minYearRef.value = Math.min(...years)
      maxYearRef.value = Math.max(...years)
    } else {
      minYearRef.value = 2024
      maxYearRef.value = 2036
    }
  }
  
  // Clamp current focus
  if (timelineFocus.value < minYearRef.value) timelineFocus.value = minYearRef.value
  if (timelineFocus.value > maxYearRef.value) timelineFocus.value = maxYearRef.value

  nodes = props.data.nodes.map(n => {
    const p = n.properties || {}
    const type = p.type?.toLowerCase() || 'consensus'
    let color = COLORS.nodeConsensus
    let radius = 8 // 共识节点更突出

    if (type === 'unique' || type === 'insight') {
      color = COLORS.nodeUnique
      radius = 6
    } else if (type === 'variable') {
      color = COLORS.nodeVariable
      radius = 5
    }

    // Parse Year
    const yearMatch = String(p.time || '').match(/20\d{2}/)
    const year = yearMatch ? parseInt(yearMatch[0]) : minYearRef.value
    
    // Calculate Target X based on Year
    const targetX = (year - minYearRef.value) * YEAR_SPACING
    
    // Dimension & Shape
    const dimension = p.dimension || 'default'

    return {
      ...n,
      label: p.name || '未命名节点',
      year: p.time || '',
      parsedYear: year,
      description: p.description || '',
      type: type,
      dimension: dimension,
      // Start near their target year but with random Y spread
      x: targetX + (Math.random() - 0.5) * 400,
      y: (Math.random() - 0.5) * height * 0.8,
      targetX: targetX, // Physics goal
      vx: 0,
      vy: 0,
      radius: radius,
      color: color,
      weight: 1
    }
  })

  // Initialize Edges
  // Map IDs to node objects for faster access
  const nodeMap = new Map(nodes.map(n => [n.id, n]))
  edges = (props.data.edges || []).map(e => {
    const source = nodeMap.get(e.source)
    const target = nodeMap.get(e.target)
    if (source && target) {
      source.weight++
      target.weight++
    }
    return {
      source,
      target,
      length: 100 + Math.random() * 50
    }
  }).filter(e => e.source && e.target)

  // Initialize Background Stars with more depth
  stars = Array.from({ length: 600 }, () => ({
    x: (Math.random() - 0.5) * 40000, // Wider starfield
    y: (Math.random() - 0.5) * 8000,
    z: Math.random() * 3 + 0.1,
    size: Math.random() * 2,
    alpha: Math.random(),
    color: ['#FFF', '#D0EFFF', '#FFEBD0', '#FFD0D0'][Math.floor(Math.random() * 4)]
  }))

  // Initialize Nebula Clouds (Phantom shapes to reinforce animal outlines)
  // Instead of random clouds, these will also flock to the animal coordinates
  nebulaClouds = []
  
  const animalKeys = Object.keys(ANIMAL_SHAPES)
  
  // Create phantom particles for each year
  for (let y = minYearRef.value; y <= maxYearRef.value; y++) {
    const yearX = (y - minYearRef.value) * YEAR_SPACING
    const animalIndex = y % animalKeys.length
    const animalKey = animalKeys[animalIndex]
    const shapePoints = ANIMAL_SHAPES[animalKey]
    
    // Create ~40 particles per year to "flesh out" the animal
    const particlesPerYear = 40
    
    for (let i = 0; i < particlesPerYear; i++) {
      const point = shapePoints[i % shapePoints.length]
      const NODE_SCALE = 120
      
      // Jitter for nebula is higher to create volume/cloud effect
      const jitterX = (Math.random() - 0.5) * 80
      const jitterY = (Math.random() - 0.5) * 80
      
      const tx = yearX + (point.x * NODE_SCALE) + jitterX
      const ty = (point.y * NODE_SCALE) + jitterY
      
      nebulaClouds.push({
        x: tx, 
        y: ty,
        targetX: tx,
        targetY: ty,
        size: 60 + Math.random() * 100, // Small cloud puffs
        color: 'rgba(74, 158, 255, 0.03)', // Subtle blue mist
        parallax: 1.0 // Move with the world (not background)
      })
    }
  }

  // --- Arrange Nodes into Animal Shapes ---
  
  // Group nodes by year
  const nodesByYear = {}
  nodes.forEach(n => {
    if (!nodesByYear[n.parsedYear]) nodesByYear[n.parsedYear] = []
    nodesByYear[n.parsedYear].push(n)
  })

  // Assign positions based on animal shapes
  Object.keys(nodesByYear).forEach(year => {
    const yearNodes = nodesByYear[year]
    if (yearNodes.length === 0) return

    const yearNum = parseInt(year)
    const yearX = (yearNum - minYearRef.value) * YEAR_SPACING
    
    // Pick a deterministic random animal for this year (so it doesn't change on re-render)
    const animalIndex = yearNum % animalKeys.length
    const animalKey = animalKeys[animalIndex]
    const shapePoints = ANIMAL_SHAPES[animalKey]
    
    // Scale for node distribution (larger than nebula points)
    const NODE_SCALE = 120 
    
    yearNodes.forEach((node, i) => {
      // Map node to a shape point
      // If we have more nodes than points, cycle through them
      // If we have fewer, we just use the first N points
      const pointIndex = i % shapePoints.length
      const point = shapePoints[pointIndex]
      
      // Add jitter so nodes don't stack perfectly on top of each other
      const jitterX = (Math.random() - 0.5) * 5
      const jitterY = (Math.random() - 0.5) * 5
      
      node.targetX = yearX + (point.x * NODE_SCALE) + jitterX
      node.targetY = (point.y * NODE_SCALE) + jitterY
      
      // Initial position (fly in)
      node.x = node.targetX + (Math.random() - 0.5) * 1000
      node.y = node.targetY + (Math.random() - 0.5) * 1000
    })
  })
  
  // Reset Camera to start
  camera.x = 0
  camera.y = 0
  camera.targetX = 0
  camera.targetY = 0
  camera.zoom = 0.6
  camera.targetZoom = 0.6
}

const updatePhysics = () => {
  // 1. Repulsion (Local separation)
  const repulsion = 800
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i]
      const b = nodes[j]
      const dx = a.x - b.x
      const dy = a.y - b.y
      const distSq = dx*dx + dy*dy + 0.1
      
      // Only repel if close
      if (distSq < 20000) { 
        const dist = Math.sqrt(distSq)
        const force = repulsion / distSq
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        
        a.vx += fx
        a.vy += fy
        b.vx -= fx
        b.vy -= fy
      }
    }
  }

  // 2. Spring Force (Edges)
  const k = 0.003
  edges.forEach(edge => {
    const dx = edge.target.x - edge.source.x
    const dy = edge.target.y - edge.source.y
    const dist = Math.sqrt(dx*dx + dy*dy)
    const displacement = dist - edge.length
    
    const fx = (dx / dist) * k * displacement
    const fy = (dy / dist) * k * displacement
    
    edge.source.vx += fx
    edge.source.vy += fy
    edge.target.vx -= fx
    edge.target.vy -= fy
  })

  // 3. Timeline Gravity (Pull to Target Year X & Shape Y)
  const shapeGravity = 0.08
  
  nodes.forEach(node => {
    // Pull x towards target year/shape X
    node.vx += (node.targetX - node.x) * shapeGravity
    
    // Pull y towards target shape Y
    // Default to 0 if no targetY set
    const targetY = node.targetY !== undefined ? node.targetY : 0
    node.vy += (targetY - node.y) * shapeGravity
    
    // Interaction Scale
    const distToCam = Math.abs(node.x - camera.x)
    const focusFactor = Math.max(0.5, 1 - distToCam / 1500)
    node.scale = focusFactor

    // Damping
    node.vx *= 0.90
    node.vy *= 0.90
    
    node.x += node.vx
    node.y += node.vy
  })
}

// --- Rendering ---

const draw = () => {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  const width = canvas.width
  const height = canvas.height
  const cx = width / 2
  const cy = height / 2

  // Update Camera Zoom Easing
  camera.zoom += (camera.targetZoom - camera.zoom) * 0.1
  camera.x += (camera.targetX - camera.x) * 0.1
  camera.y += (camera.targetY - camera.y) * 0.1

  // Clear & Background
  ctx.fillStyle = COLORS.bg
  ctx.fillRect(0, 0, width, height)

  // 1. Draw Stars (Enhanced Parallax & Depth)
  stars.forEach(star => {
    const sx = (star.x - camera.x * star.z) * camera.zoom + cx
    const sy = (star.y - camera.y * star.z) * camera.zoom + cy
    
    // Simple frustum culling
    if (sx > -50 && sx < width + 50 && sy > -50 && sy < height + 50) {
      const pulse = 0.7 + Math.sin(Date.now() * 0.001 * star.alpha + star.x) * 0.3
      ctx.fillStyle = star.color
      ctx.globalAlpha = star.alpha * pulse * Math.min(1, camera.zoom * 2)
      ctx.beginPath()
      ctx.arc(sx, sy, star.size * camera.zoom * star.z * 0.5, 0, Math.PI * 2)
      ctx.fill()
    }
  })

  // 1.5. Draw Nebula Clouds (Atmospheric Gas)
  ctx.globalCompositeOperation = 'screen'
  nebulaClouds.forEach(cloud => {
    // Apply simple physics to clouds too (drift to target)
    cloud.x += (cloud.targetX - cloud.x) * 0.05
    cloud.y += (cloud.targetY - cloud.y) * 0.05
    
    const sx = (cloud.x - camera.x * cloud.parallax) * camera.zoom + cx
    const sy = (cloud.y - camera.y * cloud.parallax) * camera.zoom + cy
    const size = cloud.size * camera.zoom

    // Only draw if roughly visible
    if (sx + size > 0 && sx - size < width && sy + size > 0 && sy - size < height) {
      const grad = ctx.createRadialGradient(sx, sy, 0, sx, sy, size)
      grad.addColorStop(0, cloud.color)
      grad.addColorStop(0.5, cloud.color.replace('0.03', '0.01'))
      grad.addColorStop(1, 'transparent')
      
      ctx.fillStyle = grad
      ctx.beginPath()
      ctx.arc(sx, sy, size, 0, Math.PI * 2)
      ctx.fill()
    }
  })
  ctx.globalCompositeOperation = 'source-over'
  ctx.globalAlpha = 1

  // Transform Context for Graph
  ctx.save()
  ctx.translate(cx, cy)
  ctx.scale(camera.zoom, camera.zoom)
  ctx.translate(-camera.x, -camera.y)

  // 1.8. Draw Timeline Guides (Year Markers)
  const YEAR_SPACING = 1000
  
  ctx.font = '300 100px "Rajdhani"'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  
  for (let y = minYearRef.value; y <= maxYearRef.value; y++) {
    const yX = (y - minYearRef.value) * YEAR_SPACING
    
    // Check visibility
    if (yX < camera.x - (width/camera.zoom) || yX > camera.x + (width/camera.zoom)) continue

    // Vertical Line
    ctx.strokeStyle = 'rgba(74, 158, 255, 0.05)'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(yX, -2000)
    ctx.lineTo(yX, 2000)
    ctx.stroke()

    // Year Label (Background)
    ctx.fillStyle = 'rgba(255, 255, 255, 0.03)'
    ctx.fillText(y.toString(), yX, 0)
    
    // Year Label (Small, detailed)
    ctx.fillStyle = 'rgba(74, 158, 255, 0.4)'
    ctx.font = '12px "Courier New"'
    ctx.fillText(`YEAR // ${y}`, yX, -300)
    ctx.font = '300 100px "Rajdhani"' // Reset
  }

  // 2. Draw Edges
  ctx.lineWidth = 1
  edges.forEach(edge => {
    const isRelated = selectedNode.value === edge.source || selectedNode.value === edge.target
    const baseOpacity = Math.min(edge.source.scale, edge.target.scale) * 0.3
    const opacity = selectedNode.value ? (isRelated ? baseOpacity * 2 : baseOpacity * 0.2) : baseOpacity
    
    if (opacity < 0.05) return

    ctx.strokeStyle = `rgba(74, 158, 255, ${opacity})`
    ctx.beginPath()
    ctx.moveTo(edge.source.x, edge.source.y)
    ctx.lineTo(edge.target.x, edge.target.y)
    ctx.stroke()

    // Flowing Energy Particles (Enhanced)
    const time = Date.now() * 0.0008
    const particleCount = isRelated ? 4 : 1
    for (let i = 0; i < particleCount; i++) {
      const offset = i / particleCount
      const particlePos = ((time + offset) % 1) // 0 to 1
      const px = edge.source.x + (edge.target.x - edge.source.x) * particlePos
      const py = edge.source.y + (edge.target.y - edge.source.y) * particlePos
      
      const pSize = (1.2 + Math.sin(time * 5 + i) * 0.5) / camera.zoom
      ctx.fillStyle = '#FFF'
      ctx.shadowBlur = isRelated ? 10 : 5
      ctx.shadowColor = COLORS.nodeDefault
      ctx.globalAlpha = opacity * 2.5
      ctx.beginPath()
      ctx.arc(px, py, pSize, 0, Math.PI * 2)
      ctx.fill()
      ctx.shadowBlur = 0
    }
  })

  // 3. Draw Nodes
  nodes.forEach(node => {
    const isHovered = hoverNode === node
    const isSelected = selectedNode.value === node
    
    // Calculate size based on radius, scale, and weight
    const weightFactor = 1 + (node.weight - 1) * 0.2
    const size = node.radius * node.scale * weightFactor
    
    // Glow
    if (node.scale > 0.4) {
      const pulse = 1 + Math.sin(Date.now() * 0.002 + node.x) * 0.15
      const glowSize = size * (isHovered || isSelected ? 5 : 3) * pulse
      const grad = ctx.createRadialGradient(node.x, node.y, size * 0.2, node.x, node.y, glowSize)
      grad.addColorStop(0, node.color)
      grad.addColorStop(0.3, node.color.replace(')', ', 0.3)').replace('rgb', 'rgba'))
      grad.addColorStop(1, 'rgba(0,0,0,0)')
      
      ctx.fillStyle = grad
      ctx.globalAlpha = 0.7 * node.scale
      ctx.beginPath()
      ctx.arc(node.x, node.y, glowSize, 0, Math.PI * 2)
      ctx.fill()
    }

    // Core Shape Drawing based on Dimension
    ctx.globalAlpha = Math.min(1, node.scale + 0.2)
    ctx.fillStyle = isSelected ? '#FFF' : node.color
    ctx.beginPath()

    const dim = node.dimension
    if (dim === 'career') {
      // Triangle (Up)
      const r = size * 1.2
      ctx.moveTo(node.x, node.y - r)
      ctx.lineTo(node.x + r * 0.866, node.y + r * 0.5)
      ctx.lineTo(node.x - r * 0.866, node.y + r * 0.5)
      ctx.closePath()
    } else if (dim === 'wealth') {
      // Diamond
      const r = size * 1.3
      ctx.moveTo(node.x, node.y - r)
      ctx.lineTo(node.x + r * 0.7, node.y)
      ctx.lineTo(node.x, node.y + r)
      ctx.lineTo(node.x - r * 0.7, node.y)
      ctx.closePath()
    } else if (dim === 'emotion') {
      // Heart
      const r = size * 1.2
      ctx.moveTo(node.x, node.y + r * 0.6)
      ctx.bezierCurveTo(
        node.x - r, node.y - r * 0.6,
        node.x - r, node.y - r * 1.2,
        node.x, node.y - r * 0.6
      )
      ctx.bezierCurveTo(
        node.x + r, node.y - r * 1.2,
        node.x + r, node.y - r * 0.6,
        node.x, node.y + r * 0.6
      )
      ctx.closePath()
    } else if (dim === 'health') {
      // Square (Stability)
      const r = size
      ctx.rect(node.x - r, node.y - r, r * 2, r * 2)
    } else {
      // Default Circle
      ctx.arc(node.x, node.y, size, 0, Math.PI * 2)
    }
    
    ctx.fill()

    // Rings for selected/hover (Match Shape)
    if (isHovered || isSelected) {
      ctx.strokeStyle = node.color
      ctx.lineWidth = 1 / camera.zoom
      ctx.beginPath()
      
      const r = size * 1.8 // Larger ring
      if (dim === 'career') {
        ctx.moveTo(node.x, node.y - r)
        ctx.lineTo(node.x + r * 0.866, node.y + r * 0.5)
        ctx.lineTo(node.x - r * 0.866, node.y + r * 0.5)
        ctx.closePath()
      } else if (dim === 'wealth') {
        ctx.moveTo(node.x, node.y - r)
        ctx.lineTo(node.x + r * 0.7, node.y)
        ctx.lineTo(node.x, node.y + r)
        ctx.lineTo(node.x - r * 0.7, node.y)
        ctx.closePath()
      } else if (dim === 'emotion') {
        const r2 = r * 0.8
        ctx.moveTo(node.x, node.y + r2 * 0.6)
        ctx.bezierCurveTo(
          node.x - r2, node.y - r2 * 0.6,
          node.x - r2, node.y - r2 * 1.2,
          node.x, node.y - r2 * 0.6
        )
        ctx.bezierCurveTo(
          node.x + r2, node.y - r2 * 1.2,
          node.x + r2, node.y - r2 * 0.6,
          node.x, node.y + r2 * 0.6
        )
        ctx.closePath()
      } else if (dim === 'health') {
        ctx.rect(node.x - r, node.y - r, r * 2, r * 2)
      } else {
        ctx.arc(node.x, node.y, r, 0, Math.PI * 2)
      }
      
      ctx.stroke()
    }

    // Label (Cleaned up logic)
    const showLabel = isHovered || isSelected || (camera.zoom > 1.2 && node.scale > 0.8)
    
    if (showLabel) {
      const fontSize = 12 / camera.zoom
      ctx.font = `${fontSize}px "Courier New"`
      const text = node.label
      const metrics = ctx.measureText(text)
      const padding = 4 / camera.zoom
      const bgWidth = metrics.width + padding * 4
      const bgHeight = fontSize + padding * 2
      
      const labelX = node.x
      const labelY = node.y + size + 8 // Offset below node

      // Semi-transparent background for readability
      ctx.fillStyle = 'rgba(5, 10, 18, 0.8)'
      ctx.beginPath()
      ctx.rect(labelX - bgWidth/2, labelY, bgWidth, bgHeight)
      ctx.fill()
      
      // Border for the label
      ctx.strokeStyle = isSelected ? '#FFF' : node.color
      ctx.lineWidth = 0.5 / camera.zoom
      ctx.stroke()

      // Text
      ctx.fillStyle = '#FFF'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'
      ctx.fillText(text, labelX, labelY + padding)
    }
  })

  ctx.restore()
}

const renderLoop = () => {
  updatePhysics()
  draw()
  animationFrameId = requestAnimationFrame(renderLoop)
}

// --- Interaction Handlers ---

const getMouseWorldPos = (e) => {
  const rect = canvasRef.value.getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top
  const width = canvasRef.value.width
  const height = canvasRef.value.height
  const cx = width / 2
  const cy = height / 2
  
  // Inverse transform
  const wx = (mx - cx) / camera.zoom + camera.x
  const wy = (my - cy) / camera.zoom + camera.y
  return { x: wx, y: wy }
}

const handleMouseDown = (e) => {
  // Prevent default to avoid text selection during drag
  e.preventDefault()

  const mousePos = getMouseWorldPos(e)
  let clicked = null
  let minDist = Infinity
  
  nodes.forEach(node => {
    const dist = Math.hypot(node.x - mousePos.x, node.y - mousePos.y)
    if (dist < node.radius * 2 && dist < minDist) {
      clicked = node
      minDist = dist
    }
  })

  if (clicked) {
    selectedNode.value = clicked
    emit('node-click', clicked)
    
    // Smooth camera focus using targets (Draw loop handles easing)
    camera.targetX = clicked.x
    camera.targetY = clicked.y
    camera.targetZoom = 1.5
  } else {
    selectedNode.value = null
    emit('node-click', null)
    isDragging = true
    lastMouse = { x: e.clientX, y: e.clientY }
    if (canvasRef.value) canvasRef.value.style.cursor = 'grabbing'
  }
}

const handleWindowDrag = (e) => {
  if (!isDragging) return
  
  const dx = e.clientX - lastMouse.x
  const dy = e.clientY - lastMouse.y
  
  // Update targets
  camera.targetX -= dx / camera.zoom
  camera.targetY -= dy / camera.zoom
  
  // Force immediate update for 1:1 feel
  camera.x = camera.targetX
  camera.y = camera.targetY
  
  lastMouse = { x: e.clientX, y: e.clientY }

  // Sync Timeline Slider (Passive sync)
  const YEAR_SPACING = 1000
  const currentYear = (camera.x / YEAR_SPACING) + minYearRef.value
  const clampedYear = Math.max(minYearRef.value, Math.min(maxYearRef.value, currentYear))
  
  // Use a temporary flag to prevent watcher from fighting the drag
  isInternalUpdate = true
  timelineFocus.value = clampedYear
  setTimeout(() => { isInternalUpdate = false }, 0)
}

const handleWindowMouseUp = () => {
  if (!isDragging) return
  isDragging = false
  if (canvasRef.value) canvasRef.value.style.cursor = 'default'
}

const handleMouseMove = (e) => {
  // Only handle Hover check here for cursor feedback
  if (isDragging) return

  const mousePos = getMouseWorldPos(e)
  let found = null
  nodes.forEach(node => {
    if (Math.hypot(node.x - mousePos.x, node.y - mousePos.y) < node.radius * 2) {
      found = node
    }
  })
  hoverNode = found
  if (canvasRef.value) {
    canvasRef.value.style.cursor = found ? 'pointer' : 'default'
  }
}

const handleMouseUp = () => {
  handleWindowMouseUp()
}

const handleWheel = (e) => {
  e.preventDefault()
  
  // 1. Get mouse position relative to canvas center
  const rect = canvasRef.value.getBoundingClientRect()
  const mx = e.clientX - rect.left - rect.width / 2
  const my = e.clientY - rect.top - rect.height / 2

  // 2. Calculate world position under mouse (using CURRENT zoom/pos)
  const wx = mx / camera.zoom + camera.x
  const wy = my / camera.zoom + camera.y

  // 3. Update Zoom
  const zoomSensitivity = 0.001
  const zoomFactor = 1 - e.deltaY * zoomSensitivity
  const newZoom = Math.max(0.1, Math.min(5, camera.targetZoom * zoomFactor))
  camera.targetZoom = newZoom

  // 4. Calculate new camera target to keep (wx, wy) under (mx, my)
  camera.targetX = wx - mx / newZoom
  camera.targetY = wy - my / newZoom

  // 5. Sync Timeline Focus (Slider) to new center
  const YEAR_SPACING = 1000
  const centerYear = (camera.targetX / YEAR_SPACING) + minYearRef.value
  
  isInternalUpdate = true
  timelineFocus.value = Math.max(minYearRef.value, Math.min(maxYearRef.value, centerYear))
  setTimeout(() => { isInternalUpdate = false }, 0)
}

// --- Lifecycle ---
let isInternalUpdate = false

const resizeCanvas = () => {
  if (container.value && canvasRef.value) {
    canvasRef.value.width = container.value.clientWidth
    canvasRef.value.height = container.value.clientHeight
  }
}

onMounted(() => {
  window.addEventListener('resize', resizeCanvas)
  window.addEventListener('mousemove', handleWindowDrag)
  window.addEventListener('mouseup', handleWindowMouseUp)
  
  resizeCanvas()
  initWorld()
  renderLoop()
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeCanvas)
  window.removeEventListener('mousemove', handleWindowDrag)
  window.removeEventListener('mouseup', handleWindowMouseUp)
  cancelAnimationFrame(animationFrameId)
})

watch(() => props.data, () => {
  initWorld()
}, { deep: true })

watch(timelineFocus, (newVal) => {
  // If update came from dragging, don't trigger camera animation
  if (isInternalUpdate || isDragging) return

  const YEAR_SPACING = 1000
  const targetX = (newVal - minYearRef.value) * YEAR_SPACING
  
  // Update target directly, render loop handles easing
  camera.targetX = targetX
})

</script>

<style scoped>
.cosmos-container {
  width: 100%;
  height: 800px;
  position: relative;
  background: #030508;
  overflow: hidden;
  font-family: 'Rajdhani', 'Segoe UI', sans-serif;
  user-select: none;
}

.cosmos-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

/* HUD Overlay */
.hud-layer {
  position: absolute;
  top: 0; left: 0; width: 100%; height: 100%;
  pointer-events: none; /* Let clicks pass to canvas */
}

.hud-header {
  position: absolute;
  top: 30px;
  left: 40px;
}

.hud-title {
  color: rgba(255, 255, 255, 0.8);
  font-size: 24px;
  letter-spacing: 4px;
  font-weight: 700;
  text-shadow: 0 0 10px rgba(74, 158, 255, 0.5);
}

.hud-title .accent {
  color: #4a9eff;
  font-weight: 300;
}

.hud-subtitle {
  color: rgba(255, 255, 255, 0.4);
  font-size: 10px;
  letter-spacing: 6px;
  margin-top: 5px;
}

.hud-controls {
  position: absolute;
  bottom: 40px;
  left: 40px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  pointer-events: auto;
}

.control-group {
  background: rgba(10, 20, 30, 0.8);
  backdrop-filter: blur(5px);
  padding: 15px;
  border: 1px solid rgba(74, 158, 255, 0.2);
  border-left: 3px solid #4a9eff;
  width: 200px;
}

.control-group label {
  display: block;
  color: #4a9eff;
  font-size: 10px;
  letter-spacing: 2px;
  margin-bottom: 10px;
}

.cyber-slider {
  width: 100%;
  height: 2px;
  background: #333;
  appearance: none;
  outline: none;
}
.cyber-slider::-webkit-slider-thumb {
  appearance: none;
  width: 10px;
  height: 10px;
  background: #4a9eff;
  border: 1px solid #FFF;
  cursor: pointer;
}

.value-display {
  text-align: right;
  color: #FFF;
  font-size: 18px;
  margin-top: 5px;
  font-family: monospace;
}

.cyber-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: rgba(255, 255, 255, 0.8);
  padding: 10px 20px;
  font-family: inherit;
  letter-spacing: 2px;
  cursor: pointer;
  transition: all 0.3s;
}
.cyber-btn:hover {
  background: rgba(74, 158, 255, 0.2);
  border-color: #4a9eff;
  color: #FFF;
}

/* Legend Overlay */
.legend-overlay {
  position: absolute;
  top: 100px;
  left: 40px;
  background: rgba(10, 20, 30, 0.7);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(74, 158, 255, 0.2);
  padding: 15px;
  pointer-events: auto;
  width: 200px;
  animation: fade-in-left 0.8s cubic-bezier(0.16, 1, 0.3, 1);
}

.legend-header {
  color: #4a9eff;
  font-size: 10px;
  letter-spacing: 2px;
  margin-bottom: 15px;
  border-bottom: 1px solid rgba(74, 158, 255, 0.2);
  padding-bottom: 5px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.dot-container {
  position: relative;
  width: 12px;
  height: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.legend-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  z-index: 2;
}

.legend-icon {
  width: 12px;
  height: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  opacity: 0.8;
}

.legend-line-icon {
  width: 14px;
  height: 1px;
  background: rgba(74, 158, 255, 0.8);
  box-shadow: 0 0 5px rgba(74, 158, 255, 0.8);
  position: relative;
}
.legend-line-icon::after {
  content: '';
  position: absolute;
  top: -1px;
  left: 50%;
  width: 3px;
  height: 3px;
  background: #FFF;
  border-radius: 50%;
  transform: translateX(-50%);
}

.legend-glow {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  filter: blur(4px);
  opacity: 0.5;
  animation: pulse-glow 2s infinite;
}

.legend-info {
  display: flex;
  flex-direction: column;
}

.legend-label {
  color: #FFF;
  font-size: 12px;
  font-weight: 500;
}

.legend-desc {
  color: rgba(255, 255, 255, 0.4);
  font-size: 9px;
  margin-top: 2px;
}

.legend-separator {
  height: 1px;
  background: rgba(255, 255, 255, 0.1);
  margin: 10px 0;
}

.size-legend .size-dots {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 24px;
}

.size-legend .dot {
  background: #FFF;
  border-radius: 50%;
  opacity: 0.6;
}
.size-legend .dot.d1 { width: 3px; height: 3px; }
.size-legend .dot.d2 { width: 5px; height: 5px; }
.size-legend .dot.d3 { width: 8px; height: 8px; }

@keyframes pulse-glow {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 0.6; transform: scale(1.2); }
}

@keyframes fade-in-left {
  from { opacity: 0; transform: translateX(-20px); }
  to { opacity: 1; transform: translateX(0); }
}

/* Detail Panel */
.detail-panel {
  position: absolute;
  top: 0;
  right: 0;
  width: 350px;
  height: 100%;
  background: rgba(5, 10, 18, 0.95);
  border-left: 1px solid rgba(74, 158, 255, 0.3);
  padding: 40px;
  pointer-events: auto;
  box-shadow: -10px 0 50px rgba(0, 0, 0, 0.8);
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 30px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding-bottom: 15px;
}

.node-id {
  color: rgba(255, 255, 255, 0.3);
  font-family: monospace;
}
.node-year {
  color: #4a9eff;
  font-weight: bold;
}

.node-title {
  color: #FFF;
  font-size: 24px;
  line-height: 1.4;
  margin: 0 0 15px 0;
  font-weight: 300;
}

.node-type {
  display: inline-block;
  padding: 4px 10px;
  font-size: 10px;
  letter-spacing: 1px;
  text-transform: uppercase;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  margin-bottom: 30px;
}
.node-type.insight, .node-type.unique { color: #ffd700; border: 1px solid rgba(255, 215, 0, 0.3); }
.node-type.consensus { color: #00f2ff; border: 1px solid rgba(0, 242, 255, 0.3); }
.node-type.variable { color: #bf7aff; border: 1px solid rgba(191, 122, 255, 0.3); }

.node-desc {
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
  line-height: 1.8;
  flex-grow: 1;
}

.panel-footer {
  margin-top: auto;
  padding-top: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.stat-row {
  display: flex;
  align-items: center;
  gap: 15px;
  color: rgba(255, 255, 255, 0.4);
  font-size: 10px;
  letter-spacing: 2px;
}

.bar {
  flex-grow: 1;
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
}
.fill {
  height: 100%;
  background: #4a9eff;
  box-shadow: 0 0 10px #4a9eff;
}

/* Transitions */
.slide-right-enter-active, .slide-right-leave-active {
  transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.slide-right-enter-from, .slide-right-leave-to {
  transform: translateX(100%);
}
</style>
