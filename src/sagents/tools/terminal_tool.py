"""终端执行工具"""
import asyncio
import logging
import os
import shlex
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger(__name__)


class TerminalTool:
    """终端执行工具"""
    
    def __init__(self, workspace_path: Optional[str] = None):
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self._env: dict = {}
    
    def set_env(self, key: str, value: str):
        """设置环境变量"""
        self._env[key] = value
    
    def get_env(self, key: str) -> Optional[str]:
        """获取环境变量"""
        return self._env.get(key)
    
    async def run_command(
        self,
        command: Union[str, list[str]],
        cwd: Optional[str] = None,
        timeout: Optional[int] = 300,
        env: Optional[dict] = None,
    ) -> dict:
        """
        执行命令
        
        Args:
            command: 命令字符串或列表
            cwd: 工作目录
            timeout: 超时秒数
            env: 环境变量
        
        Returns:
            执行结果
        """
        if isinstance(command, str):
            command = shlex.split(command)
        
        work_dir = Path(cwd) if cwd else self.workspace_path
        
        # 合并环境变量
        cmd_env = os.environ.copy()
        cmd_env.update(self._env)
        if env:
            cmd_env.update(env)
        
        logger.info(f"Running command: {' '.join(command)}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(work_dir),
                env=cmd_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise TimeoutError(f"Command timed out after {timeout}s")
            
            return {
                "status": "completed",
                "returncode": process.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }
            
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
            }
    
    async def run_python(
        self,
        script: str,
        timeout: Optional[int] = 60,
    ) -> dict:
        """
        运行 Python 脚本
        
        Args:
            script: Python 脚本内容
            timeout: 超时秒数
        
        Returns:
            执行结果
        """
        # 写入临时脚本
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script)
            script_path = f.name
        
        try:
            result = await self.run_command(
                ["python", script_path],
                timeout=timeout,
            )
            return result
        finally:
            Path(script_path).unlink(missing_ok=True)
    
    async def run_shell(
        self,
        script: str,
        timeout: Optional[int] = 60,
    ) -> dict:
        """
        运行 Shell 脚本
        
        Args:
            script: Shell 脚本内容
            timeout: 超时秒数
        
        Returns:
            执行结果
        """
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
            f.write("#!/bin/bash\n")
            f.write(script)
            script_path = f.name
        
        os.chmod(script_path, 0o755)
        
        try:
            result = await self.run_command(
                ["bash", script_path],
                timeout=timeout,
            )
            return result
        finally:
            Path(script_path).unlink(missing_ok=True)
    
    async def install_package(
        self,
        package: str,
        manager: str = "pip",
    ) -> dict:
        """
        安装包
        
        Args:
            package: 包名
            manager: 包管理器 (pip/uv)
        
        Returns:
            执行结果
        """
        if manager == "pip":
            return await self.run_command(["pip", "install", package])
        elif manager == "uv":
            return await self.run_command(["uv", "pip", "install", package])
        elif manager == "npm":
            return await self.run_command(["npm", "install", package])
        elif manager == "yarn":
            return await self.run_command(["yarn", "add", package])
        else:
            return {"status": "failed", "error": f"Unknown package manager: {manager}"}
    
    async def run_tests(
        self,
        test_path: Optional[str] = None,
        framework: str = "pytest",
        options: Optional[list[str]] = None,
    ) -> dict:
        """
        运行测试
        
        Args:
            test_path: 测试路径
            framework: 测试框架
            options: 额外选项
        
        Returns:
            测试结果
        """
        options = options or []
        
        if framework == "pytest":
            cmd = ["pytest"]
            if test_path:
                cmd.append(test_path)
            cmd.extend(options)
        elif framework == "unittest":
            cmd = ["python", "-m", "unittest"]
            if test_path:
                cmd.append(test_path)
        else:
            return {"status": "failed", "error": f"Unknown test framework: {framework}"}
        
        result = await self.run_command(cmd, timeout=300)
        
        # 解析测试结果
        if result.get("returncode") == 0:
            result["passed"] = True
        else:
            result["passed"] = False
        
        return result
    
    async def git_command(self, *args: str) -> dict:
        """
        执行 git 命令
        
        Args:
            *args: git 子命令和参数
        
        Returns:
            执行结果
        """
        command = ["git"] + list(args)
        return await self.run_command(command)
    
    async def check_command_exists(self, command: str) -> bool:
        """检查命令是否存在"""
        result = await self.run_command(["which", command])
        return result.get("returncode") == 0
