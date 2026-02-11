<template>
  <div ref="containerRef" class="real-map"></div>
</template>

<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import L from 'leaflet'

const props = defineProps({
  markers: { type: Array, default: () => [] },
  polylines: { type: Array, default: () => [] },
  events: { type: Array, default: () => [] },
  selectedCharacter: { type: String, default: '' },
  focusLocationId: { type: String, default: '' }
})

const emit = defineEmits(['select-location'])

const containerRef = ref(null)
let map = null
let markerLayer = null
let lineLayer = null
const markerIndex = new Map()

const setupDefaultIcon = () => {
  const iconRetinaUrl = new URL('leaflet/dist/images/marker-icon-2x.png', import.meta.url).toString()
  const iconUrl = new URL('leaflet/dist/images/marker-icon.png', import.meta.url).toString()
  const shadowUrl = new URL('leaflet/dist/images/marker-shadow.png', import.meta.url).toString()
  delete L.Icon.Default.prototype._getIconUrl
  L.Icon.Default.mergeOptions({ iconRetinaUrl, iconUrl, shadowUrl })
}

const buildLayers = () => {
  if (!map) return
  if (markerLayer) markerLayer.remove()
  if (lineLayer) lineLayer.remove()
  markerIndex.clear()

  markerLayer = L.layerGroup().addTo(map)
  lineLayer = L.layerGroup().addTo(map)

  const bounds = []
  
  // Build event map for quick lookup
  const locEvents = {}
  for (const e of props.events || []) {
    if (!e.location_id) continue
    if (!locEvents[e.location_id]) locEvents[e.location_id] = []
    locEvents[e.location_id].push(e)
  }

  const selected = (props.selectedCharacter || '').trim()

  for (const m of props.markers || []) {
    const lat = m.lat
    const lon = typeof m.lon === 'number' ? m.lon : m.lng
    if (typeof lat !== 'number' || typeof lon !== 'number') continue
    
    const locId = m.location_id || m.label || m.id
    const events = locEvents[locId] || []
    
    // Filter markers if a character is selected
    // Only show locations where the selected character has events
    if (selected) {
      const hasCharEvent = events.some(e => 
        e.characters && e.characters.includes(selected)
      )
      if (!hasCharEvent) continue
    }

    const label = m.label || m.name || locId
    
    // Generate parchment style popup content
    let popupContent = `<div style="font-family: 'Georgia', serif; color: #3d2b1f;">`
    popupContent += `<h3 style="margin: 0 0 8px 0; border-bottom: 1px solid #8b0000; padding-bottom: 4px;">${label}</h3>`
    
    if (m.description) {
       popupContent += `<p style="font-style: italic; margin-bottom: 8px; font-size: 0.9em;">${m.description}</p>`
    }
    
    if (events.length > 0) {
      popupContent += `<ul style="padding-left: 20px; margin: 0;">`
      const shownEvents = events.slice(0, 5) // Limit to 5 events
      for (const e of shownEvents) {
        const chars = (e.characters || []).join(', ')
        popupContent += `<li style="margin-bottom: 4px;">`
        if (chars) popupContent += `<b>${chars}</b>: `
        popupContent += `${e.summary}</li>`
      }
      if (events.length > 5) {
        popupContent += `<li>... (还有 ${events.length - 5} 个事件)</li>`
      }
      popupContent += `</ul>`
    } else {
      popupContent += `<div style="opacity: 0.7; font-size: 0.9em;">暂无事件记录</div>`
    }
    popupContent += `</div>`

    const marker = L.marker([lat, lon])
      .addTo(markerLayer)
      .bindPopup(popupContent, { maxWidth: 300 })
      
    if (locId) markerIndex.set(locId, marker)
    marker.on('click', () => emit('select-location', locId))
    bounds.push([lat, lon])
  }

  for (const p of props.polylines || []) {
    if (selected && p.character !== selected) continue
    const coords = p.geometry?.coordinates
    if (!Array.isArray(coords) || coords.length < 2) continue
    const latlngs = coords
      .map(([lon, lat]) => ([lat, lon]))
      .filter(x => Array.isArray(x) && typeof x[0] === 'number' && typeof x[1] === 'number')
    if (latlngs.length < 2) continue
    // Use dark red/brown for ink style routes
    L.polyline(latlngs, { color: '#8b0000', weight: 4, opacity: 0.8, dashArray: '5, 10', lineCap: 'round' }).addTo(lineLayer)
  }

  if (bounds.length > 0) {
    map.fitBounds(bounds, { padding: [30, 30] })
  } else {
    map.setView([34.3, 108.9], 4)
  }
}

const focusLocation = () => {
  if (!map) return
  const locId = (props.focusLocationId || '').trim()
  if (!locId) return
  const marker = markerIndex.get(locId)
  if (!marker) return
  map.setView(marker.getLatLng(), Math.max(map.getZoom(), 10))
  marker.openPopup()
}

onMounted(() => {
  setupDefaultIcon()
  map = L.map(containerRef.value, { zoomControl: true })
  const tileSources = [
    {
      // Geoq (China-friendly, fast, standard coordinates)
      url: 'https://map.geoq.cn/ArcGIS/rest/services/ChinaOnlineCommunity/MapServer/tile/{z}/{y}/{x}',
      options: { maxZoom: 19, attribution: '© Geoq' }
    },
    {
      url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
      options: { maxZoom: 19, attribution: '© CARTO' }
    },
    {
      url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      options: { maxZoom: 19, attribution: '© OpenStreetMap' }
    }
  ]
  let tileIndex = 0
  let tileLayer = L.tileLayer(tileSources[tileIndex].url, tileSources[tileIndex].options).addTo(map)
  tileLayer.on('tileerror', () => {
    if (tileIndex >= tileSources.length - 1) return
    tileIndex += 1
    if (tileLayer) tileLayer.remove()
    tileLayer = L.tileLayer(tileSources[tileIndex].url, tileSources[tileIndex].options).addTo(map)
  })
  buildLayers()
  focusLocation()
})

onUnmounted(() => {
  if (map) map.remove()
  map = null
})

watch(
  () => [props.markers, props.polylines, props.selectedCharacter],
  () => {
    buildLayers()
    focusLocation()
  }
)

watch(
  () => props.focusLocationId,
  () => focusLocation()
)
</script>

<style>
/* Global style override for Leaflet tiles in this component context */
.leaflet-tile-pane {
  filter: sepia(0.5) contrast(0.95) brightness(0.9) saturate(0.6) hue-rotate(-10deg);
}
.leaflet-container {
  background-color: #f4e4bc !important; /* Match parchment background */
}
</style>

<style scoped>
.real-map {
  width: 100%;
  height: 100%;
}
</style>
