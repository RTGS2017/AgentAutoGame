"""MAA 任务预设 - 常用任务的快捷配置模板"""

from typing import Dict, Any, Optional

# 任务预设模板
TASK_PRESETS = {
    # 基础任务
    "daily_full": {
        "name": "完整日常",
        "description": "执行所有日常任务（基建、作战、公招、商店、奖励）",
        "tasks": {
            "StartUp": True,
            "Fight": True,
            "Infrast": True,
            "Recruit": True,
            "Mall": True,
            "Award": True,
        },
        "fight_mode": "Routine",
        "medicine_count": 0,
        "stage": "1-7",
    },
    "daily_simple": {
        "name": "精简日常",
        "description": "只执行核心日常任务（基建、作战、奖励）",
        "tasks": {
            "StartUp": True,
            "Fight": True,
            "Infrast": True,
            "Award": True,
        },
        "fight_mode": "Routine",
        "medicine_count": 0,
        "stage": "1-7",
    },
    "infrast_only": {
        "name": "仅基建",
        "description": "只收基建和换班，不刷理智",
        "tasks": {
            "StartUp": True,
            "Infrast": True,
        },
    },
    "fight_only": {
        "name": "仅作战",
        "description": "只刷理智，不管其他任务",
        "tasks": {
            "StartUp": True,
            "Fight": True,
        },
        "fight_mode": "Routine",
        "medicine_count": 0,
        "stage": "1-7",
    },

    # 资源刷取
    "farm_lmd": {
        "name": "刷龙门币",
        "description": "刷CE-6龙门币关卡",
        "tasks": {
            "StartUp": True,
            "Fight": True,
        },
        "fight_mode": "Routine",
        "medicine_count": 10,
        "stage": "CE-6",
        "stage_1": "CE-5",
        "remain_stage": "1-7",
    },
    "farm_exp": {
        "name": "刷经验",
        "description": "刷LS-6经验关卡",
        "tasks": {
            "StartUp": True,
            "Fight": True,
        },
        "fight_mode": "Routine",
        "medicine_count": 10,
        "stage": "LS-6",
        "stage_1": "LS-5",
        "remain_stage": "1-7",
    },
    "farm_skill": {
        "name": "刷技能书",
        "description": "刷CA-5技能书关卡",
        "tasks": {
            "StartUp": True,
            "Fight": True,
        },
        "fight_mode": "Routine",
        "medicine_count": 10,
        "stage": "CA-5",
        "stage_1": "CA-4",
        "remain_stage": "1-7",
    },

    # 特殊任务
    "annihilation": {
        "name": "剿灭作战",
        "description": "每周剿灭，获取合成玉",
        "tasks": {
            "StartUp": True,
            "Fight": True,
        },
        "fight_mode": "Annihilation",
        "medicine_count": 0,
        "annihilation_stage": "Annihilation",
    },

    # 肉鸽（默认界园——与 MAA gui.new.json 一致）
    "roguelike": {
        "name": "自动肉鸽",
        "description": "自动刷肉鸽（集成战略），默认界园主题刷经验模式",
        "tasks": {
            "StartUp": True,
            "Roguelike": True,
        },
        "roguelike_theme": "JieGarden",
        "roguelike_mode": "Exp",
    },
    "roguelike_phantom": {
        "name": "傀影肉鸽",
        "description": "傀影与猩红孤钻，刷经验模式",
        "tasks": {
            "StartUp": True,
            "Roguelike": True,
        },
        "roguelike_theme": "Phantom",
        "roguelike_mode": "Exp",
    },
    "roguelike_mizuki": {
        "name": "水月肉鸽",
        "description": "水月与深蓝之树，刷经验模式",
        "tasks": {
            "StartUp": True,
            "Roguelike": True,
        },
        "roguelike_theme": "Mizuki",
        "roguelike_mode": "Exp",
    },
    "roguelike_sami": {
        "name": "萨米肉鸽",
        "description": "探索者的银凇止境，刷经验模式",
        "tasks": {
            "StartUp": True,
            "Roguelike": True,
        },
        "roguelike_theme": "Sami",
        "roguelike_mode": "Exp",
    },
    "roguelike_sarkaz": {
        "name": "萨卡兹肉鸽",
        "description": "萨卡兹的无终奇语，刷经验模式",
        "tasks": {
            "StartUp": True,
            "Roguelike": True,
        },
        "roguelike_theme": "Sarkaz",
        "roguelike_mode": "Exp",
    },
    "roguelike_jiegarden": {
        "name": "界园肉鸽",
        "description": "界庭之园，刷经验模式",
        "tasks": {
            "StartUp": True,
            "Roguelike": True,
        },
        "roguelike_theme": "JieGarden",
        "roguelike_mode": "Exp",
    },

    # 生息演算
    "reclamation": {
        "name": "生息演算",
        "description": "自动生息演算，默认Tales主题归档模式",
        "tasks": {"StartUp": True, "Reclamation": True},
        "reclamation_theme": "Tales",
        "reclamation_mode": "Archive",
    },
    "reclamation_tales": {
        "name": "生息演算·扣问",
        "description": "生息演算Tales主题，归档模式",
        "tasks": {"StartUp": True, "Reclamation": True},
        "reclamation_theme": "Tales",
        "reclamation_mode": "Archive",
    },
    "reclamation2": {
        "name": "生息演算·叙述",
        "description": "生息演算Reclamation2主题",
        "tasks": {"StartUp": True, "Reclamation": True},
        "reclamation_theme": "Reclamation2",
        "reclamation_mode": "Archive",
    },

    # 独立任务
    "recruit_only": {
        "name": "仅公招",
        "description": "只进行自动公招",
        "tasks": {"StartUp": True, "Recruit": True},
    },
    "mall_only": {
        "name": "仅商店",
        "description": "只进行信用商店和访友",
        "tasks": {"StartUp": True, "Mall": True},
    },

    # ========== 策略型预设（高频组合，一个词代替一组参数）==========

    # 日常变体
    "daily_no_fight": {
        "name": "日常不刷理智",
        "description": "基建+公招+商店+奖励，不消耗理智",
        "tasks": {
            "StartUp": True, "Infrast": True,
            "Recruit": True, "Mall": True, "Award": True,
        },
    },

    # 肉鸽策略
    "roguelike_invest": {
        "name": "肉鸽刷投资",
        "description": "专注投资模式，存款满自动停止",
        "tasks": {"StartUp": True, "Roguelike": True},
        "roguelike_theme": "JieGarden",
        "roguelike_mode": "Investment",
        "roguelike_investment": True,
        "roguelike_invest_count": 999,
        "roguelike_stop_when_deposit_full": True,
    },
    "roguelike_boss": {
        "name": "肉鸽打Boss",
        "description": "刷经验模式，到最终Boss自动停止",
        "tasks": {"StartUp": True, "Roguelike": True},
        "roguelike_theme": "JieGarden",
        "roguelike_mode": "Exp",
        "roguelike_stop_at_final_boss": True,
    },
    "roguelike_collect": {
        "name": "肉鸽刷藏品",
        "description": "藏品收集模式",
        "tasks": {"StartUp": True, "Roguelike": True},
        "roguelike_theme": "JieGarden",
        "roguelike_mode": "Collectible",
        "roguelike_collectible_shopping": True,
    },

    # 公招策略
    "recruit_expedited": {
        "name": "加急公招",
        "description": "使用加急许可快速公招",
        "tasks": {"StartUp": True, "Recruit": True},
        "recruit_use_expedited": True,
        "recruit_max_times": 4,
    },
    "recruit_high_star": {
        "name": "公招保底高星",
        "description": "自动公招，遇到5/6星tag自动选择",
        "tasks": {"StartUp": True, "Recruit": True},
        "recruit_level5_choose": True,
        "recruit_level4_choose": True,
    },

    # ========== 任务别名（中文语义识别）==========

    # 任务别名（中文语义识别）
    "收基建": "infrast_only",
    "基建": "infrast_only",
    "收菜": "infrast_only",
    "日常": "daily_full",
    "完整日常": "daily_full",
    "精简日常": "daily_simple",
    "快速日常": "daily_simple",
    "刷理智": "fight_only",
    "作战": "fight_only",
    "刷龙门币": "farm_lmd",
    "龙门币": "farm_lmd",
    "刷经验": "farm_exp",
    "经验": "farm_exp",
    "刷技能书": "farm_skill",
    "技能书": "farm_skill",
    "剿灭": "annihilation",
    "打剿灭": "annihilation",
    "肉鸽": "roguelike",
    "自动肉鸽": "roguelike",
    "刷肉鸽": "roguelike",
    "集成战略": "roguelike",
    "傀影": "roguelike_phantom",
    "傀影肉鸽": "roguelike_phantom",
    "猩红孤钻": "roguelike_phantom",
    "水月": "roguelike_mizuki",
    "水月肉鸽": "roguelike_mizuki",
    "深蓝之树": "roguelike_mizuki",
    "萨米": "roguelike_sami",
    "萨米肉鸽": "roguelike_sami",
    "银凇止境": "roguelike_sami",
    "萨卡兹": "roguelike_sarkaz",
    "萨卡兹肉鸽": "roguelike_sarkaz",
    "无终奇语": "roguelike_sarkaz",
    "界园": "roguelike_jiegarden",
    "界园肉鸽": "roguelike_jiegarden",
    "界庭": "roguelike_jiegarden",
    "生息演算": "reclamation",
    "生息": "reclamation",
    "扣问": "reclamation_tales",
    "叙述": "reclamation2",
    "公招": "recruit_only",
    "自动公招": "recruit_only",
    "商店": "mall_only",
    "购物": "mall_only",
    "信用商店": "mall_only",
    "日常不打": "daily_no_fight",
    "不刷理智": "daily_no_fight",
    "只收不打": "daily_no_fight",
    "刷投资": "roguelike_invest",
    "肉鸽投资": "roguelike_invest",
    "肉鸽刷投资": "roguelike_invest",
    "打Boss": "roguelike_boss",
    "肉鸽打Boss": "roguelike_boss",
    "刷藏品": "roguelike_collect",
    "肉鸽刷藏品": "roguelike_collect",
    "加急公招": "recruit_expedited",
    "公招加急": "recruit_expedited",
    "公招保底": "recruit_high_star",
    "保底公招": "recruit_high_star",
}


def get_preset(preset_name: str) -> Optional[Dict[str, Any]]:
    """
    获取预设任务配置

    :param preset_name: 预设名称或别名（如 "daily_full", "收基建"）
    :return: 任务配置字典，如果预设不存在则返回 None
    """
    # 如果是别名，解析为真实预设名
    if preset_name in TASK_PRESETS:
        value = TASK_PRESETS[preset_name]
        if isinstance(value, str):
            # 这是别名，递归获取
            return get_preset(value)
        # 这是真实预设，返回副本
        return value.copy()
    return None


def list_presets() -> Dict[str, Dict[str, str]]:
    """
    列出所有可用的预设任务

    :return: 预设列表，格式为 {preset_id: {name, description}}
    """
    presets = {}
    for key, value in TASK_PRESETS.items():
        # 只包含真实预设，不包含别名
        if isinstance(value, dict) and "name" in value:
            presets[key] = {
                "name": value["name"],
                "description": value["description"],
            }
    return presets


def merge_preset_with_params(
    preset: Dict[str, Any],
    custom_params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    将预设配置与自定义参数合并

    :param preset: 预设配置
    :param custom_params: 自定义参数（会覆盖预设）
    :return: 合并后的配置
    """
    config = preset.copy()

    # 合并 tasks 字典
    if "tasks" in custom_params:
        if "tasks" not in config:
            config["tasks"] = {}
        config["tasks"].update(custom_params["tasks"])
        del custom_params["tasks"]

    # 合并其他参数
    config.update(custom_params)

    return config


def get_preset_suggestions(input_text: str) -> list[str]:
    """
    根据输入文本提供预设建议

    :param input_text: 用户输入的文本
    :return: 建议的预设名称列表
    """
    text_lower = input_text.lower()
    suggestions = []

    # 检查所有别名
    for alias in TASK_PRESETS.keys():
        if isinstance(TASK_PRESETS[alias], str):  # 这是别名
            if alias in text_lower or text_lower in alias:
                # 找到真实预设名
                real_preset = TASK_PRESETS[alias]
                if real_preset not in suggestions:
                    suggestions.append(real_preset)

    return suggestions
