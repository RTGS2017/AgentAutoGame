"""无头定时调度器 - 基于 asyncio 的后台定时任务调度。"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, Optional

logger = logging.getLogger(__name__)


class TaskScheduler:
    """
    无头定时调度器

    后台 asyncio.Task 每 60 秒检查一次定时任务配置，
    匹配当前日期+时间时触发回调执行对应脚本配置。

    使用回调模式访问配置，避免直接依赖 MAAConfig。
    """

    def __init__(
        self,
        get_schedules: Callable[[], Dict[str, Any]],
        save_schedule: Callable[[str, Dict[str, Any]], None],
        execute_callback: Callable[[str], Coroutine[Any, Any, Any]],
    ):
        """
        Args:
            get_schedules: 获取所有定时任务配置的回调
            save_schedule: 保存单个定时任务配置的回调
            execute_callback: 触发执行的异步回调，参数为 script_profile ID
        """
        self._get_schedules = get_schedules
        self._save_schedule = save_schedule
        self._execute_callback = execute_callback

        self._task: Optional[asyncio.Task] = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """启动调度器"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("定时调度器已启动")

    async def stop(self) -> None:
        """停止调度器"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("定时调度器已停止")

    async def _loop(self) -> None:
        """主循环 - 每 60 秒检查一次"""
        while self._running:
            try:
                await self._check_schedules()
            except Exception as e:
                logger.error(f"调度检查异常: {e}")
            await asyncio.sleep(60)

    async def _check_schedules(self) -> None:
        """检查所有定时任务是否需要触发"""
        schedules = self._get_schedules()
        if not schedules:
            return

        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_day = now.strftime("%A")
        current_minute = now.strftime("%Y-%m-%d %H:%M")

        for schedule_id, schedule in schedules.items():
            if not schedule.get("enabled", False):
                continue

            # 避免同一分钟重复触发
            last_triggered = schedule.get("last_triggered")
            if last_triggered == current_minute:
                continue

            # 检查时间匹配
            sched_time = schedule.get("time", "")
            sched_days = schedule.get("days", [])

            if current_time != sched_time:
                continue

            if sched_days and current_day not in sched_days:
                continue

            # 触发
            profile_id = schedule.get("script_profile", "")
            if not profile_id:
                logger.warning(f"定时任务 {schedule_id} 未配置 script_profile")
                continue

            logger.info(f"定时触发: {schedule_id} -> {profile_id}")

            # 更新触发时间
            schedule["last_triggered"] = current_minute
            self._save_schedule(schedule_id, schedule)

            # 异步执行
            try:
                asyncio.create_task(self._execute_callback(profile_id))
            except Exception as e:
                logger.error(f"定时任务 {schedule_id} 执行失败: {e}")

    def get_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        schedules = self._get_schedules()

        active_schedules = []
        for sid, sched in schedules.items():
            if sched.get("enabled", False):
                active_schedules.append({
                    "id": sid,
                    "time": sched.get("time", ""),
                    "days": sched.get("days", []),
                    "profile": sched.get("script_profile", ""),
                    "last_triggered": sched.get("last_triggered"),
                })

        return {
            "running": self._running,
            "active_count": len(active_schedules),
            "schedules": active_schedules,
        }


if __name__ == "__main__":
    import json

    _schedules = {
        "morning": {
            "enabled": True,
            "script_profile": "main_account",
            "time": datetime.now().strftime("%H:%M"),
            "days": [datetime.now().strftime("%A")],
            "last_triggered": None,
        }
    }

    async def _execute(profile_id: str):
        print(f"[TEST] 执行脚本: {profile_id}")

    def _save(sid, data):
        _schedules[sid] = data
        print(f"[TEST] 保存: {sid} -> {json.dumps(data, default=str)}")

    async def _test():
        scheduler = TaskScheduler(
            get_schedules=lambda: _schedules,
            save_schedule=_save,
            execute_callback=_execute,
        )
        await scheduler.start()
        print("调度器状态:", scheduler.get_status())
        await asyncio.sleep(65)
        await scheduler.stop()

    asyncio.run(_test())
