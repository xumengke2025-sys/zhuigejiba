# **万年 (Wannian) - AI 命理分布式推演系统**

**万年** 是一款基于大语言模型（LLM）驱动的分布式命理分析系统。它模拟了 49 位来自东西方不同流派的命理大师，针对用户的生辰八字进行全方位的“会诊”推演，提供涵盖事业、财富、情感、健康四大维度的深度年度报告。

---

### **项目核心功能**

- **49 位命理大师集群**：内置子平八字、紫微斗数、奇门遁甲、占星术、塔罗牌等 49 个独立 Agent，每个 Agent 都有独特的专业背景、逻辑流派和语言风格。
- **分布式 Agent 协作推演**：利用 camel-ai 框架实现多 Agent 协同，模拟真实的大师会诊场景，对多方观点进行整合。
- **四大维度深度解析**：针对每一年的运势，从 **事业 (Career)**、**财富 (Wealth)**、**情感 (Emotion)**、**健康 (Health)** 四个核心维度进行结构化推演。
- **可视化命理雷达**：前端采用 Vue 3 和 D3.js 技术，将抽象的命理数据转化为直观的雷达图和可视化图表。
- **多年份未来预测**：支持自定义推演年限（如未来 3-10 年），生成详尽的年度运势报告及针对性的生活建议。

---

### **技术栈**

- **后端**：Python 3.10+, Flask, OpenAI SDK, camel-ai, Pydantic
- **前端**：Vue 3, Vite, D3.js, Axios, Tailwind CSS
- **模型**：支持 DeepSeek、GPT-4o、Qwen 等主流大模型接口

---

### **安装方法**

#### **1. 克隆项目**
```bash
git clone https://github.com/xumengke2025-sys/wannian-.git
cd wannian-
```

#### **2. 后端环境配置**
```bash
cd backend
# 建议使用虚拟环境
python -m venv venv
source venv/bin/activate  # Windows 使用 venv\Scripts\activate
pip install -r requirements.txt
```

#### **3. 前端环境配置**
```bash
cd ../frontend
npm install
```

---

### **启动方法**

#### **1. 配置环境变量**
在项目根目录下，将 `.env.example` 重命名为 `.env`，并填入你的 API Key：
- `LLM_API_KEY`: 你的大模型 API 密钥
- `LLM_BASE_URL`: API 接口地址
- `ZEP_API_KEY`: (可选) 用于记忆图谱存储

#### **2. 启动后端服务**
```bash
cd backend
python run.py
```
默认运行在 `http://localhost:5002`

#### **3. 启动前端服务**
```bash
cd frontend
npm run dev
```
访问 `http://localhost:5173` 即可开始使用。

---

### **快速预览**
1. 进入首页，输入姓名、出生日期、时间及地点。
2. 点击“开始推演”，系统将启动分布式 Agent 进行实时分析。
3. 查看自动生成的“命理推演报告”，包括大师会诊记录、年度运势详情及命理雷达图。

---

> **免责声明**：本项目推演结论基于 AI 模拟，仅供娱乐参考，请理性对待，切勿过度迷信。
