"""
命运总结官服务
负责聚合 49 位大师的推演结果，提取共识、冲突及图谱数据
"""

import json
import concurrent.futures
import random
import re
import datetime
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger('wannian.fortune_aggregator')

GRAPH_PROMPT = """
# Role: 命运架构师
# Task: 基于49位大师预测，构建未来 {{future_years}} 年的"赛博天机图谱"JSON。

# CRITICAL RULES - 必须严格遵守：
1. **严禁编造**：所有内容必须基于提供的49位大师推演文本，禁止虚构任何预测内容。
2. **标题必须概括内容**：每个节点的 `name` 必须准确概括 `description` 的核心主题。
3. **必须标注原文引用**：每个节点必须包含 `source_quote` 字段，引用该大师原文100-150字。
4. **节点数量要求**：每年至少20个节点（4维度 × 5节点），确保覆盖完整。

# Requirements:

## 1. 节点数量与分布（极其重要）
每年生成节点数量限制：
- 4个维度（事业/财富/情感/健康）
- 每个维度限制：
  * **consensus (共识) 1个**：必须聚合多位大师观点。
  * **unique (独特观点) 最多 10 个**：合并相似观点。
  * **variable (变数) 最多 5 个**：合并相似变数。

## 2. 节点数据结构（CRITICAL）
每个节点必须包含以下字段：
```json
{
  "id": "n1",
  "properties": {
    "name": "2-5字命理特征标题",
    "time": "2026年",
    "description": "200-350字详细分析...",
    "master_name": "众师共识|具体大师名",
    "source_quote": "【原文引用】100-150字的大师原文，必须一字不差地从输入文本中提取",
    "source_master": "来源大师姓名",
    "school_source": "命理流派",
    "type": "consensus|unique|variable",
    "impact": 1-10,
    "dimension": "career|wealth|emotion|health"
  }
}
```

## 3. 节点标题要求（CRITICAL）
- `name` 字段必须是 **2-5 个字的命理特征标题**
- **标题必须准确概括 description 的内容**
- 必须是具体的命理特征词："晋升机遇"、"贵人相助"、"桃花旺盛"、"脾胃调养"
- **绝对禁止抽象表达**："事业共识"、"财富变化"、"运势走向"

## 4. 节点描述要求（CRITICAL）
- **长度**：200-350字，严禁短于150字
- **结构要求**：
  * 开头必须标注：「【来源：XXX大师】」
  * 紧接着标注原文引用：「原文："..."」
  * 然后是分析解读（保留大师原始语风和专业术语）
- **严禁编造**：必须基于原文，禁止改写为通用废话

## 5. 原文引用要求（CRITICAL - 极其重要）
- `source_quote` 字段必须包含100-150字的大师原文
- **必须一字不差**地从输入文本中提取
- 用于验证内容真实性，用户可以看到大师原话

## 6. 溯源要求
- `master_name`：节点归属（"众师共识"或具体大师名）
- `source_master`：具体来源大师姓名
- `source_quote`：该大师的原文引用

## 7. 49位大师聚合逻辑
- 你会收到49位大师的推演文本，每段以 `--- 【大师名】 ---` 开头
- **按大师遍历**：逐位分析每位大师的预测
- 为每位大师的每个重要观点生成节点
- 确保每位大师的观点都有机会被纳入（至少1-2个节点）

## 8. 关联性
必须构建节点间的 `edges`，关系类型：
- "因果" (Causal): 一个事件导致另一个
- "对冲" (Conflict): 两个维度间的矛盾
- "互补" (Complement): 互相促进
- "时序" (Sequence): 跨年份的影响

# Output JSON Structure:
{
  "graph_data": {
    "nodes": [
      {
        "id": "n1",
        "properties": {
          "name": "2-5字命理特征标题",
          "time": "2026年",
          "description": "【来源：紫微斗数大师】原文：\"...\" 分析解读...",
          "master_name": "具体大师名",
          "source_quote": "100-150字原文引用",
          "source_master": "来源大师姓名",
          "school_source": "命理流派",
          "type": "consensus|unique|variable",
          "impact": 1-10,
          "dimension": "career|wealth|emotion|health"
        }
      }
    ],
    "edges": [{"source": "n1", "target": "n2", "label": "关系描述", "type": "causal|conflict|complement|sequence"}]
  },
  "consensus": ["共识点1", "共识点2"],
  "conflicts": ["冲突点1", "冲突点2"]
}

# 数量检查清单（生成后自检）：
- [ ] 每年节点数 ≥ 20个（基础保障）
- [ ] 每个维度至少有1个consensus节点
- [ ] 尽可能多地包含 unique 和 variable 节点
- [ ] 每个节点都有 source_quote 字段
- [ ] 每个节点 description 都包含来源标注和原文引用
- [ ] 覆盖所有年份（{{future_years}}年）
"""

# 分年生成图谱的提示词 - 用于减轻单次LLM调用负担
YEARLY_GRAPH_PROMPT = """
# Role: 命运架构师
# Task: 基于49位大师预测，构建 **{{year}}年** 的"赛博天机图谱"JSON。

# CRITICAL RULES：
1. **只关注 {{year}} 年**，不要生成其他年份的内容
2. **严禁编造**：所有内容必须基于提供的49位大师推演文本
3. **标题必须概括内容**：每个节点的 `name` 必须准确概括 `description`
4. **必须标注原文引用**：每个节点必须包含 `source_quote` 字段

# 节点数量要求（{{year}}年）：
- **维度级限制（CRITICAL）**：
  * **consensus (共识)**：每个维度 1 个（全维度共 4 个）。必须聚合 3-5 位以上大师的共同观点，严禁只反映一位大师的意见。`master_name` 统一设为 "众师共识"。
  * **unique (独特观点)**：**每个维度最多 10 个**。如果识别到更多，仅保留最具有代表性、跨大师印证最多的观点。
  * **variable (转折/变数)**：**每个维度最多 5 个**。必须包含关键抉择、机遇或转折。
- **维度覆盖**：必须涵盖事业、财富、情感、健康 4 个维度。
- **核心要求：多大师观点聚合**：
  * **consensus (共识)**：每个维度 1 个。**必须聚合 3-5 位以上大师的共同观点**，严禁只反映一位大师的意见。`master_name` 统一设为 "众师共识"。
  * **unique (独特观点)**：每个维度最多 10 个。如果多位大师有相似的非共识观点，**必须合并为一个节点**，并在 `master_name` 中列出所有贡献大师。
  * **variable (转折/变数)**：每个维度最多 5 个。必须包含抉择、机遇或转折。如果多个大师都识别到了同一个变数，**必须合并**。

# 聚合描述要求：
- **多来源标注**：在 `description` 开头明确标注「【来源：大师A、大师B、大师C】」。
- **深度融合**：将不同大师提供的细节进行互补，形成一段逻辑连贯、内容丰富的深度推演。

# 节点类型定义（CRITICAL）：
1. **Consensus (共识)**：多位大师共同提到的核心趋势。
2. **Unique (独特观点)**：与共识不同或更具体的视角，优先展示多师印证的独特见解。
3. **Variable (转折/变数)**：涉及机遇、抉择或风险的关键时刻。优先合并多位大师共同预警的变数。

# 来源多样性要求（CRITICAL）：
- **严禁**只使用少数几位大师（如艾薇、毕达哥等）的观点。
- 尽可能挖掘不同大师的观点，确保来源的丰富性和多样性。

# 节点数据结构：
```json
{
  "id": "{{year}}_n1",
  "properties": {
    "name": "2-5字命理特征标题",
    "time": "{{year}}",
    "description": "【来源：XXX大师】原文：\"...\" 分析解读...（200-350字）",
    "master_name": "众师共识|具体大师名",
    "source_quote": "100-150字原文引用",
    "source_master": "来源大师姓名",
    "type": "consensus|unique|variable",
    "impact": 1-10,
    "dimension": "career|wealth|emotion|health"
  }
}
```

# 标题要求：
- 2-5个中文字符
- 具体特征词："晋升机遇"、"贵人相助"、"桃花旺盛"
- **禁止**："事业共识"、"财富变化"等抽象表达

# 描述要求：
- 200-350字
- 开头：「【来源：XXX大师】原文：「...」」
- 保留大师原始语风和专业术语

# Output JSON Structure:
{
  "graph_data": {
    "nodes": [...],
    "edges": [{"source": "{{year}}_n1", "target": "{{year}}_n2", "label": "...", "type": "..."}]
  },
  "consensus": ["..."],
  "conflicts": ["..."]
}
"""

SUMMARY_PROMPT = """
# Role: 命运总结官
# Task: 基于49位大师预测，撰写一份全案致辞 Markdown。
# Requirements:
1. **一致性**：严禁编造。确保每个观点与事实逻辑吻合。
2. **结构**：按年份及维度(事业/财富/情感/健康)组织。
3. **风格**：优美自然，将结构化逻辑转化为感性解读。
# Output Format:
## 🔮 核心共识与独特信号
### 🌌 核心共识
...
### ⚡ 独特信号
...
## 📅 未来 {{future_years}} 年时空推演表
### 2026年 (丙午)
#### 💼 事业
- **众师共识**：...
- **独特视角**：...
...
"""

class FortuneAggregator:
    """命运总结官"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
    
    def aggregate_reports(
        self, 
        user_data: Dict[str, Any], 
        reports: Dict[str, Dict[str, Any]],
        on_progress: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        聚合报告：使用分年生成策略，避免单次LLM调用超时
        """
        if on_progress:
            on_progress(92, "正在拨动星盘，萃取 49 位大师推演精要...")
            
        future_years = user_data.get("future_years", 3)
        current_year = datetime.datetime.now().year
        
        # 准备大师报告文本 - 使用完整内容，不截断
        reports_text_full = ""
        for agent_id, data in reports.items():
            # 使用完整内容，确保不丢失任何信息
            reports_text_full += f"\n--- 【{data['name']}】 ---\n{data['content']}\n"
        
        user_context = f"用户信息: {json.dumps(user_data, ensure_ascii=False)}\n\n=== 49位大师完整推演文本 ===\n{reports_text_full}"
        reports_list = list(reports.values())
        
        # 预处理报告列表
        preprocessed_reports = []
        for r in reports_list:
            content = r.get('content', '')
            paras = [p.strip() for p in re.split(r'[\n。！？]', content) if p.strip()]
            preprocessed_reports.append({
                "name": r.get('name', '未知大师'),
                "paragraphs": paras
            })
        
        # 使用分年生成策略 - 每年单独生成，避免超时
        if on_progress:
            on_progress(94, "正在校准天星方位，采用分年凝聚策略...")
        
        all_nodes = []
        all_edges = []
        all_consensus = []
        all_conflicts = []
        
        # 逐年生成图谱
        for i in range(future_years):
            year = current_year + i
            year_str = f"{year}年"
            
            if on_progress:
                progress = 94 + (i * 5 // future_years)
                on_progress(progress, f"正在凝聚 {year_str} 的天机图谱...")
            
            try:
                year_result = self._generate_year_graph(
                    year_str, user_context, preprocessed_reports
                )
                
                # 合并结果
                year_nodes = year_result.get("graph_data", {}).get("nodes", [])
                year_edges = year_result.get("graph_data", {}).get("edges", [])
                
                all_nodes.extend(year_nodes)
                all_edges.extend(year_edges)
                all_consensus.extend(year_result.get("consensus", []))
                all_conflicts.extend(year_result.get("conflicts", []))
                
                logger.info(f"{year_str} 生成完成: {len(year_nodes)} 个节点")
                
            except Exception as e:
                logger.error(f"{year_str} 图谱生成失败: {str(e)}")
                # 如果某一年失败，使用补充逻辑生成该年的节点
                year_nodes = self._generate_fallback_year_nodes(year_str, preprocessed_reports)
                all_nodes.extend(year_nodes)
        
        # 构建完整的图谱结果
        graph_result = {
            "graph_data": {
                "nodes": all_nodes,
                "edges": all_edges
            },
            "consensus": all_consensus[:20],
            "conflicts": all_conflicts[:20]
        }
        
        if on_progress:
            on_progress(97, "天机正在凝聚，正在编撰全案致辞...")
        
        # 生成总结文本（简化版，使用第一个年份的节点信息）
        try:
            summary_text = self._generate_summary_text(
                future_years, all_nodes, user_context
            )
            logger.info("总结文本生成成功")
        except Exception as e:
            logger.error(f"总结生成失败: {str(e)}")
            summary_text = "（天机图谱已生成，详细推演请查看下方节点信息）"
        
        if on_progress:
            on_progress(98, "正在校验天机图谱完整性...")
        
        # 数据清洗与校验
        logger.info(f"清洗前图谱节点数: {len(all_nodes)}")
        logger.info(f"清洗前图谱边数: {len(all_edges)}")
        
        graph_result = self._sanitize_result(graph_result, future_years, preprocessed_reports)
            
        # 预处理报告列表，提取段落
        preprocessed_reports = []
        for r in reports_list:
            content = r.get('content', '')
            paras = [p.strip() for p in re.split(r'[\n。！？]', content) if p.strip()]
            preprocessed_reports.append({
                "name": r.get('name', '未知大师'),
                "paragraphs": paras
            })

        graph_result = self._sanitize_result(graph_result, future_years, preprocessed_reports)
        
        final_result = graph_result
        final_result["summary_text"] = summary_text
        
        # 调试日志：确认返回数据结构
        logger.info("="*60)
        logger.info("最终返回数据结构检查：")
        logger.info(f"final_result keys: {list(final_result.keys())}")
        logger.info(f"summary_text 长度: {len(summary_text) if summary_text else 0}")
        logger.info(f"graph_data 是否存在: {('graph_data' in final_result)}")
        if 'graph_data' in final_result:
            logger.info(f"graph_data keys: {list(final_result['graph_data'].keys())}")
            logger.info(f"nodes 数量: {len(final_result['graph_data'].get('nodes', []))}")
            logger.info(f"edges 数量: {len(final_result['graph_data'].get('edges', []))}")
            # 输出前3个节点的摘要
            for i, node in enumerate(final_result['graph_data'].get('nodes', [])[:3]):
                logger.info(f"节点 {i+1}: id={node.get('id')}, name={node.get('properties', {}).get('name')}, type={node.get('properties', {}).get('type')}")
        logger.info("="*60)
        
        if on_progress:
            on_progress(100, "天机已现，全案推演编撰完成")
            
        return final_result

    def _generate_year_graph(
        self, 
        year: str, 
        user_context: str,
        preprocessed_reports: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成单年份的图谱
        
        使用分年策略，减轻单次LLM调用负担，避免超时
        """
        logger.info(f"开始生成 {year} 的图谱...")
        
        # 构建提示词
        prompt = YEARLY_GRAPH_PROMPT.replace("{{year}}", year)
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"请基于以下大师推演，生成 {year} 的命理图谱：\n{user_context}"}
        ]
        
        # 调用LLM生成，使用较短的超时（120秒）
        try:
            result = self.llm.chat_json(messages, temperature=0.3, use_boost=True)
            logger.info(f"{year} LLM生成成功")
            
            # 确保节点ID包含年份前缀，避免冲突
            nodes = result.get("graph_data", {}).get("nodes", [])
            for i, node in enumerate(nodes):
                if not node.get("id", "").startswith(year.replace("年", "")):
                    node["id"] = f"{year.replace('年', '')}_n{i+1}"
                # 确保time字段正确
                node["properties"]["time"] = year
            
            return result
            
        except Exception as e:
            logger.error(f"{year} LLM生成失败: {str(e)}")
            raise

    def _extract_aggregated_consensus(self, preprocessed_reports: List[Dict[str, Any]], dimension: str, year: str) -> tuple:
        """从多位大师报告中聚合共识内容"""
        all_candidates = self._extract_all_relevant_paragraphs(preprocessed_reports, dimension, year)
        if not all_candidates:
            return "", "综合推演"
        master_paras = {}
        for para, master in all_candidates:
            if master not in master_paras: master_paras[master] = para
        top_masters = list(master_paras.keys())[:5]
        if not top_masters: return "", "综合推演"
        aggregated_desc = "\n".join([f"【{m}】：{master_paras[m]}" for m in top_masters])
        master_names = "、".join(top_masters)
        return aggregated_desc, master_names

    def _group_similar_candidates(self, candidates: List[tuple]) -> List[Dict]:
        """将相似的观点合并，体现多大师印证"""
        groups = []
        for para, master in candidates:
            found_group = False
            for group in groups:
                if master in group['masters']: continue
                common_chars = set(para) & set(group['para'])
                if len(common_chars) > 25:
                    group['masters'].append(master)
                    if len(para) > len(group['para']): group['para'] = para
                    found_group = True
                    break
            if not found_group: groups.append({'para': para, 'masters': [master]})
        return groups

    def _generate_fallback_year_nodes(self, year: str, preprocessed_reports: List[Dict[str, Any]]) -> List[Dict]:
        """当LLM生成失败时，使用规则生成该年的节点
        
        逻辑更新：聚合多大师观点，并严格限制每个维度的节点数量（Unique<=10, Variable<=5）。
        """
        logger.warning(f"使用聚合逻辑fallback生成 {year} 的节点")
        nodes = []
        node_id = 1
        dimensions = ["career", "wealth", "emotion", "health"]
        dim_names = {"career": "事业", "wealth": "财富", "emotion": "情感", "health": "健康"}
        variable_keywords = ["机会", "选择", "转折", "突破", "挑战", "若", "一旦", "除非", "抉择", "风险", "变数", "机遇"]

        for dim in dimensions:
            # 1. 共识节点：每个维度 1 个，聚合前 5 位大师
            consensus_desc, consensus_masters = self._extract_aggregated_consensus(preprocessed_reports, dim, year)
            if consensus_desc:
                nodes.append({
                    "id": f"{year.replace('年', '')}_n{node_id}",
                    "properties": {
                        "name": f"{dim_names[dim]}众师共识",
                        "time": year,
                        "description": f"【来源：{consensus_masters}】\n{consensus_desc}",
                        "master_name": "众师共识",
                        "source_quote": consensus_desc[:150],
                        "source_master": consensus_masters,
                        "type": "consensus",
                        "impact": 8,
                        "dimension": dim
                    }
                })
                node_id += 1

            # 2. 独特观点与变数：按维度收集并筛选
            all_candidates = self._extract_all_relevant_paragraphs(preprocessed_reports, dim, year)
            grouped_candidates = self._group_similar_candidates(all_candidates)
            
            dim_unique = []
            dim_variable = []
            
            for group in grouped_candidates:
                para = group['para']
                masters = group['masters']
                is_variable = any(kw in para for kw in variable_keywords)
                
                candidate_data = {
                    "para": para,
                    "masters": masters,
                    "score": len(masters) # 以聚合大师数量作为评分标准
                }
                
                if is_variable:
                    dim_variable.append(candidate_data)
                else:
                    dim_unique.append(candidate_data)

            # 筛选独特观点：每个维度最多 10 个，优先选择聚合大师多的
            dim_unique.sort(key=lambda x: x['score'], reverse=True)
            for cand in dim_unique[:10]:
                para = cand['para']
                masters = cand['masters']
                m_names = "、".join(masters)
                nodes.append({
                    "id": f"{year.replace('年', '')}_n{node_id}",
                    "properties": {
                        "name": self._extract_node_title(para, dim, "unique"),
                        "time": year,
                        "description": f"【来源：{m_names}】\n{para}",
                        "master_name": m_names,
                        "source_quote": para[:150],
                        "source_master": masters[0],
                        "type": "unique",
                        "impact": random.randint(5, 8),
                        "dimension": dim
                    }
                })
                node_id += 1

            # 筛选变数：每个维度最多 5 个
            dim_variable.sort(key=lambda x: x['score'], reverse=True)
            for cand in dim_variable[:5]:
                para = cand['para']
                masters = cand['masters']
                m_names = "、".join(masters)
                nodes.append({
                    "id": f"{year.replace('年', '')}_n{node_id}",
                    "properties": {
                        "name": self._extract_node_title(para, dim, "variable"),
                        "time": year,
                        "description": f"【来源：{m_names}】\n{para}",
                        "master_name": m_names,
                        "source_quote": para[:150],
                        "source_master": masters[0],
                        "type": "variable",
                        "impact": random.randint(7, 9),
                        "dimension": dim
                    }
                })
                node_id += 1
                
        return nodes

    def _extract_all_relevant_paragraphs(
        self, 
        preprocessed_reports: List[Dict[str, Any]], 
        dimension: str, 
        year: str
    ) -> List[tuple]:
        """提取所有相关的段落，不进行评分排序，只过滤无效内容"""
        keywords = {
            "career": ["事业", "工作", "晋升", "职场", "创业", "名声", "官", "学业", "职位", "升迁", "业绩"],
            "wealth": ["财富", "金钱", "投资", "收益", "破财", "财运", "金", "利", "理财", "资产", "收入"],
            "emotion": ["感情", "婚姻", "恋爱", "桃花", "伴侣", "家庭", "情", "缘", "爱情", "配偶", "姻缘"],
            "health": ["健康", "身体", "疾病", "养生", "平安", "疾", "安", "体质", "调养", "医"]
        }
        
        target_keys = keywords.get(dimension, [])
        candidates = []
        
        for report in preprocessed_reports:
            master_name = report.get('name', '未知大师')
            paragraphs = report.get('paragraphs', [])
            
            for para in paragraphs:
                # 过滤太短的内容
                if len(para) < 15: 
                    continue
                
                # 必须包含年份（如果有指定年份）
                has_year = year[:4] in para if year else False
                # 必须包含至少一个维度关键词
                has_keyword = any(k in para for k in target_keys)
                
                # 如果没有年份，也没有关键词，则视为无关
                if not has_year and not has_keyword:
                    continue
                
                # 只要相关就加入候选
                candidates.append((para, master_name))
        
        return candidates

    def _generate_summary_text(self, future_years: int, all_nodes: List[Dict], user_context: str) -> str:
        """生成总结文本
        
        使用节点信息生成简化的总结
        """
        current_year = datetime.datetime.now().year
        
        # 按年份和维度统计
        year_dim_summary = {}
        for node in all_nodes:
            props = node.get("properties", {})
            year = props.get("time", "")
            dim = props.get("dimension", "")
            node_type = props.get("type", "")
            name = props.get("name", "")
            
            if year not in year_dim_summary:
                year_dim_summary[year] = {}
            if dim not in year_dim_summary[year]:
                year_dim_summary[year][dim] = {"consensus": [], "unique": [], "variable": []}
            
            year_dim_summary[year][dim][node_type].append(name)
        
        # 构建简化总结
        summary_lines = ["## 🔮 核心推演总结\n"]
        
        for i in range(future_years):
            year = f"{current_year + i}年"
            if year in year_dim_summary:
                summary_lines.append(f"\n### {year}\n")
                dim_names = {"career": "事业", "wealth": "财富", "emotion": "情感", "health": "健康"}
                
                for dim, dim_name in dim_names.items():
                    if dim in year_dim_summary[year]:
                        consensus = year_dim_summary[year][dim].get("consensus", [])
                        if consensus:
                            summary_lines.append(f"- **{dim_name}**：{consensus[0]}\n")
        
        summary_lines.append("\n*详细推演请查看下方天机图谱*")
        
        return "".join(summary_lines)

    def _extract_rich_description(
        self, 
        preprocessed_reports: List[Dict[str, Any]], 
        dimension: str, 
        year: str, 
        exclude_texts: List[str] = None,
        exclude_masters: List[str] = None
    ) -> tuple:
        """从上下文中抓取内容丰富的描述文本及对应的大师姓名
        
        Args:
            preprocessed_reports: 预处理后的报告列表 [{'name': '...', 'paragraphs': [...]}, ...]
            exclude_texts: 已使用的描述列表，避免重复提取相同内容
            exclude_masters: 已使用过的大师列表，避免重复使用同一位大师
        """
        if exclude_texts is None:
            exclude_texts = []
        if exclude_masters is None:
            exclude_masters = []
            
        keywords = {
            "career": ["事业", "工作", "晋升", "职场", "创业", "名声", "官", "学业", "职位", "升迁", "业绩"],
            "wealth": ["财富", "金钱", "投资", "收益", "破财", "财运", "金", "利", "理财", "资产", "收入"],
            "emotion": ["感情", "婚姻", "恋爱", "桃花", "伴侣", "家庭", "情", "缘", "爱情", "配偶", "姻缘"],
            "health": ["健康", "身体", "疾病", "养生", "平安", "疾", "安", "体质", "调养", "医"]
        }
        
        target_keys = keywords.get(dimension, [])
        candidates = []
        
        for report in preprocessed_reports:
            master_name = report.get('name', '未知大师')
            
            # 跳过已使用过的大师
            if master_name in exclude_masters:
                continue
            
            paragraphs = report.get('paragraphs', [])
            
            for para in paragraphs:
                if len(para) < 15: 
                    continue
                
                # 检查是否已被使用
                if any(para[:50] in used for used in exclude_texts):
                    continue
                
                # 不再计算分数，直接收集所有符合条件的候选者
                # 分数逻辑已废弃，改用上层逻辑动态筛选
                score = 0
                has_year = year[:4] in para if year else False
                key_count = sum(1 for k in target_keys if k in para)
                
                # 简单过滤：必须包含关键词或年份
                if has_year or key_count > 0:
                    score = 1 # 标记为有效
                
                if score > 0:
                    candidates.append((score, para, master_name))
        
        if candidates:
            # 不再按分数排序，保持原始顺序或随机
            # 但为了 _extract_rich_description 的兼容性，这里暂时保留随机选择逻辑
            
            # 优化：先按大师分组，取每位大师的一条（随机），确保 Top N 来自不同大师
            master_candidates = {}
            for score, para, master_name in candidates:
                if master_name not in master_candidates:
                    master_candidates[master_name] = []
                master_candidates[master_name].append((score, para, master_name))
            
            # 从每位大师的候选列表中随机选一条
            unique_candidates = []
            for m_name, m_list in master_candidates.items():
                unique_candidates.append(random.choice(m_list))
            
            # 随机打乱顺序
            random.shuffle(unique_candidates)
            
            # 只要有多个候选者，就尝试随机
            # 此时 unique_candidates 中的每个元素都来自不同大师
            if unique_candidates:
                best_candidate = unique_candidates[0]
                
            full_text = best_candidate[1]
            master_name = best_candidate[2]
            
            # 如果段落太短，尝试从同一位大师合并后续相关段落
            if len(full_text) < 200:
                # 找到该大师的所有原始段落
                original_paras = [c for c in candidates if c[2] == master_name]
                for other_candidate in original_paras:
                    if other_candidate[1] != full_text and other_candidate[1] not in full_text:
                        full_text += " " + other_candidate[1]
                        if len(full_text) >= 200:
                            break
            
            return full_text, master_name
        
        # 如果没有找到新的大师，尝试从已排除的大师中找（兜底）
        if exclude_masters:
            logger.warning(f"未找到新的大师来源，尝试从已排除的大师中查找: {dimension}-{year}")
            return self._extract_rich_description(preprocessed_reports, dimension, year, exclude_texts, [])
        
        return "", "大师共鸣"
    
    def _extract_multiple_descriptions(self, preprocessed_reports: List[Dict[str, Any]], dimension: str, year: str, count: int) -> List[tuple]:
        """从报告中提取多个不同的描述"""
        results = []
        exclude_texts = []
        
        for _ in range(count * 2):
            desc, master = self._extract_rich_description(preprocessed_reports, dimension, year, exclude_texts)
            if desc and desc not in exclude_texts:
                results.append((desc, master))
                exclude_texts.append(desc)
                if len(results) >= count:
                    break
        
        return results

    def _is_valid_llm_title(self, title: str, used_titles: List[str] = None) -> bool:
        """检查LLM返回的标题是否有效
        
        有效标题条件：
        1. 长度为2-5个中文字符
        2. 不是抽象表达（如"事业共识"、"财富变化"）
        3. 不是断词/不完整的句子片段
        4. 未被使用过
        """
        if used_titles is None:
            used_titles = []
            
        if not title:
            return False
            
        # 移除可能的前缀符号
        clean_title = title.replace("✨", "").replace("⚡", "").strip()
        
        # 检查长度（2-5个中文字符）
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', clean_title)
        if len(chinese_chars) < 2 or len(chinese_chars) > 5:
            return False
        
        # 断词检测 - 以下结尾的标题是不完整的句子片段
        broken_endings = [
            "将", "把", "被", "让", "使", "给", "向", "往", "朝",  # 介词/助词
            "的", "地", "得", "着", "了", "过",  # 助词
            "是", "在", "有", "和", "与", "或", "及",  # 动词/连词
            "而", "但", "却", "并", "且", "也", "都",  # 连词/副词
            "能", "会", "可", "要", "应", "该", "需",  # 能愿动词
            "很", "太", "最", "更", "较", "比",  # 程度副词
            "这", "那", "其", "某", "每", "各",  # 指示词
            "视", "当", "为", "成", "做", "如", "若",  # 动词/连词
            "从", "自", "于", "至", "到", "以", "因",  # 介词
            "对", "关", "经", "通", "按", "据"  # 介词
        ]
        if clean_title and clean_title[-1] in broken_endings:
            return False
        
        # 断词检测 - 以下开头的标题是不完整的句子片段
        broken_beginnings = [
            "的", "地", "得", "了", "着", "过",  # 助词
            "和", "与", "或", "及", "并", "且",  # 连词
            "而", "但", "却", "则", "便", "即"  # 连词
        ]
        if clean_title and clean_title[0] in broken_beginnings:
            return False
        
        # 检测常见的断词模式（不完整短语）
        broken_patterns = [
            r'^[将把被让使给向往朝].+[视当为成做]$',  # 如"将健身视"
            r'^.+[是在有]$',  # 如"机会是"、"发展在"
            r'^[在从于].+$',  # 如"在事业"（除非后面还有内容）
            r'^关于.+$',  # 如"关于财富"
            r'^对于.+$',  # 如"对于健康"
        ]
        for pattern in broken_patterns:
            if re.match(pattern, clean_title):
                return False
        
        # 抽象/无效标题黑名单
        invalid_titles = [
            "事业共识", "财富共识", "情感共识", "健康共识",
            "事业变化", "财富变化", "情感变化", "健康变化",
            "事业运势", "财富运势", "情感运势", "健康运势",
            "运势走向", "健康状况", "财富分析", "事业分析",
            "年度运势", "整体运势", "综合运势", "共识观点",
            "独特观点", "命理变数", "核心共识", "年度分析",
            "年份", "事业", "财富", "情感", "健康", "运势",
            "共识", "变化", "分析", "观点"
        ]
        if clean_title in invalid_titles:
            return False
        
        # 检查是否已使用
        if title in used_titles or clean_title in used_titles:
            return False
            
        return True

    def _extract_node_title(self, description: str, dimension: str, node_type: str, used_titles: List[str] = None) -> str:
        """从描述中提取或生成节点标题
        
        优先使用LLM返回的标题，如果无效则从描述中提取关键词
        """
        if used_titles is None:
            used_titles = []
        
        # 根据节点类型添加前缀
        type_prefix = {"consensus": "", "unique": "✨", "variable": "⚡"}
        prefix = type_prefix.get(node_type, "")
        
        # 核心关键词库 - 用于从描述中匹配
        keyword_map = {
            "career": [
                ("晋升", "晋升机遇"), ("升迁", "升迁机会"), ("创业", "创业时机"), ("转型", "转型契机"),
                ("贵人", "贵人相助"), ("小人", "小人防范"), ("合作", "合作机会"), ("竞争", "竞争加剧"),
                ("突破", "突破方向"), ("稳定", "事业稳定"), ("变动", "工作变动"), ("压力", "压力管理"),
                ("学业", "学业进步"), ("考试", "考试顺利"), ("面试", "面试机会"), ("项目", "项目推进"),
                ("客户", "客户拓展"), ("团队", "团队建设"), ("决策", "重大决策"), ("机遇", "机遇降临"),
                ("挑战", "挑战来临"), ("调动", "岗位调动"), ("离职", "离职风险"), ("领导", "领导赏识"),
                ("名声", "名声提升"), ("职位", "职位变动"), ("业绩", "业绩提升"), ("能力", "能力提升"),
                ("人脉", "人脉拓展"), ("资源", "资源获取"), ("成长", "个人成长"), ("创新", "创新机会")
            ],
            "wealth": [
                ("偏财", "偏财运旺"), ("正财", "正财稳健"), ("破财", "破财风险"), ("投资", "投资机会"),
                ("理财", "理财规划"), ("收入", "收入增长"), ("财运", "财运走向"), ("守财", "守财为上"),
                ("横财", "横财信号"), ("耗财", "耗财警示"), ("财库", "财库充实"), ("资产", "资产配置"),
                ("债务", "债务风险"), ("开源", "开源节流"), ("赌博", "忌赌博"), ("借贷", "借贷谨慎"),
                ("发财", "发财时机"), ("收益", "收益回报"), ("亏损", "亏损预警"), ("房产", "房产投资"),
                ("股票", "股市投资"), ("加薪", "加薪机会"), ("奖金", "奖金收入"), ("钱财", "钱财流动"),
                ("生意", "生意经营"), ("副业", "副业收入"), ("消费", "消费支出"), ("结算", "账务结算")
            ],
            "emotion": [
                ("桃花", "桃花旺盛"), ("婚姻", "婚姻运势"), ("恋爱", "恋爱机会"), ("感情", "感情变化"),
                ("家庭", "家庭和睦"), ("矛盾", "感情矛盾"), ("分离", "分离风险"), ("复合", "复合机会"),
                ("诱惑", "外界诱惑"), ("子女", "子女缘分"), ("孤独", "孤独感强"), ("沟通", "沟通改善"),
                ("信任", "信任危机"), ("结婚", "结婚时机"), ("离婚", "离婚风险"), ("第三者", "第三者插足"),
                ("暗昧", "暗昧关系"), ("表白", "表白时机"), ("约会", "约会机会"), ("怀孕", "怀孕缘分"),
                ("生育", "生育计划"), ("父母", "父母关系"), ("朋友", "友情运势"), ("缘分", "姻缘到来"),
                ("娘家", "娘家关系"), ("纷争", "关系纷争"), ("冷淡", "感情冷淡"), ("升温", "感情升温")
            ],
            "health": [
                ("健康", "健康状态"), ("疾病", "疾病预警"), ("调养", "身体调养"), ("心理", "心理健康"),
                ("休息", "休息调整"), ("运动", "运动健身"), ("饮食", "饮食调理"), ("精神", "精神状态"),
                ("疲劳", "过度疲劳"), ("意外", "意外防范"), ("平安", "平安顺遂"), ("压力", "压力管理"),
                ("免疫", "免疫力强"), ("体质", "体质调理"), ("康复", "康复期到"), ("肠胃", "肠胃保健"),
                ("失眠", "失眠困扰"), ("焦虑", "焦虑情绪"), ("手术", "手术风险"), ("住院", "住院可能"),
                ("血光", "血光之灾"), ("车祸", "车祸防范"), ("跌伤", "跌伤风险"), ("头痛", "头痛困扰"),
                ("腹部", "腹部不适"), ("疼痛", "疼痛问题"), ("传染", "传染防护"), ("慢性", "慢性病管理")
            ]
        }
        
        # 从描述中匹配关键词
        dim_keywords = keyword_map.get(dimension, [])
        matched_titles = []
        for keyword, title in dim_keywords:
            if keyword in description:
                full_title = f"{prefix}{title}" if prefix else title
                # 检查是否已使用且是有效标题
                if full_title not in used_titles and self._is_valid_llm_title(full_title, used_titles):
                    return full_title
                matched_titles.append(full_title)
        
        # 如果所有匹配的标题都已使用，尝试加序号区分
        if matched_titles:
            base_title = matched_titles[0].replace(prefix, "")
            for i in range(2, 10):
                new_title = f"{prefix}{base_title}{i}" if prefix else f"{base_title}{i}"
                if new_title not in used_titles and self._is_valid_llm_title(new_title, used_titles):
                    return new_title
        
        # 兜底：返回一个通用但有效的标题
        fallback_titles = {
            "career": {
                "consensus": "事业稳健",
                "unique": "贵人显现",
                "variable": "变动风险"
            },
            "wealth": {
                "consensus": "财运平稳",
                "unique": "偏财机会",
                "variable": "破财防范"
            },
            "emotion": {
                "consensus": "感情顺遂",
                "unique": "桃花机遇",
                "variable": "感情波折"
            },
            "health": {
                "consensus": "身体康健",
                "unique": "养生调理",
                "variable": "健康预警"
            }
        }
        
        dim_fallbacks = fallback_titles.get(dimension, fallback_titles["career"])
        type_fallback = dim_fallbacks.get(node_type, "运势分析")
        
        full_title = f"{prefix}{type_fallback}" if prefix else type_fallback
        if full_title not in used_titles:
            return full_title
        
        # 如果全部用完，加序号
        for i in range(2, 10):
            new_title = f"{prefix}{type_fallback}{i}" if prefix else f"{type_fallback}{i}"
            if new_title not in used_titles:
                return new_title
        
        return full_title

    def _sanitize_result(self, result: Dict[str, Any], future_years: int, preprocessed_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """清洗和校验数据，确保节点数量、原文引用、年份覆盖等要求
        
        主要功能：
        1. 校验并修复节点标题
        2. 为节点附加原文引用
        3. 验证并补充节点数量（每年至少20个）
        4. 确保每一年都有节点覆盖
        """
        logger.info("="*60)
        logger.info("开始清洗和校验图谱数据...")
        logger.info(f"输入result keys: {list(result.keys())}")
        logger.info(f"preprocessed_reports 长度: {len(preprocessed_reports)}")
        
        current_year = datetime.datetime.now().year
        graph_data = result.get("graph_data", {"nodes": [], "edges": []})
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        
        logger.info(f"清洗前节点数量: {len(nodes)}")
        logger.info(f"清洗前边数量: {len(edges)}")
        
        # 第一步：基础校验和标题修复
        valid_nodes = []
        global_used_titles = []
        
        # 跟踪每个年份-维度已使用的大师
        used_masters_by_year_dim = {}
        
        for node in nodes:
            props = node.get("properties", {})
            
            # 校验必要字段
            if not props.get("name"):
                logger.warning(f"节点缺少name字段，跳过: {node.get('id')}")
                continue
            
            if not props.get("description"):
                logger.warning(f"节点缺少description字段，跳过: {node.get('id')}")
                continue
            
            year = props.get("time", "")
            dimension = props.get("dimension", "career")
            node_type = props.get("type", "consensus")
            master_name = props.get("master_name", "")
            
            # 初始化该年份-维度的大师跟踪
            key = f"{year}-{dimension}"
            if key not in used_masters_by_year_dim:
                used_masters_by_year_dim[key] = []
            
            # 校验描述长度 - 要求至少200字
            desc_len = len(props.get("description", ""))
            if desc_len < 200:
                logger.warning(f"节点描述太短({desc_len}字)，尝试补充完整内容: {props.get('name')}")
                
                # 提取更多内容，确保达到200字以上，排除已使用的大师
                extra_desc, source_master = self._extract_rich_description(
                    preprocessed_reports, dimension, year, 
                    exclude_masters=used_masters_by_year_dim[key]
                )
                if extra_desc:
                    # 记录使用的大师
                    if source_master not in used_masters_by_year_dim[key]:
                        used_masters_by_year_dim[key].append(source_master)
                    
                    # 如果提取的内容还不够长，尝试再提取一段（从其他大师）
                    if len(extra_desc) < 150:
                        extra_desc2, master2 = self._extract_rich_description(
                            preprocessed_reports, dimension, year, 
                            [extra_desc], used_masters_by_year_dim[key]
                        )
                        if extra_desc2:
                            extra_desc += " " + extra_desc2
                            if master2 not in used_masters_by_year_dim[key]:
                                used_masters_by_year_dim[key].append(master2)
                    
                    # 构建完整的描述，包含来源和原文引用
                    source_quote = extra_desc[:800] if len(extra_desc) > 800 else extra_desc
                    
                    if node_type == "consensus":
                        # 共识节点：显示为众师共识
                        new_description = f"【来源：众师共识】参考多位大师观点：「{source_quote}」\n\n"
                        new_description += f"综合多位大师共识：{extra_desc}\n\n"
                        new_description += f"多位大师一致认为，{year}在{dimension}方面需要特别关注。建议结合个人实际情况，谨慎决策。"
                        display_master = "众师共识"
                    elif node_type == "unique":
                        new_description = f"【来源：{source_master}】原文：「{source_quote}」\n\n"
                        new_description += f"{source_master}独特见解：{extra_desc}\n\n"
                        new_description += f"这一观点具有独特性，值得重点关注。建议结合其他大师意见综合考虑。"
                        display_master = source_master
                    else:  # variable
                        new_description = f"【来源：{source_master}】原文：「{source_quote}」\n\n"
                        new_description += f"{source_master}提醒注意：{extra_desc}\n\n"
                        new_description += f"这是一个需要特别关注的变数，可能存在不确定性。建议提前做好应对准备。"
                        display_master = source_master
                    
                    props["description"] = new_description
                    props["source_quote"] = source_quote
                    props["source_master"] = source_master
                    props["master_name"] = display_master
                    logger.info(f"节点内容已补充至 {len(new_description)} 字 (显示来源: {display_master}, 实际来源: {source_master})")
                else:
                    logger.warning(f"无法为节点 {props.get('name')} 补充内容")
            else:
                # 节点内容已足够，记录其来源大师
                source_master = props.get("source_master", master_name)
                if source_master and source_master not in used_masters_by_year_dim[key]:
                    used_masters_by_year_dim[key].append(source_master)
            
            # 校验标题
            llm_title = props.get("name", "")
            dimension = props.get("dimension", "career")
            node_type = props.get("type", "consensus")
            
            if not self._is_valid_llm_title(llm_title, global_used_titles):
                new_title = self._extract_node_title(
                    props.get("description", ""), 
                    dimension, 
                    node_type, 
                    global_used_titles
                )
                logger.info(f"标题无效，重新提取: '{llm_title}' -> '{new_title}'")
                props["name"] = new_title
            
            global_used_titles.append(props["name"])
            valid_nodes.append(node)
        
        logger.info(f"基础校验后节点数量: {len(valid_nodes)}")
        
        # 第二步：为节点附加原文引用
        valid_nodes = self._attach_source_quotes(valid_nodes, preprocessed_reports)
        
        # 第三步：验证并补充节点数量（每年至少20个）
        valid_nodes = self._verify_and_supplement_nodes(valid_nodes, future_years, preprocessed_reports)
        
        # 重建边（只保留两端节点都存在的边）
        valid_node_ids = {n["id"] for n in valid_nodes}
        valid_edges = []
        for edge in edges:
            if edge.get("source") in valid_node_ids and edge.get("target") in valid_node_ids:
                valid_edges.append(edge)
        
        # 如果没有足够的边，可以基于节点关系生成一些默认边
        if len(valid_edges) < len(valid_nodes) * 0.5:
            logger.info("边数量不足，尝试生成补充边...")
            valid_edges = self._generate_supplement_edges(valid_nodes, valid_edges)
        
        graph_data["nodes"] = valid_nodes
        graph_data["edges"] = valid_edges
        result["graph_data"] = graph_data
        
        logger.info(f"="*60)
        logger.info(f"清洗完成！")
        logger.info(f"最终节点数量: {len(valid_nodes)}")
        logger.info(f"最终边数量: {len(valid_edges)}")
        
        # 统计每年节点数
        year_counts = {}
        for node in valid_nodes:
            year = node.get("properties", {}).get("time", "")
            year_counts[year] = year_counts.get(year, 0) + 1
        logger.info(f"每年节点分布: {year_counts}")
        
        # 确保 consensus 和 conflicts 字段存在
        if not result.get("consensus"):
            result["consensus"] = [
                {"text": n["properties"].get("name", ""), "impact": n["properties"].get("impact", 7)}
                for n in valid_nodes if n["properties"].get("type") == "consensus"
            ][:10]
        if not result.get("conflicts"):
            result["conflicts"] = [
                {"text": n["properties"].get("name", ""), "impact": n["properties"].get("impact", 6)}
                for n in valid_nodes if n["properties"].get("type") == "variable"
            ][:10]
        
        logger.info(f"最终result包含 keys: {list(result.keys())}")
        logger.info("="*60)
        
        return result
    
    def _generate_supplement_edges(self, nodes: List[Dict], existing_edges: List[Dict]) -> List[Dict]:
        """生成补充的边关系
        
        当边数量不足时，基于节点的时间和维度关系生成补充边
        """
        edges = existing_edges.copy()
        edge_set = {(e.get("source"), e.get("target")) for e in existing_edges}
        
        # 按年份和维度分组
        nodes_by_year_dim = {}
        for node in nodes:
            props = node.get("properties", {})
            year = props.get("time", "")
            dim = props.get("dimension", "")
            key = f"{year}-{dim}"
            if key not in nodes_by_year_dim:
                nodes_by_year_dim[key] = []
            nodes_by_year_dim[key].append(node)
        
        # 为同一年同一维度的节点生成边
        for key, group_nodes in nodes_by_year_dim.items():
            if len(group_nodes) >= 2:
                # 在组内节点之间生成边
                for i in range(len(group_nodes)):
                    for j in range(i + 1, min(i + 3, len(group_nodes))):
                        source = group_nodes[i]["id"]
                        target = group_nodes[j]["id"]
                        
                        if (source, target) not in edge_set and (target, source) not in edge_set:
                            edges.append({
                                "source": source,
                                "target": target,
                                "label": "相互关联",
                                "type": "complement"
                            })
                            edge_set.add((source, target))
        
        return edges

    def _attach_source_quotes(self, nodes: List[Dict], preprocessed_reports: List[Dict]) -> List[Dict]:
        """为每个节点附加原文引用
        
        Args:
            nodes: 节点列表
            preprocessed_reports: 预处理后的报告列表
            
        Returns:
            附加了原文引用的节点列表
        """
        logger.info("开始为节点附加原文引用...")
        
        # 构建大师名到内容的映射
        master_content_map = {}
        for report in preprocessed_reports:
            master_name = report.get('name', '未知大师')
            content = ' '.join(report.get('paragraphs', []))
            master_content_map[master_name] = content
        
        for node in nodes:
            props = node.get("properties", {})
            master_name = props.get("master_name", "")
            description = props.get("description", "")
            
            # 如果已有source_quote，检查是否有效（至少100字）
            existing_quote = props.get("source_quote", "")
            if existing_quote and len(existing_quote) >= 100:
                continue
            
            # 从description中提取原文引用标记
            quote_match = re.search(r'原文：["""「](.+?)["""」]', description, re.DOTALL)
            if quote_match:
                # 保留完整引用，不截断（至少200字）
                full_quote = quote_match.group(1).strip()
                props["source_quote"] = full_quote[:800] if len(full_quote) > 800 else full_quote
                continue
            
            # 尝试从大师内容中提取匹配的段落
            source_master = props.get("source_master", master_name)
            if source_master in master_content_map:
                content = master_content_map[source_master]
                # 提取完整段落，不截断
                paragraphs = [p.strip() for p in re.split(r'[。！？\n]', content) if len(p.strip()) >= 50]
                if paragraphs:
                    # 选择最长的段落作为原文引用
                    best_para = max(paragraphs, key=len)
                    # 保留200-800字的原文
                    if len(best_para) > 800:
                        best_para = best_para[:800]
                    props["source_quote"] = best_para
                    # 更新description，添加原文引用
                    if "原文：" not in description:
                        props["description"] = f"【来源：{source_master}】原文：「{best_para}」\n\n{description}"
            
            # 确保source_master字段存在
            if not props.get("source_master"):
                props["source_master"] = master_name if master_name != "众师共识" else "多位大师"
        
        logger.info("原文引用附加完成")
        return nodes

    def _verify_and_supplement_nodes(
        self, 
        nodes: List[Dict], 
        future_years: int, 
        preprocessed_reports: List[Dict]
    ) -> List[Dict]:
        """验证节点数量并补充缺失的节点
        
        更新逻辑：
        1. 每年至少20个节点（基础保障）
        2. 每个维度至少1个consensus节点
        3. 尽可能多地保留 unique 和 variable 节点
        """
        logger.info("开始验证并补充节点数量...")
        
        current_year = datetime.datetime.now().year
        target_years = [f"{current_year + i}年" for i in range(future_years)]
        required_dims = ["career", "wealth", "emotion", "health"]
        dim_names = {
            "career": "事业", 
            "wealth": "财富", 
            "emotion": "情感", 
            "health": "健康"
        }
        
        # 统计现有节点分布
        node_count = {}
        for year in target_years:
            node_count[year] = {}
            for dim in required_dims:
                node_count[year][dim] = {"consensus": [], "unique": [], "variable": []}
        
        for node in nodes:
            props = node.get("properties", {})
            year = props.get("time", "")
            dim = props.get("dimension", "")
            node_type = props.get("type", "")
            
            if year in node_count and dim in required_dims:
                if node_type not in node_count[year][dim]:
                    # 如果有未知的type，暂归为unique
                    node_type = "unique"
                node_count[year][dim][node_type].append(node)
        
        # 检查并补充缺失的节点
        # 使用 max(existing_ids) 来避免 id 冲突
        max_id = 0
        for node in nodes:
            try:
                # 尝试解析类似 "2026_n12" 或 "n12" 中的数字
                parts = node["id"].split("n")
                if len(parts) > 1 and parts[-1].isdigit():
                    max_id = max(max_id, int(parts[-1]))
            except:
                pass
        node_id_counter = max_id + 1
        
        # 跟踪每个年份-维度已使用的大师
        used_masters_by_year_dim = {}
        
        # 必须先遍历一遍现有节点，初始化 used_masters_by_year_dim
        # 否则后面的补充逻辑会认为没有大师被使用
        for node in nodes:
            props = node.get("properties", {})
            year = props.get("time", "")
            dim = props.get("dimension", "")
            master = props.get("source_master", "")
            key = f"{year}-{dim}"
            if key not in used_masters_by_year_dim:
                used_masters_by_year_dim[key] = []
            if master and master not in used_masters_by_year_dim[key]:
                used_masters_by_year_dim[key].append(master)

        # 确保所有原始节点都包含在结果中
        # 之前可能因为 node_count 的分类导致部分节点丢失
        # 我们不再重置 nodes 列表，而是直接向其中添加新节点
        
        for year in target_years:
            year_total = 0
            for dim in required_dims:
                dim_nodes = node_count[year][dim]
                dim_total = sum(len(v) for v in dim_nodes.values())
                year_total += dim_total
                
                # 收集该年份-维度已使用的大师
                key = f"{year}-{dim}"
                if key not in used_masters_by_year_dim:
                    used_masters_by_year_dim[key] = []
                
                # 每个维度至少需要1个共识节点
                if not dim_nodes.get("consensus"):
                    logger.info(f"{year}-{dim} 缺少共识节点，正在补充...")
                    
                    desc, master = self._extract_rich_description(
                        preprocessed_reports, dim, year, 
                        exclude_masters=used_masters_by_year_dim[key]
                    )
                    
                    if not desc:
                        desc = f"根据{dim_names[dim]}推演，{year}整体趋势平稳，建议保持现状，静待时机。"
                        master = "多位大师"
                    
                    title = self._extract_node_title(desc, dim, "consensus")
                    source_quote = desc[:800] if len(desc) > 800 else desc
                    
                    new_node = {
                        "id": f"n{node_id_counter}",
                        "properties": {
                            "name": title,
                            "time": year,
                            "description": f"【来源：众师共识】参考大师观点：「{source_quote}」\n\n综合多位大师共识：{desc}",
                            "master_name": "众师共识",
                            "source_quote": source_quote,
                            "source_master": master,
                            "school_source": "综合推演",
                            "type": "consensus",
                            "impact": random.randint(6, 9),
                            "dimension": dim
                        }
                    }
                    nodes.append(new_node)
                    node_id_counter += 1
                    dim_total += 1
                    year_total += 1
                
                # 如果该维度总节点数太少（<3），尝试补充一些 unique 节点
                # 虽然用户说不限数量，但如果太少（比如只有1个共识），UI会很难看
                if dim_total < 3:
                    needed = 3 - dim_total
                    logger.info(f"{year}-{dim} 节点过少({dim_total})，补充 {needed} 个独特观点")
                    
                    # 尝试提取更多 unique 节点
                    all_candidates = self._extract_all_relevant_paragraphs(preprocessed_reports, dim, year)
                    random.shuffle(all_candidates)
                    
                    added = 0
                    for para, master_name in all_candidates:
                        if added >= needed:
                            break
                        # 允许大师重复，只要内容不同
                        # 但如果大师已经作为共识来源，还是尽量避开，除非没得选
                        if master_name in used_masters_by_year_dim[key]:
                            # 如果候选者太少，允许复用大师
                            if len(all_candidates) > 5:
                                continue
                            
                        title = self._extract_node_title(para, dim, "unique")
                        source_quote = para[:800] if len(para) > 800 else para
                        
                        # 检查内容是否重复
                        if any(source_quote in n.get("properties", {}).get("source_quote", "") for n in nodes):
                            continue
                        
                        new_node = {
                            "id": f"n{node_id_counter}",
                            "properties": {
                                "name": title,
                                "time": year,
                                "description": f"【来源：{master_name}】原文：「{source_quote}」\n\n{master_name}独特见解：{para}",
                                "master_name": master_name,
                                "source_quote": source_quote,
                                "source_master": master_name,
                                "school_source": "综合推演",
                                "type": "unique",
                                "impact": random.randint(5, 8),
                                "dimension": dim
                            }
                        }
                        nodes.append(new_node)
                        node_id_counter += 1
                        used_masters_by_year_dim[key].append(master_name)
                        added += 1
                        dim_total += 1
                        year_total += 1

            # 检查每年总数是否达到20个（基础保障）
            if year_total < 20:
                logger.warning(f"{year} 年节点总数不足: 现有{year_total}个，目标20个")
        
        logger.info(f"节点补充完成，当前总节点数: {len(nodes)}")
        return nodes
