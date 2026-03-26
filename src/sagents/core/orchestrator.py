"""协调者模块 - 负责任务编排和调度"""
import asyncio
import logging
from typing import Optional

from .state import AgentType, Task, TaskStatus, AgentMessage, InvokeMode
from .message_bus import MessageBus, MessageBusRegistry
from .health_monitor import HealthMonitor, get_health_monitor
from .config import get_config

logger = logging.getLogger(__name__)


class Orchestrator:
    """协调者 - 负责任务编排和调度"""
    
    def __init__(
        self,
        message_bus: Optional[MessageBus] = None,
        health_monitor: Optional[HealthMonitor] = None,
    ):
        self.message_bus = message_bus or MessageBusRegistry.get()
        self.health_monitor = health_monitor or get_health_monitor()
        self.config = get_config()
        self._wakeup_event = asyncio.Event()
        self._running = False
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._active_tasks: dict[str, Task] = {}
    
    async def start(self):
        """启动协调者"""
        self._running = True
        await self.message_bus.start()
        self.message_bus.subscribe(AgentType.ORCHESTRATOR, self._handle_message)
        logger.info("Orchestrator started")
    
    async def stop(self):
        """停止协调者"""
        self._running = False
        self.message_bus.unsubscribe(AgentType.ORCHESTRATOR, self._handle_message)
        logger.info("Orchestrator stopped")
    
    async def _handle_message(self, message: AgentMessage):
        """处理收到的消息"""
        if message.content.get("wake"):
            self._wakeup_event.set()
            logger.debug("Orchestrator woken up")
        
        if message.content.get("task_result"):
            await self._handle_task_result(message)
    
    async def _handle_task_result(self, message: AgentMessage):
        """处理任务结果"""
        task_id = message.content.get("task_id")
        if task_id and task_id in self._active_tasks:
            task = self._active_tasks.pop(task_id)
            task.status = TaskStatus.COMPLETED
            logger.info(f"Task {task_id} completed by {message.sender.value}")
    
    async def wait_for_work(self):
        """等待工作"""
        self._wakeup_event.clear()
        logger.debug("Orchestrator waiting for work...")
        await self._wakeup_event.wait()
    
    async def dispatch_task(
        self,
        task: Task,
        agent_type: AgentType,
        sync: bool = False,
    ) -> Optional[dict]:
        """
        下发任务给 Agent
        
        Args:
            task: 任务
            agent_type: 目标 Agent 类型
            sync: 是否同步等待
        
        Returns:
            同步模式下返回结果
        """
        mode = InvokeMode.SYNC if sync else InvokeMode.ASYNC
        timeout = self._get_timeout(agent_type)
        
        content = {
            "action": "execute_task",
            "task": task.model_dump(),
        }
        
        self._active_tasks[task.id] = task
        
        result = await self.message_bus.invoke(
            sender=AgentType.ORCHESTRATOR,
            receiver=agent_type,
            content=content,
            mode=mode,
            timeout=timeout,
        )
        
        if sync:
            await self.health_monitor.record_success(agent_type)
        
        return result
    
    async def dispatch_parallel_tasks(
        self,
        tasks: list[tuple[Task, AgentType]],
    ) -> list[Optional[dict]]:
        """
        下发并行任务
        
        Args:
            tasks: (任务, Agent类型) 列表
        
        Returns:
            结果列表
        """
        coroutines = [
            self.dispatch_task(task, agent_type, sync=False)
            for task, agent_type in tasks
        ]
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        return [r if not isinstance(r, Exception) else None for r in results]
    
    def _get_timeout(self, agent_type: AgentType) -> Optional[int]:
        """获取超时配置"""
        timeout_config = self.config.timeouts
        mapping = {
            AgentType.DEVELOPER: timeout_config.developer.max_seconds,
            AgentType.QA_ENGINEER: timeout_config.qa.max_seconds,
            AgentType.TECH_WRITER: timeout_config.tech_writer.max_seconds,
            AgentType.ORCHESTRATOR: timeout_config.orchestrator.max_seconds,
        }
        return mapping.get(agent_type)
    
    async def merge_pr(self, pr_url: str) -> bool:
        """
        合并 PR
        
        Args:
            pr_url: PR URL
        
        Returns:
            是否成功
        """
        logger.info(f"Merging PR: {pr_url}")
        # 这里会调用 GitHub API
        # TODO: 实现 GitHub API 调用
        return True
    
    async def create_branch(self, branch_name: str, base: str = "main") -> bool:
        """
        创建分支
        
        Args:
            branch_name: 分支名
            base: 基础分支
        
        Returns:
            是否成功
        """
        logger.info(f"Creating branch: {branch_name} from {base}")
        # TODO: 实现 GitHub API 调用
        return True
    
    async def notify_completion(self, agent_type: AgentType, task: Task):
        """通知任务完成"""
        await self.message_bus.send(
            sender=AgentType.ORCHESTRATOR,
            receiver=agent_type,
            content={
                "action": "task_completed",
                "task_id": task.id,
            },
        )
    
    async def run(self):
        """运行协调者主循环"""
        await self.start()
        try:
            while self._running:
                if self.health_monitor.is_paused():
                    logger.warning("System is paused, waiting for recovery...")
                    await asyncio.sleep(60)
                    continue
                
                await self.wait_for_work()
                await self._process_pending_work()
        finally:
            await self.stop()
    
    async def _process_pending_work(self):
        """处理待处理的工作"""
        while not self._task_queue.empty():
            try:
                task = self._task_queue.get_nowait()
                logger.info(f"Processing task: {task.title}")
            except asyncio.QueueEmpty:
                break


# 全局协调者实例
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """获取协调者实例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
