"""测试者 Agent"""
import asyncio
import logging
import re
from typing import Optional

from ..core.state import AgentType, Task, AgentMessage, InvokeMode
from ..core.message_bus import MessageBus
from ..tools.terminal_tool import TerminalTool
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
        
        # 初始化工具
        self.terminal_tool = TerminalTool(workspace_path=self.workspace_path)
    
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
        
        test_path = self._test_context.get("test_path", str(self.workspace_path))
        
        try:
            result = await self.terminal_tool.run_tests(
                test_path=test_path,
                framework="pytest",
                options=["-v", "--tb=short", "-m", "not integration"],
            )
            
            # 解析 pytest 输出
            passed, total, failures = self._parse_pytest_output(result)
            
            return {
                "type": "unit",
                "tests_run": total,
                "tests_passed": passed,
                "tests_failed": failures,
                "passed": failures == 0,
                "output": result.get("stdout", "")[:2000],
            }
        except Exception as e:
            logger.error(f"Unit tests failed: {e}")
            return {
                "type": "unit",
                "tests_run": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "passed": False,
                "error": str(e),
            }
    
    async def _run_integration_tests(self) -> dict:
        """运行集成测试"""
        logger.info("Running integration tests...")
        
        test_path = self._test_context.get("test_path", str(self.workspace_path))
        
        try:
            result = await self.terminal_tool.run_tests(
                test_path=test_path,
                framework="pytest",
                options=["-v", "--tb=short", "-m", "integration"],
            )
            
            # 如果没有集成测试标记文件，则跳过
            if "no tests ran" in result.get("stdout", "").lower() or result.get("returncode") == 5:
                return {
                    "type": "integration",
                    "tests_run": 0,
                    "tests_passed": 0,
                    "tests_failed": 0,
                    "passed": True,
                    "skipped": True,
                    "message": "No integration tests found",
                }
            
            passed, total, failures = self._parse_pytest_output(result)
            
            return {
                "type": "integration",
                "tests_run": total,
                "tests_passed": passed,
                "tests_failed": failures,
                "passed": failures == 0,
                "output": result.get("stdout", "")[:2000],
            }
        except Exception as e:
            logger.error(f"Integration tests failed: {e}")
            return {
                "type": "integration",
                "tests_run": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "passed": False,
                "error": str(e),
            }
    
    async def _run_regression_tests(self) -> dict:
        """运行回归测试"""
        logger.info("Running regression tests...")
        
        test_path = self._test_context.get("test_path", str(self.workspace_path))
        
        try:
            # 运行所有测试
            result = await self.terminal_tool.run_tests(
                test_path=test_path,
                framework="pytest",
                options=["-v", "--tb=short"],
            )
            
            passed, total, failures = self._parse_pytest_output(result)
            
            return {
                "type": "regression",
                "tests_run": total,
                "tests_passed": passed,
                "tests_failed": failures,
                "passed": failures == 0,
                "output": result.get("stdout", "")[:2000],
            }
        except Exception as e:
            logger.error(f"Regression tests failed: {e}")
            return {
                "type": "regression",
                "tests_run": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "passed": False,
                "error": str(e),
            }
    
    def _parse_pytest_output(self, result: dict) -> tuple[int, int, int]:
        """解析 pytest 输出"""
        output = result.get("stdout", "") + result.get("stderr", "")
        
        # 匹配 "X passed" 或 "X passed, Y failed"
        passed_match = re.search(r"(\d+) passed", output)
        failed_match = re.search(r"(\d+) failed", output)
        
        passed = int(passed_match.group(1)) if passed_match else 0
        failed = int(failed_match.group(1)) if failed_match else 0
        total = passed + failed
        
        return passed, total, failed
    
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
        
        issues = []
        
        # 使用 ruff 检查代码风格
        try:
            result = await self.terminal_tool.run_command(
                ["ruff", "check", str(self.workspace_path), "--output-format=text"],
            )
            
            if result.get("returncode") != 0:
                output = result.get("stdout", "") + result.get("stderr", "")
                for line in output.split("\n"):
                    if line.strip():
                        issues.append({
                            "tool": "ruff",
                            "severity": "warning",
                            "message": line.strip(),
                        })
        except Exception as e:
            logger.warning(f"Ruff check failed: {e}")
        
        # 使用 pylint 检查
        try:
            result = await self.terminal_tool.run_command(
                ["pylint", str(self.workspace_path), "--output-format=text"],
            )
            
            if result.get("returncode") != 0:
                output = result.get("stdout", "") + result.get("stderr", "")
                for line in output.split("\n"):
                    if ":" in line and "error" in line.lower():
                        issues.append({
                            "tool": "pylint",
                            "severity": "error",
                            "message": line.strip(),
                        })
        except Exception as e:
            logger.warning(f"Pylint check failed: {e}")
        
        return {
            "passed": len([i for i in issues if i.get("severity") == "error"]) == 0,
            "issues": issues,
            "severity": "error" if issues else "info",
        }
    
    async def _check_code_quality(self) -> dict:
        """检查代码质量"""
        logger.info("Checking code quality...")
        
        score = 10.0
        issues = []
        
        # 使用 radon 计算代码复杂度
        try:
            result = await self.terminal_tool.run_command(
                ["radon", "cc", str(self.workspace_path), "-a"],
            )
            
            output = result.get("stdout", "")
            if "Average complexity" in output:
                # 提取平均复杂度
                import re
                match = re.search(r"Average complexity: ([\d.]+)", output)
                if match:
                    avg_complexity = float(match.group(1))
                    if avg_complexity > 10:
                        score -= 2
                        issues.append({
                            "type": "complexity",
                            "severity": "warning",
                            "message": f"High average complexity: {avg_complexity}",
                        })
        except Exception as e:
            logger.warning(f"Radon complexity check failed: {e}")
        
        # 使用 flake8 检查
        try:
            result = await self.terminal_tool.run_command(
                ["flake8", str(self.workspace_path), "--count"],
            )
            
            if result.get("returncode") != 0:
                output = result.get("stdout", "")
                error_count = len(output.strip().split("\n"))
                score -= min(error_count * 0.1, 2)
                issues.append({
                    "type": "flake8",
                    "severity": "info",
                    "message": f"{error_count} flake8 warnings",
                })
        except Exception as e:
            logger.warning(f"Flake8 check failed: {e}")
        
        return {
            "passed": score >= 7.0,
            "issues": issues,
            "score": max(0, score),
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
        
        vulnerabilities = []
        
        # 使用 bandit 进行安全扫描
        try:
            result = await self.terminal_tool.run_command(
                ["bandit", "-r", str(self.workspace_path), "-f", "json"],
            )
            
            output = result.get("stdout", "")
            import json
            try:
                bandit_output = json.loads(output)
                for issue in bandit_output.get("results", []):
                    vulnerabilities.append({
                        "severity": issue.get("issue_severity", "LOW"),
                        "confidence": issue.get("issue_confidence", "LOW"),
                        "file": issue.get("filename"),
                        "line": issue.get("line_number"),
                        "description": issue.get("issue_text"),
                    })
            except json.JSONDecodeError:
                # 如果不是 JSON，解析文本输出
                for line in output.split("\n"):
                    if ">>" in line or "severity:" in line.lower():
                        vulnerabilities.append({
                            "severity": "MEDIUM",
                            "message": line.strip(),
                        })
        except Exception as e:
            logger.warning(f"Bandit security scan failed: {e}")
        
        # 使用 safety 检查依赖漏洞
        try:
            result = await self.terminal_tool.run_command(
                ["safety", "check", "--json"],
            )
            
            if result.get("returncode") != 0:
                output = result.get("stdout", "")
                import json
                try:
                    safety_output = json.loads(output)
                    for vuln in safety_output:
                        vulnerabilities.append({
                            "severity": "HIGH",
                            "type": "dependency",
                            "package": vuln.get("package"),
                            "vulnerability": vuln.get("vulnerability"),
                        })
                except json.JSONDecodeError:
                    for line in output.split("\n"):
                        if line.strip():
                            vulnerabilities.append({
                                "severity": "HIGH",
                                "type": "dependency",
                                "message": line.strip(),
                            })
        except Exception as e:
            logger.warning(f"Safety dependency check failed: {e}")
        
        return {
            "status": "completed",
            "vulnerabilities": vulnerabilities,
            "passed": len([v for v in vulnerabilities if v.get("severity") in ("HIGH", "MEDIUM")]) == 0,
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
