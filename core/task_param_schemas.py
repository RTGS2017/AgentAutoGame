"""MAA 任务参数 Schema 定义

为每个 TaskQueue 任务类型定义参数 schema，供 get_task_catalog 工具组装返回。
格式: {param_name: {"type": str, "default": Any, "label": str}}

所有 default 值严格对齐 MAATaskConfig dataclass（executor.py），
确保 schema 与实际执行行为一致。
"""

from typing import Any, Dict

# 9 个核心任务类型的参数 schema
TASK_PARAM_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "StartUp": {
        "name": "开始唤醒",
        "params": {
            "client_type": {
                "type": "enum",
                "options": ["Official", "Bilibili"],
                "default": "Official",
                "label": "客户端类型",
            },
            "account_name": {
                "type": "string",
                "default": "",
                "label": "切换账号名",
            },
        },
    },
    "Fight": {
        "name": "刷理智",
        "params": {
            "fight_mode": {
                "type": "enum",
                "options": ["Routine", "Annihilation"],
                "default": "Routine",
                "label": "作战模式",
            },
            "stage": {
                "type": "string",
                "default": "1-7",
                "label": "关卡名",
            },
            "stage_1": {
                "type": "string",
                "default": "",
                "label": "备选关卡1",
            },
            "stage_2": {
                "type": "string",
                "default": "",
                "label": "备选关卡2",
            },
            "stage_3": {
                "type": "string",
                "default": "",
                "label": "备选关卡3",
            },
            "remain_stage": {
                "type": "string",
                "default": "",
                "label": "剩余理智关卡",
            },
            "medicine_count": {
                "type": "int",
                "default": 0,
                "label": "理智药数量",
            },
            "stone_count": {
                "type": "int",
                "default": 0,
                "label": "源石数量",
            },
            "fight_times_limit": {
                "type": "int",
                "default": 0,
                "label": "次数限制(0=不限)",
            },
            "fight_drop_id": {
                "type": "string",
                "default": "",
                "label": "目标掉落物ID",
            },
            "fight_drop_count": {
                "type": "int",
                "default": 0,
                "label": "目标掉落数量",
            },
            "fight_series": {
                "type": "int",
                "default": 0,
                "label": "连续作战批次",
            },
            "fight_is_dr_grandet": {
                "type": "bool",
                "default": False,
                "label": "博朗台模式",
            },
            "fight_use_expiring_medicine": {
                "type": "bool",
                "default": False,
                "label": "优先过期药",
            },
            "annihilation_stage": {
                "type": "string",
                "default": "Annihilation",
                "label": "剿灭关卡(剿灭模式专用)",
            },
        },
    },
    "Recruit": {
        "name": "自动公招",
        "params": {
            "recruit_use_expedited": {
                "type": "bool",
                "default": False,
                "label": "加急许可",
            },
            "recruit_max_times": {
                "type": "int",
                "default": 4,
                "label": "最大次数",
            },
            "recruit_refresh_level3": {
                "type": "bool",
                "default": True,
                "label": "刷新3星tag",
            },
            "recruit_force_refresh": {
                "type": "bool",
                "default": True,
                "label": "强制刷新",
            },
            "recruit_level1_not_choose": {
                "type": "bool",
                "default": True,
                "label": "不选1星",
            },
            "recruit_level3_choose": {
                "type": "bool",
                "default": True,
                "label": "选3星",
            },
            "recruit_level4_choose": {
                "type": "bool",
                "default": True,
                "label": "选4星",
            },
            "recruit_level5_choose": {
                "type": "bool",
                "default": False,
                "label": "选5/6星",
            },
            "recruit_level3_time": {
                "type": "int",
                "default": 540,
                "label": "3星公招时长(秒)",
            },
            "recruit_level4_time": {
                "type": "int",
                "default": 540,
                "label": "4星公招时长(秒)",
            },
            "recruit_level5_time": {
                "type": "int",
                "default": 540,
                "label": "5/6星公招时长(秒)",
            },
        },
    },
    "Infrast": {
        "name": "基建换班",
        "params": {
            "infrast_mode": {
                "type": "enum",
                "options": ["Normal", "Custom"],
                "default": "Normal",
                "label": "模式",
            },
            "infrast_uses_of_drones": {
                "type": "enum",
                "options": ["Money", "Combat", "Power"],
                "default": "Money",
                "label": "无人机用途",
            },
            "infrast_dorm_threshold": {
                "type": "int",
                "default": 30,
                "label": "宿舍心情阈值(0-100)",
            },
            "infrast_dorm_trust_enabled": {
                "type": "bool",
                "default": True,
                "label": "信赖提升",
            },
            "infrast_originium_shard_auto_replenishment": {
                "type": "bool",
                "default": True,
                "label": "源石碎片自动补货",
            },
            "infrast_continue_training": {
                "type": "bool",
                "default": False,
                "label": "继续训练",
            },
            "infrast_reception_clue_exchange": {
                "type": "bool",
                "default": True,
                "label": "线索交流",
            },
            "infrast_send_clue": {
                "type": "bool",
                "default": True,
                "label": "送线索",
            },
            "infrast_rooms": {
                "type": "string",
                "default": "",
                "label": "指定房间(逗号分隔,如Mfg,Trade)",
            },
            "custom_infrast_path": {
                "type": "string",
                "default": "",
                "label": "自定义排班文件路径",
            },
            "custom_infrast_plan_index": {
                "type": "int",
                "default": -1,
                "label": "排班计划序号(-1=自动)",
            },
        },
    },
    "Mall": {
        "name": "信用商店",
        "params": {
            "mall_shopping": {
                "type": "bool",
                "default": True,
                "label": "购物",
            },
            "mall_credit_fight": {
                "type": "bool",
                "default": False,
                "label": "信用作战",
            },
            "mall_credit_fight_once_a_day": {
                "type": "bool",
                "default": True,
                "label": "信用作战每日一次",
            },
            "mall_visit_friends": {
                "type": "bool",
                "default": True,
                "label": "访问好友",
            },
            "mall_visit_friends_once_a_day": {
                "type": "bool",
                "default": False,
                "label": "访问好友每日一次",
            },
            "mall_first_list": {
                "type": "string",
                "default": "招聘许可",
                "label": "优先购买(分号分隔)",
            },
            "mall_black_list": {
                "type": "string",
                "default": "碳;家具;加急许可",
                "label": "黑名单(分号分隔)",
            },
            "mall_shopping_ignore_black_list_when_full": {
                "type": "bool",
                "default": False,
                "label": "信用满时忽略黑名单",
            },
            "mall_only_buy_discount": {
                "type": "bool",
                "default": False,
                "label": "只买折扣",
            },
            "mall_reserve_max_credit": {
                "type": "bool",
                "default": False,
                "label": "保留最大信用",
            },
        },
    },
    "Award": {
        "name": "领取奖励",
        "params": {
            "award_mail": {
                "type": "bool",
                "default": False,
                "label": "领邮件",
            },
            "award_free_gacha": {
                "type": "bool",
                "default": False,
                "label": "免费单抽",
            },
            "award_orundum": {
                "type": "bool",
                "default": False,
                "label": "合成玉",
            },
            "award_mining": {
                "type": "bool",
                "default": False,
                "label": "限时开采",
            },
            "award_special_access": {
                "type": "bool",
                "default": False,
                "label": "限定通行证",
            },
        },
    },
    "Roguelike": {
        "name": "集成战略(肉鸽)",
        "params": {
            "roguelike_theme": {
                "type": "enum",
                "options": ["Phantom", "Mizuki", "Sami", "Sarkaz", "JieGarden"],
                "default": "JieGarden",
                "label": "主题",
            },
            "roguelike_mode": {
                "type": "enum",
                "options": ["Exp", "Collectible", "Investment"],
                "default": "Exp",
                "label": "模式",
            },
            "roguelike_difficulty": {
                "type": "int",
                "default": 2147483647,
                "label": "难度(2147483647=自动最高)",
            },
            "roguelike_squad": {
                "type": "string",
                "default": "指挥分队",
                "label": "分队",
            },
            "roguelike_squad_collectible": {
                "type": "string",
                "default": "指挥分队",
                "label": "藏品模式分队",
            },
            "roguelike_roles": {
                "type": "string",
                "default": "稳扎稳打",
                "label": "职业偏好",
            },
            "roguelike_core_char": {
                "type": "string",
                "default": "",
                "label": "核心干员",
            },
            "roguelike_start_count": {
                "type": "int",
                "default": 999999,
                "label": "开始次数",
            },
            "roguelike_investment": {
                "type": "bool",
                "default": True,
                "label": "投资",
            },
            "roguelike_invest_count": {
                "type": "int",
                "default": 999,
                "label": "投资次数",
            },
            "roguelike_invest_with_more_score": {
                "type": "bool",
                "default": False,
                "label": "更多分数投资",
            },
            "roguelike_collectible_shopping": {
                "type": "bool",
                "default": False,
                "label": "藏品模式购物",
            },
            "roguelike_collectible_start_awards": {
                "type": "string",
                "default": "HotWater",
                "label": "藏品模式初始奖励",
            },
            "roguelike_use_support": {
                "type": "bool",
                "default": False,
                "label": "助战",
            },
            "roguelike_use_support_non_friend": {
                "type": "bool",
                "default": False,
                "label": "非好友助战",
            },
            "roguelike_refresh_trader_with_dice": {
                "type": "bool",
                "default": False,
                "label": "骰子刷新商店",
            },
            "roguelike_find_playtime_target": {
                "type": "string",
                "default": "Ling",
                "label": "寻访目标(游历模式)",
            },
            "roguelike_start_with_elite_two": {
                "type": "bool",
                "default": False,
                "label": "精二开局",
            },
            "roguelike_start_with_elite_two_only": {
                "type": "bool",
                "default": False,
                "label": "仅精二开局",
            },
            "roguelike_stop_when_deposit_full": {
                "type": "bool",
                "default": False,
                "label": "存款满停",
            },
            "roguelike_stop_at_final_boss": {
                "type": "bool",
                "default": False,
                "label": "到Boss停",
            },
            "roguelike_stop_when_level_max": {
                "type": "bool",
                "default": False,
                "label": "等级满停",
            },
            "roguelike_start_with_seed": {
                "type": "bool",
                "default": False,
                "label": "指定种子",
            },
            "roguelike_seed": {
                "type": "string",
                "default": "",
                "label": "种子值",
            },
        },
    },
    "Reclamation": {
        "name": "生息演算",
        "params": {
            "reclamation_theme": {
                "type": "enum",
                "options": ["Tales", "Reclamation2"],
                "default": "Tales",
                "label": "主题",
            },
            "reclamation_mode": {
                "type": "string",
                "default": "Archive",
                "label": "模式",
            },
            "reclamation_tool_to_craft": {
                "type": "string",
                "default": "",
                "label": "制作道具",
            },
            "reclamation_increment_mode": {
                "type": "int",
                "default": 0,
                "label": "增量模式",
            },
            "reclamation_max_craft_count": {
                "type": "int",
                "default": 16,
                "label": "最大制作数",
            },
            "reclamation_clear_store": {
                "type": "bool",
                "default": True,
                "label": "清空商店",
            },
        },
    },
    "CloseDown": {
        "name": "关闭游戏",
        "params": {},
    },
}


def get_task_catalog(last_params: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    组装任务目录，合并 schema 默认值与 last_used 值。

    Args:
        last_params: 从 config.get_all_last_params() 获取的上次参数

    Returns:
        带 last_used 标注的完整任务目录
    """
    catalog = {}
    for task_type, schema in TASK_PARAM_SCHEMAS.items():
        task_last = last_params.get(task_type, {})
        params_with_last = {}
        for param_name, param_def in schema["params"].items():
            entry = dict(param_def)  # copy
            if param_name in task_last:
                entry["last_used"] = task_last[param_name]
            params_with_last[param_name] = entry
        catalog[task_type] = {
            "name": schema["name"],
            "params": params_with_last,
        }
    return catalog
