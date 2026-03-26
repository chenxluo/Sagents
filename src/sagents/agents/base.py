"""Agent 基类"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional

from ..core.state import AgentType, AgentStatus, AgentState, Task, AgentMessage
from ..core.message_bus import MessageBus
from ..core.health_monitor import HealthMonitor, get_health_monitor
from ..core.config import get_config, AgentPromptConfig

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Agent 基类"""
    
    def __init__(
        self,
        agent_type: AgentType,
        message_bus: Optional[MessageBus] = None,
        health_monitor: Optional[HealthMonitor] = None,
    ):
        self.agent_type = agent_type
        self.message_bus = message_bus
        self.health_monitor = health_monitor or get_health_monitor()
        self.config = get_config()
        
        self.state = AgentState(agent_type=agent_type)
        self._running = False
        self._task: Optional[Task] = None
        self._wakeup_event = asyncio.Event()
    
    async def start(self):
        """启动 Agent"""
        if self._running:
            return
        
        self._running = True
        if self.message_bus:
            await self.message_bus.start()
            self.message_bus.subscribe(self.agent_type, self._handle_message)
        
        self.state.status = AgentStatus.IDLE
        logger.info(f"{self.agent_type.value} started")
    
    async def stop(self):
        """停止 Agent"""
        self._running = False
        if self.message_bus:
            self.message_bus.unsubscribe(self.agent_type, self._handle_message)
        
        self.state.status = AgentStatus.IDLE
        logger.info(f"{self.agent_type.value} stopped")
    
    async def _handle_message(self, message: AgentMessage):
        """处理收到的消息"""
        logger.debug(f"[{self.agent_type.value}] Received message: {message.msg_type}")
        
        if message.msg_type.value == "invoke":
            await self._handle_invoke(message)
        elif message.msg_type.value == "notification":
            await self._handle_notification(message)
    
    async def _handle_invoke(self, message: AgentMessage):
        """处理 INVOKE 消息"""
        try:
            self.state.status = AgentStatus.WORKING
            result = await self.execute(message.content)
            
            if message.invoke_mode.value == "sync":
                await self.message_bus.send_response(message, result or {})
            else:
                await self.health_monitor.record_success(self.agent_type)
                
        except Exception as e:
            logger.error(f"[{self.agent_type.value}] Error executing task: {e}")
            await self.health_monitor.record_failure(self.agent_type, str(e))
            
            if message.invoke_mode.value == "sync":
                await self.message_bus.send_error(message, str(e))
            else:
                await self.message_bus.send(
                    sender=self.agent_type,
                    receiver=AgentType.ORCHESTRATOR,
                    content={
                        "action": "task_failed",
                        "task_id": message.content.get("task", {}).get("id"),
                        "error": str(e),
                    },
                )
        finally:
            self.state.status = AgentStatus.IDLE
    
    async def _handle_notification(self, message: AgentMessage):
        """处理 NOTIFICATION 消息"""
        content = message.content
        action = content.get("action")
        
        if action == "stop":
            await self.stop()
        elif action == "pause":
            self.state.status = AgentStatus.PAUSED
        elif action == "resume":
            self.state.status = AgentStatus.IDLE
        else:
            await self.handle_notification(action, content)
    
    @abstractmethod
    async def execute(self, content: dict) -> dict:
        """
        执行任务
        
        Args:
            content: 任务内容
        
        Returns:
            执行结果
        """
        pass
    
    async def handle_notification(self, action: str, content: dict):
        """处理通知（子类可覆盖）"""
        logger.debug(f"[{self.agent_type.value}] Notification: {action}")
    
    async def wait_for_work(self, timeout: Optional[int] = None) -> bool:
        """
        等待工作
        
        Args:
            timeout: 超时秒数
        
        Returns:
            是否被唤醒
        """
        self._wakeup_event.clear()
        self.state.status = AgentStatus.WAITING
        
        if timeout:
            try:
                await asyncio.wait_for(self._wakeup_event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                return False
        else:
            await self._wakeup_event.wait()
        
        self.state.status = AgentStatus.IDLE
        return True
    
    def wakeup(self):
        """唤醒 Agent"""
        self._wakeup_event.set()
    
    def get_prompt_config(self) -> AgentPromptConfig:
        """获取提示词配置"""
        prompts = self.config.prompts
        mapping = {
            AgentType.DEVELOPER: prompts.developer,
            AgentType.QA_ENGINEER: prompts.qa,
            AgentType.TECH_WRITER: prompts.tech_writer,
            AgentType.ORCHESTRATOR: prompts.orchestrator,
        }
        return mapping.get(self.agent_type, AgentPromptConfig())
    
    async def run(self):
        """运行 Agent 主循环"""
        await self.start()
        try:
            while self._running:
                await self.wait_for_work()
                if not self._running:
                    break
        finally:
            await self.stop()
