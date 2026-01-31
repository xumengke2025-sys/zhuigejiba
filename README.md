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

- **后端**：Python 3.11+, Flask, Flask-CORS, OpenAI SDK, CAMEL-AI, CAMEL-OASIS, Pydantic
- **前端**：Vue 3 (Composition API), Vite, D3.js, Axios, Marked, Vue Router
- **模型**：支持 DeepSeek, GPT-4o, Qwen 等主流大模型接口 (需支持 OpenAI 兼容格式)

---
系统截图


<img width="666" height="546" alt="2848dbb24ab6ff44e8f10d5315308728" src="https://github.com/user-attachments/assets/045cbc17-be56-4e9a-95a1-290a3ce329ff" />
<img width="663" height="1152" alt="ab3e3a9146fdeae8efdc971acf058143" src="https://github.com/user-attachments/assets/67aca780-1842-47b7-86a9-1780a7688129" />
<img width="894" height="456" alt="733cf9b69ee708bebe59377045d649fc" src="https://github.com/user-attachments/assets/287a7d9d-c8d7-4bac-93fe-ff06dedac823" />
<img width="996" height="1065" alt="ba117ef3f7755dbb473a0339ec7fad19" src="https://github.com/user-attachments/assets/2baa08bf-0964-40d8-a68b-1354020dbe8b" />
<img width="1422" height="882" alt="d2841566d33b8f86ba002e8ec28dd4ac" src="https://github.com/user-attachments/assets/f08c4f44-67a0-403d-b79a-b6a955021637" />
<img width="1509" height="1059" alt="440c401c492e7f9b7e4b45f468326e5b" src="https://github.com/user-attachments/assets/e8f6a51c-8135-4456-b2d3-a07cd38aaf8d" />

### **🚀 快速开始 (仅需两步)**

#### **1. 一键安装环境**
在项目根目录下执行以下指令，系统将自动完成前后端所有依赖的安装（包括虚拟环境）：
```bash
npm run setup
```

#### **2. 一键启动服务**
配置好 `.env` 环境变量后，执行以下指令即可同时启动后端和前端：
```bash
npm run dev
```

---

### **详细安装步骤**

#### **1. 克隆项目**
```bash
git clone https://github.com/xumengke2025-sys/wannian-.git
cd wannian-
```

#### **2. 配置环境变量 (关键)**
将根目录下的 `.env.example` 重命名为 `.env`，并填入你的 API Key。**如果没有此文件，后端将无法启动。**

---

### **❓ 常见问题**

**Q: 启动后显示 `http proxy error: /api/...` 或 `ECONNREFUSED`？**
**A:** 这通常是因为后端服务没有成功启动。请检查：
1. 根目录下是否存在 `.env` 文件。
2. `.env` 文件中是否填写了有效的 `LLM_API_KEY`。
3. 检查终端输出，看 `backend` 进程是否报错退出。

---

### **技术栈**
1. 进入首页，输入姓名、出生日期、时间及地点。
2. 点击“开始推演”，系统将启动分布式 Agent 进行实时分析。
3. 查看自动生成的“命理推演报告”，包括大师会诊记录、年度运势详情及命理雷达图。

---

> **免责声明**：本项目推演结论基于 AI 模拟，仅供娱乐参考，请理性对待，切勿过度迷信。
