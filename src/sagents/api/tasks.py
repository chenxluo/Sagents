"""任务管理 API 路由"""
import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import APIRouter, HTTPException
import aiosqlite

from ..core.state import Task, TaskStatus, AgentType
from ..core.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["任务管理"])

# 数据库配置
_db_path: Optional[str] = None
_db: Optional[aiosqlite.Connection] = None


async def init_db(db_path: str = "./tasks.db"):
    """初始化数据库"""
    global _db, _db_path
    _db_path = db_path
    
    _db = await aiosqlite.connect(db_path)
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL,
            assignee TEXT,
            priority INTEGER DEFAULT 0,
            created_at REAL,
            updated_at REAL
        )
    """)
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS task_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            action TEXT,
            old_status TEXT,
            new_status TEXT,
            timestamp REAL
        )
    """)
    await _db.commit()
    logger.info(f"Tasks DB initialized: {db_path}")


async def close_db():
    """关闭数据库"""
    global _db
    if _db:
        await _db.close()
        _db = None


async def _save_task(task: Task):
    """保存任务到数据库"""
    if not _db:
        return
    
    await _db.execute("""
        INSERT OR REPLACE INTO tasks 
        (id, title, description, status, assignee, priority, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        task.id,
        task.title,
        task.description,
        task.status.value,
        task.assignee.value if task.assignee else None,
        task.priority or 0,
        task.created_at.timestamp() if task.created_at else None,
        task.updated_at.timestamp() if task.updated_at else None,
    ))
    await _db.commit()


async def _load_tasks() -> dict[str, Task]:
    """从数据库加载任务"""
    if not _db:
        return {}
    
    tasks = {}
    async with _db.execute("SELECT * FROM tasks") as cursor:
        rows = await cursor.fetchall()
        for row in rows:
            task = Task(
                id=row[0],
                title=row[1],
                description=row[2],
                status=TaskStatus(row[3]),
                assignee=AgentType(row[4]) if row[4] else None,
                priority=row[5],
            )
            tasks[task.id] = task
    
    return tasks


async def _save_history(task_id: str, action: str, old_status: Optional[str], new_status: str):
    """保存任务历史"""
    if not _db:
        return
    
    import time
    await _db.execute("""
        INSERT INTO task_history (task_id, action, old_status, new_status, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (task_id, action, old_status, new_status, time.time()))
    await _db.commit()


# 内存缓存（用于快速访问）
_tasks: dict[str, Task] = {}


@router.post("")
async def create_task(task: Task):
    """创建任务"""
    _tasks[task.id] = task
    await _save_task(task)
    await _save_history(task.id, "created", None, task.status.value)
    return {"task_id": task.id, "status": "created"}


@router.get("/{task_id}")
async def get_task(task_id: str):
    """获取任务"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("")
async def list_tasks(
    status: Optional[TaskStatus] = None,
    assignee: Optional[AgentType] = None,
):
    """列出任务"""
    # 如果缓存为空，从数据库加载
    if not _tasks and _db:
        loaded = await _load_tasks()
        _tasks.update(loaded)
    
    tasks = list(_tasks.values())
    
    if status:
        tasks = [t for t in tasks if t.status == status]
    
    if assignee:
        tasks = [t for t in tasks if t.assignee == assignee]
    
    return {"tasks": [t.model_dump() for t in tasks], "total": len(tasks)}


@router.patch("/{task_id}")
async def update_task(task_id: str, update: dict):
    """更新任务"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    old_status = task.status.value
    
    # 更新字段
    if "status" in update:
        task.status = TaskStatus(update["status"])
    if "assignee" in update:
        assignee_val = update["assignee"]
        task.assignee = AgentType(assignee_val) if assignee_val else None
    if "priority" in update:
        task.priority = update["priority"]
    
    await _save_task(task)
    await _save_history(task_id, "updated", old_status, task.status.value)
    
    return {"task_id": task_id, "status": "updated"}


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    if task_id in _tasks:
        task = _tasks.pop(task_id)
        if _db:
            await _db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            await _db.commit()
        await _save_history(task_id, "deleted", task.status.value, None)
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Task not found")


@router.post("/{task_id}/dispatch")
async def dispatch_task(task_id: str, agent_type: AgentType):
    """下发任务"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    old_status = task.status.value
    task.assignee = agent_type
    task.status = TaskStatus.IN_PROGRESS
    
    await _save_task(task)
    await _save_history(task_id, "dispatched", old_status, task.status.value)
    
    # 调用协调者下发任务
    try:
        orchestrator = get_orchestrator()
        await orchestrator.dispatch_task(task, agent_type)
    except Exception as e:
        logger.warning(f"Failed to dispatch to orchestrator: {e}")
    
    return {"task_id": task_id, "agent": agent_type.value, "status": "dispatched"}


@router.get("/{task_id}/history")
async def get_task_history(task_id: str, limit: int = 50):
    """获取任务历史"""
    if not _db:
        return {"history": []}
    
    async with _db.execute("""
        SELECT action, old_status, new_status, timestamp 
        FROM task_history 
        WHERE task_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (task_id, limit)) as cursor:
        rows = await cursor.fetchall()
        return {
            "history": [
                {
                    "action": row[0],
                    "old_status": row[1],
                    "new_status": row[2],
                    "timestamp": row[3],
                }
                for row in rows
            ]
        }


@router.post("/init")
async def initialize_tasks_db(db_path: str = "./tasks.db"):
    """初始化任务数据库"""
    await init_db(db_path)
    return {"status": "initialized", "db_path": db_path}
