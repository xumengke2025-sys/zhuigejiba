<template>
  <div class="fortune-view">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="resetSession">衣鱼 · SILVERFISH</div>
      </div>
      <div class="header-right">
        <div class="status-badge" v-if="sessionId">
          <span class="dot" :class="status"></span>
          {{ statusText }}
        </div>
      </div>
    </header>

    <main class="content-container">
      <!-- Left: Input & Experts -->
      <div class="left-panel" v-if="status !== 'completed'">
        <div class="input-card" v-if="!sessionId">
          <h2 class="section-title">文本关系梳理</h2>
          
          <!-- 文件上传区 -->
          <div 
            class="upload-area" 
            :class="{ 'is-dragover': isDragOver, 'has-file': file }"
            @dragover.prevent="isDragOver = true"
            @dragleave.prevent="isDragOver = false"
            @drop.prevent="handleDrop"
            @click="triggerFileInput"
          >
            <input 
              type="file" 
              ref="fileInput" 
              class="hidden-input" 
              accept=".txt" 
              @change="handleFileChange" 
            />
            
            <div v-if="!file" class="upload-placeholder">
              <span class="upload-icon">📄</span>
              <p>点击或拖拽 TXT 文件到此处</p>
              <span class="sub-text">支持长篇小说、剧本、传记</span>
            </div>
            
            <div v-else class="file-info">
              <span class="file-icon">📑</span>
              <div class="file-details">
                <span class="file-name">{{ file.name }}</span>
                <span class="file-size">{{ formatSize(file.size) }}</span>
              </div>
              <button class="remove-file" @click.stop="file = null">×</button>
            </div>
          </div>

          <button class="start-btn" @click="handleAnalyze" :disabled="loading || !file">
            {{ loading ? '正在启动...' : '开始梳理人物关系' }}
          </button>
        </div>

        <!-- 运行中状态展示 -->
        <div class="analysis-running-card" v-else-if="status === 'processing' || status === 'aggregating'">
          <div class="running-header">
            <div class="running-icon">⚙️</div>
            <h3>正在分析文本</h3>
          </div>
          <div class="file-summary">
            <span class="label">当前文件:</span>
            <span class="value">{{ file?.name }}</span>
          </div>
          <div class="running-tips">
             <transition name="fade" mode="out-in">
               <p :key="currentTipIndex">{{ tips[currentTipIndex] }}</p>
             </transition>
          </div>
          <button class="cancel-btn" @click="resetSession">取消分析</button>
        </div>

        <!-- Expert Hall -->
        <div class="master-hall">
          <div class="hall-header">
            <h2 class="section-title">分析专家团</h2>
            <div class="progress-container" v-if="sessionId">
              <div class="progress-info">
                <span class="progress-percent">{{ progress }}%</span>
                <span class="progress-msg">{{ statusMsg }}</span>
              </div>
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: progress + '%' }"></div>
              </div>
              <div class="progress-logs" v-if="statusLogs.length > 0">
                <div v-for="(log, i) in statusLogs" :key="i" class="log-item" :class="{ 'first-log': i === 0 }">
                  <span class="log-time">{{ log.time }}</span>
                  <span class="log-msg">{{ log.msg }}</span>
                </div>
              </div>
            </div>
          </div>
          
          <div class="master-grid">
            <div 
              v-for="expert in experts" 
              :key="expert.id" 
              class="master-card"
              :class="{ 'is-active': true }"
            >
              <div class="master-avatar">{{ expert.name[0] }}</div>
              <div class="master-info">
                <div class="master-name">{{ expert.name }}</div>
                <div class="master-camp">{{ expert.role }}</div>
                <div class="master-desc">{{ expert.description }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Graph & Results -->
      <div class="right-panel" :class="{ 'is-fullscreen': status === 'completed' }">
        <div class="empty-state" v-if="!sessionId">
          <div class="abstract-bg"></div>
          <div class="empty-content">
            <h3>开启文本透视</h3>
            <p>上传文本，让 AI 专家团为您梳理错综复杂的人物关系网络</p>
            <div style="margin-top: 24px; display: flex; gap: 16px; justify-content: center;">
               <button class="primary-btn" @click="$refs.fileInput.click()">
                 <span class="icon">📄</span> 上传文件
               </button>
               <button class="secondary-btn" @click="runMockPreview">
                 <span class="icon">✨</span> 演示效果
               </button>
            </div>
          </div>
        </div>

        <div class="report-container" v-else :class="{ 'no-padding': status === 'completed' }">
          <!-- Loading State -->
          <div class="summary-loading ritual-ceremony" v-if="status !== 'completed'">
             <div class="ritual-bg">
              <div class="scan-line"></div>
              <div class="orbit-circles">
                <div class="orbit-1"></div>
                <div class="orbit-2"></div>
              </div>
            </div>
            <div class="ritual-content">
              <div class="ritual-spinner"></div>
              <h2 class="ritual-title">
                {{ status === 'aggregating' ? '关系聚合中' : '专家阅读中' }}
              </h2>
              <p class="ritual-msg">{{ statusMsg }}</p>
              
              <!-- Tips Carousel -->
              <div class="fortune-tip-container">
                <Transition name="fade" mode="out-in">
                  <div :key="currentTipIndex" class="fortune-tip">
                    <span class="tip-label">分析贴士:</span>
                    <span class="tip-content">{{ tips[currentTipIndex] }}</span>
                  </div>
                </Transition>
              </div>
            </div>
          </div>

          <!-- Result Graph -->
          <div class="graph-full-section" v-else>
            <div class="section-header-overlay">
              <div class="back-btn" @click="resetSession">← 重新上传</div>
              
              <div class="search-bar">
                <input 
                  type="text" 
                  v-model="searchQuery" 
                  placeholder="搜索人物..." 
                  @keyup.enter="handleSearch"
                />
                <button class="search-btn" @click="handleSearch">
                  <span class="icon">🔍</span>
                </button>
              </div>

              <div class="stats-badge">
                已识别 {{ result?.entities?.length || 0 }} 个人物，{{ result?.relationships?.length || 0 }} 条关系链
              </div>
            </div>
            <div class="graph-visual-full">
               <GraphVisualizer 
                  ref="graphVisualizerRef"
                  v-if="result"
                  :data="graphData"
                  :layoutMode="layoutMode"
                  @select-node="handleNodeSelect"
                  @node-double-click="handleNodeDoubleClick"
                  @select-edge="handleEdgeSelect"
                  @clear-selection="handleClearSelection"
                />
            </div>
            <div class="summary-panel" v-if="result?.overview">
              <div class="summary-block overview-block">
                <div class="summary-title">整体概览</div>
                <div class="summary-text">{{ overview.overview_text || '暂无概览信息' }}</div>
                <div class="summary-stats">
                  <div class="stat-item">
                    <div class="stat-label">人物</div>
                    <div class="stat-value">{{ overview.entity_count || 0 }}</div>
                  </div>
                  <div class="stat-item">
                    <div class="stat-label">关系</div>
                    <div class="stat-value">{{ overview.relationship_count || 0 }}</div>
                  </div>
                  <div class="stat-item">
                    <div class="stat-label">核心</div>
                    <div class="stat-value">{{ overview.top_entities?.length || 0 }}</div>
                  </div>
                </div>
                <div class="type-distribution">
                  <div v-for="item in relationTypeStats" :key="item.type" class="type-row">
                    <div class="type-label">
                      <span class="type-dot" :style="{ backgroundColor: item.color }"></span>
                      {{ item.label }}
                    </div>
                    <div class="type-bar">
                      <div class="type-bar-fill" :style="{ width: item.percent + '%', backgroundColor: item.color }"></div>
                    </div>
                    <div class="type-count">{{ item.count }}</div>
                  </div>
                </div>
              </div>

              <div class="summary-block" v-if="experts.length">
                <div class="summary-title">专家视角</div>
                <div class="expert-view-grid">
                  <div 
                    v-for="expert in experts" 
                    :key="expert.id" 
                    class="expert-view-card"
                    :class="{ 'is-selected': selectedExpertId === expert.id }"
                    @click="handleExpertClick(expert)"
                  >
                    <div class="expert-view-name">{{ expert.name }}</div>
                    <div class="expert-view-role">{{ expert.role }}</div>
                    <div class="expert-view-desc">{{ expert.description }}</div>
                    <div class="expert-view-action" v-if="selectedExpertId === expert.id">
                        <div class="action-btn">查看{{ expert.name }}的分析报告 ></div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Expert Sidebar -->
              <transition name="slide-right">
                <div v-if="showingExpertReport && selectedExpert" class="entity-sidebar expert-sidebar">
                  <div class="sidebar-header">
                    <div class="expert-info">
                      <div class="name">{{ selectedExpert.name }}</div>
                      <div class="role">{{ selectedExpert.role }}</div>
                    </div>
                    <div class="close-btn" @click="closeExpertReport">×</div>
                  </div>
                  <div class="sidebar-content">
                    <div class="report-section">
                      <div class="section-title">核心发现</div>
                      <div class="section-text">
                         {{ getExpertReport(selectedExpert).findings }}
                      </div>
                    </div>
                    <div class="report-section">
                       <div class="section-title">关注的关系</div>
                       <div class="related-tags">
                          <span v-for="tag in getExpertReport(selectedExpert).tags" :key="tag" class="tag" :style="{ borderColor: typeColorMap[tag] || '#888', color: typeColorMap[tag] || '#888' }">
                            {{ getRelationLabel(tag) }}
                          </span>
                       </div>
                    </div>
                  </div>
                </div>
              </transition>

              <!-- Entity Sidebar -->
              <transition name="slide-right">
                <div v-if="selectedEntityDetail" class="entity-sidebar">
                  <div class="sidebar-header" :class="'role-' + selectedEntityDetail.type">
                    <div class="expert-info">
                      <div class="name">{{ selectedEntityDetail.id }}</div>
                      <div class="role">{{ getRoleLabel(selectedEntityDetail.type) }} | 影响力指数: {{ selectedEntityDetail.degree }}</div>
                    </div>
                    <div class="close-btn" @click="selectedEntityId = null">×</div>
                  </div>
                  <div class="sidebar-content">
                    <div class="report-section">
                      <div class="section-title">人物侧写</div>
                      <div class="section-text">
                         {{ selectedEntityDetail.description }}
                      </div>
                    </div>
                    <div class="report-section">
                       <div class="section-title">核心关系网</div>
                       <div class="relation-list-mini">
                          <div v-for="rel in getEntityRelationships(selectedEntityDetail.id)" :key="rel.target" class="relation-mini-item">
                              <span class="rel-target">{{ rel.target }}</span>
                              <span class="rel-arrow">── {{ rel.relation }} ──></span> 
                              <span class="rel-type" :style="{ color: typeColorMap[rel.type] }">{{ getRelationLabel(rel.type) }}</span>
                          </div>
                          <div v-if="getEntityRelationships(selectedEntityDetail.id).length === 0" class="no-data">暂无核心关系记录</div>
                       </div>
                    </div>
                  </div>
                </div>
              </transition>

              <transition name="slide-right">
                <div v-if="selectedRelationDetail" class="entity-sidebar relation-sidebar">
                  <div class="sidebar-header">
                    <div class="expert-info">
                      <div class="name">{{ selectedRelationDetail.relation }}</div>
                      <div class="role">{{ getRelationLabel(selectedRelationDetail.type) }} | 强度 {{ selectedRelationDetail.weight || 1 }}</div>
                    </div>
                    <div class="close-btn" @click="selectedRelation = null">×</div>
                  </div>
                  <div class="sidebar-content">
                    <div class="report-section">
                      <div class="section-title">关系双方</div>
                      <div class="relation-actors-block">
                        <button class="entity-link" @click="openEntityFromRelation(selectedRelationDetail.source)">
                          {{ selectedRelationDetail.source }}
                        </button>
                        <span class="relation-arrow">—</span>
                        <button class="entity-link" @click="openEntityFromRelation(selectedRelationDetail.target)">
                          {{ selectedRelationDetail.target }}
                        </button>
                      </div>
                    </div>
                    <div class="report-section">
                      <div class="section-title">关系标签</div>
                      <div class="relation-tag" :style="{ borderColor: typeColorMap[selectedRelationDetail.type] || '#607D8B', color: typeColorMap[selectedRelationDetail.type] || '#607D8B' }">
                        {{ getRelationLabel(selectedRelationDetail.type) }}
                      </div>
                    </div>
                    <div class="report-section" v-if="selectedRelationDetail.evidence">
                      <div class="section-title">证据</div>
                      <div class="section-text">“{{ selectedRelationDetail.evidence }}”</div>
                    </div>
                  </div>
                </div>
              </transition>

              <div class="summary-block">
                <div class="summary-title">核心人物</div>
                <div class="entity-grid">
                  <div 
                    v-for="e in topEntities" 
                    :key="e.id" 
                    class="entity-card" 
                    :class="[
                      `role-${e.type || 'neutral'}`,
                      { 
                        'is-selected': selectedEntityId === e.id,
                        'is-dimmed': selectedEntityId && selectedEntityId !== e.id
                      }
                    ]"
                    :id="`entity-${e.id}`"
                    @click="handleEntityClick(e)"
                  >
                    <div class="entity-name">{{ e.id }}</div>
                    <div class="entity-role">{{ roleLabels[e.type] || '人物' }}</div>
                    <div class="entity-degree">关联度 {{ e.degree }}</div>
                    <div class="entity-desc" v-if="e.description">{{ e.description }}</div>
                  </div>
                </div>
              </div>

              <div class="summary-block">
                <div class="summary-title">关键关系</div>
                <div class="relation-list">
                  <div 
                    v-for="(r, i) in filteredKeyRelationships" 
                    :key="i" 
                    class="relation-item"
                    :class="{ 'is-highlighted': isRelationRelevant(r) }"
                  >
                    <div class="relation-header">
                      <div class="relation-badge" :style="{ backgroundColor: typeColorMap[r.type] || '#607D8B' }">
                        {{ r.relation || r.type || '关系' }}
                      </div>
                      <div class="relation-actors">
                        <span :class="{ 'highlight-text': selectedEntityId === r.source }">{{ r.source }}</span>
                        — 
                        <span :class="{ 'highlight-text': selectedEntityId === r.target }">{{ r.target }}</span>
                      </div>
                      <div class="relation-weight">强度 {{ r.weight || 1 }}</div>
                    </div>
                    <div class="relation-evidence" v-if="r.evidence">“{{ r.evidence }}”</div>
                  </div>
                  <div v-if="keyRelationships.length > filteredKeyRelationships.length" class="more-hint">
                    ... 还有 {{ keyRelationships.length - filteredKeyRelationships.length }} 条其他关系 (点击空白处查看全部)
                  </div>
                </div>
              </div>

              <div class="summary-block" v-if="readerQuestions.length || readerTakeaways.length">
                <div class="summary-title">读者视角</div>
                <div class="reader-section" v-if="readerQuestions.length">
                  <div class="reader-subtitle">你可能最关心</div>
                  <div class="reader-list">
                    <div v-for="(q, i) in readerQuestions" :key="`rq-${i}`" class="reader-item">
                      {{ q }}
                    </div>
                  </div>
                </div>
                <div class="reader-section" v-if="readerTakeaways.length">
                  <div class="reader-subtitle">当前可回答</div>
                  <div class="reader-list">
                    <div v-for="(t, i) in readerTakeaways" :key="`rt-${i}`" class="reader-item">
                      {{ t }}
                    </div>
                  </div>
                </div>
              </div>

              <div class="summary-block" v-if="storylineLines.length">
                <div class="summary-title">剧情主线</div>
                <div class="storyline-list">
                  <div 
                    v-for="(line, i) in storylineLines" 
                    :key="i" 
                    class="storyline-item"
                    :class="{ 'is-dimmed': selectedEntityId && !line.includes(selectedEntityId) }"
                  >
                    {{ line }}
                  </div>
                </div>
              </div>

              <div class="summary-block" v-if="protagonistConnections.length">
                <div class="summary-title">主角关系圈</div>
                <div class="relation-list">
                  <div 
                    v-for="(c, i) in filteredProtagonistConnections" 
                    :key="i" 
                    class="relation-item"
                  >
                    <div class="relation-header">
                      <div class="relation-badge" :style="{ backgroundColor: typeColorMap[c.type] || '#607D8B' }">
                        {{ c.relation || '关系' }}
                      </div>
                      <div class="relation-actors">{{ overview.protagonists?.[0] || '核心人物' }} — {{ c.target }}</div>
                      <div class="relation-weight">强度 {{ c.weight || 1 }}</div>
                    </div>
                    <div class="relation-evidence" v-if="c.evidence">“{{ c.evidence }}”</div>
                  </div>
                </div>
              </div>

              <div class="summary-block" v-if="clusters.length">
                <div class="summary-title">关系簇</div>
                <div class="cluster-list">
                  <div 
                    v-for="(g, i) in clusters" 
                    :key="i" 
                    class="cluster-item"
                    :class="{ 'is-selected': selectedEntityId && (g.members || []).includes(selectedEntityId) }"
                  >
                    <div class="cluster-header">
                      <div class="relation-badge" :style="{ backgroundColor: typeColorMap[g.dominant_type] || '#607D8B' }">
                        {{ g.dominant_label }}
                      </div>
                      <div class="cluster-size">规模 {{ g.size }}</div>
                    </div>
                    <div class="cluster-members">
                      <span 
                        v-for="(m, mi) in (g.members || [])" 
                        :key="mi" 
                        :class="{ 'highlight-text': m === selectedEntityId }"
                      >
                        {{ m }}{{ mi < (g.members || []).length - 1 ? '、' : '' }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { analyzeFate, getStatus } from '../api/fortune'
import toast from '../utils/toast'
import GraphVisualizer from '../components/GraphVisualizer.vue'

const router = useRouter()
const graphVisualizerRef = ref(null)
const searchQuery = ref('')

// Upload State
const file = ref(null)
const fileInput = ref(null)
const isDragOver = ref(false)

// Analysis State
const loading = ref(false)
const sessionId = ref(null)
const status = ref('idle')
const statusMsg = ref('')
const progress = ref(0)
const statusLogs = ref([])
const experts = ref([])
const result = ref(null)
const pollTimer = ref(null)

// Selection State
const selectedEntityId = ref(null)
const selectedRelation = ref(null)
const layoutMode = ref('force')

// Tips
const currentTipIndex = ref(0)
const tips = [
  "关系考古学家正在挖掘隐藏的血缘线索...",
  "情感心理学家正在分析人物间微妙的情绪流动...",
  "权力分析师正在解构组织架构与利益同盟...",
  "叙事结构师正在辨识主线与支线的关系脉络...",
  "动机剖析师正在追踪人物行为的关键转折..."
]
let tipTimer = null

const defaultExperts = [
  { id: "genealogist", name: "关系考古学家", role: "Genealogist", description: "挖掘血缘与家族谱系" },
  { id: "psychologist", name: "情感心理学家", role: "Psychologist", description: "分析情感纠葛与心理距离" },
  { id: "strategist", name: "权力分析师", role: "Strategist", description: "解析利益同盟与权力结构" },
  { id: "structuralist", name: "叙事结构师", role: "Structuralist", description: "识别主线与支线的结构关系" },
  { id: "motivator", name: "动机剖析师", role: "Motivation Analyst", description: "追踪人物行为背后的动机与转变" }
]

const roleLabels = {
  protagonist: '主角',
  antagonist: '反派',
  supporting: '配角',
  neutral: '中立'
}

const typeColorMap = {
  family: '#00C853',
  social: '#2979FF',
  romance: '#FF4081',
  conflict: '#FF3D00',
  work: '#FFAB00',
  other: '#607D8B'
}

// Computed
const graphData = computed(() => {
  if (!result.value) return { nodes: [], edges: [] }
  const raw = result.value
  const graphData = raw.graph_data || raw.graphData || raw.graph
  const entities = Array.isArray(graphData?.nodes)
    ? graphData.nodes
    : (Array.isArray(raw.entities) ? raw.entities : (Array.isArray(raw.nodes) ? raw.nodes : []))
  const relationships = Array.isArray(graphData?.edges)
    ? graphData.edges
    : (Array.isArray(raw.relationships)
      ? raw.relationships
      : (Array.isArray(raw.edges) ? raw.edges : (Array.isArray(raw.links) ? raw.links : [])))
  return {
    nodes: entities.map(e => {
      const properties = e.properties || {}
      const name = e.name || properties.name
      const id = e.id || e.name || properties.name
      if (!id) return null
      return {
        id,
        label: name || id,
        type: e.type || properties.type,
        degree: e.degree || properties.impact,
        description: e.description || properties.description,
        ...e
      }
    }).filter(Boolean),
    links: relationships.map(r => {
      const source = r.source?.id || r.source?.name || r.source
      const target = r.target?.id || r.target?.name || r.target
      if (!source || !target) return null
      return {
        source,
        target,
        label: r.relation || r.label,
        ...r
      }
    }).filter(Boolean)
  }
})

const overview = computed(() => result.value?.overview || result.value?.summary || {})

const topEntities = computed(() => overview.value.top_entities || [])

const keyRelationships = computed(() => overview.value.key_relationships || [])

const storylineLines = computed(() => overview.value.storyline_lines || [])

const readerQuestions = computed(() => overview.value.reader_questions || [])

const readerTakeaways = computed(() => overview.value.reader_takeaways || [])

const protagonistConnections = computed(() => overview.value.protagonist_connections || [])

const clusters = computed(() => overview.value.clusters || [])

// Filtered Lists based on Selection
const filteredKeyRelationships = computed(() => {
  const all = keyRelationships.value
  if (selectedEntityId.value) {
    // Show relationships involving the selected entity
    // And prioritize them
    return all.filter(r => r.source === selectedEntityId.value || r.target === selectedEntityId.value)
  }
  return all
})

const filteredProtagonistConnections = computed(() => {
  const all = protagonistConnections.value
  if (selectedEntityId.value) {
    // If selected entity is protagonist, show all?
    // If selected entity is someone else, show connection to protagonist
    return all.filter(c => c.target === selectedEntityId.value)
  }
  return all
})

const getRelationNodeId = (node) => node?.id || node?.name || node

const selectedRelationDetail = computed(() => {
    if (!selectedRelation.value) return null
    const link = selectedRelation.value
    const source = getRelationNodeId(link.source)
    const target = getRelationNodeId(link.target)
    if (!source || !target) return null
    return {
        source,
        target,
        relation: link.relation || link.label || link.type || '关系',
        type: link.type || 'other',
        weight: link.weight || 1,
        evidence: link.evidence || ''
    }
})

const isRelationRelevant = (r) => {
    if (!selectedRelationDetail.value) return false
    const { source, target } = selectedRelationDetail.value
    return (r.source === source && r.target === target) || (r.source === target && r.target === source)
}

// Expert Interaction
const selectedExpertId = ref(null)
const showingExpertReport = ref(false)
const selectedExpert = computed(() => experts.value.find(e => e.id === selectedExpertId.value))

const handleExpertClick = (expert) => {
    selectedEntityId.value = null // Close entity sidebar
    selectedExpertId.value = expert.id
    showingExpertReport.value = true
}

const closeExpertReport = () => {
    showingExpertReport.value = false
    selectedExpertId.value = null
}

const getRelationLabel = (type) => {
    const map = {
      family: '亲属',
      social: '社交',
      romance: '情感',
      conflict: '冲突',
      work: '工作',
      other: '其他'
    }
    return map[type] || type
}

const getExpertReport = (expert) => {
    // Mock report data based on expert type
    const base = {
        genealogist: {
            findings: "家族谱系中存在隐藏的血缘纽带，建议关注父辈之间的未解之谜。",
            tags: ['family']
        },
        psychologist: {
            findings: "人物间的情感流动极其复杂，爱恨交织是推动剧情的核心动力。",
            tags: ['romance', 'social']
        },
        strategist: {
            findings: "各方势力在资源与权力上的博弈处于胶着状态，关键人物的站队将决定局势走向。",
            tags: ['work', 'conflict']
        },
        narrator: {
            findings: "关键事件的时间线存在多处重叠，暗示了背后可能存在平行叙事或不可靠叙述者。",
            tags: ['work', 'social', 'family']
        },
        conflict: { // mediator
             findings: "冲突的主要根源在于核心利益的不可调和，短期内难以通过对话解决。",
             tags: ['conflict']
        }
    }
    
    // Default fallback
    const def = {
        findings: `${expert.name} 正在深入分析相关领域的隐藏线索，目前已识别出多处关键节点。`,
        tags: ['other']
    }
    
    // Map expert id to key
    let key = expert.id
    if (key === 'mediator') key = 'conflict'
    
    return base[key] || def
}

// Entity Interaction
const selectedEntityDetail = computed(() => {
    if (!selectedEntityId.value || !result.value) return null
    return result.value.entities.find(e => e.id === selectedEntityId.value)
})

const getRoleLabel = (type) => {
    return roleLabels[type] || type
}

const getEntityRelationships = (id) => {
    if (!result.value) return []
    // Get top 5 relationships where this entity is source or target
    return result.value.relationships
        .filter(r => r.source === id || r.target === id)
        .map(r => ({
            target: r.source === id ? r.target : r.source,
            relation: r.relation,
            type: r.type,
            weight: r.weight
        }))
        .sort((a, b) => b.weight - a.weight)
}

// Interaction Handlers
const scrollToEntity = (id) => {
    setTimeout(() => {
        const el = document.getElementById(`entity-${id}`)
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 100)
}

const handleNodeSelect = (node) => {
    if (node) {
        showingExpertReport.value = false // Close expert sidebar
        selectedEntityId.value = node.id
        selectedRelation.value = null
        scrollToEntity(node.id)
    } else {
        selectedEntityId.value = null
    }
}

const handleNodeDoubleClick = (node) => {
    if (node) {
        showingExpertReport.value = false // Close expert sidebar
        selectedEntityId.value = node.id
    }
}

const handleEdgeSelect = (edge) => {
    showingExpertReport.value = false
    selectedRelation.value = edge
    selectedEntityId.value = null
}

const handleClearSelection = () => {
    selectedEntityId.value = null
    selectedRelation.value = null
    showingExpertReport.value = false // Close expert sidebar
}

const openEntityFromRelation = (id) => {
    if (!id) return
    showingExpertReport.value = false
    selectedRelation.value = null
    selectedEntityId.value = id
    scrollToEntity(id)
}

const handleEntityClick = (e) => {
    // If we want bidirectional, we need to tell GraphVisualizer to select this node
    // But GraphVisualizer doesn't expose a method easily. 
    // For now, just set local state. 
    // Ideally, we'd pass 'selectedNodeId' prop to GraphVisualizer
    showingExpertReport.value = false // Close expert sidebar
    selectedEntityId.value = e.id
}

const relationTypeStats = computed(() => {
  const counts = overview.value.relation_type_counts || {}
  const total = Object.values(counts).reduce((sum, c) => sum + c, 0) || 1
  const entries = Object.entries(counts).map(([type, count]) => ({
    type,
    label: {
      family: '亲属',
      social: '社交',
      romance: '情感',
      conflict: '冲突',
      work: '工作',
      other: '其他'
    }[type] || type,
    color: typeColorMap[type] || '#607D8B',
    count,
    percent: Math.round((count / total) * 100)
  }))
  return entries.sort((a, b) => b.count - a.count)
})

const statusText = computed(() => {
  const map = {
    idle: '待机',
    processing: '阅读分析中',
    aggregating: '图谱构建中',
    completed: '梳理完成',
    failed: '分析异常'
  }
  return map[status.value] || status.value
})

// File Methods
const triggerFileInput = () => fileInput.value.click()

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
  if (f.size > 20 * 1024 * 1024) { // 限制 20MB
    toast.error('文件过大', '目前仅支持 20MB 以内的文本文件')
    return
  }
  file.value = f
}

const formatSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

// Watch for selection to update graph?
// Ideally GraphVisualizer should take a prop 'selectedId'
// Let's rely on the user clicking the graph for now, 
// OR implemented bidirectional if we have time. 
// For now, Graph -> UI is the main request.

// Search Method
const handleSearch = () => {
  if (!searchQuery.value.trim() || !result.value) return
  
  const query = searchQuery.value.trim().toLowerCase()
  const entities = result.value.entities || []
  
  // Find best match
  const match = entities.find(e => {
    const name = (e.id || e.name || '').toLowerCase()
    return name === query
  }) || entities.find(e => {
    const name = (e.id || e.name || '').toLowerCase()
    return name.includes(query)
  })
  
  if (match) {
    if (graphVisualizerRef.value) {
      graphVisualizerRef.value.focusNode(match.id)
      toast.success(`已定位: ${match.id}`)
      searchQuery.value = '' // Clear search after successful find
    }
  } else {
    toast.error('未找到相关人物')
  }
}

// Analysis Methods
const handleAnalyze = async () => {
  loading.value = true
  result.value = null
  progress.value = 0
  statusLogs.value = []
  
  const closeLoading = toast.loading('正在上传并启动分析...')
  
  try {
    const formData = new FormData()
    formData.append('file', file.value)
    
    const res = await analyzeFate(formData)
    if (res.success) {
      sessionId.value = res.session_id
      status.value = 'processing'
      startPolling()
      startTipRotation()
    }
  } catch (err) {
    console.error('Analysis start failed:', err)
    toast.error('启动失败', err.response?.data?.error || err.message)
  } finally {
    loading.value = false
    closeLoading()
  }
}

const startPolling = () => {
  if (pollTimer.value) clearInterval(pollTimer.value)
  pollTimer.value = setInterval(async () => {
    try {
      const res = await getStatus(sessionId.value)
      if (res.success) {
        status.value = res.status
        progress.value = res.progress
        
        if (res.message && res.message !== statusMsg.value) {
          statusMsg.value = res.message
          statusLogs.value.unshift({
            time: new Date().toLocaleTimeString(),
            msg: res.message
          })
        }
        
        if (res.status === 'completed') {
          result.value = res.data
          clearInterval(pollTimer.value)
          stopTipRotation()
        } else if (res.status === 'failed') {
          clearInterval(pollTimer.value)
          stopTipRotation()
          toast.error('分析失败', res.error)
        }
      }
    } catch (err) {
      console.error(err)
    }
  }, 2000)
}

const startTipRotation = () => {
  if (tipTimer) clearInterval(tipTimer)
  tipTimer = setInterval(() => {
    currentTipIndex.value = (currentTipIndex.value + 1) % tips.length
  }, 4000)
}

const stopTipRotation = () => {
  if (tipTimer) clearInterval(tipTimer)
}

const resetSession = () => {
  sessionId.value = null
  status.value = 'idle'
  result.value = null
  file.value = null
  progress.value = 0
  statusLogs.value = []
  experts.value = defaultExperts
}

const runMockPreview = () => {
  loading.value = true
  status.value = 'reading'
  result.value = null // 先清空旧数据触发重载
  statusMsg.value = '正在加载演示数据...'
  sessionId.value = 'mock-session-001'
  
  // Simulate loading process
  let p = 0
  const timer = setInterval(() => {
    p += 5
    progress.value = p
    if (p < 30) status.value = 'reading'
    else if (p < 70) status.value = 'analyzing'
    else status.value = 'aggregating'
    
    if (p >= 100) {
      clearInterval(timer)
      status.value = 'completed'
      loading.value = false
      
      // Mock Data
      const entities = [
          { id: '叶文洁', type: 'protagonist', degree: 96, description: '红岸基地工程师，向宇宙发出第一次回应的人' },
          { id: '汪淼', type: 'protagonist', degree: 92, description: '纳米材料专家，被卷入三体危机的科学家' },
          { id: '史强', type: 'supporting', degree: 85, description: '刑警大史，直觉敏锐，汪淼的关键伙伴' },
          { id: '申玉菲', type: 'antagonist', degree: 78, description: 'ETO成员，冷静而隐秘的组织骨干' },
          { id: '迈克·伊文斯', type: 'antagonist', degree: 88, description: 'ETO领袖之一，与三体文明建立联系' },
          { id: '杨卫宁', type: 'supporting', degree: 74, description: '红岸基地指挥官，叶文洁的重要同伴' },
          { id: '杨冬', type: 'supporting', degree: 70, description: '叶文洁之女，科学界的核心人物' },
          { id: '丁仪', type: 'supporting', degree: 76, description: '物理学家，推动汪淼理解科学异象' },
          { id: '雷志成', type: 'antagonist', degree: 72, description: '文革时期的施压者，影响叶文洁命运' },
          { id: '魏成', type: 'neutral', degree: 62, description: '数学家，沉迷于神秘的数列规律' },
          { id: '红岸基地', type: 'neutral', degree: 68, description: '深空发射基地，叶文洁工作的关键场所' },
          { id: '三体人', type: 'antagonist', degree: 98, description: '三体文明的信号回应者' }
      ];

      const relationships = [
          { source: '叶文洁', target: '三体人', relation: '通信', type: 'conflict', weight: 10, evidence: '红岸基地向宇宙发送信息并收到回应' },
          { source: '汪淼', target: '史强', relation: '搭档', type: 'work', weight: 9, evidence: '共同追查科学家离奇事件' },
          { source: '汪淼', target: '申玉菲', relation: '被引导', type: 'social', weight: 8, evidence: '被带入三体游戏与ETO线索' },
          { source: '申玉菲', target: '迈克·伊文斯', relation: '同盟', type: 'work', weight: 7, evidence: '共同推动ETO行动' },
          { source: '叶文洁', target: '杨卫宁', relation: '伴侣', type: 'romance', weight: 6, evidence: '红岸时期共同生活' },
          { source: '叶文洁', target: '杨冬', relation: '母女', type: 'family', weight: 9, evidence: '亲生关系影响人物选择' },
          { source: '叶文洁', target: '雷志成', relation: '迫害', type: 'conflict', weight: 8, evidence: '文革时期的打击与利用' },
          { source: '汪淼', target: '丁仪', relation: '好友', type: 'social', weight: 7, evidence: '共同探讨科学异象与物理困境' },
          { source: '汪淼', target: '迈克·伊文斯', relation: '对峙', type: 'conflict', weight: 8, evidence: '古筝行动暴露ETO核心' },
          { source: '叶文洁', target: '红岸基地', relation: '任职', type: 'work', weight: 6, evidence: '负责深空通讯项目' },
          { source: '魏成', target: '汪淼', relation: '启发', type: 'social', weight: 5, evidence: '数列与宇宙规律的讨论' }
      ];

      // Procedurally generate more nodes (Soldiers, Civilians, ETO Members)
      const factions = ['ETO', 'PDC', 'Fleet', 'Civilian'];
      for (let i = 0; i < 50; i++) {
          const id = `Unit-${100 + i}`;
          const faction = factions[Math.floor(Math.random() * factions.length)];
          const type = faction === 'ETO' ? 'antagonist' : (faction === 'Civilian' ? 'neutral' : 'supporting');
          
          entities.push({
              id,
              type,
              degree: Math.floor(Math.random() * 20 + 10),
              description: `Generated ${faction} member unit.`
          });

          // Connect to existing main characters
          const target = entities[Math.floor(Math.random() * 12)]; // Connect to main 12
          relationships.push({
              source: id,
              target: target.id,
              relation: '隶属',
              type: 'work',
              weight: Math.floor(Math.random() * 5 + 1),
              evidence: 'Automated connection'
          });
          
          // Connect to another random node to create clusters
          if (Math.random() > 0.5 && i > 0) {
               const target2 = entities[12 + Math.floor(Math.random() * i)];
               relationships.push({
                  source: id,
                  target: target2.id,
                  relation: '同僚',
                  type: 'social',
                  weight: 3,
                  evidence: 'Automated connection'
               });
          }
      }

      result.value = {
        entities,
        relationships,
        overview: {
          overview_text: '《三体》第一部聚焦叶文洁的抉择与汪淼的追寻，红岸基地的信号引来宇宙回音，ETO与科学危机交织出人类文明的命运拐点。',
          entity_count: entities.length,
          relationship_count: relationships.length,
          top_entities: [
            { id: '叶文洁', type: 'protagonist', degree: 96 },
            { id: '汪淼', type: 'protagonist', degree: 92 },
            { id: '迈克·伊文斯', type: 'antagonist', degree: 88 }
          ],
          relation_type_counts: {
            conflict: 4,
            romance: 1,
            work: 3,
            social: 3,
            family: 1
          },
          reader_questions: [
             '叶文洁为何选择向宇宙发出回应？',
             '三体游戏的目的究竟是什么？',
             'ETO内部的分裂将如何影响人类？'
          ],
          reader_takeaways: [
             '文明交流的代价',
             '科学信念的崩塌与重建',
             '人与文明的选择'
          ],
          storyline_lines: [
             '文革创伤 -> 叶文洁进入红岸基地',
             '红岸信号发送 -> 三体回应',
             '三体游戏引导汪淼 -> 科学家离奇事件',
             '古筝行动 -> ETO暴露',
             '叶文洁坦白 -> 人类迎来危机'
          ],
          protagonist_connections: [
             { target: '史强', relation: '搭档', type: 'work', weight: 9 },
             { target: '申玉菲', relation: '线索', type: 'social', weight: 8 },
             { target: '丁仪', relation: '好友', type: 'social', weight: 7 }
          ],
          protagonists: ['汪淼', '叶文洁']
        }
      }
      
      experts.value = defaultExperts.map(e => ({
         ...e,
         description: `${e.name} 已完成分析，生成了 3 条洞察。`
      }))
    }
  }, 100)
}

onMounted(async () => {
  experts.value = defaultExperts
})

onUnmounted(() => {
  if (pollTimer.value) clearInterval(pollTimer.value)
  if (tipTimer) clearInterval(tipTimer)
})
</script>

<style scoped>
.fortune-view {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #000; /* Fallback */
  color: #E0E0E0;
  font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  overflow: hidden;
  position: relative;
}

.app-header {
  height: 64px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(13, 13, 15, 0.75);
  backdrop-filter: blur(12px);
  z-index: 10;
}

.brand {
  font-family: 'Consolas', 'Monaco', monospace;
  font-weight: 800;
  font-size: 20px;
  letter-spacing: 2px;
  color: #FFF;
  cursor: pointer;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  background: #1A1A1D;
  padding: 6px 12px;
  border-radius: 20px;
  border: 1px solid #2A2A2F;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #444;
}
.dot.processing { background: #FF9800; animation: pulse 1s infinite; }
.dot.completed { background: #4CAF50; }

@keyframes pulse { 50% { opacity: 0.4; } }

.content-container {
  flex: 1;
  display: flex;
  overflow: hidden;
  height: calc(100vh - 64px);
}

/* Left Panel */
.left-panel {
  width: 400px;
  min-width: 400px;
  border-right: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  background: rgba(13, 13, 15, 0.65);
  backdrop-filter: blur(12px);
  z-index: 5;
}

.input-card {
  background: rgba(20, 20, 22, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
}

.analysis-running-card {
  background: rgba(20, 20, 22, 0.6);
  border: 1px solid #3b82f6;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  animation: pulse-border 2s infinite;
  backdrop-filter: blur(5px);
}

@keyframes pulse-border {
  0% { border-color: #3b82f644; }
  50% { border-color: #3b82f6ff; }
  100% { border-color: #3b82f644; }
}

.running-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.running-icon {
  font-size: 24px;
  animation: spin 4s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.file-summary {
  font-size: 14px;
  color: #8E8E93;
  margin-bottom: 12px;
}

.file-summary .value {
  color: #FFFFFF;
  margin-left: 8px;
}

.running-tips {
  min-height: 48px;
  font-size: 14px;
  color: #3b82f6;
  font-style: italic;
  margin-bottom: 16px;
}

/* Interaction Styles */
.entity-card.is-selected {
  border-color: #FFF;
  background: #2A2A2F;
  box-shadow: 0 0 15px rgba(255, 255, 255, 0.1);
  transform: scale(1.02);
}

.entity-card.is-dimmed {
  opacity: 0.3;
  filter: grayscale(0.5);
}

.storyline-item.is-dimmed {
  opacity: 0.3;
}

.cluster-item.is-selected {
  border-color: #FFF;
  background: #2A2A2F;
}

.highlight-text {
  color: #FFF;
  font-weight: bold;
  text-decoration: underline;
  text-decoration-color: #FFD700;
}

.relation-item.is-highlighted {
  border-color: #FFD700;
  background: #2A2A10;
}

.more-hint {
  text-align: center;
  font-size: 12px;
  color: #666;
  padding: 8px;
  font-style: italic;
}

.cancel-btn {
  width: 100%;
  padding: 8px;
  background: transparent;
  border: 1px solid #3A3A3C;
  color: #8E8E93;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.cancel-btn:hover {
  border-color: #FF453A;
  color: #FF453A;
}

.section-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 20px;
  color: #FFF;
  text-transform: uppercase;
  letter-spacing: 1px;
}

/* Upload Area */
.upload-area {
  border: 2px dashed rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  padding: 32px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: rgba(255, 255, 255, 0.02);
  min-height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-area:hover, .upload-area.is-dragover {
  border-color: rgba(255, 255, 255, 0.5);
  background: rgba(255, 255, 255, 0.05);
  box-shadow: 0 0 15px rgba(255, 255, 255, 0.1);
}

.upload-area.has-file {
  border-style: solid;
  border-color: #4CAF50;
  background: rgba(76, 175, 80, 0.05);
}

.hidden-input { display: none; }

.upload-icon { font-size: 32px; margin-bottom: 12px; display: block; }
.upload-placeholder p { font-size: 14px; color: #DDD; margin-bottom: 4px; }
.sub-text { font-size: 12px; color: #666; }

.file-info {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.file-icon { font-size: 24px; }
.file-details { flex: 1; text-align: left; overflow: hidden; }
.file-name { display: block; font-size: 14px; color: #FFF; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.file-size { font-size: 12px; color: #888; }

.remove-file {
  background: none;
  border: none;
  color: #666;
  font-size: 20px;
  cursor: pointer;
  padding: 4px;
}

.remove-file:hover { color: #FF5252; }

.start-btn {
  width: 100%;
  margin-top: 24px;
  padding: 14px;
  background: #FFF;
  color: #000;
  border: none;
  border-radius: 8px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s;
}

.start-btn:disabled {
  background: #333;
  color: #666;
  cursor: not-allowed;
}

/* Master Hall */
.master-hall {
  padding: 24px;
  flex: 1;
  overflow-y: auto;
}

.progress-container {
  margin-top: 16px;
  background: rgba(20, 20, 22, 0.6);
  padding: 16px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.progress-percent { font-family: 'Consolas', 'Monaco', monospace; font-weight: 800; color: #FFF; text-shadow: 0 0 10px rgba(255, 255, 255, 0.5); }
.progress-msg { font-size: 12px; color: #BBB; }

.progress-bar {
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #FFF;
  box-shadow: 0 0 10px #FFF;
  transition: width 0.3s;
}

.progress-logs {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.log-item {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 10px;
  color: #666;
  display: flex;
  gap: 8px;
}

.first-log { color: #BBB; text-shadow: 0 0 5px rgba(255, 255, 255, 0.3); }
.log-time { color: #888; min-width: 50px; }

.master-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
  margin-top: 20px;
}

.master-card {
  background: rgba(20, 20, 23, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.05);
  padding: 12px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 12px;
  transition: all 0.3s;
}

.master-card:hover {
  background: rgba(30, 30, 35, 0.7);
  border-color: rgba(255, 255, 255, 0.2);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.master-avatar {
  width: 36px;
  height: 36px;
  background: #2A2A2F;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #FFF;
  font-weight: 700;
}

.master-name { font-size: 14px; font-weight: 600; color: #DDD; }
.master-camp { font-size: 12px; color: #666; }
.master-desc { font-size: 12px; color: #888; margin-top: 4px; line-height: 1.4; }

/* Right Panel */
.right-panel {
  flex: 1;
  height: 100%;
  background: transparent;
  position: relative;
  display: flex;
  flex-direction: column;
  transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1;
}

.right-panel.is-fullscreen {
  flex: none;
  width: 100vw;
  height: calc(100vh - 64px);
}

.empty-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.empty-content h3 { font-size: 24px; color: #FFF; margin-bottom: 12px; }
.empty-content p { color: #666; }

.primary-btn, .secondary-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: 8px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.primary-btn {
  background: #FFF;
  color: #000;
  box-shadow: 0 0 15px rgba(255, 255, 255, 0.2);
}

.primary-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 0 25px rgba(255, 255, 255, 0.4);
}

.secondary-btn {
  background: rgba(255, 255, 255, 0.1);
  color: #FFF;
  backdrop-filter: blur(4px);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.secondary-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.3);
}

.report-container {
  height: 100%;
  padding: 24px;
  overflow: hidden;
  transition: padding 0.5s;
  min-height: 0;
}

.report-container.no-padding {
  padding: 0;
}

.graph-full-section {
  height: 100%;
  display: flex;
  flex-direction: column;
  position: relative;
  min-height: 0;
}

.section-header-overlay {
  position: absolute;
  top: 20px;
  left: 20px;
  right: 20px;
  z-index: 50;
  display: flex;
  justify-content: space-between;
  align-items: center;
  pointer-events: none;
}

.back-btn {
  pointer-events: auto;
  cursor: pointer;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  padding: 8px 16px;
  border-radius: 20px;
  border: 1px solid #333;
  color: #FFF;
  font-size: 14px;
  transition: all 0.2s;
}

.back-btn:hover {
  background: #333;
  border-color: #666;
}

.stats-badge {
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  padding: 8px 16px;
  border-radius: 20px;
  border: 1px solid #333;
  color: #888;
  font-size: 12px;
}

.mode-btn {
  pointer-events: auto;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid #333;
  color: #888;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.mode-btn:hover {
  background: #333;
  color: #DDD;
}

.mode-btn.icon-only {
  padding: 6px 8px;
  font-size: 14px;
}

.mode-btn.active {
  background: #FFD700;
  color: #000;
  border-color: #FFD700;
  font-weight: bold;
}

.graph-visual-full {
  flex: 1;
  height: 100%;
  min-height: 500px;
  background: transparent;
  border-radius: 12px;
  border: 1px solid #1F1F22;
  overflow: hidden;
  position: relative;
  z-index: 20;
}

.report-container.no-padding .graph-visual-full {
  border-radius: 0;
  border: none;
}

.summary-panel {
  margin-top: 16px;
  display: grid;
  grid-template-columns: 1.2fr 1fr 1fr;
  gap: 16px;
  padding: 16px;
  background: linear-gradient(135deg, rgba(18, 18, 22, 0.95), rgba(10, 10, 12, 0.95));
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(6px);
  max-height: 40vh;
  overflow: auto;
}

.summary-block {
  background: linear-gradient(180deg, rgba(24, 24, 28, 0.9), rgba(16, 16, 20, 0.9));
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.02), 0 8px 24px rgba(0, 0, 0, 0.25);
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.summary-block:hover {
  transform: translateY(-1px);
  border-color: rgba(255, 255, 255, 0.12);
}

.summary-title {
  font-size: 14px;
  font-weight: 700;
  color: #FFF;
  letter-spacing: 1px;
}

.summary-text {
  color: #B8B8C0;
  line-height: 1.7;
  font-size: 14px;
}

.summary-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.stat-item {
  background: rgba(10, 10, 14, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 10px 12px;
}

.stat-label {
  font-size: 11px;
  color: #8E8E93;
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: #FFF;
}

.type-distribution {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.type-row {
  display: grid;
  grid-template-columns: 80px 1fr 32px;
  gap: 8px;
  align-items: center;
}

.type-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #C7C7D1;
}

.type-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.type-bar {
  background: rgba(8, 8, 12, 0.9);
  border-radius: 999px;
  height: 8px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.type-bar-fill {
  height: 100%;
  border-radius: 999px;
}

.type-count {
  font-size: 11px;
  color: #8E8E93;
  text-align: right;
}

.entity-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.entity-card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 10px 12px;
  background: rgba(10, 10, 14, 0.9);
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.entity-card.role-protagonist { border-color: #FFD70055; box-shadow: 0 0 12px #FFD70022; }
.entity-card.role-antagonist { border-color: #F5005755; box-shadow: 0 0 12px #F5005722; }
.entity-card.role-supporting { border-color: #00E5FF55; box-shadow: 0 0 12px #00E5FF22; }

.entity-name {
  font-size: 14px;
  font-weight: 700;
  color: #FFF;
}

.entity-role {
  font-size: 11px;
  color: #8E8E93;
}

.entity-degree {
  font-size: 11px;
  color: #B0BEC5;
}

.entity-desc {
  font-size: 12px;
  color: #C7C7D1;
  margin-top: 6px;
}

.relation-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.relation-item {
  background: rgba(10, 10, 14, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 10px 12px;
  transition: border-color 0.2s ease, transform 0.2s ease;
}

.relation-header {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.relation-actors {
  font-size: 12px;
  color: #E0E0E0;
}

.relation-weight {
  font-size: 11px;
  color: #8E8E93;
}

.relation-evidence {
  margin-top: 8px;
  font-size: 12px;
  color: #B8B8C0;
  line-height: 1.5;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.reader-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.reader-subtitle {
  font-size: 11px;
  color: #8E8E93;
  letter-spacing: 1px;
}

.reader-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.reader-item {
  background: rgba(10, 10, 14, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 12px;
  color: #C7C7D1;
  line-height: 1.5;
}

.storyline-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.storyline-item {
  background: rgba(10, 10, 14, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 12px;
  color: #C7C7D1;
  line-height: 1.5;
}

.cluster-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cluster-item {
  background: rgba(10, 10, 14, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 10px 12px;
}

/* Entity Styles */
.expert-modal-header.role-protagonist { border-bottom-color: #FFD700; background: linear-gradient(90deg, rgba(255, 215, 0, 0.1) 0%, transparent 100%); }
.expert-modal-header.role-antagonist { border-bottom-color: #FF2A68; background: linear-gradient(90deg, rgba(255, 42, 104, 0.1) 0%, transparent 100%); }
.expert-modal-header.role-supporting { border-bottom-color: #00F0FF; background: linear-gradient(90deg, rgba(0, 240, 255, 0.1) 0%, transparent 100%); }

.relation-list-mini {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.relation-mini-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #CCC;
  padding: 8px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
}
.rel-target { font-weight: 600; color: #FFF; }
.rel-arrow { color: #666; font-size: 11px; }
.rel-type { font-weight: 600; font-size: 11px; }
.no-data { color: #666; font-size: 12px; font-style: italic; }
.quote { font-style: italic; color: #E0E0E0; font-family: "Georgia", serif; border-left: 2px solid #666; padding-left: 12px; }

/* Expert Modal */
.expert-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(5px);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
}

.expert-modal {
  width: 500px;
  background: rgba(20, 24, 30, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.05);
  overflow: hidden;
  animation: slide-up 0.3s ease-out;
}

@keyframes slide-up {
  from { transform: translateY(20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.expert-modal-header {
  padding: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(90deg, rgba(255,255,255,0.05) 0%, transparent 100%);
}

.expert-info .name {
  font-size: 18px;
  font-weight: 600;
  color: #FFF;
}
.expert-info .role {
  font-size: 12px;
  color: #888;
  margin-top: 2px;
}

.close-btn {
  font-size: 24px;
  cursor: pointer;
  color: #666;
  transition: color 0.2s;
}
.close-btn:hover { color: #FFF; }

.expert-modal-content {
  padding: 24px;
}

.report-section {
  margin-bottom: 24px;
}
.report-section:last-child { margin-bottom: 0; }

.section-title {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #666;
  margin-bottom: 8px;
}

.section-text {
  font-size: 14px;
  line-height: 1.6;
  color: #DDD;
}

.related-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.tag {
  font-size: 12px;
  padding: 4px 10px;
  border: 1px solid #444;
  border-radius: 12px;
}

.expert-view-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.expert-view-card {
  background: rgba(20, 20, 24, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  backdrop-filter: blur(4px);
  transition: all 0.3s;
  cursor: pointer;
}

.expert-view-card:hover {
  background: rgba(30, 30, 35, 0.8);
  border-color: rgba(255, 255, 255, 0.2);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.expert-view-card.is-selected {
  border-color: #FFD700;
  background: rgba(255, 215, 0, 0.05);
  box-shadow: 0 0 15px rgba(255, 215, 0, 0.1);
}

.expert-view-name {
  font-size: 13px;
  font-weight: 700;
  color: #FFF;
  text-shadow: 0 0 5px rgba(255, 255, 255, 0.3);
}

.expert-view-role {
  font-size: 11px;
  color: #8E8E93;
}

.expert-view-desc {
  font-size: 12px;
  color: #C7C7D1;
  line-height: 1.5;
}

.expert-view-action {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}
.action-btn {
  font-size: 11px;
  color: #FFD700;
  font-weight: 600;
}

.cluster-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.cluster-size {
  font-size: 11px;
  color: #8E8E93;
}

.cluster-members {
  font-size: 12px;
  color: #C7C7D1;
  line-height: 1.5;
}

/* Loading */
.ritual-ceremony {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
}

.ritual-title { font-size: 24px; color: #FFF; margin-bottom: 16px; }
.ritual-msg { color: #888; margin-bottom: 32px; }

.fortune-tip-container {
  background: rgba(255, 255, 255, 0.05);
  padding: 12px 24px;
  border-radius: 24px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.tip-label { color: #FFD700; margin-right: 8px; font-weight: bold; }
.tip-content { color: #CCC; }

/* Transitions */
.fade-enter-active, .fade-leave-active { transition: opacity 0.5s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* Entity Sidebar */
.entity-sidebar {
  position: absolute;
  top: 0;
  right: 0;
  width: 360px;
  height: 100%;
  background: rgba(18, 18, 22, 0.98);
  border-left: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: -10px 0 30px rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(12px);
  z-index: 100;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(90deg, rgba(255,255,255,0.05) 0%, transparent 100%);
}

.sidebar-header.role-protagonist { border-bottom-color: #FFD700; }
.sidebar-header.role-antagonist { border-bottom-color: #FF2A68; }
.sidebar-header.role-supporting { border-bottom-color: #00F0FF; }

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.relation-actors-block {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  color: #E5E5EA;
}

.relation-arrow {
  color: #8E8E93;
}

.entity-link {
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.06);
  color: #FFFFFF;
  cursor: pointer;
  font-size: 12px;
}

.entity-link:hover {
  background: rgba(255, 255, 255, 0.12);
}

.relation-tag {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  font-size: 12px;
  font-weight: 600;
}

/* Slide Transition */
.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-right-enter-from,
.slide-right-leave-to {
  transform: translateX(100%);
}

/* Search Bar */
.search-bar {
  pointer-events: auto;
  display: flex;
  align-items: center;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 20px;
  padding: 4px 8px;
  margin-right: 16px;
  backdrop-filter: blur(4px);
}

.search-bar input {
  background: transparent;
  border: none;
  color: #FFF;
  font-size: 13px;
  width: 120px;
  padding: 4px 8px;
  outline: none;
}

.search-bar input::placeholder {
  color: rgba(255, 255, 255, 0.4);
}

.search-btn {
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  padding: 4px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.search-btn:hover {
  color: #FFF;
  background: rgba(255, 255, 255, 0.1);
}

.search-btn .icon {
  font-size: 14px;
}
</style>
