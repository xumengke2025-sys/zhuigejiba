"""
LLM客户端封装
统一使用OpenAI格式调用
"""

import json
from typing import Optional, Dict, Any, List
from openai import OpenAI

from ..config import Config
from .retry import retry_with_backoff


class LLMClient:
    """LLM客户端"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY 未配置")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=300.0
        )
        
        # 初始化加速模型客户端（如果有配置）
        self.boost_client = None
        if Config.LLM_BOOST_API_KEY:
            boost_base_url = Config.LLM_BOOST_BASE_URL or self.base_url
            self.boost_client = OpenAI(
                api_key=Config.LLM_BOOST_API_KEY,
                base_url=boost_base_url,
                timeout=300.0
            )
    
    @retry_with_backoff(max_retries=3, initial_delay=2.0, max_delay=60.0, exceptions=(Exception,))
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
        use_boost: bool = False
    ) -> str:
        """
        发送聊天请求
        """
        from openai import APIConnectionError, APITimeoutError
        
        # 如果指定使用加速模型且配置了加速模型，则尝试切换
        if use_boost and self.boost_client:
            try:
                kwargs = {
                    "model": Config.LLM_BOOST_MODEL_NAME,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if response_format:
                    kwargs["response_format"] = response_format
                
                # 加速模型使用更短的超时，如果慢就不用了
                response = self.boost_client.chat.completions.create(**kwargs)
                return response.choices[0].message.content
            except (APIConnectionError, APITimeoutError) as e:
                from .logger import get_logger
                logger = get_logger('silverfish.llm')
                logger.warning(f"加速模型连接失败或超时，跳过加速: {str(e)}")
            except Exception as e:
                from .logger import get_logger
                logger = get_logger('silverfish.llm')
                logger.warning(f"加速模型调用异常，正在退回到主模型: {str(e)}")
                # 失败后继续向下执行，使用主模型

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if response_format:
            kwargs["response_format"] = response_format
        
        try:
            from .logger import get_logger
            logger = get_logger('silverfish.llm')
            logger.debug(f"LLM Request: model={kwargs['model']}, temp={temperature}")
            
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            
            logger.debug(f"LLM Response received: {len(content)} chars")
            return content
        except APIConnectionError as e:
            from .logger import get_logger
            logger = get_logger('silverfish.llm')
            logger.error(f"LLM 连接拒绝 (10061) 或网络不可达: {str(e)}")
            # 对于连接错误，重试可能没用，直接抛出以便上层触发 fallback
            raise
    
    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        use_boost: bool = False
    ) -> Dict[str, Any]:
        """
        发送聊天请求并返回JSON
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            use_boost: 是否使用加速模型
            
        Returns:
            解析后的JSON对象
        """
        try:
            response = self.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                use_boost=use_boost
            )
            
            # 尝试直接解析
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # 如果解析失败，尝试提取代码块中的JSON
                import re
                json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))
                
                # 尝试提取最外层的 { }
                json_match = re.search(r'(\{.*\})', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(1))
                
                raise
        except Exception as e:
            from .logger import get_logger
            logger = get_logger('wannian.llm')
            logger.error(f"LLM JSON 解析失败: {str(e)}")
            logger.error(f"原始响应内容: {response if 'response' in locals() else 'None'}")
            raise

