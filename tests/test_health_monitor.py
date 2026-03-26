"""健康监控测试"""
import pytest

from sagents.core.state import AgentType, HealthLevel
from sagents.core.health_monitor import HealthMonitor, AgentHealthStats


@pytest.fixture
def health_monitor():
    """创建健康监控器"""
    return HealthMonitor()


def test_agent_health_stats():
    """测试 Agent 健康统计"""
    stats = AgentHealthStats(AgentType.DEVELOPER)
    
    assert stats.total_tasks == 0
    assert stats.failure_rate == 0.0
    assert stats.success_rate == 1.0
    
    # 记录成功
    stats.record_success()
    assert stats.total_tasks == 1
    assert stats.success_tasks == 1
    assert stats.failure_rate == 0.0
    
    # 记录失败
    stats.record_failure()
    assert stats.total_tasks == 2
    assert stats.failed_tasks == 1
    assert stats.failure_rate == 0.5
    
    # 健康等级应该是 WARNING
    assert stats.get_health_level() == HealthLevel.WARNING


def test_health_monitor_get_or_create_stats():
    """测试获取或创建统计"""
    monitor = HealthMonitor()
    
    stats1 = monitor.get_or_create_stats(AgentType.DEVELOPER)
    stats2 = monitor.get_or_create_stats(AgentType.DEVELOPER)
    
    assert stats1 is stats2  # 应该是同一个对象


@pytest.mark.asyncio
async def test_record_success():
    """测试记录成功"""
    monitor = HealthMonitor()
    
    await monitor.record_success(AgentType.DEVELOPER)
    await monitor.record_success(AgentType.DEVELOPER)
    
    stats = monitor._stats[AgentType.DEVELOPER]
    assert stats.total_tasks == 2
    assert stats.success_tasks == 2


@pytest.mark.asyncio
async def test_record_failure():
    """测试记录失败"""
    monitor = HealthMonitor()
    
    await monitor.record_failure(AgentType.DEVELOPER)
    
    stats = monitor._stats[AgentType.DEVELOPER]
    assert stats.total_tasks == 1
    assert stats.failed_tasks == 1


@pytest.mark.asyncio
async def test_record_timeout():
    """测试记录超时"""
    monitor = HealthMonitor()
    
    await monitor.record_timeout(AgentType.DEVELOPER)
    
    stats = monitor._stats[AgentType.DEVELOPER]
    assert stats.total_tasks == 1
    assert stats.timeouts == 1


def test_get_health_level():
    """测试获取健康等级"""
    monitor = HealthMonitor()
    
    # 无数据时应该是 HEALTHY
    assert monitor.get_health_level() == HealthLevel.HEALTHY
    
    # 添加统计
    stats = monitor.get_or_create_stats(AgentType.DEVELOPER)
    stats.total_tasks = 100
    stats.failed_tasks = 10
    
    # 更新全局失败率
    monitor._update_global_rate()
    assert monitor.get_health_level() == HealthLevel.HEALTHY
    
    stats.failed_tasks = 40
    monitor._update_global_rate()
    assert monitor.get_health_level() == HealthLevel.WARNING
    
    stats.failed_tasks = 60
    monitor._update_global_rate()
    assert monitor.get_health_level() == HealthLevel.CRITICAL
    
    stats.failed_tasks = 80
    monitor._update_global_rate()
    assert monitor.get_health_level() == HealthLevel.PAUSED


@pytest.mark.asyncio
async def test_pause_resume():
    """测试暂停和恢复"""
    monitor = HealthMonitor()
    
    # 默认不暂停
    assert not monitor.is_paused()
    
    # 暂停
    await monitor.pause()
    assert monitor.is_paused()
    
    # 恢复
    await monitor.resume()
    assert not monitor.is_paused()


def test_get_all_stats():
    """测试获取所有统计"""
    monitor = HealthMonitor()
    
    monitor.get_or_create_stats(AgentType.DEVELOPER)
    monitor.get_or_create_stats(AgentType.QA_ENGINEER)
    
    all_stats = monitor.get_all_stats()
    
    assert AgentType.DEVELOPER in all_stats
    assert AgentType.QA_ENGINEER in all_stats


def test_get_summary():
    """测试获取摘要"""
    monitor = HealthMonitor()
    
    monitor.get_or_create_stats(AgentType.DEVELOPER)
    
    summary = monitor.get_summary()
    
    assert "global_failure_rate" in summary
    assert "health_level" in summary
    assert "is_paused" in summary
    assert "agent_stats" in summary
