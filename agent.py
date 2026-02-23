"""MAA 自动化控制 Agent v5.1 - 两步确认工作流

移除对 agent_comms / maa_comms 的外部依赖，所有功能整合到内部模块。
新增: ADB 自动发现、模拟器自动启动、通知推送、定时调度、多脚本管理。
v5.1: 新增 get_task_catalog / start_emulator，参数持久化，两步确认流程。
"""

from __future__ import annotations

import json
import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path

from .core.config import MAAConfig
from .core.task_presets import get_preset, list_presets, merge_preset_with_params
from .core.task_param_schemas import get_task_catalog

from .enhanced.emulator_manager import EmulatorManager, DeviceStatus
from .enhanced.executor import EnhancedMAAExecutor, MAATaskConfig, MAAExecutionResult
from .enhanced.adb_discovery import AdbDiscovery
from .enhanced.notification import TaskNotifier
from .enhanced.scheduler import TaskScheduler
from .enhanced.script_profiles import ScriptProfileManager
from .enhanced.process_manager import EnhancedProcessManager

logger = logging.getLogger(__name__)


class MAAAgent:
    """MAA 控制 Agent v5.1 - 7 个 MCP 工具，两步确认工作流"""

    name = "MAA Control Agent v5.1"

    def __init__(self) -> None:
        # 核心配置
        self.config = MAAConfig()

        # 通知
        self.notifier = TaskNotifier(
            callback_url=self.config.get_callback_url(),
            session_id="maa_agent",
        )

        # ADB 发现
        self.adb_discovery = AdbDiscovery()

        # 模拟器管理
        self.emulator_manager = EmulatorManager()
        self.emulator_manager.load_from_config(self.config.get_emulator_profiles())

        # 脚本配置管理
        self.script_manager = ScriptProfileManager(self.config)

        # 进程管理（用于 stop_task）
        self._process_manager = EnhancedProcessManager()

        # 当前执行器引用
        self._current_executor: Optional[EnhancedMAAExecutor] = None

        # 定时调度器
        self.scheduler = TaskScheduler(
            get_schedules=self.config.get_schedules,
            save_schedule=self.config.set_schedule,
            execute_callback=self._scheduled_execute,
        )
        # 启动调度器（延迟到事件循环可用时）
        self._scheduler_started = False

    def _ensure_scheduler(self) -> None:
        """确保调度器已启动"""
        if not self._scheduler_started:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.scheduler.start())
                self._scheduler_started = True
            except RuntimeError:
                pass

    async def handle_handoff(self, task: dict[str, Any]) -> str:
        """处理工具调用请求"""
        self._ensure_scheduler()

        try:
            tool_name = str(task.get("tool_name") or "").strip()
            if not tool_name:
                return json.dumps({
                    "status": "error",
                    "message": "缺少 tool_name 参数",
                    "data": {},
                }, ensure_ascii=False)

            if tool_name == "execute_task":
                data = await self._execute_task(task)
            elif tool_name == "configure_maa":
                data = await self._configure_maa(task)
            elif tool_name == "get_status":
                data = await self._get_status()
            elif tool_name == "stop_task":
                data = await self._stop_task()
            elif tool_name == "list_presets":
                data = self._list_presets()
            elif tool_name == "get_task_catalog":
                data = self._get_task_catalog()
            elif tool_name == "start_emulator":
                data = await self._start_emulator(task)
            else:
                return json.dumps({
                    "status": "error",
                    "message": f"未知工具: {tool_name}。可用: execute_task, configure_maa, get_status, stop_task, list_presets, get_task_catalog, start_emulator",
                    "data": {},
                }, ensure_ascii=False)

            return json.dumps(data, ensure_ascii=False, default=str)

        except Exception as exc:
            return json.dumps({
                "status": "error",
                "message": f"处理请求时发生错误: {str(exc)}",
                "data": {},
            }, ensure_ascii=False)

    # ================================================================
    # 工具 1: execute_task
    # ================================================================

    async def _execute_task(self, task: dict[str, Any]) -> Dict[str, Any]:
        """
        执行 MAA 任务

        支持:
        1. 预设: {"preset": "daily_full"} 或 {"preset": "收基建"}
        2. 脚本配置: {"script_profile": "main_account"}
        3. 自定义: {"tasks": {...}, "stage": "1-7", ...}
        4. 队列: {"queue": ["profile1", "profile2"]}
        """
        # 检查配置
        config_check = self._check_configuration()
        if config_check["status"] == "error":
            return config_check

        maa_path = Path(self.config.get_maa_path())

        # === 队列模式 ===
        queue = task.get("queue")
        if queue and isinstance(queue, list):
            return await self._execute_queue(queue, maa_path)

        # === 预检查: 提供具体的错误信息 ===
        preset_name = task.get("preset")
        if preset_name and not get_preset(preset_name):
            available = list_presets()
            return {
                "status": "error",
                "message": f"预设 '{preset_name}' 不存在",
                "data": {
                    "available_presets": available,
                    "hint": "可使用中文别名，如 '收基建'、'日常'、'刷龙门币'",
                },
            }

        profile_id = task.get("script_profile")
        if profile_id and self.script_manager.build_task_params(profile_id) is None:
            available = self.script_manager.list_profiles()
            return {
                "status": "error",
                "message": f"脚本配置 '{profile_id}' 不存在",
                "data": {
                    "available_profiles": list(available.keys()),
                    "hint": "使用 configure_maa 的 script_profiles 参数创建配置",
                },
            }

        # === 解析任务参数 ===
        task_params = await self._resolve_task_params(task)
        if task_params is None:
            return {
                "status": "error",
                "message": "请指定 preset / script_profile / tasks 之一",
                "data": {
                    "examples": [
                        {"preset": "daily_full"},
                        {"preset": "收基建"},
                        {"script_profile": "main_account"},
                        {"tasks": {"StartUp": True, "Infrast": True}},
                    ]
                },
            }

        # === 执行单个任务 ===
        return await self._execute_single(task_params, maa_path)

    async def _resolve_task_params(self, task: dict) -> Optional[Dict[str, Any]]:
        """从工具调用中解析出任务参数"""
        # 1. 脚本配置模式
        profile_id = task.get("script_profile")
        if profile_id:
            params = self.script_manager.build_task_params(profile_id)
            if params is None:
                return None
            # 合并额外参数
            extra = {k: v for k, v in task.items()
                     if k not in ("tool_name", "script_profile")}
            if extra:
                params.update(extra)
            return params

        # 2. 预设模式
        preset_name = task.get("preset")
        if preset_name:
            preset = get_preset(preset_name)
            if not preset:
                return None
            task_config = {k: v for k, v in preset.items()
                          if k not in ("name", "description")}
            custom = {k: v for k, v in task.items()
                      if k not in ("preset", "tool_name")}
            if custom:
                task_config = merge_preset_with_params(task_config, custom)
            return task_config

        # 3. 自定义模式（显式指定 tasks 字典）
        if "tasks" in task:
            return {k: v for k, v in task.items() if k != "tool_name"}

        # 4. 自动推断模式 — 根据参数前缀推断需启用的任务
        #    例如 AI 只传 {"roguelike_core_char": "棘刺"} 即可，无需手写 tasks
        task_params = {k: v for k, v in task.items() if k != "tool_name"}
        inferred = MAATaskConfig.infer_tasks(task_params)
        if len(inferred) > 1:  # 推断出了 StartUp 以外的任务
            task_params["tasks"] = inferred
            return task_params

        return None

    async def _execute_single(
        self, params: Dict[str, Any], maa_path: Path
    ) -> Dict[str, Any]:
        """执行单个 MAA 任务"""
        # ADB 地址解析
        connect_address = params.get("connect_address") or self.config.get_connect_address()

        # 模拟器配置
        emulator_id = None
        emulator_index = None
        emu_profile_id = params.get("emulator_profile")

        if emu_profile_id:
            emu_profile = self.config.get_emulator_profile(emu_profile_id)
            if emu_profile:
                emulator_id = emu_profile_id
                emulator_index = emu_profile.get("index", "0")
                # 重新加载模拟器管理器（确保最新配置）
                if emu_profile_id not in self.emulator_manager.emulators:
                    self.emulator_manager.load_from_config(
                        {emu_profile_id: emu_profile}
                    )

        # ADB 自动发现（如无连接地址且无模拟器配置）
        if not connect_address and not emulator_id:
            self.notifier.notify_status("正在自动发现模拟器...", auto_hide_ms=5000)
            discovered = self.adb_discovery.discover()
            if discovered:
                dev = discovered[0]
                if dev.serial != "not_running" and dev.serial != "Unknown":
                    # 模拟器正在运行，直接使用 ADB 地址
                    connect_address = dev.serial
                    logger.info(f"自动发现 ADB 设备: {connect_address}")
                    self.notifier.notify_status(
                        f"已发现设备: {connect_address}", auto_hide_ms=3000,
                    )
                elif dev.emulator_path and dev.emulator_type in (
                    "mumu", "ldplayer", "bluestacks", "nox",
                ):
                    # 发现了模拟器安装但未运行，自动注册并启动
                    emu_type = dev.emulator_type
                    logger.info(f"发现 {emu_type} 安装（未运行）: {dev.emulator_path}")
                    auto_id = f"_auto_{emu_type}"
                    self.config.set_emulator_profile(auto_id, {
                        "type": emu_type,
                        "path": dev.emulator_path,
                        "index": dev.index,
                        "adb_path": dev.adb_path,
                    })
                    self.emulator_manager.load_from_config(
                        {auto_id: self.config.get_emulator_profile(auto_id)}
                    )
                    emulator_id = auto_id
                    emulator_index = dev.index
                    self.notifier.notify_status(
                        f"发现 {emu_type} 模拟器（未运行），将自动启动...",
                        auto_hide_ms=5000,
                    )

        # 回退：自动发现也找不到设备时，使用已配置的第一个模拟器
        if not connect_address and not emulator_id:
            profiles = self.config.get_emulator_profiles()
            if profiles:
                fallback_id = next(iter(profiles))
                fallback = profiles[fallback_id]
                logger.info(f"自动发现未找到设备，使用已配置模拟器: {fallback_id}")
                emulator_id = fallback_id
                emulator_index = fallback.get("index", "0")
                if fallback_id not in self.emulator_manager.emulators:
                    self.emulator_manager.load_from_config({fallback_id: fallback})
                self.notifier.notify_status(
                    f"使用已配置模拟器 {fallback_id}，自动启动...",
                    auto_hide_ms=5000,
                )

        # 构建 MAATaskConfig
        # 1) 获取显式 tasks，再用参数前缀补充推断（确保传了参数就启用对应任务）
        tasks = params.get("tasks", {"StartUp": True})
        inferred = MAATaskConfig.infer_tasks(params)
        for task_type, enabled in inferred.items():
            if enabled:
                tasks.setdefault(task_type, True)

        # 2) 批量构造 — 利用 dataclass 自省，新增字段只需改 MAATaskConfig，此处零改动
        task_config = MAATaskConfig.from_params(
            maa_path=maa_path,
            tasks=tasks,
            params=params,
            emulator_id=emulator_id,
            emulator_index=emulator_index,
            connect_address=connect_address,
        )

        # 创建执行器
        self._current_executor = EnhancedMAAExecutor(
            config=task_config,
            emulator_manager=self.emulator_manager if emulator_id else None,
            notifier=self.notifier,
        )

        # 执行
        try:
            result = await self._current_executor.execute()
        finally:
            self._current_executor = None
            # 确保前端通知被清理
            self.notifier.hide_status()

        # 执行成功后保存本次参数到 last_params
        if result.status == "success":
            self._save_last_params(tasks, params)

        # 构建对 AI 友好的结构化返回
        completed_str = ", ".join(result.tasks_completed) if result.tasks_completed else "无"
        failed_str = ", ".join(result.tasks_failed) if result.tasks_failed else "无"
        duration_str = f"{result.duration:.0f}秒"

        if result.status == "success":
            message = (
                f"任务已成功完成，耗时 {duration_str}。"
                f"完成的任务: {completed_str}。"
            )
            if result.restart_count > 0:
                message += f"（过程中自动重启了 {result.restart_count} 次）"
        elif result.status == "timeout":
            message = (
                f"任务执行超时（已运行 {duration_str}），已自动终止 MAA。"
                f"已完成: {completed_str}；未完成: {failed_str}。"
                f"如果是长时间任务（如肉鸽），可以考虑增加 timeout_minutes 参数。"
            )
        elif result.status == "failed":
            message = (
                f"任务执行失败: {result.message}。"
                f"已完成: {completed_str}；未完成: {failed_str}。"
                f"建议: 检查模拟器连接状态后重试。"
            )
        else:
            message = (
                f"任务出错: {result.message}。"
                f"已完成: {completed_str}；未完成: {failed_str}。"
            )

        # 附加执行过程记录，让 AI 能了解任务执行细节
        if result.execution_events:
            events_text = "\n".join(f"  - {e}" for e in result.execution_events)
            message += f"\n\n执行过程记录:\n{events_text}"

        return {
            "status": result.status,
            "message": message,
            "data": {
                "duration": f"{result.duration:.1f}s",
                "tasks_completed": result.tasks_completed,
                "tasks_failed": result.tasks_failed,
                "restart_count": result.restart_count,
                "log_lines": len(result.logs),
                "execution_events": result.execution_events,
            },
        }

    async def _execute_queue(
        self, profile_ids: List[str], maa_path: Path
    ) -> Dict[str, Any]:
        """顺序执行多个脚本配置"""
        results = []
        for pid in profile_ids:
            params = self.script_manager.build_task_params(pid)
            if params is None:
                results.append({"profile": pid, "status": "error", "message": "配置不存在"})
                continue

            self.notifier.notify_status(f"正在执行配置: {pid}")
            r = await self._execute_single(params, maa_path)
            results.append({"profile": pid, **r})

        succeeded = [r["profile"] for r in results if r.get("status") == "success"]
        failed = [r["profile"] for r in results if r.get("status") != "success"]
        all_ok = len(failed) == 0

        if all_ok:
            message = f"队列全部执行成功，共 {len(results)} 个配置: {', '.join(succeeded)}。"
        else:
            message = (
                f"队列执行完成（{len(results)} 个配置），"
                f"成功: {', '.join(succeeded) if succeeded else '无'}；"
                f"失败: {', '.join(failed)}。"
            )

        return {
            "status": "success" if all_ok else "error",
            "message": message,
            "data": {"results": results},
        }

    async def _scheduled_execute(self, profile_id: str) -> None:
        """定时调度器触发的执行回调"""
        logger.info(f"定时任务触发: {profile_id}")
        self.notifier.notify_status(f"定时任务触发: {profile_id}")

        maa_path_str = self.config.get_maa_path()
        if not maa_path_str:
            logger.error("定时任务执行失败: MAA 路径未配置")
            return

        params = self.script_manager.build_task_params(profile_id)
        if params is None:
            logger.error(f"定时任务执行失败: 脚本配置 {profile_id} 不存在")
            return

        try:
            await self._execute_single(params, Path(maa_path_str))
        except Exception as e:
            logger.error(f"定时任务执行异常: {e}")

    # ================================================================
    # 工具 2: configure_maa
    # ================================================================

    async def _configure_maa(self, task: dict[str, Any]) -> Dict[str, Any]:
        """配置 MAA"""
        results = []

        # MAA 路径
        if "maa_path" in task:
            path = task["maa_path"]
            valid, msg = self.config.validate_maa_path(path)
            if valid:
                self.config.set_maa_path(path)
                results.append({"item": "maa_path", "status": "success", "message": f"MAA 路径已设置: {path}"})
            else:
                results.append({"item": "maa_path", "status": "error", "message": msg})

        # 连接地址
        if "connect_address" in task:
            addr = task["connect_address"]
            self.config.set_connect_address(addr)
            results.append({"item": "connect_address", "status": "success", "message": f"连接地址已设置: {addr}"})

        # 通知回调地址
        if "callback_url" in task:
            url = task["callback_url"]
            self.config.set_callback_url(url)
            self.notifier.callback_url = url
            results.append({"item": "callback_url", "status": "success", "message": f"回调地址已设置: {url}"})

        # 模拟器配置
        if "emulator_profiles" in task:
            profiles = task["emulator_profiles"]
            if isinstance(profiles, dict):
                self.config.set_emulator_profiles(profiles)
                self.emulator_manager.load_from_config(profiles)
                results.append({"item": "emulator_profiles", "status": "success",
                                "message": f"已配置 {len(profiles)} 个模拟器"})

        # 脚本配置
        if "script_profiles" in task:
            profiles = task["script_profiles"]
            if isinstance(profiles, dict):
                self.config.set_script_profiles(profiles)
                results.append({"item": "script_profiles", "status": "success",
                                "message": f"已配置 {len(profiles)} 个脚本"})

        # 定时任务
        if "schedules" in task:
            schedules = task["schedules"]
            if isinstance(schedules, dict):
                self.config.set_schedules(schedules)
                results.append({"item": "schedules", "status": "success",
                                "message": f"已配置 {len(schedules)} 个定时任务"})

        if not results:
            return {
                "status": "error",
                "message": "请提供至少一个配置项",
                "data": {
                    "supported": [
                        "maa_path", "connect_address", "callback_url",
                        "emulator_profiles", "script_profiles", "schedules",
                    ],
                    "example": {
                        "maa_path": r"D:\MaaAssistantArknights",
                        "connect_address": "127.0.0.1:16384",
                    },
                },
            }

        success_items = [r for r in results if r["status"] == "success"]
        failed_items = [r for r in results if r["status"] != "success"]

        if failed_items and not success_items:
            # 全部失败
            status = "error"
            summary = "配置失败: " + "; ".join(r["message"] for r in failed_items)
        elif failed_items:
            # 部分成功部分失败 — 仍标记为 success，在 message 中说明哪些失败
            status = "success"
            summary = (
                "配置部分完成。成功: " + "; ".join(r["message"] for r in success_items) +
                "。失败: " + "; ".join(r["message"] for r in failed_items)
            )
        else:
            # 全部成功
            status = "success"
            summary = "配置已全部成功完成。" + "; ".join(r["message"] for r in results)

        return {
            "status": status,
            "message": summary,
            "data": {
                "results": results,
                "current_config": {
                    "maa_path": self.config.get_maa_path(),
                    "connect_address": self.config.get_connect_address(),
                    "callback_url": self.config.get_callback_url(),
                    "emulator_profiles": list(self.config.get_emulator_profiles().keys()),
                    "script_profiles": list(self.config.get_script_profiles().keys()),
                    "schedules": list(self.config.get_schedules().keys()),
                },
            },
        }

    # ================================================================
    # 工具 3: get_status
    # ================================================================

    async def _get_status(self) -> Dict[str, Any]:
        """获取 MAA 当前状态"""
        config_check = self._check_configuration()

        # 调度器状态
        scheduler_status = self.scheduler.get_status()

        # 脚本配置列表
        script_profiles = self.script_manager.list_profiles()

        # 已发现设备
        discovered_devices = []
        try:
            devices = self.adb_discovery.discover()
            discovered_devices = [
                {"type": d.emulator_type, "serial": d.serial, "index": d.index}
                for d in devices
            ]
        except Exception as e:
            logger.debug(f"设备发现失败: {e}")

        # 当前执行状态
        executor_status = None
        if self._current_executor:
            executor_status = {
                "running": True,
                "status": self._current_executor.current_status,
            }

        return {
            "status": "success",
            "message": "状态查询成功",
            "data": {
                "configuration": config_check["data"],
                "executor": executor_status,
                "scheduler": scheduler_status,
                "script_profiles": {
                    k: v.get("name", k) for k, v in script_profiles.items()
                } if script_profiles else {},
                "discovered_devices": discovered_devices,
                "emulator_profiles": list(self.config.get_emulator_profiles().keys()),
            },
        }

    # ================================================================
    # 工具 4: stop_task
    # ================================================================

    async def _stop_task(self) -> Dict[str, Any]:
        """停止当前 MAA 任务"""
        if self._current_executor:
            try:
                await self._current_executor.process_manager.kill()
                if self._current_executor.log_monitor:
                    await self._current_executor.log_monitor.stop()
                self._current_executor = None
                return {
                    "status": "success",
                    "message": "MAA 任务已停止",
                    "data": {},
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"停止失败: {str(e)}",
                    "data": {},
                }

        # 尝试通过进程名查找并终止
        try:
            import psutil
            for proc in psutil.process_iter(["name"]):
                if proc.info["name"] and "MAA" in proc.info["name"]:
                    proc.terminate()
                    return {
                        "status": "success",
                        "message": "已终止 MAA 进程",
                        "data": {"pid": proc.pid},
                    }
        except Exception:
            pass

        return {
            "status": "success",
            "message": "当前没有正在运行的 MAA 任务",
            "data": {},
        }

    # ================================================================
    # 工具 5: list_presets
    # ================================================================

    def _list_presets(self) -> Dict[str, Any]:
        """列出可用预设"""
        presets = list_presets()

        common_tasks = {
            "daily_full": "每日完整日常",
            "infrast_only": "仅收基建（快速）",
            "farm_lmd": "刷龙门币",
            "farm_exp": "刷经验",
            "annihilation": "每周剿灭",
        }

        return {
            "status": "success",
            "message": "可用预设任务列表",
            "data": {
                "presets": presets,
                "common_tasks": common_tasks,
                "usage": "使用 execute_task，传入 preset 参数即可执行",
                "examples": [
                    {"preset": "daily_full"},
                    {"preset": "收基建"},
                    {"preset": "farm_lmd", "medicine_count": 20},
                    {"script_profile": "main_account"},
                    {"queue": ["main_account", "sub_account"]},
                ],
            },
        }

    # ================================================================
    # 工具 6: get_task_catalog
    # ================================================================

    def _get_task_catalog(self) -> Dict[str, Any]:
        """
        获取任务目录 + 上次参数

        返回所有任务类型的参数 schema，合并 last_used 值，
        供 AI 规划阶段展示给用户确认。
        """
        last_params = self.config.get_all_last_params()
        catalog = get_task_catalog(last_params)

        # 附加可用预设列表
        presets_summary = {}
        for key, value in list_presets().items():
            presets_summary[key] = value["name"]

        return {
            "status": "success",
            "message": "任务目录",
            "data": {
                "tasks": catalog,
                "presets": presets_summary,
            },
        }

    # ================================================================
    # 工具 7: start_emulator
    # ================================================================

    async def _start_emulator(self, task: dict[str, Any]) -> Dict[str, Any]:
        """
        预启动模拟器

        AI 在规划阶段并行调用，提前启动模拟器节省等待时间。
        """
        emu_profile_id = task.get("emulator_profile", "default")

        # 查找模拟器配置
        emu_profile = self.config.get_emulator_profile(emu_profile_id)
        if not emu_profile:
            # 尝试使用第一个可用的配置
            profiles = self.config.get_emulator_profiles()
            if not profiles:
                return {
                    "status": "success",
                    "message": "未配置模拟器，执行任务时将自动发现设备，无需手动启动。",
                    "data": {"detail": "no_emulator_configured"},
                }
            emu_profile_id = next(iter(profiles))
            emu_profile = profiles[emu_profile_id]

        # 确保模拟器已注册
        if emu_profile_id not in self.emulator_manager.emulators:
            self.emulator_manager.load_from_config({emu_profile_id: emu_profile})

        index = emu_profile.get("index", "0")

        # 检查是否已在运行
        try:
            status = await self.emulator_manager.get_status(emu_profile_id, index)
            if status == DeviceStatus.ONLINE:
                adb_addr = await self.emulator_manager.emulators[emu_profile_id].get_adb_address(index)
                return {
                    "status": "success",
                    "message": f"模拟器 {emu_profile_id} 已在运行，无需重复启动。",
                    "data": {"adb_address": adb_addr, "detail": "already_running"},
                }
        except Exception:
            pass

        # 启动模拟器
        try:
            self.notifier.notify_status(f"正在启动模拟器 {emu_profile_id}...", auto_hide_ms=5000)
            info = await self.emulator_manager.start(emu_profile_id, index)
            is_ready = info.status == DeviceStatus.ONLINE
            return {
                "status": "success",
                "message": f"模拟器 {emu_profile_id} {'已就绪，可以执行任务。' if is_ready else '正在启动中，执行任务时会自动等待就绪。'}",
                "data": {"adb_address": info.adb_address, "detail": "ready" if is_ready else "starting"},
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"模拟器启动失败: {str(e)}",
                "data": {},
            }

    # ================================================================
    # 内部方法
    # ================================================================

    def _save_last_params(self, tasks: Dict[str, bool], params: Dict[str, Any]) -> None:
        """按任务类型保存本次参数到 last_params"""
        # 参数前缀到任务类型的映射
        prefix_map = {
            "Fight": ["stage", "stage_1", "stage_2", "stage_3", "remain_stage",
                       "medicine_count", "stone_count", "fight_", "annihilation_stage"],
            "Roguelike": ["roguelike_"],
            "Reclamation": ["reclamation_"],
            "Recruit": ["recruit_"],
            "Infrast": ["infrast_", "custom_infrast_"],
            "Mall": ["mall_"],
            "Award": ["award_"],
            "StartUp": ["client_type", "account_name"],
        }

        for task_type, enabled in tasks.items():
            if not enabled:
                continue
            prefixes = prefix_map.get(task_type, [])
            if not prefixes:
                continue

            task_params = {}
            for key, value in params.items():
                if key in ("tool_name", "preset", "script_profile", "queue",
                           "tasks", "emulator_profile", "post_action"):
                    continue
                for prefix in prefixes:
                    if key == prefix or key.startswith(prefix):
                        task_params[key] = value
                        break

            if task_params:
                self.config.set_last_params(task_type, task_params)

    def _check_configuration(self) -> Dict[str, Any]:
        """检查 MAA 配置是否完整"""
        errors = []
        warnings = []
        config_data = {}

        # MAA 路径
        maa_path = self.config.get_maa_path()
        if not maa_path:
            errors.append("MAA 路径未配置")
            config_data["maa_path"] = None
            config_data["maa_path_configured"] = False
        else:
            valid, msg = self.config.validate_maa_path(maa_path)
            if not valid:
                errors.append(f"MAA 路径无效: {msg}")
                config_data["maa_path"] = maa_path
                config_data["maa_path_configured"] = False
            else:
                config_data["maa_path"] = maa_path
                config_data["maa_path_configured"] = True

        # 连接地址
        connect_address = self.config.get_connect_address()
        config_data["connect_address"] = connect_address
        config_data["connect_address_configured"] = bool(connect_address)
        if not connect_address:
            warnings.append("连接地址未配置（可自动发现）")

        if errors:
            return {
                "status": "error",
                "message": "配置不完整: " + "; ".join(errors),
                "data": {
                    **config_data,
                    "errors": errors,
                    "warnings": warnings,
                    "fix_instruction": "使用 configure_maa 配置 MAA 路径",
                    "example": {
                        "tool_name": "configure_maa",
                        "maa_path": r"D:\MaaAssistantArknights",
                    },
                },
            }

        message = "配置完整"
        if warnings:
            message += " (" + "; ".join(warnings) + ")"

        return {
            "status": "success",
            "message": message,
            "data": config_data,
        }
