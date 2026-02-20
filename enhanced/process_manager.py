"""增强的进程管理器 - 异步进程启动/监控/终止。"""

import asyncio
import psutil
from pathlib import Path
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List


@dataclass
class ProcessInfo:
    """进程信息"""
    pid: Optional[int] = None
    name: Optional[str] = None
    exe: Optional[str] = None
    cmdline: Optional[List[str]] = None


@dataclass
class ProcessResult:
    """进程执行结果"""
    stdout: str
    stderr: str
    returncode: int


def match_process(proc: psutil.Process, target: ProcessInfo) -> bool:
    """检查进程是否匹配目标"""
    try:
        if target.pid is not None and proc.pid != target.pid:
            return False
        if target.name is not None and proc.name() != target.name:
            return False
        if target.exe is not None and Path(proc.exe()) != Path(target.exe):
            return False
        if target.cmdline is not None and proc.cmdline() != target.cmdline:
            return False
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False
    return True


class EnhancedProcessManager:
    """
    增强的进程管理器

    特性：
    1. 异步进程启动和监控
    2. 目标进程跟踪（支持多级派生进程）
    3. 优雅终止（terminate → kill）
    4. 进程存活检测
    """

    def __init__(self):
        self.process: Optional[asyncio.subprocess.Process] = None
        self.target_process: Optional[psutil.Process] = None
        self._creation_flags = 0x08000000  # CREATE_NO_WINDOW on Windows

    @property
    def main_pid(self) -> Optional[int]:
        """主进程的PID"""
        if self.target_process is not None:
            return self.target_process.pid
        if self.process is not None:
            return self.process.pid
        return None

    async def open_process(
        self,
        program: Path | str,
        *args: str,
        cwd: Optional[Path] = None,
        target_process: Optional[ProcessInfo] = None,
        capture_output: bool = False,
        force: bool = False,
    ) -> None:
        """
        启动进程

        Args:
            program: 可执行文件路径
            *args: 启动参数
            cwd: 工作目录
            target_process: 目标进程信息（用于多级派生进程跟踪）
            capture_output: 是否捕获输出
            force: 如果已有进程在运行，是否强制终止后再启动
        """
        if await self.is_running():
            if force:
                await self.kill(force=True)
                await asyncio.sleep(1)
            else:
                raise RuntimeError("无法同时管理多个进程")

        if target_process is not None:
            if all(x is None for x in [target_process.pid, target_process.name,
                                       target_process.exe, target_process.cmdline]):
                raise ValueError("目标进程信息不完整")

        await self.clear()

        # 启动进程
        self.process = await asyncio.create_subprocess_exec(
            program,
            *args,
            cwd=cwd or (Path(program).parent if Path(program).is_file() else None),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE if capture_output else asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.STDOUT if capture_output else asyncio.subprocess.DEVNULL,
            creationflags=self._creation_flags,
        )

        # 如果指定了目标进程，则搜索
        if target_process is not None:
            await self._search_process(target_process, datetime.now() + timedelta(seconds=60))

    async def _search_process(self, target: ProcessInfo, deadline: datetime) -> None:
        """搜索目标进程"""
        while datetime.now() < deadline:
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
                try:
                    if match_process(proc, target):
                        self.target_process = proc
                        return
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            await asyncio.sleep(0.1)
        raise RuntimeError("未能在限定时间内找到目标进程")

    async def is_running(self) -> bool:
        """检查进程是否在运行"""
        if self.target_process is not None:
            return self.target_process.is_running()
        if self.process is not None:
            return self.process.returncode is None
        return False

    async def kill(self, force: bool = False) -> None:
        """
        终止进程

        Args:
            force: 是否强制终止
        """
        # 终止目标进程
        if self.target_process is not None and self.target_process.is_running():
            with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                if force:
                    self.target_process.kill()
                else:
                    self.target_process.terminate()
                    try:
                        await asyncio.get_running_loop().run_in_executor(
                            None, self.target_process.wait, 3
                        )
                    except psutil.TimeoutExpired:
                        self.target_process.kill()
                        with suppress(psutil.TimeoutExpired):
                            await asyncio.get_running_loop().run_in_executor(
                                None, self.target_process.wait, 3
                            )

        # 终止子进程
        if self.process is not None and self.process.returncode is None:
            with suppress(ProcessLookupError):
                if force:
                    self.process.kill()
                else:
                    self.process.terminate()
                    try:
                        await asyncio.wait_for(self.process.wait(), timeout=3)
                    except asyncio.TimeoutError:
                        self.process.kill()
                        with suppress(asyncio.TimeoutError):
                            await asyncio.wait_for(self.process.wait(), timeout=3)

        await self.clear()

    async def clear(self) -> None:
        """清空进程信息"""
        self.process = None
        self.target_process = None

    async def wait(self, timeout: Optional[float] = None) -> int:
        """
        等待进程结束

        Returns:
            进程退出码
        """
        if self.process is None:
            raise RuntimeError("没有正在运行的进程")

        if timeout is not None:
            return await asyncio.wait_for(self.process.wait(), timeout=timeout)
        return await self.process.wait()


class ProcessRunner:
    """进程运行器 - 用于运行一次性进程"""

    @staticmethod
    async def run(
        program: Path | str,
        *args: str,
        cwd: Optional[Path] = None,
        timeout: float = 60,
        merge_stderr: bool = False,
    ) -> ProcessResult:
        """
        运行进程并获取结果

        Args:
            program: 可执行文件路径
            *args: 启动参数
            cwd: 工作目录
            timeout: 超时时间（秒）
            merge_stderr: 是否合并stderr到stdout

        Returns:
            ProcessResult: 进程执行结果
        """
        process = await asyncio.create_subprocess_exec(
            program,
            *args,
            cwd=cwd or (Path(program).parent if Path(program).is_file() else None),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT if merge_stderr else asyncio.subprocess.PIPE,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            with suppress(ProcessLookupError):
                process.kill()
            await process.wait()
            raise

        return ProcessResult(
            stdout=stdout.decode('utf-8', errors='ignore') if stdout else '',
            stderr=stderr.decode('utf-8', errors='ignore') if stderr else '',
            returncode=process.returncode if process.returncode is not None else await process.wait(),
        )
