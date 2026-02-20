"""增强的日志监控器 - 实时日志文件监控与解析。"""

import asyncio
import aiofiles
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Callable, List, Optional, Awaitable
from contextlib import suppress


# ANSI转义序列正则表达式
ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# 时间格式字段映射
TIME_FIELDS = {
    '%Y': 'year',
    '%m': 'month',
    '%d': 'day',
    '%H': 'hour',
    '%M': 'minute',
    '%S': 'second',
    '%f': 'microsecond',
}


def strptime_partial(date_string: str, format_str: str, default_date: datetime) -> datetime:
    """
    根据指定格式解析日期字符串，未指定的字段使用默认值

    Args:
        date_string: 日期字符串
        format_str: 格式字符串
        default_date: 默认日期（用于填充未指定的字段）

    Returns:
        解析后的datetime对象
    """
    parsed = datetime.strptime(date_string, format_str)

    # 构建参数字典
    datetime_kwargs = {}
    for format_code, field_name in TIME_FIELDS.items():
        if format_code in format_str:
            datetime_kwargs[field_name] = getattr(parsed, field_name)
        else:
            datetime_kwargs[field_name] = getattr(default_date, field_name)

    return datetime(**datetime_kwargs)


class EnhancedLogMonitor:
    """
    增强的日志监控器

    特性：
    1. 实时监控日志文件或进程输出
    2. 时间戳解析和日志过滤
    3. 异步回调机制
    4. 超时检测
    5. 日志变化检测
    """

    def __init__(
        self,
        time_range: tuple[int, int],
        time_format: str,
        callback: Callable[[List[str], datetime], Awaitable[None]],
        except_logs: Optional[List[str]] = None,
    ):
        """
        Args:
            time_range: 时间戳在日志行中的位置范围 (start, end)
            time_format: 时间格式字符串
            callback: 回调函数，接收 (日志列表, 最新时间戳)
            except_logs: 排除的日志行（不更新时间戳）
        """
        self.time_start = time_range[0]
        self.time_end = time_range[1]
        self.time_format = time_format
        self.callback = callback
        self.except_logs = except_logs or []

        self.last_callback_time: datetime = datetime.now()
        self.log_contents: List[str] = []
        self.latest_time: datetime = datetime.now()
        self.last_log: str = ""
        self.task: Optional[asyncio.Task] = None

    async def _monitor_file(self, log_file_path: Path, log_start_time: datetime):
        """监控日志文件的主循环"""

        await self._update_latest_timestamp("", init=True)

        file_checked = False
        log_started = False
        offset = 0
        log_contents: List[str] = []

        while True:
            # 检查文件是否存在
            if not log_file_path.exists():
                await self._do_callback()
                await asyncio.sleep(1)
                continue

            # 检查文件修改时间
            if not file_checked:
                file_stat = log_file_path.stat()
                if datetime.fromtimestamp(file_stat.st_mtime).date() == datetime.now().date():
                    file_checked = True
                else:
                    await self._do_callback()
                    await asyncio.sleep(1)
                    continue

            # 检查文件是否被重置或替换
            try:
                current_stat = log_file_path.stat()
                if (file_stat.st_ino != current_stat.st_ino or
                    file_stat.st_size > current_stat.st_size):
                    offset = 0
                    log_contents = []
                    log_started = False

                file_stat = current_stat

                # 文件大小未变化
                if file_stat.st_size <= offset:
                    # 超时调用回调
                    if datetime.now() - self.last_callback_time > timedelta(minutes=1):
                        await self._do_callback()
                    await asyncio.sleep(1)
                    continue

                # 读取新日志
                async with aiofiles.open(log_file_path, 'rb') as f:
                    await f.seek(offset)
                    async for bline in f:
                        offset = await f.tell()
                        line = bline.decode('utf-8', errors='ignore')

                        # 查找日志起始点
                        if not log_started:
                            with suppress(IndexError, ValueError):
                                entry_time = strptime_partial(
                                    line[self.time_start:self.time_end],
                                    self.time_format,
                                    self.last_callback_time,
                                )
                                if entry_time > log_start_time:
                                    log_started = True
                                    log_contents.append(line)
                                    await self._update_latest_timestamp(line)
                        else:
                            log_contents.append(line)
                            await self._update_latest_timestamp(line)

            except (FileNotFoundError, PermissionError):
                await asyncio.sleep(5)
                continue

            # 日志变化时调用回调
            if len(log_contents) != len(self.log_contents):
                self.log_contents = log_contents.copy()
                await self._do_callback()

            await asyncio.sleep(1)

    async def _monitor_process(self, process: asyncio.subprocess.Process):
        """监控进程输出的主循环"""

        await self._update_latest_timestamp("", init=True)

        if process.stdout is None:
            raise ValueError("进程没有标准输出")

        self.log_contents = []

        while True:
            try:
                bline = await asyncio.wait_for(process.stdout.readline(), timeout=60)
            except asyncio.TimeoutError:
                await self._do_callback()
                continue

            if not bline:  # EOF
                break

            line = ANSI_ESCAPE_RE.sub('', bline.decode('utf-8', errors='ignore'))
            self.log_contents.append(line)
            await self._update_latest_timestamp(line)

            # 定期回调
            if datetime.now() - self.last_callback_time > timedelta(seconds=0.1):
                await self._do_callback()

    async def _do_callback(self):
        """安全调用回调函数"""
        self.last_callback_time = datetime.now()
        try:
            await self.callback(self.log_contents, self.latest_time)
        except Exception as e:
            # 静默处理回调异常，避免中断监控
            pass

    async def _update_latest_timestamp(self, log: str, init: bool = False) -> None:
        """更新最新时间戳"""
        if init:
            self.last_log = log
            self.latest_time = datetime.now()
            return

        # 跳过排除的日志
        if any(excl in log for excl in self.except_logs):
            return

        with suppress(IndexError, ValueError):
            log_text = log[:self.time_start] + log[self.time_end:]
            if log_text != self.last_log:
                self.latest_time = strptime_partial(
                    log[self.time_start:self.time_end],
                    self.time_format,
                    self.last_callback_time,
                )
                self.last_log = log_text

    async def start_monitor_file(self, log_file_path: Path, start_time: datetime) -> None:
        """
        开始监控日志文件

        Args:
            log_file_path: 日志文件路径
            start_time: 日志起始时间（只处理此时间之后的日志）
        """
        if log_file_path.is_dir():
            raise ValueError(f"日志路径不能是目录: {log_file_path}")

        if self.task is not None and not self.task.done():
            await self.stop()

        self.task = asyncio.create_task(self._monitor_file(log_file_path, start_time))

    async def start_monitor_process(self, process: asyncio.subprocess.Process) -> None:
        """
        开始监控进程输出

        Args:
            process: 进程对象
        """
        if self.task is not None and not self.task.done():
            await self.stop()

        self.task = asyncio.create_task(self._monitor_process(process))

    async def stop(self):
        """停止监控"""
        if self.task is not None and not self.task.done():
            self.task.cancel()

            try:
                await self.task
            except asyncio.CancelledError:
                pass

        self.task = None

    def get_logs(self) -> List[str]:
        """获取当前日志内容"""
        return self.log_contents.copy()

    def get_latest_time(self) -> datetime:
        """获取最新时间戳"""
        return self.latest_time
