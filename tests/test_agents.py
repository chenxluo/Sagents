"""Agent 测试"""
import asyncio
import pytest

from sagents.core.state import AgentType, AgentStatus, Task, TaskStatus
from sagents.core.message_bus import MessageBus
from sagents.agents.base import BaseAgent
from sagents.agents.developer import DeveloperAgent
from sagents.agents.qa_engineer import QAEngineerAgent
from sagents.agents.tech_writer import TechWriterAgent


class DummyAgent(BaseAgent):
    """用于测试的虚拟 Agent"""
    
    async def execute(self, content: dict) -> dict:
        return {"status": "executed", "content": content}


@pytest.mark.asyncio
async def test_base_agent_start_stop():
    """测试基础 Agent 启动和停止"""
    bus = MessageBus()
    await bus.start()
    
    agent = DummyAgent(
        agent_type=AgentType.DEVELOPER,
        message_bus=bus,
    )
    
    await agent.start()
    assert agent.state.status == AgentStatus.IDLE
    
    await agent.stop()
    assert agent.state.status == AgentStatus.IDLE
    
    await bus.stop()


@pytest.mark.asyncio
async def test_developer_agent_creation():
    """测试开发者 Agent 创建"""
    agent = DeveloperAgent()
    assert agent.agent_type == AgentType.DEVELOPER


@pytest.mark.asyncio
async def test_qa_agent_creation():
    """测试 QA Agent 创建"""
    agent = QAEngineerAgent()
    assert agent.agent_type == AgentType.QA_ENGINEER


@pytest.mark.asyncio
async def test_tech_writer_agent_creation():
    """测试文档维护者 Agent 创建"""
    agent = TechWriterAgent()
    assert agent.agent_type == AgentType.TECH_WRITER


@pytest.mark.asyncio
async def test_agent_execute_task():
    """测试 Agent 执行任务"""
    bus = MessageBus()
    await bus.start()
    
    agent = DeveloperAgent(message_bus=bus)
    await agent.start()
    
    content = {
        "action": "execute_task",
        "task": {
            "id": "test-1",
            "title": "Test Task",
            "description": "Test Description",
            "status": "pending",
        },
    }
    
    result = await agent.execute(content)
    
    # Agent 应该返回执行结果
    assert "status" in result
    
    await agent.stop()
    await bus.stop()


@pytest.mark.asyncio
async def test_agent_wait_for_work():
    """测试 Agent 等待工作"""
    bus = MessageBus()
    await bus.start()
    
    agent = DeveloperAgent(message_bus=bus)
    await agent.start()
    
    # 启动等待任务
    async def wait_and_wakeup():
        await asyncio.sleep(0.1)
        agent.wakeup()
    
    asyncio.create_task(wait_and_wakeup())
    
    result = await agent.wait_for_work(timeout=1)
    
    assert result is True
    
    await agent.stop()
    await bus.stop()


@pytest.mark.asyncio
async def test_agent_handle_invoke():
    """测试 Agent 处理 INVOKE 消息"""
    from sagents.core.state import AgentMessage, MessageType, InvokeMode
    
    bus = MessageBus()
    await bus.start()
    
    agent = DeveloperAgent(message_bus=bus)
    await agent.start()
    
    message = AgentMessage(
        msg_type=MessageType.INVOKE,
        sender=AgentType.ORCHESTRATOR,
        receiver=AgentType.DEVELOPER,
        content={
            "action": "execute_task",
            "task": {
                "id": "test-1",
                "title": "Test",
                "status": "pending",
            },
        },
        invoke_mode=InvokeMode.ASYNC,
    )
    
    await agent._handle_message(message)
    
    # 等待异步执行完成
    await asyncio.sleep(0.2)
    
    await agent.stop()
    await bus.stop()
