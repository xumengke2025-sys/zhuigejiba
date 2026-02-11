<template>
  <div class="canvas-map-wrapper" ref="wrapperRef">
    <!-- Parchment Texture Filter -->
    <svg width="0" height="0" style="position: absolute;">
      <filter id="paper-noise">
        <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="5" result="noise" />
        <feDiffuseLighting in="noise" lighting-color="#f4e4bc" surfaceScale="2">
          <feDistantLight azimuth="45" elevation="60" />
        </feDiffuseLighting>
      </filter>
    </svg>
    
    <div class="parchment-bg"></div>

    <canvas 
      ref="canvasRef"
      @pointerdown="onPointerDown"
      @pointerup="onPointerUp"
      @mousemove="onMouseMove"
    ></canvas>
    
    <!-- Custom Tooltip (Overlay) -->
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
    
    <div v-if="loading" class="loading-overlay">
      <div class="loading-text">正在绘制地图...</div>
    </div>

    <div class="map-legend scroll-style">
      <div class="scroll-rod top"></div>
      <div class="scroll-content">
        <div class="legend-title">图例</div>
        <div class="legend-grid">
          <div class="legend-item" v-for="item in legendItems" :key="item.label">
            <span class="legend-swatch" :style="{ background: item.color }"></span>
            <span class="legend-label">{{ item.label }}</span>
          </div>
        </div>
        <div class="legend-icons">
          <div class="legend-item" v-for="item in legendIconItems" :key="item.label">
            <span class="legend-icon" :class="`icon-${item.type}`"></span>
            <span class="legend-label">{{ item.label }}</span>
          </div>
        </div>
      </div>
      <div class="scroll-rod bottom"></div>
    </div>
    
    <!-- Click Effect (Wax Seal) -->
    <div v-if="clickEffect.visible" 
         class="click-effect-seal" 
         :style="{ left: clickEffect.x + 'px', top: clickEffect.y + 'px' }"
         @animationend="clickEffect.visible = false">
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  mapData: { type: Object, default: null },
  events: { type: Array, default: () => [] },
  selectedCharacter: { type: String, default: '' },
  visibleLocationIds: { type: Array, default: null }, // If provided, only these locations are visible
  focusLocationId: { type: String, default: '' },
  showRelations: { type: Boolean, default: true },
  showRoutes: { type: Boolean, default: true }
})

const emit = defineEmits(['select-location'])

const wrapperRef = ref(null)
const canvasRef = ref(null)
const loading = ref(false)
const clickEffect = ref({ visible: false, x: 0, y: 0 })
let hoveredNodeId = null

// --- Animation State ---
const animState = {
  active: false,
  lastTime: 0,
  dashOffset: 0,
  targetDashOffset: 0,
  time: 0,
  nodes: {}
}

// --- PRNG (Seeded Random) for Stability ---
class SeededRandom {
  constructor(seed) {
    this.seed = seed;
  }
  next() {
    this.seed = (this.seed * 9301 + 49297) % 233280;
    return this.seed / 233280;
  }
}
const MAP_SEED = 12345;
const WORLD_W = 2000;
const WORLD_H = 1500;

// --- State ---
let simulation = null
let transform = d3.zoomIdentity
let width = 800
let height = 600
let nodes = []
let links = []
let voronoiRegions = []
let rivers = []
let canvasContext = null
let offscreenCanvas = null
let resizeObserver = null
let zoomBehavior = null

const tooltip = ref({ visible: false, x: 0, y: 0, title: '', events: [] })

const legendItems = [
  { label: '海洋', color: '#7da0b6' },
  { label: '海岸', color: '#8fb3c2' },
  { label: '湖泊', color: '#86b6d8' },
  { label: '草原', color: '#a6bd7a' },
  { label: '森林', color: '#7da168' },
  { label: '荒漠', color: '#e8d8b6' },
  { label: '雪地', color: '#f8f8f8' }
]

const legendIconItems = [
  { label: '城镇', type: 'city' },
  { label: '山脉', type: 'mountain' },
  { label: '河流', type: 'river' },
  { label: '湖泊', type: 'lake' },
  { label: '峡谷', type: 'gorge' },
  { label: '林地', type: 'forest' },
  { label: '宫殿', type: 'temple' },
  { label: '遗迹', type: 'ruin' },
  { label: '矿脉', type: 'mine' },
  { label: '荒漠', type: 'desert' }
]

const themePalette = {
  bg: '#e8dcb5', // Antique Parchment
  waterDeep: '#2f4f4f', // Dark Slate Gray (Deep Ocean)
  waterMedium: '#466d6d', // Muted Cyan
  waterShallow: '#6b8e8e', // Faded Blue-Green
  border: '#3d2b1f', // Dark Brown
  ink: '#2c1b18', // Very Dark Brown
  gold: '#c5a059', // Dull Gold for accents
  red: '#8b0000', // Dark Red for seals/routes
  forest: '#2f3d26', // Dark Olive Green
  mountain: '#5a4632' // Bronze/Brown
}

const patterns = {};

const createBiomePatterns = () => {
    const createPatternCanvas = (w, h, drawFn) => {
        const c = document.createElement('canvas');
        c.width = w;
        c.height = h;
        const ctx = c.getContext('2d');
        drawFn(ctx, w, h);
        return ctx.createPattern(c, 'repeat');
    };

    // 1. Ocean Pattern (Subtle Waves)
    patterns.ocean = createPatternCanvas(60, 30, (ctx, w, h) => {
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        // Wave 1
        ctx.moveTo(10, 10);
        ctx.bezierCurveTo(20, 5, 30, 15, 40, 10);
        ctx.stroke();
        // Wave 2 (offset)
        ctx.beginPath();
        ctx.moveTo(30, 25);
        ctx.bezierCurveTo(40, 20, 50, 30, 60, 25);
        ctx.stroke();
    });

    // 2. Forest Pattern (Leafy Stippling)
    patterns.forest = createPatternCanvas(24, 24, (ctx, w, h) => {
        ctx.fillStyle = 'rgba(47, 61, 38, 0.15)'; 
        // Random blobs
        ctx.beginPath(); ctx.arc(4, 4, 3, 0, Math.PI*2); ctx.fill();
        ctx.beginPath(); ctx.arc(16, 10, 4, 0, Math.PI*2); ctx.fill();
        ctx.beginPath(); ctx.arc(8, 18, 2, 0, Math.PI*2); ctx.fill();
        ctx.beginPath(); ctx.arc(20, 20, 3, 0, Math.PI*2); ctx.fill();
    });

    // 3. Mountain Pattern (Rough Hatching)
    patterns.mountain = createPatternCanvas(16, 16, (ctx, w, h) => {
        ctx.strokeStyle = 'rgba(90, 70, 50, 0.1)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, h);
        ctx.lineTo(w, 0);
        ctx.stroke();
    });

    // 4. Swamp Pattern (Horizontal Dashes)
    patterns.swamp = createPatternCanvas(20, 20, (ctx, w, h) => {
        ctx.strokeStyle = 'rgba(60, 70, 60, 0.2)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(4, 10);
        ctx.lineTo(16, 10);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(5, 0);
        ctx.stroke();
    });
    
    // 5. Desert/Plains (Fine Grain)
    patterns.desert = createPatternCanvas(64, 64, (ctx, w, h) => {
        ctx.fillStyle = 'rgba(160, 120, 60, 0.15)';
        for(let i=0; i<16; i++) {
            ctx.fillRect(Math.random()*w, Math.random()*h, 1, 1);
        }
    });
    
    // 6. Aged Creases (Global overlay pattern)
    patterns.creases = createPatternCanvas(200, 200, (ctx, w, h) => {
        ctx.strokeStyle = 'rgba(0,0,0,0.03)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        // Random long lines
        ctx.moveTo(Math.random()*w, 0);
        ctx.lineTo(Math.random()*w, h);
        ctx.stroke();
    });
}


// --- NOISE ---
const PERM = new Uint8Array([151,160,137,91,90,15,131,13,201,95,96,53,194,233,7,225,140,36,103,30,69,142,8,99,37,240,21,10,23,190,6,148,247,120,234,75,0,26,197,62,94,252,219,203,117,35,11,32,57,177,33,88,237,149,56,87,174,20,125,136,171,168,68,175,74,165,71,134,139,48,27,166,77,146,158,231,83,111,229,122,60,211,133,230,220,105,92,41,55,46,245,40,244,102,143,54,65,25,63,161,1,216,80,73,209,76,132,187,208,89,18,169,200,196,135,130,116,188,159,86,164,100,109,198,173,186,3,64,52,217,226,250,124,123,5,202,38,147,118,126,255,82,85,212,207,206,59,227,47,16,58,17,182,189,28,42,223,183,170,213,119,248,152,2,44,154,163,70,221,153,101,155,167,43,172,9,129,22,39,253,19,98,108,110,79,113,224,232,178,185,112,104,218,246,97,228,251,34,242,193,238,210,144,12,191,179,162,241,81,51,145,235,249,14,239,107,49,192,214,31,181,199,106,157,184,84,204,176,115,121,50,45,127,4,150,254,138,236,205,93,222,114,67,29,24,72,243,141,128,195,78,66,215,61,156,180]);
const perm = new Uint8Array(512);
for(let i=0; i<512; i++) perm[i] = PERM[i & 255];
const fade = (t) => t * t * t * (t * (t * 6 - 15) + 10);
const lerp = (t, a, b) => a + t * (b - a);
const grad = (hash, x, y) => {
    const h = hash & 15;
    const u = h < 8 ? x : y;
    const v = h < 4 ? y : h === 12 || h === 14 ? x : 0;
    return ((h & 1) === 0 ? u : -u) + ((h & 2) === 0 ? v : -v);
}
const noise2d = (x, y) => {
    const X = Math.floor(x) & 255;
    const Y = Math.floor(y) & 255;
    x -= Math.floor(x);
    y -= Math.floor(y);
    const u = fade(x);
    const v = fade(y);
    const A = perm[X] + Y, AA = perm[A], AB = perm[A + 1],
          B = perm[X + 1] + Y, BA = perm[B], BB = perm[B + 1];
    return lerp(v, lerp(u, grad(perm[AA], x, y), grad(perm[BA], x - 1, y)),
                   lerp(u, grad(perm[AB], x, y - 1), grad(perm[BB], x - 1, y - 1)));
}
const fbm = (x, y, octaves = 6) => {
    let t = 0;
    let amp = 1;
    let freq = 0.005;
    let maxValue = 0;
    for(let i=0; i<octaves; i++){
        t += noise2d(x*freq, y*freq)*amp;
        maxValue += amp;
        amp *= 0.5;
        freq *= 2;
    }
    return t / maxValue;
}

// Biome Logic
const getBiome = (h, m) => {
  if (h < 0.2) return 'OCEAN';
  if (h < 0.25) return 'COAST';
  // Simplified biomes for the antique style
  return 'LAND'; 
}

const getBiomeColor = (biome) => {
    const colors = {
        'OCEAN': '#5a8f8e', // Teal
        'COAST': '#6fa3a1', // Lighter Teal
        'LAKE': '#7caeb0',
        'LAND': '#e6d5ac', // Parchment
        'SNOW': '#f0e6d2'  // Light parchment
    };
    return colors[biome] || '#e6d5ac';
}

// Helpers
const drawPaperTexture = (ctx, w, h) => {
  ctx.fillStyle = themePalette.bg;
  ctx.fillRect(0, 0, w, h);
  
  // Subtle grain
  ctx.save();
  ctx.globalAlpha = 0.03;
  for (let i = 0; i < w; i += 4) {
      for (let j = 0; j < h; j += 4) {
          if (Math.random() > 0.5) {
              ctx.fillStyle = '#000';
              ctx.fillRect(i, j, 2, 2);
          }
      }
  }
  ctx.restore();
}

const drawCompass = (ctx, w, h) => {
    const cx = w - 80
    const cy = h - 80
    const r = 40
    ctx.save()
    ctx.translate(cx, cy)
    
    // Outer Ring
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, Math.PI*2);
    ctx.strokeStyle = '#3d2b1f';
    ctx.lineWidth = 2;
    ctx.stroke();
    
    // Inner Ring
    ctx.beginPath();
    ctx.arc(0, 0, r*0.9, 0, Math.PI*2);
    ctx.strokeStyle = 'rgba(60, 45, 30, 0.5)';
    ctx.lineWidth = 1;
    ctx.stroke();

    // Star
    ctx.fillStyle = '#2c1b18'; // Dark Ink
    ctx.beginPath();
    for (let i = 0; i < 4; i++) {
        ctx.rotate(Math.PI / 2)
        ctx.moveTo(0, -r * 0.9)
        ctx.lineTo(r * 0.25, -r * 0.25)
        ctx.lineTo(0, 0)
        ctx.lineTo(-r * 0.25, -r * 0.25)
        ctx.closePath()
    }
    ctx.fill();
    
    // Gold Accents
    ctx.fillStyle = '#c5a059'; 
    ctx.beginPath();
    ctx.rotate(Math.PI / 4); // Offset for secondary points
    for (let i = 0; i < 4; i++) {
        ctx.rotate(Math.PI / 2)
        ctx.moveTo(0, -r * 0.6)
        ctx.lineTo(r * 0.15, -r * 0.15)
        ctx.lineTo(0, 0)
        ctx.lineTo(-r * 0.15, -r * 0.15)
        ctx.closePath()
    }
    ctx.fill();

    // N Label
    ctx.rotate(-Math.PI / 4); // Reset rotation
    ctx.fillStyle = '#8b0000';
    ctx.font = 'bold 24px "IM Fell English SC", serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('N', 0, -r - 15);
    
    ctx.restore()
}

const drawIcon = (ctx, type, x, y, size) => {
    ctx.save();
    ctx.translate(x, y);
    if (type === 'mountain') {
        // Hand-drawn mountain style (jagged peaks with hatching)
        const s = size * 1.3;
        ctx.beginPath();
        ctx.moveTo(-s, s*0.5);
        ctx.lineTo(-s*0.5, -s*0.3); // Left slope
        ctx.lineTo(-s*0.2, s*0.2); // Small dip
        ctx.lineTo(0, -s); // Peak
        ctx.lineTo(s*0.3, -s*0.2); // Right slope 1
        ctx.lineTo(s*0.6, -s*0.5); // Right slope 2
        ctx.lineTo(s, s*0.5); // Base right
        ctx.closePath();
        
        ctx.fillStyle = '#d6cdb8'; // Base color
        ctx.fill();
        
        ctx.strokeStyle = themePalette.mountain;
        ctx.lineWidth = 1.5;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        ctx.stroke();
        
        // Hatching shading (Shadow side)
        ctx.beginPath();
        ctx.strokeStyle = 'rgba(60, 50, 40, 0.4)';
        ctx.lineWidth = 0.8;
        // Right side hatching
        ctx.moveTo(0, -s);
        ctx.lineTo(s*0.2, s*0.5);
        ctx.moveTo(s*0.15, -s*0.6);
        ctx.lineTo(s*0.35, s*0.5);
        ctx.moveTo(s*0.3, -s*0.2);
        ctx.lineTo(s*0.5, s*0.5);
        ctx.stroke();

    } else if (type === 'tree') {
        // Detailed deciduous/pine mix
        const s = size * 1.1;
        
        // Trunk
        ctx.beginPath();
        ctx.moveTo(0, s*0.6);
        ctx.lineTo(0, s*0.9);
        ctx.strokeStyle = themePalette.border;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Foliage (Cloud-like for deciduous, jagged for pine - Randomize slightly?)
        // Let's stick to a stylized "bushy" tree for forests
        ctx.beginPath();
        ctx.arc(0, -s*0.2, s*0.5, 0, Math.PI*2);
        ctx.arc(-s*0.3, s*0.2, s*0.4, 0, Math.PI*2);
        ctx.arc(s*0.3, s*0.2, s*0.4, 0, Math.PI*2);
        
        ctx.fillStyle = themePalette.forest;
        ctx.fill();
        
        // Outline (Ink)
        ctx.strokeStyle = '#1a2b15';
        ctx.lineWidth = 1;
        ctx.stroke();
        
        // Highlight
        ctx.beginPath();
        ctx.arc(-s*0.1, -s*0.3, s*0.1, 0, Math.PI*2);
        ctx.fillStyle = 'rgba(255,255,255,0.1)';
        ctx.fill();
    } else if (type === 'wave') {
        // Decorative Ocean Wave
        const s = size;
        ctx.beginPath();
        ctx.moveTo(-s, 0);
        ctx.quadraticCurveTo(-s*0.5, -s*0.8, 0, 0);
        ctx.quadraticCurveTo(s*0.5, -s*0.8, s, 0);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
        ctx.lineWidth = 1.5;
        ctx.stroke();
        
        // Underline
        ctx.beginPath();
        ctx.moveTo(-s*0.8, s*0.3);
        ctx.quadraticCurveTo(0, s*0.5, s*0.8, s*0.3);
        ctx.strokeStyle = 'rgba(47, 79, 79, 0.4)'; // Dark teal shadow
        ctx.lineWidth = 1;
        ctx.stroke();
    } else if (type === 'castle') {
        // Medieval Castle
        const s = size * 1.2;
        ctx.fillStyle = '#e8dcc5';
        ctx.strokeStyle = '#2c1b18';
        ctx.lineWidth = 1.5;
        
        // Central Keep
        ctx.beginPath();
        ctx.rect(-s*0.4, -s*0.6, s*0.8, s*0.8);
        ctx.fill();
        ctx.stroke();
        
        // Battlements
        ctx.beginPath();
        ctx.moveTo(-s*0.5, -s*0.6);
        ctx.lineTo(s*0.5, -s*0.6);
        ctx.stroke();
        
        // Towers (Left/Right)
        ctx.beginPath();
        ctx.rect(-s*0.7, -s*0.4, s*0.3, s*0.6); // Left
        ctx.rect(s*0.4, -s*0.4, s*0.3, s*0.6);  // Right
        ctx.fill();
        ctx.stroke();
        
        // Roofs (Conical)
        ctx.beginPath();
        ctx.moveTo(-s*0.7, -s*0.4);
        ctx.lineTo(-s*0.55, -s*0.8);
        ctx.lineTo(-s*0.4, -s*0.4);
        ctx.fill();
        ctx.stroke();
        
        ctx.beginPath();
        ctx.moveTo(s*0.4, -s*0.4);
        ctx.lineTo(s*0.55, -s*0.8);
        ctx.lineTo(s*0.7, -s*0.4);
        ctx.fill();
        ctx.stroke();

        // Flag
        ctx.beginPath();
        ctx.moveTo(s*0.55, -s*0.8);
        ctx.lineTo(s*0.55, -s*1.1);
        ctx.lineTo(s*0.8, -s*0.95);
        ctx.lineTo(s*0.55, -s*0.9);
        ctx.stroke();

    } else if (type === 'tower') {
        // Watchtower
        const s = size * 1.2;
        ctx.fillStyle = '#e8dcc5';
        ctx.strokeStyle = '#2c1b18';
        ctx.lineWidth = 1.5;
        
        // Base
        ctx.beginPath();
        ctx.rect(-s*0.3, -s*0.8, s*0.6, s*1.0);
        ctx.fill();
        ctx.stroke();
        
        // Top
        ctx.beginPath();
        ctx.rect(-s*0.4, -s*0.9, s*0.8, s*0.2);
        ctx.fill();
        ctx.stroke();
        
    } else if (type === 'city') {
        // Walled City
        const s = size;
        ctx.fillStyle = '#e8dcc5';
        ctx.strokeStyle = '#2c1b18';
        ctx.lineWidth = 1.5;

        // Houses cluster
        ctx.beginPath();
        ctx.rect(-s*0.5, -s*0.4, s*0.4, s*0.4); // House 1
        ctx.rect(s*0.1, -s*0.6, s*0.3, s*0.5);  // House 2
        ctx.fill();
        ctx.stroke();
        
        // Roofs
        ctx.beginPath();
        ctx.moveTo(-s*0.5, -s*0.4);
        ctx.lineTo(-s*0.3, -s*0.7);
        ctx.lineTo(-s*0.1, -s*0.4);
        ctx.fill();
        ctx.stroke();
        
        ctx.beginPath();
        ctx.moveTo(s*0.1, -s*0.6);
        ctx.lineTo(s*0.25, -s*0.9);
        ctx.lineTo(s*0.4, -s*0.6);
        ctx.fill();
        ctx.stroke();

        // Wall
        ctx.beginPath();
        ctx.arc(0, 0, s*0.8, 0, Math.PI*2);
        ctx.strokeStyle = 'rgba(44, 27, 24, 0.6)';
        ctx.setLineDash([2, 2]);
        ctx.stroke();
        ctx.setLineDash([]);
    }
    ctx.restore();
}

const idSeed = (value) => {
    let h = 0;
    const s = String(value);
    for (let i = 0; i < s.length; i++) {
        h = (h * 31 + s.charCodeAt(i)) >>> 0;
    }
    return h;
}

const seededRand = (seed) => {
    let x = seed >>> 0;
    x = (x ^ 61) ^ (x >>> 16);
    x = x + (x << 3);
    x = x ^ (x >>> 4);
    x = x * 0x27d4eb2d;
    x = x ^ (x >>> 15);
    return (x >>> 0) / 4294967295;
}

const drawLocationIcon = (ctx, type, x, y) => {
    ctx.save();
    ctx.translate(x, y);
    ctx.lineWidth = 1.6;
    ctx.strokeStyle = '#2c1b18';
    ctx.fillStyle = '#e8dcc5';
    if (type === 'city') {
        drawIcon(ctx, 'castle', 0, -5, 12);
    } else if (type === 'mountain') {
        drawIcon(ctx, 'mountain', 0, -2, 10);
    } else if (type === 'river') {
        drawIcon(ctx, 'wave', 0, 0, 8);
    } else if (type === 'lake') {
        ctx.beginPath();
        ctx.ellipse(0, 2, 7, 4, 0, 0, Math.PI * 2);
        ctx.fillStyle = '#86b6d8';
        ctx.fill();
        ctx.strokeStyle = '#587a95';
        ctx.stroke();
    } else if (type === 'gorge') {
        ctx.beginPath();
        ctx.moveTo(-7, -6);
        ctx.lineTo(-2, 6);
        ctx.moveTo(2, -6);
        ctx.lineTo(7, 6);
        ctx.strokeStyle = '#6b4b3a';
        ctx.lineWidth = 2;
        ctx.stroke();
    } else if (type === 'forest') {
        drawIcon(ctx, 'tree', 0, 0, 8);
    } else if (type === 'temple') {
        drawIcon(ctx, 'tower', 0, -5, 10);
    } else if (type === 'ruin') {
        ctx.beginPath();
        ctx.moveTo(-6, -6);
        ctx.lineTo(6, -6);
        ctx.lineTo(4, 6);
        ctx.lineTo(-4, 6);
        ctx.closePath();
        ctx.stroke();
    } else if (type === 'mine') {
        ctx.beginPath();
        ctx.moveTo(0, -7);
        ctx.lineTo(7, 0);
        ctx.lineTo(0, 7);
        ctx.lineTo(-7, 0);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
    } else if (type === 'desert') {
        ctx.beginPath();
        ctx.moveTo(-8, 4);
        ctx.quadraticCurveTo(-2, -2, 4, 2);
        ctx.quadraticCurveTo(7, 4, 8, 6);
        ctx.strokeStyle = '#bfa97a';
        ctx.lineWidth = 2;
        ctx.stroke();
    } else {
        ctx.beginPath();
        ctx.arc(0, 0, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
    }
    ctx.restore();
}

const drawSubMapIndicator = (ctx, x, y) => {
    const time = Date.now() / 500;
    const pulse = (Math.sin(time * 4) + 1) / 2; // 0 to 1 fast pulse

    ctx.save();
    ctx.translate(x + 10, y - 10);
    
    // 1. Pulsing Glow (Outer)
    ctx.beginPath();
    ctx.arc(0, 0, 8 + pulse * 6, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(255, 215, 0, ${0.6 - pulse * 0.4})`; // Gold glow
    ctx.fill();

    // 2. Main Badge Background (Wax Seal Red)
    ctx.fillStyle = '#8b0000';
    ctx.beginPath();
    ctx.arc(0, 0, 9, 0, Math.PI * 2);
    ctx.fill();
    
    // 3. Gold Border
    ctx.strokeStyle = '#ffd700';
    ctx.lineWidth = 2;
    ctx.stroke();
    
    // 4. Icon (Grid)
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.rect(-4, -4, 8, 8); // Square box
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(0, -4); ctx.lineTo(0, 4); // Vertical line
    ctx.moveTo(-4, 0); ctx.lineTo(4, 0); // Horizontal line
    ctx.stroke();
    
    ctx.restore();
}

const areaTypes = new Set(['forest', 'gorge', 'desert', 'mountain', 'lake', 'river'])

const drawAreaMarker = (ctx, type, region, seed) => {
    const poly = region.polygon;
    if (!poly) return;

    ctx.save();
    
    // 1. Draw Cell Polygon (Subtle tint)
    ctx.beginPath();
    ctx.moveTo(poly[0][0], poly[0][1]);
    for (let i = 1; i < poly.length; i++) ctx.lineTo(poly[i][0], poly[i][1]);
    ctx.closePath();

    if (type === 'forest') ctx.fillStyle = 'rgba(110, 127, 94, 0.15)';
    else if (type === 'mountain') ctx.fillStyle = 'rgba(120, 100, 80, 0.15)';
    else if (type === 'desert') ctx.fillStyle = 'rgba(210, 180, 120, 0.2)';
    else if (type === 'gorge') ctx.fillStyle = 'rgba(90, 70, 50, 0.15)';
    else if (type === 'river') ctx.fillStyle = 'rgba(100, 130, 160, 0.2)';
    else if (type === 'lake') ctx.fillStyle = 'rgba(110, 150, 190, 0.3)';
    else ctx.fillStyle = 'rgba(140, 120, 100, 0.1)';
    
    ctx.fill();
    
    // Border (faint)
    ctx.strokeStyle = 'rgba(60, 40, 30, 0.15)';
    ctx.lineWidth = 0.5;
    ctx.stroke();

    // 2. Clip for internal details
    ctx.clip();

    // 3. Draw Details (scattered within bounds)
    const cx = region.x;
    const cy = region.y;
    const base = seed + 97;
    const scatterR = 30; 

    ctx.translate(cx, cy);

    if (type === 'forest') {
        for (let i = 0; i < 7; i++) {
            const a = seededRand(base + i * 11) * Math.PI * 2;
            const r = seededRand(base + i * 17) * scatterR;
            drawIcon(ctx, 'tree', Math.cos(a) * r, Math.sin(a) * r, 5 + seededRand(base+i)*3);
        }
    } else if (type === 'mountain') {
        for (let i = 0; i < 4; i++) {
            const a = seededRand(base + i * 19) * Math.PI * 2;
            const r = seededRand(base + i * 23) * scatterR * 0.9;
            drawIcon(ctx, 'mountain', Math.cos(a) * r, Math.sin(a) * r, 8 + seededRand(base+i)*5);
        }
    } else if (type === 'river') {
         // Draw a river segment
        ctx.beginPath();
        ctx.moveTo(-scatterR, -scatterR*0.3);
        ctx.bezierCurveTo(-10, -10, 10, 10, scatterR, scatterR*0.3);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
        ctx.lineWidth = 2;
        ctx.stroke();
    } else if (type === 'gorge') {
        // Crack
        ctx.beginPath();
        ctx.moveTo(-scatterR*0.8, -scatterR*0.5);
        ctx.lineTo(scatterR*0.5, scatterR*0.8);
        ctx.strokeStyle = 'rgba(60, 40, 30, 0.4)';
        ctx.lineWidth = 1.5;
        ctx.stroke();
    } else if (type === 'desert') {
         // Dunes
         for(let i=0; i<4; i++) {
             const ox = (seededRand(base+i*5)-0.5)*40;
             const oy = (seededRand(base+i*7)-0.5)*40;
             ctx.beginPath();
             ctx.moveTo(ox-6, oy);
             ctx.quadraticCurveTo(ox, oy-4, ox+6, oy);
             ctx.strokeStyle = 'rgba(160, 130, 80, 0.6)';
             ctx.lineWidth = 1;
             ctx.stroke();
         }
    }

    ctx.restore();
}

const getLocationType = (label, kind) => {
    // 1. Check kind first (passed from backend)
    if (kind) {
        const k = String(kind).toLowerCase().trim();
        // Chinese mappings (from raw LLM output)
        if (/[城都州郡镇村府]/.test(k)) return 'city';
        if (/[山岭峰]/.test(k)) return 'mountain';
        if (/[江河溪川]/.test(k)) return 'river';
        if (/[湖泊潭]/.test(k)) return 'lake';
        if (/[林森原]/.test(k)) return 'forest';
        if (/[峡谷崖渊]/.test(k)) return 'gorge';
        if (/[宫殿寺观阁宗门派帮会盟]/.test(k)) return 'temple';
        if (/[遗迹遗址废墟秘境界域]/.test(k)) return 'ruin';
        if (/[矿]/.test(k)) return 'mine';
        if (/[漠沙荒]/.test(k)) return 'desert';
        
        // English mappings (fallback)
        if (['city', 'town', 'country', 'capital'].some(x => k.includes(x))) return 'city';
        if (['mountain', 'hill', 'peak'].some(x => k.includes(x))) return 'mountain';
        if (['river', 'water', 'stream'].some(x => k.includes(x))) return 'river';
        if (['lake', 'pool', 'pond'].some(x => k.includes(x))) return 'lake';
        if (['forest', 'wood'].some(x => k.includes(x))) return 'forest';
        if (['gorge', 'valley', 'cliff'].some(x => k.includes(x))) return 'gorge';
        if (['temple', 'sect', 'palace'].some(x => k.includes(x))) return 'temple';
        if (['ruin', 'relic'].some(x => k.includes(x))) return 'ruin';
        if (['desert'].some(x => k.includes(x))) return 'desert';
    }

    const text = String(label || '');
    if (/湖|泊|潭/.test(text)) return 'lake';
    if (/河|江|溪|川/.test(text)) return 'river';
    if (/峡|谷|崖|渊/.test(text)) return 'gorge';
    if (/矿|矿脉/.test(text)) return 'mine';
    if (/遗迹|遗址|废墟|秘境/.test(text)) return 'ruin';
    if (/宫|殿|寺|观|阁/.test(text)) return 'temple';
    if (/林|森/.test(text)) return 'forest';
    if (/漠|沙|荒/.test(text)) return 'desert';
    if (/山|岭|峰|山脉/.test(text)) return 'mountain';
    if (/城|州|都|皇城/.test(text)) return 'city';
    return 'city';
}

const drawCity = (ctx, x, y, label) => {
  ctx.save()
  ctx.translate(x, y)
  // Shadow
  ctx.fillStyle = 'rgba(0,0,0,0.2)'
  ctx.beginPath()
  ctx.ellipse(0, 6, 8, 3, 0, 0, Math.PI*2)
  ctx.fill()
  
  // Icon
  ctx.strokeStyle = '#2c1b18'
  ctx.lineWidth = 2
  ctx.fillStyle = '#e8dcc5' 
  ctx.beginPath()
  ctx.rect(-5, -5, 10, 10)
  ctx.fill()
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(-6, -5)
  ctx.lineTo(0, -12)
  ctx.lineTo(6, -5)
  ctx.stroke()
  ctx.restore()
}

// Subdivide a line segment into jagged segments
const subdivide = (p1, p2, depth, rng) => {
    if (depth <= 0) return [p1, p2];
    const mx = (p1[0] + p2[0]) / 2;
    const my = (p1[1] + p2[1]) / 2;
    const dist = Math.hypot(p2[0]-p1[0], p2[1]-p1[1]);
    const offset = (rng.next() - 0.5) * dist * 0.3; // Jitter
    
    // Perpendicular vector
    const dx = p2[0] - p1[0];
    const dy = p2[1] - p1[1];
    const px = -dy;
    const py = dx;
    const len = Math.hypot(px, py);
    
    const nx = mx + (px/len) * offset;
    const ny = my + (py/len) * offset;
    const mid = [nx, ny];
    
    const left = subdivide(p1, mid, depth-1, rng);
    const right = subdivide(mid, p2, depth-1, rng);
    return [...left.slice(0, -1), ...right];
}

let visualLoopId = null;

const tickVisuals = (timestamp) => {
    animState.time = timestamp;
    
    // Always update for ambient animations (water, route flow)
    if (props.selectedCharacter) {
        animState.routeDashOffset = (timestamp / 20) % 20;
    }

    let settled = true;
    for (const id in animState.nodes) {
        const st = animState.nodes[id];
        if (Math.abs(st.opacity - st.targetOpacity) > 0.01) {
            st.opacity += (st.targetOpacity - st.opacity) * 0.1;
            settled = false;
        } else {
            st.opacity = st.targetOpacity;
        }
        if (Math.abs(st.scale - st.targetScale) > 0.01) {
            st.scale += (st.targetScale - st.scale) * 0.1;
            settled = false;
        } else {
            st.scale = st.targetScale;
        }
    }
    
    render(timestamp);
    visualLoopId = requestAnimationFrame(tickVisuals);
}

const startVisualLoop = () => {
    if (!visualLoopId) {
        visualLoopId = requestAnimationFrame(tickVisuals);
    }
}

// --- RENDER ---
const render = (timestamp = 0) => {
  if (!canvasContext || !canvasRef.value) return
  const ctx = canvasContext
  const w = width
  const h = height

  ctx.clearRect(0, 0, w, h)
  drawPaperTexture(ctx, w, h)

  ctx.save()
  ctx.translate(transform.x, transform.y)
  ctx.scale(transform.k, transform.k)

  if (voronoiRegions.length > 0) {
      // 1. Draw Ocean First (Base Layer)
      voronoiRegions.forEach(r => {
          if (!r.polygon) return;
          
          let alpha = 1;
          if (animState.nodes[r.id]) alpha = animState.nodes[r.id].opacity;
          
          if (alpha < 0.01) return;
          
          if (r.biome === 'OCEAN') {
              ctx.save();
              ctx.globalAlpha = alpha;
              
              ctx.beginPath();
              const p = r.noisyPolygon || r.polygon; 
              if (p && p.length > 0 && p[0]) {
                  ctx.moveTo(p[0][0], p[0][1]);
                  for(let i=1; i<p.length; i++) {
                      if (p[i]) ctx.lineTo(p[i][0], p[i][1]);
                  }
              }
              ctx.closePath();
              
              if (r.depth <= 1) ctx.fillStyle = themePalette.waterShallow;
              else if (r.depth <= 3) ctx.fillStyle = themePalette.waterMedium;
              else ctx.fillStyle = themePalette.waterDeep;
              ctx.fill();
              
              // Pattern Overlay
              if (patterns.ocean) {
                  ctx.fillStyle = patterns.ocean;
                  ctx.save();
                  ctx.globalAlpha = 0.2 * alpha; 
                  ctx.fill();
                  ctx.restore();
              }
              
              // Animated Waves
              if (r.depth > 1) {
                   const seed = (r.id * 9301 + 49297) % 233280;
                   const wavePhase = (animState.time / 2000 + seed) % (Math.PI * 2);
                   const waveAlpha = (Math.sin(wavePhase) + 1) / 2; // 0 to 1
                   
                   if (waveAlpha > 0.1) {
                       ctx.save();
                       ctx.translate(r.x, r.y);
                       ctx.strokeStyle = `rgba(255, 255, 255, ${0.2 * waveAlpha * alpha})`;
                       ctx.lineWidth = 1.5;
                       ctx.beginPath();
                       ctx.moveTo(-6, 0);
                       ctx.quadraticCurveTo(0, -3, 6, 0);
                       ctx.stroke();
                       ctx.restore();
                   }
              }

              // Coastal Ripples (Stroke depth bands)
              if (r.depth <= 2) {
                   const pulse = 0.15 + Math.sin(animState.time / 800 + r.id) * 0.05;
                   ctx.strokeStyle = `rgba(255, 255, 255, ${pulse * alpha})`;
                   ctx.lineWidth = 2;
                   ctx.stroke();
              }
              ctx.restore();
          }
      });

      // 2. Draw Land (Overlay)
      voronoiRegions.forEach(r => {
          if (!r.polygon) return;
          
          let alpha = 1;
          if (animState.nodes[r.id]) alpha = animState.nodes[r.id].opacity;
          
          if (alpha < 0.01) return;
          
          if (r.biome !== 'OCEAN') {
              ctx.save();
              ctx.globalAlpha = alpha;
              
              ctx.beginPath();
              const p = r.noisyPolygon || r.polygon; 
          if (p && p.length > 0 && p[0]) {
              ctx.moveTo(p[0][0], p[0][1]);
              for(let i=1; i<p.length; i++) {
                  if (p[i]) ctx.lineTo(p[i][0], p[i][1]);
              }
          }
              ctx.closePath();
              
              ctx.fillStyle = themePalette.bg;
              ctx.fill();

              // Biome Texture
              let pat = null;
              let patAlpha = 0.4;
              
              if (r.biome === 'FOREST') { pat = patterns.forest; patAlpha = 0.6; }
              else if (r.biome === 'SWAMP') { pat = patterns.swamp; patAlpha = 0.5; }
              else if (r.biome === 'DESERT') { pat = patterns.desert; patAlpha = 0.4; }
              else if (r.biome === 'MOUNTAIN' || r.h > 0.8) { pat = patterns.mountain; patAlpha = 0.5; }
              
              if (pat) {
                  ctx.fillStyle = pat;
                  ctx.save();
                  ctx.globalAlpha = patAlpha * alpha;
                  ctx.fill();
                  ctx.restore();
              }

              // Subtle Relief Shading
              if (r.relief) {
                  ctx.fillStyle = r.relief > 0 ? `rgba(255,255,255,${r.relief*0.3})` : `rgba(60,50,40,${-r.relief*0.2})`;
                  ctx.fill();
              }
              
              // Coastline Stroke (Check neighbors for Ocean)
              let isCoast = false;
              if (r.neighbors) {
                  for(const nIdx of r.neighbors) {
                      if (voronoiRegions[nIdx] && voronoiRegions[nIdx].biome === 'OCEAN') {
                          isCoast = true;
                          break;
                      }
                  }
              }
              
              if (isCoast) {
                  ctx.strokeStyle = '#4a3c31'; // Dark brown for coastline
                  ctx.lineWidth = 1.5;
                  ctx.stroke();
                  
                  // Inner Coastline Fade
                  ctx.lineWidth = 4;
                  ctx.strokeStyle = `rgba(60, 45, 30, ${0.1 * alpha})`;
                  ctx.stroke();
              }
              ctx.restore();
          }
      });
  }
  
  // 3. Rivers
  if (rivers.length > 0) {
     rivers.forEach(r => {
         // Water body
         ctx.beginPath();
         ctx.moveTo(r.x1, r.y1);
         ctx.quadraticCurveTo(r.cx, r.cy, r.x2, r.y2);
         ctx.strokeStyle = themePalette.waterMedium;
         ctx.lineWidth = r.width;
         ctx.lineCap = 'round';
         ctx.stroke();
     });
  }

  // 4. Icons (Vegetation & Mountains)
  voronoiRegions.forEach(r => {
      if ( r.visible && r.biome !== 'OCEAN') {
          // Trees
          if (r.m > 0.5 && r.h < 0.7) {
               if (r.id % 3 === 0) { // Higher density
                   drawIcon(ctx, 'tree', r.x, r.y, 8 + seededRand(r.id)*4);
               }
          }
          // Mountains
          if (r.relief > 0.15 || r.h > 0.7) {
               const base = idSeed(r.id);
               drawIcon(ctx, 'mountain', r.x, r.y - 8, 14);
               if (r.h > 0.8) { // Extra peak
                   drawIcon(ctx, 'mountain', r.x + 10, r.y + 2, 10);
               }
          }
      }
  });

  // 5. Routes (Footprints Path)
  if (props.showRelations && props.selectedCharacter) {
      const charPolylines = (props.mapData?.polylines || []).filter(p => p.character === props.selectedCharacter);
      
      charPolylines.forEach(poly => {
          const n1 = nodes.find(n => n.id === poly.from_location);
          const n2 = nodes.find(n => n.id === poly.to_location);
          if (n1 && n2) {
              const dist = Math.hypot(n2.x - n1.x, n2.y - n1.y);
              const angle = Math.atan2(n2.y - n1.y, n2.x - n1.x);
              
              // Curve Control Points for Natural Path
              const cp1x = n1.x + (n2.x - n1.x) * 0.33 + (seededRand(n1.id) - 0.5) * 40;
              const cp1y = n1.y + (n2.y - n1.y) * 0.33 + (seededRand(n2.id) - 0.5) * 40;
              const cp2x = n1.x + (n2.x - n1.x) * 0.66 + (seededRand(n1.id + n2.id) - 0.5) * 40;
              const cp2y = n1.y + (n2.y - n1.y) * 0.66 + (seededRand(n1.id * n2.id) - 0.5) * 40;

              // Draw Dashed Guideline (Optional, faint)
              ctx.beginPath();
              ctx.moveTo(n1.x, n1.y);
              ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, n2.x, n2.y);
              ctx.strokeStyle = 'rgba(139, 0, 0, 0.25)'; 
              ctx.lineWidth = 1.5;
              ctx.setLineDash([5, 5]);
              ctx.lineDashOffset = -animState.routeDashOffset;
              ctx.stroke();
              ctx.setLineDash([]);
              ctx.lineDashOffset = 0;

              // Draw Footprints along the curve
                      const stepCount = Math.floor(dist / 18); // Spacing between steps
                      ctx.fillStyle = 'rgba(100, 20, 20, 0.7)'; // Dark red ink

                      for (let i = 1; i < stepCount; i++) {
                          const t = i / stepCount;
                          
                          // Bezier point calculation
                          const cx = 3 * (1 - t) * (1 - t) * t * cp1x + 3 * (1 - t) * t * t * cp2x + t * t * t * n2.x + (1 - t) * (1 - t) * (1 - t) * n1.x;
                          const cy = 3 * (1 - t) * (1 - t) * t * cp1y + 3 * (1 - t) * t * t * cp2y + t * t * t * n2.y + (1 - t) * (1 - t) * (1 - t) * n1.y;
                          
                          // Calculate tangent for rotation
                          const tx = 3 * (1 - t) * (1 - t) * (cp1x - n1.x) + 6 * (1 - t) * t * (cp2x - cp1x) + 3 * t * t * (n2.x - cp2x);
                          const ty = 3 * (1 - t) * (1 - t) * (cp1y - n1.y) + 6 * (1 - t) * t * (cp2y - cp1y) + 3 * t * t * (n2.y - cp2y);
                          const rot = Math.atan2(ty, tx);

                          ctx.save();
                          ctx.translate(cx, cy);
                          ctx.rotate(rot);
                          
                          // Offset for left/right foot
                          const isLeft = i % 2 === 0;
                          const sideOffset = isLeft ? -4 : 4;
                          ctx.translate(0, sideOffset);

                          // Draw Footprint (Simple shoe shape)
                          ctx.beginPath();
                          // Sole
                          ctx.ellipse(0, 0, 4, 1.8, 0, 0, Math.PI * 2);
                          // Heel
                          ctx.ellipse(-3, 0, 2.5, 1.5, 0, 0, Math.PI * 2);
                          ctx.fill();

                          ctx.restore();
                      }

                      // Draw Direction Arrow at the end (near n2)
                      // Calculate point near end (t=0.9)
                      const tEnd = 0.95;
                      const arrowX = 3 * (1 - tEnd) * (1 - tEnd) * tEnd * cp1x + 3 * (1 - tEnd) * tEnd * tEnd * cp2x + tEnd * tEnd * tEnd * n2.x + (1 - tEnd) * (1 - tEnd) * (1 - tEnd) * n1.x;
                      const arrowY = 3 * (1 - tEnd) * (1 - tEnd) * tEnd * cp1y + 3 * (1 - tEnd) * tEnd * tEnd * cp2y + tEnd * tEnd * tEnd * n2.y + (1 - tEnd) * (1 - tEnd) * (1 - tEnd) * n1.y;
                      
                      const txEnd = 3 * (1 - tEnd) * (1 - tEnd) * (cp1x - n1.x) + 6 * (1 - tEnd) * tEnd * (cp2x - cp1x) + 3 * tEnd * tEnd * (n2.x - cp2x);
                      const tyEnd = 3 * (1 - tEnd) * (1 - tEnd) * (cp1y - n1.y) + 6 * (1 - tEnd) * tEnd * (cp2y - cp1y) + 3 * tEnd * tEnd * (n2.y - cp2y);
                      const rotEnd = Math.atan2(tyEnd, txEnd);

                      ctx.save();
                      ctx.translate(arrowX, arrowY);
                      ctx.rotate(rotEnd);
                      ctx.fillStyle = 'rgba(139, 0, 0, 0.9)';
                      ctx.beginPath();
                      ctx.moveTo(0, 0);
                      ctx.lineTo(-10, -5);
                      ctx.lineTo(-7, 0); // Inner notch
                      ctx.lineTo(-10, 5);
                      ctx.closePath();
                      ctx.fill();
                      ctx.restore();
          }
      });
  }

  // 6. Cities/Locations
  nodes.forEach(n => {
      let alpha = 1;
      let scale = 1;
      if (animState.nodes[n.id]) {
          alpha = animState.nodes[n.id].opacity;
          scale = animState.nodes[n.id].scale;
      }
      
      if (alpha < 0.01) return;

      const region = voronoiRegions[n.index];
      
      // Highlight Region if hovered
      if (n.id === hoveredNodeId && region) {
           const p = region.noisyPolygon || region.polygon;
           if (p && p.length > 0 && p[0]) {
               ctx.save();
               ctx.beginPath();
               ctx.moveTo(p[0][0], p[0][1]);
               for(let i=1; i<p.length; i++) {
                   if (p[i]) ctx.lineTo(p[i][0], p[i][1]);
               }
               ctx.closePath();
               
               // Pulsing highlight
               const glow = 0.2 + Math.sin(animState.time / 200) * 0.1;
               ctx.fillStyle = `rgba(255, 255, 255, ${glow * alpha})`;
               ctx.fill();
               
               ctx.strokeStyle = themePalette.gold;
               ctx.lineWidth = 2;
               ctx.stroke();
               ctx.restore();
           }
      }
      
      ctx.save();
      ctx.translate(n.x, n.y);
      ctx.scale(scale, scale);
      ctx.translate(-n.x, -n.y);
      ctx.globalAlpha = alpha;

      const locType = getLocationType(n.label, n.kind);
      if (areaTypes.has(locType)) {
          drawAreaMarker(ctx, locType, region, idSeed(n.id));
      } else {
          drawLocationIcon(ctx, locType, n.x, n.y);
      }
      
      if (n.has_sub_map) {
          drawSubMapIndicator(ctx, n.x, n.y);
      }

      ctx.font = 'bold 14px "IM Fell English SC", Georgia, "Times New Roman", serif'; // Added fallbacks
      ctx.textAlign = 'center';
      ctx.fillStyle = themePalette.ink;
      // Shadow for text
      ctx.shadowColor = themePalette.bg;
      ctx.shadowBlur = 4;
      ctx.fillText(n.label, n.x, n.y + 24);
      ctx.shadowBlur = 0;
      
      ctx.restore();
  });

  ctx.restore()
  
  // Vignette
  const grad = ctx.createRadialGradient(w/2, h/2, Math.max(w,h)*0.5, w/2, h/2, Math.max(w,h)*0.95);
  grad.addColorStop(0, 'rgba(0,0,0,0)');
  grad.addColorStop(1, 'rgba(50, 30, 10, 0.4)');
  ctx.fillStyle = grad;
  ctx.globalCompositeOperation = 'multiply';
  ctx.fillRect(0, 0, w, h);
  ctx.globalCompositeOperation = 'source-over';
  
  drawCompass(ctx, w, h);
  
  // Aged Creases Overlay
  if (patterns.creases) {
      ctx.fillStyle = patterns.creases;
      ctx.globalCompositeOperation = 'multiply';
      ctx.globalAlpha = 0.4;
      ctx.fillRect(0, 0, w, h);
      ctx.globalCompositeOperation = 'source-over';
      ctx.globalAlpha = 1;
  }

  // drawWaxSeal(ctx, w - 60, h - 60, 40); // Removed as per user request
  drawParchmentBorder(ctx, w, h);
}

// --- DECORATION ---
// Wax Seal Removed

const drawParchmentBorder = (ctx, w, h) => {
    ctx.save();
    
    // 1. Vignette/Burnt Edges (Drawn on top of everything)
    const grad = ctx.createRadialGradient(w/2, h/2, Math.max(w,h)*0.6, w/2, h/2, Math.max(w,h)*0.95);
    grad.addColorStop(0, 'rgba(0,0,0,0)');
    grad.addColorStop(0.8, 'rgba(60, 45, 30, 0.1)');
    grad.addColorStop(1, 'rgba(40, 25, 10, 0.6)');
    ctx.fillStyle = grad;
    ctx.globalCompositeOperation = 'multiply';
    ctx.fillRect(0, 0, w, h);
    
    // 2. Decorative Border Frame
    ctx.globalCompositeOperation = 'source-over';
    
    // Outer Frame
    const border = 16;
    ctx.strokeStyle = '#3d2b1f';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.rect(border, border, w - border*2, h - border*2);
    ctx.stroke();

    // Inner Frame (Gold/Bronze)
    ctx.strokeStyle = '#8b6c42';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.rect(border + 4, border + 4, w - (border + 4)*2, h - (border + 4)*2);
    ctx.stroke();
    
    // Patterned Line (Dots) removed in favor of complex edge pattern below
    // ctx.strokeStyle = 'rgba(60, 45, 30, 0.3)';
    // ctx.setLineDash([2, 8]);
    // ctx.lineWidth = 1.5;
    // ctx.beginPath();
    // ctx.rect(border + 8, border + 8, w - (border + 8)*2, h - (border + 8)*2);
    // ctx.stroke();
    // ctx.setLineDash([]);

    // 2.5 Complex Edge Pattern (Vines along the border)
    const drawVineEdge = (x1, y1, x2, y2, vertical = false) => {
        const dist = Math.hypot(x2 - x1, y2 - y1);
        const steps = Math.floor(dist / 30); // Repeat every 30px
        const stepX = (x2 - x1) / steps;
        const stepY = (y2 - y1) / steps;
        
        ctx.strokeStyle = 'rgba(60, 45, 30, 0.5)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        
        // Main sine wave
        ctx.moveTo(x1, y1);
        for(let i=0; i<=steps; i++) {
            const px = x1 + stepX * i;
            const py = y1 + stepY * i;
            // Add wave offset
            const offset = (i % 2 === 0 ? 1 : -1) * 4;
            const ox = vertical ? offset : 0;
            const oy = vertical ? 0 : offset;
            
            if (i===0) ctx.moveTo(px, py);
            else {
                const prevX = x1 + stepX * (i-1);
                const prevY = y1 + stepY * (i-1);
                const cp1x = prevX + (vertical ? offset*1.5 : stepX/2);
                const cp1y = prevY + (vertical ? stepY/2 : offset*1.5);
                const cp2x = px + (vertical ? -offset*1.5 : -stepX/2);
                const cp2y = py + (vertical ? -stepY/2 : -offset*1.5);
                ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, px, py);
            }
            
            // Draw small leaf/dot at nodes
            ctx.save();
            ctx.fillStyle = '#8b6c42';
            ctx.translate(px, py);
            ctx.beginPath();
            ctx.arc(0, 0, 1.5, 0, Math.PI*2);
            ctx.fill();
            ctx.restore();
        }
        ctx.stroke();
    }
    
    const edgeM = border + 10;
    // Top
    drawVineEdge(edgeM + 40, edgeM, w - edgeM - 40, edgeM);
    // Bottom
    drawVineEdge(edgeM + 40, h - edgeM, w - edgeM - 40, h - edgeM);
    // Left
    drawVineEdge(edgeM, edgeM + 40, edgeM, h - edgeM - 40, true);
    // Right
    drawVineEdge(w - edgeM, edgeM + 40, w - edgeM, h - edgeM - 40, true);

    // 3. Corner Flourishes (Complex Medieval Decoration)
    const drawComplexCorner = (cx, cy, rotation) => {
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(rotation);
        
        ctx.strokeStyle = '#3d2b1f';
        ctx.lineWidth = 1.5;
        
        // --- Main Vine ---
        ctx.beginPath();
        ctx.moveTo(0, 0);
        // Long curve out
        ctx.bezierCurveTo(30, 30, 60, 0, 100, 20); 
        // Curl back
        ctx.bezierCurveTo(120, 30, 90, 50, 80, 40);
        ctx.stroke();

        // --- Secondary Vine (Mirroring) ---
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.bezierCurveTo(30, 30, 0, 60, 20, 100);
        ctx.bezierCurveTo(30, 120, 50, 90, 40, 80);
        ctx.stroke();

        // --- Leaves / Details ---
        ctx.fillStyle = '#2f3d26'; // Dark Green
        
        // Leaf 1
        ctx.beginPath();
        ctx.ellipse(50, 15, 8, 4, Math.PI/6, 0, Math.PI*2);
        ctx.fill();
        
        // Leaf 2
        ctx.beginPath();
        ctx.ellipse(15, 50, 8, 4, Math.PI/3, 0, Math.PI*2);
        ctx.fill();

        // Leaf 3 (End)
        ctx.beginPath();
        ctx.ellipse(90, 30, 6, 3, -Math.PI/6, 0, Math.PI*2);
        ctx.fill();

        // Leaf 4 (End)
        ctx.beginPath();
        ctx.ellipse(30, 90, 6, 3, -Math.PI/3, 0, Math.PI*2);
        ctx.fill();
        
        // --- Flowers / Berries ---
        ctx.fillStyle = '#8b0000';
        ctx.beginPath(); ctx.arc(25, 25, 3, 0, Math.PI*2); ctx.fill();
        ctx.beginPath(); ctx.arc(70, 15, 2.5, 0, Math.PI*2); ctx.fill();
        ctx.beginPath(); ctx.arc(15, 70, 2.5, 0, Math.PI*2); ctx.fill();

        // --- Gold Accents ---
        ctx.strokeStyle = '#c5a059';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(10, 10);
        ctx.lineTo(15, 15);
        ctx.stroke();

        ctx.restore();
    }
    
    const m = border; // Align with outer frame
    drawComplexCorner(m, m, 0); // TL
    drawComplexCorner(w-m, m, Math.PI/2); // TR
    drawComplexCorner(w-m, h-m, Math.PI); // BR
    drawComplexCorner(m, h-m, -Math.PI/2); // BL

    ctx.restore();
}

// --- LOGIC ---
const calculateRelief = (cellData, neighbors) => {
    cellData.forEach((d, i) => {
        let slopeX = 0;
        let slopeY = 0;
        neighbors[i].forEach(nIdx => {
            const n = cellData[nIdx];
            slopeX += (d.x - n.x) * (d.h - n.h);
            slopeY += (d.y - n.y) * (d.h - n.h);
        });
        const relief = (slopeX - slopeY) * 2;
        d.relief = Math.max(-0.3, Math.min(0.3, relief));
    });
}

const calculateOceanDepth = (cellData, neighbors) => {
    // 1. Identify Coasts (Water with Land neighbor)
    const queue = [];
    cellData.forEach((d, i) => {
        if (d.h < 0.2) { // Water
            let isCoast = false;
            for(const nIdx of neighbors[i]) {
                if (cellData[nIdx].h >= 0.2) {
                    isCoast = true;
                    break;
                }
            }
            if (isCoast) {
                d.depth = 1;
                queue.push(i);
            } else {
                d.depth = 999; // Infinite depth initially
            }
        } else {
            d.depth = 0; // Land
        }
    });

    // 2. BFS for Depth
    while(queue.length > 0) {
        const u = queue.shift();
        const d = cellData[u].depth;
        
        for(const nIdx of neighbors[u]) {
            const neighbor = cellData[nIdx];
            if (neighbor.h < 0.2 && neighbor.depth === 999) {
                neighbor.depth = d + 1;
                queue.push(nIdx);
            }
        }
    }
}

const initLayout = () => {
  if (simulation) simulation.stop();
  if (!props.mapData || !props.mapData.nodes) return;

  const rawNodes = props.mapData.nodes;
  const rawEdges = props.mapData.edges || [];
  const rng = new SeededRandom(MAP_SEED);
  
  // 1. Initial Positions (Deterministic based on WORLD size)
  // Fix: Strictly filter out sub-locations from the World Map to ensure hierarchy distinction
  const validNodes = rawNodes.filter(n => n.scope !== 'sub');
  
  nodes = validNodes.map((n, i) => ({
    id: n.location_id,
    label: n.label,
    x: WORLD_W/2 + (rng.next() - 0.5) * (WORLD_W * 0.5),
    y: WORLD_H/2 + (rng.next() - 0.5) * (WORLD_H * 0.5),
    index: i,
    kind: n.kind,
    scope: n.scope,
    parent_id: n.parent_id,
    has_sub_map: !!n.sub_map
  }));

  const validIds = new Set(nodes.map(n => n.id));
  links = rawEdges
    .filter(e => validIds.has(e.a) && validIds.has(e.b))
    .map(e => ({
      source: e.a,
      target: e.b,
      type: e.type
    }));

  // 2. Simulation (Deterministic forces)
  simulation = d3.forceSimulation(nodes)
    .force("charge", d3.forceManyBody().strength(-300))
    .force("center", d3.forceCenter(WORLD_W / 2, WORLD_H / 2))
    .force("collide", d3.forceCollide().radius(50))
    .force("link", d3.forceLink(links).id(d => d.id).distance(120))
    .stop();

  for (let i = 0; i < 300; ++i) simulation.tick();
  
  // 3. Voronoi & Terrain
  const delaunay = d3.Delaunay.from(nodes, d => d.x, d => d.y);
  const voronoi = delaunay.voronoi([0, 0, WORLD_W, WORLD_H]);
  const neighbors = new Array(nodes.length).fill(0).map((_, i) => [...delaunay.neighbors(i)]);
  
  const cellData = nodes.map((n, i) => {
      const nx = n.x / WORLD_W; 
      const ny = n.y / WORLD_H;
      // FBM Noise for Height
      let hVal = fbm(nx * 2, ny * 2, 6); 
      
      // Radial Mask (Island shape)
      const dx = (n.x - WORLD_W/2) / (WORLD_W/2);
      const dy = (n.y - WORLD_H/2) / (WORLD_H/2);
      const d = Math.sqrt(dx*dx + dy*dy);
      hVal = hVal + 0.35 - Math.pow(d, 1.5); // Stronger falloff
      
      const mVal = fbm(nx + 10, ny + 20, 4); // Moisture
      return { h: hVal, m: mVal, x: n.x, y: n.y, id: i, relief: 0, lake: false };
  });
  
  // Enforce Land/Terrain for specific location types (Fix: prevent Mountains in Sea)
  nodes.forEach((n, i) => {
      const type = getLocationType(n.label);
      const d = cellData[i];
      if (type === 'mountain') {
          d.h = Math.max(d.h, 0.75); // Force high mountain
      } else if (['forest', 'city', 'ruin', 'temple', 'mine', 'gorge', 'desert'].includes(type)) {
          d.h = Math.max(d.h, 0.25); // Force land
      } else if (type === 'lake') {
          // For lakes, we might want a depression, but not necessarily ocean.
          // Let's force it to be a local depression in the next step or just ensure it's not a peak.
          d.h = Math.max(d.h, 0.22); // Land but low
          d.lake = true; // Force lake flag
      }
  });

  calculateRelief(cellData, neighbors);
  calculateOceanDepth(cellData, neighbors);
  
  // 4. Rivers (Downhill Flow)
  rivers = [];
  const flux = new Array(nodes.length).fill(0);
  const dest = new Array(nodes.length).fill(-1);
  const sortedIndices = cellData.map((d, i) => i).sort((a, b) => cellData[b].h - cellData[a].h);
  
  cellData.forEach((d, i) => {
      if (d.h < 0.2 || d.h > 0.95) return;
      let minH = d.h;
      let minIdx = -1;
      neighbors[i].forEach(nIdx => {
          if (cellData[nIdx].h < minH) {
              minH = cellData[nIdx].h;
              minIdx = nIdx;
          }
      });
      dest[i] = minIdx;
  });
  
  sortedIndices.forEach(i => {
      const d = cellData[i];
      if (d.h < 0.2) return;
      flux[i] += d.m * 5 + 1;
      const j = dest[i];
      if (j !== -1) flux[j] += flux[i];
  });
  
  sortedIndices.forEach(i => {
      if (flux[i] > 18 && dest[i] !== -1 && cellData[i].h >= 0.2) {
          let curr = i;
          let steps = 0;
          const w = Math.min(Math.sqrt(flux[i]), 8);
          while (dest[curr] !== -1 && cellData[curr].h >= 0.2 && steps < 60) {
              const j = dest[curr];
              const cx = (cellData[curr].x + cellData[j].x)/2 + (rng.next()-0.5)*15;
              const cy = (cellData[curr].y + cellData[j].y)/2 + (rng.next()-0.5)*15;
              rivers.push({
                  x1: cellData[curr].x,
                  y1: cellData[curr].y,
                  x2: cellData[j].x,
                  y2: cellData[j].y,
                  cx: cx,
                  cy: cy,
                  width: w
              });
              curr = j;
              steps++;
          }
      }
  });
  
  cellData.forEach((d, i) => {
      if (d.h >= 0.2 && d.h < 0.28) {
          let isLocalMin = true;
          let hasWaterNeighbor = false;
          neighbors[i].forEach(nIdx => {
              const n = cellData[nIdx];
              if (n.h < d.h) isLocalMin = false;
              if (n.h < 0.2) hasWaterNeighbor = true;
          });
          if (isLocalMin && !hasWaterNeighbor) d.lake = true;
      }
  });

  voronoiRegions = nodes.map((n, i) => {
      const d = cellData[i];
      let biome = getBiome(d.h, d.m);
      if (d.lake) biome = 'LAKE';
      const poly = voronoi.cellPolygon(i);
      
      // Create noisy polygon for render
      // Note: We are not solving shared edge gaps here, but using stroke to cover them
      let noisy = null;
      if (poly) {
          noisy = [];
          for(let k=0; k<poly.length-1; k++) {
              const seg = subdivide(poly[k], poly[k+1], 2, rng);
              noisy.push(...seg.slice(0, -1));
          }
          noisy.push(poly[poly.length-1]);
      }

      return {
          id: n.id,
          index: i,
          polygon: poly,
          noisyPolygon: noisy,
          x: n.x, 
          y: n.y,
          h: d.h,
          m: d.m, // Store moisture
          biome: biome,
          color: getBiomeColor(biome),
          relief: d.relief,
          depth: d.depth,
          visible: true,
          neighbors: neighbors[i] // Store neighbor indices
      };
  });
  
  // Center Map View (Fit to Content)
  let bounds = { minX: 0, maxX: WORLD_W, minY: 0, maxY: WORLD_H };
  
  if (nodes.length > 0) {
      const xs = nodes.map(n => n.x);
      const ys = nodes.map(n => n.y);
      bounds.minX = Math.min(...xs);
      bounds.maxX = Math.max(...xs);
      bounds.minY = Math.min(...ys);
      bounds.maxY = Math.max(...ys);
  }

  // Add padding
  const padding = 100;
  const contentW = bounds.maxX - bounds.minX + padding * 2;
  const contentH = bounds.maxY - bounds.minY + padding * 2;
  const contentCx = (bounds.minX + bounds.maxX) / 2;
  const contentCy = (bounds.minY + bounds.maxY) / 2;

  const scale = Math.min(width / contentW, height / contentH) * 0.9; // 0.9 for extra margin
  const tx = width / 2 - contentCx * scale;
  const ty = height / 2 - contentCy * scale;

  if (canvasRef.value) {
      // Defer to next tick to ensure canvas is ready
      setTimeout(() => {
         const sel = d3.select(canvasRef.value);
         const t = d3.zoomIdentity.translate(tx, ty).scale(scale);
         sel.call(d3.zoom().transform, t);
         transform = t;
         render();
      }, 0);
  } else {
      updateVisuals();
  }
}

const updateVisuals = () => {
    let visibleSet = null;
    if (props.visibleLocationIds) {
        visibleSet = new Set(props.visibleLocationIds);
    } else if (props.selectedCharacter) {
        visibleSet = new Set();
        (props.events || []).forEach(e => {
            if (e.characters && e.characters.includes(props.selectedCharacter)) {
                visibleSet.add(e.location_id);
            }
        });
    }

    // Initialize animState entries if missing
    nodes.forEach(n => {
        if (!animState.nodes[n.id]) {
            animState.nodes[n.id] = { opacity: 1, targetOpacity: 1, scale: 1, targetScale: 1 };
        }
    });

    if (!visibleSet) {
        nodes.forEach(n => {
            if (animState.nodes[n.id]) {
                animState.nodes[n.id].targetOpacity = 1;
                animState.nodes[n.id].targetScale = 1;
            }
        });
    } else {
        nodes.forEach(n => {
             if (animState.nodes[n.id]) {
                 if (visibleSet.has(n.id)) {
                     animState.nodes[n.id].targetOpacity = 1;
                     animState.nodes[n.id].targetScale = 1;
                 } else {
                     animState.nodes[n.id].targetOpacity = 0.1;
                     animState.nodes[n.id].targetScale = 0.8;
                 }
             }
        });
    }
    
    startVisualLoop();
}

// Interactions
const initZoom = () => {
  zoomBehavior = d3.zoom()
    .scaleExtent([0.5, 5])
    .on('zoom', (e) => {
      transform = e.transform
      requestAnimationFrame(render)
    })
  d3.select(canvasRef.value).call(zoomBehavior).on("dblclick.zoom", null)
}

const getSubjectAt = (mx, my) => {
  const x = (mx - transform.x) / transform.k
  const y = (my - transform.y) / transform.k
  
  // Increase hit radius for easier clicking, especially on mobile/small screens
  const hitRadiusSq = 900; // 30px radius
  
  for (const n of nodes) {
    const dx = x - n.x
    const dy = y - n.y
    if (dx*dx + dy*dy < hitRadiusSq) return n
  }
  return null
}

let startPos = null

const onPointerDown = (e) => {
  startPos = { x: e.clientX, y: e.clientY }
}

const onMouseMove = (e) => {
  const canvas = canvasRef.value
  const rect = canvas.getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top
  
  const subject = getSubjectAt(mx, my)
  
  // Update hovered node for visual highlight
  if (subject) {
      hoveredNodeId = subject.id
  } else {
      hoveredNodeId = null
  }

  if (subject) {
    canvas.style.cursor = 'pointer'
    const locEvents = (props.events || []).filter(ev => ev.location_id === subject.id)
    tooltip.value = {
      visible: true,
      x: mx + 20,
      y: my,
      title: subject.label,
      events: locEvents
    }
  } else {
    canvas.style.cursor = 'grab'
    tooltip.value.visible = false
  }
}

const onPointerUp = (e) => {
  if (!startPos) return
  const dist = Math.hypot(e.clientX - startPos.x, e.clientY - startPos.y)
  startPos = null
  
  // If movement is small, treat as click
  if (dist < 10) { // Slightly more lenient click detection
    const canvas = canvasRef.value
    const rect = canvas.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    
    console.log('Canvas Click:', { mx, my, transform })
    
    // Trigger Wax Seal Effect
    clickEffect.value = { visible: false, x: 0, y: 0 }
    requestAnimationFrame(() => {
      clickEffect.value = { visible: true, x: mx, y: my }
    })
    
    const subject = getSubjectAt(mx, my)
    if (subject) {
       console.log('Hit Node:', subject)
       emit('select-location', subject.id)
    } else {
       console.log('No node hit at click location')
    }
  }
}

onMounted(() => {
  if (!wrapperRef.value || !canvasRef.value) return
  canvasContext = canvasRef.value.getContext('2d')
  
  createBiomePatterns(); // Initialize patterns

  resizeObserver = new ResizeObserver(entries => {
    for (const entry of entries) {
      const { width: w, height: h } = entry.contentRect
      width = w
      height = h
      canvasRef.value.width = w
      canvasRef.value.height = h
      requestAnimationFrame(render)
    }
  })
  resizeObserver.observe(wrapperRef.value)
  
  initZoom()
  
  if (props.mapData) initLayout()
})

onUnmounted(() => {
  if (resizeObserver) resizeObserver.disconnect()
  if (visualLoopId) cancelAnimationFrame(visualLoopId)
})

watch(() => props.mapData, initLayout, { deep: true })
watch(() => [props.selectedCharacter, props.events], updateVisuals, { deep: true })

watch(() => props.focusLocationId, (newId) => {
  if (!newId || !zoomBehavior || !canvasRef.value) return;
  const targetNode = nodes.find(n => n.id === newId);
  if (targetNode) {
    const k = 1.5; // Zoom level
    // Calculate translate to center the node
    const tx = width / 2 - targetNode.x * k;
    const ty = height / 2 - targetNode.y * k;
    
    d3.select(canvasRef.value)
      .transition()
      .duration(750)
      .call(zoomBehavior.transform, d3.zoomIdentity.translate(tx, ty).scale(k));
  }
});
</script>

<style scoped>
/* Google Fonts mirror used in index.html */

.canvas-map-wrapper {
  width: 100%;
  height: 100%;
  position: relative;
  background-color: #f4e4bc;
  overflow: hidden;
  animation: ink-reveal 1.5s cubic-bezier(0.25, 1, 0.5, 1) forwards;
}

@keyframes ink-reveal {
  0% { clip-path: circle(0% at 50% 50%); filter: sepia(1) blur(10px); }
  100% { clip-path: circle(150% at 50% 50%); filter: sepia(0) blur(0px); }
}

canvas {
  display: block;
}

.map-tooltip {
  position: absolute;
  background: #f4e4bc;
  border: 2px solid #3d2b1f;
  padding: 12px;
  border-radius: 2px;
  box-shadow: 
    3px 3px 15px rgba(0,0,0,0.4),
    inset 0 0 20px rgba(60, 45, 30, 0.2);
  pointer-events: none;
  font-family: 'IM Fell English SC', serif;
  color: #2c1b18;
  z-index: 100;
  max-width: 320px;
  max-height: 400px;
  overflow-y: auto;
  transform: translate(10px, 10px);
}

.map-tooltip::after {
  content: '';
  position: absolute;
  top: 2px; left: 2px; right: 2px; bottom: 2px;
  border: 1px solid rgba(60, 45, 30, 0.3);
  pointer-events: none;
}

.click-effect-seal {
  position: absolute;
  width: 40px;
  height: 40px;
  background: #8b0000;
  border-radius: 50% 45% 55% 40% / 40% 55% 45% 60%;
  transform: translate(-50%, -50%) scale(0);
  box-shadow: 
    0 2px 4px rgba(0,0,0,0.4),
    inset 2px 2px 4px rgba(255,255,255,0.2),
    inset -2px -2px 4px rgba(0,0,0,0.2);
  pointer-events: none;
  z-index: 200;
  animation: seal-pop 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
}

.click-effect-seal::before {
  content: '';
  position: absolute;
  top: 50%; left: 50%;
  width: 26px; height: 26px;
  transform: translate(-50%, -50%);
  border: 2px solid rgba(0,0,0,0.2);
  border-radius: 50%;
}

@keyframes seal-pop {
  0% { transform: translate(-50%, -50%) scale(0); opacity: 0.5; }
  100% { transform: translate(-50%, -50%) scale(1); opacity: 0.9; }
}


.map-tooltip .title {
  font-weight: bold;
  font-size: 1.1em;
  border-bottom: 1px solid #ccc;
  margin-bottom: 5px;
}

.event-item {
  font-size: 0.9em;
  margin-bottom: 4px;
}

.chars {
  color: #8b0000;
  font-weight: bold;
  margin-right: 4px;
}

.map-legend {
  position: absolute;
  left: 16px;
  bottom: 24px;
  z-index: 90;
  font-family: 'IM Fell English SC', serif;
  color: #3d2b1f;
  
  /* Reset default box model styles as we use scroll structure */
  background: transparent;
  border: none;
  padding: 0;
  box-shadow: none;
  min-width: 200px;
}

.map-legend.scroll-style {
  filter: drop-shadow(4px 4px 8px rgba(0,0,0,0.4));
  transform: rotate(-1deg); /* Slight natural tilt */
}

.scroll-rod {
  height: 12px;
  background: linear-gradient(to right, #3d2b1f, #8b6c42, #3d2b1f);
  border-radius: 6px;
  position: relative;
  z-index: 2;
  box-shadow: 0 2px 4px rgba(0,0,0,0.3);
}

.scroll-rod::before, .scroll-rod::after {
  content: '';
  position: absolute;
  top: -2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, #c5a059, #8b6c42);
  border: 1px solid #3d2b1f;
  box-shadow: inset -1px -1px 2px rgba(0,0,0,0.5);
}

.scroll-rod::before { left: -6px; }
.scroll-rod::after { right: -6px; }

.scroll-content {
  background: #f4e4bc; /* Parchment color */
  padding: 12px 16px;
  margin: -6px 4px; /* Pull under rods */
  box-shadow: inset 0 0 20px rgba(60, 45, 30, 0.1);
  position: relative;
  z-index: 1;
  
  /* Paper Texture */
  background-image: url("data:image/svg+xml,%3Csvg width='100' height='100' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.5' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.05'/%3E%3C/svg%3E");
}

.legend-title {
  font-weight: bold;
  font-size: 1.1em;
  margin-bottom: 8px;
  text-align: center;
  border-bottom: 1px solid rgba(60, 45, 30, 0.3);
  padding-bottom: 4px;
}

.legend-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 10px;
}

.legend-icons {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 10px;
  margin-top: 8px;
  border-top: 1px solid rgba(60, 40, 30, 0.2);
  padding-top: 8px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.9em;
}

.legend-swatch {
  width: 14px;
  height: 14px;
  border-radius: 2px;
  border: 1px solid rgba(60, 40, 30, 0.5);
  box-shadow: 1px 1px 2px rgba(0,0,0,0.1);
}

.legend-icon {
  width: 16px;
  height: 16px;
  position: relative;
  display: inline-block;
  filter: sepia(0.8) hue-rotate(-20deg) contrast(1.2); /* Match medieval tone */
}

.legend-icon.icon-city {
  border: 2px solid #2c1b18;
  border-bottom-width: 4px;
}

.legend-icon.icon-mountain {
  border-left: 7px solid transparent;
  border-right: 7px solid transparent;
  border-bottom: 12px solid #5c4e3d;
  width: 0;
  height: 0;
}

.legend-icon.icon-river {
  border-bottom: 2px solid #6d8faa;
  border-radius: 10px;
  transform: rotate(-20deg);
}

.legend-icon.icon-lake {
  background: #86b6d8;
  border: 1px solid #587a95;
  border-radius: 50%;
}

.legend-icon.icon-gorge {
  border-left: 2px solid #6b4b3a;
  border-right: 2px solid #6b4b3a;
  transform: skewX(-10deg);
}

.legend-icon.icon-forest {
  background: #7da168;
  border-radius: 2px;
}

.legend-icon.icon-temple {
  border: 2px solid #2c1b18;
  border-top-width: 4px;
}

.legend-icon.icon-ruin {
  border: 2px dashed #6b4b3a;
}

.legend-icon.icon-mine {
  background: #c7b08b;
  transform: rotate(45deg);
}

.legend-icon.icon-desert {
  border-bottom: 2px solid #bfa97a;
  border-radius: 10px;
}
</style>
