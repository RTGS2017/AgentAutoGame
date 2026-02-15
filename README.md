# AgentAutoGame 技术架构设计文档

## 当前实现说明（2026-02-14）

- 已按项目要求将 AUTO-MAS 后端源码复制到本仓库（见 `app/` 与 `main.py`）。
- 已优先保留并可用两类能力：
  - 非 MAA 代理脚本（General）管理能力。
  - 任务规划能力（计划表 + 队列 + 定时 + 调度）。
- 为方便 Agent 侧调用，额外提供了聚合接口（见 `app/api/agent.py`）：
  - `POST /api/agent/script/add`：创建 MAA 或 General 脚本。
  - `POST /api/agent/plan/add`：创建 MaaPlan 计划表。
  - `POST /api/agent/planning/create`：一键创建任务规划（队列 + 脚本项 + 可选定时）。

## 许可证调整

- 由于后端代码直接复制自 GPL-3.0 项目 AUTO-MAS，本仓库许可证已调整为 GPL-3.0。
- 详情见 `LICENSE` 与 `COPYRIGHT_NOTICE.md`。

## 后端启动

```bash
pip install -r requirements.txt
python main.py
```

## 文档索引

- 后端落地与接口说明：`BACKEND_USAGE.md`
- 许可证与版权说明：`LICENSE`、`COPYRIGHT_NOTICE.md`

## 平台说明

- 当前以后端 Windows 运行为优先目标。
- 代码包含部分跨平台兼容处理，但不承诺 Linux 全量可用。

## 1. 项目概述

### 1.1 项目定位
AgentAutoGame 是一个智能代理脚本管理器，作为 Agent 技能插件使用。通过自然语言交互，实现对自动化脚本系统所有功能的完整控制，包括脚本管理、任务调度、配置管理等。

### 1.2 核心目标
- **自然语言交互**：用户通过自然语言描述需求，Agent 理解并执行
- **完整功能覆盖**：实现自动化脚本系统的所有功能，包括脚本、用户、队列、计划、模拟器等管理
- **智能决策**：Agent 能够根据上下文和用户意图做出合理的配置决策
- **状态感知**：实时感知系统状态，提供智能建议

### 1.3 技术栈
- **LLM框架**：支持 OpenAI、Claude、本地模型等
- **API客户端**：HTTP/WebSocket 客户端调用后端 API
- **状态管理**：会话状态、上下文管理
- **工具系统**：函数调用（Function Calling）机制

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      AgentAutoGame                          │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   NLU层      │  │  意图识别层   │  │  实体提取层   │   │
│  │ (自然语言理解)│  │ (Intent)      │  │ (Entity)     │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                  │                  │           │
│         └──────────────────┴──────────────────┘           │
│                            │                               │
│                   ┌────────▼────────┐                      │
│                   │   决策引擎      │                      │
│                   │  (Decision Engine)│                    │
│                   └────────┬────────┘                      │
│                            │                               │
│         ┌──────────────────┼──────────────────┐           │
│         │                  │                  │           │
│  ┌──────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐   │
│  │  工具层     │  │  状态管理     │  │  上下文管理   │   │
│  │ (Tools)     │  │ (State)       │  │ (Context)    │   │
│  └──────┬──────┘  └───────────────┘  └──────────────┘   │
│         │                                                 │
│         └──────────────────┬─────────────────────────────┘
│                            │
│                   ┌────────▼────────┐
│                   │   后端 API      │
│                   │   适配层        │
│                   └────────┬────────┘
│                            │
└────────────────────────────┼───────────────────────────────┘
                             │
                   ┌─────────▼─────────┐
                   │   后端服务        │
                   └───────────────────┘
```

### 2.2 核心模块说明

#### 2.2.1 NLU层（自然语言理解）
- **功能**：接收用户自然语言输入，进行初步理解
- **输入**：用户自然语言文本
- **输出**：结构化意图和实体信息
- **技术**：LLM Prompt Engineering + Function Calling

#### 2.2.2 意图识别层
- **功能**：识别用户意图，映射到具体操作
- **支持的意图类型**：
  - `CREATE_SCRIPT` - 创建脚本
  - `UPDATE_SCRIPT` - 更新脚本
  - `DELETE_SCRIPT` - 删除脚本
  - `CREATE_USER` - 创建用户
  - `UPDATE_USER` - 更新用户
  - `CREATE_QUEUE` - 创建队列
  - `START_TASK` - 启动任务
  - `STOP_TASK` - 停止任务
  - `QUERY_STATUS` - 查询状态
  - `CONFIGURE_EMULATOR` - 配置模拟器
  - `SET_SCHEDULE` - 设置定时任务
  - 等等...

#### 2.2.3 实体提取层
- **功能**：从自然语言中提取关键参数
- **提取的实体类型**：
  - 脚本ID、脚本名称、脚本类型
  - 用户ID、用户名称、用户配置
  - 队列ID、队列名称
  - 模拟器ID、模拟器类型
  - 时间、日期、关卡信息
  - 配置参数值

#### 2.2.4 决策引擎
- **功能**：根据意图和实体，决定执行流程
- **决策逻辑**：
  - 参数完整性检查
  - 多步骤操作规划
  - 依赖关系处理
  - 错误恢复策略

#### 2.2.5 工具层（Tools）
- **功能**：封装所有后端 API 调用
- **工具分类**：
  - 脚本管理工具
  - 用户管理工具
  - 队列管理工具
  - 任务调度工具
  - 模拟器管理工具
  - 配置查询工具
  - 历史记录工具

#### 2.2.6 状态管理
- **功能**：管理会话状态和系统状态
- **状态类型**：
  - 会话状态（当前对话上下文）
  - 系统状态（后端服务运行状态）
  - 任务状态（正在执行的任务）
  - 配置状态（当前配置快照）

#### 2.2.7 上下文管理
- **功能**：维护对话历史和上下文信息
- **上下文内容**：
  - 历史对话记录
  - 已执行的操作记录
  - 用户偏好设置
  - 系统状态快照

---

## 3. 详细设计

### 3.1 工具系统设计

#### 3.1.1 脚本管理工具组

```python
# 工具定义示例
tools = [
    {
        "type": "function",
        "function": {
            "name": "create_script",
            "description": "创建新的脚本配置",
            "parameters": {
                "type": "object",
                "properties": {
                    "script_type": {
                        "type": "string",
                        "enum": ["MaaConfig", "GeneralConfig"],
                        "description": "脚本类型：MaaConfig为MAA脚本，GeneralConfig为通用脚本"
                    },
                    "script_name": {
                        "type": "string",
                        "description": "脚本名称"
                    }
                },
                "required": ["script_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_script",
            "description": "查询脚本配置信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "script_id": {
                        "type": "string",
                        "description": "脚本ID，如果为空则查询所有脚本"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_script",
            "description": "更新脚本配置信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "script_id": {
                        "type": "string",
                        "description": "脚本ID"
                    },
                    "config": {
                        "type": "object",
                        "description": "要更新的配置项"
                    }
                },
                "required": ["script_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_script",
            "description": "删除脚本",
            "parameters": {
                "type": "object",
                "properties": {
                    "script_id": {
                        "type": "string",
                        "description": "脚本ID"
                    }
                },
                "required": ["script_id"]
            }
        }
    }
]
```

#### 3.1.2 用户管理工具组

```python
tools.extend([
    {
        "type": "function",
        "function": {
            "name": "create_user",
            "description": "为指定脚本创建新用户",
            "parameters": {
                "type": "object",
                "properties": {
                    "script_id": {
                        "type": "string",
                        "description": "脚本ID"
                    },
                    "user_name": {
                        "type": "string",
                        "description": "用户名称"
                    }
                },
                "required": ["script_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_user",
            "description": "更新用户配置",
            "parameters": {
                "type": "object",
                "properties": {
                    "script_id": {"type": "string"},
                    "user_id": {"type": "string"},
                    "config": {
                        "type": "object",
                        "description": "用户配置项，包括：服务器、关卡、基建模式、任务开关等"
                    }
                },
                "required": ["script_id", "user_id"]
            }
        }
    }
])
```

#### 3.1.3 队列管理工具组

```python
tools.extend([
    {
        "type": "function",
        "function": {
            "name": "create_queue",
            "description": "创建调度队列",
            "parameters": {
                "type": "object",
                "properties": {
                    "queue_name": {
                        "type": "string",
                        "description": "队列名称"
                    },
                    "startup_enabled": {
                        "type": "boolean",
                        "description": "是否在启动时自动运行"
                    },
                    "after_accomplish": {
                        "type": "string",
                        "enum": ["NoAction", "Shutdown", "Reboot", "Hibernate", "Sleep"],
                        "description": "完成后操作"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_queue_item",
            "description": "向队列添加脚本项",
            "parameters": {
                "type": "object",
                "properties": {
                    "queue_id": {"type": "string"},
                    "script_id": {"type": "string"}
                },
                "required": ["queue_id", "script_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_schedule",
            "description": "为队列添加定时任务",
            "parameters": {
                "type": "object",
                "properties": {
                    "queue_id": {"type": "string"},
                    "enabled": {"type": "boolean"},
                    "days": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "执行日期：Monday, Tuesday, ..., Sunday"
                    },
                    "time": {
                        "type": "string",
                        "description": "执行时间，格式：HH:MM"
                    }
                },
                "required": ["queue_id"]
            }
        }
    }
])
```

#### 3.1.4 任务调度工具组

```python
tools.extend([
    {
        "type": "function",
        "function": {
            "name": "start_task",
            "description": "启动任务",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["AutoProxy", "ManualReview", "ScriptConfig"],
                        "description": "任务模式：AutoProxy自动代理，ManualReview手动审核，ScriptConfig脚本配置"
                    },
                    "task_id": {
                        "type": "string",
                        "description": "任务ID，可以是队列ID、脚本ID或用户ID"
                    }
                },
                "required": ["mode", "task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stop_task",
            "description": "停止任务",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "任务ID，使用'ALL'停止所有任务"
                    }
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_task_status",
            "description": "查询任务状态",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "任务ID"
                    }
                }
            }
        }
    }
])
```

#### 3.1.5 模拟器管理工具组

```python
tools.extend([
    {
        "type": "function",
        "function": {
            "name": "create_emulator",
            "description": "创建模拟器配置",
            "parameters": {
                "type": "object",
                "properties": {
                    "emulator_name": {"type": "string"},
                    "emulator_path": {"type": "string"},
                    "emulator_type": {
                        "type": "string",
                        "enum": ["general", "mumu", "ldplayer"]
                    },
                    "boss_key": {
                        "type": "string",
                        "description": "老板键，JSON格式数组，如：['ctrl', 'alt', 'h']"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_emulators",
            "description": "搜索系统中已安装的模拟器",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
])
```

#### 3.1.6 查询工具组

```python
tools.extend([
    {
        "type": "function",
        "function": {
            "name": "get_available_stages",
            "description": "获取可用的关卡列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "stage_type": {
                        "type": "string",
                        "enum": ["Today", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "ALL"],
                        "description": "关卡类型"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_overview",
            "description": "获取系统总览信息",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_history",
            "description": "搜索历史记录",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["AutoProxy", "ManualReview"]
                    },
                    "start_date": {
                        "type": "string",
                        "description": "开始日期，格式：YYYY-MM-DD"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "结束日期，格式：YYYY-MM-DD"
                    }
                }
            }
        }
    }
])
```

### 3.2 API适配层设计

#### 3.2.1 API客户端封装

```python
class BackendAPIClient:
    """后端 API 客户端封装"""
    
    def __init__(self, base_url: str = "http://localhost:36163"):
        self.base_url = base_url
        self.session = httpx.AsyncClient(timeout=30.0)
    
    async def call_api(self, endpoint: str, method: str = "POST", **kwargs):
        """通用API调用方法"""
        url = f"{self.base_url}{endpoint}"
        response = await self.session.request(method, url, **kwargs)
        return response.json()
    
    # 脚本管理API
    async def create_script(self, script_type: str):
        """创建脚本"""
        return await self.call_api(
            "/api/scripts/add",
            json={"type": script_type}
        )
    
    async def get_script(self, script_id: str = None):
        """查询脚本"""
        return await self.call_api(
            "/api/scripts/get",
            json={"scriptId": script_id or ""}
        )
    
    async def update_script(self, script_id: str, config: dict):
        """更新脚本"""
        return await self.call_api(
            "/api/scripts/update",
            json={"scriptId": script_id, "data": config}
        )
    
    async def delete_script(self, script_id: str):
        """删除脚本"""
        return await self.call_api(
            "/api/scripts/delete",
            json={"scriptId": script_id}
        )
    
    # 用户管理API
    async def create_user(self, script_id: str):
        """创建用户"""
        return await self.call_api(
            "/api/scripts/user/add",
            json={"scriptId": script_id}
        )
    
    async def get_user(self, script_id: str, user_id: str = None):
        """查询用户"""
        return await self.call_api(
            "/api/scripts/user/get",
            json={"scriptId": script_id, "userId": user_id or ""}
        )
    
    async def update_user(self, script_id: str, user_id: str, config: dict):
        """更新用户"""
        return await self.call_api(
            "/api/scripts/user/update",
            json={"scriptId": script_id, "userId": user_id, "data": config}
        )
    
    # 队列管理API
    async def create_queue(self):
        """创建队列"""
        return await self.call_api("/api/queue/add")
    
    async def get_queue(self, queue_id: str = None):
        """查询队列"""
        return await self.call_api(
            "/api/queue/get",
            json={"queueId": queue_id or ""}
        )
    
    async def add_queue_item(self, queue_id: str):
        """添加队列项"""
        return await self.call_api(
            "/api/queue/item/add",
            json={"queueId": queue_id}
        )
    
    async def update_queue_item(self, queue_id: str, item_id: str, script_id: str):
        """更新队列项"""
        return await self.call_api(
            "/api/queue/item/update",
            json={
                "queueId": queue_id,
                "queueItemId": item_id,
                "data": {"Info": {"ScriptId": script_id}}
            }
        )
    
    # 任务调度API
    async def start_task(self, mode: str, task_id: str):
        """启动任务"""
        return await self.call_api(
            "/api/dispatch/start",
            json={"mode": mode, "taskId": task_id}
        )
    
    async def stop_task(self, task_id: str):
        """停止任务"""
        return await self.call_api(
            "/api/dispatch/stop",
            json={"taskId": task_id}
        )
    
    # 模拟器管理API
    async def create_emulator(self):
        """创建模拟器"""
        return await self.call_api("/api/emulator/add")
    
    async def get_emulator(self, emulator_id: str = None):
        """查询模拟器"""
        return await self.call_api(
            "/api/emulator/get",
            json={"emulatorId": emulator_id or ""}
        )
    
    async def search_emulators(self):
        """搜索模拟器"""
        return await self.call_api("/api/emulator/emulator/search")
    
    # 查询API
    async def get_stages(self, stage_type: str):
        """获取关卡列表"""
        return await self.call_api(
            "/api/info/combox/stage",
            json={"type": stage_type}
        )
    
    async def get_overview(self):
        """获取系统总览"""
        return await self.call_api("/api/info/get/overview")
    
    async def search_history(self, mode: str, start_date: str, end_date: str):
        """搜索历史记录"""
        return await self.call_api(
            "/api/history/search",
            json={
                "mode": mode,
                "start_date": start_date,
                "end_date": end_date
            }
        )
```

### 3.3 Agent核心引擎设计

```python
class AgentAutoGame:
    """AgentAutoGame 核心引擎"""
    
    def __init__(self, llm_client, api_client: BackendAPIClient):
        self.llm_client = llm_client
        self.api_client = api_client
        self.tools = self._load_tools()
        self.context_manager = ContextManager()
        self.state_manager = StateManager()
    
    def _load_tools(self):
        """加载所有工具定义"""
        # 返回所有工具定义的列表
        return [
            # 脚本管理工具
            self._create_tool("create_script", self._handle_create_script),
            self._create_tool("get_script", self._handle_get_script),
            self._create_tool("update_script", self._handle_update_script),
            self._create_tool("delete_script", self._handle_delete_script),
            # 用户管理工具
            self._create_tool("create_user", self._handle_create_user),
            self._create_tool("update_user", self._handle_update_user),
            # 队列管理工具
            self._create_tool("create_queue", self._handle_create_queue),
            self._create_tool("add_queue_item", self._handle_add_queue_item),
            self._create_tool("add_schedule", self._handle_add_schedule),
            # 任务调度工具
            self._create_tool("start_task", self._handle_start_task),
            self._create_tool("stop_task", self._handle_stop_task),
            # 查询工具
            self._create_tool("get_available_stages", self._handle_get_stages),
            self._create_tool("get_system_overview", self._handle_get_overview),
            # ... 更多工具
        ]
    
    async def process(self, user_input: str) -> str:
        """处理用户输入"""
        # 1. 更新上下文
        self.context_manager.add_user_message(user_input)
        
        # 2. 调用LLM进行意图识别和工具选择
        response = await self.llm_client.chat_completion(
            messages=self.context_manager.get_messages(),
            tools=self.tools,
            tool_choice="auto"
        )
        
        # 3. 处理工具调用
        if response.tool_calls:
            for tool_call in response.tool_calls:
                result = await self._execute_tool(tool_call)
                self.context_manager.add_tool_result(tool_call, result)
            
            # 再次调用LLM生成最终回复
            final_response = await self.llm_client.chat_completion(
                messages=self.context_manager.get_messages()
            )
            return final_response.content
        else:
            return response.content
    
    async def _execute_tool(self, tool_call):
        """执行工具调用"""
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)
        
        # 查找对应的工具处理器
        handler = self._get_tool_handler(tool_name)
        if handler:
            return await handler(**arguments)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    # 工具处理器实现
    async def _handle_create_script(self, script_type: str, script_name: str = None):
        """创建脚本处理器"""
        result = await self.api_client.create_script(script_type)
        if result["code"] == 200:
            script_id = result["scriptId"]
            if script_name:
                await self.api_client.update_script(
                    script_id,
                    {"Info": {"Name": script_name}}
                )
            return f"成功创建脚本，ID: {script_id}"
        else:
            return f"创建脚本失败: {result['message']}"
    
    async def _handle_get_script(self, script_id: str = None):
        """查询脚本处理器"""
        result = await self.api_client.get_script(script_id)
        if result["code"] == 200:
            scripts = result.get("data", {})
            if script_id:
                return f"脚本信息: {json.dumps(scripts.get(script_id, {}), ensure_ascii=False)}"
            else:
                script_list = result.get("index", [])
                return f"共有 {len(script_list)} 个脚本: {', '.join([s['uid'] for s in script_list])}"
        else:
            return f"查询失败: {result['message']}"
    
    # ... 更多工具处理器
```

### 3.4 上下文管理系统

```python
class ContextManager:
    """上下文管理器"""
    
    def __init__(self, max_history: int = 20):
        self.messages = []
        self.max_history = max_history
        self.system_prompt = self._get_system_prompt()
        self._initialize()
    
    def _initialize(self):
        """初始化系统提示"""
        self.messages.append({
            "role": "system",
            "content": self.system_prompt
        })
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是 AgentAutoGame，一个智能的自动化脚本管理助手。

你的职责是帮助用户管理自动化脚本系统，包括：
1. 脚本配置管理（创建、更新、删除脚本）
2. 用户配置管理（为脚本添加和管理用户）
3. 调度队列管理（创建队列、添加定时任务）
4. 任务调度（启动、停止任务）
5. 模拟器管理（配置模拟器）
6. 状态查询（查询脚本、任务、历史记录等）

请始终以友好、专业的方式与用户交流，理解用户的自然语言需求，并执行相应的操作。
如果用户的需求不明确，请主动询问以获取必要信息。"""
    
    def add_user_message(self, content: str):
        """添加用户消息"""
        self.messages.append({
            "role": "user",
            "content": content
        })
        self._trim_history()
    
    def add_assistant_message(self, content: str):
        """添加助手消息"""
        self.messages.append({
            "role": "assistant",
            "content": content
        })
        self._trim_history()
    
    def add_tool_result(self, tool_call, result):
        """添加工具执行结果"""
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": tool_call.function.name,
            "content": str(result)
        })
    
    def get_messages(self):
        """获取消息列表"""
        return self.messages.copy()
    
    def _trim_history(self):
        """修剪历史记录"""
        if len(self.messages) > self.max_history:
            # 保留系统提示和最近的对话
            self.messages = [self.messages[0]] + self.messages[-(self.max_history-1):]
```

### 3.5 状态管理系统

```python
class StateManager:
    """状态管理器"""
    
    def __init__(self, api_client: BackendAPIClient):
        self.api_client = api_client
        self.cache = {}
        self.cache_ttl = 60  # 缓存有效期（秒）
    
    async def get_scripts(self, force_refresh: bool = False):
        """获取脚本列表（带缓存）"""
        cache_key = "scripts"
        if not force_refresh and cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return cached_data
        
        result = await self.api_client.get_script()
        if result["code"] == 200:
            self.cache[cache_key] = (result, time.time())
            return result
        return None
    
    async def get_queues(self, force_refresh: bool = False):
        """获取队列列表（带缓存）"""
        cache_key = "queues"
        if not force_refresh and cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return cached_data
        
        result = await self.api_client.get_queue()
        if result["code"] == 200:
            self.cache[cache_key] = (result, time.time())
            return result
        return None
    
    def invalidate_cache(self, key: str = None):
        """使缓存失效"""
        if key:
            self.cache.pop(key, None)
        else:
            self.cache.clear()
```

---

## 4. 实现细节

### 4.1 项目结构

```
AgentAutoGame/
├── agentautogame/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent.py              # Agent核心引擎
│   │   ├── context.py            # 上下文管理
│   │   └── state.py              # 状态管理
│   ├── api/
│   │   ├── __init__.py
│   │   └── client.py             # 后端 API 客户端
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── script_tools.py       # 脚本管理工具
│   │   ├── user_tools.py         # 用户管理工具
│   │   ├── queue_tools.py        # 队列管理工具
│   │   ├── task_tools.py         # 任务调度工具
│   │   ├── emulator_tools.py     # 模拟器管理工具
│   │   └── query_tools.py        # 查询工具
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── llm_client.py         # LLM客户端封装
│   │   └── helpers.py            # 辅助函数
│   └── config/
│       ├── __init__.py
│       └── settings.py            # 配置管理
├── tests/
│   ├── test_agent.py
│   ├── test_api_client.py
│   └── test_tools.py
├── examples/
│   ├── basic_usage.py
│   └── advanced_usage.py
├── README.md
├── requirements.txt
└── setup.py
```

### 4.2 配置管理

```python
# config/settings.py
from pydantic import BaseSettings

class Settings(BaseSettings):
    # 后端 API 配置
    backend_url: str = "http://localhost:36163"
    api_timeout: int = 30
    
    # LLM配置
    llm_provider: str = "openai"  # openai, anthropic, local
    llm_api_key: str = ""
    llm_model: str = "gpt-4"
    llm_base_url: str = None  # 用于本地模型
    
    # Agent配置
    max_history: int = 20
    cache_ttl: int = 60
    
    class Config:
        env_file = ".env"
```

### 4.3 工具定义规范

每个工具需要定义：
1. **工具名称**：清晰的函数名
2. **工具描述**：详细说明工具用途和使用场景
3. **参数定义**：完整的参数类型和描述
4. **处理器函数**：实际的执行逻辑

### 4.4 错误处理策略

```python
class AgentError(Exception):
    """Agent基础异常"""
    pass

class APIError(AgentError):
    """API调用错误"""
    pass

class ValidationError(AgentError):
    """参数验证错误"""
    pass

async def safe_execute_tool(tool_handler, **kwargs):
    """安全执行工具"""
    try:
        return await tool_handler(**kwargs)
    except APIError as e:
        return f"API调用失败: {str(e)}"
    except ValidationError as e:
        return f"参数错误: {str(e)}"
    except Exception as e:
        return f"执行失败: {str(e)}"
```

---

## 5. 使用示例

### 5.1 基础使用

```python
from agentautogame import AgentAutoGame
from agentautogame.api import BackendAPIClient
from agentautogame.utils import OpenAIClient

# 初始化
api_client = BackendAPIClient(base_url="http://localhost:36163")
llm_client = OpenAIClient(api_key="your-api-key", model="gpt-4")
agent = AgentAutoGame(llm_client, api_client)

# 使用
response = await agent.process("帮我创建一个MAA脚本，名字叫'主账号'")
print(response)
```

### 5.2 复杂场景示例

```python
# 场景1：创建完整的自动化流程
user_input = """
我想创建一个自动化流程：
1. 创建一个MAA脚本，名字叫'主账号脚本'
2. 为这个脚本添加一个用户，名字叫'账号1'，服务器选择官方服
3. 设置用户每天刷1-7关卡
4. 创建一个队列，名字叫'每日任务'
5. 把脚本添加到队列中
6. 设置队列每天早上8点自动运行
"""

response = await agent.process(user_input)
print(response)

# 场景2：查询和修改
user_input = """
查看一下当前有哪些脚本在运行，然后停止所有任务
"""

response = await agent.process(user_input)
print(response)
```

---

## 6. 扩展性设计

### 6.1 插件系统
- 支持自定义工具扩展
- 支持自定义意图识别器
- 支持自定义响应格式化

### 6.2 多Agent协作
- 支持多个Agent实例
- 支持Agent间通信
- 支持任务分工

### 6.3 持久化存储
- 会话状态持久化
- 用户偏好存储
- 操作历史记录

---

## 7. 测试策略

### 7.1 单元测试
- API客户端测试
- 工具处理器测试
- 上下文管理测试

### 7.2 集成测试
- 端到端流程测试
- 多步骤操作测试
- 错误恢复测试

### 7.3 性能测试
- 响应时间测试
- 并发处理测试
- 内存使用测试

---

## 8. 部署方案

### 8.1 作为技能插件
- 提供标准插件接口
- 支持配置注入
- 支持生命周期管理

### 8.2 独立服务
- 提供REST API接口
- 提供WebSocket接口
- 支持多客户端连接

---

## 9. 安全考虑

### 9.1 API安全
- API密钥管理
- 请求签名验证
- 访问权限控制

### 9.2 数据安全
- 敏感信息加密
- 日志脱敏
- 数据备份

---

## 10. 未来规划

1. **智能推荐**：根据历史数据推荐最优配置
2. **异常检测**：自动检测异常任务并告警
3. **性能优化**：自动优化任务执行效率
4. **多语言支持**：支持英文等其他语言
5. **可视化界面**：提供Web界面进行可视化操作

---

## 附录

### A. 后端 API 映射表

| Agent工具 | 后端 API | 说明 |
|----------|---------|------|
| create_script | POST /api/scripts/add | 创建脚本 |
| get_script | POST /api/scripts/get | 查询脚本 |
| update_script | POST /api/scripts/update | 更新脚本 |
| delete_script | POST /api/scripts/delete | 删除脚本 |
| create_user | POST /api/scripts/user/add | 创建用户 |
| update_user | POST /api/scripts/user/update | 更新用户 |
| create_queue | POST /api/queue/add | 创建队列 |
| add_queue_item | POST /api/queue/item/add | 添加队列项 |
| start_task | POST /api/dispatch/start | 启动任务 |
| stop_task | POST /api/dispatch/stop | 停止任务 |
| ... | ... | ... |

### B. 意图到工具的映射

| 用户意图 | 工具组合 | 说明 |
|---------|---------|------|
| "创建一个脚本" | create_script | 单步操作 |
| "设置用户每天刷1-7" | update_user (多步) | 需要先查询用户，再更新 |
| "创建一个完整的自动化流程" | create_script → create_user → create_queue → add_queue_item → add_schedule | 多步操作链 |

---

**文档版本**: v1.0  
**最后更新**: 2026-02-13  
**作者**: 柏斯阔落
