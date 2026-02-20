"""MAA 控制工具实现 - 完整版本"""

import asyncio
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from threading import Thread, Lock
from tempfile import gettempdir

# 将项目根目录加入 Python 路径，便于导入同项目模块
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 导入 agent_comms 模块
from agent_comms.config import (
    get_maa_path,
    set_maa_path as save_maa_path,
    validate_maa_path,
    get_maa_exe_path,
    get_maa_config_dir,
    get_connect_address as get_saved_connect_address,
    set_connect_address as save_connect_address,
    get_config,
    set_config,
)

# 导入 maa_comms.process 模块
from maa_comms.process import (
    launch_maa,
    kill_maa,
    is_maa_running,
    update_maa as maa_update,
)

# 导入 maa_comms.script_config 模块
from maa_comms.script_config.config_builder import (
    load_maa_config,
    save_maa_config,
    ensure_default_config,
    apply_global_run_options,
    set_connect_address as set_config_connect_address,
    set_post_actions,
    set_client_and_account,
    build_task_queue_from_tasks,
)
from maa_comms.script_config.config_copy import (
    backup_config_dir,
    restore_config_dir,
)
from maa_comms.script_config.tasks_bilibili import set_bilibili_agreement
from maa_comms.script_config.constants import (
    MAA_TASKS,
    MAA_TASKS_ZH,
    MAA_DEBUG_LOG,
    MAA_TASKS_JSON,
)

# 导入 maa_comms.run_loop 模块
from maa_comms.run_loop import run_maa_until_done, run_queue

# 导入 maa_comms.task_system 模块
from maa_comms.task_system.progress_callback import (
    parse_status_from_log,
    is_terminal_status,
    STATUS_RUNNING,
    STATUS_SUCCESS,
)


class TaskHistory:
    """任务历史记录"""

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.history: List[Dict[str, Any]] = []
        self._lock = Lock()

    def add_record(
        self,
        task_type: str,
        status: str,
        start_time: datetime,
        end_time: datetime,
        details: Optional[Dict[str, Any]] = None,
    ):
        """添加任务记录"""
        with self._lock:
            record = {
                "task_type": task_type,
                "status": status,
                "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
                "duration": (end_time - start_time).total_seconds(),
                "details": details or {},
            }
            self.history.insert(0, record)
            if len(self.history) > self.max_size:
                self.history = self.history[: self.max_size]

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取历史记录"""
        with self._lock:
            return self.history[:limit]


class MAATools:
    """MAA 工具类 - 完整功能版本"""

    def __init__(self):
        # 任务状态
        self._current_task_status = STATUS_RUNNING
        self._current_logs: List[str] = []
        self._latest_time: Optional[datetime] = None
        self._current_task_type = "未知"
        self._task_start_time: Optional[datetime] = None
        self._lock = Lock()

        # 监控线程
        self._monitoring_thread: Optional[Thread] = None
        self._stop_monitoring = False

        # 任务历史
        self._task_history = TaskHistory()

        # 备份目录
        self._backup_base_dir = Path(gettempdir()) / "maa_control_backups"
        self._backup_base_dir.mkdir(parents=True, exist_ok=True)

    # ==================== 基础配置管理 ====================

    async def set_maa_path(self, maa_path: Optional[str]) -> Dict[str, Any]:
        """设置 MAA 安装路径"""
        try:
            if not maa_path or not isinstance(maa_path, str):
                return {
                    "status": "error",
                    "message": "请提供有效的 MAA 路径",
                    "data": {}
                }

            # 验证路径
            is_valid, msg = validate_maa_path(maa_path)
            if not is_valid:
                return {"status": "error", "message": msg, "data": {}}

            # 保存路径
            save_maa_path(maa_path)

            return {
                "status": "success",
                "message": f"MAA 路径设置成功: {maa_path}",
                "data": {
                    "maa_path": str(Path(maa_path).resolve()),
                    "maa_exe": str(Path(maa_path) / "MAA.exe"),
                    "config_dir": str(Path(maa_path) / "config"),
                }
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"设置 MAA 路径失败: {str(e)}",
                "data": {}
            }

    async def get_maa_status(self) -> Dict[str, Any]:
        """获取 MAA 当前状态"""
        try:
            maa_path = get_maa_path()

            # 检查是否已配置路径
            if not maa_path:
                return {
                    "status": "success",
                    "message": "MAA 未配置",
                    "data": {
                        "configured": False,
                        "running": False,
                        "maa_path": None,
                    }
                }

            # 验证路径
            is_valid, msg = validate_maa_path(maa_path)
            if not is_valid:
                return {
                    "status": "success",
                    "message": f"MAA 路径无效: {msg}",
                    "data": {
                        "configured": True,
                        "valid": False,
                        "running": False,
                        "maa_path": maa_path,
                        "error": msg,
                    }
                }

            # 检查是否正在运行
            maa_exe = get_maa_exe_path()
            running = is_maa_running(maa_exe) if maa_exe else False

            # 获取当前任务状态
            with self._lock:
                task_status = self._current_task_status
                task_type = self._current_task_type
                latest_logs = self._current_logs[-10:] if self._current_logs else []
                task_start_time = self._task_start_time

            # 计算运行时长
            duration = None
            if task_start_time:
                duration = (datetime.now() - task_start_time).total_seconds()

            return {
                "status": "success",
                "message": "MAA 状态获取成功",
                "data": {
                    "configured": True,
                    "valid": True,
                    "running": running,
                    "maa_path": str(Path(maa_path).resolve()),
                    "maa_exe": str(maa_exe),
                    "connect_address": get_saved_connect_address(),
                    "task_status": task_status,
                    "task_type": task_type,
                    "duration_seconds": duration,
                    "latest_logs": latest_logs,
                    "is_finished": is_terminal_status(task_status),
                }
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"获取 MAA 状态失败: {str(e)}",
                "data": {}
            }

    async def set_connect_address(self, address: Optional[str]) -> Dict[str, Any]:
        """设置连接地址"""
        try:
            if not address:
                return {
                    "status": "error",
                    "message": "请提供有效的连接地址",
                    "data": {}
                }

            save_connect_address(address)

            return {
                "status": "success",
                "message": f"连接地址设置成功: {address}",
                "data": {"connect_address": address}
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"设置连接地址失败: {str(e)}",
                "data": {}
            }

    async def get_connect_address(self) -> Dict[str, Any]:
        """获取连接地址"""
        try:
            address = get_saved_connect_address()

            return {
                "status": "success",
                "message": "连接地址获取成功",
                "data": {
                    "connect_address": address,
                    "configured": address is not None,
                }
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"获取连接地址失败: {str(e)}",
                "data": {}
            }

    # ==================== 任务执行 ====================

    async def start_maa_task(
        self,
        tasks: Dict[str, bool],
        fight_mode: str = "Routine",
        medicine_count: int = 0,
        stone_count: int = 0,
        series: int = 0,
        stage: str = "",
        stage_1: str = "",
        stage_2: str = "",
        stage_3: str = "",
        remain_stage: str = "",
        client_type: str = "Official",
        account_name: str = "",
        annihilation_stage: str = "Annihilation",
        infrast_mode: str = "Normal",
        custom_infrast_path: Optional[str] = None,
        custom_infrast_plan_index: int = 0,
        post_action: str = "NoAction",
        connect_address: Optional[str] = None,
        max_restart: int = 3,
        restart_delay: float = 2.0,
        backup_before_run: bool = True,
        restore_after_run: bool = True,
        auto_update: bool = False,
    ) -> Dict[str, Any]:
        """启动 MAA 执行任务"""
        try:
            # 检查 MAA 路径
            maa_path = get_maa_path()
            if not maa_path:
                return {
                    "status": "error",
                    "message": "请先使用 set_maa_path 配置 MAA 路径",
                    "data": {}
                }

            is_valid, msg = validate_maa_path(maa_path)
            if not is_valid:
                return {"status": "error", "message": f"MAA 路径无效: {msg}", "data": {}}

            # 检查是否已在运行
            maa_exe = get_maa_exe_path()
            if is_maa_running(maa_exe):
                return {
                    "status": "error",
                    "message": "MAA 已在运行中，请先停止当前任务",
                    "data": {}
                }

            # 自动更新
            if auto_update:
                try:
                    maa_update(Path(maa_path))
                except Exception as e:
                    pass  # 更新失败不影响后续流程

            # 获取配置目录
            config_dir = get_maa_config_dir()
            if not config_dir or not config_dir.exists():
                return {
                    "status": "error",
                    "message": "MAA 配置目录不存在，请先运行一次 MAA",
                    "data": {}
                }

            # 备份配置
            backup_dir = None
            if backup_before_run:
                backup_dir = self._backup_base_dir / f"auto_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                backup_config_dir(config_dir, backup_dir)

            # 加载和修改配置
            try:
                self._prepare_config(
                    config_dir=config_dir,
                    tasks=tasks,
                    fight_mode=fight_mode,
                    medicine_count=medicine_count,
                    stone_count=stone_count,
                    series=series,
                    stage=stage,
                    stage_1=stage_1,
                    stage_2=stage_2,
                    stage_3=stage_3,
                    remain_stage=remain_stage,
                    client_type=client_type,
                    account_name=account_name,
                    annihilation_stage=annihilation_stage,
                    infrast_mode=infrast_mode,
                    custom_infrast_path=custom_infrast_path,
                    custom_infrast_plan_index=custom_infrast_plan_index,
                    post_action=post_action,
                    connect_address=connect_address,
                )
            except Exception as e:
                # 配置失败时还原备份
                if backup_dir and backup_dir.exists():
                    restore_config_dir(config_dir, backup_dir)
                return {
                    "status": "error",
                    "message": f"配置 MAA 失败: {str(e)}",
                    "data": {}
                }

            # B服协议处理
            if client_type == "Bilibili":
                tasks_json_path = Path(maa_path) / MAA_TASKS_JSON
                if tasks_json_path.exists():
                    set_bilibili_agreement(tasks_json_path, True)

            # 重置监控状态
            with self._lock:
                self._current_task_status = STATUS_RUNNING
                self._current_logs = []
                self._latest_time = None
                self._current_task_type = "启动中"
                self._task_start_time = datetime.now()
                self._stop_monitoring = False

            # 启动异步任务执行
            asyncio.create_task(
                self._run_maa_task_async(
                    maa_exe=maa_exe,
                    maa_path=Path(maa_path),
                    tasks=tasks,
                    fight_mode=fight_mode,
                    max_restart=max_restart,
                    restart_delay=restart_delay,
                    backup_dir=backup_dir if restore_after_run else None,
                    config_dir=config_dir,
                    client_type=client_type,
                )
            )

            return {
                "status": "success",
                "message": "MAA 任务已启动",
                "data": {
                    "tasks": tasks,
                    "fight_mode": fight_mode,
                    "medicine_count": medicine_count,
                    "stage": stage,
                    "client_type": client_type,
                    "account_name": account_name,
                    "max_restart": max_restart,
                    "backup_created": backup_dir is not None,
                }
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"启动 MAA 任务失败: {str(e)}",
                "data": {}
            }

    async def _run_maa_task_async(
        self,
        maa_exe: Path,
        maa_path: Path,
        tasks: Dict[str, bool],
        fight_mode: str,
        max_restart: int,
        restart_delay: float,
        backup_dir: Optional[Path],
        config_dir: Path,
        client_type: str,
    ):
        """异步执行 MAA 任务（后台运行）"""
        start_time = datetime.now()

        def callback(logs: List[str], latest_time: datetime, status: str):
            """日志回调"""
            with self._lock:
                self._current_logs = logs
                self._latest_time = latest_time
                self._current_task_status = status

                # 解析当前任务类型
                for task_zh in MAA_TASKS_ZH:
                    if any(task_zh in log for log in logs[-5:]):
                        self._current_task_type = task_zh
                        break

        try:
            # 启动并监控（含异常重启）
            log_path = maa_path / MAA_DEBUG_LOG
            final_status = await asyncio.get_event_loop().run_in_executor(
                None,
                run_maa_until_done,
                maa_exe,
                log_path,
                callback,
                None,  # log_start_time
                1.0,  # poll_interval
                60.0,  # idle_timeout_minutes
                {"enabled_tasks": tasks, "mode": fight_mode},  # parse_status_kwargs
                max_restart,
                restart_delay,
            )

            with self._lock:
                self._current_task_status = final_status

        except Exception as e:
            with self._lock:
                self._current_task_status = f"执行异常: {str(e)}"
            final_status = f"执行异常: {str(e)}"

        finally:
            # 记录历史
            end_time = datetime.now()
            self._task_history.add_record(
                task_type="单次任务",
                status=final_status,
                start_time=start_time,
                end_time=end_time,
                details={
                    "tasks": tasks,
                    "fight_mode": fight_mode,
                    "client_type": client_type,
                },
            )

            # 清理 B服协议
            if client_type == "Bilibili":
                tasks_json_path = maa_path / MAA_TASKS_JSON
                if tasks_json_path.exists():
                    set_bilibili_agreement(tasks_json_path, False)

            # 还原配置
            if backup_dir and backup_dir.exists():
                restore_config_dir(config_dir, backup_dir, remove_backup=True)

    async def start_maa_queue(
        self,
        queue_items: List[Dict[str, Any]],
        max_restart: int = 3,
        restart_delay: float = 2.0,
    ) -> Dict[str, Any]:
        """启动 MAA 队列任务（多账号/多配置循环执行）"""
        try:
            if not queue_items:
                return {
                    "status": "error",
                    "message": "队列任务列表不能为空",
                    "data": {}
                }

            # 检查 MAA 路径
            maa_path = get_maa_path()
            if not maa_path:
                return {
                    "status": "error",
                    "message": "请先使用 set_maa_path 配置 MAA 路径",
                    "data": {}
                }

            is_valid, msg = validate_maa_path(maa_path)
            if not is_valid:
                return {"status": "error", "message": f"MAA 路径无效: {msg}", "data": {}}

            maa_exe = get_maa_exe_path()
            if is_maa_running(maa_exe):
                return {
                    "status": "error",
                    "message": "MAA 已在运行中，请先停止当前任务",
                    "data": {}
                }

            config_dir = get_maa_config_dir()
            if not config_dir or not config_dir.exists():
                return {
                    "status": "error",
                    "message": "MAA 配置目录不存在，请先运行一次 MAA",
                    "data": {}
                }

            # 启动异步队列任务
            asyncio.create_task(
                self._run_maa_queue_async(
                    queue_items=queue_items,
                    maa_exe=maa_exe,
                    maa_path=Path(maa_path),
                    config_dir=config_dir,
                    max_restart=max_restart,
                    restart_delay=restart_delay,
                )
            )

            return {
                "status": "success",
                "message": f"MAA 队列任务已启动，共 {len(queue_items)} 项",
                "data": {
                    "queue_size": len(queue_items),
                    "max_restart": max_restart,
                }
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"启动队列任务失败: {str(e)}",
                "data": {}
            }

    async def _run_maa_queue_async(
        self,
        queue_items: List[Dict[str, Any]],
        maa_exe: Path,
        maa_path: Path,
        config_dir: Path,
        max_restart: int,
        restart_delay: float,
    ):
        """异步执行队列任务"""
        start_time = datetime.now()

        def callback(logs: List[str], latest_time: datetime, status: str):
            """日志回调"""
            with self._lock:
                self._current_logs = logs
                self._latest_time = latest_time
                self._current_task_status = status
                for task_zh in MAA_TASKS_ZH:
                    if any(task_zh in log for log in logs[-5:]):
                        self._current_task_type = task_zh
                        break

        def prepare_item(item: Dict[str, Any]):
            """准备单项配置"""
            self._prepare_config(
                config_dir=config_dir,
                tasks=item.get("tasks", {}),
                fight_mode=item.get("fight_mode", "Routine"),
                medicine_count=item.get("medicine_count", 0),
                stone_count=item.get("stone_count", 0),
                series=item.get("series", 0),
                stage=item.get("stage", ""),
                stage_1=item.get("stage_1", ""),
                stage_2=item.get("stage_2", ""),
                stage_3=item.get("stage_3", ""),
                remain_stage=item.get("remain_stage", ""),
                client_type=item.get("client_type", "Official"),
                account_name=item.get("account_name", ""),
                annihilation_stage=item.get("annihilation_stage", "Annihilation"),
                infrast_mode=item.get("infrast_mode", "Normal"),
                custom_infrast_path=item.get("custom_infrast_path"),
                custom_infrast_plan_index=item.get("custom_infrast_plan_index", 0),
                post_action=item.get("post_action", "NoAction"),
                connect_address=item.get("connect_address"),
            )

            # B服协议
            if item.get("client_type") == "Bilibili":
                tasks_json_path = maa_path / MAA_TASKS_JSON
                if tasks_json_path.exists():
                    set_bilibili_agreement(tasks_json_path, True)

        def cleanup_item(item: Dict[str, Any]):
            """清理单项"""
            if item.get("client_type") == "Bilibili":
                tasks_json_path = maa_path / MAA_TASKS_JSON
                if tasks_json_path.exists():
                    set_bilibili_agreement(tasks_json_path, False)

        try:
            # 执行队列
            log_path = maa_path / MAA_DEBUG_LOG
            results = await asyncio.get_event_loop().run_in_executor(
                None,
                run_queue,
                queue_items,
                prepare_item,
                cleanup_item,
                maa_exe,
                log_path,
                callback,
                None,  # log_start_time
                1.0,  # poll_interval
                60.0,  # idle_timeout_minutes
                None,  # parse_status_kwargs (prepare_item 中已设置)
                max_restart,
                restart_delay,
            )

            final_status = f"队列完成: {results}"

        except Exception as e:
            final_status = f"队列执行异常: {str(e)}"

        finally:
            end_time = datetime.now()
            with self._lock:
                self._current_task_status = final_status

            self._task_history.add_record(
                task_type="队列任务",
                status=final_status,
                start_time=start_time,
                end_time=end_time,
                details={"queue_size": len(queue_items)},
            )

    async def get_task_progress(self) -> Dict[str, Any]:
        """获取任务进度"""
        try:
            with self._lock:
                status = self._current_task_status
                task_type = self._current_task_type
                logs = self._current_logs[-20:] if self._current_logs else []
                latest_time = self._latest_time
                task_start_time = self._task_start_time

            # 检查 MAA 是否在运行
            maa_exe = get_maa_exe_path()
            running = is_maa_running(maa_exe) if maa_exe else False

            # 计算运行时长
            duration = None
            if task_start_time:
                duration = (datetime.now() - task_start_time).total_seconds()

            return {
                "status": "success",
                "message": "任务进度获取成功",
                "data": {
                    "task_status": status,
                    "is_running": running,
                    "current_task": task_type,
                    "latest_time": latest_time.strftime("%Y-%m-%d %H:%M:%S") if latest_time else None,
                    "duration_seconds": duration,
                    "recent_logs": logs,
                    "is_finished": is_terminal_status(status),
                    "is_success": status == STATUS_SUCCESS,
                }
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"获取任务进度失败: {str(e)}",
                "data": {}
            }

    async def stop_maa(self) -> Dict[str, Any]:
        """停止 MAA"""
        try:
            maa_exe = get_maa_exe_path()
            if not maa_exe:
                return {
                    "status": "error",
                    "message": "MAA 未配置",
                    "data": {}
                }

            if not is_maa_running(maa_exe):
                return {
                    "status": "success",
                    "message": "MAA 未在运行",
                    "data": {"was_running": False}
                }

            # 停止监控
            self._stop_monitoring = True

            # 结束进程
            success = kill_maa(maa_exe)

            if success:
                with self._lock:
                    self._current_task_status = "已手动停止"
                    self._current_task_type = "已停止"

                return {
                    "status": "success",
                    "message": "MAA 已停止",
                    "data": {"was_running": True}
                }
            else:
                return {
                    "status": "error",
                    "message": "停止 MAA 失败",
                    "data": {}
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"停止 MAA 失败: {str(e)}",
                "data": {}
            }

    # ==================== MAA 维护 ====================

    async def update_maa(self) -> Dict[str, Any]:
        """检查并执行 MAA 更新"""
        try:
            maa_path = get_maa_path()
            if not maa_path:
                return {
                    "status": "error",
                    "message": "请先配置 MAA 路径",
                    "data": {}
                }

            # 检查是否有更新包
            maa_root = Path(maa_path)
            gui_json = maa_root / "config" / "gui.json"
            if not gui_json.exists():
                return {
                    "status": "error",
                    "message": "MAA 配置文件不存在",
                    "data": {}
                }

            # 读取更新包信息
            with open(gui_json, "r", encoding="utf-8") as f:
                data = json.load(f)

            update_package = data.get("Global", {}).get("VersionUpdate.package", "")
            if not update_package:
                return {
                    "status": "success",
                    "message": "没有可用的更新包",
                    "data": {"has_update": False}
                }

            update_package_path = maa_root / update_package
            if not update_package_path.exists():
                return {
                    "status": "success",
                    "message": "更新包文件不存在",
                    "data": {"has_update": False, "package": update_package}
                }

            # 执行更新
            success = maa_update(maa_root)

            if success:
                return {
                    "status": "success",
                    "message": "MAA 更新执行成功",
                    "data": {
                        "has_update": True,
                        "package": update_package,
                        "updated": True,
                    }
                }
            else:
                return {
                    "status": "error",
                    "message": "MAA 更新执行失败",
                    "data": {
                        "has_update": True,
                        "package": update_package,
                        "updated": False,
                    }
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"检查/执行更新失败: {str(e)}",
                "data": {}
            }

    # ==================== 配置备份还原 ====================

    async def backup_config(self, backup_name: str = "default") -> Dict[str, Any]:
        """备份 MAA 配置"""
        try:
            config_dir = get_maa_config_dir()
            if not config_dir or not config_dir.exists():
                return {
                    "status": "error",
                    "message": "MAA 配置目录不存在",
                    "data": {}
                }

            backup_dir = self._backup_base_dir / backup_name
            backup_config_dir(config_dir, backup_dir)

            return {
                "status": "success",
                "message": f"配置备份成功: {backup_name}",
                "data": {
                    "backup_name": backup_name,
                    "backup_path": str(backup_dir),
                }
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"备份配置失败: {str(e)}",
                "data": {}
            }

    async def restore_config(self, backup_name: str = "default") -> Dict[str, Any]:
        """从备份还原 MAA 配置"""
        try:
            config_dir = get_maa_config_dir()
            if not config_dir or not config_dir.exists():
                return {
                    "status": "error",
                    "message": "MAA 配置目录不存在",
                    "data": {}
                }

            backup_dir = self._backup_base_dir / backup_name
            if not backup_dir.exists():
                return {
                    "status": "error",
                    "message": f"备份不存在: {backup_name}",
                    "data": {}
                }

            restore_config_dir(config_dir, backup_dir, remove_backup=False)

            return {
                "status": "success",
                "message": f"配置还原成功: {backup_name}",
                "data": {
                    "backup_name": backup_name,
                    "backup_path": str(backup_dir),
                }
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"还原配置失败: {str(e)}",
                "data": {}
            }

    # ==================== 信息查询 ====================

    async def list_available_tasks(self) -> Dict[str, Any]:
        """列出所有可用的任务类型"""
        try:
            tasks_info = []
            for en_task, zh_task in zip(MAA_TASKS, MAA_TASKS_ZH):
                tasks_info.append({
                    "task_type": en_task,
                    "display_name": zh_task,
                })

            return {
                "status": "success",
                "message": "任务列表获取成功",
                "data": {
                    "tasks": tasks_info,
                    "fight_modes": [
                        {"value": "Routine", "name": "常规刷关"},
                        {"value": "Annihilation", "name": "剿灭作战"},
                    ],
                    "client_types": [
                        {"value": "Official", "name": "官服"},
                        {"value": "Bilibili", "name": "B服"},
                        {"value": "YoStarEN", "name": "国际服英文"},
                        {"value": "YoStarJP", "name": "日服"},
                        {"value": "YoStarKR", "name": "韩服"},
                        {"value": "txwy", "name": "繁中服"},
                    ],
                    "infrast_modes": [
                        {"value": "Normal", "name": "普通模式"},
                        {"value": "Custom", "name": "自定义模式"},
                    ],
                    "post_actions": [
                        {"value": "NoAction", "name": "无动作"},
                        {"value": "ExitGame", "name": "退出游戏"},
                        {"value": "ExitEmulator", "name": "退出模拟器"},
                    ],
                }
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"获取任务列表失败: {str(e)}",
                "data": {}
            }

    async def get_task_history(self, limit: int = 10) -> Dict[str, Any]:
        """获取任务历史记录"""
        try:
            history = self._task_history.get_history(limit)

            return {
                "status": "success",
                "message": "任务历史获取成功",
                "data": {
                    "history": history,
                    "total": len(history),
                }
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"获取任务历史失败: {str(e)}",
                "data": {}
            }

    # ==================== 内部辅助方法 ====================

    def _prepare_config(
        self,
        config_dir: Path,
        tasks: Dict[str, bool],
        fight_mode: str,
        medicine_count: int,
        stone_count: int,
        series: int,
        stage: str,
        stage_1: str,
        stage_2: str,
        stage_3: str,
        remain_stage: str,
        client_type: str,
        account_name: str,
        annihilation_stage: str,
        infrast_mode: str,
        custom_infrast_path: Optional[str],
        custom_infrast_plan_index: int,
        post_action: str,
        connect_address: Optional[str],
    ):
        """准备 MAA 配置"""
        # 加载配置
        gui_set, gui_new_set = load_maa_config(config_dir)

        # 确保使用 Default 配置
        ensure_default_config(gui_set, gui_new_set)

        # 应用全局运行选项
        apply_global_run_options(
            gui_set,
            run_directly=True,
            open_emulator_after_launch=False,
            minimize_directly=True,
            disable_timers=True,
            disable_update_check=True,
        )

        # 设置连接地址
        addr = connect_address or get_saved_connect_address() or ""
        if addr:
            set_config_connect_address(gui_set, addr)

        # 设置客户端和账号
        set_client_and_account(
            gui_set,
            gui_new_set,
            client_type=client_type,
            account_name=account_name,
        )

        # 设置任务后动作
        set_post_actions(gui_set, post_action)

        # 构建任务队列
        plan_data = {
            "MedicineNumb": medicine_count,
            "SeriesNumb": series,
            "Stage": stage or "-",
            "Stage_1": stage_1 or "-",
            "Stage_2": stage_2 or "-",
            "Stage_3": stage_3 or "-",
            "Stage_Remain": remain_stage or "-",
        }

        task_enabled = {task: tasks.get(task, False) for task in MAA_TASKS}

        build_task_queue_from_tasks(
            gui_new_set,
            task_enabled,
            fight_mode=fight_mode,
            plan_data=plan_data,
            server=client_type,
            account_name=account_name,
            annihilation_stage=annihilation_stage,
            infrast_mode=infrast_mode,
            custom_infrast_path=custom_infrast_path,
            custom_infrast_plan_index=custom_infrast_plan_index,
            add_remain_fight=bool(remain_stage),
            remain_stage=remain_stage,
        )

        # 保存配置
        save_maa_config(config_dir, gui_set, gui_new_set)
