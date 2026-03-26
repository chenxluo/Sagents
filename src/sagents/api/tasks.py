"""任务管理 API 路由"""
from typing import Optional

from fastapi import APIRouter, HTTPException

from ..core.state import Task, TaskStatus, AgentType

router = APIRouter(prefix="/tasks", tags=["任务管理"])

# 简单的内存任务存储（生产环境应使用数据库）
_tasks: dict[str, Task] = {}


@router.post("")
async def create_task(task: Task):
    """创建任务"""
    _tasks[task.id] = task
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
    
    # 更新字段
    if "status" in update:
        task.status = TaskStatus(update["status"])
    if "assignee" in update and update["assignee"]:
        task.assignee = AgentType(update["assignee"])
    if "priority" in update:
        task.priority = update["priority"]
    
    return {"task_id": task_id, "status": "updated"}


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    if task_id in _tasks:
        del _tasks[task_id]
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Task not found")


@router.post("/{task_id}/dispatch")
async def dispatch_task(task_id: str, agent_type: AgentType):
    """下发任务"""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.assignee = agent_type
    task.status = TaskStatus.IN_PROGRESS
    
    # TODO: 调用协调者下发任务
    return {"task_id": task_id, "agent": agent_type.value, "status": "dispatched"}
