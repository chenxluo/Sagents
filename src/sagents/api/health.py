"""健康度 API 路由"""
from fastapi import APIRouter

from ..core.health_monitor import get_health_monitor

router = APIRouter(prefix="/health", tags=["健康度"])


@router.get("")
async def get_health():
    """获取健康度摘要"""
    monitor = get_health_monitor()
    return monitor.get_summary()


@router.get("/agents/{agent_type}")
async def get_agent_health(agent_type: str):
    """获取指定 Agent 的健康度"""
    from ..core.state import AgentType
    
    monitor = get_health_monitor()
    
    try:
        agent = AgentType(agent_type)
    except ValueError:
        return {"error": f"Unknown agent type: {agent_type}"}
    
    stats = monitor._stats.get(agent)
    if not stats:
        return {"status": "no_data", "agent_type": agent_type}
    
    return stats.to_dict()


@router.post("/pause")
async def pause_system():
    """暂停系统"""
    monitor = get_health_monitor()
    await monitor.pause()
    return {"status": "paused"}


@router.post("/resume")
async def resume_system():
    """恢复系统"""
    monitor = get_health_monitor()
    await monitor.resume()
    return {"status": "resumed"}
