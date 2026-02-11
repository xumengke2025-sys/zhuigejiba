<template>
  <div class="trace-view">
    <header class="app-header">
      <div class="brand" @click="resetSession">追迹</div>
      <div class="status-badge" v-if="sessionId">
        <span class="dot" :class="status"></span>
        {{ statusText }}
      </div>
    </header>

    <main class="content">
      <aside class="left">
        <div class="scroll-style character-scroll" v-if="result">
          <div class="scroll-rod top"></div>
          <div class="scroll-content">
             <div class="scroll-title">筛选维度</div>
             
             <div class="filter-group">
               <label>角色</label>
               <select class="select scroll-select" v-model="selectedCharacter">
                <option value="">全部角色</option>
                <option v-for="c in characters" :key="c" :value="c">{{ c }}</option>
               </select>
             </div>

             <div class="filter-group">
               <label>地点类型</label>
               <select class="select scroll-select" v-model="selectedKind">
                <option value="">全部类型</option>
                <option v-for="k in availableKinds" :key="k" :value="k">{{ k }}</option>
               </select>
             </div>

             <div class="filter-group">
               <label>关键词</label>
               <input class="input scroll-input" v-model="searchKeyword" placeholder="搜地点/事件..." />
             </div>
          </div>
          <div class="scroll-rod bottom"></div>
        </div>

        <div class="card" v-if="!sessionId">
          <div class="title">上传整篇小说（TXT）</div>
          <div
            class="upload"
            :class="{ drag: isDragOver, has: file }"
            @dragover.prevent="isDragOver = true"
            @dragleave.prevent="isDragOver = false"
            @drop.prevent="handleDrop"
            @click="triggerFileInput"
          >
            <input ref="fileInput" type="file" class="hidden" accept=".txt" @change="handleFileChange" />
            <div v-if="!file" class="placeholder">
              <div class="big">点击或拖拽 TXT</div>
              <div class="sub">支持长篇小说（最多 300 万字）</div>
            </div>
            <div v-else class="file">
              <div class="name">{{ file.name }}</div>
              <div class="sub">{{ formatSize(file.size) }}</div>
              <button class="remove" @click.stop="file = null">×</button>
            </div>
          </div>
          <button class="primary" :disabled="loading || !file" @click="handleAnalyze">
            {{ loading ? '正在启动...' : '开始分析足迹' }}
          </button>
          <div class="demo-link" @click="handleLoadDemo">或 查看《云山传》样例效果</div>
        </div>

        <div class="card" v-else>
          <div class="title">分析进度</div>
          <div class="row">
            <div class="k">进度</div>
            <div class="v">{{ progress }}%</div>
          </div>
          <div class="progress">
            <div class="bar" :style="{ width: progress + '%' }"></div>
          </div>
          <div class="msg">{{ statusMsg }}</div>
          <div class="logs" v-if="statusLogs.length">
            <div v-for="(l, i) in statusLogs" :key="i" class="log">
              <span class="t">{{ l.time }}</span>
              <span class="m">{{ l.msg }}</span>
            </div>
          </div>
          <button class="secondary" @click="resetSession">重新上传</button>
        </div>

        <div class="card" v-if="result">
          <div class="title">分析概览</div>
          <!-- Moved controls to top of map area -->
          <div class="row">
            <div class="k">状态</div>
            <div class="v">分析完成</div>
          </div>
        </div>
      </aside>

      <section class="right">
        <!-- Map Controls Bar (Moved out of map overlay) -->
        <div class="map-controls-bar" v-if="result">
          <div class="control-group stats">
            <span class="stat-item">事件: {{ result.overview?.event_count || 0 }}</span>
            <span class="stat-item">地点: {{ result.overview?.location_count || 0 }}</span>
          </div>
          <div class="hint-text" v-if="viewMode === 'world'">
            <span class="icon">✨</span> 点击带光圈地点进入详情
          </div>
          <div class="tabs">
            <button class="tab" :class="{ active: activeTab === 'fictional' }" @click="activeTab = 'fictional'">地图</button>
            <button class="tab" :class="{ active: activeTab === 'events' }" @click="activeTab = 'events'">事件列表</button>
          </div>
        </div>

        <div v-if="!result" class="empty">
          <div class="big">把人物“走过哪里”变成地图</div>
          <div class="sub">上传小说，自动抽取地点、事件与角色路线，并构建虚拟地图</div>
        </div>

        <div class="result" v-if="result">
          <div class="panel" v-if="activeTab === 'fictional'">
            <CanvasMap
              v-if="viewMode === 'world'"
              :mapData="result.maps?.fictional_map || null"
              :events="result.events || []"
              :selectedCharacter="selectedCharacter"
              :visibleLocationIds="visibleLocationIds"
              :focusLocationId="focusLocationId"
              @select-location="handleSelectLocation"
            />
            <InteriorMap
              v-else
              :locationData="currentInteriorLocation"
              @back="handleBackToWorld"
            />
          </div>

          <div class="panel events" v-else>
            <div class="event" v-for="e in filteredEvents" :key="e.id" @click="selectEvent(e)">
              <div class="meta">
                <span class="ord">#{{ e.order }}</span>
                <span class="chap" v-if="e.chapter_hint">{{ e.chapter_hint }}</span>
              </div>
              <div class="place">
                <span class="loc">{{ e.location_id }}</span>
                <span class="tag" :class="locationTypeMap[e.location_id]">{{ locationTypeMap[e.location_id] || 'uncertain' }}</span>
              </div>
              <div class="sum">{{ e.summary || e.evidence }}</div>
              <div class="chars" v-if="e.characters?.length">{{ e.characters.join('、') }}</div>
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, shallowRef, defineAsyncComponent } from 'vue'
import toast from '../utils/toast'
import { analyzeTrace, getTraceStatus, getSampleData } from '../api/trace'
import Skeleton from '../components/Skeleton.vue'

import CanvasMap from '../components/CanvasMap.vue'
import InteriorMap from '../components/InteriorMap.vue'

const file = ref(null)
const fileInput = ref(null)
const isDragOver = ref(false)

const loading = ref(false)
const sessionId = ref(null)
const status = ref('idle')
const progress = ref(0)
const statusMsg = ref('')
const statusLogs = shallowRef([])
const result = shallowRef(null)
const pollTimer = ref(null)

const selectedCharacter = ref('')
const selectedKind = ref('')
const searchKeyword = ref('')
const activeTab = ref('fictional')
const focusLocationId = ref('')

const viewMode = ref('world') // 'world' | 'interior'
const currentInteriorLocation = shallowRef(null)

const availableKinds = computed(() => {
  if (!result.value || !result.value.locations) return []
  const kinds = new Set(result.value.locations.map(l => l.kind).filter(Boolean))
  return Array.from(kinds).sort()
})

const visibleLocationIds = computed(() => {
  if (!result.value) return null
  
  const hasChar = !!selectedCharacter.value
  const hasKind = !!selectedKind.value
  const hasKw = !!searchKeyword.value.trim()
  
  // If no filters are active, return null to let CanvasMap show all (default behavior)
  // BUT: CanvasMap's default behavior is "show all", but if selectedCharacter is passed as prop, 
  // it usually highlights that character's path.
  // Wait, if I pass visibleLocationIds=null, CanvasMap falls back to checking selectedCharacter prop.
  // If selectedCharacter is set, CanvasMap calculates visibility based on it.
  // So if only Character is selected, I can return null and let CanvasMap handle it?
  // NO, because I want to support combination (Char + Kind).
  // So if ANY filter is active (including Char), I should compute the set myself.
  
  if (!hasChar && !hasKind && !hasKw) return null
  
  let locs = result.value.locations || []
  
  // 1. Filter by Kind
  if (hasKind) {
    locs = locs.filter(l => l.kind === selectedKind.value)
  }
  
  // 2. Filter by Keyword
  if (hasKw) {
    const kw = searchKeyword.value.trim().toLowerCase()
    const matchingLocIds = new Set()
    
    // Check location fields
    locs.forEach(l => {
        if ((l.id || '').toLowerCase().includes(kw) || (l.description || '').toLowerCase().includes(kw)) {
            matchingLocIds.add(l.id)
        }
    })
    
    // Check events
    if (result.value.events) {
        result.value.events.forEach(e => {
            if ((e.summary || '').toLowerCase().includes(kw) || (e.evidence || '').toLowerCase().includes(kw)) {
                matchingLocIds.add(e.location_id)
            }
        })
    }
    
    locs = locs.filter(l => matchingLocIds.has(l.id))
  }
  
  // 3. Filter by Character
   if (hasChar) {
     const charLocs = new Set()
     if (result.value.events) {
         result.value.events.forEach(e => {
             if (e.characters && e.characters.includes(selectedCharacter.value)) {
                 charLocs.add(e.location_id)
             }
         })
     }
     locs = locs.filter(l => charLocs.has(l.id))
   }
   
   return locs.map(l => l.id)
 })

 const filteredEvents = computed(() => {
   if (!result.value || !result.value.events) return []
   
   const hasChar = !!selectedCharacter.value
   const hasKind = !!selectedKind.value
   const hasKw = !!searchKeyword.value.trim()
   
   if (!hasChar && !hasKind && !hasKw) return result.value.events
   
   let events = result.value.events
   
   // 1. Character
   if (hasChar) {
     events = events.filter(e => e.characters && e.characters.includes(selectedCharacter.value))
   }
   
   // 2. Kind
   if (hasKind) {
       const locKindMap = new Map()
       if (result.value.locations) {
           result.value.locations.forEach(l => locKindMap.set(l.id, l.kind))
       }
       events = events.filter(e => locKindMap.get(e.location_id) === selectedKind.value)
   }
   
   // 3. Keyword
   if (hasKw) {
       const kw = searchKeyword.value.trim().toLowerCase()
       events = events.filter(e => {
           return (e.summary || '').toLowerCase().includes(kw) || 
                  (e.evidence || '').toLowerCase().includes(kw) ||
                  (e.location_id || '').toLowerCase().includes(kw)
       })
   }
   
   return events
 })
 
 const handleSelectLocation = (locId) => {
  focusLocationId.value = locId
  console.log('Location Selected:', locId)

  if (!result.value) {
    console.warn('handleSelectLocation: No result data available')
    return
  }

  // 1. Try to find in fictional_map nodes (has layout info)
  const mapNodes = result.value.maps?.fictional_map?.nodes || []
  let mapNode = mapNodes.find(n => n.location_id === locId)
  
  // 2. Fallback to locations list (contains sub_map in sample data)
  const locations = result.value.locations || []
  const rawLoc = locations.find(l => l.id === locId)
  
  // If we found the raw location but it has sub_map and the mapNode doesn't, merge them
  if (rawLoc && rawLoc.sub_map && mapNode && !mapNode.sub_map) {
    console.log('Merging sub_map from raw location data for:', locId)
    mapNode = { ...mapNode, sub_map: rawLoc.sub_map }
  } else if (!mapNode && rawLoc) {
    console.log('Using raw location data as mapNode for:', locId)
    mapNode = { ...rawLoc, location_id: rawLoc.id }
  }

  if (mapNode) {
    const subNodes = mapNode.sub_map?.nodes || []
    const hasSubMapData = subNodes.length > 0 || !!mapNode.sub_map
    const explicitHasSubMap = mapNode.has_sub_map !== false && mapNode.has_sub_map !== undefined
    
    // 只要有子地图数据，或者显式标记了 has_sub_map，就允许下钻
    const canDrillDown = hasSubMapData || explicitHasSubMap
    
    console.log(`Drill down check for ${locId}:`, { hasSubMapData, explicitHasSubMap, canDrillDown })
    
    if (canDrillDown) {
      toast.success(`进入地点：${mapNode.label || mapNode.id}`)
      currentInteriorLocation.value = mapNode
      viewMode.value = 'interior'
    } else {
      toast.info(`选中地点：${mapNode.label || mapNode.id} (无内部地图)`)
    }
  } else {
    console.warn('handleSelectLocation: Node not found in map data:', locId)
  }
}

const handleBackToWorld = () => {
  viewMode.value = 'world'
  currentInteriorLocation.value = null
}

const statusText = computed(() => {
  const map = {
    idle: '待机',
    processing: '提取中',
    aggregating: '合并中',
    completed: '完成',
    failed: '失败'
  }
  return map[status.value] || status.value
})

const characters = computed(() => {
  const list = (result.value?.tracks || []).map(t => t.character).filter(Boolean)
  const uniq = Array.from(new Set(list))
  return uniq.slice(0, 200)
})

const locationTypeMap = computed(() => {
  const map = {}
  for (const l of result.value?.locations || []) {
    map[l.id] = l.place_type
  }
  return map
})

const triggerFileInput = () => fileInput.value?.click()

const handleFileChange = (e) => {
  const selected = e.target.files[0]
  if (selected) validateAndSetFile(selected)
}

const handleDrop = (e) => {
  isDragOver.value = false
  const selected = e.dataTransfer.files[0]
  if (selected) validateAndSetFile(selected)
}

const validateAndSetFile = (f) => {
  if (!f.name.endsWith('.txt')) {
    toast.error('仅支持 TXT 文件')
    return
  }
  if (f.size > 20 * 1024 * 1024) {
    toast.error('文件过大', '建议先去除重复空白或按章节拆分后再上传')
    return
  }
  file.value = f
}

const formatSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const handleAnalyze = async () => {
  loading.value = true
  result.value = null
  progress.value = 0
  statusLogs.value = []
  selectedCharacter.value = ''
  activeTab.value = 'fictional'
  focusLocationId.value = ''

  const closeLoading = toast.loading('正在上传并启动分析...')
  try {
    const formData = new FormData()
    formData.append('file', file.value)
    const res = await analyzeTrace(formData)
    if (res.success) {
      sessionId.value = res.session_id
      status.value = 'processing'
      startPolling()
    }
  } catch (err) {
    toast.error('启动失败', err.response?.data?.error || err.message)
  } finally {
    loading.value = false
    closeLoading()
  }
}

const handleLoadDemo = async () => {
  if (loading.value) return
  loading.value = true
  result.value = null
  progress.value = 0
  statusLogs.value = []
  selectedCharacter.value = ''
  activeTab.value = 'fictional'
  focusLocationId.value = ''

  const closeLoading = toast.loading('正在加载样例数据...')
  try {
    const res = await getSampleData()
    if (res.success) {
      sessionId.value = res.session_id
      status.value = 'completed'
      progress.value = 100
      statusMsg.value = '样例数据加载完成'
      result.value = res.result
      statusLogs.value = [{ time: new Date().toLocaleTimeString(), msg: '样例数据加载成功' }]
    } else {
      toast.error('加载失败', res.error)
    }
  } catch (err) {
    toast.error('加载失败', err.message)
  } finally {
    loading.value = false
    closeLoading()
  }
}

const startPolling = () => {
  if (pollTimer.value) clearInterval(pollTimer.value)
  pollTimer.value = setInterval(async () => {
    try {
      const res = await getTraceStatus(sessionId.value)
      if (!res.success) return
      status.value = res.status
      progress.value = res.progress
      if (res.message && res.message !== statusMsg.value) {
        statusMsg.value = res.message
        statusLogs.value.unshift({ time: new Date().toLocaleTimeString(), msg: res.message })
      }
      if (res.status === 'completed') {
        result.value = res.data
        clearInterval(pollTimer.value)
      }
      if (res.status === 'failed') {
        clearInterval(pollTimer.value)
        toast.error('分析失败', res.error)
      }
    } catch (err) {
      console.error(err)
    }
  }, 2000)
}

const resetSession = () => {
  if (pollTimer.value) clearInterval(pollTimer.value)
  sessionId.value = null
  status.value = 'idle'
  progress.value = 0
  statusMsg.value = ''
  statusLogs.value = []
  result.value = null
  file.value = null
  selectedCharacter.value = ''
  activeTab.value = 'fictional'
  focusLocationId.value = ''
}

const selectEvent = (e) => {
  if (!e) return
  focusLocationId.value = e.location_id
  activeTab.value = 'fictional'
  
  // Also check for interior map when selecting event
  const locations = result.value?.locations || []
  const loc = locations.find(l => l.id === e.location_id)
  if (loc && loc.sub_map) {
    currentInteriorLocation.value = loc
    viewMode.value = 'interior'
  } else {
    viewMode.value = 'world'
  }
}

onMounted(() => {})

onUnmounted(() => {
  if (pollTimer.value) clearTimeout(pollTimer.value)
})
</script>

<style scoped>
.trace-view {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #0b0c10;
  color: #e6e6e6;
}
.app-header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(12, 12, 16, 0.8);
  backdrop-filter: blur(10px);
}
.brand {
  font-weight: 800;
  letter-spacing: 1px;
  cursor: pointer;
}
.status-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #bbb;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #666;
}
.dot.processing, .dot.aggregating { background: #ffb300; }
.dot.completed { background: #4caf50; }
.dot.failed { background: #f44336; }

.demo-link {
  margin-top: 16px;
  font-size: 13px;
  color: #666;
  text-decoration: underline;
  cursor: pointer;
  text-align: center;
  user-select: none;
}
.demo-link:hover {
  color: #999;
}

.content {
  flex: 1;
  display: flex;
  min-height: 0;
}
.left {
  width: 360px;
  padding: 16px;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  overflow-y: auto;
  background: rgba(12, 12, 16, 0.6);
}
.right {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  min-width: 0;
}

.map-controls-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: #fdf5e6;
  padding: 4px 16px;
  border-bottom: 2px solid #8b6c42;
  font-family: "IM Fell English SC", Georgia, "Times New Roman", serif;
  color: #3d2b1f;
  min-height: 40px;
  box-sizing: border-box;
}

.hint-text {
  font-size: 13px;
  color: #8b6c42;
  font-style: italic;
  margin: 0 10px;
}

.control-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.control-group.stats {
  border-left: 1px solid rgba(60, 45, 30, 0.2);
  border-right: 1px solid rgba(60, 45, 30, 0.2);
  padding: 0 12px;
}

.stat-item {
  font-size: 13px;
  font-weight: bold;
  color: #3d2b1f;
  margin-right: 6px;
}

.tabs {
  display: flex;
  gap: 8px;
}

.tab {
  padding: 3px 12px;
  border-radius: 2px;
  border: 1px solid #8b6c42;
  background: transparent;
  color: #5c4033;
  cursor: pointer;
  font-family: inherit;
  font-weight: bold;
  font-size: 13px;
  transition: all 0.2s;
}
.tab:hover {
  background: rgba(139, 108, 66, 0.1);
}
.tab.active {
  background: #3d2b1f;
  border-color: #3d2b1f;
  color: #e8dcc5;
}

.card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(20, 20, 28, 0.65);
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 14px;
}
.title {
  font-weight: 700;
  margin-bottom: 12px;
}
.upload {
  border: 2px dashed rgba(255, 255, 255, 0.18);
  border-radius: 12px;
  padding: 18px;
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: 0.2s;
}
.upload.drag {
  border-color: rgba(255, 255, 255, 0.45);
  background: rgba(255, 255, 255, 0.04);
}
.upload.has {
  border-style: solid;
  border-color: rgba(76, 175, 80, 0.55);
}
.hidden { display: none; }
.placeholder .big { font-size: 14px; color: #ddd; }
.placeholder .sub { font-size: 12px; color: #777; margin-top: 6px; }
.file { width: 100%; position: relative; }
.file .name { font-weight: 700; color: #fff; }
.file .sub { font-size: 12px; color: #888; margin-top: 6px; }
.remove {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.2);
  background: rgba(0,0,0,0.35);
  color: #fff;
  cursor: pointer;
}
.primary {
  margin-top: 12px;
  width: 100%;
  padding: 10px 12px;
  border-radius: 10px;
  border: none;
  background: #fff;
  color: #000;
  font-weight: 800;
  cursor: pointer;
}
.primary:disabled {
  background: #333;
  color: #777;
  cursor: not-allowed;
}
.secondary {
  margin-top: 12px;
  width: 100%;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.2);
  background: transparent;
  color: #ddd;
  cursor: pointer;
}
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin: 8px 0;
}
.k { color: #888; font-size: 12px; }
.v { font-weight: 700; }
.progress {
  height: 6px;
  border-radius: 999px;
  background: rgba(255,255,255,0.08);
  overflow: hidden;
  margin: 10px 0;
}
.bar {
  height: 100%;
  background: #fff;
  width: 0%;
  transition: width 0.3s;
}
.msg { font-size: 12px; color: #aaa; margin-top: 6px; }
.logs { margin-top: 10px; display: flex; flex-direction: column; gap: 6px; }
.log { font-size: 10px; color: #666; display: flex; gap: 8px; }
.log .t { min-width: 56px; color: #777; }
.log .m { color: #aaa; }
.select {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #fff;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 13px;
  min-width: 120px;
}
.select:focus {
  outline: none;
  border-color: #646cff;
}

.empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #666;
}
.empty .big { font-size: 20px; font-weight: 800; color: #fff; }
.empty .sub { font-size: 13px; color: #888; }

.result {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.panel {
  flex: 1;
  min-height: 0;
  margin: 12px;
  border-radius: 4px;
  border: 2px solid #8b6c42;
  overflow: hidden;
  background: #e8dcb5; /* Parchment base */
  position: relative;
  box-shadow: inset 0 0 40px rgba(60, 45, 30, 0.15);
}
.panel.events {
  overflow-y: auto;
  padding: 24px;
  content-visibility: auto;
  contain-intrinsic-size: 1000px;
  /* Paper Texture */
  background-image: url("data:image/svg+xml,%3Csvg width='100' height='100' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.5' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.05'/%3E%3C/svg%3E");
}
.event {
  padding: 12px 16px;
  border: none;
  border-bottom: 1px dashed rgba(60, 45, 30, 0.3);
  border-radius: 0;
  background: transparent;
  margin-bottom: 8px;
  cursor: pointer;
  transition: background 0.2s;
}
.event:hover {
  background: rgba(60, 45, 30, 0.05);
}
.meta { display: flex; gap: 10px; color: #8b0000; font-size: 13px; font-weight: bold; font-family: "IM Fell English SC", serif; }
.place { display: flex; gap: 10px; align-items: center; margin-top: 4px; }
.loc { font-weight: 800; color: #2c1b18; font-size: 16px; font-family: "IM Fell English SC", serif; }
.tag {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 2px;
  border: 1px solid #8b6c42;
  color: #5c4033;
  font-family: sans-serif;
  text-transform: uppercase;
}
.tag.real { border-color: #2e7d32; color: #2e7d32; }
.tag.fictional { border-color: #f57f17; color: #e65100; }
.tag.uncertain { border-color: #795548; color: #795548; }
.sum { margin-top: 6px; color: #3d2b1f; line-height: 1.6; font-family: serif; font-size: 14px; }
.chars { margin-top: 6px; color: #5c4033; font-size: 12px; font-style: italic; }

/* Scroll Style for Character Selection */
.scroll-style {
  position: relative;
  margin-bottom: 24px;
  filter: drop-shadow(2px 4px 6px rgba(0,0,0,0.5));
  font-family: 'IM Fell English SC', serif;
}

.character-scroll {
  width: 100%;
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
  padding: 16px 20px;
  margin: -6px 4px; /* Pull under/over rods */
  box-shadow: inset 0 0 20px rgba(60, 45, 30, 0.1);
  position: relative;
  z-index: 1;
  color: #3d2b1f;
  display: flex;
  flex-direction: column;
  align-items: center;
  
  /* Paper Texture */
  background-image: url("data:image/svg+xml,%3Csvg width='100' height='100' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.5' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.05'/%3E%3C/svg%3E");
}

.scroll-title {
  font-weight: bold;
  font-size: 1.1em;
  margin-bottom: 12px;
  text-align: center;
  border-bottom: 2px solid rgba(60, 45, 30, 0.2);
  padding-bottom: 4px;
  width: 100%;
}

.scroll-select {
  appearance: none;
  background: rgba(255, 255, 255, 0.4);
  border: 1px solid #8b6c42;
  border-radius: 4px;
  padding: 8px 30px 8px 12px; /* Extra padding right for arrow */
  width: 100%;
  font-family: inherit;
  font-size: 1em;
  color: #2c1b18;
  cursor: pointer;
  outline: none;
  box-shadow: inset 1px 1px 4px rgba(0,0,0,0.1);
  transition: all 0.2s;
  background-image: url("data:image/svg+xml,%3Csvg width='10' height='6' viewBox='0 0 10 6' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M5 6L0 0H10L5 6Z' fill='%233d2b1f'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 10px center;
}

.scroll-select:hover {
  background-color: rgba(255, 255, 255, 0.6);
  border-color: #3d2b1f;
}

.scroll-select option {
  background: #f4e4bc;
  color: #3d2b1f;
}
</style>
