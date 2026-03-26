"""简单工作流程示例"""
import asyncio
import logging

from sagents.core.config import ConfigManager
from sagents.core.message_bus import MessageBusRegistry
from sagents.core.orchestrator import Orchestrator
from sagents.core.state import Task, TaskStatus, AgentType
from sagents.agents.developer import DeveloperAgent
from sagents.agents.qa_engineer import QAEngineerAgent
from sagents.agents.tech_writer import TechWriterAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def simple_workflow():
    """简单工作流程示例"""
    # 初始化配置
    config_manager = ConfigManager("./config")
    config = config_manager.load()
    
    # 初始化消息总线
    message_bus = MessageBusRegistry.get()
    await message_bus.start()
    
    # 初始化 Agent
    developer = DeveloperAgent(message_bus=message_bus)
    qa = QAEngineerAgent(message_bus=message_bus)
    tech_writer = TechWriterAgent(message_bus=message_bus)
    
    # 初始化协调者
    orchestrator = Orchestrator(message_bus=message_bus)
    
    # 启动所有组件
    await asyncio.gather(
        developer.start(),
        qa.start(),
        tech_writer.start(),
        orchestrator.start(),
    )
    
    logger.info("All agents started")
    
    # 创建示例任务
    task = Task(
        title="实现用户认证功能",
        description="实现基本的用户注册和登录功能",
        status=TaskStatus.PENDING,
    )
    
    # 下发任务给开发者
    logger.info(f"Dispatching task: {task.title}")
    result = await orchestrator.dispatch_task(
        task=task,
        agent_type=AgentType.DEVELOPER,
        sync=True,
    )
    
    logger.info(f"Task result: {result}")
    
    # 清理
    await asyncio.gather(
        developer.stop(),
        qa.stop(),
        tech_writer.stop(),
        orchestrator.stop(),
    )
    await message_bus.stop()
    
    logger.info("Workflow completed")


if __name__ == "__main__":
    asyncio.run(simple_workflow())
