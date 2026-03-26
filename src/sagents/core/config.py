"""配置管理模块"""
import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class AgentTimeoutConfig(BaseModel):
    """Agent 超时配置"""
    max_rounds: int = 50
    max_seconds: int = 3600
    retry_on_timeout: bool = True
    max_retries: int = 2


class TimeoutConfig(BaseModel):
    """超时配置"""
    developer: AgentTimeoutConfig = Field(default_factory=lambda: AgentTimeoutConfig(
        max_rounds=50, max_seconds=3600, retry_on_timeout=True, max_retries=2
    ))
    qa: AgentTimeoutConfig = Field(default_factory=lambda: AgentTimeoutConfig(
        max_rounds=30, max_seconds=1800, retry_on_timeout=False, max_retries=0
    ))
    tech_writer: AgentTimeoutConfig = Field(default_factory=lambda: AgentTimeoutConfig(
        max_rounds=10, max_seconds=300, retry_on_timeout=False, max_retries=0
    ))
    orchestrator: AgentTimeoutConfig = Field(default_factory=lambda: AgentTimeoutConfig(
        max_rounds=100, max_seconds=7200, retry_on_timeout=True, max_retries=3
    ))


class LLMModelConfig(BaseModel):
    """LLM 模型配置"""
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    api_key: Optional[str] = None


class LLMConfig(BaseModel):
    """LLM 配置"""
    developer: LLMModelConfig = Field(default_factory=lambda: LLMModelConfig(provider="anthropic", model="claude-sonnet-4-20250514"))
    qa: LLMModelConfig = Field(default_factory=lambda: LLMModelConfig(provider="openai", model="gpt-4"))
    tech_writer: LLMModelConfig = Field(default_factory=lambda: LLMModelConfig(provider="anthropic", model="claude-haiku"))
    orchestrator: LLMModelConfig = Field(default_factory=lambda: LLMModelConfig(provider="anthropic", model="claude-sonnet-4-20250514"))


class AgentPromptConfig(BaseModel):
    """Agent 提示词配置"""
    role: str = ""
    goal: str = ""
    capabilities: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    response_format: str = ""
    fallback_rules: str = ""


class PromptsConfig(BaseModel):
    """提示词配置"""
    developer: AgentPromptConfig = Field(default_factory=AgentPromptConfig)
    qa: AgentPromptConfig = Field(default_factory=AgentPromptConfig)
    tech_writer: AgentPromptConfig = Field(default_factory=AgentPromptConfig)
    orchestrator: AgentPromptConfig = Field(default_factory=AgentPromptConfig)


class SagentsConfig(BaseModel):
    """Sagents 主配置"""
    db_path: str = "./sagents.db"
    github_token: Optional[str] = None
    log_level: str = "INFO"
    prompt_dir: str = "./config"
    
    # 子配置
    timeouts: TimeoutConfig = Field(default_factory=TimeoutConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    prompts: PromptsConfig = Field(default_factory=PromptsConfig)


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir) if config_dir else Path("./config")
        self._config: Optional[SagentsConfig] = None
    
    def load(self) -> SagentsConfig:
        """加载配置"""
        if self._config:
            return self._config
        
        # 从环境变量覆盖
        config = SagentsConfig(
            db_path=os.getenv("SAGENTS_DB_PATH", "./sagents.db"),
            github_token=os.getenv("SAGENTS_GITHUB_TOKEN"),
            log_level=os.getenv("SAGENTS_LOG_LEVEL", "INFO"),
            prompt_dir=os.getenv("SAGENTS_PROMPT_DIR", "./config"),
        )
        
        # 加载 YAML 配置
        if self.config_dir.exists():
            self._load_yaml_configs(config)
        
        self._config = config
        return config
    
    def _load_yaml_configs(self, config: SagentsConfig):
        """加载 YAML 配置文件"""
        # 加载超时配置
        timeout_file = self.config_dir / "agent_timeouts.yaml"
        if timeout_file.exists():
            with open(timeout_file) as f:
                data = yaml.safe_load(f)
                if data:
                    config.timeouts = TimeoutConfig(**data)
        
        # 加载提示词配置
        prompts_file = self.config_dir / "prompts.yaml"
        if prompts_file.exists():
            with open(prompts_file) as f:
                data = yaml.safe_load(f)
                if data:
                    config.prompts = PromptsConfig(**data)
        
        # 加载模型配置
        models_file = self.config_dir / "models.yaml"
        if models_file.exists():
            with open(models_file) as f:
                data = yaml.safe_load(f)
                if data:
                    config.llm = LLMConfig(**data)
    
    def get_config(self) -> SagentsConfig:
        """获取配置"""
        if not self._config:
            return self.load()
        return self._config


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """获取配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> SagentsConfig:
    """获取配置"""
    return get_config_manager().get_config()
