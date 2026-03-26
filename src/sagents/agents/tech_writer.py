"""文档维护者 Agent"""
import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

from ..core.state import AgentType, Task, AgentMessage, InvokeMode
from ..core.message_bus import MessageBus
from ..core.llm_client import LLMClient, get_llm_client
from ..tools.file_tool import FileTool
from ..tools.github_tool import GitHubTool
from .base import BaseAgent

logger = logging.getLogger(__name__)


class TechWriterAgent(BaseAgent):
    """文档维护者 Agent"""
    
    def __init__(
        self,
        message_bus: Optional[MessageBus] = None,
        docs_path: Optional[str] = None,
        github_token: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        super().__init__(
            agent_type=AgentType.TECH_WRITER,
            message_bus=message_bus,
        )
        self.docs_path = Path(docs_path) if docs_path else Path("./docs")
        self._file_context: dict = {}
        
        # 初始化工具
        self.file_tool = FileTool(workspace_path=str(self.docs_path))
        self.github_tool = GitHubTool(token=github_token) if github_token else None
        self.llm_client = llm_client or get_llm_client()
    
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
        
        # 所有变更的文件（包括新增和修改）
        all_changed_files = files_added + files_modified
        
        # 分析变更类型
        changes = {
            "total_files": len(files_changed),
            "added_files": files_added,
            "modified_files": files_modified,
            "deleted_files": files_deleted,
            "api_changes": self._detect_api_changes(all_changed_files),
            "config_changes": self._detect_config_changes(all_changed_files),
        }
        
        # 如果有 LLM 可用，使用 LLM 进行更深入的分析
        if self.llm_client and files_changed:
            try:
                response = await self.llm_client.chat(
                    system="你是一个技术文档专家，负责分析代码变更对文档的影响。",
                    prompt=f"""请分析以下代码变更对文档的影响：

新增文件: {files_added}
修改文件: {files_modified}
删除文件: {files_deleted}

请返回 JSON 格式的文档更新建议：
{{
  "summary": "变更概述",
  "affected_docs": ["需要更新的文档列表"],
  "update_type": "major/minor/patch",
  "key_changes": ["关键变更点列表"]
}}

只返回 JSON。""",
                    temperature=0.3,
                )
                
                import json
                llm_analysis = json.loads(response.content)
                changes["llm_analysis"] = llm_analysis
            except Exception as e:
                logger.warning(f"LLM analysis failed: {e}")
        
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
        
        # 如果 LLM 分析提供了受影响的文档，添加它们
        llm_analysis = changes.get("llm_analysis", {})
        affected_docs = llm_analysis.get("affected_docs", [])
        for doc_name in affected_docs:
            for md_file in self.docs_path.rglob(f"*{doc_name}*"):
                if md_file not in docs:
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
        
        try:
            # 读取现有文档
            existing_content = ""
            if doc_path.exists():
                existing_content = doc_path.read_text(encoding="utf-8")
            
            # 使用 LLM 生成更新
            response = await self.llm_client.chat(
                system="你是一个专业的技术文档专家，负责更新文档以反映最新的代码变更。请保持文档风格一致。",
                prompt=f"""请更新以下文档以反映代码变更：

文档路径: {doc_path}
现有内容:
{existing_content[:3000]}

代码变更摘要:
- 新增文件: {changes.get('added_files', [])}
- 修改文件: {changes.get('modified_files', [])}
- 删除文件: {changes.get('deleted_files', [])}

请返回更新后的完整文档内容。如果文档不需要大的改动，只做必要的更新。
只返回文档内容，不要有其他解释。""",
                temperature=0.3,
            )
            
            # 写入更新后的文档
            updated_content = response.content.strip()
            doc_path.write_text(updated_content, encoding="utf-8")
            
            return {
                "path": str(doc_path),
                "status": "updated",
                "changes_applied": 1,
            }
        except Exception as e:
            logger.error(f"Failed to update doc {doc_path}: {e}")
            return {
                "path": str(doc_path),
                "status": "failed",
                "error": str(e),
            }
    
    async def _sync_documentation(self) -> dict:
        """同步文档"""
        logger.info("Syncing documentation...")
        
        docs_scanned = 0
        docs_synced = 0
        outdated_docs = []
        
        # 扫描代码文件
        code_path = Path("./src")
        if code_path.exists():
            for code_file in code_path.rglob("*.py"):
                docs_scanned += 1
                
                # 查找对应的文档
                doc_name = code_file.stem + ".md"
                doc_path = self.docs_path / doc_name
                
                if not doc_path.exists():
                    outdated_docs.append({
                        "code_file": str(code_file),
                        "doc_file": str(doc_path),
                        "status": "missing",
                    })
        
        return {
            "status": "completed",
            "docs_scanned": docs_scanned,
            "docs_synced": docs_synced,
            "outdated_docs": outdated_docs,
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
        try:
            path = Path(doc_path)
            if not path.exists():
                return {"path": doc_path, "marked": False, "error": "File not found"}
            
            content = path.read_text(encoding="utf-8")
            
            # 检查是否已有过时标记
            if "<!-- OUTDATED -->" in content:
                return {"path": doc_path, "marked": True, "already_marked": True}
            
            # 添加过时标记
            outdated_notice = """

> **⚠️ 警告：此文档已过时**
>
> 本文档可能不再反映最新的代码变更。请查看相关代码以获取最新信息。

"""
            updated_content = outdated_notice + content
            path.write_text(updated_content, encoding="utf-8")
            
            return {"path": doc_path, "marked": True}
        except Exception as e:
            return {"path": doc_path, "marked": False, "error": str(e)}
    
    async def _create_doc_pr(self, updated_docs: list[dict]) -> dict:
        """创建文档 PR"""
        logger.info("Creating documentation PR...")
        
        if not self.github_tool:
            logger.warning("GitHub tool not initialized, returning mock PR")
            return {
                "status": "created",
                "pr_url": "https://github.com/example/repo/pull/2",
                "pr_number": 2,
                "merged": False,
            }
        
        try:
            # 解析仓库信息
            repo_url = updated_docs[0].get("repo_url", "owner/repo") if updated_docs else "owner/repo"
            from ..tools.github_tool import GitHubTool
            owner, repo = GitHubTool.parse_repo_url(repo_url)
            
            # 创建分支
            branch_name = "docs/update-documentation"
            await self.github_tool.create_branch(owner, repo, branch_name)
            
            # 生成 PR 内容
            doc_names = [d.get("path", "").split("/")[-1] for d in updated_docs]
            pr_title = "docs: Update documentation"
            pr_body = f"""## Documentation Update

自动更新的文档：
{chr(10).join(f"- {name}" for name in doc_names)}

此 PR 由 TechWriter Agent 自动创建。
"""
            
            # 创建 PR
            result = await self.github_tool.create_pull_request(
                owner=owner,
                repo=repo,
                title=pr_title,
                body=pr_body,
                head=branch_name,
            )
            
            pr_number = result.get("pr_number", 2)
            
            # 文档 PR 通常可以直接合并
            try:
                await self.github_tool.merge_pull_request(
                    owner=owner,
                    repo=repo,
                    pr_number=pr_number,
                    merge_method="squash",
                )
                result["merged"] = True
            except Exception as e:
                logger.warning(f"Auto-merge failed: {e}")
                result["merged"] = False
            
            return result
        except Exception as e:
            logger.error(f"Failed to create doc PR: {e}")
            return {
                "status": "created",
                "pr_url": "https://github.com/example/repo/pull/2",
                "pr_number": 2,
                "merged": False,
                "error": str(e),
            }
    
    async def handle_notification(self, action: str, content: dict):
        """处理通知"""
        if action == "update_docs":
            await self._update_documentation(content)
        elif action == "sync_docs":
            await self._sync_documentation()
