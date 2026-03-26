"""LLM 客户端模块"""
import asyncio
import logging
import os
import time
from typing import Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class LLMUsage:
    """Token 使用统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    
    def add(self, other: "LLMUsage"):
        """累加使用量"""
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.cost += other.cost


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    model: str
    usage: LLMUsage
    finish_reason: Optional[str] = None
    raw_response: Optional[dict] = None


# 模型价格映射（每 1M tokens 的价格，单位：美元）
MODEL_PRICES = {
    "gpt-4": {"prompt": 30.0, "completion": 60.0},
    "gpt-4-turbo": {"prompt": 10.0, "completion": 30.0},
    "gpt-3.5-turbo": {"prompt": 0.5, "completion": 1.5},
    "claude-3-opus": {"prompt": 15.0, "completion": 75.0},
    "claude-3-sonnet": {"prompt": 3.0, "completion": 15.0},
    "claude-3-haiku": {"prompt": 0.25, "completion": 1.25},
    "gemini-pro": {"prompt": 1.25, "completion": 5.0},
}


def _calculate_cost(model: str, usage: LLMUsage) -> float:
    """计算 API 调用成本"""
    model_base = model.split("/")[-1].lower()
    
    for price_model, prices in MODEL_PRICES.items():
        if price_model in model_base:
            prompt_cost = (usage.prompt_tokens / 1_000_000) * prices["prompt"]
            completion_cost = (usage.completion_tokens / 1_000_000) * prices["completion"]
            return prompt_cost + completion_cost
    
    # 默认价格估算
    return (usage.total_tokens / 1_000_000) * 1.0


class LLMClient:
    """LLM 客户端封装"""
    
    def __init__(
        self,
        model: str = "gpt-3.5-turbo",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 60,
    ):
        """
        初始化 LLM 客户端
        
        Args:
            model: 模型名称
            api_key: API 密钥
            base_url: API 基础 URL
            max_retries: 最大重试次数
            timeout: 超时秒数
        """
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.max_retries = max_retries
        self.timeout = timeout
        
        self._usage: LLMUsage = LLMUsage()
        self._client = None
        self._lock = asyncio.Lock()
    
    async def _get_client(self):
        """获取 LiteLLM 客户端"""
        if self._client is None:
            try:
                import litellm
                self._client = litellm
                
                if self.api_key:
                    self._client.api_key = self.api_key
                if self.base_url:
                    self._client.base_url = self.base_url
                    
            except ImportError:
                logger.warning("LiteLLM not installed, using mock client")
                self._client = MockLLMClient(self.model)
    
    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        发送完成请求
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数
        
        Returns:
            LLM 响应
        """
        await self._get_client()
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self._call_llm(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                
                # 更新使用统计
                async with self._lock:
                    self._usage.add(response.usage)
                
                return response
                
            except Exception as e:
                last_error = e
                logger.warning(f"LLM call failed (attempt {attempt + 1}): {e}")
                
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
        
        logger.error(f"LLM call failed after {self.max_retries} attempts: {last_error}")
        raise last_error
    
    async def _call_llm(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
        **kwargs,
    ) -> LLMResponse:
        """实际调用 LLM"""
        # 如果没有 API key，直接使用 mock
        if not self.api_key and not os.environ.get("OPENAI_API_KEY"):
            logger.info("No API key found, using mock LLM client")
            return await MockLLMClient(self.model).complete(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        
        try:
            import litellm
            # LiteLLM 异步调用
            response = await litellm.acompletion(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            
            content = response["choices"][0]["message"]["content"]
            usage_data = response.get("usage", {})
            
            usage = LLMUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )
            usage.cost = _calculate_cost(self.model, usage)
            
            return LLMResponse(
                content=content,
                model=response.get("model", self.model),
                usage=usage,
                finish_reason=response["choices"][0].get("finish_reason"),
                raw_response=response,
            )
        except (ImportError, AttributeError, Exception) as e:
            # 如果 LiteLLM 调用失败，使用 mock
            logger.warning(f"LiteLLM call failed, using mock: {e}")
            return await MockLLMClient(self.model).complete(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
    
    async def chat(
        self,
        prompt: str,
        system: Optional[str] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        简单的聊天请求
        
        Args:
            prompt: 用户提示
            system: 系统提示
            **kwargs: 其他参数
        
        Returns:
            LLM 响应
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        return await self.complete(messages, **kwargs)
    
    def get_usage(self) -> LLMUsage:
        """获取总使用量"""
        return self._usage
    
    def reset_usage(self):
        """重置使用统计"""
        self._usage = LLMUsage()


class MockLLMClient:
    """Mock LLM 客户端（用于测试）"""
    
    def __init__(self, model: str):
        self.model = model
    
    async def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
    ) -> LLMResponse:
        """模拟完成请求"""
        await asyncio.sleep(0.1)  # 模拟网络延迟
        
        # 获取最后一条用户消息
        last_message = messages[-1]["content"] if messages else ""
        
        return LLMResponse(
            content=f"Mock response to: {last_message[:50]}...",
            model=self.model,
            usage=LLMUsage(
                prompt_tokens=len(last_message) // 4,
                completion_tokens=20,
                total_tokens=len(last_message) // 4 + 20,
                cost=0.001,
            ),
            finish_reason="stop",
        )


# 全局 LLM 客户端实例
_llm_client: Optional[LLMClient] = None


def get_llm_client(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> LLMClient:
    """获取或创建 LLM 客户端"""
    global _llm_client
    
    if _llm_client is None:
        _llm_client = LLMClient(
            model=model or "gpt-3.5-turbo",
            api_key=api_key,
        )
    
    return _llm_client


def reset_llm_client():
    """重置 LLM 客户端（用于测试）"""
    global _llm_client
    _llm_client = None
