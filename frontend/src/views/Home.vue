<template>
  <div class="home-container">
    <!-- 顶部导航栏 -->
    <nav class="navbar">
      <div class="nav-brand">WANNIAN / 万年</div>
      <div class="nav-links">
        <router-link to="/fortune" class="fortune-link">
          进入推演试验场 <span class="badge">BETA</span>
        </router-link>
      </div>
    </nav>

    <div class="main-content">
      <!-- Hero 区域 -->
      <section class="hero-section">
        <div class="hero-left">
          <div class="tag-row">
            <span class="blue-tag">专业级命理轨迹预测引擎</span>
            <span class="version-text">/ V1.0-Wannian</span>
          </div>
          
          <h1 class="main-title">
            聚合 49 位大师<br>
            <span class="gradient-text">洞察人生演化轨迹</span>
          </h1>
          
          <div class="hero-desc">
            <p>
              <span class="highlight-bold">万年</span> 基于 49 位跨越时空与流派的命理大师 Agent，全自动构建人生逻辑平行世界。通过多维视角深度推演，在复杂的命运博弈中寻找最优<span class="highlight-code">"人生决策路径"</span>
            </p>
            <p class="slogan-text">
              让演化在推演中清晰，让决策在终局前预知<span class="blinking-cursor">_</span>
            </p>
          </div>
          
          <div class="cta-row">
            <button class="primary-btn" @click="router.push('/fortune')">
              开启 49 位大师并行推演
            </button>
          </div>
        </div>
        
        <div class="hero-right">
          <div class="logo-container">
            <div class="brand-logo-placeholder">万年</div>
          </div>
        </div>
      </section>

      <!-- 核心特点 -->
      <section class="features-section">
        <div class="feature-card">
          <div class="feature-icon">⚡</div>
          <h3>49 位大师并行</h3>
          <p>整合子平八字、紫微斗数、古典占星等 49 种核心命理流派。</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">📊</div>
          <h3>命运总结官</h3>
          <p>智能聚合推演报告，识别核心共识与命理变数，提供三维人生建议。</p>
        </div>
        <div class="feature-card">
          <div class="feature-icon">🕸️</div>
          <h3>人生推演图谱</h3>
          <p>将推演结果存入 Neo4j 知识图谱，可视化呈现未来人生轨迹。</p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<style scoped>
.home-container {
  min-height: 100vh;
  background: #0A0A0B;
  color: #E0E0E0;
  font-family: 'Space Grotesk', -apple-system, sans-serif;
}

.navbar {
  height: 64px;
  padding: 0 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #1F1F22;
  background: rgba(13, 13, 15, 0.8);
  backdrop-filter: blur(10px);
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 20px;
  letter-spacing: 2px;
  color: #FFF;
}

.nav-links .fortune-link {
  color: #FFF;
  text-decoration: none;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border: 1px solid #2A2A2F;
  border-radius: 20px;
  transition: all 0.2s;
}

.nav-links .fortune-link:hover {
  background: #1A1A1D;
  border-color: #FFF;
}

.badge {
  font-size: 10px;
  background: #FFF;
  color: #000;
  padding: 2px 6px;
  border-radius: 4px;
}

.main-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 80px 40px;
}

.hero-section {
  display: flex;
  align-items: center;
  gap: 60px;
  margin-bottom: 100px;
}

.hero-left {
  flex: 1;
}

.tag-row {
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.blue-tag {
  background: rgba(33, 150, 243, 0.1);
  color: #2196F3;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
  border: 1px solid rgba(33, 150, 243, 0.2);
}

.version-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #666;
}

.main-title {
  font-size: 56px;
  font-weight: 800;
  line-height: 1.1;
  margin-bottom: 32px;
  color: #FFF;
}

.gradient-text {
  background: linear-gradient(90deg, #FFF, #666);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.hero-desc {
  font-size: 18px;
  line-height: 1.6;
  color: #888;
  margin-bottom: 40px;
}

.highlight-bold { color: #FFF; font-weight: 700; }
.highlight-code { font-family: 'JetBrains Mono', monospace; color: #FFF; background: #1A1A1D; padding: 2px 6px; border-radius: 4px; }

.slogan-text {
  margin-top: 20px;
  font-style: italic;
}

.blinking-cursor {
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  from, to { color: transparent; }
  50% { color: #FFF; }
}

.cta-row {
  display: flex;
  gap: 20px;
}

.primary-btn {
  background: #FFF;
  color: #000;
  padding: 16px 32px;
  border-radius: 8px;
  font-weight: 700;
  font-size: 16px;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
}

.primary-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 20px rgba(255, 255, 255, 0.1);
}

.hero-right {
  flex: 0.8;
  display: flex;
  justify-content: center;
}

.logo-container {
  width: 300px;
  height: 300px;
  background: linear-gradient(135deg, #1A1A1D 0%, #0D0D0F 100%);
  border: 1px solid #1F1F22;
  border-radius: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.brand-logo-placeholder {
  font-size: 48px;
  font-weight: 900;
  letter-spacing: 8px;
  color: #FFF;
  opacity: 0.8;
}

.features-section {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 32px;
}

.feature-card {
  background: #0D0D0F;
  border: 1px solid #1F1F22;
  padding: 32px;
  border-radius: 16px;
  transition: all 0.2s;
}

.feature-card:hover {
  border-color: #3A3A3F;
  transform: translateY(-4px);
}

.feature-icon {
  font-size: 32px;
  margin-bottom: 20px;
}

.feature-card h3 {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 16px;
  color: #FFF;
}

.feature-card p {
  font-size: 14px;
  line-height: 1.6;
  color: #888;
}
</style>
