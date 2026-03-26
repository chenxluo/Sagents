"""消息总线模块 - Agent 间异步通信"""
import asyncio
import logging
from typing import Callable, Optional
from collections import defaultdict

from .state import AgentMessage, AgentType, MessageType, InvokeMode

logger = logging.getLogger(__name__)


class MessageBus:
    """异步消息总线，支持 SYNC/ASYNC 模式"""
    
    def __init__(self):
        self._subscribers: dict[AgentType, list[Callable]] = defaultdict(list)
        self._pending_responses: dict[str, asyncio.Future] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """启动消息总线"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._process_messages())
        logger.info("MessageBus started")
    
    async def stop(self):
        """停止消息总线"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("MessageBus stopped")
    
    async def _process_messages(self):
        """消息处理循环"""
        while self._running:
            try:
                message = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)
                await self._dispatch_message(message)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing message: {e}")
    
    async def _dispatch_message(self, message: AgentMessage):
        """分发消息到订阅者"""
        # 查找接收者的订阅者
        handlers = self._subscribers.get(message.receiver, [])
        
        # 同时通知所有订阅者
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error(f"Error in message handler: {e}")
        
        # 如果是 INVOKE 消息且需要响应
        if message.msg_type == MessageType.INVOKE and message.invoke_mode == InvokeMode.SYNC:
            # 响应将在响应方调用 send_response 时处理
            pass
    
    async def invoke(
        self,
        sender: AgentType,
        receiver: AgentType,
        content: dict,
        mode: InvokeMode = InvokeMode.ASYNC,
        timeout: Optional[int] = None,
    ) -> Optional[dict]:
        """
        发送 INVOKE 消息
        
        Args:
            sender: 发送方
            receiver: 接收方
            content: 消息内容
            mode: 调用模式 (SYNC/ASYNC)
            timeout: 超时秒数
        
        Returns:
            SYNC 模式返回响应内容，ASYNC 模式返回 None
        """
        message = AgentMessage(
            msg_type=MessageType.INVOKE,
            sender=sender,
            receiver=receiver,
            content=content,
            invoke_mode=mode,
        )
        
        if mode == InvokeMode.SYNC:
            # 创建 Future 等待响应
            future = asyncio.get_event_loop().create_future()
            self._pending_responses[message.id] = future
            message.correlation_id = message.id
            
            await self._message_queue.put(message)
            
            try:
                if timeout:
                    response = await asyncio.wait_for(future, timeout=timeout)
                else:
                    response = await future
                return response.get("result") if response else None
            except asyncio.TimeoutError:
                logger.warning(f"SYNC invoke timeout: {message.id}")
                self._pending_responses.pop(message.id, None)
                return None
        else:
            # ASYNC 模式，立即返回
            await self._message_queue.put(message)
            return None
    
    async def send(
        self,
        sender: AgentType,
        receiver: AgentType,
        content: dict,
    ):
        """
        发送通知 (Fire-Forget)
        
        Args:
            sender: 发送方
            receiver: 接收方
            content: 消息内容
        """
        message = AgentMessage(
            msg_type=MessageType.NOTIFICATION,
            sender=sender,
            receiver=receiver,
            content=content,
        )
        await self._message_queue.put(message)
    
    async def send_response(
        self,
        original_message: AgentMessage,
        result: dict,
    ):
        """
        发送响应消息
        
        Args:
            original_message: 原始消息
            result: 响应内容
        """
        if original_message.correlation_id and original_message.correlation_id in self._pending_responses:
            future = self._pending_responses.pop(original_message.correlation_id)
            response = AgentMessage(
                msg_type=MessageType.RESPONSE,
                sender=original_message.receiver,
                receiver=original_message.sender,
                content={"result": result, "original_id": original_message.id},
                correlation_id=original_message.correlation_id,
            )
            future.set_result({"result": result, "message": response})
    
    async def send_error(
        self,
        original_message: AgentMessage,
        error: str,
    ):
        """
        发送错误消息
        
        Args:
            original_message: 原始消息
            error: 错误信息
        """
        if original_message.correlation_id and original_message.correlation_id in self._pending_responses:
            future = self._pending_responses.pop(original_message.correlation_id)
            future.set_exception(Exception(error))
        else:
            error_message = AgentMessage(
                msg_type=MessageType.ERROR,
                sender=original_message.receiver,
                receiver=original_message.sender,
                content={"error": error},
                correlation_id=original_message.correlation_id,
            )
            await self._message_queue.put(error_message)
    
    def subscribe(self, agent_type: AgentType, handler: Callable):
        """
        订阅消息
        
        Args:
            agent_type: Agent 类型
            handler: 消息处理函数
        """
        self._subscribers[agent_type].append(handler)
        logger.debug(f"Agent {agent_type} subscribed to messages")
    
    def unsubscribe(self, agent_type: AgentType, handler: Callable):
        """
        取消订阅
        
        Args:
            agent_type: Agent 类型
            handler: 消息处理函数
        """
        if handler in self._subscribers[agent_type]:
            self._subscribers[agent_type].remove(handler)
    
    async def wait_for_wakeup(
        self,
        agent_type: AgentType,
        event: asyncio.Event,
        timeout: Optional[int] = None,
    ) -> bool:
        """
        等待唤醒
        
        Args:
            agent_type: Agent 类型
            event: 唤醒事件
            timeout: 超时秒数
        
        Returns:
            是否被唤醒
        """
        try:
            if timeout:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            else:
                await event.wait()
            return True
        except asyncio.TimeoutError:
            return False


class MessageBusRegistry:
    """消息总线注册表"""
    _instances: dict[str, MessageBus] = {}
    
    @classmethod
    def get(cls, name: str = "default") -> MessageBus:
        """获取消息总线实例"""
        if name not in cls._instances:
            cls._instances[name] = MessageBus()
        return cls._instances[name]
    
    @classmethod
    def create(cls, name: str = "default") -> MessageBus:
        """创建新的消息总线"""
        if name in cls._instances:
            raise ValueError(f"MessageBus '{name}' already exists")
        cls._instances[name] = MessageBus()
        return cls._instances[name]
    
    @classmethod
    async def start_all(cls):
        """启动所有消息总线"""
        for bus in cls._instances.values():
            await bus.start()
    
    @classmethod
    async def stop_all(cls):
        """停止所有消息总线"""
        for bus in cls._instances.values():
            await bus.stop()
        cls._instances.clear()
