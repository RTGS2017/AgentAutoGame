"""增强的 MAA 执行器 - 整合进程管理、日志监控、模拟器管理

移除了对 maa_comms 模块的依赖，所有常量内联。
集成了通知推送和 ADB 自动发现。
"""

import json
import shutil
import asyncio
import logging
import dataclasses
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field

from .process_manager import EnhancedProcessManager
from .log_monitor import EnhancedLogMonitor
from .emulator_manager import EmulatorManager, EmulatorInfo, DeviceStatus
from .notification import TaskNotifier

logger = logging.getLogger(__name__)

# ---- 内联 MAA 常量（原 maa_comms.script_config.constants）----

MAA_TASKS = [
    "StartUp", "CloseDown", "Fight", "Recruit", "Infrast",
    "Mall", "Award", "Roguelike", "Reclamation",
]

MAA_TASKS_ZH = [
    "开始唤醒", "关闭游戏", "刷理智", "自动公招", "基建换班",
    "领取信用及购物", "领取日常奖励", "自动肉鸽", "生息演算",
]

MAA_ANNIHILATION_FIGHT_BASE = {
    "IsStageManually": True,
    "StagePlan": [],
    "UseMedicine": False,
    "MedicineCount": 0,
    "UseStone": False,
    "StoneCount": 0,
}

MAA_REMAIN_FIGHT_BASE = {
    "$type": "FightTask",
    "Name": "剩余理智-刷关",
    "IsEnable": True,
    "TaskType": "Fight",
    "IsStageManually": True,
    "StagePlan": [],
    "UseMedicine": False,
    "MedicineCount": 0,
    "UseStone": False,
    "StoneCount": 0,
}


# ---- 数据类 ----

@dataclass
class MAATaskConfig:
    """MAA 任务配置"""
    # 基本配置
    maa_path: Path
    tasks: Dict[str, bool]  # {"StartUp": True, "Fight": True, ...}

    # 作战配置
    fight_mode: str = "Routine"  # "Routine" or "Annihilation"
    medicine_count: int = 0
    stone_count: int = 0
    stage: str = "1-7"
    stage_1: str = ""
    stage_2: str = ""
    stage_3: str = ""
    remain_stage: str = ""

    # 客户端配置
    client_type: str = "Official"  # "Official", "Bilibili"
    account_name: str = ""

    # 剿灭配置
    annihilation_stage: str = "Annihilation"

    # 基建配置
    infrast_mode: str = "Normal"  # "Normal" or "Custom"
    custom_infrast_path: Optional[str] = None
    custom_infrast_plan_index: int = -1

    # ===== 肉鸽（对齐 MAA gui.new.json RoguelikeTask）=====
    roguelike_theme: str = "JieGarden"               # Phantom/Mizuki/Sami/Sarkaz/JieGarden
    roguelike_mode: str = "Exp"                      # Exp/Collectible/Investment
    roguelike_squad: str = "指挥分队"
    roguelike_squad_collectible: str = "指挥分队"
    roguelike_roles: str = "稳扎稳打"
    roguelike_start_count: int = 999999
    roguelike_difficulty: int = 2147483647            # 最大值=自动最高
    roguelike_core_char: str = ""
    roguelike_investment: bool = True
    roguelike_invest_count: int = 999
    roguelike_invest_with_more_score: bool = False
    roguelike_collectible_start_awards: str = "HotWater"
    roguelike_collectible_shopping: bool = False
    roguelike_start_with_elite_two: bool = False
    roguelike_start_with_elite_two_only: bool = False
    roguelike_expected_collapsal_paradigms: str = ""  # 注意拼写: Collapsal
    roguelike_monthly_squad_auto_iterate: bool = True
    roguelike_monthly_squad_check_comms: bool = True
    roguelike_deep_exploration_auto_iterate: bool = True
    roguelike_find_playtime_target: str = "Ling"
    roguelike_use_support: bool = False
    roguelike_use_support_non_friend: bool = False
    roguelike_refresh_trader_with_dice: bool = False
    roguelike_squad_is_foldartal: bool = False
    roguelike_sami_first_floor_foldartal: bool = False
    roguelike_sami_first_floor_foldartals: str = ""
    roguelike_sami_new_squad2_starting_foldartal: bool = False
    roguelike_sami_new_squad2_starting_foldartals: str = ""
    roguelike_stop_when_deposit_full: bool = False
    roguelike_stop_at_final_boss: bool = False
    roguelike_stop_when_level_max: bool = False
    roguelike_start_with_seed: bool = False
    roguelike_seed: str = ""

    # ===== 生息演算（对齐 MAA ReclamationTask）=====
    reclamation_theme: str = "Tales"                 # Tales/Reclamation2
    reclamation_mode: str = "Archive"
    reclamation_tool_to_craft: str = ""
    reclamation_increment_mode: int = 0
    reclamation_max_craft_count: int = 16
    reclamation_clear_store: bool = True

    # ===== 公招（对齐 MAA RecruitTask）=====
    recruit_use_expedited: bool = False
    recruit_max_times: int = 4
    recruit_refresh_level3: bool = True
    recruit_force_refresh: bool = True
    recruit_level1_not_choose: bool = True
    recruit_level3_choose: bool = True
    recruit_level4_choose: bool = True
    recruit_level5_choose: bool = False
    recruit_level3_time: int = 540                   # 3星公招时长(秒)
    recruit_level4_time: int = 540
    recruit_level5_time: int = 540

    # ===== 基建（对齐 MAA InfrastTask）=====
    infrast_uses_of_drones: str = "Money"
    infrast_dorm_threshold: int = 30
    infrast_dorm_trust_enabled: bool = True
    infrast_originium_shard_auto_replenishment: bool = True
    infrast_dorm_filter_not_stationed: bool = True
    infrast_reception_message_board: bool = True
    infrast_reception_clue_exchange: bool = True
    infrast_send_clue: bool = True
    infrast_continue_training: bool = False
    infrast_rooms: Optional[List[Any]] = None        # None=保留模板。可传房间名列表如["Mfg","Trade"]自动转格式

    # ===== 商店（对齐 MAA MallTask）=====
    mall_shopping: bool = True
    mall_credit_fight: bool = False
    mall_credit_fight_once_a_day: bool = True
    mall_visit_friends: bool = True
    mall_visit_friends_once_a_day: bool = False
    mall_first_list: str = "招聘许可"
    mall_black_list: str = "碳;家具;加急许可"
    mall_shopping_ignore_black_list_when_full: bool = False
    mall_only_buy_discount: bool = False
    mall_reserve_max_credit: bool = False

    # ===== 奖励（对齐 MAA AwardTask）=====
    award_mail: bool = False
    award_free_gacha: bool = False
    award_orundum: bool = False
    award_mining: bool = False
    award_special_access: bool = False

    # ===== 作战扩展（对齐 MAA FightTask）=====
    fight_times_limit: int = 0
    fight_drop_id: str = ""
    fight_drop_count: int = 0
    fight_is_dr_grandet: bool = False                # 博朗台模式
    fight_use_expiring_medicine: bool = False
    fight_series: int = 0

    # 任务后动作
    post_action: str = "NoAction"  # "NoAction", "ExitGame", "ExitEmulator"

    # 模拟器配置
    emulator_id: Optional[str] = None
    emulator_index: Optional[str] = None
    connect_address: Optional[str] = None

    # 运行配置
    max_restart: int = 3
    restart_delay: float = 2.0
    timeout_minutes: float = 60.0

    # 备份配置
    backup_before_run: bool = True
    restore_after_run: bool = True

    # 作战相关参数名（无统一前缀，需显式列举）
    _FIGHT_PARAM_NAMES = frozenset({
        "fight_mode", "stage", "stage_1", "stage_2", "stage_3",
        "remain_stage", "medicine_count", "stone_count",
        "annihilation_stage", "fight_times_limit", "fight_drop_id",
        "fight_drop_count", "fight_use_expiring_medicine", "fight_series",
        "fight_is_dr_grandet",
    })

    @classmethod
    def from_params(
        cls,
        maa_path: "Path",
        tasks: Dict[str, bool],
        params: Dict[str, Any],
        *,
        emulator_id: Optional[str] = None,
        emulator_index: Optional[str] = None,
        connect_address: Optional[str] = None,
    ) -> "MAATaskConfig":
        """
        从合并后的参数字典批量构造 MAATaskConfig。

        利用 dataclass 字段自省，自动将 params 中匹配的 key 传入构造器。
        新增字段只需改 dataclass 定义，此处无需任何改动。
        """
        kwargs: Dict[str, Any] = {
            "maa_path": maa_path,
            "tasks": tasks,
            "emulator_id": emulator_id,
            "emulator_index": emulator_index,
            "connect_address": connect_address,
        }
        for f in dataclasses.fields(cls):
            if not f.init:
                continue  # 跳过 init=False 字段
            if f.name in kwargs:
                continue  # 已通过显式参数提供
            if f.name in params:
                kwargs[f.name] = params[f.name]
        return cls(**kwargs)

    @classmethod
    def infer_tasks(cls, params: Dict[str, Any]) -> Dict[str, bool]:
        """
        从参数 key 的前缀自动推断需要启用的任务类型。

        规则：
        - roguelike_*  → Roguelike
        - reclamation_ → Reclamation
        - recruit_*    → Recruit
        - infrast_* / custom_infrast_* → Infrast
        - mall_*       → Mall
        - award_*      → Award
        - stage / medicine_count / fight_* 等 → Fight
        - 始终包含 StartUp
        """
        prefix_map = {
            "roguelike_": "Roguelike",
            "reclamation_": "Reclamation",
            "recruit_": "Recruit",
            "infrast_": "Infrast",
            "custom_infrast_": "Infrast",
            "mall_": "Mall",
            "award_": "Award",
        }
        tasks: Dict[str, bool] = {"StartUp": True}
        for key in params:
            if key in cls._FIGHT_PARAM_NAMES:
                tasks["Fight"] = True
                continue
            for prefix, task_type in prefix_map.items():
                if key.startswith(prefix):
                    tasks[task_type] = True
                    break
        return tasks


@dataclass
class MAAExecutionResult:
    """MAA 执行结果"""
    status: str  # "success", "failed", "timeout", "error"
    message: str
    start_time: datetime
    end_time: datetime
    duration: float
    logs: List[str] = field(default_factory=list)
    tasks_completed: List[str] = field(default_factory=list)
    tasks_failed: List[str] = field(default_factory=list)
    restart_count: int = 0


class EnhancedMAAExecutor:
    """
    增强的 MAA 执行器

    特性:
    1. 自动启动模拟器
    2. 实时日志监控和状态判断
    3. 异常自动重启
    4. 配置自动备份还原
    5. B服协议自动处理
    6. 通知推送
    """

    def __init__(
        self,
        config: MAATaskConfig,
        emulator_manager: Optional[EmulatorManager] = None,
        notifier: Optional[TaskNotifier] = None,
        progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ):
        self.config = config
        self.emulator_manager = emulator_manager
        self.notifier = notifier
        self.progress_callback = progress_callback

        # 组件
        self.process_manager = EnhancedProcessManager()
        self.log_monitor: Optional[EnhancedLogMonitor] = None

        # 路径
        self.maa_root = config.maa_path
        self.maa_exe = self.maa_root / "MAA.exe"
        self.maa_config_dir = self.maa_root / "config"
        self.maa_log_path = self.maa_root / "debug" / "gui.log"
        self.maa_tasks_json = self.maa_root / "resource" / "tasks" / "tasks.json"

        # 状态
        self.backup_dir: Optional[Path] = None
        self.task_dict: Dict[str, bool] = {}
        self.wait_event = asyncio.Event()
        self.current_status = "未运行"
        self._last_forwarded_line_count = 0  # 已转发到前端的日志行数

    async def execute(self) -> MAAExecutionResult:
        """执行 MAA 任务"""
        start_time = datetime.now()
        restart_count = 0

        try:
            # 1. 备份配置
            if self.config.backup_before_run:
                await self._backup_config()

            # 2. 启动模拟器
            emulator_info: Optional[EmulatorInfo] = None
            if (self.emulator_manager and self.config.emulator_id
                    and self.config.emulator_index):
                emulator_info = await self._start_emulator()

            # 3. 执行（带重试）
            final_status = "failed"
            final_message = "未知错误"

            for attempt in range(self.config.max_restart + 1):
                if attempt > 0:
                    restart_count += 1
                    self._notify(f"正在重启 ({attempt}/{self.config.max_restart})...")
                    await self._report_progress("重启", {
                        "attempt": attempt, "max": self.config.max_restart,
                    })
                    # 彻底清理: 先杀所有 MAA 进程，再清理管理器状态
                    self._kill_all_maa_processes()
                    await self.process_manager.clear()
                    await asyncio.sleep(max(self.config.restart_delay, 3.0))

                # 配置 MAA
                await self._configure_maa(emulator_info)

                # 启动 MAA
                status, message = await self._run_maa()

                if status == "success":
                    final_status = "success"
                    final_message = "任务完成"
                    break
                elif status in ("timeout", "error"):
                    final_status = status
                    final_message = message
                    break
                else:
                    final_status = status
                    final_message = message
                    if attempt >= self.config.max_restart:
                        break

            # 4. 清理
            end_time = datetime.now()

            if self.config.restore_after_run and self.backup_dir:
                await self._restore_config()

            # 5. 通知结果
            result_msg = f"MAA 任务{'完成' if final_status == 'success' else '失败'}: {final_message}"
            if self.notifier:
                self.notifier.notify_result(result_msg)

            return MAAExecutionResult(
                status=final_status,
                message=final_message,
                start_time=start_time,
                end_time=end_time,
                duration=(end_time - start_time).total_seconds(),
                logs=self.log_monitor.get_logs() if self.log_monitor else [],
                tasks_completed=[t for t, done in self.task_dict.items() if not done],
                tasks_failed=[t for t, done in self.task_dict.items() if done],
                restart_count=restart_count,
            )

        except Exception as e:
            error_msg = f"执行异常: {str(e)}"
            if self.notifier:
                self.notifier.notify_result(error_msg)
            return MAAExecutionResult(
                status="error",
                message=error_msg,
                start_time=start_time,
                end_time=datetime.now(),
                duration=(datetime.now() - start_time).total_seconds(),
                logs=[],
                restart_count=restart_count,
            )

        finally:
            # 确保前端通知被清理，无论成功或失败
            if self.notifier:
                self.notifier.hide_status()

    async def _backup_config(self) -> None:
        """备份 MAA 配置"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_dir = self.maa_root / f"_backup_{timestamp}"

        if self.maa_config_dir.exists():
            shutil.copytree(self.maa_config_dir, self.backup_dir, dirs_exist_ok=True)

        await self._report_progress("备份", {"path": str(self.backup_dir)})

    async def _restore_config(self) -> None:
        """还原 MAA 配置"""
        if self.backup_dir and self.backup_dir.exists():
            shutil.copytree(self.backup_dir, self.maa_config_dir, dirs_exist_ok=True)
            shutil.rmtree(self.backup_dir, ignore_errors=True)

        await self._report_progress("还原", {"restored": True})

    async def _start_emulator(self) -> EmulatorInfo:
        """启动模拟器"""
        self._notify("正在启动模拟器...")
        await self._report_progress("启动模拟器", {"id": self.config.emulator_id})

        emulator_info = await self.emulator_manager.start(
            self.config.emulator_id,
            self.config.emulator_index,
        )

        ready = await self.emulator_manager.wait_ready(
            self.config.emulator_id,
            self.config.emulator_index,
            timeout=120,
        )

        if not ready:
            raise RuntimeError("模拟器启动超时")

        # 重新获取 ADB 地址
        info = await self.emulator_manager.get_info(
            self.config.emulator_id, self.config.emulator_index,
        )
        if self.config.emulator_id in info and self.config.emulator_index in info[self.config.emulator_id]:
            emulator_info = info[self.config.emulator_id][self.config.emulator_index]

        self._notify(f"模拟器就绪 (ADB: {emulator_info.adb_address})")
        await self._report_progress("模拟器就绪", {"adb": emulator_info.adb_address})
        return emulator_info

    async def _configure_maa(self, emulator_info: Optional[EmulatorInfo]) -> None:
        """配置 MAA（直接读写 gui.json / gui.new.json）"""
        await self._report_progress("配置MAA", {})

        gui_json_path = self.maa_config_dir / "gui.json"
        gui_new_json_path = self.maa_config_dir / "gui.new.json"

        gui_set = json.loads(gui_json_path.read_text(encoding="utf-8"))
        gui_new_set = json.loads(gui_new_json_path.read_text(encoding="utf-8"))

        # 使用 Default 配置
        if gui_set.get("Current") != "Default":
            gui_set["Configurations"]["Default"] = gui_set["Configurations"][gui_set["Current"]]
            gui_new_set["Configurations"]["Default"] = gui_new_set["Configurations"][gui_set["Current"]]
            gui_set["Current"] = "Default"

        global_set = gui_set["Global"]
        default_set = gui_set["Configurations"]["Default"]

        # 全局配置
        global_set["GUI.Localization"] = "zh-cn"
        for i in range(1, 9):
            global_set[f"Timer.Timer{i}"] = "False"
        global_set["GUI.UseTray"] = "True"
        global_set["GUI.MinimizeToTray"] = "True"
        global_set["Start.MinimizeDirectly"] = "True"

        # 连接配置
        if emulator_info and emulator_info.adb_address != "Unknown":
            default_set["Connect.Address"] = emulator_info.adb_address
        elif self.config.connect_address:
            default_set["Connect.Address"] = self.config.connect_address

        # 运行配置
        default_set["Start.RunDirectly"] = "True"
        default_set["Start.OpenEmulatorAfterLaunch"] = "False"
        default_set["Start.StartGame"] = "True"

        # 客户端配置
        default_set["Start.ClientType"] = self.config.client_type

        # 任务后动作（MAA v6.3.2+ 枚举: 0=None, 1=StopGame, 4=ExitEmulator, 8=ExitSelf）
        post_action_map = {
            "NoAction": "0",
            "ExitGame": "1",
            "ExitEmulator": "4",
            "ExitSelf": "8",
        }
        default_set["MainFunction.PostActions"] = post_action_map.get(
            self.config.post_action, "8"
        )

        # 构建任务队列
        task_queue = self._build_task_queue(gui_new_set)
        gui_new_set["Configurations"]["Default"]["TaskQueue"] = task_queue

        # 保存
        gui_json_path.write_text(
            json.dumps(gui_set, ensure_ascii=False, indent=4), encoding="utf-8"
        )
        gui_new_json_path.write_text(
            json.dumps(gui_new_set, ensure_ascii=False, indent=4), encoding="utf-8"
        )

        # B服协议
        if self.config.client_type == "Bilibili":
            await self._set_bilibili_agreement(True)

    def _build_task_queue(self, gui_new_set: Dict) -> List[Dict]:
        """构建任务队列"""
        task_queue = []
        existing_queue = gui_new_set["Configurations"]["Default"].get("TaskQueue", [])

        # 提取现有任务模板
        task_templates = {}
        for en_task, zh_task in zip(MAA_TASKS, MAA_TASKS_ZH):
            for item in existing_queue:
                if item.get("TaskType") == en_task:
                    task_templates[en_task] = item.copy()
                    task_templates[en_task]["Name"] = zh_task
                    break
            else:
                task_templates[en_task] = {
                    "$type": f"{en_task}Task",
                    "Name": zh_task,
                    "IsEnable": False,
                    "TaskType": en_task,
                }

        # 配置开始唤醒
        task_templates["StartUp"]["AccountName"] = self.config.account_name
        task_templates["StartUp"]["IsEnable"] = self.config.tasks.get("StartUp", True)

        # 配置理智作战
        fight_task = task_templates["Fight"]
        if self.config.fight_mode == "Annihilation":
            fight_task.update(MAA_ANNIHILATION_FIGHT_BASE)
            fight_task["AnnihilationStage"] = self.config.annihilation_stage
        else:
            fight_task["UseMedicine"] = bool(self.config.medicine_count > 0)
            fight_task["MedicineCount"] = self.config.medicine_count
            fight_task["UseStone"] = bool(self.config.stone_count > 0)
            fight_task["StoneCount"] = self.config.stone_count

            stages = [
                self.config.stage, self.config.stage_1,
                self.config.stage_2, self.config.stage_3,
            ]
            fight_task["StagePlan"] = [s for s in stages if s and s != "-"]
            fight_task["IsStageManually"] = True

        # 配置作战扩展
        if self.config.tasks.get("Fight") and self.config.fight_mode != "Annihilation":
            if self.config.fight_times_limit > 0:
                fight_task["EnableTimesLimit"] = True
                fight_task["TimesLimit"] = self.config.fight_times_limit
            if self.config.fight_drop_id:
                fight_task["EnableTargetDrop"] = True
                fight_task["DropId"] = self.config.fight_drop_id
                fight_task["DropCount"] = self.config.fight_drop_count
            fight_task["UseExpiringMedicine"] = self.config.fight_use_expiring_medicine
            fight_task["IsDrGrandet"] = self.config.fight_is_dr_grandet
            if self.config.fight_series > 0:
                fight_task["Series"] = self.config.fight_series

        # 配置肉鸽
        if self.config.tasks.get("Roguelike"):
            roguelike_task = task_templates["Roguelike"]
            roguelike_task["Theme"] = self.config.roguelike_theme
            roguelike_task["Mode"] = self.config.roguelike_mode
            roguelike_task["StartCount"] = self.config.roguelike_start_count
            if self.config.roguelike_squad:
                roguelike_task["Squad"] = self.config.roguelike_squad
            if self.config.roguelike_squad_collectible:
                roguelike_task["SquadCollectible"] = self.config.roguelike_squad_collectible
            roguelike_task["Difficulty"] = self.config.roguelike_difficulty
            if self.config.roguelike_roles:
                roguelike_task["Roles"] = self.config.roguelike_roles
            if self.config.roguelike_core_char:
                roguelike_task["CoreChar"] = self.config.roguelike_core_char
            roguelike_task["Investment"] = self.config.roguelike_investment
            roguelike_task["InvestCount"] = self.config.roguelike_invest_count
            roguelike_task["InvestWithMoreScore"] = self.config.roguelike_invest_with_more_score
            roguelike_task["UseSupport"] = self.config.roguelike_use_support
            roguelike_task["UseSupportNonFriend"] = self.config.roguelike_use_support_non_friend
            roguelike_task["StopWhenDepositFull"] = self.config.roguelike_stop_when_deposit_full
            roguelike_task["StopAtFinalBoss"] = self.config.roguelike_stop_at_final_boss
            roguelike_task["StopWhenLevelMax"] = self.config.roguelike_stop_when_level_max
            roguelike_task["StartWithEliteTwo"] = self.config.roguelike_start_with_elite_two
            roguelike_task["StartWithEliteTwoOnly"] = self.config.roguelike_start_with_elite_two_only
            roguelike_task["CollectibleStartAwards"] = self.config.roguelike_collectible_start_awards
            roguelike_task["CollectibleShopping"] = self.config.roguelike_collectible_shopping
            roguelike_task["MonthlySquadAutoIterate"] = self.config.roguelike_monthly_squad_auto_iterate
            roguelike_task["MonthlySquadCheckComms"] = self.config.roguelike_monthly_squad_check_comms
            roguelike_task["DeepExplorationAutoIterate"] = self.config.roguelike_deep_exploration_auto_iterate
            roguelike_task["FindPlaytimeTarget"] = self.config.roguelike_find_playtime_target
            roguelike_task["RefreshTraderWithDice"] = self.config.roguelike_refresh_trader_with_dice
            roguelike_task["SquadIsFoldartal"] = self.config.roguelike_squad_is_foldartal
            if self.config.roguelike_expected_collapsal_paradigms:
                roguelike_task["ExpectedCollapsalParadigms"] = self.config.roguelike_expected_collapsal_paradigms
            # Sami 折叠通路相关（JSON key 需带 Sami 前缀）
            roguelike_task["SamiFirstFloorFoldartal"] = self.config.roguelike_sami_first_floor_foldartal
            if self.config.roguelike_sami_first_floor_foldartals:
                roguelike_task["SamiFirstFloorFoldartals"] = self.config.roguelike_sami_first_floor_foldartals
            roguelike_task["SamiNewSquad2StartingFoldartal"] = self.config.roguelike_sami_new_squad2_starting_foldartal
            if self.config.roguelike_sami_new_squad2_starting_foldartals:
                roguelike_task["SamiNewSquad2StartingFoldartals"] = self.config.roguelike_sami_new_squad2_starting_foldartals
            # 种子
            roguelike_task["StartWithSeed"] = self.config.roguelike_start_with_seed
            if self.config.roguelike_seed:
                roguelike_task["Seed"] = self.config.roguelike_seed

        # 配置生息演算
        if self.config.tasks.get("Reclamation"):
            reclamation_task = task_templates["Reclamation"]
            reclamation_task["Theme"] = self.config.reclamation_theme
            reclamation_task["Mode"] = self.config.reclamation_mode
            if self.config.reclamation_tool_to_craft:
                reclamation_task["ToolToCraft"] = self.config.reclamation_tool_to_craft
            reclamation_task["IncrementMode"] = self.config.reclamation_increment_mode
            reclamation_task["MaxCraftCountPerRound"] = self.config.reclamation_max_craft_count
            reclamation_task["ClearStore"] = self.config.reclamation_clear_store

        # 配置公招
        if self.config.tasks.get("Recruit"):
            recruit_task = task_templates["Recruit"]
            recruit_task["UseExpedited"] = self.config.recruit_use_expedited
            recruit_task["MaxTimes"] = self.config.recruit_max_times
            recruit_task["RefreshLevel3"] = self.config.recruit_refresh_level3
            recruit_task["ForceRefresh"] = self.config.recruit_force_refresh
            recruit_task["Level1NotChoose"] = self.config.recruit_level1_not_choose
            recruit_task["Level3Choose"] = self.config.recruit_level3_choose
            recruit_task["Level4Choose"] = self.config.recruit_level4_choose
            recruit_task["Level5Choose"] = self.config.recruit_level5_choose
            recruit_task["Level3Time"] = self.config.recruit_level3_time
            recruit_task["Level4Time"] = self.config.recruit_level4_time
            recruit_task["Level5Time"] = self.config.recruit_level5_time

        # 配置基建
        if self.config.tasks.get("Infrast"):
            infrast_task = task_templates["Infrast"]
            infrast_task["Mode"] = self.config.infrast_mode
            if self.config.custom_infrast_path:
                infrast_task["Filename"] = self.config.custom_infrast_path
            infrast_task["PlanSelect"] = self.config.custom_infrast_plan_index
            infrast_task["UsesOfDrones"] = self.config.infrast_uses_of_drones
            infrast_task["DormThreshold"] = self.config.infrast_dorm_threshold
            infrast_task["DormTrustEnabled"] = self.config.infrast_dorm_trust_enabled
            infrast_task["OriginiumShardAutoReplenishment"] = self.config.infrast_originium_shard_auto_replenishment
            infrast_task["DormFilterNotStationed"] = self.config.infrast_dorm_filter_not_stationed
            infrast_task["ReceptionMessageBoard"] = self.config.infrast_reception_message_board
            infrast_task["ContinueTraining"] = self.config.infrast_continue_training
            infrast_task["ReceptionClueExchange"] = self.config.infrast_reception_clue_exchange
            infrast_task["SendClue"] = self.config.infrast_send_clue
            if self.config.infrast_rooms is not None:
                # 支持简写(房间名列表)和完整格式(对象列表)
                rooms = self.config.infrast_rooms
                if rooms and isinstance(rooms[0], str):
                    rooms = [{"Room": r, "IsEnabled": True} for r in rooms]
                infrast_task["RoomList"] = rooms

        # 配置商店
        if self.config.tasks.get("Mall"):
            mall_task = task_templates["Mall"]
            mall_task["Shopping"] = self.config.mall_shopping
            mall_task["CreditFight"] = self.config.mall_credit_fight
            mall_task["CreditFightOnceADay"] = self.config.mall_credit_fight_once_a_day
            mall_task["VisitFriends"] = self.config.mall_visit_friends
            mall_task["VisitFriendsOnceADay"] = self.config.mall_visit_friends_once_a_day
            mall_task["FirstList"] = self.config.mall_first_list
            mall_task["BlackList"] = self.config.mall_black_list
            mall_task["ShoppingIgnoreBlackListWhenFull"] = self.config.mall_shopping_ignore_black_list_when_full
            mall_task["OnlyBuyDiscount"] = self.config.mall_only_buy_discount
            mall_task["ReserveMaxCredit"] = self.config.mall_reserve_max_credit

        # 配置奖励
        if self.config.tasks.get("Award"):
            award_task = task_templates["Award"]
            award_task["Award"] = True
            award_task["Mail"] = self.config.award_mail
            award_task["FreeGacha"] = self.config.award_free_gacha
            award_task["Orundum"] = self.config.award_orundum
            award_task["Mining"] = self.config.award_mining
            award_task["SpecialAccess"] = self.config.award_special_access

        # 添加所有任务
        for task_type in MAA_TASKS:
            task_templates[task_type]["IsEnable"] = self.config.tasks.get(task_type, False)
            task_queue.append(task_templates[task_type])

            # 剩余理智关卡
            if (task_type == "Fight"
                    and self.config.fight_mode == "Routine"
                    and self.config.tasks.get("Fight")
                    and self.config.remain_stage):
                remain_fight = MAA_REMAIN_FIGHT_BASE.copy()
                remain_fight["StagePlan"] = [self.config.remain_stage]
                task_queue.append(remain_fight)

        return task_queue

    @staticmethod
    def _kill_all_maa_processes() -> int:
        """
        终止系统中所有 MAA.exe 进程

        Returns:
            被终止的进程数
        """
        killed = 0
        try:
            import psutil
            for proc in psutil.process_iter(["name"]):
                try:
                    if proc.info["name"] and proc.info["name"].lower() == "maa.exe":
                        proc.kill()
                        killed += 1
                        logger.info(f"已终止 MAA 进程: PID={proc.pid}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.debug(f"MAA 进程清理失败: {e}")
        return killed

    async def _run_maa(self) -> tuple:
        """运行 MAA 并监控"""
        self._notify("MAA 正在启动...")
        await self._report_progress("启动MAA", {})

        # 初始化日志监控
        self.log_monitor = EnhancedLogMonitor(
            time_range=(1, 20),
            time_format="%Y-%m-%d %H:%M:%S",
            callback=self._log_callback,
            except_logs=["如果长时间无进一步日志更新，可能需要手动干预。"],
        )

        self.wait_event.clear()
        self.task_dict = self.config.tasks.copy()
        self._last_forwarded_line_count = 0

        # 在启动前清理所有残留 MAA 进程（防止 "无法同时创建多个实例"）
        killed = self._kill_all_maa_processes()
        if killed > 0:
            logger.info(f"启动前清理了 {killed} 个残留 MAA 进程")
            await asyncio.sleep(2)  # 等待进程完全退出

        # 确保 process_manager 状态干净
        await self.process_manager.clear()

        # 启动 MAA 进程
        await self.process_manager.open_process(self.maa_exe)

        # MAA.exe 是启动器：它启动 GUI 后自身会退出。
        # 等待后用 psutil 找到实际运行的 MAA GUI 进程来跟踪。
        await asyncio.sleep(5)
        self._track_maa_gui_process()

        # 开始日志监控
        log_start_time = datetime.now()
        await self.log_monitor.start_monitor_file(self.maa_log_path, log_start_time)

        # 等待完成或超时
        try:
            await asyncio.wait_for(
                self.wait_event.wait(),
                timeout=self.config.timeout_minutes * 60,
            )
        except asyncio.TimeoutError:
            await self.log_monitor.stop()
            self._kill_all_maa_processes()
            await self.process_manager.clear()
            return "timeout", "任务超时"

        await self.log_monitor.stop()
        # 彻底清理所有 MAA 进程（避免重试时 "无法同时创建多个实例"）
        self._kill_all_maa_processes()
        await self.process_manager.clear()
        return self._parse_final_status()

    def _track_maa_gui_process(self) -> None:
        """查找并跟踪实际运行的 MAA GUI 进程（非启动器）"""
        try:
            import psutil
            launcher_pid = (self.process_manager.process.pid
                           if self.process_manager.process else -1)
            for proc in psutil.process_iter(["name", "pid"]):
                try:
                    if (proc.info["name"]
                            and proc.info["name"].lower() == "maa.exe"
                            and proc.is_running()
                            and proc.pid != launcher_pid):
                        self.process_manager.target_process = proc
                        logger.info(f"跟踪 MAA GUI 进程: PID={proc.pid}")
                        return
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.debug(f"MAA GUI 进程搜索失败: {e}")

    # 不转发到前端的日志行关键字（调试噪音）
    _LOG_NOISE_KEYWORDS = [
        "Downloading",
        "OTA version",
        "[Info] MAA",  # MAA 启动信息行
        "如果长时间无进一步日志更新",
        "检查更新",
        "资源版本",
    ]

    async def _log_callback(self, logs: List[str], latest_time: datetime) -> None:
        """日志回调 - 解析日志判断状态 + 实时转发日志到前端"""
        log_text = "".join(logs)

        await self._report_progress("日志更新", {"lines": len(logs)})

        # ---- 实时转发新日志行到前端 ----
        new_lines = logs[self._last_forwarded_line_count:]
        self._last_forwarded_line_count = len(logs)

        for line in new_lines:
            stripped = line.strip()
            if not stripped:
                continue
            # 跳过调试噪音
            if any(kw in stripped for kw in self._LOG_NOISE_KEYWORDS):
                continue
            # 提取时间戳后的内容（MAA 日志格式: [时间戳] 内容）
            # 时间戳占位 1-20，加上前后的方括号约 22 字符
            display_text = stripped
            if len(stripped) > 22 and stripped[0] in ("[", "2"):
                # 尝试去掉时间戳前缀，只显示核心内容
                content_start = stripped.find("]", 20)
                if content_start > 0:
                    display_text = stripped[content_start + 1:].strip()
                    if not display_text:
                        continue
            self._notify(f"MAA: {display_text}", auto_hide_ms=8000)

        # ---- 判断状态并推送通知 ----
        if "未选择任务" in log_text:
            self.current_status = "未选择任务"
            self._notify("MAA: 未选择任务")
            self.wait_event.set()
        elif "任务出错: 开始唤醒" in log_text:
            self.current_status = "登录失败"
            self._notify("MAA: 登录失败")
            self.wait_event.set()
        elif "任务已全部完成！" in log_text:
            for en_task, zh_task in zip(MAA_TASKS, MAA_TASKS_ZH):
                if f"完成任务: {zh_task}" in log_text:
                    self.task_dict[en_task] = False

            if any(self.task_dict.values()):
                self.current_status = "部分任务失败"
                self._notify("MAA: 部分任务失败")
            else:
                self.current_status = "success"
                self._notify("MAA: 任务已全部完成")
            self.wait_event.set()
        elif "请 ｢检查连接设置｣" in log_text:
            self.current_status = "ADB连接异常"
            self._notify("MAA: ADB 连接异常")
            self.wait_event.set()
        elif "未检测到任何模拟器" in log_text:
            self.current_status = "未检测到模拟器"
            self._notify("MAA: 未检测到模拟器")
            self.wait_event.set()
        elif "已停止" in log_text:
            self.current_status = "任务中止"
            self._notify("MAA: 任务已停止")
            self.wait_event.set()
        elif not await self.process_manager.is_running():
            self.current_status = "进程退出"
            self._notify("MAA: 进程已退出")
            self.wait_event.set()

    def _parse_final_status(self) -> tuple:
        """解析最终状态

        返回值含义:
        - "success": 任务完成
        - "failed":  可重试的失败（如 ADB 连接异常）
        - "error":   不可重试的错误（进程退出、用户中止等）
        """
        if self.current_status == "success":
            return "success", "任务完成"
        elif self.current_status in ("ADB连接异常", "未检测到模拟器"):
            return "failed", self.current_status
        elif self.current_status in ("登录失败", "未选择任务",
                                     "进程退出", "任务中止"):
            return "error", self.current_status
        else:
            return "failed", self.current_status

    async def _set_bilibili_agreement(self, agree: bool) -> None:
        """设置 B服协议"""
        if not self.maa_tasks_json.exists():
            return
        tasks_data = json.loads(self.maa_tasks_json.read_text(encoding="utf-8"))
        self.maa_tasks_json.write_text(
            json.dumps(tasks_data, ensure_ascii=False, indent=4), encoding="utf-8"
        )

    def _notify(self, text: str, auto_hide_ms: int = 5000) -> None:
        """推送状态通知"""
        if self.notifier:
            self.notifier.notify_status(text, auto_hide_ms)

    async def _report_progress(self, event: str, data: Dict[str, Any]) -> None:
        """报告进度"""
        if self.progress_callback:
            try:
                self.progress_callback(event, data)
            except Exception:
                pass
