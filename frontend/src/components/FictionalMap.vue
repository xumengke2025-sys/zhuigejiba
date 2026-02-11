<template>
  <div class="fictional-map" ref="containerRef">
    <svg
      v-if="simulationNodes.length > 0"
      :viewBox="viewBox"
      preserveAspectRatio="xMidYMid meet"
      :class="['svg parchment-theme', `theme-${theme}`]"
      @click="handleBgClick"
    >
      <defs>
        <filter id="ink-blur">
          <feGaussianBlur in="SourceGraphic" stdDeviation="0.4" />
        </filter>
        <filter id="paper-texture">
          <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="5" result="noise" />
          <feDiffuseLighting in="noise" lighting-color="#fdf5e6" surfaceScale="2">
            <feDistantLight azimuth="45" elevation="60" />
          </feDiffuseLighting>
          <feComposite operator="arithmetic" k1="1" k2="0" k3="0" k4="0" in="SourceGraphic" in2="noise" />
        </filter>
        <!-- Enhanced Map Border Wobble -->
        <filter id="border-wobble">
          <feTurbulence type="fractalNoise" baseFrequency="0.03" numOctaves="3" result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="3" />
        </filter>
        <!-- Terrain Symbols -->
        <symbol id="mountain-symbol" viewBox="0 0 20 20">
          <path d="M2,18 L10,4 L18,18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" />
          <path d="M6,12 L10,8 L14,14" fill="none" stroke="currentColor" stroke-width="1" opacity="0.6" />
        </symbol>
        <symbol id="tree-symbol" viewBox="0 0 20 20">
          <circle cx="10" cy="8" r="6" fill="currentColor" opacity="0.2" />
          <path d="M10,18 L10,8 M6,10 Q10,6 14,10" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
        </symbol>
        <symbol id="grass-symbol" viewBox="0 0 20 20">
          <path d="M5,15 Q8,10 10,15 M10,15 Q12,8 15,15" fill="none" stroke="currentColor" stroke-width="1" opacity="0.6" />
        </symbol>
        <symbol id="city-symbol" viewBox="0 0 24 24">
           <path d="M4,20 L4,8 L12,4 L20,8 L20,20 L16,20 L16,14 L8,14 L8,20 Z" fill="none" stroke="currentColor" stroke-width="1.5" />
           <rect x="10" y="16" width="4" height="4" fill="currentColor" opacity="0.3" />
        </symbol>
        
        <!-- Arrow marker for directed edges -->
        <marker id="arrow" viewBox="0 0 10 10" refX="18" refY="5"
          markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#5a4a42" opacity="0.8"/>
        </marker>
      </defs>
      
      <!-- Parchment Background -->
      <rect x="0" y="0" width="100%" height="100%" :fill="background.base" />
      
      <!-- Map Group for Zoom/Pan -->
      <g ref="mapGroup">
        <!-- Voronoi Regions (Territories) -->
        <g class="regions" v-if="simulationNodes.length > 0">
          <g v-for="region in voronoiRegions" :key="`region-${region.id}`">
             <path
              :d="region.path"
              :fill="region.color"
              stroke="#8b7d6b"
              stroke-width="1.5"
              stroke-opacity="0.6"
              filter="url(#border-wobble)"
              opacity="0.9"
              style="mix-blend-mode: multiply;" 
            />
            <!-- Terrain Decorators -->
            <g v-if="region.biome === 'mountain'" class="terrain mountain" :transform="`translate(${region.x - 20}, ${region.y - 20}) scale(2)`" opacity="0.8" style="color: #4a3b2a;">
              <use href="#mountain-symbol" />
              <use href="#mountain-symbol" x="12" y="5" transform="scale(0.8)" />
              <use href="#mountain-symbol" x="-8" y="8" transform="scale(0.7)" />
            </g>
            <g v-if="region.biome === 'forest'" class="terrain forest" :transform="`translate(${region.x - 15}, ${region.y - 15}) scale(1.5)`" opacity="0.7" style="color: #2d4a3e;">
              <use href="#tree-symbol" />
              <use href="#tree-symbol" x="10" y="2" transform="scale(0.9)" />
              <use href="#tree-symbol" x="5" y="10" transform="scale(0.8)" />
            </g>
            <g v-if="region.biome === 'plain'" class="terrain grass" :transform="`translate(${region.x - 10}, ${region.y}) scale(1.2)`" opacity="0.5" style="color: #5a6b4a;">
              <use href="#grass-symbol" />
              <use href="#grass-symbol" x="15" y="-5" />
            </g>
          </g>
        </g>

        <!-- World Relations (Edges) -->
        <g class="edges" v-if="showRelations">
          <line
            v-for="(e, i) in simulationLinks"
            :key="`e-${i}`"
            :x1="e.source.x"
            :y1="e.source.y"
            :x2="e.target.x"
            :y2="e.target.y"
            stroke="#5a4a42"
            stroke-width="1"
            stroke-dasharray="3,3"
            opacity="0.4"
            marker-end="url(#arrow)"
            filter="url(#ink-blur)"
          />
        </g>

        <!-- Character Routes (Polylines) -->
        <g class="routes" v-if="showRoutes">
          <path
            v-for="(route, i) in visibleRoutes"
            :key="`r-${i}`"
            :d="getRoutePath(route)"
            stroke="#8b0000"
            stroke-width="2"
            fill="none"
            stroke-linecap="round"
            filter="url(#ink-blur)"
            opacity="0.6"
            class="route-path"
          />
        </g>

        <!-- Nodes -->
        <g class="nodes">
          <g
            v-for="n in simulationNodes"
            :key="n.id"
            class="node"
            :transform="`translate(${n.x},${n.y})`"
            @click.stop="handleNodeClick(n)"
            @mouseenter="handleNodeEnter(n, $event)"
            @mouseleave="handleNodeLeave"
            @mousedown.stop="dragStart($event, n)"
            style="cursor: grab;"
          >
            <!-- City Icon -->
            <use href="#city-symbol" x="-12" y="-12" width="24" height="24" class="city-icon" style="color: #3d2b1f;" />
            
            <text 
              dy="20"
              text-anchor="middle"
              fill="#2c1b18" 
              font-family="'IM Fell English SC', 'Georgia', serif" 
              font-weight="bold" 
              font-size="14"
              class="node-label"
              style="pointer-events: none; letter-spacing: 1px;"
            >{{ n.label }}</text>
          </g>
        </g>
      </g>
      
      <!-- Overlays (Texture & Vignette) - Placed after content to affect it -->
      <rect x="0" y="0" width="100%" height="100%" filter="url(#paper-texture)" :opacity="background.textureOpacity" style="mix-blend-mode: multiply; pointer-events: none;" />
      <rect x="0" y="0" width="100%" height="100%" fill="url(#vignette)" style="pointer-events: none; mix-blend-mode: multiply;" />
    </svg>
    <div v-else class="empty">没有虚拟地图数据</div>

    <!-- Custom Tooltip -->
    <div v-if="tooltip.visible" class="map-tooltip" :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }">
      <div class="title">{{ tooltip.title }}</div>
      <div v-if="tooltip.events.length" class="events">
        <div v-for="(e, i) in tooltip.events" :key="i" class="event-item">
          <span class="chars" v-if="e.characters && e.characters.length">[{{ e.characters.join(',') }}]</span>
          <span class="summary">{{ e.summary }}</span>
        </div>
      </div>
      <div v-else class="no-event">暂无事件</div>
    </div>
  </div>
</template>

<script setup>
// import * as d3 from 'd3'
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'

let d3 = null

const props = defineProps({
  mapData: { type: Object, default: null },
  events: { type: Array, default: () => [] },
  selectedCharacter: { type: String, default: '' },
  focusLocationId: { type: String, default: '' },
  showRelations: { type: Boolean, default: true },
  showRoutes: { type: Boolean, default: true }
})

const emit = defineEmits(['select-location'])

const containerRef = ref(null)
const mapGroup = ref(null)
const width = ref(800)
const height = ref(600)
const viewBox = computed(() => `0 0 ${width.value} ${height.value}`)

// D3 Simulation State
const simulationNodes = ref([])
const simulationLinks = ref([])
const voronoiRegions = ref([])
let simulation = null
let zoomBehavior = null

const themePalette = {
  default: { 
    base: '#f4e4bc', textureOpacity: 0.4, wash: '#e7d6b3', washOpacity: 0.12, ink: '#6b5a4a', inkOpacity: 0.06,
    regionColors: ['#e8dcc5', '#e0d2b4', '#d9ccae', '#ead8b5'] 
  },
  xianxia: { 
    base: '#f0f4f4', textureOpacity: 0.3, wash: '#d1e0e5', washOpacity: 0.2, ink: '#2f4f4f', inkOpacity: 0.1,
    regionColors: ['#eef5f5', '#e0ecec', '#d5e4e4', '#f2f8f8']
  },
  wuxia: { 
    base: '#f4e4bc', textureOpacity: 0.4, wash: '#d4b483', washOpacity: 0.2, ink: '#5a4632', inkOpacity: 0.1,
    regionColors: ['#eadbc8', '#e4d0b6', '#dcc4a4', '#f2e6d2']
  },
  historical: { 
    base: '#fdf5e6', textureOpacity: 0.4, wash: '#dcc6a0', washOpacity: 0.15, ink: '#5c4033', inkOpacity: 0.1,
    regionColors: ['#f5e6cc', '#eeddbb', '#e6d4aa', '#faeec0']
  },
  fantasy: { 
    base: '#f1e8ff', textureOpacity: 0.3, wash: '#b7a6d7', washOpacity: 0.14, ink: '#6a5a8f', inkOpacity: 0.08,
    regionColors: ['#eaddff', '#e0d0ff', '#d8c8f8', '#efe8ff']
  },
  scifi: { 
    base: '#1d2431', textureOpacity: 0.15, wash: '#2c4a6b', washOpacity: 0.18, ink: '#7bb7ff', inkOpacity: 0.08,
    regionColors: ['#232b3a', '#2a3242', '#202836', '#252e3e']
  },
  urban: { 
    base: '#f2f4f8', textureOpacity: 0.2, wash: '#b5bcc6', washOpacity: 0.12, ink: '#3b434c', inkOpacity: 0.05,
    regionColors: ['#eaecf0', '#e2e5ea', '#dee1e6', '#f4f6f9']
  }
}

const detectTheme = () => {
  const texts = []
  if (props.mapData?.world?.name) texts.push(props.mapData.world.name)
  for (const n of props.mapData?.nodes || []) {
    if (n.label) texts.push(n.label)
    if (n.location_id) texts.push(n.location_id)
  }
  for (const e of props.events || []) {
    if (e.summary) texts.push(e.summary)
    if (e.evidence) texts.push(e.evidence)
  }
  const text = texts.join(' ').toLowerCase()
  const rules = [
    { key: 'xianxia', words: ['仙', '修真', '灵', '宗', '御剑', '剑气', '法宝', '丹', '洞府', '妖', '魔', '天劫', '灵气'] },
    { key: 'wuxia', words: ['江湖', '武林', '门派', '掌门', '镖', '帮派', '剑客', '侠'] },
    { key: 'historical', words: ['朝廷', '皇帝', '皇后', '王朝', '王爷', '将军', '御史', '都城', '京城'] },
    { key: 'scifi', words: ['星舰', '宇宙', '量子', '虫洞', '外星', '太空', '机器人', 'ai', '人工智能', '基地', '舰队', '星际'] },
    { key: 'urban', words: ['都市', '公司', '写字楼', '地铁', '公寓', '警局', '医院', '校园', '律师', '记者'] },
    { key: 'fantasy', words: ['魔法', '精灵', '巨龙', '王国', '魔王', '法师', '骑士', '圣殿'] }
  ]
  for (const rule of rules) {
    if (rule.words.some(w => text.includes(w))) return rule.key
  }
  return 'default'
}

const theme = computed(() => detectTheme())
const background = computed(() => themePalette[theme.value] || themePalette.default)

// Filtered Data based on props
const filteredData = computed(() => {
  const allNodes = (props.mapData?.nodes || []).filter(n => n && n.location_id)
  const selected = (props.selectedCharacter || '').trim()
  
  let nodes = allNodes
  if (selected) {
    nodes = allNodes.filter(n => {
      const locEvents = (props.events || []).filter(e => e.location_id === n.location_id)
      return locEvents.some(e => e.characters && e.characters.includes(selected))
    })
  }
  
  const nodeIds = new Set(nodes.map(n => n.location_id))
  
  // Relations (Edges)
  const edges = (props.mapData?.edges || []).filter(e => 
    e && e.a && e.b && nodeIds.has(e.a) && nodeIds.has(e.b)
  )

  // Polylines (Routes)
  const polylines = (props.mapData?.polylines || []).filter(p => {
    if (selected && p.character !== selected) return false
    return nodeIds.has(p.from_location) && nodeIds.has(p.to_location)
  })

  return { nodes, edges, polylines }
})

// Initialize and run D3 simulation
const initSimulation = () => {
  if (!d3) return
  if (simulation) simulation.stop()

  const data = filteredData.value
  const w = width.value
  const h = height.value

  // Deep copy to avoid mutating props, map location_id to id for d3
  const nodes = data.nodes.map(n => ({ 
    id: n.location_id, 
    label: n.label,
    // Use existing xy if available as hint, else random center
    x: w / 2 + (Math.random() - 0.5) * 50,
    y: h / 2 + (Math.random() - 0.5) * 50
  }))

  const links = data.edges.map(e => ({
    source: e.a,
    target: e.b,
    type: e.type,
    evidence: e.evidence
  }))

  simulationNodes.value = nodes
  simulationLinks.value = links

  simulation = d3.forceSimulation(nodes)
    .force("charge", d3.forceManyBody().strength(-300))
    .force("center", d3.forceCenter(w / 2, h / 2))
    .force("collide", d3.forceCollide().radius(30))
    .force("link", d3.forceLink(links).id(d => d.id).distance(100))
    // Custom directional forces
    .force("direction", (alpha) => {
      for (const link of links) {
        const source = link.source
        const target = link.target
        const type = (link.type || '').toLowerCase()
        
        const k = alpha * 0.5 // Strength factor

        if (type === 'north_of') { // Source is North of Target (Source.y < Target.y)
             if (source.y > target.y - 50) {
                 source.vy -= k * 2
                 target.vy += k * 2
             }
        } else if (type === 'south_of') {
             if (source.y < target.y + 50) {
                 source.vy += k * 2
                 target.vy -= k * 2
             }
        } else if (type === 'west_of') {
             if (source.x > target.x - 50) {
                 source.vx -= k * 2
                 target.vx += k * 2
             }
        } else if (type === 'east_of') {
             if (source.x < target.x + 50) {
                 source.vx += k * 2
                 target.vx -= k * 2
             }
        }
      }
    })
    .on("tick", () => {
      // Trigger reactivity
      simulationNodes.value = [...nodes] 
      simulationLinks.value = [...links]
      
      // Calculate Voronoi Regions
      if (nodes.length > 2) {
        const delaunay = d3.Delaunay.from(nodes, d => d.x, d => d.y)
        // Make Voronoi large enough to cover zoomable area
        const voronoi = delaunay.voronoi([-w, -h, w * 3, h * 3])
        
        const palette = themePalette[theme.value]?.regionColors || themePalette.default.regionColors
        
        // Pseudo-random biome generation
        const getBiome = (x, y) => {
          const val = Math.sin(x * 0.01) + Math.cos(y * 0.01) + Math.sin(x * y * 0.0001) * 2;
          if (val > 1.5) return 'mountain'
          if (val < -1.0) return 'forest'
          return 'plain'
        }

        voronoiRegions.value = nodes.map((n, i) => {
          // Simple consistent color hashing
          const colorIndex = (n.id.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)) % palette.length
          return {
            id: n.id,
            path: voronoi.renderCell(i),
            color: palette[colorIndex],
            x: n.x,
            y: n.y,
            biome: getBiome(n.x, n.y)
          }
        })
      }
    })
}

// Dragging logic
const dragStart = (event, node) => {
  if (!event.active) simulation.alphaTarget(0.3).restart()
  node.fx = node.x
  node.fy = node.y
  
  const move = (e) => {
    node.fx = e.clientX - containerRef.value.getBoundingClientRect().left
    node.fy = e.clientY - containerRef.value.getBoundingClientRect().top
  }
  
  const end = () => {
    if (!event.active) simulation.alphaTarget(0)
    node.fx = null
    node.fy = null
    document.removeEventListener('mousemove', move)
    document.removeEventListener('mouseup', end)
  }
  
  document.addEventListener('mousemove', move)
  document.addEventListener('mouseup', end)
}

// Routes visualization
const visibleRoutes = computed(() => {
  return filteredData.value.polylines.map(p => {
    const sourceNode = simulationNodes.value.find(n => n.id === p.from_location)
    const targetNode = simulationNodes.value.find(n => n.id === p.to_location)
    if (!sourceNode || !targetNode) return null
    return { source: sourceNode, target: targetNode, character: p.character }
  }).filter(Boolean)
})

const getRoutePath = (route) => {
  const dx = route.target.x - route.source.x
  const dy = route.target.y - route.source.y
  const dr = Math.sqrt(dx * dx + dy * dy)
  // Curve the path slightly for aesthetic
  return `M${route.source.x},${route.source.y}A${dr},${dr} 0 0,1 ${route.target.x},${route.target.y}`
}

// Tooltip logic
const tooltip = ref({ visible: false, x: 0, y: 0, title: '', events: [] })

const handleNodeEnter = (n, event) => {
  const rect = event.target.getBoundingClientRect()
  const parentRect = containerRef.value.getBoundingClientRect()
  const locEvents = (props.events || []).filter(e => e.location_id === n.id)
  
  tooltip.value = {
    visible: true,
    x: rect.left - parentRect.left + 20,
    y: rect.top - parentRect.top,
    title: n.label,
    events: locEvents
  }
}

const handleNodeLeave = () => {
  tooltip.value.visible = false
}

const handleNodeClick = (n) => {
  emit('select-location', n.id)
}

const handleBgClick = () => {
  // Optional: clear selection
}

// Lifecycle
watch(() => [props.mapData, props.selectedCharacter], () => {
  initSimulation()
}, { deep: true })

onMounted(async () => {
  try {
    d3 = await import('d3')
    if (props.mapData) {
      initSimulation()
    }
  } catch (e) {
    console.error('Failed to load d3', e)
  }
})

onUnmounted(() => {
  if (simulation) simulation.stop()
})
</script>

<style scoped>
/* Google Fonts mirror used in index.html */

.fictional-map {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
  user-select: none;
  background-color: #0b0c10; /* Outer dark bg */
}
.svg {
  width: 100%;
  height: 100%;
  cursor: grab;
  box-shadow: inset 0 0 100px rgba(0,0,0,0.5); /* Vignette effect */
}
.svg:active {
  cursor: grabbing;
}
.empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #8b0000;
  font-family: "IM Fell English SC", Georgia, "Times New Roman", serif;
  font-size: 24px;
  font-style: italic;
  letter-spacing: 2px;
}
.map-tooltip {
  position: absolute;
  z-index: 1000;
  background: rgba(244, 228, 188, 0.95);
  border: 2px solid #5a4632;
  border-radius: 4px;
  padding: 12px;
  box-shadow: 4px 4px 12px rgba(0,0,0,0.4);
  pointer-events: none;
  min-width: 220px;
  max-width: 320px;
  max-height: 400px;
  overflow-y: auto;
  font-family: 'Georgia', serif;
  color: #3d2b1f;
}
.map-tooltip .title {
  font-weight: bold;
  font-family: "IM Fell English SC", Georgia, "Times New Roman", serif;
  font-size: 1.2em;
  border-bottom: 2px solid #5a4632;
  margin-bottom: 8px;
  padding-bottom: 4px;
  color: #2c1b18;
}
.event-item {
  margin-bottom: 6px;
  font-size: 0.95em;
  line-height: 1.4;
  border-bottom: 1px dashed rgba(90, 70, 50, 0.2);
  padding-bottom: 4px;
}
.event-item:last-child {
  border-bottom: none;
}
.chars {
  font-weight: bold;
  color: #8b0000;
  margin-right: 4px;
}
.more {
  font-size: 0.8em;
  color: #666;
  text-align: right;
  margin-top: 4px;
  font-style: italic;
}
.no-event {
  font-style: italic;
  opacity: 0.7;
}

.route-path {
  animation: dash 60s linear infinite;
  stroke-dasharray: 8, 6;
  filter: url(#ink-blur);
}

.node-label {
  paint-order: stroke;
  stroke: rgba(244, 228, 188, 0.8);
  stroke-width: 4px;
  stroke-linejoin: round;
  text-shadow: 0 1px 2px rgba(0,0,0,0.1);
}

.city-icon {
  filter: drop-shadow(0 1px 1px rgba(0,0,0,0.2));
}

@keyframes dash {
  to {
    stroke-dashoffset: -1000;
  }
}
</style>
