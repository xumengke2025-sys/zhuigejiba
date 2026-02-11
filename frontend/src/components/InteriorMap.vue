<template>
  <div class="interior-map-wrapper" ref="wrapperRef">
    <canvas ref="canvasRef"></canvas>
    <div v-if="tooltip.visible" 
         class="map-tooltip parchment-tooltip"
         :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }">
      <h3>{{ tooltip.title }}</h3>
      <p v-if="tooltip.desc" class="desc">{{ tooltip.desc }}</p>
      <div v-if="tooltip.events.length" class="events-list">
        <div v-for="ev in tooltip.events" :key="ev.id" class="event-item">
          <span class="event-dot"></span>
          <div class="event-content">
            <span class="event-chars" v-if="ev.characters && ev.characters.length">[{{ ev.characters.join(', ') }}]</span>
            <span class="event-desc">{{ ev.description }}</span>
          </div>
        </div>
      </div>
    </div>
    
    <button class="back-btn" @click="$emit('back')">
      ← 返回大地图
    </button>
    
    <div class="location-title">
      {{ locationData.label || locationData.id }} - 内部详图
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  locationData: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['back'])

const wrapperRef = ref(null)
const canvasRef = ref(null)
const tooltip = ref({ visible: false, x: 0, y: 0, title: '', desc: '', events: [] })

let ctx = null
let width = 800
let height = 600
let transform = d3.zoomIdentity

// Theme Colors (Matching CanvasMap)
const theme = {
  bg: '#e8dcb5',
  wall: '#3d2b1f',
  floor: '#dcd0b6', // Slightly darker than bg
  ink: '#2c1b18',
  highlight: '#c5a059',
  red: '#8b0000'
}

const render = () => {
  if (!ctx) return
  const w = width
  const h = height
  
  ctx.clearRect(0, 0, w, h)
  
  // 1. Parchment Background
  ctx.fillStyle = theme.bg;
  ctx.fillRect(0, 0, w, h);
  
  // Background Grid (Architectural feel)
  ctx.strokeStyle = 'rgba(60, 45, 30, 0.05)';
  ctx.lineWidth = 1;
  const gridSize = 40;
  ctx.beginPath();
  for(let gx = 0; gx <= w; gx += gridSize) {
    ctx.moveTo(gx, 0); ctx.lineTo(gx, h);
  }
  for(let gy = 0; gy <= h; gy += gridSize) {
    ctx.moveTo(0, gy); ctx.lineTo(w, gy);
  }
  ctx.stroke();

  // Vignette
  const grad = ctx.createRadialGradient(w/2, h/2, Math.max(w,h)*0.5, w/2, h/2, Math.max(w,h)*0.95);
  grad.addColorStop(0, 'rgba(0,0,0,0)');
  grad.addColorStop(1, 'rgba(50, 30, 10, 0.4)');
  ctx.fillStyle = grad;
  ctx.globalCompositeOperation = 'multiply';
  ctx.fillRect(0, 0, w, h);
  ctx.globalCompositeOperation = 'source-over';

  ctx.save()
  ctx.translate(transform.x, transform.y)
  ctx.scale(transform.k, transform.k)

  const subMap = props.locationData.sub_map || { nodes: [], edges: [] }
  const nodes = subMap.nodes || []
  const edges = subMap.edges || []

  // 2. Draw Corridors/Paths (Edges)
  ctx.strokeStyle = 'rgba(60, 45, 30, 0.2)';
  ctx.lineWidth = 16; // Wider paths
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  
  edges.forEach(e => {
    const s = nodes.find(n => n.id === e.source);
    const t = nodes.find(n => n.id === e.target);
    if (s && t) {
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      ctx.stroke();
      
      // Dashed center line for paths
      ctx.save();
      ctx.strokeStyle = 'rgba(60, 45, 30, 0.3)';
      ctx.lineWidth = 1;
      ctx.setLineDash([5, 5]);
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      ctx.stroke();
      ctx.restore();
    }
  });

  // 3. Draw Nodes (Rooms/Places)
  nodes.forEach(n => {
    let rw = 120, rh = 80;
    
    // Resolve visual type
    let vType = 'room';
    const t = String(n.kind || n.type || '').toLowerCase();
    if (t === 'plaza' || /[场坛台市街]/.test(t)) vType = 'plaza';
    else if (t === 'gate' || /[门户关]/.test(t)) vType = 'gate';
    else if (t === 'path' || /[廊道阶梯]/.test(t)) vType = 'path';
    else if (t === 'hall' || /[宫殿堂]/.test(t)) vType = 'hall';
    else if (t === 'pavilion' || /[亭榭]/.test(t)) vType = 'pavilion';

    // Customize size/shape based on type
    if (vType === 'plaza') { rw = 160; rh = 120; }
    else if (vType === 'gate') { rw = 100; rh = 40; }
    else if (vType === 'path') { rw = 40; rh = 40; }
    else if (vType === 'hall') { rw = 140; rh = 100; }
    else if (vType === 'pavilion') { rw = 60; rh = 60; }
    
    const x = n.x - rw/2;
    const y = n.y - rh/2;

    // Floor
    ctx.fillStyle = theme.floor;
    // For plaza, maybe a different color
    if (vType === 'plaza') ctx.fillStyle = '#e0d5b0';
    
    if (vType === 'path') {
      // Path node is just a small circle/spot
      ctx.beginPath();
      ctx.arc(n.x, n.y, 15, 0, Math.PI*2);
      ctx.fill();
      ctx.stroke();
    } else {
      // Rectangular rooms/buildings
      ctx.fillRect(x, y, rw, rh);
      
      // Walls (Hand-drawn style box with double line)
      ctx.strokeStyle = theme.wall;
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.rect(x, y, rw, rh);
      ctx.stroke();
      
      // Inner decorative line
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.rect(x+4, y+4, rw-8, rh-8);
      ctx.stroke();
    }

    // Label
    ctx.fillStyle = theme.ink;
    ctx.font = vType === 'plaza' ? 'bold 20px "IM Fell English SC", serif' : 'bold 16px "IM Fell English SC", serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(n.label, n.x, n.y - (vType === 'path' ? 25 : 10));

    // Type Icon/Text
    if (vType !== 'path') {
      ctx.font = 'italic 12px serif';
      ctx.fillStyle = 'rgba(44, 27, 24, 0.7)';
      ctx.fillText(n.kind || n.type || 'Room', n.x, n.y + 10);
    }
    
    // Events Indicator
    const events = (subMap.events || []).filter(e => e.location_id === n.id);
    if (events.length > 0) {
      const indicatorX = n.x + rw/2 - 10;
      const indicatorY = n.y - rh/2 + 10;
      
      ctx.beginPath();
      ctx.arc(indicatorX, indicatorY, 8, 0, Math.PI*2);
      ctx.fillStyle = theme.red;
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1;
      ctx.stroke();
      
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 11px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(events.length, indicatorX, indicatorY + 1);
    }
  });

  ctx.restore()
}

const handleInteract = () => {
  const canvas = canvasRef.value
  const selection = d3.select(canvas)
  
  const zoom = d3.zoom()
    .scaleExtent([0.5, 3])
    .on('zoom', (e) => {
      transform = e.transform
      requestAnimationFrame(render)
    })
  
  selection.call(zoom).on('dblclick.zoom', null)

  selection.on('mousemove', (e) => {
    const [mx, my] = d3.pointer(e)
    // Inverse transform
    const x = (mx - transform.x) / transform.k
    const y = (my - transform.y) / transform.k
    
    const subMap = props.locationData.sub_map || { nodes: [] }
    const hit = subMap.nodes.find(n => {
       let rw = 120, rh = 80;
       
       let vType = 'room';
       const t = String(n.type || '').toLowerCase();
       if (t === 'plaza' || /[场坛台市街]/.test(t)) vType = 'plaza';
       else if (t === 'gate' || /[门户关]/.test(t)) vType = 'gate';
       else if (t === 'path' || /[廊道阶梯]/.test(t)) vType = 'path';
       else if (t === 'hall' || /[宫殿堂]/.test(t)) vType = 'hall';
       else if (t === 'pavilion' || /[亭榭]/.test(t)) vType = 'pavilion';

       if (vType === 'plaza') { rw = 160; rh = 120; }
       else if (vType === 'gate') { rw = 100; rh = 40; }
       else if (vType === 'path') { rw = 40; rh = 40; }
       else if (vType === 'hall') { rw = 140; rh = 100; }
       else if (vType === 'pavilion') { rw = 60; rh = 60; }

       return x >= n.x - rw/2 && x <= n.x + rw/2 &&
              y >= n.y - rh/2 && y <= n.y + rh/2;
    })

    if (hit) {
      canvas.style.cursor = 'pointer'
      const events = (subMap.events || []).filter(ev => ev.location_id === hit.id)
      
      tooltip.value = {
        visible: true,
        x: mx + 15,
        y: my + 15,
        title: hit.label,
        desc: hit.description || hit.desc,
        events: events
      }
    } else {
      canvas.style.cursor = 'default'
      tooltip.value.visible = false
    }
  })
}

onMounted(() => {
  if (!canvasRef.value) return
  ctx = canvasRef.value.getContext('2d')
  
  const resize = () => {
    if (wrapperRef.value) {
      width = wrapperRef.value.clientWidth
      height = wrapperRef.value.clientHeight
      canvasRef.value.width = width
      canvasRef.value.height = height
      render()
    }
  }
  
  window.addEventListener('resize', resize)
  resize()
  
  handleInteract()
})
</script>

<style scoped>
.interior-map-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  background: #e8dcb5;
  overflow: hidden;
}

.back-btn {
  position: absolute;
  top: 20px;
  left: 20px;
  background: #3d2b1f;
  color: #e8dcc5;
  border: 2px solid #c5a059;
  padding: 8px 16px;
  font-family: "IM Fell English SC", Georgia, "Times New Roman", serif;
  font-size: 16px;
  cursor: pointer;
  box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
  transition: all 0.2s;
  z-index: 100;
}
.back-btn:hover {
  background: #5c4033;
  transform: translateY(-2px);
}

.location-title {
  position: absolute;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  font-family: "IM Fell English SC", Georgia, "Times New Roman", serif;
  font-size: 24px;
  font-weight: bold;
  color: #3d2b1f;
  text-shadow: 0 1px 2px rgba(255,255,255,0.5);
  pointer-events: none;
}

.parchment-tooltip {
  position: absolute;
  background: #fdf5e6;
  border: 1px solid #8b4513;
  padding: 10px;
  border-radius: 4px;
  box-shadow: 3px 3px 10px rgba(0,0,0,0.3);
  pointer-events: none;
  max-width: 250px;
  z-index: 999;
  font-family: serif;
}
.parchment-tooltip h3 {
  margin: 0 0 5px 0;
  color: #3d2b1f;
  font-size: 16px;
  border-bottom: 1px solid #ccc;
  padding-bottom: 3px;
}
.parchment-tooltip .desc {
  font-size: 13px;
  color: #555;
  font-style: italic;
  margin-bottom: 8px;
}
.events-list {
  max-height: 200px;
  overflow-y: auto;
  margin-top: 5px;
  border-top: 1px dashed #ccc;
  padding-top: 5px;
}
.events-list::-webkit-scrollbar {
  width: 4px;
}
.events-list::-webkit-scrollbar-thumb {
  background: #8b4513;
  border-radius: 2px;
}
.event-item {
  font-size: 12px;
  color: #333;
  margin-bottom: 6px;
  display: flex;
  align-items: flex-start;
}
.event-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.event-chars {
  color: #8b0000;
  font-weight: bold;
  font-size: 11px;
}
.event-desc {
  line-height: 1.4;
}
.event-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  background: #8b0000;
  border-radius: 50%;
  margin-right: 6px;
  margin-top: 4px;
  flex-shrink: 0;
}
</style>
