# MAA 自动化控制 MCP 插件 v5.1

无前端、自包含的 MCP 插件，用于控制 [MAA (MaaAssistantArknights)](https://github.com/MaaAssistantArknights/MaaAssistantArknights)。AI 只需一句自然语言指令即可完成从模拟器启动到任务执行的完整流程。

## v5.1 优化重点：降低 AI 调度负荷

每次任务都是**单次调用**——AI 读 manifest、决定参数、发一次请求、等结果。v5.1 围绕这个模式做了四项结构性优化：

| 优化 | 效果 |
|------|------|
| **参数自动推断 tasks** | AI 传 `roguelike_core_char="棘刺"` 即自动启用 Roguelike，无需手写 tasks 字典 |
| **`from_params()` 批量构造** | 新增字段只改 dataclass，agent.py 零改动（消除 50+ 行手动 params.get） |
| **策略型预设** | `"肉鸽刷投资"`、`"加急公招"` 等一个词代替 3-5 个参数组合 |
| **manifest 分层精简** | 常用参数直接列出，高级参数分组概述，AI 阅读量减少 60% |

---

## 核心工作流

```
AI 发出指令（如 preset="收基建"）
  │
  ├─ 1. 解析：preset / script_profile / 纯参数（自动推断 tasks）
  ├─ 2. 验证 MAA 路径
  ├─ 3. ADB 地址：已配置 → 直接用 / 未配置 → 自动发现
  ├─ 4. 模拟器：需要时自动启动
  ├─ 5. MAATaskConfig.from_params() 批量构造配置
  ├─ 6. EnhancedMAAExecutor 执行（备份→写配置→启动MAA→监控→重试→还原）
  └─ 7. 返回结构化结果
```

### 五种执行模式

```json
// 1. 预设（推荐）— 一个词搞定
{"preset": "收基建"}

// 2. 预设 + 微调 — 覆盖个别参数
{"preset": "刷龙门币", "medicine_count": 20}

// 3. 纯参数 — 自动推断 tasks，无需手写
{"roguelike_core_char": "棘刺", "roguelike_stop_at_final_boss": true}
// → 自动推断启用 StartUp + Roguelike

// 4. 脚本配置
{"script_profile": "main_account"}

// 5. 队列
{"queue": ["main_account", "sub_account"]}
```

### 自动推断规则

| 参数前缀 / 参数名 | 自动启用任务 |
|-------------------|------------|
| `roguelike_*` | Roguelike |
| `reclamation_*` | Reclamation |
| `recruit_*` | Recruit |
| `infrast_*` / `custom_infrast_*` | Infrast |
| `mall_*` | Mall |
| `award_*` | Award |
| `stage` / `medicine_count` / `fight_*` 等 | Fight |

始终自动包含 `StartUp`。如已有显式 `tasks` 字典，推断结果只做补充不覆盖。

---

## MCP 工具一览（5 个）

| 工具 | 说明 |
|------|------|
| `execute_task` | 执行任务。传 preset 或直接传参数 |
| `configure_maa` | 配置 MAA 路径、模拟器、脚本、定时任务（仅首次） |
| `get_status` | 查询状态 |
| `stop_task` | 停止当前任务 |
| `list_presets` | 列出所有预设和别名 |

---

## 预设任务

25 个内置预设，59 个中文别名。**策略预设让 AI 一个词表达复杂意图。** 所有默认值对齐 MAA gui.new.json。

### 基础任务

| 预设 ID | 名称 | 中文别名 |
|---------|------|---------|
| `daily_full` | 完整日常 | 日常、完整日常 |
| `daily_simple` | 精简日常 | 精简日常、快速日常 |
| `daily_no_fight` | 日常不刷理智 | 日常不打、不刷理智、只收不打 |
| `infrast_only` | 仅基建 | 收基建、基建、收菜 |
| `fight_only` | 仅作战 | 刷理智、作战 |
| `recruit_only` | 仅公招 | 公招、自动公招 |
| `mall_only` | 仅商店 | 商店、购物、信用商店 |

### 资源刷取

| 预设 ID | 名称 | 中文别名 |
|---------|------|---------|
| `farm_lmd` | 刷龙门币 | 刷龙门币、龙门币 |
| `farm_exp` | 刷经验 | 刷经验、经验 |
| `farm_skill` | 刷技能书 | 刷技能书、技能书 |
| `annihilation` | 剿灭作战 | 剿灭、打剿灭 |

### 肉鸽（集成战略）

| 预设 ID | 名称 | 中文别名 |
|---------|------|---------|
| `roguelike` | 自动肉鸽（界园刷经验） | 肉鸽、自动肉鸽、刷肉鸽、集成战略 |
| `roguelike_invest` | **肉鸽刷投资**（投资模式+存款满停） | 刷投资、肉鸽投资、肉鸽刷投资 |
| `roguelike_boss` | **肉鸽打Boss**（到Boss停） | 打Boss、肉鸽打Boss |
| `roguelike_collect` | **肉鸽刷藏品** | 刷藏品、肉鸽刷藏品 |
| `roguelike_phantom` | 傀影肉鸽 | 傀影、傀影肉鸽、猩红孤钻 |
| `roguelike_mizuki` | 水月肉鸽 | 水月、水月肉鸽、深蓝之树 |
| `roguelike_sami` | 萨米肉鸽 | 萨米、萨米肉鸽、银凇止境 |
| `roguelike_sarkaz` | 萨卡兹肉鸽 | 萨卡兹、萨卡兹肉鸽、无终奇语 |
| `roguelike_jiegarden` | 界园肉鸽 | 界园、界园肉鸽、界庭 |

### 公招策略

| 预设 ID | 名称 | 中文别名 |
|---------|------|---------|
| `recruit_expedited` | **加急公招** | 加急公招、公招加急 |
| `recruit_high_star` | **公招保底高星** | 公招保底、保底公招 |

### 生息演算

| 预设 ID | 名称 | 中文别名 |
|---------|------|---------|
| `reclamation` | 生息演算 | 生息演算、生息 |
| `reclamation_tales` | 生息演算·扣问 | 扣问 |
| `reclamation2` | 生息演算·叙述 | 叙述 |

---

## AI 交互示例

| 用户说 | AI 只需传 |
|--------|----------|
| "帮我收一下基建" | `preset="收基建"` |
| "做日常" | `preset="日常"` |
| "日常不要刷理智" | `preset="日常不打"` |
| "刷 20 瓶药的龙门币" | `preset="刷龙门币", medicine_count=20` |
| "打生息演算" | `preset="生息演算"` |
| "公招用加急" | `preset="加急公招"` |
| "肉鸽刷投资" | `preset="肉鸽刷投资"` |
| "肉鸽用棘刺打到 boss 停" | `preset="肉鸽打Boss", roguelike_core_char="棘刺"` |
| "去商店买东西" | `preset="商店"` |
| "刷 1-7 三十次就停" | `stage="1-7", fight_times_limit=30`（自动推断 Fight） |

---

## 参数参考

### 常用参数（按需传，不传用默认值）

| 参数 | 说明 |
|------|------|
| `medicine_count` | 理智药数量，默认 0 |
| `stage` | 关卡名，默认 1-7 |
| `client_type` | Official / Bilibili |
| `post_action` | NoAction / ExitGame / ExitEmulator |
| `roguelike_core_char` | 核心干员名 |
| `roguelike_difficulty` | 难度等级 |
| `recruit_use_expedited` | 加急许可 |
| `infrast_uses_of_drones` | 无人机用途 Money/Combat/Power |

### 全量参数

所有参数名与 `MAATaskConfig` dataclass 字段一一对应，均有合理默认值。按前缀分组：

- **作战**：`fight_mode`, `stage`, `stage_1`~`stage_3`, `remain_stage`, `medicine_count`, `stone_count`, `fight_times_limit`, `fight_drop_id`, `fight_drop_count`, `fight_use_expiring_medicine`, `fight_is_dr_grandet`, `fight_series`
- **肉鸽**：`roguelike_theme`(默认JieGarden), `roguelike_mode`, `roguelike_squad`, `roguelike_squad_collectible`, `roguelike_start_count`, `roguelike_difficulty`, `roguelike_core_char`, `roguelike_roles`, `roguelike_investment`, `roguelike_invest_count`, `roguelike_use_support`, `roguelike_stop_when_deposit_full`, `roguelike_stop_at_final_boss`, `roguelike_stop_when_level_max`, `roguelike_start_with_elite_two`, `roguelike_refresh_trader_with_dice`, `roguelike_squad_is_foldartal`, `roguelike_find_playtime_target`, `roguelike_expected_collapsal_paradigms`, `roguelike_start_with_seed`, `roguelike_seed` 等
- **生息演算**：`reclamation_theme`, `reclamation_mode`, `reclamation_tool_to_craft`, `reclamation_increment_mode`, `reclamation_max_craft_count`, `reclamation_clear_store`
- **公招**：`recruit_use_expedited`, `recruit_max_times`, `recruit_refresh_level3`, `recruit_level3_choose`, `recruit_level4_choose`, `recruit_level5_choose`, `recruit_level3_time`, `recruit_level4_time`, `recruit_level5_time` 等
- **基建**：`infrast_mode`, `infrast_uses_of_drones`, `infrast_dorm_threshold`, `infrast_dorm_trust_enabled`, `infrast_originium_shard_auto_replenishment`, `infrast_dorm_filter_not_stationed`, `infrast_reception_message_board`, `infrast_continue_training`, `infrast_reception_clue_exchange`, `infrast_send_clue`, `infrast_rooms`(房间名列表自动转格式)
- **商店**：`mall_shopping`, `mall_credit_fight`, `mall_credit_fight_once_a_day`, `mall_visit_friends`, `mall_visit_friends_once_a_day`, `mall_first_list`(分号分隔), `mall_black_list`(分号分隔), `mall_shopping_ignore_black_list_when_full`, `mall_only_buy_discount`, `mall_reserve_max_credit`
- **奖励**：`award_mail`, `award_free_gacha`, `award_orundum`, `award_mining`, `award_special_access`

---

## 架构

### 目录结构

```
项目根目录/
  agent.py                     # MAAAgent — 5 个 MCP 工具入口
  agent-manifest.json           # MCP 插件清单（分层精简版）
  .agent_maa_config.json        # 持久化配置（运行时生成）

  core/
    config.py                   # MAAConfig — JSON 配置读写
    task_presets.py              # 25 个预设 + 40 个中文别名

  enhanced/
    executor.py                 # MAATaskConfig（from_params + infer_tasks）+ EnhancedMAAExecutor
    emulator_manager.py         # MuMu / LDPlayer 启停控制
    adb_discovery.py            # ADB 自动发现
    notification.py             # HTTP 通知推送
    scheduler.py                # 无头定时调度
    script_profiles.py          # 多脚本/多账号管理
    process_manager.py          # 异步进程管理
    log_monitor.py              # 实时日志监控
```

### 新增字段只需改一处

```
之前（3 处联动）：
  MAATaskConfig 加字段 → agent.py 加 params.get() → _build_task_queue 写入 JSON

现在（2 处）：
  MAATaskConfig 加字段 → _build_task_queue 写入 JSON
  （agent.py 通过 from_params() 自省，零改动）
```

---

## 配置 & 定时调度

首次使用配置 MAA 路径（其余自动发现）：

```json
{"tool_name": "configure_maa", "maa_path": "D:\\MaaAssistantArknights"}
```

定时调度示例——每天 6:30 做日常：

```json
{
  "tool_name": "configure_maa",
  "script_profiles": {"main": {"name": "主账号", "preset": "daily_full"}},
  "schedules": {"morning": {"enabled": true, "script_profile": "main", "time": "06:30",
    "days": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]}}
}
```

---

## 依赖

| 包 | 用途 | 缺失时 |
|----|------|--------|
| `psutil` | 进程扫描、ADB 发现 | 需手动配置地址 |
| `httpx` | 异步通知推送 | 静默禁用 |
| `aiofiles` | 异步日志读取 | 必须安装 |
