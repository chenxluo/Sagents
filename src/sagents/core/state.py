"""状态定义模块"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Agent 类型"""
    ORCHESTRATOR = "orchestrator"
    DEVELOPER = "developer"
    QA_ENGINEER = "qa_engineer"
    TECH_WRITER = "tech_writer"
    DEV_OPS = "dev_ops"


class AgentStatus(str, Enum):
    """Agent 状态"""
    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    PAUSED = "paused"
    ERROR = "error"


class MessageType(str, Enum):
    """消息类型"""
    INVOKE = "invoke"
    RESPONSE = "response"
    ERROR = "error"
    NOTIFICATION = "notification"


class InvokeMode(str, Enum):
    """调用模式"""
    SYNC = "sync"
    ASYNC = "async"


class HealthLevel(str, Enum):
    """健康等级"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    PAUSED = "paused"


class AgentMessage(BaseModel):
    """Agent 间消息"""
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    msg_type: MessageType
    sender: AgentType
    receiver: AgentType
    content: dict = Field(default_factory=dict)
    invoke_mode: InvokeMode = InvokeMode.ASYNC
    correlation_id: Optional[str] = None
    timeout_seconds: Optional[int] = None
    created_at: str = Field(default_factory=lambda: __import__("datetime").datetime.utcnow().isoformat())


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class Task(BaseModel):
    """任务模型"""
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    assignee: Optional[AgentType] = None
    priority: int = 0
    metadata: dict = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: __import__("datetime").datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: __import__("datetime").datetime.utcnow().isoformat())


class AgentState(BaseModel):
    """Agent 状态"""
    agent_type: AgentType
    status: AgentStatus = AgentStatus.IDLE
    current_task: Optional[Task] = None
    task_history: list[Task] = Field(default_factory=list)
    error_count: int = 0
    success_count: int = 0
    total_rounds: int = 0
