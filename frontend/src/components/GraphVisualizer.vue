<template>
  <div class="cosmos-container" ref="container">
    <div ref="graphContainer" class="graph-container"></div>
    
    <!-- Modals removed, using Sidebar in parent view -->
    
    <!-- UI Overlay (HUD) -->
    <div class="hud-layer">
      <div class="hud-header">
        <div class="hud-title">COSMIC WEB // <span class="accent">全息关系网</span></div>
        <div class="hud-subtitle">3D DYNAMIC VISUALIZATION</div>
      </div>

      <div class="controls">
        <button class="control-btn" @click="toggleRotation" :class="{ active: autoRotate }">
          {{ autoRotate ? '⏸ 暂停旋转' : '▶ 自动旋转' }}
        </button>
        <button class="control-btn" @click="resetCamera">
          ⟲ 重置视角
        </button>
      </div>

      <!-- Legend Overlay -->
      <div class="legend-overlay">
        <div class="legend-items">
          <div 
            v-for="(config, type) in TYPE_CONFIG" 
            :key="type" 
            class="legend-item"
            :class="{ 'active': activeFilter === type, 'dimmed': activeFilter && activeFilter !== type }"
            @click="toggleFilter(type)"
          >
            <div class="dot-container">
              <div class="legend-dot" :style="{ backgroundColor: config.color, boxShadow: `0 0 8px ${config.color}` }"></div>
            </div>
            <div class="legend-info">
              <div class="legend-label">{{ config.label }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import ForceGraph3D from '3d-force-graph'
import SpriteText from 'three-spritetext'
import * as THREE from 'three'
import { CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js'
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js'

// Procedural Planet Texture Generator
const createPlanetTexture = () => {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 512;
    const ctx = canvas.getContext('2d');
    
    // Base Noise
    ctx.fillStyle = '#888888';
    ctx.fillRect(0,0,512,512);
    
    for (let i = 0; i < 2000; i++) {
        const x = Math.random() * 512;
        const y = Math.random() * 512;
        const r = Math.random() * 40 + 5;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,255,255,${Math.random() * 0.1})`;
        ctx.fill();
    }

    // Dark patches
    for (let i = 0; i < 1000; i++) {
        const x = Math.random() * 512;
        const y = Math.random() * 512;
        const r = Math.random() * 20 + 2;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(0,0,0,${Math.random() * 0.15})`;
        ctx.fill();
    }
    
    const tex = new THREE.CanvasTexture(canvas);
    return tex;
}
const planetTexture = createPlanetTexture();

const props = defineProps({
  data: Object,
  layoutMode: {
    type: String,
    default: 'force'
  }
})

const emit = defineEmits(['select-node', 'select-edge', 'clear-selection'])

const focusNode = (nodeId) => {
  if (!graphInstance.value) return
  const graph = graphInstance.value
  const { nodes } = graph.graphData()
  const node = nodes.find(n => n.id === nodeId)
  
  if (node) {
    const distance = 120
    const distRatio = 1 + distance/Math.hypot(node.x, node.y, node.z)
    
    graph.cameraPosition(
      { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio }, // new position
      node, // lookAt ({ x, y, z })
      2000  // ms transition duration
    )
    
    // Trigger selection
    selectedNode.value = node
    selectedEdge.value = null
    emit('select-node', node)
  }
}

defineExpose({
  focusNode
})

const container = ref(null)
const graphContainer = ref(null)
const selectedNode = ref(null)
const selectedEdge = ref(null)
const activeFilter = ref(null)
const graphInstance = ref(null)
const autoRotate = ref(true)
let animationFrameId = null
let resizeObserver = null

// --- Style Config ---
const COLORS = {
  bg: '#000005', // Deep space
  protagonist: '#FFD700', // Gold
  antagonist: '#FF2A68', // Pink/Red
  supporting: '#00E5FF', // Cyan
  neutral: '#E0E0E0',
  family: '#69F0AE',
  social: '#448AFF',
  romance: '#FF5252',
  conflict: '#FFAB40',
  work: '#E040FB',
  other: '#B0BEC5'
}

const TYPE_CONFIG = {
  family: { label: '亲属', color: COLORS.family },
  social: { label: '社交', color: COLORS.social },
  romance: { label: '情感', color: COLORS.romance },
  conflict: { label: '冲突', color: COLORS.conflict },
  work: { label: '工作', color: COLORS.work }
}

const getRelationColor = (type) => COLORS[type?.toLowerCase()] || COLORS.other
const getNodeColor = (type) => {
  if (['protagonist', 'antagonist', 'supporting', 'neutral'].includes(type)) return COLORS[type]
  return COLORS.neutral
}
const getLinkLabel = (link) => link.label || link.relation || link.type || ''
const maxVisibleLinkLabels = 100

const getLinkNodeId = (node) => node?.id || node?.name || node

const parseLinkWeight = (link) => {
  const weight = Number(link?.weight)
  return Number.isFinite(weight) ? weight : 1
}

const rankLinkLabels = (links) => {
  const sorted = [...links].sort((a, b) => {
    const wa = parseLinkWeight(a)
    const wb = parseLinkWeight(b)
    if (wb !== wa) return wb - wa
    const ea = (a.evidence || '').length
    const eb = (b.evidence || '').length
    return eb - ea
  })
  sorted.forEach((link, index) => {
    link.__labelRank = index
    link.__labelOffset = (index % 2 === 0 ? 1 : -1) * 4
  })
}

const shouldShowLinkLabel = (link) => {
  if (!link) return false
  if (selectedEdge.value) return link === selectedEdge.value
  if (selectedNode.value) {
    const src = getLinkNodeId(link.source)
    const tgt = getLinkNodeId(link.target)
    return src === selectedNode.value.id || tgt === selectedNode.value.id
  }
  const rank = link.__labelRank ?? 9999
  return rank < maxVisibleLinkLabels
}

// --- Data Normalization ---
const normalizeGraphData = (rawNodes, rawLinks) => {
  const nodes = Array.isArray(rawNodes) ? rawNodes.map(n => ({ ...n })) : []
  const nodeMap = new Map()
  nodes.forEach(n => {
    const id = n.id || n.name || n.label
    if (!id) return
    n.id = id
    if (!n.label) n.label = id
    nodeMap.set(id, n)
  })

  const links = Array.isArray(rawLinks) ? rawLinks.map(l => ({ ...l })) : []
  const normalizedLinks = links.map(l => {
    const source = l.source?.id || l.source?.name || l.source
    const target = l.target?.id || l.target?.name || l.target
    if (!source || !target) return null
    if (!nodeMap.has(source)) {
      const node = { id: source, label: source }
      nodeMap.set(source, node)
      nodes.push(node)
    }
    if (!nodeMap.has(target)) {
      const node = { id: target, label: target }
      nodeMap.set(target, node)
      nodes.push(node)
    }
    return { ...l, source, target }
  }).filter(Boolean)

  return { nodes, links: normalizedLinks }
}

// --- 3D Graph Init ---
const initGraph = () => {
  if (!graphContainer.value) return

  const Graph = ForceGraph3D({
    extraRenderers: [new CSS2DRenderer()]
  })(graphContainer.value)
    .backgroundColor('#00000000')
    .showNavInfo(false)
    .nodeId('id')
    .nodeLabel(null) // Disable default tooltip (we use SpriteText)
    .nodeColor(node => getNodeColor(node.type))
    .nodeRelSize(4)
    // Custom Node Object (Planet + Text)
    .nodeThreeObject(node => {
        const color = getNodeColor(node.type)
        const group = new THREE.Group()

        // 1. Planet Surface
        // User requested size comparable to galaxy particles (size ~2.5)
        // We set radius range 1.5 - 4 (Diameter 3 - 8)
        const size = Math.max(1.5, Math.min((node.degree || 1) * 0.5, 4));
        const geometry = new THREE.SphereGeometry(size, 32, 32)
        const material = new THREE.MeshStandardMaterial({ 
            color: color,
            map: planetTexture,
            bumpMap: planetTexture,
            bumpScale: 0.5,
            roughness: 0.6,
            metalness: 0.1,
            emissive: color,
            emissiveIntensity: 0.2 // Low emissive, rely on external light for shape
        })
        const planet = new THREE.Mesh(geometry, material)
        group.add(planet)

        // 2. Atmosphere / Glow
        const atmoGeo = new THREE.SphereGeometry(size * 1.2, 32, 32)
        const atmoMat = new THREE.MeshPhongMaterial({
            color: color,
            transparent: true,
            opacity: 0.15,
            blending: THREE.AdditiveBlending,
            side: THREE.BackSide // Render on inside to look like glow? No, FrontSide is fine for cloud layer
        })
        const atmosphere = new THREE.Mesh(atmoGeo, atmoMat)
        group.add(atmosphere)

        // 3. Ring (for large nodes)
        if (size > 3) { // Lower threshold for rings
            const ringGeo = new THREE.RingGeometry(size * 1.4, size * 2.2, 64);
            const ringMat = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.3,
                side: THREE.DoubleSide
            });
            const ring = new THREE.Mesh(ringGeo, ringMat);
            ring.rotation.x = Math.random() * Math.PI;
            ring.rotation.y = Math.random() * Math.PI;
            group.add(ring);
        }

        // Store rotation speed
        group.userData = {
            rotSpeed: (Math.random() - 0.5) * 0.02,
            cloudSpeed: (Math.random() - 0.5) * 0.01
        }

        // Text Label
        const label = new SpriteText(node.label || node.id)
        label.color = '#FFFFFF' // Pure white
        label.textHeight = 8 // Increased from 6
        label.backgroundColor = 'rgba(0,0,0,0.6)' // Darker background for contrast
        label.padding = 3 // More padding
        label.borderRadius = 4
        label.fontWeight = 'bold' // Bold text
        label.position.y = - (size * 1.5 + 5)
        group.add(label)

        return group
    })
    .linkWidth(link => link === selectedEdge.value ? 1 : 0.3) // Thinner lines
    .linkColor(link => {
        if (selectedEdge.value === link) return '#FFF'
        // Use a more subtle, uniform color for non-selected links, or keeping relation color but very faint
        // Let's stick to relation color but ensure opacity handles the "subtlety"
        return getRelationColor(link.type)
    })
    .linkOpacity(0.15) // Very faint, barely visible until bloom hits it
    .linkDirectionalParticles(0) // No particles for "cleaner, high-end" look
    // .linkDirectionalParticleWidth(3) 
    // .linkDirectionalParticleSpeed(0.01) 
    // .linkDirectionalParticleColor(() => '#FFFFFF') 
    // Edge Labels
    .linkThreeObjectExtend(true)
    .linkThreeObject(link => {
        const sprite = new SpriteText(getLinkLabel(link));
        sprite.color = 'rgba(255, 255, 255, 0.9)';
        sprite.textHeight = 3;
        sprite.backgroundColor = 'rgba(0,0,0,0.5)';
        sprite.padding = 1.2;
        sprite.borderRadius = 2;
        sprite.userData = { link }
        return sprite;
    })
    .linkPositionUpdate((sprite, { start, end }, link) => {
        const middlePos = Object.assign(...['x', 'y', 'z'].map(c => ({
            [c]: start[c] + (end[c] - start[c]) / 2 // calc middle point
        })));
        const linkData = link || sprite.userData?.link
        let offset = new THREE.Vector3(0, 0, 0)
        if (linkData && linkData.__labelOffset) {
            const dir = new THREE.Vector3(end.x - start.x, end.y - start.y, end.z - start.z)
            const len = dir.length()
            if (len > 0.0001) {
                const axis = Math.abs(dir.y / len) < 0.9 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0)
                offset = new THREE.Vector3().crossVectors(dir, axis).normalize().multiplyScalar(linkData.__labelOffset)
            }
        }
        Object.assign(sprite.position, {
          x: middlePos.x + offset.x,
          y: middlePos.y + offset.y,
          z: middlePos.z + offset.z
        })
        sprite.visible = shouldShowLinkLabel(linkData)
    })
    // Click Handlers
    .onNodeClick(node => {
        // Double Click Detection
        const now = Date.now();
        if (node._lastClick && (now - node._lastClick < 300)) {
            // Double Click
            node._lastClick = 0; // Reset
            emit('node-double-click', node);
            return;
        }
        node._lastClick = now;

        // Single Click Logic (Always runs, providing instant feedback)
        if (selectedNode.value !== node) {
             selectedNode.value = node
             selectedEdge.value = null
             autoRotate.value = false // Stop rotation to prevent jitter
             if (Graph.controls()) Graph.controls().autoRotate = false
             emit('select-node', node)
             
             // Update Highlights
             updateHighlights(node)
             
             // Fly to node
             const distance = 120
             const distRatio = 1 + distance/Math.hypot(node.x, node.y, node.z)
             Graph.cameraPosition(
                 { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio }, // new position
                 node, // lookAt ({ x, y, z })
                 2000  // ms transition duration
             )
        }
    })
    .onLinkClick(link => {
        selectedEdge.value = link
        selectedNode.value = null
        emit('select-edge', link)
        updateHighlights(null) // Clear neighbor highlights
    })
    .onBackgroundClick(() => {
        selectedNode.value = null
        selectedEdge.value = null
        emit('clear-selection')
        updateHighlights(null) // Reset all
    })

  // Helper for highlighting
  const updateHighlights = (centerNode) => {
      const { nodes, links } = Graph.graphData()
      
      const relatedNodeIds = new Set()
      const relatedLinks = new Set()
      
      if (centerNode) {
          relatedNodeIds.add(centerNode.id)
          links.forEach(link => {
              if (link.source.id === centerNode.id || link.target.id === centerNode.id) {
                  relatedLinks.add(link)
                  relatedNodeIds.add(link.source.id)
                  relatedNodeIds.add(link.target.id)
              }
          })
      }
      
      // Update Links
      Graph.linkWidth(link => {
          if (centerNode) return relatedLinks.has(link) ? 1.5 : 0.1
          return 0.3
      })
      .linkColor(link => {
           if (centerNode) return relatedLinks.has(link) ? '#FFF' : '#333' // Fade others to dark
           return getRelationColor(link.type)
      })
      .linkOpacity(link => {
           if (centerNode) return relatedLinks.has(link) ? 0.8 : 0.05
           return 0.15
      })
      
      // Update Nodes
      nodes.forEach(node => {
          const group = node.__threeObj
          if (!group) return
          
          const isRelated = !centerNode || relatedNodeIds.has(node.id)
          const opacity = isRelated ? 1 : 0.1
          
          // Traverse and dim
          group.traverse(obj => {
              if (obj.material) {
                  obj.material.transparent = true
                  obj.material.opacity = opacity
                  // Reduce emissive for non-related
                  if (obj.material.emissiveIntensity !== undefined) {
                      obj.material.emissiveIntensity = isRelated ? 0.2 : 0
                  }
              }
              // Hide label for non-related if busy?
              // if (obj.type === 'Sprite' && obj !== group.children.find(c => c.isMesh)) { // Text sprite
              //    obj.visible = isRelated
              // }
          })
      })
  }

  // Lighting
  const ambientLight = new THREE.AmbientLight(0x404040, 0.2) // Low ambient for contrast
  Graph.scene().add(ambientLight)
  const dirLight = new THREE.DirectionalLight(0xffffff, 2.0) // Strong sun light
  dirLight.position.set(100, 100, 100)
  Graph.scene().add(dirLight)
  const pointLight = new THREE.PointLight(0xffffff, 0.2) // Faint camera light
  Graph.scene().add(pointLight)

  // Physics / Layout Config
  // Extreme repulsion to force "Satellite" layout
  Graph.d3Force('charge').strength(-2000) 
  Graph.d3Force('link').distance(100) // Reduced from 200 to fit better in ring
  // Custom Force: Flatten to Disk & Constrain to Ring
  Graph.d3Force('galaxy_layout', (alpha) => {
      const nodes = Graph.graphData().nodes;
      // Ring particles are generated from R=150 to R=600
      // We place nodes strictly within this range
      const ringInnerRadius = 180; // Adjusted to be closer to starfield start
      const ringOuterRadius = 500; // Adjusted to be safely inside starfield end
      const tiltAngle = 0.2; // Match galaxy.rotation.z
      const tanTilt = Math.tan(tiltAngle);

      nodes.forEach(node => {
          // 1. Flatten to Tilted Plane (Y = X * tan(0.2))
          // The galaxy is rotated around Z axis, so the plane equation involves X and Y.
          // Target Y is based on X.
          const targetY = node.x * tanTilt;
          
          // Strong force to keep them on the tilted plane
          node.vy -= (node.y - targetY) * 1.0 * alpha; 
          
          // Limit vertical deviation from plane (hard constraint if too far)
          // Tightened from 50 to 20 to match galaxy thickness
          if (Math.abs(node.y - targetY) > 20) {
              node.vy -= Math.sign(node.y - targetY) * 20 * alpha;
          }

          // 2. Radial Constraints (using 3D distance)
          const r = Math.sqrt(node.x * node.x + node.y * node.y + node.z * node.z);
          
          // Normalized vector from center (direction of push/pull)
          // Avoid division by zero
          const nx = r > 0.1 ? node.x / r : 1;
          const ny = r > 0.1 ? node.y / r : 0;
          const nz = r > 0.1 ? node.z / r : 0;

          // Push out from center (Don't hide in the central sphere)
          if (r < ringInnerRadius) {
              const dist = ringInnerRadius - r;
              const strength = dist * 2.0 * alpha; // Stronger push (was 0.8)
              
              node.vx += nx * strength;
              node.vy += ny * strength;
              node.vz += nz * strength;
          }

          // Pull in from outer edge (Keep within ring)
          if (r > ringOuterRadius) {
              const dist = r - ringOuterRadius;
              const strength = dist * 2.0 * alpha; // Stronger pull (was 0.8)
              
              node.vx -= nx * strength;
              node.vy -= ny * strength;
              node.vz -= nz * strength;
          }
      });
  });

  // Weak center force to keep them from drifting to infinity, 
  // but we rely on 'galaxy_layout' to keep them out of the center.
  Graph.d3Force('center').strength(0.01)

  // Starfield Background
  const galaxyUniforms = { time: { value: 0 } }
  const starField = addStarfield(Graph.scene(), galaxyUniforms)

  // Bloom Effect
  const bloomPass = new UnrealBloomPass()
  bloomPass.strength = 0.35 // Reduced from 0.6 to reduce light pollution
  bloomPass.radius = 0.1
  bloomPass.threshold = 0.5 // Increased from 0.2 so only bright objects glow
  Graph.postProcessingComposer().addPass(bloomPass)

  graphInstance.value = Graph
  
  // Auto Rotate & Animation Loop
  // Disable OrbitControls autoRotate because we want to sync with galaxy
  if (autoRotate.value) {
      Graph.controls().autoRotate = false 
  }

  // Custom Animation Loop
  const animate = () => {
      // 1. Rotate Galaxy
      if (starField) {
          // starField.rotation.y += 0.0005 // Disable independent rotation so it syncs with nodes
          galaxyUniforms.time.value += 0.01
      }
      
      // 2. Rotate Graph Nodes (Synchronized with Galaxy)
      // We rotate the entire scene group that holds the graph content
      // Note: ForceGraph3D adds objects to scene(), but doesn't expose a single container for nodes/links easily
      // So we rotate the camera in reverse to simulate the scene rotating? 
      // OR we can manually rotate the camera around the center at the same speed as the galaxy.
      
      if (autoRotate.value) {
          const angle = 0.00002; // Slower rotation (reduced from 0.0001)
          const cam = Graph.camera();
          const x = cam.position.x;
          const z = cam.position.z;
          cam.position.x = x * Math.cos(angle) - z * Math.sin(angle);
          cam.position.z = x * Math.sin(angle) + z * Math.cos(angle);
          cam.lookAt(0, 0, 0);
      }
          
          // Rotate Planets
          const { nodes } = Graph.graphData();
          if (nodes) {
              nodes.forEach(node => {
                  const obj = node.__threeObj;
                  if (obj && obj.userData.rotSpeed) {
                      // Planet rotation (child 0)
                      if (obj.children[0]) obj.children[0].rotation.y += obj.userData.rotSpeed;
                      // Atmosphere rotation (child 1)
                      if (obj.children[1]) obj.children[1].rotation.y -= obj.userData.cloudSpeed;
                  }
              });
          }

          // Force graph to rotate with galaxy
          // We manually update camera angle to simulate "orbiting with galaxy"
          // Or simpler: rotate the whole graph scene container? 
          // 3d-force-graph controls camera, so rotating camera is easier.
          // But user wants nodes to rotate *with* galaxy. 
          // Galaxy rotates at 0.0003 rad/frame. 
          // Let's rotate the graph scene group itself.
          const graphScene = Graph.scene();
          // The graph structure is inside the scene. But 3d-force-graph manages positions.
          // Rotating the camera is the standard way to "orbit".
          // If we want nodes to rotate relative to camera (which is static relative to galaxy?), 
          // it means camera rotates around center.
          // The previous autoRotate did exactly this.
          // User said "rotate with golden particles".
          
          // Let's ensure the rotation speed matches galaxy rotation direction
          // Galaxy rotates Y positive.
          // Camera auto-rotate usually orbits around.
          
          // Update camera light
          const cam = Graph.camera()
          pointLight.position.copy(cam.position)
          
          animationFrameId = requestAnimationFrame(animate)
      }
      animate()

  updateGraphData()
  handleResize()
}

const addStarfield = (scene, uniforms) => {
    // Galaxy Logic from User Snippet
    // Central Sphere (50,000 pts) + Outer Disk (100,000 pts)
    const pts = []
    const sizes = []
    const shift = []

    const pushShift = () => {
        shift.push(
            Math.random() * Math.PI,
            Math.random() * Math.PI * 2,
            (Math.random() * 0.9 + 0.1) * Math.PI * 0.1,
            Math.random() * 0.9 + 0.1
        )
    }

    // 1. Central Sphere
    for (let i = 0; i < 4000; i++) {
        sizes.push(Math.random() * 1.5 + 0.5)
        pushShift()
        const p = new THREE.Vector3().randomDirection().multiplyScalar(Math.random() * 0.5 + 9.5)
        // Scale up to fit our scene (graph is ~100-500 units)
        // User snippet was small (9.5-10), we need larger.
        // Adjusted scale to 15 to bring galaxy closer to nodes (Radius ~150)
        p.multiplyScalar(15) 
        pts.push(p)
    }

    // 2. Outer Disk
    for (let i = 0; i < 15000; i++) {
        let r = 10, R = 40
        let rand = Math.pow(Math.random(), 1.5)
        let radius = Math.sqrt(R * R * rand + (1 - rand) * r * r)
        
        const p = new THREE.Vector3().setFromCylindricalCoords(
            radius, 
            Math.random() * 2 * Math.PI, 
            (Math.random() - 0.5) * 2
        )
        // Scale up
        p.multiplyScalar(15)
        
        pts.push(p)
        sizes.push(Math.random() * 1.5 + 0.5)
        pushShift()
    }

    const geometry = new THREE.BufferGeometry().setFromPoints(pts)
    geometry.setAttribute('sizes', new THREE.Float32BufferAttribute(sizes, 1))
    geometry.setAttribute('shift', new THREE.Float32BufferAttribute(shift, 4))

    const material = new THREE.PointsMaterial({
        size: 2.5, // Adjusted for scale
        transparent: true,
        opacity: 0.6, // More transparent
        depthTest: false,
        blending: THREE.AdditiveBlending,
        onBeforeCompile: shader => {
            shader.uniforms.time = uniforms.time
            
            shader.vertexShader = `
                uniform float time;
                attribute float sizes;
                attribute vec4 shift;
                varying vec3 vColor;
                ${shader.vertexShader}
            `.replace(
                `gl_PointSize = size;`,
                `gl_PointSize = size * sizes;`
            ).replace(
                `#include <color_vertex>`,
                `#include <color_vertex>
                // Adjust for our scale (scale 15)
                float d = length(abs(position) / vec3(600., 150., 600.)); 
                d = clamp(d, 0., 1.);
                // Changed to white/pale gold for less distraction
                vColor = mix(vec3(255., 255., 255.), vec3(255., 240., 200.), d) / 255.;`
            ).replace(
                `#include <begin_vertex>`,
                `#include <begin_vertex>
                float t = time;
                float moveT = mod(shift.x + shift.z * t, 6.28318);
                float moveS = mod(shift.y + shift.z * t, 6.28318);
                transformed += vec3(cos(moveS) * sin(moveT), cos(moveT), sin(moveS) * sin(moveT)) * shift.w * 15.0; // Scale movement too
                `
            )

            shader.fragmentShader = `
                varying vec3 vColor;
                ${shader.fragmentShader}
            `.replace(
                `#include <clipping_planes_fragment>`,
                `#include <clipping_planes_fragment>
                float d = length(gl_PointCoord.xy - 0.5);
                if (d > 0.5) discard;
                `
            ).replace(
                `vec4 diffuseColor = vec4( diffuse, opacity );`,
                `vec4 diffuseColor = vec4( vColor, opacity );`
            )
        }
    })

    const galaxy = new THREE.Points(geometry, material)
    galaxy.rotation.order = 'ZYX'
    galaxy.rotation.z = 0.2
    scene.add(galaxy)
    return galaxy
}

const updateGraphData = () => {
  if (!graphInstance.value || !props.data) return

  const normalized = normalizeGraphData(props.data.nodes || [], props.data.edges || props.data.links || [])
  let nodes = normalized.nodes
  let links = normalized.links

  if (activeFilter.value) {
    links = links.filter(l => l.type === activeFilter.value)
    const activeNodeIds = new Set()
    links.forEach(l => {
      activeNodeIds.add(l.source.id || l.source)
      activeNodeIds.add(l.target.id || l.target)
    })
    nodes = nodes.filter(n => activeNodeIds.has(n.id))
  }

  rankLinkLabels(links)
  graphInstance.value.graphData({ nodes, links })
}

// --- Interaction ---
const toggleRotation = () => {
    autoRotate.value = !autoRotate.value
    if (graphInstance.value) {
        // Always keep OrbitControls autoRotate OFF to prevent conflict with manual rotation
        graphInstance.value.controls().autoRotate = false
    }
}

const resetCamera = () => {
    if (graphInstance.value) {
        graphInstance.value.cameraPosition({ x: 0, y: 0, z: 600 }, { x: 0, y: 0, z: 0 }, 2000)
    }
}

const toggleFilter = (type) => {
  activeFilter.value = activeFilter.value === type ? null : type
}

// Modals handled by parent


const handleResize = () => {
    if (graphInstance.value && graphContainer.value) {
        const { clientWidth, clientHeight } = container.value
        graphInstance.value.width(clientWidth)
        graphInstance.value.height(clientHeight)
    }
}

// --- Watchers & Lifecycle ---
watch(() => props.data, () => updateGraphData(), { deep: true })
watch(activeFilter, updateGraphData)

onMounted(() => {
  initGraph()
  window.addEventListener('resize', handleResize)
  if (container.value && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(handleResize)
    resizeObserver.observe(container.value)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (resizeObserver) resizeObserver.disconnect()
  if (animationFrameId) cancelAnimationFrame(animationFrameId)
  if (graphInstance.value) graphInstance.value._destructor()
})
</script>

<style scoped>
.cosmos-container {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
  background: radial-gradient(circle at center, #111 0%, #000 100%);
}

.graph-container {
  width: 100%;
  height: 100%;
}

/* Controls */
.controls {
    position: absolute;
    bottom: 100px;
    right: 24px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    pointer-events: auto;
    z-index: 20;
}

.control-btn {
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.2);
    color: #FFF;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    transition: all 0.2s;
    backdrop-filter: blur(4px);
}

.control-btn:hover {
    background: rgba(255,255,255,0.2);
}

.control-btn.active {
    background: rgba(253, 184, 19, 0.2);
    border-color: rgba(253, 184, 19, 0.5);
    color: #FDB813;
}

/* UI Overlays */
/* Modals removed */

.hud-layer {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  padding: 24px;
  pointer-events: none;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}

.hud-header {
  text-align: left;
}

.hud-title {
  font-size: 24px;
  font-weight: 800;
  color: #FFF;
  letter-spacing: 2px;
  text-shadow: 0 0 10px rgba(255, 255, 255, 0.3);
  font-family: "Songti SC", serif;
}

.accent { color: #FFD700; }

.hud-subtitle {
  font-size: 10px;
  color: #666;
  letter-spacing: 4px;
  margin-top: 4px;
}

.legend-overlay {
  pointer-events: auto;
}

.legend-items {
  display: flex;
  gap: 16px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: all 0.3s;
  padding: 6px 12px;
  background: rgba(0, 0, 0, 0.4);
  border-radius: 20px;
  border: 1px solid transparent;
}

.legend-item:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.2);
}

.legend-item.active {
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.4);
}

.legend-item.dimmed {
  opacity: 0.3;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.legend-label {
  font-size: 12px;
  color: #CCC;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Stats Grid removed with modals */
</style>
