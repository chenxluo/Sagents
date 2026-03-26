"""Sagents 主入口文件"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_config, ConfigManager
from .core.message_bus import MessageBusRegistry
from .core.orchestrator import Orchestrator, get_orchestrator
from .core.health_monitor import get_health_monitor
from .api import health, tasks

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    logger.info("Starting Sagents...")
    
    config = get_config()
    logger.info(f"Config loaded: log_level={config.log_level}")
    
    # 启动消息总线
    await MessageBusRegistry.start_all()
    logger.info("MessageBus started")
    
    # 启动健康监控
    health_monitor = get_health_monitor()
    logger.info("Health monitor initialized")
    
    yield
    
    # 关闭
    logger.info("Shutting down Sagents...")
    await MessageBusRegistry.stop_all()
    logger.info("Sagents stopped")


# 创建 FastAPI 应用
app = FastAPI(
    title="Sagents",
    description="Multi-Agent System for Automated GitHub Collaboration",
    version="0.1.0",
    lifespan=lifespan,
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(health.router)
app.include_router(tasks.router)


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "Sagents",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/status")
async def status():
    """系统状态"""
    return {
        "status": "running",
        "health": get_health_monitor().get_summary(),
        "agents": {
            "orchestrator": "running",
            "developer": "available",
            "qa_engineer": "available",
            "tech_writer": "available",
        },
        "version": "0.1.0",
    }


async def run_cli():
    """运行 CLI 模式"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Sagents CLI")
    parser.add_argument("--config", "-c", help="Config directory")
    parser.add_argument("--log-level", "-l", default="INFO", help="Log level")
    args = parser.parse_args()
    
    # 设置日志级别
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
    
    # 加载配置
    if args.config:
        config_manager = ConfigManager(args.config)
        config_manager.load()
    
    # 运行协调者
    orchestrator = get_orchestrator()
    await orchestrator.run()


def main():
    """主入口"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] not in ["uvicorn", "fastapi"]:
        # CLI 模式
        asyncio.run(run_cli())
    else:
        # API 服务器模式（通过 uvicorn 运行）
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
