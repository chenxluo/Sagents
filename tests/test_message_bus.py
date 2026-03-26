"""消息总线测试"""
import asyncio
import pytest

from sagents.core.state import AgentType, MessageType, InvokeMode, AgentMessage
from sagents.core.message_bus import MessageBus


@pytest.fixture
def message_bus():
    """创建消息总线"""
    bus = MessageBus()
    return bus


@pytest.fixture
async def running_bus():
    """创建并启动消息总线"""
    bus = MessageBus()
    await bus.start()
    yield bus
    await bus.stop()


@pytest.mark.asyncio
async def test_message_bus_start_stop():
    """测试消息总线启动和停止"""
    bus = MessageBus()
    assert not bus._running
    
    await bus.start()
    assert bus._running
    
    await bus.stop()
    assert not bus._running


@pytest.mark.asyncio
async def test_message_subscription():
    """测试消息订阅"""
    bus = MessageBus()
    await bus.start()
    
    received = []
    
    async def handler(message):
        received.append(message)
    
    bus.subscribe(AgentType.DEVELOPER, handler)
    
    # 发送消息
    message = AgentMessage(
        msg_type=MessageType.NOTIFICATION,
        sender=AgentType.ORCHESTRATOR,
        receiver=AgentType.DEVELOPER,
        content={"test": "data"},
    )
    await bus._message_queue.put(message)
    
    # 等待消息处理
    await asyncio.sleep(0.1)
    
    assert len(received) == 1
    assert received[0].content["test"] == "data"
    
    await bus.stop()


@pytest.mark.asyncio
async def test_async_invoke():
    """测试异步调用"""
    bus = MessageBus()
    await bus.start()
    
    async def handler(message):
        # 模拟处理
        await asyncio.sleep(0.05)
    
    bus.subscribe(AgentType.DEVELOPER, handler)
    
    # ASYNC 调用
    result = await bus.invoke(
        sender=AgentType.ORCHESTRATOR,
        receiver=AgentType.DEVELOPER,
        content={"action": "test"},
        mode=InvokeMode.ASYNC,
    )
    
    assert result is None  # ASYNC 立即返回
    
    await bus.stop()


@pytest.mark.asyncio
async def test_sync_invoke():
    """测试同步调用"""
    bus = MessageBus()
    await bus.start()
    
    async def handler(message):
        if message.invoke_mode == InvokeMode.SYNC:
            await bus.send_response(message, {"result": "success"})
    
    bus.subscribe(AgentType.DEVELOPER, handler)
    
    # SYNC 调用
    result = await bus.invoke(
        sender=AgentType.ORCHESTRATOR,
        receiver=AgentType.DEVELOPER,
        content={"action": "test"},
        mode=InvokeMode.SYNC,
        timeout=5,
    )
    
    # 返回的是 {"result": "success"} 字典
    assert result == {"result": "success"}
    
    await bus.stop()


@pytest.mark.asyncio
async def test_notification():
    """测试通知发送"""
    bus = MessageBus()
    await bus.start()
    
    received = []
    
    async def handler(message):
        received.append(message)
    
    bus.subscribe(AgentType.DEVELOPER, handler)
    
    await bus.send(
        sender=AgentType.ORCHESTRATOR,
        receiver=AgentType.DEVELOPER,
        content={"action": "notify"},
    )
    
    await asyncio.sleep(0.1)
    
    assert len(received) == 1
    assert received[0].msg_type == MessageType.NOTIFICATION
    
    await bus.stop()
