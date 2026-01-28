"""
命理推演编排服务
负责 49 位大师 Agent 的并行调度与结果汇总
"""

import threading
import concurrent.futures
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from ..utils.fortune_utils import FortuneUtils
from .fortune_agents import MASTER_PERSONAS, get_agent_system_prompt

logger = get_logger('wannian.fortune_service')

class FortuneService:
    """命理服务调度器"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        self.sessions: Dict[str, Dict[str, Any]] = {}
        # 添加简单的内存缓存，避免重复计算
        # Key: md5(agent_id + sorted_input_json), Value: report_str
        self.agent_cache: Dict[str, str] = {}
    
    def _get_cache_key(self, agent_id: str, input_data: Dict[str, Any]) -> str:
        """生成缓存键"""
        import hashlib
        # 创建输入的副本以避免修改原始数据
        data_copy = input_data.copy()
        # 移除可能变化的非核心字段（如果有）
        if "future_years" in data_copy:
             # future_years 应该影响结果，所以保留
             pass
             
        # 序列化为稳定的 JSON 字符串
        input_str = json.dumps(data_copy, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(f"{agent_id}:{input_str}".encode()).hexdigest()
    
    def analyze_fate(
        self, 
        name: str,
        birthday: str, 
        birth_time: str, 
        birth_location: str, 
        gender: str,
        future_years: int = 3,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        开始 49 位大师的并行推演
        """
        if not session_id:
            import uuid
            session_id = f"fate_{uuid.uuid4().hex[:12]}"
        
        # 1. 数据归一化
        normalized_data = FortuneUtils.normalize_input(
            name, birthday, birth_time, birth_location, gender
        )
        normalized_data["future_years"] = future_years
        
        if "error" in normalized_data:
            return {"success": False, "error": normalized_data["error"]}
        
        self.sessions[session_id] = {
            "status": "processing",
            "status_msg": "正在初始化推演序列...",
            "input": normalized_data,
            "reports": {},
            "summary": None,
            "created_at": datetime.now().isoformat(),
            "progress": 0,
            "future_years": future_years
        }
        
        # 2. 并行请求 49 位大师
        def run_agent_task(persona: Dict[str, Any]):
            try:
                # 检查缓存
                cache_key = self._get_cache_key(persona["id"], normalized_data)
                if cache_key in self.agent_cache:
                    return persona["id"], persona["name"], self.agent_cache[cache_key]

                self.sessions[session_id]["status_msg"] = f"大师 {persona['name']} 正在接入星盘..."
                system_prompt = get_agent_system_prompt(persona["id"])
                
                # 填充变量
                for key, value in normalized_data.items():
                    system_prompt = system_prompt.replace(f"{{{{{key}}}}}", str(value))
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"请根据我的出生信息进行深度推演，并重点预测未来 {future_years} 年的运势走向。"}
                ]
                
                report = self.llm.chat(messages, temperature=0.7)
                
                # 写入缓存
                self.agent_cache[cache_key] = report
                
                return persona["id"], persona["name"], report
            except Exception as e:
                logger.error(f"Agent {persona['id']} 推演失败: {str(e)}")
                return persona["id"], persona["name"], f"推演过程中发生错误: {str(e)}"

        def background_execution():
            # 调整并发数为 25，提升并行处理效率
            with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
                future_to_agent = {executor.submit(run_agent_task, p): p for p in MASTER_PERSONAS}
                
                completed = 0
                failed = 0
                total_masters = len(MASTER_PERSONAS)
                total_futures = len(future_to_agent)
                
                logger.info(f"[推演任务 {session_id}] 已提交 {total_futures} 个任务，开始等待完成...")
                
                # 等待所有 49 位大师完成，不设置超时
                # 重要：必须等待49位大师全部完成后才能绘制图谱和生成报告
                for future in concurrent.futures.as_completed(future_to_agent):
                    persona = future_to_agent[future]
                    try:
                        agent_id, agent_name, report = future.result()
                        self.sessions[session_id]["reports"][agent_id] = {
                            "name": agent_name,
                            "content": report
                        }
                        completed += 1
                        logger.debug(f"[{session_id}] 大师 {agent_name} 完成 ({completed}/{total_masters})")
                    except Exception as e:
                        failed += 1
                        logger.error(f"[{session_id}] 大师 {persona['name']} 推演失败: {e}")
                    
                    # 推演阶段占 90% 进度
                    total_done = completed + failed
                    self.sessions[session_id]["progress"] = int((total_done / total_masters) * 90)
                    self.sessions[session_id]["status_msg"] = f"已完成 {total_done}/{total_masters} 位大师的推演..."
                
                # 确认所有49位大师都已完成
                final_count = completed + failed
                logger.info(f"[推演任务 {session_id}] for循环结束，成功: {completed}，失败: {failed}，总计: {final_count}/{total_masters}")
                
                # 如果实际完成数小于总数，等待剩余的 future 完成
                if final_count < total_masters:
                    logger.warning(f"[推演任务 {session_id}] 警告：实际完成数({final_count})小于总数({total_masters})，尝试等待剩余任务...")
                    
                    # 显式等待所有未完成的 future
                    for future, persona in future_to_agent.items():
                        if not future.done():
                            logger.info(f"[推演任务 {session_id}] 等待未完成的大师: {persona['name']}")
                            try:
                                agent_id, agent_name, report = future.result(timeout=120)  # 最多等待2分钟
                                self.sessions[session_id]["reports"][agent_id] = {
                                    "name": agent_name,
                                    "content": report
                                }
                                completed += 1
                            except Exception as e:
                                failed += 1
                                logger.error(f"[推演任务 {session_id}] 大师 {persona['name']} 最终失败: {e}")
                    
                    final_count = completed + failed
                    logger.info(f"[推演任务 {session_id}] 二次等待后，成功: {completed}，失败: {failed}，总计: {final_count}/{total_masters}")
                
                logger.info(f"推演任务 {session_id}: 所有 {total_masters} 位大师已完成，开始图谱绘制")
                self.sessions[session_id]["status_msg"] = f"{total_masters}位大师推演完毕，正在启动图谱绘制..."
                self.sessions[session_id]["progress"] = 90
                
            # 3. 触发聚合
            try:
                self.sessions[session_id]["status"] = "aggregating"
                from .fortune_aggregator import FortuneAggregator
                aggregator = FortuneAggregator(self.llm)
                
                def update_aggregator_progress(p, msg):
                    self.sessions[session_id]["progress"] = p
                    self.sessions[session_id]["status_msg"] = msg
                
                summary = aggregator.aggregate_reports(
                    normalized_data, 
                    self.sessions[session_id]["reports"],
                    on_progress=update_aggregator_progress
                )
                
                # 调试日志：确认聚合返回数据
                logger.info(f"[{session_id}] 聚合返回类型: {type(summary)}, keys: {list(summary.keys()) if isinstance(summary, dict) else 'N/A'}")
                if isinstance(summary, dict):
                    logger.info(f"[{session_id}] summary_text 存在: {'summary_text' in summary}, 长度: {len(summary.get('summary_text', '')) if summary.get('summary_text') else 0}")
                
                self.sessions[session_id]["summary"] = summary
                self.sessions[session_id]["status"] = "completed"
                logger.info(f"[{session_id}] 已设置 session summary, 状态: completed")
            except Exception as e:
                import traceback
                logger.error(f"聚合报告失败: {str(e)}")
                logger.error(f"堆栈: {traceback.format_exc()}")
                self.sessions[session_id]["status"] = "failed"
                self.sessions[session_id]["error"] = str(e)

        # 启动异步线程执行
        thread = threading.Thread(target=background_execution)
        thread.start()
        
        return {
            "success": True,
            "session_id": session_id,
            "status": "processing",
            "message": "49位大师已开始并行推演，请稍后查询结果"
        }

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """查询推演进度与结果"""
        session = self.sessions.get(session_id)
        if not session:
            return {"success": False, "error": "未找到推演任务"}
        
        return {
            "success": True,
            "status": session["status"],
            "status_msg": session.get("status_msg", ""),
            "progress": session["progress"],
            "reports_count": len(session["reports"]),
            "summary": session["summary"],
            "created_at": session["created_at"]
        }
    
    def get_full_report(self, session_id: str) -> Dict[str, Any]:
        """获取完整报告内容"""
        session = self.sessions.get(session_id)
        if not session:
            return {"success": False, "error": "未找到推演任务"}
        
        return {
            "success": True,
            "session_id": session_id,
            "input": session["input"],
            "reports": session["reports"],
            "summary": session["summary"],
            "status": session["status"]
        }
