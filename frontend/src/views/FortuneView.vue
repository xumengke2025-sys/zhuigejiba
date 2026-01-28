<template>
  <div class="fortune-view">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">万年 · WANNIAN</div>
        <!-- 防命薄机制 -->
        <label class="fate-shield-toggle" :class="{ disabled: sessionId }">
          <input 
            type="checkbox" 
            v-model="fateShieldEnabled" 
            :disabled="!!sessionId"
            @change="handleFateShieldChange"
          />
          <span class="toggle-label">防命薄机制</span>
        </label>
      </div>
      <div class="header-right">
        <div class="status-badge" v-if="sessionId">
          <span class="dot" :class="status"></span>
          {{ statusText }}
        </div>
      </div>
    </header>

    <main class="content-container">
      <!-- Left: Input & Masters -->
      <div class="left-panel">
        <div class="input-card" v-if="!sessionId || status === 'processing'">
          <h2 class="section-title">输入出生信息</h2>
          <div class="form-grid">
            <div class="form-item">
              <label>用户姓名</label>
              <input type="text" v-model="formData.name" placeholder="请输入您的姓名" :disabled="loading" />
            </div>
            <div class="form-item">
              <label>公历生日</label>
              <input type="date" v-model="formData.birthday" :disabled="loading" />
            </div>
            <div class="form-item">
              <label>出生时间</label>
              <input type="time" v-model="formData.birth_time" :disabled="loading" />
            </div>
            <div class="form-item">
              <label>出生地点</label>
              <input type="text" v-model="formData.birth_location" placeholder="例如：北京" :disabled="loading" />
            </div>
            <div class="form-item">
              <label>性别</label>
              <select v-model="formData.gender" :disabled="loading">
                <option value="男">男</option>
                <option value="女">女</option>
              </select>
            </div>
            <div class="form-item">
              <label>预测未来年数</label>
              <input type="number" v-model="formData.future_years" min="1" max="20" :disabled="loading" />
            </div>
          </div>
          <button class="start-btn" @click="handleAnalyze" :disabled="loading || !isFormValid">
            {{ loading ? '推演启动中...' : '启动 49 位大师并行推演' }}
          </button>
        </div>

        <!-- Master Hall -->
        <div class="master-hall">
          <div class="hall-header">
            <h2 class="section-title">大师殿堂 · 49 位命理大师</h2>
            <div class="progress-container" v-if="sessionId">
              <div class="progress-info">
                <span class="progress-percent">{{ progress }}%</span>
                <span class="progress-msg">{{ statusMsg }}</span>
              </div>
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: progress + '%' }"></div>
              </div>
              <div class="progress-logs" v-if="statusLogs.length > 0">
                <div v-for="(log, i) in statusLogs" :key="i" class="log-item" :class="{ 
                  'first-log': i === 0,
                  'graph-log': log.msg.includes('图谱')
                }">
                  <span class="log-time">{{ log.time }}</span>
                  <span class="log-msg">{{ log.msg }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="master-grid">
            <div 
              v-for="master in masters" 
              :key="master.id" 
              class="master-card"
              :class="{ 
                'is-done': reports[master.id], 
                'is-active': activeMasterId === master.id,
                'is-pending': sessionId && !reports[master.id]
              }"
              @click="selectedMaster = master"
            >
              <div class="master-avatar">{{ master.name[0] }}</div>
              <div class="master-info">
                <div class="master-name">{{ master.name }}</div>
                <div class="master-camp">{{ master.camp }}</div>
              </div>
              <div class="check-icon" v-if="reports[master.id]">✓</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Reports & Summary -->
      <div class="right-panel">
        <div class="empty-state" v-if="!sessionId">
          <div class="abstract-bg"></div>
          <div class="empty-content">
            <h3>开启万年推演</h3>
            <p>输入出生信息与预测年限，49 位跨越时空与流派的大师将为您合力推演未来轨迹</p>
          </div>
        </div>

        <div class="report-container" v-else>
          <div class="active-report" v-if="activeMasterId && reports[activeMasterId]">
            <div class="report-header">
              <span class="master-tag">{{ reports[activeMasterId].name }}</span>
              <button class="close-report" @click="activeMasterId = null">查看全案总结</button>
            </div>
            <div class="report-content markdown-body" v-html="formatMarkdown(reports[activeMasterId].content)"></div>
          </div>

          <div class="global-summary" v-else-if="summary">
            <div class="summary-header">
              <h2 class="summary-title">命运总结官 · 全案汇总</h2>
              <div class="summary-badge">聚合 49 位大师共识</div>
            </div>

            <!-- Tab Content -->
            <div class="tab-content-area" v-if="hasGraphData">
              <!-- 1. Graph Visualizer (Main Tree View) -->
              <div class="graph-full-section">
                <div class="section-header">
                  <h3 class="section-title">全量命运时空图 · 关联推演</h3>
                  <div class="section-subtitle">通过底部滑块控制时间轴，观测命运之树的生长轨迹</div>
                </div>
                <div class="graph-visual-full">
                  <GraphVisualizer 
                    :data="summary.graph_data" 
                    :min-year="predictionStartYear"
                    :max-year="predictionEndYear"
                  />
                </div>
              </div>

              <!-- 2. Fate Radar & Structured Report -->
              <div class="graph-full-section">

                <div class="section-header">
                  <h3 class="section-title">
                    {{ currentYearTab === 'all' ? '赛博天机仪 · 核心推演拟合' : `${currentYearTab} · 年度天机拟合` }}
                  </h3>
                  <div class="section-subtitle">
                    {{ currentYearTab === 'all' ? '基于 49 位命理大师的预测进行全量时空拟合' : `聚焦 ${currentYearTab} 的核心定数与变数` }}
                  </div>
                </div>
                <div class="radar-visual-wrapper">
                  <FateRadar :data="currentRadarData" :key="currentYearTab" />
                </div>
              </div>

              <!-- 3. Yearly Breakdown List (Visible when specific year selected) -->
              <div class="summary-grid" v-if="currentYearTab !== 'all'">
                 <div class="summary-block">
                  <h3>{{ currentYearTab }} 核心定数</h3>
                  <ul v-if="currentYearConsensus.length">
                    <li v-for="(item, i) in currentYearConsensus" :key="i">
                      <span class="item-text">{{ item.name }}</span>
                      <span class="item-desc" v-if="item.description"> - {{ item.description.substring(0, 30) }}...</span>
                      <span class="item-impact">强度 {{ item.impact }}</span>
                    </li>
                  </ul>
                  <div v-else class="empty-list">本年度暂无核心定数记录</div>
                </div>
                <div class="summary-block">
                  <h3>{{ currentYearTab }} 命理变数</h3>
                  <ul v-if="currentYearUnique.length">
                    <li v-for="(item, i) in currentYearUnique" :key="i" class="conflict-item">
                      <span class="item-text">{{ item.name }}</span>
                      <span class="item-desc" v-if="item.description"> - {{ item.description.substring(0, 30) }}...</span>
                      <span class="item-impact">变数 {{ item.impact }}</span>
                    </li>
                  </ul>
                  <div v-else class="empty-list">本年度暂无特殊变数记录</div>
                </div>
              </div>
            </div>

            <!-- 4. 结构化报告表格 (Always Visible) -->
            <div class="fate-report-table" v-if="hasGraphData">
              <div class="table-header">
                <h3 class="table-title">
                  <span class="title-icon">📜</span>
                  全案推演报告
                </h3>
                <div class="table-filters">
                  <button 
                    v-for="dim in [{key: 'all', name: '全部', icon: '🌐'}, {key: 'career', name: '事业', icon: '💼'}, {key: 'wealth', name: '财富', icon: '💰'}, {key: 'emotion', name: '情感', icon: '❤️'}, {key: 'health', name: '健康', icon: '🌿'}]"
                    :key="dim.key"
                    :class="['filter-btn', { active: selectedDimension === dim.key }]"
                    @click="selectedDimension = dim.key"
                  >
                    <span class="btn-icon">{{ dim.icon }}</span>
                    {{ dim.name }}
                  </button>
                </div>
              </div>
              
              <div class="table-container">
                <div v-for="yearData in filteredTableData" :key="yearData.year" class="year-section">
                  <div class="year-header">
                    <span class="year-badge">{{ yearData.year }}</span>
                    <div class="year-line"></div>
                  </div>
                  
                  <div class="dimensions-grid">
                    <div v-for="dimData in yearData.dimensions" :key="dimData.dimension" class="dimension-card">
                      <div class="dim-header">
                        <span class="dim-icon">{{ dimData.icon }}</span>
                        <span class="dim-name">{{ dimData.name }}</span>
                      </div>
                      
                      <!-- 核心共识 -->
                      <div class="insight-group consensus-group" v-if="dimData.consensus.length">
                        <div class="group-label">
                          <span class="label-dot consensus"></span>
                          核心共识
                        </div>
                        <div v-for="(item, idx) in dimData.consensus" :key="'c'+idx" class="insight-item">
                          <div class="item-header" @click="toggleRowExpand(`${yearData.year}-${dimData.dimension}-c-${idx}`)">
                            <span class="item-title">{{ item.name }}</span>
                            <div class="item-meta">
                              <span class="impact-badge high">强度 {{ item.impact }}</span>
                              <span class="expand-icon">{{ expandedRows.has(`${yearData.year}-${dimData.dimension}-c-${idx}`) ? '▲' : '▼' }}</span>
                            </div>
                          </div>
                          <Transition name="slide">
                            <div v-if="expandedRows.has(`${yearData.year}-${dimData.dimension}-c-${idx}`)" class="item-detail">
                              <p class="detail-text">{{ item.description }}</p>
                              <span class="detail-source">— {{ item.master_name }}</span>
                            </div>
                          </Transition>
                        </div>
                      </div>
                      
                      <!-- 独特视角 -->
                      <div class="insight-group unique-group" v-if="dimData.unique.length">
                        <div class="group-label">
                          <span class="label-dot unique"></span>
                          独特视角
                        </div>
                        <div v-for="(item, idx) in dimData.unique" :key="'u'+idx" class="insight-item">
                          <div class="item-header" @click="toggleRowExpand(`${yearData.year}-${dimData.dimension}-u-${idx}`)">
                            <span class="item-title unique-title">✨ {{ item.name }}</span>
                            <div class="item-meta">
                              <span class="impact-badge medium">影响 {{ item.impact }}</span>
                              <span class="expand-icon">{{ expandedRows.has(`${yearData.year}-${dimData.dimension}-u-${idx}`) ? '▲' : '▼' }}</span>
                            </div>
                          </div>
                          <Transition name="slide">
                            <div v-if="expandedRows.has(`${yearData.year}-${dimData.dimension}-u-${idx}`)" class="item-detail">
                              <p class="detail-text">{{ item.description }}</p>
                              <span class="detail-source">— {{ item.master_name }}</span>
                            </div>
                          </Transition>
                        </div>
                      </div>
                      
                      <!-- 命理变数 -->
                      <div class="insight-group variable-group" v-if="dimData.variable.length">
                        <div class="group-label">
                          <span class="label-dot variable"></span>
                          命理变数
                        </div>
                        <div v-for="(item, idx) in dimData.variable" :key="'v'+idx" class="insight-item">
                          <div class="item-header" @click="toggleRowExpand(`${yearData.year}-${dimData.dimension}-v-${idx}`)">
                            <span class="item-title variable-title">⚡ {{ item.name }}</span>
                            <div class="item-meta">
                              <span class="impact-badge warning">变数 {{ item.impact }}</span>
                              <span class="expand-icon">{{ expandedRows.has(`${yearData.year}-${dimData.dimension}-v-${idx}`) ? '▲' : '▼' }}</span>
                            </div>
                          </div>
                          <Transition name="slide">
                            <div v-if="expandedRows.has(`${yearData.year}-${dimData.dimension}-v-${idx}`)" class="item-detail variable-detail">
                              <p class="detail-text">{{ item.description }}</p>
                              <span class="detail-source">— {{ item.master_name }}</span>
                            </div>
                          </Transition>
                        </div>
                      </div>
                      
                      <div v-if="!dimData.consensus.length && !dimData.unique.length && !dimData.variable.length" class="empty-dim">
                        暂无数据
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 5. Global Lists (Only in All tab and if graph data exists) -->
            <div class="summary-grid" v-if="currentYearTab === 'all' && hasGraphData">
              <div class="summary-block">
                <h3>全案核心共识</h3>
                <ul>
                  <li v-for="(item, i) in summary.consensus" :key="i">
                    <span class="item-text">{{ typeof item === 'object' ? item.text : item }}</span>
                    <span v-if="item.impact" class="item-impact">强度 {{ item.impact }}</span>
                  </li>
                </ul>
              </div>
              <div class="summary-block">
                <h3>全案命理变数</h3>
                <ul>
                  <li v-for="(item, i) in summary.conflicts" :key="i" class="conflict-item">
                    <span class="item-text">{{ typeof item === 'object' ? item.text : item }}</span>
                    <span v-if="item.impact" class="item-impact">变数 {{ item.impact }}</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          <div class="summary-loading ritual-ceremony" v-else>
            <div class="ritual-bg">
              <div class="scan-line"></div>
              <div class="orbit-circles">
                <div class="orbit-1"></div>
                <div class="orbit-2"></div>
                <div class="orbit-3"></div>
              </div>
            </div>
            <div class="ritual-content">
              <div class="ritual-spinner"></div>
              <h2 class="ritual-title">
                {{ status === 'completed' ? '天机已现' : (status === 'aggregating' ? '天机聚合中' : '大师推演中') }}
              </h2>
              <p class="ritual-msg">
                {{ status === 'completed' ? '推演全案已准备就绪，正在呈现最终图谱...' : statusMsg }}
              </p>
              
              <!-- 天机贴士轮播 -->
              <div class="fortune-tip-container" v-if="status !== 'completed'">
                <Transition name="fade" mode="out-in">
                  <div :key="currentTipIndex" class="fortune-tip">
                    <span class="tip-label">天机贴士:</span>
                    <span class="tip-content">{{ fortuneTips[currentTipIndex] }}</span>
                  </div>
                </Transition>
              </div>

              <div class="loading-stats">已完成: {{ reportsCount }} / 49 位大师</div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- Master Detail Modal -->
    <div class="modal-overlay" v-if="selectedMaster" @click="selectedMaster = null">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <div class="modal-avatar">{{ selectedMaster.name[0] }}</div>
          <div class="modal-title-group">
            <h3>{{ selectedMaster.name }}</h3>
            <span class="modal-camp">{{ selectedMaster.camp }} · {{ selectedMaster.role }}</span>
          </div>
          <button class="close-modal" @click="selectedMaster = null">&times;</button>
        </div>
        <div class="modal-body">
          <div class="info-section">
            <h4>流派简介</h4>
            <p>{{ selectedMaster.description }}</p>
          </div>
          <div class="info-section">
            <h4>核心推演逻辑</h4>
            <p>{{ selectedMaster.methodology }}</p>
          </div>
          <div class="report-section" v-if="reports[selectedMaster.id]">
            <h4>推演报告</h4>
            <div class="report-text markdown-body" v-html="formatMarkdown(reports[selectedMaster.id].content)"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 防命薄机制弹窗 -->
    <div class="modal-overlay fate-shield-modal" v-if="showFateShieldModal" @click="showFateShieldModal = false">
      <div class="modal-content fate-shield-content" @click.stop>
        <div class="modal-header">
          <div class="modal-avatar">🛡️</div>
          <div class="modal-title-group">
            <h3>防命薄机制已启动</h3>
            <span class="modal-camp">平行时空保护协议</span>
          </div>
        </div>
        <div class="modal-body">
          <div class="shield-message">
            <p>我会告诉各位大师本次为<strong>平行时空</strong>下的命理演算，不会对您的个人命运造成影响。</p>
          </div>
          <button class="confirm-btn" @click="confirmFateShield">确认启动</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { analyzeFate, getStatus, getReport, listMasters } from '../api/fortune'
import toast from '../utils/toast'
import { marked } from 'marked'
import GraphVisualizer from '../components/GraphVisualizer.vue'
import FateRadar from '../components/FateRadar.vue'

const router = useRouter()

// Form Data
const formData = ref({
  name: '',
  birthday: '1995-06-15',
  birth_time: '10:00',
  birth_location: '上海',
  gender: '男',
  future_years: 3
})

const predictionStartYear = computed(() => new Date().getFullYear())
const predictionEndYear = computed(() => {
  const years = parseInt(formData.value.future_years) || 10
  return predictionStartYear.value + years
})

// State
const loading = ref(false)
const sessionId = ref(null)
const status = ref('idle')
const statusMsg = ref('')
const progress = ref(0)
const statusLogs = ref([])
const masters = ref([])
const reports = ref({})
const summary = ref(null)
const activeMasterId = ref(null)
const selectedMaster = ref(null)
const pollTimer = ref(null)
const currentYearTab = ref('all') // 'all' or '2026年', '2027年' etc.

// 防命薄机制状态
const fateShieldEnabled = ref(false)
const showFateShieldModal = ref(false)

// 天机贴士逻辑
const currentTipIndex = ref(0)
const fortuneTips = [
  "紫微斗数起源于北宋，是中国传统命理学的重要支柱。",
  "八字中的‘五行’指金、木、水、火、土，代表宇宙能量的循环。",
  "天干地支共有60种组合，称为‘六十甲子’。",
  "奇门遁甲被誉为‘帝王之学’，侧重于时空方位的选择。",
  "西方古典占星学通过行星的尊贵力量来判断命运轨迹。",
  "人类图结合了易经、占星、卡巴拉和脉轮系统。",
  "塔罗牌的大阿卡纳共有22张，象征灵魂成长的不同阶段。",
  "大师们的观点若有冲突，往往代表你命局中存在转折的变数。"
]
let tipTimer = null

const startTipRotation = () => {
  if (tipTimer) clearInterval(tipTimer)
  tipTimer = setInterval(() => {
    currentTipIndex.value = (currentTipIndex.value + 1) % fortuneTips.length
  }, 5000)
}

const stopTipRotation = () => {
  if (tipTimer) clearInterval(tipTimer)
}

// 防命薄机制处理
const handleFateShieldChange = () => {
  if (fateShieldEnabled.value) {
    showFateShieldModal.value = true
  }
}

const confirmFateShield = () => {
  showFateShieldModal.value = false
}

const isFormValid = computed(() => {
  return formData.value.birthday && formData.value.birth_time && formData.value.birth_location
})

const availableYears = computed(() => {
  if (!summary.value || !summary.value.graph_data || !summary.value.graph_data.nodes) return []
  const years = new Set(summary.value.graph_data.nodes.map(n => n.properties?.time).filter(t => t))
  return Array.from(years).sort()
})

const currentRadarData = computed(() => {
  if (!summary.value || !summary.value.graph_data) return { nodes: [], edges: [] }
  if (currentYearTab.value === 'all') return summary.value.graph_data
  
  const filteredNodes = summary.value.graph_data.nodes.filter(n => n.properties?.time === currentYearTab.value)
  // Keep edges only if both source and target are in filteredNodes
  const nodeIds = new Set(filteredNodes.map(n => n.id))
  const filteredEdges = summary.value.graph_data.edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
  
  return { nodes: filteredNodes, edges: filteredEdges }
})

const currentYearConsensus = computed(() => {
  if (!currentRadarData.value.nodes) return []
  return currentRadarData.value.nodes
    .filter(n => n.properties?.type === 'consensus')
    .map(n => n.properties)
    .sort((a, b) => b.impact - a.impact)
})

const currentYearUnique = computed(() => {
  if (!currentRadarData.value.nodes) return []
  return currentRadarData.value.nodes
    .filter(n => n.properties?.type === 'unique' || n.properties?.type === 'conflict' || n.properties?.type === 'variable')
    .map(n => n.properties)
    .sort((a, b) => b.impact - a.impact)
})

const hasGraphData = computed(() => {
  return summary.value?.graph_data?.nodes?.length > 0
})

// 表格数据计算属性 - 按年份和维度组织数据
const tableData = computed(() => {
  if (!summary.value?.graph_data?.nodes) return []
  
  const nodes = summary.value.graph_data.nodes
  const dimensions = ['career', 'wealth', 'emotion', 'health']
  const dimNames = { career: '事业', wealth: '财富', emotion: '情感', health: '健康' }
  const dimIcons = { career: '💼', wealth: '💰', emotion: '❤️', health: '🌿' }
  
  // 按年份分组
  const years = [...new Set(nodes.map(n => n.properties?.time).filter(Boolean))].sort()
  
  return years.map(year => {
    const yearNodes = nodes.filter(n => n.properties?.time === year)
    
    const dimData = dimensions.map(dim => {
      const dimNodes = yearNodes.filter(n => n.properties?.dimension === dim)
      return {
        dimension: dim,
        name: dimNames[dim],
        icon: dimIcons[dim],
        consensus: dimNodes.filter(n => n.properties?.type === 'consensus').map(n => n.properties),
        unique: dimNodes.filter(n => n.properties?.type === 'unique').map(n => n.properties),
        variable: dimNodes.filter(n => n.properties?.type === 'variable').map(n => n.properties)
      }
    })
    
    return { year, dimensions: dimData }
  })
})

// 表格筛选状态
const selectedDimension = ref('all')
const expandedRows = ref(new Set())

const filteredTableData = computed(() => {
  if (selectedDimension.value === 'all') return tableData.value
  return tableData.value.map(yearData => ({
    ...yearData,
    dimensions: yearData.dimensions.filter(d => d.dimension === selectedDimension.value)
  }))
})

const toggleRowExpand = (key) => {
  if (expandedRows.value.has(key)) {
    expandedRows.value.delete(key)
  } else {
    expandedRows.value.add(key)
  }
  expandedRows.value = new Set(expandedRows.value)
}

const statusText = computed(() => {
  const map = {
    idle: '待机',
    processing: '大师推演中',
    aggregating: '总结官汇总中',
    completed: '推演已完成',
    failed: '推演异常'
  }
  return map[status.value] || status.value
})

const reportsCount = computed(() => Object.keys(reports.value).length)

// Methods
const handleAnalyze = async () => {
  loading.value = true
  reports.value = {}
  summary.value = null
  progress.value = 0
  statusLogs.value = []
  try {
    const res = await analyzeFate(formData.value)
    if (res.success) {
      sessionId.value = res.session_id
      status.value = 'processing'
      startPolling()
      startTipRotation()
    }
  } catch (err) {
    toast.error('启动失败', err.message)
  } finally {
    loading.value = false
  }
}

const startPolling = () => {
  if (pollTimer.value) clearInterval(pollTimer.value)
  pollTimer.value = setInterval(async () => {
    try {
      const res = await getStatus(sessionId.value)
      if (res.success) {
        status.value = res.status
        if (res.status_msg && res.status_msg !== statusMsg.value) {
          statusMsg.value = res.status_msg
          statusLogs.value.unshift({
            time: new Date().toLocaleTimeString(),
            msg: res.status_msg
          })
          if (statusLogs.value.length > 5) statusLogs.value.pop()
        }
        progress.value = res.progress
        
        // 如果 summary 存在，直接更新，减少一次请求
        if (res.summary) {
          summary.value = res.summary
        }

        // 如果已经完成但 summary 还没拿到，或者需要更新大师报告（小于49个时持续更新）
        if (status.value === 'completed' || status.value === 'failed' || Object.keys(reports.value).length < 49) {
          const fullRes = await getReport(sessionId.value)
          if (fullRes.success) {
            reports.value = fullRes.reports || {}
            if (fullRes.summary) summary.value = fullRes.summary
          }
        }

        if (status.value === 'completed' || status.value === 'failed') {
          clearInterval(pollTimer.value)
          stopTipRotation()
        }
      }
    } catch (err) {
      console.error('轮询失败:', err)
    }
  }, 2000)
}

const formatMarkdown = (text) => {
  if (!text) return ''
  return marked(text)
}

onMounted(async () => {
  const res = await listMasters()
  if (res.success) {
    masters.value = res.data
  }
})

onUnmounted(() => {
  if (pollTimer.value) clearInterval(pollTimer.value)
})
</script>

<style scoped>
.fortune-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #0A0A0B;
  color: #E0E0E0;
  font-family: 'Space Grotesk', -apple-system, sans-serif;
  overflow: hidden;
}

.app-header {
  height: 64px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #1F1F22;
  background: #0D0D0F;
}

.brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 20px;
  letter-spacing: 2px;
  color: #FFF;
  cursor: pointer;
  background: linear-gradient(90deg, #FFF, #888);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

/* 防命薄机制样式 */
.fate-shield-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 24px;
  cursor: pointer;
  user-select: none;
}

.fate-shield-toggle.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.fate-shield-toggle input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: #FFD700;
  cursor: inherit;
}

.fate-shield-toggle .toggle-label {
  font-size: 13px;
  color: #888;
  transition: color 0.2s;
}

.fate-shield-toggle:not(.disabled):hover .toggle-label {
  color: #FFD700;
}

.fate-shield-toggle input:checked + .toggle-label {
  color: #FFD700;
}

/* 防命薄弹窗样式 */
.fate-shield-modal .fate-shield-content {
  max-width: 400px;
  text-align: center;
}

.fate-shield-content .modal-header {
  flex-direction: column;
  gap: 16px;
}

.fate-shield-content .modal-avatar {
  font-size: 48px;
  background: none;
}

.fate-shield-content .shield-message {
  padding: 24px;
  background: rgba(255, 215, 0, 0.1);
  border-radius: 12px;
  border: 1px solid rgba(255, 215, 0, 0.2);
  margin-bottom: 24px;
}

.fate-shield-content .shield-message p {
  color: #E0E0E0;
  line-height: 1.8;
  font-size: 15px;
}

.fate-shield-content .shield-message strong {
  color: #FFD700;
}

.fate-shield-content .confirm-btn {
  width: 100%;
  padding: 14px;
  background: linear-gradient(135deg, #FFD700, #FFA500);
  color: #000;
  border: none;
  border-radius: 8px;
  font-weight: 700;
  font-size: 15px;
  cursor: pointer;
  transition: all 0.2s;
}

.fate-shield-content .confirm-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(255, 215, 0, 0.3);
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
.dot.aggregating { background: #2196F3; animation: pulse 1s infinite; }
.dot.completed { background: #4CAF50; }

@keyframes pulse { 50% { opacity: 0.4; } }

.content-container {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* Left Panel */
.left-panel {
  width: 480px;
  min-width: 480px;
  border-right: 1px solid #1F1F22;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  background: #0D0D0F;
}

.input-card {
  padding: 24px;
  border-bottom: 1px solid #1F1F22;
}

.section-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 20px;
  color: #FFF;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-item label {
  font-size: 11px;
  color: #888;
  text-transform: uppercase;
}

.form-item input, .form-item select {
  background: #1A1A1D;
  border: 1px solid #2A2A2F;
  color: #FFF;
  padding: 10px;
  border-radius: 6px;
  font-size: 14px;
  width: 100%;
}

.form-item input[type="number"] {
  -moz-appearance: textfield;
}
.form-item input::-webkit-outer-spin-button,
.form-item input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

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

.master-hall {
  padding: 24px;
  flex: 1;
}

.hall-header {
  margin-bottom: 24px;
}

.progress-container {
  margin-top: 16px;
  background: #141417;
  padding: 16px;
  border-radius: 12px;
  border: 1px solid #1F1F22;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.progress-percent {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 18px;
  color: #FFF;
}

.progress-msg {
  font-size: 12px;
  color: #888;
  font-style: italic;
}

.progress-bar {
  height: 6px;
  background: #1A1A1D;
  border-radius: 3px;
  overflow: hidden;
}

.progress-logs {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.log-item {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #444;
  display: flex;
  gap: 10px;
  transition: all 0.3s;
}

.first-log {
  color: #AAA;
}

.graph-log {
  color: #64B5F6 !important; /* 科技蓝色 */
  font-weight: 500;
}

.log-time {
  flex-shrink: 0;
  width: 70px;
}

.log-msg {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #444, #FFF, #444);
  background-size: 200% 100%;
  animation: shine 2s linear infinite;
  transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes shine {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.master-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.master-card {
  background: #141417;
  border: 1px solid #1F1F22;
  padding: 12px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.master-card:hover { border-color: #3A3A3F; background: #1A1A1D; }
.master-card.is-active { border-color: #FFF; background: #1F1F22; }
.master-card.is-pending { opacity: 0.6; }
.master-card.is-done { border-color: rgba(76, 175, 80, 0.3); }

.master-avatar {
  width: 32px;
  height: 32px;
  background: #2A2A2F;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  color: #FFF;
}

.master-info { overflow: hidden; }
.master-name { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.master-camp { font-size: 10px; color: #666; }

.check-icon {
  position: absolute;
  right: 8px;
  top: 8px;
  color: #4CAF50;
  font-size: 12px;
  font-weight: bold;
}

/* Right Panel */
.right-panel {
  flex: 1;
  background: #080809;
  position: relative;
  display: flex;
  flex-direction: column;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.empty-content h3 { font-size: 24px; margin-bottom: 12px; color: #FFF; }
.empty-content p { color: #666; max-width: 300px; line-height: 1.6; }

.report-container {
  height: 100%;
  overflow-y: auto;
  padding: 40px;
}

.active-report {
  background: #0D0D0F;
  border: 1px solid #1F1F22;
  border-radius: 12px;
  padding: 32px;
  animation: slideUp 0.4s ease-out;
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.master-tag {
  background: #FFF;
  color: #000;
  padding: 4px 12px;
  border-radius: 4px;
  font-weight: 700;
  font-size: 12px;
}

.close-report {
  background: transparent;
  border: 1px solid #333;
  color: #888;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
}

.global-summary {
  max-width: 1000px; /* 增加最大宽度以适配大图 */
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.summary-header {
  margin-bottom: 32px;
  text-align: center;
}

.summary-title { font-size: 32px; font-weight: 800; color: #FFF; margin-bottom: 12px; }
.summary-badge { display: inline-block; background: #1A1A1D; color: #888; padding: 4px 16px; border-radius: 20px; font-size: 12px; border: 1px solid #2A2A2F; }

.graph-full-section {
  background: #141417;
  border-radius: 16px;
  padding: 24px;
  border: 1px solid #1F1F22;
}

.section-header {
  margin-bottom: 20px;
}

.section-title {
  font-size: 18px;
  color: #FFF;
  margin: 0;
}

.section-subtitle {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}

.graph-visual-full {
  width: 100%;
  min-height: 600px;
  border-radius: 12px;
  /* 允许内部 SVG 完整展示，不被外层裁剪 */
  overflow: visible;
  position: relative;
}

.radar-visual-wrapper {
  width: 100%;
  height: 600px;
  border-radius: 12px;
  overflow: hidden;
  background: #080809;
}

/* Ritual Ceremony Styles */
.ritual-ceremony {
  height: 600px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  background: #050505;
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid #1a1a1d;
}

.ritual-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  opacity: 0.3;
}

.scan-line {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, transparent, #FFD700, transparent);
  animation: scanMove 3s infinite linear;
}

@keyframes scanMove {
  from { top: 0; }
  to { top: 100%; }
}

.orbit-circles div {
  position: absolute;
  top: 50%;
  left: 50%;
  border: 1px solid rgba(255, 215, 0, 0.2);
  border-radius: 50%;
  transform: translate(-50%, -50%);
}

.orbit-1 { width: 200px; height: 200px; animation: rotateCW 10s linear infinite; }
.orbit-2 { width: 400px; height: 400px; animation: rotateCCW 15s linear infinite; border-style: dashed !important; }
.orbit-3 { width: 600px; height: 600px; animation: rotateCW 20s linear infinite; }

@keyframes rotateCW { from { transform: translate(-50%, -50%) rotate(0deg); } to { transform: translate(-50%, -50%) rotate(360deg); } }
@keyframes rotateCCW { from { transform: translate(-50%, -50%) rotate(0deg); } to { transform: translate(-50%, -50%) rotate(-360deg); } }

.ritual-content {
  position: relative;
  z-index: 2;
  text-align: center;
}

.ritual-spinner {
  width: 60px;
  height: 60px;
  border: 3px solid rgba(255, 215, 0, 0.1);
  border-top-color: #FFD700;
  border-radius: 50%;
  animation: spin 1s infinite linear;
  margin: 0 auto 24px;
}

.ritual-title {
  font-size: 28px;
  font-weight: 800;
  color: #FFF;
  letter-spacing: 4px;
  margin-bottom: 16px;
  text-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
}

.ritual-msg {
  color: #888;
  font-style: italic;
  font-size: 14px;
  margin-bottom: 24px;
}

.summary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.summary-block {
  background: #141417;
  padding: 24px;
  border-radius: 12px;
  border: 1px solid #1F1F22;
}

.summary-block h3 { font-size: 16px; color: #FFF; margin-bottom: 16px; }
.summary-block ul { list-style: none; padding: 0; }
.summary-block li {
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 12px;
  color: #AAA;
  position: relative;
  padding-left: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.item-impact {
  font-size: 10px;
  background: rgba(255, 215, 0, 0.1);
  color: #FFD700;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid rgba(255, 215, 0, 0.2);
  margin-left: 10px;
  white-space: nowrap;
}

.conflict-item .item-impact {
  background: rgba(255, 82, 82, 0.1);
  color: #FF5252;
  border-color: rgba(255, 82, 82, 0.2);
}
.summary-block li::before { content: "•"; position: absolute; left: 0; color: #FFF; }
.conflict-item { color: #FFAB91 !important; }

.advice-section { margin-top: 40px; }
.advice-section h3 { margin-bottom: 20px; text-align: center; }
.advice-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.advice-card { padding: 20px; border-radius: 12px; border: 1px solid #1F1F22; }
.advice-card h4 { margin-bottom: 12px; font-size: 14px; text-transform: uppercase; }
.advice-card p { font-size: 13px; line-height: 1.5; color: #888; margin-bottom: 8px; }

.career { border-top: 3px solid #2196F3; }
.wealth { border-top: 3px solid #FFC107; }
.emotion { border-top: 3px solid #E91E63; }

.graph-placeholder { margin-top: 48px; }
.graph-visual { background: #0D0D0F; border: 1px dashed #333; border-radius: 12px; height: 300px; display: flex; align-items: center; justify-content: center; }
.visual-placeholder { text-align: center; color: #444; font-size: 14px; line-height: 2; }

.summary-loading {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
}

.spinner { width: 40px; height: 40px; border: 3px solid #222; border-top-color: #FFF; border-radius: 50%; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes slideUp { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

.loading-stats {
  font-family: 'JetBrains Mono', monospace;
  font-size: 14px;
  color: #666;
}

/* 天机贴士样式 */
.fortune-tip-container {
  margin: 20px 0;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.fortune-tip {
  background: rgba(255, 215, 0, 0.05);
  border: 1px solid rgba(255, 215, 0, 0.1);
  padding: 12px 20px;
  border-radius: 8px;
  max-width: 400px;
  text-align: center;
}

.tip-label {
  color: #FFD700;
  font-weight: bold;
  margin-right: 8px;
  font-size: 12px;
  text-transform: uppercase;
}

.tip-content {
  color: #AAA;
  font-size: 13px;
  line-height: 1.5;
}

/* Transition Animations */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.5s ease, transform 0.5s ease;
}
.fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

.summary-text {
  margin-top: 32px;
}

/* Markdown Styles */
.markdown-body { color: #BBB; line-height: 1.8; font-size: 15px; }
.markdown-body h2 { color: #FFF; margin: 24px 0 16px; }
.markdown-body p { margin-bottom: 16px; }
.markdown-body blockquote { border-left: 4px solid #333; padding-left: 16px; color: #888; font-style: italic; }

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-content {
  background: #0D0D0F;
  border: 1px solid #1F1F22;
  border-radius: 16px;
  width: 100%;
  max-width: 600px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 24px 48px rgba(0,0,0,0.5);
  animation: modalIn 0.3s ease-out;
}

@keyframes modalIn { from { transform: scale(0.95); opacity: 0; } to { transform: scale(1); opacity: 1; } }

.modal-header {
  padding: 24px;
  border-bottom: 1px solid #1F1F22;
  display: flex;
  align-items: center;
  gap: 16px;
  position: relative;
}

.modal-avatar {
  width: 48px;
  height: 48px;
  background: #2A2A2F;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 20px;
  color: #FFF;
}

.modal-title-group h3 { font-size: 20px; color: #FFF; margin-bottom: 4px; }
.modal-camp { font-size: 13px; color: #666; }

.close-modal {
  position: absolute;
  right: 20px;
  top: 20px;
  background: none;
  border: none;
  color: #666;
  font-size: 28px;
  cursor: pointer;
  line-height: 1;
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}

.info-section { margin-bottom: 24px; }
.info-section h4 { font-size: 14px; color: #FFF; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px; }
.info-section p { font-size: 15px; color: #AAA; line-height: 1.6; }

.report-section { margin-top: 32px; border-top: 1px solid #1F1F22; padding-top: 24px; }
.report-section h4 { font-size: 14px; color: #FFF; margin-bottom: 16px; text-transform: uppercase; }

/* Tab Navigation Styles */
.year-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  border-bottom: 1px solid #1F1F22;
  padding-bottom: 12px;
  overflow-x: auto;
}

.tab-item {
  padding: 8px 16px;
  border-radius: 6px;
  background: #141417;
  color: #888;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #1F1F22;
  white-space: nowrap;
}

.tab-item:hover {
  background: #1A1A1D;
  color: #BBB;
}

.tab-item.active {
  background: #FFF;
  color: #000;
  font-weight: 700;
  border-color: #FFF;
}

.tab-content-area {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.item-desc {
  font-size: 12px;
  color: #666;
  font-style: italic;
  margin-left: 4px;
}

.empty-list {
  color: #666;
  font-style: italic;
  font-size: 13px;
  padding: 10px 0;
}

/* ========================================
   全案推演报告表格样式 - 酷炫深色主题
   ======================================== */
.fate-report-table {
  margin-top: 32px;
  background: linear-gradient(180deg, #0D0D10 0%, #080809 100%);
  border-radius: 16px;
  border: 1px solid #1A1A1F;
  overflow: hidden;
  box-shadow: 
    0 4px 24px rgba(0, 0, 0, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.03);
}

.table-header {
  padding: 20px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #1A1A1F;
  background: linear-gradient(90deg, rgba(20, 20, 25, 0.8) 0%, rgba(15, 15, 18, 0.8) 100%);
}

.table-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 700;
  color: #FFF;
  margin: 0;
}

.title-icon {
  font-size: 22px;
}

.table-filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 20px;
  background: rgba(30, 30, 35, 0.6);
  border: 1px solid #2A2A30;
  color: #888;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.25s ease;
}

.filter-btn:hover {
  background: rgba(50, 50, 60, 0.6);
  color: #BBB;
  border-color: #3A3A45;
}

.filter-btn.active {
  background: linear-gradient(135deg, #2D2D35 0%, #1F1F25 100%);
  color: #FFF;
  border-color: #FFD700;
  box-shadow: 0 0 12px rgba(255, 215, 0, 0.15);
}

.btn-icon {
  font-size: 14px;
}

.table-container {
  padding: 20px;
  max-height: 600px;
  overflow-y: auto;
}

.table-container::-webkit-scrollbar {
  width: 6px;
}

.table-container::-webkit-scrollbar-track {
  background: #0A0A0C;
  border-radius: 3px;
}

.table-container::-webkit-scrollbar-thumb {
  background: #2A2A30;
  border-radius: 3px;
}

.table-container::-webkit-scrollbar-thumb:hover {
  background: #3A3A40;
}

/* 年份分区 */
.year-section {
  margin-bottom: 32px;
}

.year-section:last-child {
  margin-bottom: 0;
}

.year-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.year-badge {
  padding: 8px 20px;
  background: linear-gradient(135deg, #1A1A20 0%, #141418 100%);
  border: 1px solid #2A2A35;
  border-radius: 24px;
  font-size: 15px;
  font-weight: 700;
  color: #FFF;
  letter-spacing: 1px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.year-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, #2A2A35 0%, transparent 100%);
}

/* 维度卡片网格 */
.dimensions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.dimension-card {
  background: linear-gradient(160deg, #12121A 0%, #0C0C10 100%);
  border: 1px solid #1F1F28;
  border-radius: 12px;
  padding: 16px;
  transition: all 0.3s ease;
}

.dimension-card:hover {
  border-color: #2A2A38;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  transform: translateY(-2px);
}

.dim-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 12px;
  margin-bottom: 12px;
  border-bottom: 1px solid #1A1A25;
}

.dim-icon {
  font-size: 20px;
}

.dim-name {
  font-size: 15px;
  font-weight: 600;
  color: #EEE;
}

/* 洞察分组 */
.insight-group {
  margin-bottom: 16px;
}

.insight-group:last-child {
  margin-bottom: 0;
}

.group-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #777;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.label-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.label-dot.consensus {
  background: linear-gradient(135deg, #FFD700, #FFC107);
  box-shadow: 0 0 8px rgba(255, 215, 0, 0.5);
}

.label-dot.unique {
  background: linear-gradient(135deg, #29B6F6, #03A9F4);
  box-shadow: 0 0 8px rgba(41, 182, 246, 0.5);
}

.label-dot.variable {
  background: linear-gradient(135deg, #FF5252, #F44336);
  box-shadow: 0 0 8px rgba(255, 82, 82, 0.5);
}

/* 洞察项目 */
.insight-item {
  margin-bottom: 8px;
  background: rgba(20, 20, 28, 0.5);
  border-radius: 8px;
  border: 1px solid #1A1A25;
  overflow: hidden;
  transition: all 0.2s ease;
}

.insight-item:hover {
  border-color: #2A2A38;
  background: rgba(25, 25, 35, 0.6);
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  cursor: pointer;
  user-select: none;
}

.item-title {
  font-size: 14px;
  font-weight: 500;
  color: #DDD;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-title.unique-title {
  color: #29B6F6;
}

.item-title.variable-title {
  color: #FF5252;
}

.item-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.impact-badge {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}

.impact-badge.high {
  background: rgba(255, 215, 0, 0.15);
  color: #FFD700;
  border: 1px solid rgba(255, 215, 0, 0.3);
}

.impact-badge.medium {
  background: rgba(41, 182, 246, 0.15);
  color: #29B6F6;
  border: 1px solid rgba(41, 182, 246, 0.3);
}

.impact-badge.warning {
  background: rgba(255, 82, 82, 0.15);
  color: #FF5252;
  border: 1px solid rgba(255, 82, 82, 0.3);
}

.expand-icon {
  font-size: 10px;
  color: #555;
  transition: transform 0.2s ease;
}

/* 展开的详细内容 */
.item-detail {
  padding: 0 14px 14px;
  border-top: 1px solid #1A1A25;
  background: rgba(15, 15, 22, 0.5);
}

.item-detail.variable-detail {
  background: rgba(255, 82, 82, 0.03);
  border-top-color: rgba(255, 82, 82, 0.15);
}

.detail-text {
  font-size: 13px;
  line-height: 1.7;
  color: #AAA;
  margin: 12px 0 8px;
}

.detail-source {
  display: block;
  font-size: 12px;
  color: #666;
  font-style: italic;
  text-align: right;
}

.empty-dim {
  text-align: center;
  color: #555;
  font-size: 13px;
  padding: 20px;
  font-style: italic;
}

/* 展开动画 */
.slide-enter-active {
  transition: all 0.25s ease-out;
}

.slide-leave-active {
  transition: all 0.2s ease-in;
}

.slide-enter-from {
  opacity: 0;
  max-height: 0;
  transform: translateY(-8px);
}

.slide-leave-to {
  opacity: 0;
  max-height: 0;
}

.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 500px;
}
</style>
