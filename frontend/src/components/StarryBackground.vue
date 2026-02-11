<template>
  <div ref="container" class="starry-bg"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as THREE from 'three'

const container = ref(null)
let scene, camera, renderer, particles, material
let animationFrameId = null

// Texture generation for soft particles
const getTexture = () => {
  const canvas = document.createElement('canvas')
  canvas.width = 32
  canvas.height = 32
  const ctx = canvas.getContext('2d')
  
  const gradient = ctx.createRadialGradient(16, 16, 0, 16, 16, 16)
  gradient.addColorStop(0, 'rgba(255, 255, 255, 1)')
  gradient.addColorStop(0.2, 'rgba(255, 255, 255, 0.8)')
  gradient.addColorStop(0.5, 'rgba(255, 255, 255, 0.2)')
  gradient.addColorStop(1, 'rgba(0, 0, 0, 0)')
  
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, 32, 32)
  
  const texture = new THREE.Texture(canvas)
  texture.needsUpdate = true
  return texture
}

const init = () => {
  if (!container.value) return

  // Scene setup
  scene = new THREE.Scene()
  scene.fog = new THREE.FogExp2(0x000000, 0.0008) // Add fog for depth

  // Camera setup
  camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 1, 2000)
  camera.position.z = 1000

  // Renderer setup
  renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.setSize(window.innerWidth, window.innerHeight)
  renderer.setClearColor(0x000000, 0) // 设置透明度为0，完全透明
  container.value.appendChild(renderer.domElement)

  // Particles setup
  const geometry = new THREE.BufferGeometry()
  const count = 3000
  const positions = []
  const colors = []
  
  const color1 = new THREE.Color(0x8a2be2) // BlueViolet
  const color2 = new THREE.Color(0x4169e1) // RoyalBlue
  const color3 = new THREE.Color(0x00ffff) // Cyan

  for (let i = 0; i < count; i++) {
    // Random positions in a spread out volume
    const x = Math.random() * 2000 - 1000
    const y = Math.random() * 2000 - 1000
    const z = Math.random() * 2000 - 1000
    positions.push(x, y, z)

    // Mix colors based on position or random
    const mixedColor = color1.clone().lerp(color2, Math.random()).lerp(color3, Math.random() * 0.5)
    colors.push(mixedColor.r, mixedColor.g, mixedColor.b)
  }

  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))

  material = new THREE.PointsMaterial({
    size: 8,
    map: getTexture(),
    transparent: true,
    opacity: 0.8,
    vertexColors: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    sizeAttenuation: true
  })

  particles = new THREE.Points(geometry, material)
  scene.add(particles)

  // Add a second layer of smaller, more distant stars
  const starGeo = new THREE.BufferGeometry()
  const starCount = 5000
  const starPos = []
  for(let i=0; i<starCount; i++) {
    starPos.push(Math.random() * 3000 - 1500)
    starPos.push(Math.random() * 3000 - 1500)
    starPos.push(Math.random() * 3000 - 1500)
  }
  starGeo.setAttribute('position', new THREE.Float32BufferAttribute(starPos, 3))
  const starMat = new THREE.PointsMaterial({
    color: 0xffffff,
    size: 2,
    transparent: true,
    opacity: 0.6,
    blending: THREE.AdditiveBlending,
    sizeAttenuation: true
  })
  const stars = new THREE.Points(starGeo, starMat)
  scene.add(stars)

  animate()
}

const animate = () => {
  animationFrameId = requestAnimationFrame(animate)

  const time = Date.now() * 0.0005

  // Rotate the particle system
  if (particles) {
    particles.rotation.y = time * 0.1
    particles.rotation.x = time * 0.05
    
    // Pulse effect for size (requires shader or uniform update, but for basic material we can just rotate)
  }
  
  // Rotate scene slightly
  scene.rotation.z = time * 0.02

  renderer.render(scene, camera)
}

const onWindowResize = () => {
  if (!camera || !renderer) return
  camera.aspect = window.innerWidth / window.innerHeight
  camera.updateProjectionMatrix()
  renderer.setSize(window.innerWidth, window.innerHeight)
}

onMounted(() => {
  init()
  window.addEventListener('resize', onWindowResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onWindowResize)
  if (animationFrameId) cancelAnimationFrame(animationFrameId)
  if (renderer) {
    renderer.dispose()
    if (container.value && container.value.contains(renderer.domElement)) {
      container.value.removeChild(renderer.domElement)
    }
  }
  if (material) material.dispose()
})
</script>

<style scoped>
.starry-bg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  overflow: hidden;
  background-color: #000; /* Ensure black background if canvas fails or loads late */
}
</style>
