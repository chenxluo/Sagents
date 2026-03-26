"""健康度监控模块"""
import asyncio
import logging
import time
from typing import Optional
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from .state import AgentType, HealthLevel

logger = logging.getLogger(__name__)


class AgentHealthStats:
    """Agent 健康统计"""
    
    def __init__(self, agent_type: AgentType):
        self.agent_type = agent_type
        self.total_tasks: int = 0
        self.success_tasks: int = 0
        self.failed_tasks: int = 0
        self.timeouts: int = 0
        self._history: deque = deque(maxlen=100)
        self.last_updated: float = time.time()
    
    @property
    def failure_rate(self) -> float:
        """计算失败率"""
        if self.total_tasks == 0:
            return 0.0
        return self.failed_tasks / self.total_tasks
    
    @property
    def success_rate(self) -> float:
        """计算成功率"""
        if self.total_tasks == 0:
            return 1.0
        return self.success_tasks / self.total_tasks
    
    def record_success(self):
        """记录成功"""
        self.total_tasks += 1
        self.success_tasks += 1
        self._history.append({"type": "success", "timestamp": time.time()})
        self.last_updated = time.time()
    
    def record_failure(self, error: Optional[str] = None):
        """记录失败"""
        self.total_tasks += 1
        self.failed_tasks += 1
        self._history.append({"type": "failure", "error": error, "timestamp": time.time()})
        self.last_updated = time.time()
    
    def record_timeout(self):
        """记录超时"""
        self.total_tasks += 1
        self.timeouts += 1
        self._history.append({"type": "timeout", "timestamp": time.time()})
        self.last_updated = time.time()
    
    def get_health_level(self) -> HealthLevel:
        """获取健康等级"""
        rate = self.failure_rate
        if rate <= 0.3:
            return HealthLevel.HEALTHY
        elif rate <= 0.5:
            return HealthLevel.WARNING
        elif rate <= 0.7:
            return HealthLevel.CRITICAL
        else:
            return HealthLevel.PAUSED
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "agent_type": self.agent_type.value,
            "total_tasks": self.total_tasks,
            "success_tasks": self.success_tasks,
            "failed_tasks": self.failed_tasks,
            "timeouts": self.timeouts,
            "failure_rate": self.failure_rate,
            "success_rate": self.success_rate,
            "health_level": self.get_health_level().value,
            "last_updated": self.last_updated,
        }


class HealthMonitor:
    """健康度监控器"""
    
    def __init__(self, db_path: Optional[str] = None):
        self._stats: dict[AgentType, AgentHealthStats] = {}
        self._global_failure_rate: float = 0.0
        self._paused: bool = False
        self._lock: asyncio.Lock = asyncio.Lock()
        self._db_path = db_path or "./health_monitor.db"
        self._db: Optional[aiosqlite.Connection] = None
        self._initialized: bool = False
    
    async def initialize(self):
        """初始化数据库"""
        if self._initialized:
            return
        
        await self._init_db()
        await self._load_from_db()
        self._initialized = True
    
    async def _init_db(self):
        """初始化数据库表"""
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS health_stats (
                agent_type TEXT PRIMARY KEY,
                total_tasks INTEGER DEFAULT 0,
                success_tasks INTEGER DEFAULT 0,
                failed_tasks INTEGER DEFAULT 0,
                timeouts INTEGER DEFAULT 0,
                last_updated REAL
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS health_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_type TEXT,
                event_type TEXT,
                error TEXT,
                timestamp REAL
            )
        """)
        await self._db.commit()
        logger.info(f"Health monitor DB initialized: {self._db_path}")
    
    async def _load_from_db(self):
        """从数据库加载状态"""
        async with self._db.execute("SELECT * FROM health_stats") as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                agent_type_str, total, success, failed, timeouts, last_updated = row
                agent_type = AgentType(agent_type_str)
                stats = AgentHealthStats(agent_type)
                stats.total_tasks = total
                stats.success_tasks = success
                stats.failed_tasks = failed
                stats.timeouts = timeouts
                stats.last_updated = last_updated or time.time()
                self._stats[agent_type] = stats
                self._update_global_rate()
    
    async def _save_stats(self, agent_type: AgentType):
        """保存统计到数据库"""
        if not self._db:
            return
        
        stats = self._stats.get(agent_type)
        if not stats:
            return
        
        await self._db.execute("""
            INSERT OR REPLACE INTO health_stats 
            (agent_type, total_tasks, success_tasks, failed_tasks, timeouts, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            agent_type.value,
            stats.total_tasks,
            stats.success_tasks,
            stats.failed_tasks,
            stats.timeouts,
            stats.last_updated,
        ))
        await self._db.commit()
    
    async def _save_event(self, agent_type: AgentType, event_type: str, error: Optional[str] = None):
        """保存事件到数据库"""
        if not self._db:
            return
        
        await self._db.execute("""
            INSERT INTO health_events (agent_type, event_type, error, timestamp)
            VALUES (?, ?, ?, ?)
        """, (agent_type.value, event_type, error, time.time()))
        await self._db.commit()
    
    async def close(self):
        """关闭数据库连接"""
        if self._db:
            await self._db.close()
            self._db = None
    
    def get_or_create_stats(self, agent_type: AgentType) -> AgentHealthStats:
        """获取或创建统计"""
        if agent_type not in self._stats:
            self._stats[agent_type] = AgentHealthStats(agent_type)
        return self._stats[agent_type]
    
    async def record_success(self, agent_type: AgentType):
        """记录成功"""
        async with self._lock:
            stats = self.get_or_create_stats(agent_type)
            stats.record_success()
            self._update_global_rate()
            
            # 保存到数据库
            await self._save_stats(agent_type)
            await self._save_event(agent_type, "success")
            
            logger.info(f"[{agent_type.value}] Success recorded. Rate: {stats.success_rate:.2%}")
    
    async def record_failure(self, agent_type: AgentType, error: Optional[str] = None):
        """记录失败"""
        async with self._lock:
            stats = self.get_or_create_stats(agent_type)
            stats.record_failure(error)
            self._update_global_rate()
            
            # 保存到数据库
            await self._save_stats(agent_type)
            await self._save_event(agent_type, "failure", error)
            
            level = stats.get_health_level()
            if level == HealthLevel.CRITICAL:
                logger.warning(f"[{agent_type.value}] Health CRITICAL! Failure rate: {stats.failure_rate:.2%}")
            elif level == HealthLevel.PAUSED:
                logger.error(f"[{agent_type.value}] Health PAUSED! Failure rate: {stats.failure_rate:.2%}")
    
    async def record_timeout(self, agent_type: AgentType):
        """记录超时"""
        async with self._lock:
            stats = self.get_or_create_stats(agent_type)
            stats.record_timeout()
            self._update_global_rate()
            
            # 保存到数据库
            await self._save_stats(agent_type)
            await self._save_event(agent_type, "timeout")
            
            logger.warning(f"[{agent_type.value}] Timeout recorded")
    
    def _update_global_rate(self):
        """更新全局失败率"""
        total = sum(s.total_tasks for s in self._stats.values())
        if total == 0:
            self._global_failure_rate = 0.0
            return
        
        total_failed = sum(s.failed_tasks for s in self._stats.values())
        self._global_failure_rate = total_failed / total
    
    def get_health_level(self, agent_type: Optional[AgentType] = None) -> HealthLevel:
        """获取健康等级"""
        if agent_type:
            stats = self._stats.get(agent_type)
            return stats.get_health_level() if stats else HealthLevel.HEALTHY
        
        # 全局健康等级
        if self._global_failure_rate <= 0.3:
            return HealthLevel.HEALTHY
        elif self._global_failure_rate <= 0.5:
            return HealthLevel.WARNING
        elif self._global_failure_rate <= 0.7:
            return HealthLevel.CRITICAL
        else:
            return HealthLevel.PAUSED
    
    def is_paused(self) -> bool:
        """是否暂停"""
        return self.get_health_level() == HealthLevel.PAUSED or self._paused
    
    async def pause(self):
        """暂停系统"""
        self._paused = True
        logger.warning("System PAUSED by health monitor")
    
    async def resume(self):
        """恢复系统"""
        self._paused = False
        logger.info("System RESUMED")
    
    def get_all_stats(self) -> dict[AgentType, dict]:
        """获取所有统计"""
        return {
            agent_type: stats.to_dict()
            for agent_type, stats in self._stats.items()
        }
    
    def get_summary(self) -> dict:
        """获取健康度摘要"""
        return {
            "global_failure_rate": self._global_failure_rate,
            "health_level": self.get_health_level().value,
            "is_paused": self.is_paused(),
            "agent_stats": self.get_all_stats(),
        }
    
    async def get_history(self, agent_type: AgentType, limit: int = 100) -> list[dict]:
        """获取历史事件"""
        if not self._db:
            return []
        
        async with self._db.execute("""
            SELECT event_type, error, timestamp 
            FROM health_events 
            WHERE agent_type = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (agent_type.value, limit)) as cursor:
            rows = await cursor.fetchall()
            return [
                {"type": row[0], "error": row[1], "timestamp": row[2]}
                for row in rows
            ]


# 全局健康监控实例
_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor(db_path: Optional[str] = None) -> HealthMonitor:
    """获取健康监控实例"""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor(db_path=db_path)
    return _health_monitor


async def initialize_health_monitor(db_path: Optional[str] = None) -> HealthMonitor:
    """初始化并返回健康监控实例"""
    monitor = get_health_monitor(db_path=db_path)
    await monitor.initialize()
    return monitor
