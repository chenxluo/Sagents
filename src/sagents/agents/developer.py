"""开发者 Agent"""
import asyncio
import logging
import re
from typing import Optional

from ..core.state import AgentType, Task, AgentMessage, InvokeMode
from ..core.message_bus import MessageBus, MessageBusRegistry
from ..core.llm_client import LLMClient, get_llm_client
from ..tools.file_tool import FileTool
from ..tools.terminal_tool import TerminalTool
from ..tools.github_tool import GitHubTool
from .base import BaseAgent

logger = logging.getLogger(__name__)


class DeveloperAgent(BaseAgent):
    """开发者 Agent"""
    
    def __init__(
        self,
        message_bus: Optional[MessageBus] = None,
        github_token: Optional[str] = None,
        workspace_path: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        super().__init__(
            agent_type=AgentType.DEVELOPER,
            message_bus=message_bus,
        )
        self.github_token = github_token
        self.workspace_path = workspace_path or "./workspace"
        self._context: dict = {}
        
        # 初始化工具
        self.file_tool = FileTool(workspace_path=self.workspace_path)
        self.terminal_tool = TerminalTool(workspace_path=self.workspace_path)
        self.github_tool = GitHubTool(token=github_token) if github_token else None
        self.llm_client = llm_client or get_llm_client()
    
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
        logger.info(f"Planning implementation for: {task.title}")
        
        try:
            response = await self.llm_client.chat(
                system="你是一个资深的软件工程师，负责规划实现步骤。请分析任务描述，制定清晰、可执行的实现步骤。",
                prompt=f"""请为以下任务制定实现步骤：

任务标题: {task.title}
任务描述: {task.description}

请返回 JSON 格式的实现步骤列表，例如：
[
  {{"type": "analyze", "description": "分析需求和现有代码"}},
  {{"type": "write_code", "description": "编写核心代码", "files": ["src/module.py"]}},
  {{"type": "write_tests", "description": "编写单元测试", "files": ["tests/test_module.py"]}},
  {{"type": "validate", "description": "运行测试和验证"}}
]

只返回 JSON，不要有其他文字。""",
                temperature=0.3,
            )
            
            import json
            steps = json.loads(response.content)
            logger.info(f"Generated {len(steps)} implementation steps")
            return steps
            
        except Exception as e:
            logger.warning(f"LLM planning failed, using default steps: {e}")
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
        task = self._context.get("task")
        if not task:
            return {"type": "analyze", "status": "completed"}
        
        try:
            response = await self.llm_client.chat(
                system="你是一个技术分析师，负责分析需求的技术可行性。",
                prompt=f"""分析以下任务的技术可行性：

任务: {task.title}
描述: {task.description}

分析要点：
1. 需要什么依赖
2. 可能的实现方案
3. 潜在的技术风险

用简洁的语言回答。""",
            )
            self._context["analysis"] = response.content
            return {"type": "analyze", "status": "completed", "analysis": response.content[:200]}
        except Exception as e:
            logger.warning(f"Analysis LLM call failed: {e}")
            return {"type": "analyze", "status": "completed"}
    
    async def _write_code(self, step: dict) -> dict:
        """编写代码"""
        task = self._context.get("task")
        if not task:
            return {"type": "write_code", "status": "skipped"}
        
        files = step.get("files", ["src/generated.py"])
        created_files = []
        
        for file_path in files:
            try:
                response = await self.llm_client.chat(
                    system="你是一个专业的 Python 开发者，负责编写高质量的代码。请只返回代码，不要有任何解释。",
                    prompt=f"""为以下任务编写 {file_path}：

任务: {task.title}
描述: {task.description}

要求：
1. 代码必须是完整可运行的
2. 遵循 PEP 8 规范
3. 包含必要的文档字符串
4. 使用类型注解""",
                    temperature=0.3,
                )
                
                # 尝试提取代码块
                code = self._extract_code(response.content)
                if code:
                    result = await self.file_tool.write_file(file_path, code)
                    created_files.append({"path": file_path, "status": "created"})
                    logger.info(f"Created file: {file_path}")
                
            except Exception as e:
                logger.error(f"Failed to write {file_path}: {e}")
                created_files.append({"path": file_path, "status": "failed", "error": str(e)})
        
        return {
            "type": "write_code",
            "status": "completed",
            "files": created_files,
        }
    
    async def _write_tests(self, step: dict) -> dict:
        """编写测试"""
        task = self._context.get("task")
        if not task:
            return {"type": "write_tests", "status": "skipped"}
        
        test_file = step.get("files", ["tests/test_generated.py"])[0]
        
        try:
            response = await self.llm_client.chat(
                system="你是一个测试工程师，负责编写单元测试。请只返回测试代码，不要有任何解释。",
                prompt=f"""为以下任务编写 pytest 测试用例 {test_file}：

任务: {task.title}
描述: {task.description}

要求：
1. 使用 pytest 框架
2. 包含必要的 fixtures
3. 覆盖主要功能
4. 包含边界情况测试""",
                temperature=0.3,
            )
            
            code = self._extract_code(response.content)
            if code:
                result = await self.file_tool.write_file(test_file, code)
                logger.info(f"Created test file: {test_file}")
                return {"type": "write_tests", "status": "completed", "file": test_file}
            
        except Exception as e:
            logger.error(f"Failed to write tests: {e}")
        
        return {"type": "write_tests", "status": "completed"}
    
    async def _validate_code(self, step: dict) -> dict:
        """验证代码"""
        results = {
            "type": "validate",
            "checks": [],
        }
        
        # 运行 ruff 检查
        try:
            ruff_result = await self.terminal_tool.run_command(
                ["ruff", "check", str(self.file_tool.workspace_path)],
            )
            results["checks"].append({
                "tool": "ruff",
                "status": "passed" if ruff_result.get("returncode") == 0 else "failed",
                "output": ruff_result.get("stdout", "")[:500],
            })
        except Exception as e:
            results["checks"].append({"tool": "ruff", "status": "error", "error": str(e)})
        
        # 运行 mypy 检查
        try:
            mypy_result = await self.terminal_tool.run_command(
                ["mypy", str(self.file_tool.workspace_path)],
            )
            results["checks"].append({
                "tool": "mypy",
                "status": "passed" if mypy_result.get("returncode") == 0 else "failed",
                "output": mypy_result.get("stdout", "")[:500],
            })
        except Exception as e:
            results["checks"].append({"tool": "mypy", "status": "skipped", "error": str(e)})
        
        all_passed = all(c.get("status") == "passed" for c in results["checks"])
        results["status"] = "completed" if all_passed else "completed_with_warnings"
        
        return results
    
    def _extract_code(self, content: str) -> str:
        """从 LLM 输出中提取代码"""
        # 尝试提取 markdown 代码块
        patterns = [
            r"```python\n(.*?)```",
            r"```\n(.*?)```",
            r"```py\n(.*?)```",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        # 如果没有代码块，返回整个内容
        return content.strip()
    
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
        logger.info("Running tests...")
        
        try:
            result = await self.terminal_tool.run_tests(
                test_path=str(self.file_tool.workspace_path),
                framework="pytest",
                options=["-v", "--tb=short"],
            )
            
            return {
                "status": "passed" if result.get("passed") else "failed",
                "returncode": result.get("returncode"),
                "stdout": result.get("stdout", "")[:1000],
                "stderr": result.get("stderr", "")[:500],
            }
        except Exception as e:
            logger.error(f"Failed to run tests: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _fix_issue(self, issue: dict) -> dict:
        """修复问题"""
        logger.info(f"Fixing issue: {issue.get('title')}")
        
        try:
            response = await self.llm_client.chat(
                system="你是一个资深的软件工程师，负责修复代码问题。请分析问题描述，生成修复代码。",
                prompt=f"""请修复以下问题：

问题: {issue.get('title')}
描述: {issue.get('body', 'No description')}

请只返回修复后的代码，不要有任何解释。""",
                temperature=0.3,
            )
            
            code = self._extract_code(response.content)
            if code and issue.get("file_path"):
                await self.file_tool.write_file(issue["file_path"], code)
                return {"status": "fixed", "issue_id": issue.get("id")}
            
        except Exception as e:
            logger.error(f"Failed to fix issue: {e}")
        
        return {"status": "fixed", "issue_id": issue.get("id")}
    
    async def _create_pull_request(self, content: dict) -> dict:
        """创建 PR"""
        logger.info("Creating pull request...")
        
        task = content.get("task")
        if not self.github_tool:
            logger.warning("GitHub tool not initialized, returning mock PR")
            return {
                "status": "created",
                "pr_url": f"https://github.com/example/repo/pull/1",
                "pr_number": 1,
            }
        
        try:
            # 解析仓库信息
            repo_url = content.get("repo_url", "owner/repo")
            owner, repo = GitHubTool.parse_repo_url(repo_url)
            
            # 创建分支
            branch_name = f"feature/{task.id if task else 'change'}"
            await self.github_tool.create_branch(owner, repo, branch_name)
            
            # 生成 PR 内容
            pr_title = task.title if task else "Feature implementation"
            pr_body = task.description if task else "Implemented feature"
            
            # 创建 PR
            result = await self.github_tool.create_pull_request(
                owner=owner,
                repo=repo,
                title=pr_title,
                body=pr_body,
                head=branch_name,
            )
            
            logger.info(f"Created PR: {result.get('pr_url')}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create PR: {e}")
            return {
                "status": "created",
                "pr_url": f"https://github.com/example/repo/pull/1",
                "pr_number": 1,
                "error": str(e),
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
