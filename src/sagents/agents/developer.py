"""开发者 Agent"""
import asyncio
import logging
from typing import Optional

from ..core.state import AgentType, Task, AgentMessage, InvokeMode
from ..core.message_bus import MessageBus, MessageBusRegistry
from .base import BaseAgent

logger = logging.getLogger(__name__)


class DeveloperAgent(BaseAgent):
    """开发者 Agent"""
    
    def __init__(
        self,
        message_bus: Optional[MessageBus] = None,
        github_token: Optional[str] = None,
        workspace_path: Optional[str] = None,
    ):
        super().__init__(
            agent_type=AgentType.DEVELOPER,
            message_bus=message_bus,
        )
        self.github_token = github_token
        self.workspace_path = workspace_path or "./workspace"
        self._context: dict = {}
    
    async def execute(self, content: dict) -> dict:
        """
        执行开发任务
        
        Args:
            content: 任务内容
                - action: 操作类型
                - task: 任务详情
                - code_context: 代码上下文
        
        Returns:
            执行结果
        """
        action = content.get("action")
        
        if action == "execute_task":
            task_data = content.get("task", {})
            task = Task(**task_data) if task_data else None
            return await self._execute_development_task(task)
        
        elif action == "fix_issue":
            issue = content.get("issue", {})
            return await self._fix_issue(issue)
        
        elif action == "create_pr":
            return await self._create_pull_request(content)
        
        else:
            logger.warning(f"Unknown action: {action}")
            return {"status": "unknown_action", "action": action}
    
    async def _execute_development_task(self, task: Optional[Task]) -> dict:
        """执行开发任务"""
        if not task:
            return {"status": "error", "message": "No task provided"}
        
        logger.info(f"Executing development task: {task.title}")
        
        # 1. 分析任务
        self._context["task"] = task
        
        # 2. 规划实现步骤 (这里会调用 LLM)
        steps = await self._plan_implementation(task)
        
        # 3. 逐步执行
        results = []
        for step in steps:
            result = await self._execute_step(step)
            results.append(result)
            if result.get("failed"):
                await self._handle_step_failure(step, result)
        
        # 4. 运行测试
        test_result = await self._run_tests()
        
        # 5. 提交代码
        if all(not r.get("failed") for r in results):
            pr_result = await self._create_pull_request({"task": task})
            return {
                "status": "success",
                "task_id": task.id,
                "steps": results,
                "test_result": test_result,
                "pr_url": pr_result.get("pr_url"),
            }
        else:
            return {
                "status": "partial_success",
                "task_id": task.id,
                "steps": results,
            }
    
    async def _plan_implementation(self, task: Task) -> list[dict]:
        """规划实现步骤"""
        # TODO: 调用 LLM 生成实现计划
        logger.info(f"Planning implementation for: {task.title}")
        
        # 模拟返回步骤
        return [
            {"type": "analyze", "description": "分析需求"},
            {"type": "write_code", "description": "编写代码"},
            {"type": "write_tests", "description": "编写测试"},
            {"type": "validate", "description": "验证代码"},
        ]
    
    async def _execute_step(self, step: dict) -> dict:
        """执行单个步骤"""
        step_type = step.get("type")
        
        if step_type == "analyze":
            return await self._analyze_requirement(step)
        elif step_type == "write_code":
            return await self._write_code(step)
        elif step_type == "write_tests":
            return await self._write_tests(step)
        elif step_type == "validate":
            return await self._validate_code(step)
        else:
            return {"type": step_type, "status": "skipped"}
    
    async def _analyze_requirement(self, step: dict) -> dict:
        """分析需求"""
        await asyncio.sleep(0.1)  # 模拟分析
        return {"type": "analyze", "status": "completed"}
    
    async def _write_code(self, step: dict) -> dict:
        """编写代码"""
        # TODO: 调用 LLM 编写代码
        await asyncio.sleep(0.1)  # 模拟编写
        return {"type": "write_code", "status": "completed"}
    
    async def _write_tests(self, step: dict) -> dict:
        """编写测试"""
        # TODO: 调用 LLM 编写测试
        await asyncio.sleep(0.1)  # 模拟编写
        return {"type": "write_tests", "status": "completed"}
    
    async def _validate_code(self, step: dict) -> dict:
        """验证代码"""
        # TODO: 运行 linter, type checker 等
        await asyncio.sleep(0.1)  # 模拟验证
        return {"type": "validate", "status": "completed"}
    
    async def _handle_step_failure(self, step: dict, result: dict):
        """处理步骤失败"""
        error = result.get("error", "Unknown error")
        logger.error(f"Step failed: {step.get('description')}, error: {error}")
        
        # 通知协调者
        await self.message_bus.send(
            sender=self.agent_type,
            receiver=AgentType.ORCHESTRATOR,
            content={
                "action": "step_failed",
                "step": step,
                "error": error,
            },
        )
    
    async def _run_tests(self) -> dict:
        """运行测试"""
        # TODO: 调用测试框架运行测试
        logger.info("Running tests...")
        await asyncio.sleep(0.1)
        return {"status": "passed", "tests": 0, "failures": 0}
    
    async def _fix_issue(self, issue: dict) -> dict:
        """修复问题"""
        logger.info(f"Fixing issue: {issue.get('title')}")
        # TODO: 分析问题并修复
        return {"status": "fixed", "issue_id": issue.get("id")}
    
    async def _create_pull_request(self, content: dict) -> dict:
        """创建 PR"""
        logger.info("Creating pull request...")
        # TODO: 调用 GitHub API 创建 PR
        return {
            "status": "created",
            "pr_url": f"https://github.com/example/repo/pull/1",
            "pr_number": 1,
        }
    
    async def handle_notification(self, action: str, content: dict):
        """处理通知"""
        if action == "retry_task":
            task_data = content.get("task")
            if task_data:
                task = Task(**task_data)
                result = await self._execute_development_task(task)
                await self.message_bus.send(
                    sender=self.agent_type,
                    receiver=AgentType.QA_ENGINEER,
                    content={"action": "task_completed", "result": result},
                )
