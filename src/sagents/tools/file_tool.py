"""文件操作工具"""
import asyncio
import logging
import re
from pathlib import Path
from typing import Optional, Union

logger = logging.getLogger(__name__)


class FileTool:
    """文件操作工具"""
    
    def __init__(self, workspace_path: Optional[str] = None):
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self._ensure_workspace()
    
    def _ensure_workspace(self):
        """确保工作目录存在"""
        self.workspace_path.mkdir(parents=True, exist_ok=True)
    
    def resolve_path(self, path: Union[str, Path]) -> Path:
        """解析文件路径"""
        path = Path(path)
        if path.is_absolute():
            return path
        return self.workspace_path / path
    
    async def read_file(self, path: Union[str, Path]) -> str:
        """
        读取文件内容
        
        Args:
            path: 文件路径
        
        Returns:
            文件内容
        """
        file_path = self.resolve_path(path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not file_path.is_file():
            raise ValueError(f"Not a file: {file_path}")
        
        return file_path.read_text(encoding="utf-8")
    
    async def write_file(
        self,
        path: Union[str, Path],
        content: str,
        create_parents: bool = True,
    ) -> dict:
        """
        写入文件
        
        Args:
            path: 文件路径
            content: 文件内容
            create_parents: 是否创建父目录
        
        Returns:
            操作结果
        """
        file_path = self.resolve_path(path)
        
        if create_parents:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_path.write_text(content, encoding="utf-8")
        
        return {
            "status": "written",
            "path": str(file_path),
            "size": len(content),
        }
    
    async def edit_file(
        self,
        path: Union[str, Path],
        old_str: str,
        new_str: str,
    ) -> dict:
        """
        编辑文件（替换）
        
        Args:
            path: 文件路径
            old_str: 要替换的字符串
            new_str: 新字符串
        
        Returns:
            操作结果
        """
        file_path = self.resolve_path(path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        content = file_path.read_text(encoding="utf-8")
        
        if old_str not in content:
            raise ValueError(f"String not found in file: {old_str[:50]}...")
        
        new_content = content.replace(old_str, new_str)
        file_path.write_text(new_content, encoding="utf-8")
        
        return {
            "status": "edited",
            "path": str(file_path),
            "changes": content.count(old_str),
        }
    
    async def append_file(
        self,
        path: Union[str, Path],
        content: str,
    ) -> dict:
        """
        追加文件内容
        
        Args:
            path: 文件路径
            content: 追加的内容
        
        Returns:
            操作结果
        """
        file_path = self.resolve_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(content)
        
        return {
            "status": "appended",
            "path": str(file_path),
        }
    
    async def delete_file(self, path: Union[str, Path]) -> dict:
        """
        删除文件
        
        Args:
            path: 文件路径
        
        Returns:
            操作结果
        """
        file_path = self.resolve_path(path)
        
        if not file_path.exists():
            return {"status": "not_found", "path": str(file_path)}
        
        if not file_path.is_file():
            raise ValueError(f"Not a file: {file_path}")
        
        file_path.unlink()
        
        return {"status": "deleted", "path": str(file_path)}
    
    async def list_files(
        self,
        path: Union[str, Path] = ".",
        pattern: Optional[str] = None,
        recursive: bool = False,
    ) -> list[str]:
        """
        列出文件
        
        Args:
            path: 目录路径
            pattern: 文件模式（如 *.py）
            recursive: 是否递归
        
        Returns:
            文件列表
        """
        dir_path = self.resolve_path(path)
        
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")
        
        if not dir_path.is_dir():
            raise ValueError(f"Not a directory: {dir_path}")
        
        if recursive:
            if pattern:
                files = list(dir_path.rglob(pattern))
            else:
                files = [f for f in dir_path.rglob("*") if f.is_file()]
        else:
            if pattern:
                files = list(dir_path.glob(pattern))
            else:
                files = [f for f in dir_path.iterdir() if f.is_file()]
        
        return [str(f.relative_to(self.workspace_path)) for f in files]
    
    async def create_directory(
        self,
        path: Union[str, Path],
        parents: bool = True,
    ) -> dict:
        """
        创建目录
        
        Args:
            path: 目录路径
            parents: 是否创建父目录
        
        Returns:
            操作结果
        """
        dir_path = self.resolve_path(path)
        dir_path.mkdir(parents=parents, exist_ok=True)
        
        return {"status": "created", "path": str(dir_path)}
    
    async def delete_directory(
        self,
        path: Union[str, Path],
        recursive: bool = False,
    ) -> dict:
        """
        删除目录
        
        Args:
            path: 目录路径
            recursive: 是否递归删除
        
        Returns:
            操作结果
        """
        dir_path = self.resolve_path(path)
        
        if not dir_path.exists():
            return {"status": "not_found", "path": str(dir_path)}
        
        if not dir_path.is_dir():
            raise ValueError(f"Not a directory: {dir_path}")
        
        import shutil
        if recursive:
            shutil.rmtree(dir_path)
        else:
            dir_path.rmdir()
        
        return {"status": "deleted", "path": str(dir_path)}
    
    async def get_file_info(self, path: Union[str, Path]) -> dict:
        """
        获取文件信息
        
        Args:
            path: 文件路径
        
        Returns:
            文件信息
        """
        file_path = self.resolve_path(path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        stat = file_path.stat()
        
        return {
            "path": str(file_path),
            "name": file_path.name,
            "size": stat.st_size,
            "is_file": file_path.is_file(),
            "is_dir": file_path.is_dir(),
            "modified": stat.st_mtime,
        }
    
    async def search_in_file(
        self,
        path: Union[str, Path],
        pattern: str,
        regex: bool = False,
    ) -> list[dict]:
        """
        在文件中搜索
        
        Args:
            path: 文件路径
            pattern: 搜索模式
            regex: 是否使用正则表达式
        
        Returns:
            匹配结果列表
        """
        content = await self.read_file(path)
        lines = content.split("\n")
        
        results = []
        if regex:
            matcher = re.compile(pattern)
            for i, line in enumerate(lines, 1):
                if matcher.search(line):
                    results.append({
                        "line_number": i,
                        "content": line,
                    })
        else:
            for i, line in enumerate(lines, 1):
                if pattern in line:
                    results.append({
                        "line_number": i,
                        "content": line,
                    })
        
        return results
    
    async def copy_file(
        self,
        source: Union[str, Path],
        destination: Union[str, Path],
    ) -> dict:
        """
        复制文件
        
        Args:
            source: 源文件
            destination: 目标文件
        
        Returns:
            操作结果
        """
        import shutil
        
        src_path = self.resolve_path(source)
        dst_path = self.resolve_path(destination)
        
        if not src_path.exists():
            raise FileNotFoundError(f"Source not found: {src_path}")
        
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dst_path)
        
        return {"status": "copied", "from": str(src_path), "to": str(dst_path)}
    
    async def move_file(
        self,
        source: Union[str, Path],
        destination: Union[str, Path],
    ) -> dict:
        """
        移动文件
        
        Args:
            source: 源文件
            destination: 目标文件
        
        Returns:
            操作结果
        """
        import shutil
        
        src_path = self.resolve_path(source)
        dst_path = self.resolve_path(destination)
        
        if not src_path.exists():
            raise FileNotFoundError(f"Source not found: {src_path}")
        
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src_path, dst_path)
        
        return {"status": "moved", "from": str(src_path), "to": str(dst_path)}
