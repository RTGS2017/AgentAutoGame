# AgentAutoGame 后端接入文档

## 1. 当前落地范围

本仓库已直接复制 AUTO-MAS 后端源码，并在此基础上补充 Agent 聚合接口。

- 已落地功能
  - 脚本管理（含 `MAA` / `General`）
  - 用户管理
  - 计划管理（`MaaPlan`）
  - 调度队列与定时项
  - 任务调度（启动/停止）
  - 信息查询（下拉框、总览）
- 新增聚合接口
  - `POST /api/agent/script/add`
  - `POST /api/agent/plan/add`
  - `POST /api/agent/planning/create`

## 2. 运行环境与平台说明

- 推荐平台：Windows（与 AUTO-MAS 后端一致）
- 当前策略：Windows 优先；未对 Linux 做专门支持承诺
- Python：建议 3.11+

## 3. 启动方式

```bash
pip install -r requirements.txt
python main.py
```

默认监听：`http://0.0.0.0:36163`

## 4. 关键目录

- 代码入口：`main.py`
- 后端实现：`app/`
- 配置与数据（运行后生成）
  - `config/`
  - `data/`
  - `history/`
  - `debug/`

## 5. 接口分组总览

### 5.1 原生后端接口（AUTO-MAS）

- 脚本管理：`/api/scripts/*`
- 计划管理：`/api/plan/*`
- 队列管理：`/api/queue/*`
- 调度管理：`/api/dispatch/*`
- 信息查询：`/api/info/*`

### 5.2 Agent 聚合接口（新增）

#### A) 创建代理脚本（支持非 MAA）

`POST /api/agent/script/add`

请求示例：

```json
{
  "type": "General",
  "name": "我的通用代理脚本"
}
```

响应示例：

```json
{
  "code": 200,
  "status": "success",
  "message": "操作成功",
  "scriptId": "c281b0f7-b965-4bd6-a32b-95d02f8ba0f8",
  "scriptType": "GeneralConfig"
}
```

#### B) 创建任务规划计划表

`POST /api/agent/plan/add`

请求示例：

```json
{
  "name": "日常规划",
  "mode": "Weekly"
}
```

#### C) 一键创建任务规划（队列 + 队列项 + 定时）

`POST /api/agent/planning/create`

请求示例：

```json
{
  "queue_name": "每日自动任务",
  "script_ids": [
    "c281b0f7-b965-4bd6-a32b-95d02f8ba0f8"
  ],
  "startup_enabled": false,
  "time_enabled": true,
  "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
  "time": "08:00",
  "after_accomplish": "NoAction"
}
```

响应示例：

```json
{
  "code": 200,
  "status": "success",
  "message": "操作成功",
  "queueId": "0f10f517-0103-4638-b419-8e8f568d790a",
  "queueItemIds": ["002f5b90-4dc7-4342-aea9-0566e0e8b00f"],
  "timeSetId": "1f4f5a63-cd3d-447f-aace-4d609f19fcbb"
}
```

## 6. 典型调用流程

1. 调 `POST /api/agent/script/add` 创建 `General` 脚本。
2. 调 `POST /api/scripts/user/add` 给脚本添加用户。
3. 调 `POST /api/agent/planning/create` 创建队列与定时。
4. 调 `POST /api/dispatch/start` 启动任务。
5. 调 `POST /api/dispatch/stop` 停止任务。

## 7. 许可证与版权

- 本仓库后端代码来自 AUTO-MAS（GPL-3.0）。
- 许可证见 `LICENSE`。
- 版权说明见 `COPYRIGHT_NOTICE.md`。
