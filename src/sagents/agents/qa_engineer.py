"""测试者 Agent"""
import asyncio
import logging
from typing import Optional

from ..core.state import AgentType, Task, AgentMessage, InvokeMode
from ..core.message_bus import MessageBus
from .base import BaseAgent

logger = logging.getLogger(__name__)


class QAEngineerAgent(BaseAgent):
    """测试者 Agent"""
    
    def __init__(
        self,
        message_bus: Optional[MessageBus] = None,
        workspace_path: Optional[str] = None,
    ):
        super().__init__(
            agent_type=AgentType.QA_ENGINEER,
            message_bus=message_bus,
        )
        self.workspace_path = workspace_path or "./workspace"
        self._test_context: dict = {}
    
    async def execute(self, content: dict) -> dict:
        """
        执行测试任务
        
        Args:
            content: 任务内容
                - action: 操作类型
                - pr_url: PR URL
                - test_type: 测试类型
        
        Returns:
            测试结果
        """
        action = content.get("action")
        
        if action == "run_tests":
            return await self._run_all_tests(content)
        
        elif action == "code_review":
            return await self._code_review(content)
        
        elif action == "security_scan":
            return await self._security_scan(content)
        
        else:
            logger.warning(f"Unknown action: {action}")
            return {"status": "unknown_action", "action": action}
    
    async def _run_all_tests(self, content: dict) -> dict:
        """运行全套测试"""
        logger.info("Running all tests...")
        
        # 1. 单元测试
        unit_result = await self._run_unit_tests()
        
        # 2. 集成测试
        integration_result = await self._run_integration_tests()
        
        # 3. 回归测试
        regression_result = await self._run_regression_tests()
        
        # 汇总结果
        all_passed = all([
            unit_result.get("passed"),
            integration_result.get("passed"),
            regression_result.get("passed"),
        ])
        
        result = {
            "status": "completed",
            "unit_tests": unit_result,
            "integration_tests": integration_result,
            "regression_tests": regression_result,
            "overall_passed": all_passed,
        }
        
        # 通知协调者
        await self._notify_result(content, result)
        
        return result
    
    async def _run_unit_tests(self) -> dict:
        """运行单元测试"""
        logger.info("Running unit tests...")
        # TODO: 调用 pytest 或其他测试框架
        await asyncio.sleep(0.1)
        
        return {
            "type": "unit",
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "passed": True,
            "duration_seconds": 0,
        }
    
    async def _run_integration_tests(self) -> dict:
        """运行集成测试"""
        logger.info("Running integration tests...")
        # TODO: 运行集成测试
        await asyncio.sleep(0.1)
        
        return {
            "type": "integration",
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "passed": True,
            "duration_seconds": 0,
        }
    
    async def _run_regression_tests(self) -> dict:
        """运行回归测试"""
        logger.info("Running regression tests...")
        # TODO: 运行回归测试
        await asyncio.sleep(0.1)
        
        return {
            "type": "regression",
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "passed": True,
            "duration_seconds": 0,
        }
    
    async def _code_review(self, content: dict) -> dict:
        """代码评审"""
        logger.info("Performing code review...")
        
        # 1. 代码风格检查
        style_result = await self._check_code_style()
        
        # 2. 代码质量检查
        quality_result = await self._check_code_quality()
        
        # 3. 生成评审报告
        report = await self._generate_review_report(style_result, quality_result)
        
        return report
    
    async def _check_code_style(self) -> dict:
        """检查代码风格"""
        logger.info("Checking code style...")
        # TODO: 调用 ruff, pylint 等
        await asyncio.sleep(0.1)
        
        return {
            "passed": True,
            "issues": [],
            "severity": "info",
        }
    
    async def _check_code_quality(self) -> dict:
        """检查代码质量"""
        logger.info("Checking code quality...")
        # TODO: 调用代码质量工具
        await asyncio.sleep(0.1)
        
        return {
            "passed": True,
            "issues": [],
            "score": 10.0,
        }
    
    async def _generate_review_report(self, style: dict, quality: dict) -> dict:
        """生成评审报告"""
        issues = style.get("issues", []) + quality.get("issues", [])
        
        return {
            "status": "completed",
            "style_check": style,
            "quality_check": quality,
            "total_issues": len(issues),
            "blocking_issues": [i for i in issues if i.get("severity") == "error"],
            "report": f"Code review completed. Found {len(issues)} issues.",
        }
    
    async def _security_scan(self, content: dict) -> dict:
        """安全扫描"""
        logger.info("Running security scan...")
        # TODO: 调用安全扫描工具
        await asyncio.sleep(0.1)
        
        return {
            "status": "completed",
            "vulnerabilities": [],
            "passed": True,
        }
    
    async def _notify_result(self, original_content: dict, result: dict):
        """通知测试结果"""
        pr_url = original_content.get("pr_url")
        task_id = original_content.get("task_id")
        
        if result.get("overall_passed"):
            # 测试通过，通知协调者
            await self.message_bus.send(
                sender=self.agent_type,
                receiver=AgentType.ORCHESTRATOR,
                content={
                    "action": "tests_passed",
                    "task_id": task_id,
                    "pr_url": pr_url,
                    "result": result,
                },
            )
        else:
            # 测试失败，直接返工给开发者
            await self.message_bus.send(
                sender=self.agent_type,
                receiver=AgentType.DEVELOPER,
                content={
                    "action": "retry_task",
                    "task_id": task_id,
                    "pr_url": pr_url,
                    "test_result": result,
                    "message": "Tests failed, please fix and resubmit.",
                },
            )
    
    async def handle_notification(self, action: str, content: dict):
        """处理通知"""
        if action == "run_tests":
            await self._run_all_tests(content)
        elif action == "code_review":
            await self._code_review(content)
