# Sagents 架构设计文档

> **项目代号**：Sagents  
> **文档版本**：v1.0  
> **更新日期**：2026-03-26  
> **状态**：✅ 设计完成，待实现

---

## 1. 项目概述

### 1.1 目标

构建一个基于多智能体协作（Multi-Agent System）的全自动 GitHub 异地协作开发团队管线原型。

### 1.2 核心能力

| 能力 | 描述 |
|------|------|
| **统筹规划** | 自动拆解需求为可执行任务 |
| **文档维护** | 保持代码与文档同步 |
| **代码流转** | 多人协作的代码评审流程 |
| **自动测试** | 持续集成与自动化测试 |
| **Bug 修复** | 自动定位和修复问题 |

### 1.3 核心原则

- **无人值守**：各 Agent 在自身职责范围内完全自主完成工作
- **职责分离**：每个 Agent 有明确的边界，不越权
- **可观测性**：完整的健康度监控和日志记录

---

## 2. 技术栈

| 组件 | 技术选型 | 版本 | 说明 |
|------|----------|------|------|
| 后端语言 | Python | 3.11+ | 生态丰富，AI/ML 支持好 |
| Agent 框架 | LangGraph | Latest | 状态机设计，适合多 Agent 协作 |
| 最小执行单元 | OpenHands SDK | Current | 成熟的沙盒执行环境 |
| Web 框架 | FastAPI | Latest | 轻量、高性能、异步支持 |
| 持久化 | SQLite | 3.x | 简单可靠，无需额外服务 |
| LLM 适配层 | LiteLLM | Current | 统一接口，支持多模型 |
| 配置管理 | Pydantic + YAML | - | 类型安全，配置分离 |

**运行环境**：Linux / WSL (Windows Subsystem for Linux)

---

## 3. 系统架构

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SAGENTS SYSTEM                                  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                        MESSAGE BUS (asyncio)                          │   │
│  │                 异步消息总线，支持 SYNC / ASYNC 模式                    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                    ▲                          ▲                          │
│                    │                          │                          │
│  ┌─────────────────┴─────────────────┐  ┌──────┴───────────────────────┐  │
│  │      ORCHESTRATOR (协调者)         │  │      HEALTH MONITOR          │  │
│  │  • 维护仓库分支、决定合并          │  │  • 失败率统计                  │  │
│  │  • 下发任务、评估并行可能性        │  │  • 告警与系统暂停              │  │
│  │  • 等待工作、被唤醒处理            │  │                               │  │
│  └───────────────────────────────────┘  └───────────────────────────────┘  │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  DEVELOPER  │  │     QA      │  │ TECH_WRITER│  │   DEV_OPS   │        │
│  │  (开发者)   │  │  (测试者)   │  │ (文档维护) │  │   (可选)    │        │
│  │            │  │            │  │            │  │            │        │
│  │ • 自主规划  │  │ • 全方位测试 │  │ • 同步文档 │  │            │        │
│  │ • 编写代码  │  │ • 直接返工  │  │ • 有权合并 │  │            │        │
│  │ • 解决冲突  │  │ • 通知结果  │  │ • 标记问题  │  │            │        │
│  └─────────────┘  └──────┬──────┘  └─────────────┘  └─────────────┘        │
│                          │                                                  │
│                          ▼                                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                          GITHUB                                       │   │
│  │               PR / Branch / Issue / Actions                           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Agent 间交互流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              典型工作流程                                      │
└─────────────────────────────────────────────────────────────────────────────┘

[1] PR 合并触发
    │
    ▼
┌─────────────────┐
│   协调者         │
│  被唤醒处理      │
└────────┬────────┘
         │
         │ SYNC (等待完成)
         ▼
┌─────────────────┐
│  文档维护者       │
│  更新文档 → 合并   │
└────────┬────────┘
         │
         │ ASYNC (并行)
         │ ASYNC (并行)
         ▼
┌─────────────────┐   ┌─────────────────┐
│  开发者 A        │   │  开发者 B        │
│  接收任务        │   │  接收任务        │
└────────┬────────┘   └────────┬────────┘
         │                    │
         ▼                    ▼
┌─────────────────┐   ┌─────────────────┐
│  提交 PR        │   │  提交 PR        │
│  自动触发测试    │   │  自动触发测试    │
└────────┬────────┘   └────────┬────────┘
         │                    │
         ▼                    ▼
┌─────────────────────────────────────────┐
│              测试者                       │
│  直接通知开发者返工 / 通知协调者通过        │
└─────────────────────────────────────────┘
         │                    │
         ▼                    ▼
┌─────────────────┐   ┌─────────────────┐
│  开发者 A 返工   │   │  协调者决定合并  │
│  (复用上下文)    │   │                  │
└─────────────────┘   └─────────────────┘
```

---

## 4. Agent 详细设计

### 4.1 协调者 (Orchestrator)

**职责**：
- 维护仓库分支结构，决定合并时机
- 评估任务并行可能性，下发任务
- 接收测试结果，决定合并或返工
- 维护项目蓝图文档（仅自己参考）

**权限**：
- GitHub: 创建分支、合并PR、评论
- 消息总线: 调用所有Agent
- 文件: 仅读写项目蓝图文档

**不做**：
- ❌ 不写代码
- ❌ 不做细节规划
- ❌ 不看代码细节（只看PR说明和测试意见）

**调用模式**：
- `SYNC`: 等待结果（文档更新必须用）
- `ASYNC`: 发完即返回（并行开发）
- `wait_for_work()`: 进入等待状态，直到被唤醒

### 4.2 开发者 (Developer)

**职责**：
- 接收任务后自主规划
- 按 todo 分步执行
- 编写/修改代码，运行测试
- 提交 PR，解决合并冲突
- 修复测试反馈的问题

**工具集**：
| 工具 | 说明 |
|------|------|
| `read_file` | 读取文件内容 |
| `write_file` | 写入文件 |
| `edit_file` | 编辑文件 |
| `run_command` | 执行终端命令 |
| `create_todo` | 创建待办事项 |
| `git_*` | Git 操作 |
| `create_pr` | 创建 PR |

**特点**：
- 依赖文档理解项目
- 任务完成后自动触发测试者
- 返工时复用当前会话上下文

### 4.3 测试者 (QA Engineer)

**职责**：
- 运行全套测试（单元/集成/回归）
- 代码质量和风格检查
- 安全基础扫描
- 生成详细的测试报告

**特点**：
- 直接通知开发者返工（不经过协调者）
- 保持开发者会话上下文
- 通知协调者测试通过

### 4.4 文档维护者 (Tech Writer)

**职责**：
- 分析代码变动，更新相关文档
- 确保文档与代码一致
- 标记过时代码和低质量文件
- 通知协调者需要清理的内容

**权限**：
- ✅ 仅限读写 `.md` 文件
- ✅ 有权直接合并自己的文档 PR
- ❌ 不直接删除/修改代码文件

**特点**：
- 协调者调用时必须 `SYNC` 等待完成
- 文档是系统运行的前提条件

### 4.5 DevOps (可选/后期)

**MVP 阶段暂不实现**

可能职责：
- 管理 GitHub Actions workflow
- 维护 CI/CD 配置
- 触发部署流程

---

## 5. A2A 通信协议

### 5.1 消息类型

| 类型 | 模式 | 典型场景 |
|------|------|---------|
| `INVOKE` | SYNC | 协调者 → 开发者：实现功能 |
| `INVOKE` | ASYNC | 协调者 → 开发者：并行任务 |
| `NOTIFICATION` | Fire-Forget | 测试者 → 开发者：返工通知 |
| `NOTIFICATION` | Fire-Forget | 测试者 → 协调者：通过通知 |

### 5.2 消息格式

```python
class MessageType(Enum):
    INVOKE = "invoke"           # 调用
    RESPONSE = "response"       # 响应
    ERROR = "error"             # 错误
    NOTIFICATION = "notification"  # 通知

class InvokeMode(Enum):
    SYNC = "sync"      # 等待结果
    ASYNC = "async"    # 发完即返回

class AgentMessage(BaseModel):
    id: str                           # 消息ID
    msg_type: MessageType             # 消息类型
    sender: str                       # 发送方
    receiver: str                     # 接收方
    content: dict                     # 消息内容
    invoke_mode: InvokeMode            # 调用模式
    correlation_id: str | None = None # 关联ID（用于响应匹配）
    timeout_seconds: int | None = None
    created_at: str
```

### 5.3 消息总线 (MessageBus)

```python
class MessageBus:
    """异步消息总线"""
    
    async def invoke(sender, receiver, content, mode, timeout):
        """同步/异步调用"""
    
    async def send(message):
        """发送通知（Fire-Forget）"""
    
    async def wait_for_wakeup(agent, conditions):
        """等待唤醒"""
    
    async def subscribe(event, handler):
        """订阅事件"""
```

---

## 6. 健康度监控

### 6.1 健康等级

| 等级 | 失败率 | 说明 |
|------|--------|------|
| 🟢 HEALTHY | 0-30% | 正常运行 |
| 🟡 WARNING | 30-50% | 需要关注 |
| 🔴 CRITICAL | 50-70% | 需要人工介入 |
| ⏸️ PAUSED | >70% | 系统暂停 |

### 6.2 超时配置（可配置）

```yaml
# config/agent_timeouts.yaml

developer:
  max_rounds: 50
  max_seconds: 3600
  retry_on_timeout: true
  max_retries: 2

qa:
  max_rounds: 30
  max_seconds: 1800
  retry_on_timeout: false

tech_writer:
  max_rounds: 10
  max_seconds: 300
  retry_on_timeout: false
```

---

## 7. Agent 提示词配置

所有 Agent 的系统提示词均可配置，支持文件覆盖和环境变量。

### 7.1 配置结构

```python
class AgentPromptConfig(BaseModel):
    role: str              # 角色名称
    goal: str              # 核心目标
    capabilities: list[str]  # 能力列表
    constraints: list[str]  # 约束条件
    tools: list[str]        # 可用工具
    response_format: str     # 输出格式要求
    fallback_rules: str     # 失败处理规则
```

### 7.2 配置加载优先级

1. 环境变量指定的配置文件
2. `config/prompts.yaml`
3. 内置默认配置

### 7.3 配置文件示例

```yaml
# config/prompts.yaml

developer:
  role: "高级 Python 开发者"
  goal: "编写简洁、高效、可维护的 Python 代码"
  capabilities:
    - "Python 代码编写"
    - "单元测试编写"
    - "类型注解"
    - "异步编程"
  constraints:
    - "优先使用类型注解"
    - "保持函数简洁，单一职责"
    - "必须添加 docstring"
```

---

## 8. 项目结构

```
Sagents/
├── src/
│   └── sagents/
│       ├── __init__.py
│       ├── main.py                    # 入口文件
│       ├── core/                      # 核心框架
│       │   ├── __init__.py
│       │   ├── config.py             # 配置管理
│       │   ├── message_bus.py        # 消息总线
│       │   ├── orchestrator.py       # 协调者
│       │   ├── health_monitor.py     # 健康度监控
│       │   └── state.py              # 状态定义
│       ├── agents/                    # Agent 实现
│       │   ├── __init__.py
│       │   ├── base.py               # Agent 基类
│       │   ├── developer.py          # 开发者
│       │   ├── qa_engineer.py        # 测试者
│       │   └── tech_writer.py         # 文档维护者
│       ├── tools/                     # 工具集
│       │   ├── __init__.py
│       │   ├── github_tool.py        # GitHub API
│       │   ├── file_tool.py           # 文件操作
│       │   └── terminal_tool.py       # 终端执行
│       ├── prompts/                   # 提示词配置
│       │   ├── __init__.py
│       │   └── default_prompts.py     # 默认提示词
│       └── api/                       # FastAPI 路由
│           ├── __init__.py
│           ├── health.py             # 健康度 API
│           └── tasks.py              # 任务管理 API
├── tests/                             # 测试目录
│   ├── __init__.py
│   ├── test_message_bus.py
│   ├── test_orchestrator.py
│   ├── test_agents.py
│   └── test_health_monitor.py
├── config/                             # 配置文件
│   ├── agent_timeouts.yaml
│   └── prompts.yaml
├── examples/                           # 示例
│   └── simple_workflow.py
├── pyproject.toml
├── uv.lock
└── README.md
```

---

## 9. 配置说明

### 9.1 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SAGENTS_DB_PATH` | SQLite 数据库路径 | `./sagents.db` |
| `SAGENTS_GITHUB_TOKEN` | GitHub 访问令牌 | - |
| `SAGENTS_LOG_LEVEL` | 日志级别 | INFO |
| `SAGENTS_PROMPT_DIR` | 提示词配置目录 | `./config` |

### 9.2 LLM 模型配置

```yaml
# config/models.yaml

developer:
  provider: "anthropic"
  model: "claude-sonnet-4-5-20250929"
  api_key: "${ANTHROPIC_API_KEY}"

qa:
  provider: "openai"
  model: "gpt-4"
  api_key: "${OPENAI_API_KEY}"

tech_writer:
  provider: "anthropic"
  model: "claude-haiku"
  api_key: "${ANTHROPIC_API_KEY}"
```

---

## 10. 数据流

### 10.1 PR 处理流程

```
1. PR 合并
   ↓
2. 协调者被唤醒
   ↓
3. SYNC 调用文档维护者（等待完成）
   ↓
4. ASYNC 下发多个开发任务
   ↓
5. 开发者自主执行，提交 PR
   ↓
6. 自动触发测试者
   ↓
7a. 测试失败 → 直接返工给开发者（复用上下文）
    ↓
    开发者修复 → 重新测试
    ↓
7b. 测试通过 → 通知协调者
    ↓
8. 协调者决定合并或返工
```

### 10.2 消息流

```
协调者 ──INVOKE(SYNC)──→ 文档维护者
         ↑                    │
         │              更新文档
         │                    ↓
         └──────RESPONSE──────┘

协调者 ──INVOKE(ASYNC)──→ 开发者A ──自动──→ 测试者
         │                    │                   │
         │                    │              直接通知
         │                    │                   ↓
         │                    │              开发者A 返工
         │                    │                   │
         │                    ↓                   ↓
         │              测试通过 ←──────────────┘
         │                    │
         └─────NOTIFY─────────┴──→ 协调者
                                       ↓
                                  决定合并
```

---

## 11. 实现计划

### Phase 1: 核心框架
- [ ] 项目结构搭建
- [ ] 配置系统
- [ ] 消息总线
- [ ] 健康度监控

### Phase 2: Agent 实现
- [ ] Agent 基类
- [ ] 协调者
- [ ] 开发者
- [ ] 测试者
- [ ] 文档维护者

### Phase 3: 工具集
- [ ] GitHub API 工具
- [ ] 文件操作工具
- [ ] 终端执行工具

### Phase 4: 集成测试
- [ ] 单元测试
- [ ] 集成测试
- [ ] 端到端测试

### Phase 5: API & 部署
- [ ] FastAPI 接口
- [ ] 健康度 API
- [ ] 部署文档

---

## 12. 附录

### 12.1 参考资料

- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [OpenHands SDK](https://docs.openhands.dev/)
- [LiteLLM 文档](https://docs.litellm.ai/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)

### 12.2 术语表

| 术语 | 说明 |
|------|------|
| Agent | 智能体，能够自主执行任务的软件实体 |
| Orchestrator | 协调者，负责任务编排和调度 |
| Message Bus | 消息总线，Agent 间通信基础设施 |
| SYNC | 同步调用，等待结果返回 |
| ASYNC | 异步调用，发完即返回 |
| PR | Pull Request，代码评审请求 |
| Health Monitor | 健康度监控，监控系统运行状态 |

---

*本文档随代码更新同步维护*
*Sagents 项目组*
