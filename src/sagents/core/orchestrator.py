"""协调者模块 - 负责任务编排和调度"""
import asyncio
import logging
from typing import Optional

from .state import AgentType, Task, TaskStatus, AgentMessage, InvokeMode
from .message_bus import MessageBus, MessageBusRegistry
from .health_monitor import HealthMonitor, get_health_monitor
from .config import get_config
from ..tools.github_tool import GitHubTool

logger = logging.getLogger(__name__)


class Orchestrator:
    """协调者 - 负责任务编排和调度"""
    
    def __init__(
        self,
        message_bus: Optional[MessageBus] = None,
        health_monitor: Optional[HealthMonitor] = None,
        github_token: Optional[str] = None,
    ):
        self.message_bus = message_bus or MessageBusRegistry.get()
        self.health_monitor = health_monitor or get_health_monitor()
        self.config = get_config()
        self._wakeup_event = asyncio.Event()
        self._running = False
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._active_tasks: dict[str, Task] = {}
        
        # GitHub 集成
        self.github_tool = GitHubTool(token=github_token) if github_token else None
    
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
    
    async def merge_pr(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        merge_method: str = "squash",
    ) -> dict:
        """
        合并 PR
        
        Args:
            owner: 仓库所有者
            repo: 仓库名
            pr_number: PR 编号
            merge_method: 合并方式 (squash, merge, rebase)
        
        Returns:
            合并结果
        """
        logger.info(f"Merging PR #{pr_number} in {owner}/{repo}")
        
        if not self.github_tool:
            logger.warning("GitHub tool not initialized")
            return {"status": "failed", "error": "GitHub tool not initialized"}
        
        try:
            result = await self.github_tool.merge_pull_request(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                merge_method=merge_method,
            )
            logger.info(f"PR #{pr_number} merged successfully")
            return result
        except Exception as e:
            logger.error(f"Failed to merge PR: {e}")
            return {"status": "failed", "error": str(e)}
    
    async def create_branch(
        self,
        owner: str,
        repo: str,
        branch_name: str,
        base: str = "main",
    ) -> dict:
        """
        创建分支
        
        Args:
            owner: 仓库所有者
            repo: 仓库名
            branch_name: 分支名
            base: 基础分支
        
        Returns:
            创建结果
        """
        logger.info(f"Creating branch: {branch_name} from {base} in {owner}/{repo}")
        
        if not self.github_tool:
            logger.warning("GitHub tool not initialized")
            return {"status": "failed", "error": "GitHub tool not initialized"}
        
        try:
            result = await self.github_tool.create_branch(
                owner=owner,
                repo=repo,
                branch_name=branch_name,
                base_branch=base,
            )
            logger.info(f"Branch {branch_name} created successfully")
            return result
        except Exception as e:
            logger.error(f"Failed to create branch: {e}")
            return {"status": "failed", "error": str(e)}
    
    async def handle_webhook(self, event: dict) -> dict:
        """
        处理 webhook 事件
        
        Args:
            event: webhook 事件数据
        
        Returns:
            处理结果
        """
        event_type = event.get("type")
        action = event.get("action")
        
        logger.info(f"Handling webhook: {event_type} - {action}")
        
        if event_type == "pull_request":
            if action == "closed" and event.get("pull_request", {}).get("merged"):
                # PR 被合并
                pr = event["pull_request"]
                return {
                    "status": "pr_merged",
                    "pr_number": pr.get("number"),
                    "merged_by": pr.get("merged_by", {}).get("login"),
                }
            elif action == "opened":
                # 新 PR
                pr = event["pull_request"]
                return {
                    "status": "pr_opened",
                    "pr_number": pr.get("number"),
                    "author": pr.get("user", {}).get("login"),
                }
        
        return {"status": "ignored"}
    
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
