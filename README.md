# Sagents

Multi-Agent System for Automated GitHub Collaboration

## 项目概述

Sagents 是一个基于多智能体协作（Multi-Agent System）的全自动 GitHub 异地协作开发团队管线原型。

### 核心能力

- **统筹规划**: 自动拆解需求为可执行任务
- **文档维护**: 保持代码与文档同步
- **代码流转**: 多人协作的代码评审流程
- **自动测试**: 持续集成与自动化测试
- **Bug 修复**: 自动定位和修复问题

## 快速开始

### 安装

```bash
pip install -e .
```

### 运行

```bash
# 启动 API 服务器
uvicorn sagents.main:app --reload

# 或运行 CLI
python -m sagents.main
```

### 运行示例

```bash
python examples/simple_workflow.py
```

## 技术栈

- **后端语言**: Python 3.11+
- **Agent 框架**: LangGraph
- **最小执行单元**: OpenHands SDK
- **Web 框架**: FastAPI
- **持久化**: SQLite
- **LLM 适配层**: LiteLLM

## 项目结构

```
sagents/
├── src/sagents/
│   ├── core/           # 核心框架
│   ├── agents/         # Agent 实现
│   ├── tools/          # 工具集
│   ├── prompts/        # 提示词配置
│   └── api/            # FastAPI 路由
├── tests/              # 测试目录
├── config/             # 配置文件
├── examples/           # 示例
└── pyproject.toml
```

## License

MIT