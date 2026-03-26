"""GitHub API 工具"""
import asyncio
import logging
from typing import Optional
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class GitHubTool:
    """GitHub API 工具"""
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self, token: Optional[str] = None):
        self.token = token
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None:
            headers = {
                "Authorization": f"Bearer {self.token}" if self.token else "",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers=headers,
                timeout=30.0,
            )
        return self._client
    
    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def create_branch(
        self,
        owner: str,
        repo: str,
        branch_name: str,
        base_branch: str = "main",
    ) -> dict:
        """创建分支"""
        client = await self._get_client()
        
        # 获取基础分支的 SHA
        ref_response = await client.get(f"/repos/{owner}/{repo}/git/ref/heads/{base_branch}")
        if ref_response.status_code != 200:
            raise Exception(f"Failed to get ref: {ref_response.text}")
        
        base_sha = ref_response.json()["object"]["sha"]
        
        # 创建新分支
        response = await client.post(
            f"/repos/{owner}/{repo}/git/refs",
            json={
                "ref": f"refs/heads/{branch_name}",
                "sha": base_sha,
            },
        )
        
        if response.status_code not in (200, 201):
            raise Exception(f"Failed to create branch: {response.text}")
        
        return {"status": "created", "branch": branch_name}
    
    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> dict:
        """创建 PR"""
        client = await self._get_client()
        
        response = await client.post(
            f"/repos/{owner}/{repo}/pulls",
            json={
                "title": title,
                "body": body,
                "head": head,
                "base": base,
            },
        )
        
        if response.status_code not in (200, 201):
            raise Exception(f"Failed to create PR: {response.text}")
        
        data = response.json()
        return {
            "status": "created",
            "pr_number": data["number"],
            "pr_url": data["html_url"],
        }
    
    async def merge_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        merge_method: str = "squash",
        commit_title: Optional[str] = None,
        commit_message: Optional[str] = None,
    ) -> dict:
        """合并 PR"""
        client = await self._get_client()
        
        response = await client.put(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/merge",
            json={
                "merge_method": merge_method,
                "commit_title": commit_title,
                "commit_message": commit_message,
            },
        )
        
        if response.status_code not in (200, 201):
            raise Exception(f"Failed to merge PR: {response.text}")
        
        data = response.json()
        return {
            "status": "merged",
            "merged": data.get("merged"),
            "merge_commit_sha": data.get("merge_commit_sha"),
        }
    
    async def get_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> dict:
        """获取 PR 信息"""
        client = await self._get_client()
        
        response = await client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
        
        if response.status_code != 200:
            raise Exception(f"Failed to get PR: {response.text}")
        
        return response.json()
    
    async def list_pull_request_files(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> list[dict]:
        """列出 PR 修改的文件"""
        client = await self._get_client()
        
        response = await client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}/files")
        
        if response.status_code != 200:
            raise Exception(f"Failed to list files: {response.text}")
        
        return response.json()
    
    async def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str = "main",
    ) -> str:
        """获取文件内容"""
        client = await self._get_client()
        
        response = await client.get(f"/repos/{owner}/{repo}/contents/{path}", params={"ref": ref})
        
        if response.status_code != 200:
            raise Exception(f"Failed to get file: {response.text}")
        
        import base64
        data = response.json()
        if data.get("encoding") == "base64":
            return base64.b64decode(data["content"]).decode("utf-8")
        
        return data.get("content", "")
    
    async def create_or_update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str,
        sha: Optional[str] = None,
    ) -> dict:
        """创建或更新文件"""
        client = await self._get_client()
        
        import base64
        encoded_content = base64.b64encode(content.encode()).decode()
        
        payload = {
            "message": message,
            "content": encoded_content,
            "branch": branch,
        }
        
        if sha:
            payload["sha"] = sha
        
        response = await client.put(
            f"/repos/{owner}/{repo}/contents/{path}",
            json=payload,
        )
        
        if response.status_code not in (200, 201):
            raise Exception(f"Failed to update file: {response.text}")
        
        data = response.json()
        return {
            "status": "updated" if sha else "created",
            "commit": data.get("commit", {}).get("sha"),
        }
    
    async def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        labels: Optional[list[str]] = None,
    ) -> dict:
        """创建 Issue"""
        client = await self._get_client()
        
        response = await client.post(
            f"/repos/{owner}/{repo}/issues",
            json={
                "title": title,
                "body": body,
                "labels": labels or [],
            },
        )
        
        if response.status_code not in (200, 201):
            raise Exception(f"Failed to create issue: {response.text}")
        
        data = response.json()
        return {
            "status": "created",
            "issue_number": data["number"],
            "issue_url": data["html_url"],
        }
    
    async def add_comment(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        body: str,
    ) -> dict:
        """添加评论"""
        client = await self._get_client()
        
        response = await client.post(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json={"body": body},
        )
        
        if response.status_code not in (200, 201):
            raise Exception(f"Failed to add comment: {response.text}")
        
        return {"status": "added", "comment_id": response.json()["id"]}
    
    async def list_commits(
        self,
        owner: str,
        repo: str,
        sha: str = "main",
        per_page: int = 30,
    ) -> list[dict]:
        """列出提交"""
        client = await self._get_client()
        
        response = await client.get(
            f"/repos/{owner}/{repo}/commits",
            params={"sha": sha, "per_page": per_page},
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to list commits: {response.text}")
        
        return response.json()
    
    @staticmethod
    def parse_repo_url(url: str) -> tuple[str, str]:
        """解析仓库 URL"""
        # 支持格式:
        # https://github.com/owner/repo
        # git@github.com:owner/repo.git
        # owner/repo
        
        if "/" not in url:
            raise ValueError(f"Invalid repo URL: {url}")
        
        parts = url.rstrip("/").replace(".git", "").split("/")
        
        if url.startswith("http") or url.startswith("git@"):
            owner = parts[-2]
            repo = parts[-1]
        else:
            owner = parts[0]
            repo = parts[1]
        
        return owner, repo
