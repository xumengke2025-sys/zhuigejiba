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
# Task: 基于49位大师预测，构建未来 {{future_years}} 年的“赛博天机图谱”JSON。

# Requirements:
1. **结构化分类 (Crucial)**：每年每个维度（事业/财富/情感/健康）必须包含以下三种类型的节点：
   - **consensus (共识)**：至少 60% 大师达成的核心共识。`master_name` 固定为 "众师共识"。每个维度每年 1 个。
   - **unique (独特观点)**：某位大师提出的与众不同的深刻洞察。`master_name` 必须是具体大师名。**每个维度每年 1-3 个**。
   - **variable (命理变数)**：预测中的不确定项、冲突点或转折契机。`master_name` 必须是具体大师名。**每个维度每年 1-2 个**。

2. **共识节点内容要求 (Critical)**：
   - 共识节点的 `description` 必须真正汇总多位大师的共同观点，不是简单复制某一位大师的言论
   - 必须列举“多位大师一致认为...”的共同观点，并说明为什么这是共识
   - 格式：“多位大师一致认为[具体观点]。其中墨玄从周易角度指出...，云松居士则从紫微方面...，这些观点在[具体方面]上高度契合。”

3. **节点标题要求 (Critical - 极其重要)**：
   - `name` 字段必须是 **2-5 个字的命理特征标题**，用于在图谱中直接展示
   - 必须是具体的命理特征词，如：“晋升机遇”、“贵人相助”、“桃花旺盛”、“肂胃调养”、“偶财可期”、“小人防范”
   - 绝对禁止抽象表达：“事业共识”、“财富变化”、“运势走向”、“健康状况”、“情感运势”
   - 标题示例：
     - 事业：“晋升机遇”、“贵人相助”、“小人防范”、“转型契机”、“事业稳定”、“学业进步”
     - 财富：“正财稳健”、“偶财可期”、“破财预警”、“投资谨慎”、“开源节流”
     - 情感：“桃花旺盛”、“婚姻稳固”、“感情警示”、“家庭和睦”、“子女缘旺”
     - 健康：“肂胃调养”、“意外防范”、“心理调整”、“体质调理”、“平安顺遂”

4. **节点描述要求 (Critical)**：
   - 每个节点的 `description` 必须包含 200-350 字的详细分析
   - **对于 unique/variable 节点（极其重要）**：必须保留该大师的**原始语风和专业术语**（如“官杀混杂”、“天克地冲”等），**绝对禁止**将其改写为通用的“运势变好/变坏”废话。
   - 描述中**禁止**出现“这位大师认为”、“根据预测”等废话套话，直接陈述观点。
   - 必须包含：具体时间节点、事件描述、原因分析、应对建议
   - 让用户能够清晰理解这个观点是什么、为什么、怎么办

5. **溯源**：除共识节点外，必须精准指明观点出自哪位大师。

6. **关联性**：必须构建节点间的 `edges`。关系类型包括：
   - "因果" (Causal): 一个事件导致另一个。
   - "对冲" (Conflict): 两个维度间的矛盾或观点冲突。
   - "互补" (Complement): 互相促进。
   - "时序" (Sequence): 跨年份的影响。

7. **49位大师意见聚合逻辑 (重要)**：
   - 你会收到 49 位大师的推演摘要文本，每段以 `--- 【大师名】 ---` 开头，后面是该大师对未来若干年的事业/财富/情感/健康分析。
   - 请按「年份 × 维度」（如 2026年-事业）对所有内容进行分组，在同一组内完成以下步骤：
     1) 为每位大师在该组内容中提取 2-4 个 **核心关键词**，每个为 2-5 个汉字的具体短语（如“晋升机遇”“贵人扶持”“小人防范”“转型关口”等），禁止使用抽象词或断句片段。
     2) 按语义将含义相近的关键词聚类为主题簇，统计每个主题簇被多少不同大师提及。
     3) 频次足够高、且表达方向基本一致的主题簇，生成 `consensus` 共识节点；描述中要综合多位大师的观点，而不是简单复制单一大师原文。
     4) 只有少数大师提及，或在立场上明显偏离共识但具有参考价值的主题簇，生成 `unique` 独特观点节点，**必须保留其独特的预测细节和语气，不要将其同质化**。
     5) 在同一主题上存在“机会 vs 风险”明显分歧，或文本中出现“如果…则…”、“一旦…”等条件转折，或不同年份之间出现明显走向改变的，生成 `variable` 命理变数节点，强调其不确定性与转折性。
     6) 为每个节点生成符合本提示中标题/描述要求的 `name` 和 `description` 字段，使用户一眼就能理解这个节点的核心含义。

# Output JSON Structure:
{
  "graph_data": {
    "nodes": [{"id": "n1", "properties": {"name": "2-5字命理特征标题", "time": "2026年", "description": "200-350字详细分析...", "master_name": "众师共识|具体大师名", "school_source": "..", "type": "consensus|unique|variable", "impact": 1-10, "dimension": "career|wealth|emotion|health"}}],
    "edges": [{"source": "n1", "target": "n2", "label": "关系描述", "type": "causal|conflict|complement|sequence"}]
  },
  "consensus": ["共识点1", "共识点2"], 
  "conflicts": ["冲突点1", "冲突点2"]
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
        并行聚合报告：同时生成图谱和文本，大幅提升速度
        """
        if on_progress:
            on_progress(92, "正在拨动星盘，萃取 49 位大师推演精要...")
            
        future_years = user_data.get("future_years", 3)
        
        reports_text_preview = ""
        full_reports_text = ""
        for agent_id, data in reports.items():
            # 增加预览长度以保留更多独特观点，防止 LLM 只有开头套话
            content_preview = data['content'][:800] + "..." if len(data['content']) > 800 else data['content']
            reports_text_preview += f"\n--- 【{data['name']}】 ---\n{content_preview}\n"
            full_reports_text += f"\n--- 【{data['name']}】 ---\n{data['content']}\n"
        
        user_context = f"用户信息: {json.dumps(user_data, ensure_ascii=False)}\n推演摘要: {reports_text_preview}"

        reports_list = list(reports.values())
        
        # 使用线程池并行执行两个耗时的 LLM 任务
        # 注意：不使用 with 语句，以便在超时发生时能通过 shutdown(wait=False) 强制不等待僵尸线程
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        try:
            if on_progress:
                on_progress(94, "正在校准天星方位，凝聚时空天机图谱...")
            
            # 任务 1: 生成图谱 JSON
            graph_future = executor.submit(
                self.llm.chat_json, 
                [{"role": "system", "content": GRAPH_PROMPT.replace("{{future_years}}", str(future_years))},
                 {"role": "user", "content": user_context}],
                temperature=0.3, use_boost=True
            )
            
            # 任务 2: 生成总结文本
            summary_future = executor.submit(
                self.llm.chat,
                [{"role": "system", "content": SUMMARY_PROMPT.replace("{{future_years}}", str(future_years))},
                 {"role": "user", "content": f"请基于大师推演摘要撰写报告：\n{user_context}"}],
                temperature=0.7, use_boost=True
            )

            # 获取图谱结果 - 增加超时时间到 180s
            try:
                graph_result = graph_future.result(timeout=180)
                logger.info("图谱 JSON 生成成功")
            except concurrent.futures.TimeoutError:
                logger.error("图谱生成任务超时 (180s)，正在启动 Fallback 机制...")
                graph_result = self._generate_fallback_graph(reports_list, future_years)
            except Exception as e:
                logger.error(f"图谱生成发生异常: {str(e)}，正在启动 Fallback 机制...")
                graph_result = self._generate_fallback_graph(reports_list, future_years)

            if on_progress:
                on_progress(97, "天机正在凝聚，正在编撰全案致辞...")

            # 获取总结结果 - 增加超时时间到 180s
            try:
                summary_text = summary_future.result(timeout=180)
                logger.info("总结文本生成成功")
            except concurrent.futures.TimeoutError:
                logger.error("总结文本生成超时 (180s)，使用默认占位文本")
                summary_text = "（天机运行稍显迟滞，由于推演规模巨大，总结生成超时。请直接查阅下方详细图谱与大师报告）"
            except Exception as e:
                logger.error(f"总结生成发生异常: {str(e)}")
                summary_text = "（天机运行稍显迟滞，请直接查阅下方详细图谱与大师报告）"
        
        finally:
            # 关键修复：不再等待线程结束，防止因 LLM 客户端挂死导致主线程永久阻塞
            executor.shutdown(wait=False)

        # 数据清洗与补全 - 传入 reports_list 用于智能抓取描述
        if not isinstance(graph_result, dict) or not graph_result.get("graph_data", {}).get("nodes"):
            logger.warning("图谱生成结果异常或为空，强制使用 fallback 生成")
            graph_result = self._generate_fallback_graph(reports_list, future_years)
        
        # 调试：检查 graph_result 内容
        logger.info(f"清洗前图谱节点数: {len(graph_result.get('graph_data', {}).get('nodes', []))}")
        logger.info(f"清洗前图谱边数: {len(graph_result.get('graph_data', {}).get('edges', []))}")
            
        # 预处理报告列表，提取段落，大幅提升 fallback 和 sanitize 的速度
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

    def _extract_rich_description(self, preprocessed_reports: List[Dict[str, Any]], dimension: str, year: str, exclude_texts: List[str] = None) -> tuple:
        """从上下文中抓取内容丰富的描述文本及对应的大师姓名
        
        Args:
            preprocessed_reports: 预处理后的报告列表 [{'name': '...', 'paragraphs': [...]}, ...]
            exclude_texts: 已使用的描述列表，避免重复提取相同内容
        """
        if exclude_texts is None:
            exclude_texts = []
            
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
                if len(para) < 30: continue
                
                # 检查是否已被使用
                if any(para[:50] in used for used in exclude_texts):
                    continue
                
                score = 0
                has_year = year[:4] in para if year else False
                key_count = sum(1 for k in target_keys if k in para)
                
                if has_year:
                    score += 50
                score += key_count * 10
                score += min(len(para), 200) // 10
                
                if score > 0:
                    candidates.append((score, para, master_name))
        
        if candidates:
            candidates.sort(key=lambda x: -x[0])
            return candidates[0][1][:250], candidates[0][2]
        
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

    def _synthesize_consensus_description(self, preprocessed_reports: List[Dict[str, Any]], dimension: str, year: str) -> str:
        """汇总多位大师的共同观点"""
        dim_names = {"career": "事业", "wealth": "财富", "emotion": "情感", "health": "健康"}
        dim_name = dim_names.get(dimension, "运势")
        
        all_opinions = self._extract_multiple_descriptions(preprocessed_reports, dimension, year, 6)
        
        if len(all_opinions) < 2:
            # 如果只有一个观点，直接返回
            if all_opinions:
                return f"【多位大师共识】关于{year}{dim_name}运势，{all_opinions[0][0]}"
            return f"【多位大师共识】关于{year}{dim_name}运势，多位大师给出了一致的建议。"
        
        # 构建汇总性描述
        masters_mentioned = []
        key_points = []
        
        for desc, master in all_opinions[:4]:  # 取前4个观点
            if master not in masters_mentioned:
                masters_mentioned.append(master)
            # 提取关键短语（前60字）
            key_point = desc[:60].rstrip("。，，！？") if len(desc) > 60 else desc
            key_points.append(key_point)
        
        # 构建共识描述
        masters_str = "、".join(masters_mentioned[:3])
        if len(masters_mentioned) > 3:
            masters_str += "等"
        
        consensus_desc = f"【多位大师共识】关于{year}{dim_name}运势，{masters_str}多位大师达成了高度共识。"
        
        # 添加各位大师的观点摘要
        for i, (desc, master) in enumerate(all_opinions[:3]):
            point = desc[:80].rstrip("。，，！？") if len(desc) > 80 else desc
            if i == 0:
                consensus_desc += f" 其中{master}指出：{point}"
            else:
                consensus_desc += f"；{master}则认为：{point}"
        
        consensus_desc += "。"
        
        # 添加综合建议
        consensus_desc += f" 综合来看，{year}的{dim_name}运势需要重点关注以上几点，合理规划、把握时机。"
        
        return consensus_desc

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
        """从描述中提取2-5个中文字的核心关键词作为节点标题
                
        目标：让用户一眼看懂节点内容的核心主题
        所有生成的标题都会经过断词校验
            
        Args:
            used_titles: 已使用的标题列表，避免重复
        """
        if used_titles is None:
            used_titles = []
        
        # 辅助函数：校验提取的标题是否有效（非断词）
        def is_valid_extracted_title(title: str) -> bool:
            """检查提取的标题是否是完整的词语，而非断词"""
            if not title:
                return False
            clean = title.replace("✨", "").replace("⚡", "").strip()
            if not clean:
                return False
            # 断词结尾检测
            broken_endings = ["将", "把", "被", "让", "使", "给", "向", "往", "朝", "的", "地", "得", "着", "了", "过",
                              "是", "在", "有", "和", "与", "或", "及", "而", "但", "却", "并", "且", "也", "都",
                              "能", "会", "可", "要", "应", "该", "需", "很", "太", "最", "更", "较", "比",
                              "这", "那", "其", "某", "每", "各", "视", "当", "为", "成", "做", "如", "若",
                              "从", "自", "于", "至", "到", "以", "因", "对", "关", "经", "通", "按", "据"]
            if clean[-1] in broken_endings:
                return False
            # 断词开头检测
            broken_beginnings = ["的", "地", "得", "了", "着", "过", "和", "与", "或", "及", "并", "且", "而", "但", "却", "则", "便", "即"]
            if clean[0] in broken_beginnings:
                return False
            return True
                
        # 核心关键词库 - 扩充更多常见词汇
        keyword_map = {
            "career": [
                ("晋升", "晋升"), ("升迁", "升迁"), ("创业", "创业"), ("转型", "转型"),
                ("稳定", "稳定"), ("突破", "突破"), ("贵人", "贵人相助"), ("合作", "合作机会"),
                ("竞争", "竞争加剧"), ("业绩", "业绩提升"), ("学业", "学业进步"), ("名声", "名声起起"),
                ("职位", "职位变动"), ("小人", "小人防范"), ("压力", "压力测试"), ("官运", "官运亨通"),
                ("考试", "考试顺利"), ("面试", "面试机会"), ("起伏", "运势起伏"), ("变动", "工作变动"),
                ("机遇", "机遇降临"), ("挑战", "挑战来临"), ("调动", "岗位调动"), ("辞职", "离职风险"),
                ("领导", "领导赏识"), ("事业", "事业发展"), ("工作", "工作环境"), ("功名", "功名运"),
                ("项目", "项目推进"), ("客户", "客户拓展"), ("团队", "团队合作"), ("决策", "重大决策"),
                ("资源", "资源获取"), ("人脉", "人脉拓展"), ("能力", "能力提升"), ("成长", "个人成长")
            ],
            "wealth": [
                ("偏财", "偏财运"), ("正财", "正财稳"), ("破财", "破财风险"), ("投资", "投资机会"),
                ("理财", "理财规划"), ("收入", "收入增长"), ("财运", "财运走向"), ("守财", "守财为上"),
                ("横财", "横财信号"), ("耗财", "耗财警示"), ("财库", "财库充实"), ("资产", "资产配置"),
                ("债务", "债务风险"), ("开源", "开源节流"), ("赌博", "忌赌博"), ("借贷", "借贷谨慎"),
                ("发财", "发财时机"), ("收益", "收益回报"), ("亏损", "亏损预警"), ("房产", "房产运"),
                ("股票", "股市运"), ("加薪", "加薪机会"), ("奖金", "奖金收入"), ("钱财", "钱财流动"),
                ("生意", "生意运"), ("副业", "副业收入"), ("购物", "消费支出"), ("结算", "账务结算")
            ],
            "emotion": [
                ("桃花", "桃花运"), ("婚姻", "婚姻运"), ("恋爱", "恋爱机会"), ("感情", "感情变化"),
                ("家庭", "家庭和睦"), ("矛盾", "感情矛盾"), ("分离", "分离风险"), ("复合", "复合机会"),
                ("诱惑", "外界诱惑"), ("子女", "子女缘"), ("孤独", "孤独感"), ("沟通", "沟通问题"),
                ("信任", "信任危机"), ("结婚", "结婚时机"), ("离婚", "离婚风险"), ("第三者", "第三者"),
                ("暗昧", "暗昧关系"), ("表白", "表白时机"), ("约会", "约会机会"), ("怀孕", "怀孕缘"),
                ("生育", "生育计划"), ("父母", "家人关系"), ("朋友", "友情运"), ("缘分", "姻缘运"),
                ("娘家", "娘家关系"), ("纷争", "关系纷争"), ("冷淡", "感情冷淡"), ("升温", "感情升温")
            ],
            "health": [
                ("健康", "健康状态"), ("疾病", "疾病预警"), ("调养", "调养身体"), ("心理", "心理健康"),
                ("休息", "休息调整"), ("运动", "运动健身"), ("饮食", "饮食调理"), ("精神", "精神状态"),
                ("疲劳", "过度疲劳"), ("意外", "意外防范"), ("平安", "平安顺遂"), ("压力", "压力管理"),
                ("免疫", "免疫力"), ("体质", "体质调理"), ("康复", "康复期"), ("肠胃", "肠胃保健"),
                ("失眠", "失眠问题"), ("焦虑", "焦虑情绪"), ("手术", "手术风险"), ("住院", "住院可能"),
                ("血光", "血光之灾"), ("车祸", "车祸防范"), ("跌伤", "跌伤风险"), ("头痛", "头痛困扰"),
                ("腹部", "腹部不适"), ("疹疼", "疹疼问题"), ("传染", "传染防护"), ("慢性病", "慢性病")
            ]
        }
                
        # 根据节点类型添加前缀
        type_prefix = {"consensus": "", "unique": "✨", "variable": "⚡"}
        prefix = type_prefix.get(node_type, "")
                
        # 从描述中匹配关键词
        dim_keywords = keyword_map.get(dimension, [])
        matched_titles = []
        for keyword, title in dim_keywords:
            if keyword in description:
                full_title = f"{prefix}{title}" if prefix else title
                # 检查是否已使用且是有效标题
                if full_title not in used_titles and is_valid_extracted_title(full_title):
                    return full_title
                matched_titles.append(full_title)
            
        # 如果所有匹配的标题都已使用，尝试加序号区分
        if matched_titles:
            base_title = matched_titles[0].replace(prefix, "")
            for i in range(2, 10):
                new_title = f"{prefix}{base_title}{i}" if prefix else f"{base_title}{i}"
                if new_title not in used_titles and is_valid_extracted_title(new_title):
                    return new_title
                
        # 如果没有匹配到，从描述中提取有意义的中文词
        clean_desc = description.replace("【共识】", "").replace("【", "").split("】")[-1].strip()
            
        # 扩展跳过词列表
        skip_words = ["在此", "关于", "对于", "多数", "大师", "认为", "预测", "显示", "根据", "表明", 
                      "可能", "将会", "建议", "需要", "应该", "一定", "必须", "注意", "这个", "那个",
                      "其中", "因此", "所以", "但是", "如果", "虽然", "不过", "然而", "而且", "并且"]
        for sw in skip_words:
            if clean_desc.startswith(sw):
                clean_desc = clean_desc[len(sw):]
            
        # 尝试提取更有意义的词组
        meaningful_patterns = [
            r'([\u4e00-\u9fff]{2,4})运势', r'([\u4e00-\u9fff]{2,4})方面',
            r'([\u4e00-\u9fff]{2,4})问题', r'([\u4e00-\u9fff]{2,4})机会',
            r'([\u4e00-\u9fff]{2,4})风险', r'([\u4e00-\u9fff]{2,4})变化',
            r'关于([\u4e00-\u9fff]{2,4})', r'需要([\u4e00-\u9fff]{2,4})',
            r'注意([\u4e00-\u9fff]{2,4})', r'把握([\u4e00-\u9fff]{2,4})',
            r'([\u4e00-\u9fff]{2,4})上升', r'([\u4e00-\u9fff]{2,4})下降',
            r'([\u4e00-\u9fff]{2,4})提升', r'([\u4e00-\u9fff]{2,4})调整',
            r'([\u4e00-\u9fff]{2,4})保持', r'([\u4e00-\u9fff]{2,4})增长',
            r'([\u4e00-\u9fff]{2,4})稳定', r'([\u4e00-\u9fff]{2,4})波动',
            r'([\u4e00-\u9fff]{2,4})时机', r'([\u4e00-\u9fff]{2,4})转折',
            r'([\u4e00-\u9fff]{2,4})突破', r'([\u4e00-\u9fff]{2,4})挑战',
            r'可能会([\u4e00-\u9fff]{2,4})', r'建议([\u4e00-\u9fff]{2,4})',
            r'([\u4e00-\u9fff]{2,3})年', r'下半年([\u4e00-\u9fff]{2,4})',
            r'上半年([\u4e00-\u9fff]{2,4})'
        ]
        for pattern in meaningful_patterns:
            match = re.search(pattern, clean_desc)
            if match:
                extracted = match.group(1)
                # 跳过太笼统的词
                generic_words = ["运势", "方面", "情况", "状态", "时期", "阶段", "变化", "发展"]
                if extracted not in generic_words and len(extracted) >= 2:
                    full_title = f"{prefix}{extracted}" if prefix else extracted
                    # 添加断词校验
                    if full_title not in used_titles and is_valid_extracted_title(full_title):
                        return full_title
                
        # 不再直接取前四个字，而是直接使用 fallback 标题
                
        # 最后兆底 - 使用具体的建议性标题，而不是抽象的类型名称
        fallback_titles = {
            "career": {
                "consensus": ["事业稳中有升", "职场磨练期", "时机待把握", "能力积累期"],
                "unique": ["贵人显现", "转型契机", "突破方向", "创新机会"],
                "variable": ["竞争加剧", "变动风险", "决策关口", "调整时机"]
            },
            "wealth": {
                "consensus": ["财运平稳", "稳健理财", "收入有序", "开源为上"],
                "unique": ["偶发横财", "投资时机", "副业可期", "合作生财"],
                "variable": ["破财预警", "耗财防范", "投资谨慎", "资金波动"]
            },
            "emotion": {
                "consensus": ["感情稳定", "家庭和睦", "缘分待发", "感情顺遂"],
                "unique": ["桃花旺盛", "姻缘到来", "复合可期", "深度连接"],
                "variable": ["感情波折", "误会防范", "第三者防", "沟通关口"]
            },
            "health": {
                "consensus": ["身体康健", "平安顺遂", "体质平稳", "调养为上"],
                "unique": ["运动健身", "作息调整", "饮食注意", "心态调适"],
                "variable": ["健康预警", "意外防范", "旧疾复发", "精力透支"]
            }
        }
        
        dim_fallbacks = fallback_titles.get(dimension, fallback_titles["career"])
        type_fallbacks = dim_fallbacks.get(node_type, dim_fallbacks["consensus"])
        
        for fb_title in type_fallbacks:
            full_title = f"{prefix}{fb_title}" if prefix else fb_title
            if full_title not in used_titles and is_valid_extracted_title(full_title):
                return full_title
        
        # 如果全部用完，加序号
        base = type_fallbacks[0]
        for i in range(2, 10):
            new_title = f"{prefix}{base}{i}" if prefix else f"{base}{i}"
            if new_title not in used_titles and is_valid_extracted_title(new_title):
                return new_title
        return f"{prefix}{base}" if prefix else base

    def _generate_fallback_graph(self, context_data: Any, future_years: int) -> Dict[str, Any]:
        """兆底策略：生成饱满的图谱，确保每个维度都有共识、多个独特观点和多个变数
        context_data: 可以是 List[Dict] (大师报告列表) 或 str (汇总文本)
        """
        # 统一转换为 List[Dict] 格式
        reports_list = []
        if isinstance(context_data, list):
            reports_list = context_data
        elif isinstance(context_data, str):
            # 如果是字符串，尝试按大师分隔，或者作为单一来源
            if "--- 【" in context_data:
                parts = context_data.split("--- 【")
                for part in parts:
                    if "】 ---" in part:
                        name_part, content = part.split("】 ---", 1)
                        reports_list.append({"name": name_part.strip(), "content": content.strip()})
            else:
                # 简单处理：按年份切分或直接作为内容
                reports_list = [{"name": "众师精要", "content": context_data}]
        
        logger.info(f"Fallback 启动，输入数据类型: {type(context_data)}, 转换后报告数: {len(reports_list)}")
        
        # 预处理报告
        preprocessed_reports = []
        for r in reports_list:
            content = r.get('content', '')
            paras = [p.strip() for p in re.split(r'[\n。！？]', content) if p.strip()]
            preprocessed_reports.append({
                "name": r.get('name', '未知大师'),
                "paragraphs": paras
            })

        current_year = datetime.datetime.now().year
        nodes = []
        edges = []
                
        # 未来N年包含当前年（如2026年，未权3年为2026/2027/2028）
        target_years = [f"{current_year + i}年" for i in range(future_years)]
        dims = ["career", "wealth", "emotion", "health"]
        dim_names = {"career": "事业", "wealth": "财富", "emotion": "情感", "health": "健康"}
        type_names = {"consensus": "核心共识", "unique": "独特视角", "variable": "命理变数"}
                
        # 大师候选列表
        master_pool = ["墨玄", "云松居士", "莉莉丝", "隐鹤", "了尘", "随风", "铁口", 
                       "爿位", "德厚", "博雅", "阿格里帕", "艾薛", "毕达哥", "奥丁",
                       "织命者卡洛斯", "镧射", "库库尔坎", "玻尔", "虚空", "迦叶"]
            
        # 全局去重跟踪
        global_used_titles = []  # 跟踪已使用的标题
        global_used_descriptions = []  # 跟踪已使用的描述前50字
                
        for ty in target_years:
            for dim in dims:
                used_masters = []
                        
                # 从报告中提取该年份该维度的所有相关内容
                all_descriptions = self._extract_multiple_descriptions(preprocessed_reports, dim, ty, 10)
                desc_index = 0
                        
                def get_next_unique_description():
                    """ 获取下一个未使用过的描述 """
                    nonlocal desc_index
                    while desc_index < len(all_descriptions):
                        desc, master = all_descriptions[desc_index]
                        desc_index += 1
                        # 检查描述是否已使用（用前50字作为指纹）
                        desc_fingerprint = desc[:50] if len(desc) >= 50 else desc
                        if desc_fingerprint not in global_used_descriptions:
                            global_used_descriptions.append(desc_fingerprint)
                            return (desc, master)
                    return ("", "大师共鸣")
                        
                # 1个共识节点 - 使用新的汇总方法
                consensus_desc = self._synthesize_consensus_description(preprocessed_reports, dim, ty)
                    
                title = self._extract_node_title(consensus_desc, dim, "consensus", global_used_titles)
                global_used_titles.append(title)
                nodes.append({"id": f"fallback_{ty}_{dim}_consensus", "properties": {
                    "name": title, "time": ty, "description": consensus_desc,
                    "master_name": "众师共识", "school_source": "大师精要", "type": "consensus",
                    "impact": random.randint(6, 9), "dimension": dim}})
                        
                # 3-4个独特视角节点
                unique_count = random.randint(3, 4)
                for ui in range(unique_count):
                    desc, m_name = get_next_unique_description()
                    if m_name == "大师共鸣" or m_name in used_masters or not desc:
                        available = [m for m in master_pool if m not in used_masters]
                        m_name = random.choice(available) if available else random.choice(master_pool)
                    used_masters.append(m_name)
                            
                    if desc:
                        desc = f"【{m_name}观点】{desc}"
                    else:
                        desc, _ = self._extract_rich_description(preprocessed_reports, dim, "")
                        desc = f"【{m_name}观点】{desc}" if desc else f"在此维度，{m_name}大师捕捉到了一个关键的{type_names['unique']}。"
                        
                    title = self._extract_node_title(desc, dim, "unique", global_used_titles)
                    global_used_titles.append(title)
                    nodes.append({"id": f"fallback_{ty}_{dim}_unique_{ui}", "properties": {
                        "name": title, "time": ty, "description": desc,
                        "master_name": m_name, "school_source": "大师精要", "type": "unique",
                        "impact": random.randint(5, 8), "dimension": dim}})
                        
                # 2-3个变数节点
                variable_count = random.randint(2, 3)
                for vi in range(variable_count):
                    desc, m_name = get_next_unique_description()
                    if m_name == "大师共鸣" or m_name in used_masters or not desc:
                        available = [m for m in master_pool if m not in used_masters]
                        m_name = random.choice(available) if available else random.choice(master_pool)
                    used_masters.append(m_name)
                            
                    if desc:
                        desc = f"【{m_name}变数】{desc}"
                    else:
                        desc, _ = self._extract_rich_description(preprocessed_reports, dim, "")
                        desc = f"【{m_name}变数】{desc}" if desc else f"在此维度，{m_name}大师捕捉到了一个关键的{type_names['variable']}。"
                        
                    title = self._extract_node_title(desc, dim, "variable", global_used_titles)
                    global_used_titles.append(title)
                    nodes.append({"id": f"fallback_{ty}_{dim}_variable_{vi}", "properties": {
                        "name": title, "time": ty, "description": desc,
                        "master_name": m_name, "school_source": "大师精要", "type": "variable",
                        "impact": random.randint(5, 8), "dimension": dim}})
        
        # 构建星形关联：所有独特视角和变数都围绕共识节点
        for ty in target_years:
            for dim in dims:
                # 找到该年份该维度的所有节点
                year_dim_nodes = [n for n in nodes if n["properties"]["time"] == ty and n["properties"]["dimension"] == dim]
                consensus_node = next((n for n in year_dim_nodes if n["properties"]["type"] == "consensus"), None)
                unique_nodes = [n for n in year_dim_nodes if n["properties"]["type"] == "unique"]
                variable_nodes = [n for n in year_dim_nodes if n["properties"]["type"] == "variable"]
                
                if consensus_node:
                    # 共识 -> 每个独特视角（星形结构）
                    for u in unique_nodes:
                        edges.append({"source": consensus_node["id"], "target": u["id"], "label": "视角延伸", "type": "complement"})
                    # 共识 -> 每个变数（星形结构）
                    for v in variable_nodes:
                        edges.append({"source": consensus_node["id"], "target": v["id"], "label": "潜在变局", "type": "conflict"})
        
        # 从节点中提取共识和冲突列表
        consensus_list = []
        conflicts_list = []
        for n in nodes:
            props = n.get("properties", {})
            if props.get("type") == "consensus":
                consensus_list.append({"text": props.get("name", ""), "impact": props.get("impact", 7)})
            elif props.get("type") == "variable":
                conflicts_list.append({"text": props.get("name", ""), "impact": props.get("impact", 6)})
        
        return {
            "graph_data": {"nodes": nodes, "edges": edges},
            "consensus": consensus_list[:10],  # 取前10个
            "conflicts": conflicts_list[:10]   # 取前10个
        }

    def _sanitize_result(self, result: Dict[str, Any], future_years: int, preprocessed_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """清洗和补全数据，支持每年/每维度有多个独特视角和变数
        all_descriptions = self._extract_multiple_descriptions(preprocessed_reports, dim, year, 10)
        """
        logger.info("开始清洗图谱数据...")
        logger.info(f"输入result keys: {list(result.keys())}")
        logger.info(f"preprocessed_reports 长度: {len(preprocessed_reports)}")
        
        current_year = datetime.datetime.now().year
        graph_data = result.get("graph_data", {"nodes": [], "edges": []})
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
                
        # 未来N年包含当前年（如2026年，未权3年为2026/2027/2028）
        target_years = [f"{current_year + i}年" for i in range(future_years)]
        required_dims = ["career", "wealth", "emotion", "health"]
        dim_names = {"career": "事业", "wealth": "财富", "emotion": "情感", "health": "健康"}
        type_names = {"consensus": "共识", "unique": "独特视角", "variable": "变数"}
                
        # 大师候选列表
        master_pool = ["墨玄", "云松居士", "莉莉丝", "隐鹤", "了尘", "随风", "铁口", 
                       "爿位", "德厚", "博雅", "阿格里帕", "艾薛", "毕达哥", "奥丁",
                       "织命者卡洛斯", "镧射", "库库尔坎", "玻尔", "虚空", "迦叶"]
        
        valid_nodes = []
            
        # 全局去重跟踪
        global_used_titles = []  # 跟踪已使用的标题
        global_used_descriptions = []  # 跟踪已使用的描述前50字
                
        # 建立索引以便快速检查 - 支持多个同类型节点
        node_map = {}  # (year, dim, type) -> [nodes]
        for node in nodes:
            props = node.get("properties", {})
            y = str(props.get("time", ""))
            # 统一年份格式，处理 "2026" vs "2026年"
            y_clean = y if "年" in y else f"{y}年"
            d = props.get("dimension", "")
            t = props.get("type", "consensus")
            if "20" in y_clean and d in required_dims:
                key = (y_clean, d, t)
                if key not in node_map:
                    node_map[key] = []
                node_map[key].append(node)
        
        logger.info(f"建立 node_map 成功，Key 数量: {len(node_map)}")
        for k, v in node_map.items():
            logger.debug(f"Key: {k}, 节点数: {len(v)}")
        
        # 遍历补齐
        for year in target_years:
            for dim in required_dims:
                used_masters = []
                        
                # 为此年份此维度提取多个描述
                all_descriptions = self._extract_multiple_descriptions(preprocessed_reports, dim, year, 10)
                desc_index = 0
                        
                def get_next_unique_description():
                    """ 获取下一个未使用过的描述 """
                    nonlocal desc_index
                    while desc_index < len(all_descriptions):
                        desc, master = all_descriptions[desc_index]
                        desc_index += 1
                        # 检查描述是否已使用（用前50字作为指纹）
                        desc_fingerprint = desc[:50] if len(desc) >= 50 else desc
                        if desc_fingerprint not in global_used_descriptions:
                            global_used_descriptions.append(desc_fingerprint)
                            return (desc, master)
                    return ("", "大师共鸣")
                        
                # 1. 处理 consensus - 每个维度每年只要 1 个，使用汇总方法生成内容
                existing_consensus = node_map.get((year, dim, "consensus"), [])
                if existing_consensus:
                    node = existing_consensus[0]
                    props = node["properties"]
                    props["master_name"] = "众师共识"
                    
                    # 如果描述太短或不够详细，重新生成汇总描述
                    if len(props.get("description", "")) < 150:
                        props["description"] = self._synthesize_consensus_description(preprocessed_reports, dim, year)
                    
                    # 优先使用LLM返回的标题，如果无效才重新提取
                    llm_title = props.get("name", "")
                    if self._is_valid_llm_title(llm_title, global_used_titles):
                        title = llm_title
                    else:
                        title = self._extract_node_title(props.get("description", ""), dim, "consensus", global_used_titles)
                    global_used_titles.append(title)
                    props["name"] = title
                    valid_nodes.append(node)
                else:
                    # 生成新的共识节点，使用汇总方法
                    consensus_desc = self._synthesize_consensus_description(preprocessed_reports, dim, year)
                    title = self._extract_node_title(consensus_desc, dim, "consensus", global_used_titles)
                    global_used_titles.append(title)
                    valid_nodes.append({
                        "id": f"gen_{year}_{dim}_consensus",
                        "properties": {
                            "name": title,
                            "time": year,
                            "description": consensus_desc,
                            "master_name": "众师共识",
                            "school_source": "大师共鸣",
                            "type": "consensus",
                            "impact": random.randint(6, 9),
                            "dimension": dim
                        }
                    })
                        
                # 2. 处理 unique - 每个维度每年需要 3-4 个
                existing_unique = node_map.get((year, dim, "unique"), [])
                target_unique_count = random.randint(3, 4)
                    
                # 先处理已有的 unique 节点，检查并去重
                unique_added = 0
                for i, node in enumerate(existing_unique):
                    if unique_added >= target_unique_count:
                        break
                    props = node["properties"]
                    desc = props.get("description", "")
                    desc_fingerprint = desc[:50] if len(desc) >= 50 else desc
                    # 检查描述是否已使用
                    if desc_fingerprint in global_used_descriptions:
                        continue  # 跳过重复的节点
                    global_used_descriptions.append(desc_fingerprint)
                        
                    if not props.get("master_name") or props["master_name"] == "众师共识":
                        _, m_name = get_next_unique_description()
                        if m_name == "大师共鸣" or m_name in used_masters:
                            available = [m for m in master_pool if m not in used_masters]
                            m_name = random.choice(available) if available else random.choice(master_pool)
                        props["master_name"] = m_name
                    used_masters.append(props["master_name"])
                        
                    # 优先使用LLM返回的标题，如果无效才重新提取
                    llm_title = props.get("name", "")
                    if self._is_valid_llm_title(llm_title, global_used_titles):
                        title = llm_title
                    else:
                        title = self._extract_node_title(desc, dim, "unique", global_used_titles)
                    global_used_titles.append(title)
                    props["name"] = title
                        
                    # 如果描述太短，补充内容
                    if len(desc) < 150:
                        rich_desc, _ = get_next_unique_description()
                        if rich_desc:
                            # 移除废话模板，直接拼接具体内容
                            props["description"] = f"【{props['master_name']}观点】{rich_desc}"
                    valid_nodes.append(node)
                    unique_added += 1
                        
                # 补充不足的 unique 节点
                for i in range(unique_added, target_unique_count):
                    rich_desc, rich_master = get_next_unique_description()
                    if rich_master == "大师共鸣" or rich_master in used_masters:
                        available = [m for m in master_pool if m not in used_masters]
                        rich_master = random.choice(available) if available else random.choice(master_pool)
                    used_masters.append(rich_master)
                    
                    # 构建详细描述
                    if rich_desc:
                        # 移除废话模板，直接使用提取的丰富内容
                        full_desc = f"【{rich_master}观点】{rich_desc}"
                    else:
                        # Fallback: 如果实在没有内容，使用稍微具体一点的通用语，但避免太机械
                        full_desc = f"【{rich_master}观点】{rich_master}大师在{year}年{dim_names[dim]}方面有独到见解，提醒注意细节变化，具体吉凶需结合个人八字细推。"
                        
                    title = self._extract_node_title(full_desc, dim, "unique", global_used_titles)
                    global_used_titles.append(title)
                    valid_nodes.append({
                        "id": f"gen_{year}_{dim}_unique_{i}",
                        "properties": {
                            "name": title,
                            "time": year,
                            "description": full_desc,
                            "master_name": rich_master,
                            "school_source": "大师共鸣",
                            "type": "unique",
                            "impact": random.randint(5, 8),
                            "dimension": dim
                        }
                    })
                        
                # 3. 处理 variable - 每个维度每年需要 2-3 个
                existing_variable = node_map.get((year, dim, "variable"), [])
                target_variable_count = random.randint(2, 3)
                    
                # 先处理已有的 variable 节点，检查并去重
                variable_added = 0
                for i, node in enumerate(existing_variable):
                    if variable_added >= target_variable_count:
                        break
                    props = node["properties"]
                    desc = props.get("description", "")
                    desc_fingerprint = desc[:50] if len(desc) >= 50 else desc
                    # 检查描述是否已使用
                    if desc_fingerprint in global_used_descriptions:
                        continue  # 跳过重复的节点
                    global_used_descriptions.append(desc_fingerprint)
                        
                    if not props.get("master_name") or props["master_name"] == "众师共识":
                        _, m_name = get_next_unique_description()
                        if m_name == "大师共鸣" or m_name in used_masters:
                            available = [m for m in master_pool if m not in used_masters]
                            m_name = random.choice(available) if available else random.choice(master_pool)
                        props["master_name"] = m_name
                    used_masters.append(props["master_name"])
                        
                    # 优先使用LLM返回的标题，如果无效才重新提取
                    llm_title = props.get("name", "")
                    if self._is_valid_llm_title(llm_title, global_used_titles):
                        title = llm_title
                    else:
                        title = self._extract_node_title(desc, dim, "variable", global_used_titles)
                    global_used_titles.append(title)
                    props["name"] = title
                        
                    # 如果描述太短，补充内容
                    if len(desc) < 150:
                        rich_desc, _ = get_next_unique_description()
                        if rich_desc:
                            # 移除废话模板
                            props["description"] = f"【{props['master_name']}变数】{rich_desc}"
                    valid_nodes.append(node)
                    variable_added += 1
                        
                # 补充不足的 variable 节点
                for i in range(variable_added, target_variable_count):
                    rich_desc, rich_master = get_next_unique_description()
                    if rich_master == "大师共鸣" or rich_master in used_masters:
                        available = [m for m in master_pool if m not in used_masters]
                        rich_master = random.choice(available) if available else random.choice(master_pool)
                    used_masters.append(rich_master)
                    
                    # 构建详细描述
                    if rich_desc:
                        # 移除废话模板
                        full_desc = f"【{rich_master}变数】{rich_desc}"
                    else:
                        full_desc = f"【{rich_master}变数】{rich_master}大师指出{year}年{dim_names[dim]}存在关键转折，机遇与挑战并存，需灵活应变。"
                        
                    title = self._extract_node_title(full_desc, dim, "variable", global_used_titles)
                    global_used_titles.append(title)
                    valid_nodes.append({
                        "id": f"gen_{year}_{dim}_variable_{i}",
                        "properties": {
                            "name": title,
                            "time": year,
                            "description": full_desc,
                            "master_name": rich_master,
                            "school_source": "大师共鸣",
                            "type": "variable",
                            "impact": random.randint(5, 8),
                            "dimension": dim
                        }
                    })
    
        # 关联补全逻辑：构建星形结构，独特视角和变数围绕共识节点
        edges = []  # 重建边，确保星形结构
                
        # 1. 同年同维度的星形关联：共识为中心
        for year in target_years:
            for dim in required_dims:
                year_dim_nodes = [n for n in valid_nodes if n["properties"]["time"] == year and n["properties"]["dimension"] == dim]
                consensus_node = next((n for n in year_dim_nodes if n["properties"]["type"] == "consensus"), None)
                unique_nodes = [n for n in year_dim_nodes if n["properties"]["type"] == "unique"]
                variable_nodes = [n for n in year_dim_nodes if n["properties"]["type"] == "variable"]
                            
                if consensus_node:
                    # 共识 -> 每个独特视角（星形结构）
                    for u in unique_nodes:
                        edges.append({"source": consensus_node["id"], "target": u["id"], "label": "视角延伸", "type": "complement"})
                    # 共识 -> 每个变数（星形结构）
                    for v in variable_nodes:
                        edges.append({"source": consensus_node["id"], "target": v["id"], "label": "潜在变局", "type": "conflict"})
        
        # 2. 跨维度关联 (事业 -> 财富)
        for year in target_years:
            career = next((n for n in valid_nodes if n["properties"]["time"] == year and n["properties"]["dimension"] == "career" and n["properties"]["type"] == "consensus"), None)
            wealth = next((n for n in valid_nodes if n["properties"]["time"] == year and n["properties"]["dimension"] == "wealth" and n["properties"]["type"] == "consensus"), None)
            if career and wealth:
                edges.append({"source": career["id"], "target": wealth["id"], "label": "事业化财", "type": "causal"})
    
        graph_data["nodes"] = valid_nodes
        graph_data["edges"] = edges
        result["graph_data"] = graph_data
        
        logger.info(f"清洗后的节点数量: {len(valid_nodes)}")
        logger.info(f"清洗后的边数量: {len(edges)}")
        if valid_nodes:
            logger.info(f"第一个节点示例: {valid_nodes[0]}")
        
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
        logger.info("清洗完成，返回result")
        
        return result
