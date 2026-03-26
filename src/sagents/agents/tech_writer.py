"""文档维护者 Agent"""
import asyncio
import logging
from pathlib import Path
from typing import Optional

from ..core.state import AgentType, Task, AgentMessage, InvokeMode
from ..core.message_bus import MessageBus
from .base import BaseAgent

logger = logging.getLogger(__name__)


class TechWriterAgent(BaseAgent):
    """文档维护者 Agent"""
    
    def __init__(
        self,
        message_bus: Optional[MessageBus] = None,
        docs_path: Optional[str] = None,
    ):
        super().__init__(
            agent_type=AgentType.TECH_WRITER,
            message_bus=message_bus,
        )
        self.docs_path = Path(docs_path) if docs_path else Path("./docs")
        self._file_context: dict = {}
    
    async def execute(self, content: dict) -> dict:
        """
        执行文档任务
        
        Args:
            content: 任务内容
                - action: 操作类型
                - code_diff: 代码变更
                - doc_type: 文档类型
        
        Returns:
            执行结果
        """
        action = content.get("action")
        
        if action == "update_docs":
            return await self._update_documentation(content)
        
        elif action == "analyze_changes":
            return await self._analyze_code_changes(content)
        
        elif action == "sync_docs":
            return await self._sync_documentation()
        
        elif action == "mark_outdated":
            return await self._mark_outdated_docs(content)
        
        else:
            logger.warning(f"Unknown action: {action}")
            return {"status": "unknown_action", "action": action}
    
    async def _update_documentation(self, content: dict) -> dict:
        """更新文档"""
        logger.info("Updating documentation...")
        
        code_diff = content.get("code_diff", {})
        doc_type = content.get("doc_type", "general")
        
        # 1. 分析代码变更
        changes = await self._analyze_code_changes(content)
        
        # 2. 识别需要更新的文档
        docs_to_update = await self._identify_docs_to_update(changes)
        
        # 3. 更新每个文档
        updated_docs = []
        for doc_path in docs_to_update:
            result = await self._update_single_doc(doc_path, changes)
            updated_docs.append(result)
        
        # 4. 创建文档 PR
        pr_result = await self._create_doc_pr(updated_docs)
        
        # 5. 合并文档 PR（文档维护者有权限直接合并）
        if pr_result.get("merged"):
            await self.message_bus.send_response(content, {"status": "success"})
        
        return {
            "status": "completed",
            "changes_analyzed": changes,
            "docs_updated": updated_docs,
            "pr_url": pr_result.get("pr_url"),
        }
    
    async def _analyze_code_changes(self, content: dict) -> dict:
        """分析代码变更"""
        logger.info("Analyzing code changes...")
        
        code_diff = content.get("code_diff", {})
        files_changed = code_diff.get("files", [])
        files_added = code_diff.get("added", [])
        files_modified = code_diff.get("modified", [])
        files_deleted = code_diff.get("deleted", [])
        
        # 分析变更类型
        changes = {
            "total_files": len(files_changed),
            "added_files": files_added,
            "modified_files": files_modified,
            "deleted_files": files_deleted,
            "api_changes": self._detect_api_changes(files_modified),
            "config_changes": self._detect_config_changes(files_modified),
        }
        
        return changes
    
    def _detect_api_changes(self, modified_files: list[str]) -> list[dict]:
        """检测 API 变更"""
        api_files = [f for f in modified_files if "api" in f.lower() or "endpoint" in f.lower()]
        return [{"file": f, "type": "api"} for f in api_files]
    
    def _detect_config_changes(self, modified_files: list[str]) -> list[dict]:
        """检测配置变更"""
        config_extensions = (".yaml", ".json", ".toml", ".env")
        config_files = [f for f in modified_files if f.endswith(config_extensions)]
        return [{"file": f, "type": "config"} for f in config_files]
    
    async def _identify_docs_to_update(self, changes: dict) -> list[Path]:
        """识别需要更新的文档"""
        docs = []
        
        # 查找所有 .md 文件
        if self.docs_path.exists():
            for md_file in self.docs_path.rglob("*.md"):
                # 检查是否需要更新
                if self._should_update_doc(md_file, changes):
                    docs.append(md_file)
        
        return docs
    
    def _should_update_doc(self, doc_path: Path, changes: dict) -> bool:
        """判断文档是否需要更新"""
        doc_name = doc_path.stem.lower()
        
        # API 变更
        if changes.get("api_changes"):
            if "api" in doc_name or "reference" in doc_name:
                return True
        
        # 配置变更
        if changes.get("config_changes"):
            if "config" in doc_name or "configuration" in doc_name:
                return True
        
        # 通用文档更新
        return True
    
    async def _update_single_doc(self, doc_path: Path, changes: dict) -> dict:
        """更新单个文档"""
        logger.info(f"Updating doc: {doc_path}")
        
        # TODO: 调用 LLM 分析并更新文档
        await asyncio.sleep(0.1)
        
        return {
            "path": str(doc_path),
            "status": "updated",
            "changes_applied": 0,
        }
    
    async def _sync_documentation(self) -> dict:
        """同步文档"""
        logger.info("Syncing documentation...")
        
        # 1. 扫描所有代码文件
        # 2. 检查对应的文档是否存在
        # 3. 标记过时的文档
        # 4. 生成同步报告
        
        return {
            "status": "completed",
            "docs_scanned": 0,
            "docs_synced": 0,
            "outdated_docs": [],
        }
    
    async def _mark_outdated_docs(self, content: dict) -> dict:
        """标记过时文档"""
        logger.info("Marking outdated documentation...")
        
        docs_to_mark = content.get("docs", [])
        
        marked = []
        for doc_path in docs_to_mark:
            result = await self._mark_doc_outdated(doc_path)
            marked.append(result)
        
        return {
            "status": "completed",
            "docs_marked": marked,
        }
    
    async def _mark_doc_outdated(self, doc_path: str) -> dict:
        """标记单个文档过时"""
        # TODO: 在文档中添加过时标记
        return {
            "path": doc_path,
            "marked": True,
        }
    
    async def _create_doc_pr(self, updated_docs: list[dict]) -> dict:
        """创建文档 PR"""
        logger.info("Creating documentation PR...")
        
        # TODO: 调用 GitHub API 创建 PR
        pr_url = "https://github.com/example/repo/pull/2"
        
        # 文档维护者有权限直接合并
        # TODO: 调用 GitHub API 合并 PR
        merged = True
        
        return {
            "status": "created",
            "pr_url": pr_url,
            "pr_number": 2,
            "merged": merged,
        }
    
    async def handle_notification(self, action: str, content: dict):
        """处理通知"""
        if action == "update_docs":
            await self._update_documentation(content)
        elif action == "sync_docs":
            await self._sync_documentation()
