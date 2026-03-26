"""协调者测试"""
import asyncio
import pytest

from sagents.core.state import Task, TaskStatus, AgentType
from sagents.core.message_bus import MessageBus
from sagents.core.orchestrator import Orchestrator


@pytest.fixture
async def orchestrator():
    """创建协调者"""
    bus = MessageBus()
    await bus.start()
    orch = Orchestrator(message_bus=bus)
    await orch.start()
    yield orch
    await orch.stop()
    await bus.stop()


@pytest.mark.asyncio
async def test_orchestrator_start_stop():
    """测试协调者启动和停止"""
    bus = MessageBus()
    await bus.start()
    
    orch = Orchestrator(message_bus=bus)
    assert not orch._running
    
    await orch.start()
    assert orch._running
    
    await orch.stop()
    assert not orch._running
    
    await bus.stop()


@pytest.mark.asyncio
async def test_dispatch_task():
    """测试下发任务"""
    bus = MessageBus()
    await bus.start()
    
    # 添加一个测试处理器
    async def handler(message):
        if message.invoke_mode.value == "sync":
            await bus.send_response(message, {"status": "handled"})
    
    bus.subscribe(AgentType.DEVELOPER, handler)
    
    orch = Orchestrator(message_bus=bus)
    await orch.start()
    
    task = Task(
        title="Test Task",
        description="Test Description",
    )
    
    result = await orch.dispatch_task(
        task=task,
        agent_type=AgentType.DEVELOPER,
        sync=True,
    )
    
    assert result is not None
    
    await orch.stop()
    await bus.stop()


@pytest.mark.asyncio
async def test_dispatch_parallel_tasks():
    """测试并行下发任务"""
    bus = MessageBus()
    await bus.start()
    
    # 添加测试处理器
    async def handler(message):
        if message.invoke_mode.value == "sync":
            await bus.send_response(message, {"status": "handled"})
    
    bus.subscribe(AgentType.DEVELOPER, handler)
    bus.subscribe(AgentType.QA_ENGINEER, handler)
    
    orch = Orchestrator(message_bus=bus)
    await orch.start()
    
    tasks = [
        (Task(title="Task 1"), AgentType.DEVELOPER),
        (Task(title="Task 2"), AgentType.DEVELOPER),
    ]
    
    results = await orch.dispatch_parallel_tasks(tasks)
    
    assert len(results) == 2
    
    await orch.stop()
    await bus.stop()


@pytest.mark.asyncio
async def test_wakeup():
    """测试唤醒机制"""
    bus = MessageBus()
    await bus.start()
    
    orch = Orchestrator(message_bus=bus)
    await orch.start()
    
    # 唤醒协调者
    orch._wakeup_event.set()
    
    # 验证唤醒事件被设置
    await asyncio.sleep(0.1)
    assert orch._wakeup_event.is_set()
    
    await orch.stop()
    await bus.stop()
