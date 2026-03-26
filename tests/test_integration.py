"""集成测试"""
import asyncio
import tempfile
import os
import pytest
from pathlib import Path

from sagents.core.state import AgentType, AgentStatus, Task, TaskStatus, AgentMessage, MessageType, InvokeMode
from sagents.core.message_bus import MessageBus
from sagents.core.orchestrator import Orchestrator
from sagents.core.health_monitor import HealthMonitor, get_health_monitor
from sagents.agents.developer import DeveloperAgent
from sagents.agents.qa_engineer import QAEngineerAgent
from sagents.agents.tech_writer import TechWriterAgent
from sagents.tools.terminal_tool import TerminalTool
from sagents.tools.file_tool import FileTool


class TestAgentMessagePassing:
    """测试 Agent 间消息传递"""
    
    @pytest.mark.asyncio
    async def test_sync_message_pass(self):
        """测试同步消息传递"""
        bus = MessageBus()
        await bus.start()
        
        # 创建 Developer Agent
        developer = DeveloperAgent(message_bus=bus)
        await developer.start()
        
        # 创建 QA Agent
        qa_agent = QAEngineerAgent(message_bus=bus)
        await qa_agent.start()
        
        # 订阅消息
        received = []
        async def capture_message(msg: AgentMessage):
            received.append(msg)
        
        bus.subscribe(AgentType.QA_ENGINEER, capture_message)
        
        # 发送消息
        await bus.send(
            sender=AgentType.DEVELOPER,
            receiver=AgentType.QA_ENGINEER,
            content={"action": "test", "data": "hello"},
        )
        
        # 等待消息传递
        await asyncio.sleep(0.2)
        
        assert len(received) == 1
        assert received[0].content["data"] == "hello"
        
        await developer.stop()
        await qa_agent.stop()
        await bus.stop()


class TestTaskDispatchFlow:
    """测试任务调度流程"""
    
    @pytest.mark.asyncio
    async def test_task_creation_and_dispatch(self):
        """测试任务创建和下发"""
        bus = MessageBus()
        await bus.start()
        
        orchestrator = Orchestrator(message_bus=bus)
        await orchestrator.start()
        
        # 创建任务
        task = Task(
            id="test-task-1",
            title="Test Task",
            description="A test task",
            status=TaskStatus.PENDING,
        )
        
        # 下发任务
        result = await orchestrator.dispatch_task(
            task=task,
            agent_type=AgentType.DEVELOPER,
            sync=True,
        )
        
        # 任务应该在下发列表中
        assert task.id in orchestrator._active_tasks
        
        await orchestrator.stop()
        await bus.stop()


class TestHealthMonitor:
    """测试健康监控"""
    
    @pytest.mark.asyncio
    async def test_health_record_success(self):
        """测试记录成功"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_health.db")
            monitor = HealthMonitor(db_path=db_path)
            await monitor.initialize()
            
            # 记录成功
            await monitor.record_success(AgentType.DEVELOPER)
            
            # 验证统计
            stats = monitor.get_or_create_stats(AgentType.DEVELOPER)
            assert stats.total_tasks == 1
            assert stats.success_tasks == 1
            assert stats.failure_rate == 0.0
            
            await monitor.close()
    
    @pytest.mark.asyncio
    async def test_health_record_failure(self):
        """测试记录失败"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_health.db")
            monitor = HealthMonitor(db_path=db_path)
            await monitor.initialize()
            
            # 记录失败
            await monitor.record_failure(AgentType.DEVELOPER, "Test error")
            
            # 验证统计
            stats = monitor.get_or_create_stats(AgentType.DEVELOPER)
            assert stats.total_tasks == 1
            assert stats.failed_tasks == 1
            assert stats.failure_rate == 1.0
            
            await monitor.close()
    
    @pytest.mark.asyncio
    async def test_health_persistence(self):
        """测试健康数据持久化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_health.db")
            
            # 第一次写入
            monitor1 = HealthMonitor(db_path=db_path)
            await monitor1.initialize()
            await monitor1.record_success(AgentType.DEVELOPER)
            await monitor1.record_success(AgentType.DEVELOPER)
            await monitor1.record_failure(AgentType.QA_ENGINEER)
            await monitor1.close()
            
            # 重新加载
            monitor2 = HealthMonitor(db_path=db_path)
            await monitor2.initialize()
            
            # 验证数据恢复
            dev_stats = monitor2.get_or_create_stats(AgentType.DEVELOPER)
            assert dev_stats.total_tasks == 2
            assert dev_stats.success_tasks == 2
            
            qa_stats = monitor2.get_or_create_stats(AgentType.QA_ENGINEER)
            assert qa_stats.total_tasks == 1
            assert qa_stats.failed_tasks == 1
            
            await monitor2.close()


class TestTools:
    """测试工具"""
    
    @pytest.mark.asyncio
    async def test_terminal_tool_run_command(self):
        """测试终端工具执行命令"""
        tool = TerminalTool()
        
        result = await tool.run_command(["echo", "hello"])
        
        assert result["status"] == "completed"
        assert result["returncode"] == 0
        assert "hello" in result["stdout"]
    
    @pytest.mark.asyncio
    async def test_file_tool_write_read(self):
        """测试文件工具读写"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = FileTool(workspace_path=tmpdir)
            
            # 写入文件
            result = await tool.write_file("test.txt", "Hello, World!")
            assert result["status"] == "written"
            
            # 读取文件
            content = await tool.read_file("test.txt")
            assert content == "Hello, World!"


class TestDeveloperWorkflow:
    """测试开发者工作流"""
    
    @pytest.mark.asyncio
    async def test_developer_pr_creation_mock(self):
        """测试开发者 PR 创建（无 GitHub Token）"""
        agent = DeveloperAgent(
            workspace_path="./workspace",
        )
        
        result = await agent._create_pull_request({
            "task": Task(
                id="pr-test-1",
                title="Test PR",
                description="Test",
                status=TaskStatus.COMPLETED,
            )
        })
        
        # 应该返回模拟 PR
        assert result["status"] == "created"
        assert "pr_url" in result


class TestQAWorkflow:
    """测试 QA 工作流"""
    
    @pytest.mark.asyncio
    async def test_qa_parse_pytest_output(self):
        """测试 pytest 输出解析"""
        agent = QAEngineerAgent(workspace_path="./")
        
        # 测试解析逻辑
        result = {"stdout": "3 passed, 1 failed", "stderr": ""}
        passed, total, failures = agent._parse_pytest_output(result)
        
        assert passed == 3
        assert failures == 1
        assert total == 4


class TestTechWriterWorkflow:
    """测试文档维护者工作流"""
    
    @pytest.mark.asyncio
    async def test_tech_writer_analyze_changes(self):
        """测试文档变更分析"""
        agent = TechWriterAgent()
        
        content = {
            "code_diff": {
                "files": ["src/api.py", "config.yaml"],
                "added": ["src/new_api.py"],
                "modified": ["src/api.py"],
                "deleted": [],
            }
        }
        
        result = await agent._analyze_code_changes(content)
        
        # 验证结果 - 检查基础字段
        assert result["total_files"] == 2
        assert "src/new_api.py" in result["added_files"]
        assert "src/api.py" in result["modified_files"]
        # api_changes 和 config_changes 的数量取决于 LLM 分析（可能失败）
    
    @pytest.mark.asyncio
    async def test_tech_writer_mark_outdated(self):
        """测试标记过时文档"""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = TechWriterAgent(docs_path=tmpdir)
            
            # 创建文档
            doc_path = Path(tmpdir) / "old_doc.md"
            doc_path.write_text("# Old Documentation\n\nThis is old content.")
            
            # 标记过时
            result = await agent._mark_doc_outdated(str(doc_path))
            
            assert result["marked"] is True
            
            # 验证内容被修改
            content = doc_path.read_text()
            assert "过时" in content or "outdated" in content.lower()
