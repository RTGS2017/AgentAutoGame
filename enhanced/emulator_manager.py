"""增强的模拟器管理器 - MuMu / LDPlayer 等命令行启停控制。"""

import json
import asyncio
import logging
from enum import IntEnum
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass

from .process_manager import ProcessRunner

logger = logging.getLogger(__name__)


# ---- 设备状态枚举 ----

class DeviceStatus(IntEnum):
    """设备状态枚举"""
    ONLINE = 0
    OFFLINE = 1
    STARTING = 2
    CLOSING = 3
    ERROR = 4
    NOT_FOUND = 5
    UNKNOWN = 10


# ---- 数据类 ----

@dataclass
class EmulatorInfo:
    """模拟器信息"""
    name: str
    index: str
    adb_address: str
    status: DeviceStatus = DeviceStatus.UNKNOWN
    pid: Optional[int] = None


# ---- 模拟器基类 ----

class BaseEmulator:
    """模拟器基类"""

    def __init__(self, manager_path: Path, adb_path: Optional[Path] = None):
        """
        Args:
            manager_path: 模拟器管理工具路径（MuMuManager.exe / dnconsole.exe）
            adb_path: ADB 可执行文件路径（可选）
        """
        self.manager_path = manager_path
        self.adb_path = adb_path

    async def start(self, index: str) -> EmulatorInfo:
        raise NotImplementedError

    async def stop(self, index: str) -> DeviceStatus:
        raise NotImplementedError

    async def get_status(self, index: str) -> DeviceStatus:
        raise NotImplementedError

    async def get_info(self, index: Optional[str] = None) -> Dict[str, EmulatorInfo]:
        raise NotImplementedError

    async def get_adb_address(self, index: str) -> str:
        raise NotImplementedError

    async def wait_ready(self, index: str, timeout: float = 120) -> bool:
        """等待模拟器就绪（ONLINE 状态）"""
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            status = await self.get_status(index)
            if status == DeviceStatus.ONLINE:
                await asyncio.sleep(3)  # 等待 ADB 服务完全就绪
                return True
            if status in (DeviceStatus.ERROR, DeviceStatus.NOT_FOUND):
                return False
            await asyncio.sleep(1)
        return False


# ---- MuMu 模拟器 ----

class MuMuEmulator(BaseEmulator):
    """
    MuMu 模拟器管理

    命令格式:
      启动: MuMuManager.exe control -v {idx} launch
      停止: MuMuManager.exe control -v {idx} shutdown
      信息: MuMuManager.exe info -v {idx}
    """

    async def start(self, index: str) -> EmulatorInfo:
        """启动 MuMu 模拟器"""
        # 检查是否已在运行
        status = await self.get_status(index)
        if status == DeviceStatus.ONLINE:
            info = await self.get_info(index)
            if index in info:
                return info[index]

        result = await ProcessRunner.run(
            self.manager_path,
            "control", "-v", index, "launch",
            timeout=60,
            merge_stderr=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"MuMu 启动失败: {result.stdout}")

        # 等待就绪并获取信息
        if await self.wait_ready(index):
            info = await self.get_info(index)
            if index in info:
                return info[index]

        adb_addr = await self.get_adb_address(index)
        return EmulatorInfo(
            name=f"MuMu-{index}",
            index=index,
            adb_address=adb_addr,
            status=DeviceStatus.STARTING,
        )

    async def stop(self, index: str) -> DeviceStatus:
        """停止 MuMu 模拟器"""
        status = await self.get_status(index)
        if status == DeviceStatus.OFFLINE:
            return DeviceStatus.OFFLINE

        result = await ProcessRunner.run(
            self.manager_path,
            "control", "-v", index, "shutdown",
            timeout=30,
            merge_stderr=True,
        )
        if result.returncode != 0:
            logger.warning(f"MuMu 停止命令失败: {result.stdout}")
            return DeviceStatus.ERROR

        # 等待关闭
        for _ in range(30):
            s = await self.get_status(index)
            if s == DeviceStatus.OFFLINE:
                return DeviceStatus.OFFLINE
            await asyncio.sleep(1)

        return await self.get_status(index)

    async def get_status(self, index: str) -> DeviceStatus:
        """获取 MuMu 模拟器状态"""
        try:
            raw = await self._get_raw_info(index)
            data = json.loads(raw)
        except Exception as e:
            logger.debug(f"MuMu 状态获取失败: {e}")
            return DeviceStatus.ERROR

        if data.get("is_android_started"):
            return DeviceStatus.ONLINE
        elif data.get("is_process_started"):
            return DeviceStatus.STARTING
        else:
            return DeviceStatus.OFFLINE

    async def get_info(self, index: Optional[str] = None) -> Dict[str, EmulatorInfo]:
        """获取 MuMu 模拟器信息"""
        query_idx = index or "all"
        try:
            raw = await self._get_raw_info(query_idx)
            data = json.loads(raw)
        except Exception as e:
            logger.warning(f"MuMu 信息获取失败: {e}")
            return {}

        result: Dict[str, EmulatorInfo] = {}

        # 单个设备
        if isinstance(data, dict) and "index" in data and "name" in data:
            idx = str(data["index"])
            status = await self.get_status(idx)
            adb_addr = self._parse_adb_address(data)
            result[idx] = EmulatorInfo(
                name=data.get("name", f"MuMu-{idx}"),
                index=idx,
                adb_address=adb_addr,
                status=status,
            )
        # 多个设备
        elif isinstance(data, dict):
            for value in data.values():
                if isinstance(value, dict) and "index" in value:
                    idx = str(value["index"])
                    status = await self.get_status(idx)
                    adb_addr = self._parse_adb_address(value)
                    result[idx] = EmulatorInfo(
                        name=value.get("name", f"MuMu-{idx}"),
                        index=idx,
                        adb_address=adb_addr,
                        status=status,
                    )

        return result

    async def get_adb_address(self, index: str) -> str:
        """获取 MuMu ADB 地址"""
        try:
            raw = await self._get_raw_info(index)
            data = json.loads(raw)
            return self._parse_adb_address(data)
        except Exception:
            # MuMu 默认端口计算: 16384 + index * 32
            try:
                port = 16384 + int(index) * 32
                return f"127.0.0.1:{port}"
            except ValueError:
                return "127.0.0.1:16384"

    async def _get_raw_info(self, index: str) -> str:
        """执行 MuMuManager.exe info -v {index}"""
        result = await ProcessRunner.run(
            self.manager_path,
            "info", "-v", index,
            timeout=15,
            merge_stderr=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"MuMuManager info 失败: {result.stdout.strip()}")
        return result.stdout.strip()

    @staticmethod
    def _parse_adb_address(data: dict) -> str:
        """从 MuMuManager JSON 解析 ADB 地址"""
        ip = data.get("adb_host_ip")
        port = data.get("adb_port")
        if ip and port is not None:
            return f"{ip}:{port}"
        return "Unknown"


# ---- LDPlayer 模拟器 ----

class LDPlayerEmulator(BaseEmulator):
    """
    雷电模拟器管理

    命令格式:
      启动: dnconsole.exe launch --index {idx}
      停止: dnconsole.exe quit --index {idx}
      列表: dnconsole.exe list2
    """

    async def start(self, index: str) -> EmulatorInfo:
        """启动雷电模拟器"""
        # 检查是否已在运行
        status = await self.get_status(index)
        if status == DeviceStatus.ONLINE:
            info = await self.get_info(index)
            if index in info:
                return info[index]

        result = await ProcessRunner.run(
            self.manager_path,
            "launch", "--index", index,
            timeout=60,
            merge_stderr=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"LDPlayer 启动失败: {result.stdout}")

        # 等待就绪
        if await self.wait_ready(index):
            info = await self.get_info(index)
            if index in info:
                return info[index]

        return EmulatorInfo(
            name=f"LDPlayer-{index}",
            index=index,
            adb_address="Unknown",
            status=DeviceStatus.STARTING,
        )

    async def stop(self, index: str) -> DeviceStatus:
        """停止雷电模拟器"""
        status = await self.get_status(index)
        if status == DeviceStatus.OFFLINE:
            return DeviceStatus.OFFLINE

        result = await ProcessRunner.run(
            self.manager_path,
            "quit", "--index", index,
            timeout=30,
            merge_stderr=True,
        )
        if result.returncode != 0:
            logger.warning(f"LDPlayer 停止命令失败: {result.stdout}")
            return DeviceStatus.ERROR

        for _ in range(30):
            s = await self.get_status(index)
            if s == DeviceStatus.OFFLINE:
                return DeviceStatus.OFFLINE
            await asyncio.sleep(1)

        return await self.get_status(index)

    async def get_status(self, index: str) -> DeviceStatus:
        """获取雷电模拟器状态"""
        try:
            devices = await self._get_device_list()
        except Exception as e:
            logger.debug(f"LDPlayer 状态获取失败: {e}")
            return DeviceStatus.ERROR

        if index not in devices:
            return DeviceStatus.NOT_FOUND

        in_android = devices[index].get("in_android", 0)
        vbox_pid = devices[index].get("vbox_pid", 0)

        if in_android == 1:
            return DeviceStatus.ONLINE
        elif in_android == 2 or vbox_pid > 0:
            return DeviceStatus.STARTING
        else:
            return DeviceStatus.OFFLINE

    async def get_info(self, index: Optional[str] = None) -> Dict[str, EmulatorInfo]:
        """获取雷电模拟器信息"""
        try:
            devices = await self._get_device_list()
        except Exception as e:
            logger.warning(f"LDPlayer 信息获取失败: {e}")
            return {}

        result: Dict[str, EmulatorInfo] = {}
        for idx, data in devices.items():
            if index is not None and idx != index:
                continue

            in_android = data.get("in_android", 0)
            if in_android == 1:
                status = DeviceStatus.ONLINE
            elif in_android == 2:
                status = DeviceStatus.STARTING
            else:
                status = DeviceStatus.OFFLINE

            # 获取 ADB 端口
            adb_addr = "Unknown"
            if status == DeviceStatus.ONLINE:
                adb_port = self._get_adb_port(data.get("vbox_pid", 0))
                if adb_port:
                    adb_addr = f"127.0.0.1:{adb_port}"
                else:
                    adb_addr = f"emulator-{5554 + int(idx) * 2}"

            result[idx] = EmulatorInfo(
                name=data.get("title", f"LDPlayer-{idx}"),
                index=idx,
                adb_address=adb_addr,
                status=status,
                pid=data.get("pid"),
            )

        return result

    async def get_adb_address(self, index: str) -> str:
        """获取雷电模拟器 ADB 地址"""
        info = await self.get_info(index)
        if index in info:
            return info[index].adb_address
        return "Unknown"

    async def _get_device_list(self) -> Dict[str, dict]:
        """执行 dnconsole.exe list2 并解析 10 字段 CSV"""
        result = await ProcessRunner.run(
            self.manager_path,
            "list2",
            timeout=15,
            merge_stderr=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"dnconsole list2 失败: {result.stdout}")

        devices: Dict[str, dict] = {}
        for line in result.stdout.strip().splitlines():
            parts = line.strip().split(",")
            if len(parts) < 10:
                continue
            try:
                idx = parts[0]
                devices[idx] = {
                    "idx": int(parts[0]),
                    "title": parts[1],
                    "top_hwnd": int(parts[2]),
                    "bind_hwnd": int(parts[3]),
                    "in_android": int(parts[4]),
                    "pid": int(parts[5]),
                    "vbox_pid": int(parts[6]),
                    "width": int(parts[7]),
                    "height": int(parts[8]),
                    "density": int(parts[9]),
                }
            except (ValueError, IndexError):
                continue

        return devices

    @staticmethod
    def _get_adb_port(vbox_pid: int) -> Optional[int]:
        """使用 psutil 从 vbox 进程网络连接获取 ADB 端口"""
        if vbox_pid <= 0:
            return None
        try:
            import psutil
            proc = psutil.Process(vbox_pid)
            for conn in proc.net_connections(kind="inet"):
                if conn.status == psutil.CONN_LISTEN and conn.laddr.port != 2222:
                    return conn.laddr.port
        except Exception:
            pass
        return None


# ---- BlueStacks 模拟器 ----

class BlueStacksEmulator(BaseEmulator):
    """
    BlueStacks 模拟器管理

    BlueStacks 没有统一的 CLI 管理工具，主要通过 ADB 连接。
    启动通过直接运行 HD-Player.exe，停止通过终止进程。
    """

    async def start(self, index: str) -> EmulatorInfo:
        """启动 BlueStacks"""
        status = await self.get_status(index)
        if status == DeviceStatus.ONLINE:
            info = await self.get_info(index)
            if index in info:
                return info[index]

        # BlueStacks 的 manager_path 实际是 HD-Player.exe
        exe_path = self.manager_path
        try:
            args = ["--instance", f"Nougat{index}"] if index != "0" else []
            result = await ProcessRunner.run(
                exe_path, *args, timeout=5, merge_stderr=True,
            )
        except asyncio.TimeoutError:
            pass  # HD-Player.exe 不会立即退出，超时正常

        if await self.wait_ready(index, timeout=120):
            info = await self.get_info(index)
            if index in info:
                return info[index]

        adb_addr = await self.get_adb_address(index)
        return EmulatorInfo(
            name=f"BlueStacks-{index}",
            index=index,
            adb_address=adb_addr,
            status=DeviceStatus.STARTING,
        )

    async def stop(self, index: str) -> DeviceStatus:
        """停止 BlueStacks（通过终止进程）"""
        try:
            import psutil
            for proc in psutil.process_iter(["name"]):
                try:
                    if proc.info["name"] and "HD-Player" in proc.info["name"]:
                        proc.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.warning(f"BlueStacks 停止失败: {e}")
            return DeviceStatus.ERROR

        for _ in range(15):
            s = await self.get_status(index)
            if s == DeviceStatus.OFFLINE:
                return DeviceStatus.OFFLINE
            await asyncio.sleep(1)
        return await self.get_status(index)

    async def get_status(self, index: str) -> DeviceStatus:
        """通过 ADB 连接检查 BlueStacks 状态"""
        adb_addr = await self.get_adb_address(index)
        if adb_addr == "Unknown":
            return DeviceStatus.OFFLINE
        return await self._check_adb_device(adb_addr)

    async def get_info(self, index: Optional[str] = None) -> Dict[str, EmulatorInfo]:
        """获取 BlueStacks 信息"""
        idx = index or "0"
        adb_addr = await self.get_adb_address(idx)
        status = await self._check_adb_device(adb_addr)
        return {
            idx: EmulatorInfo(
                name=f"BlueStacks-{idx}",
                index=idx,
                adb_address=adb_addr,
                status=status,
            )
        }

    async def get_adb_address(self, index: str) -> str:
        """BlueStacks 默认 ADB 端口"""
        try:
            port = 5555 + int(index) * 10
        except ValueError:
            port = 5555
        return f"127.0.0.1:{port}"

    async def _check_adb_device(self, address: str) -> DeviceStatus:
        """通过 ADB 检查设备状态"""
        if not self.adb_path:
            # 尝试查找系统 ADB
            import shutil
            adb = shutil.which("adb")
            if not adb:
                return DeviceStatus.UNKNOWN
            self.adb_path = Path(adb)

        try:
            result = await ProcessRunner.run(
                self.adb_path, "connect", address,
                timeout=10, merge_stderr=True,
            )
            if "connected" in result.stdout.lower():
                return DeviceStatus.ONLINE
            elif "refused" in result.stdout.lower():
                return DeviceStatus.OFFLINE
        except Exception:
            pass
        return DeviceStatus.UNKNOWN


# ---- Nox 模拟器 ----

class NoxEmulator(BaseEmulator):
    """
    夜神模拟器管理

    命令格式:
      启动: Nox.exe -clone:Nox_{idx}
      停止: Nox.exe -clone:Nox_{idx} -quit
      manager_path 指向 Nox.exe
    """

    async def start(self, index: str) -> EmulatorInfo:
        """启动夜神模拟器"""
        status = await self.get_status(index)
        if status == DeviceStatus.ONLINE:
            info = await self.get_info(index)
            if index in info:
                return info[index]

        clone_name = f"Nox_{index}" if index != "0" else "Nox_0"
        try:
            await ProcessRunner.run(
                self.manager_path,
                f"-clone:{clone_name}",
                timeout=5, merge_stderr=True,
            )
        except asyncio.TimeoutError:
            pass  # Nox.exe 不会立即退出

        if await self.wait_ready(index, timeout=120):
            info = await self.get_info(index)
            if index in info:
                return info[index]

        adb_addr = await self.get_adb_address(index)
        return EmulatorInfo(
            name=f"Nox-{index}",
            index=index,
            adb_address=adb_addr,
            status=DeviceStatus.STARTING,
        )

    async def stop(self, index: str) -> DeviceStatus:
        """停止夜神模拟器"""
        clone_name = f"Nox_{index}" if index != "0" else "Nox_0"
        try:
            await ProcessRunner.run(
                self.manager_path,
                f"-clone:{clone_name}", "-quit",
                timeout=15, merge_stderr=True,
            )
        except Exception as e:
            logger.warning(f"Nox 停止失败: {e}")
            return DeviceStatus.ERROR

        for _ in range(15):
            s = await self.get_status(index)
            if s == DeviceStatus.OFFLINE:
                return DeviceStatus.OFFLINE
            await asyncio.sleep(1)
        return await self.get_status(index)

    async def get_status(self, index: str) -> DeviceStatus:
        """通过进程检查 Nox 状态"""
        try:
            import psutil
            for proc in psutil.process_iter(["name", "cmdline"]):
                try:
                    if proc.info["name"] and "nox" in proc.info["name"].lower():
                        cmdline = proc.info.get("cmdline") or []
                        clone_name = f"Nox_{index}" if index != "0" else "Nox_0"
                        if any(clone_name in arg for arg in cmdline) or index == "0":
                            return DeviceStatus.ONLINE
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        return DeviceStatus.OFFLINE

    async def get_info(self, index: Optional[str] = None) -> Dict[str, EmulatorInfo]:
        idx = index or "0"
        status = await self.get_status(idx)
        adb_addr = await self.get_adb_address(idx)
        return {
            idx: EmulatorInfo(
                name=f"Nox-{idx}", index=idx,
                adb_address=adb_addr, status=status,
            )
        }

    async def get_adb_address(self, index: str) -> str:
        """Nox 默认 ADB 端口: 62001 + (index-1)*2, index 0 → 62001"""
        try:
            idx = int(index)
            port = 62001 + idx * 2
        except ValueError:
            port = 62001
        return f"127.0.0.1:{port}"


# ---- 通用模拟器（仅 ADB）----

class GeneralEmulator(BaseEmulator):
    """
    通用模拟器管理 - 仅通过 ADB 地址连接

    适用于没有专用 CLI 管理工具的模拟器，或用户手动指定 ADB 地址的场景。
    不支持启动/停止，只支持状态检查和地址获取。
    manager_path 在此用作 ADB 可执行文件路径。
    """

    def __init__(self, manager_path: Path, adb_path: Optional[Path] = None,
                 default_address: str = "127.0.0.1:5555"):
        super().__init__(manager_path, adb_path or manager_path)
        self.default_address = default_address

    async def start(self, index: str) -> EmulatorInfo:
        """通用模拟器不支持自动启动"""
        status = await self.get_status(index)
        if status == DeviceStatus.ONLINE:
            info = await self.get_info(index)
            if index in info:
                return info[index]
        raise RuntimeError(
            "通用模拟器不支持自动启动，请手动启动模拟器后重试"
        )

    async def stop(self, index: str) -> DeviceStatus:
        """通用模拟器不支持自动停止"""
        logger.warning("通用模拟器不支持自动停止")
        return DeviceStatus.UNKNOWN

    async def get_status(self, index: str) -> DeviceStatus:
        """通过 ADB 检查设备状态"""
        adb = self.adb_path or self.manager_path
        address = self.default_address
        try:
            result = await ProcessRunner.run(
                adb, "connect", address,
                timeout=10, merge_stderr=True,
            )
            if "connected" in result.stdout.lower():
                return DeviceStatus.ONLINE
            elif "refused" in result.stdout.lower():
                return DeviceStatus.OFFLINE
        except Exception:
            pass
        return DeviceStatus.UNKNOWN

    async def get_info(self, index: Optional[str] = None) -> Dict[str, EmulatorInfo]:
        idx = index or "0"
        status = await self.get_status(idx)
        return {
            idx: EmulatorInfo(
                name=f"General-{idx}", index=idx,
                adb_address=self.default_address, status=status,
            )
        }

    async def get_adb_address(self, index: str) -> str:
        return self.default_address


# ---- 模拟器管理器 ----

class EmulatorManager:
    """
    模拟器管理器 - 注册和管理多个模拟器实例

    支持从 MAAConfig 自动加载已注册的模拟器。
    """

    EMULATOR_TYPES = {
        "mumu": MuMuEmulator,
        "ldplayer": LDPlayerEmulator,
        "bluestacks": BlueStacksEmulator,
        "nox": NoxEmulator,
        "general": GeneralEmulator,
    }

    def __init__(self):
        self.emulators: Dict[str, BaseEmulator] = {}

    def register_emulator(
        self,
        emulator_id: str,
        emulator_type: str,
        manager_path: str,
        adb_path: Optional[str] = None,
        default_address: Optional[str] = None,
    ) -> None:
        """注册模拟器"""
        if emulator_type not in self.EMULATOR_TYPES:
            raise ValueError(f"不支持的模拟器类型: {emulator_type}，"
                           f"支持: {list(self.EMULATOR_TYPES.keys())}")

        cls = self.EMULATOR_TYPES[emulator_type]
        kwargs = {
            "manager_path": Path(manager_path),
            "adb_path": Path(adb_path) if adb_path else None,
        }
        if emulator_type == "general" and default_address:
            kwargs["default_address"] = default_address

        self.emulators[emulator_id] = cls(**kwargs)
        logger.info(f"已注册模拟器: {emulator_id} ({emulator_type})")

    def load_from_config(self, emulator_profiles: Dict[str, dict]) -> None:
        """从配置字典批量加载模拟器"""
        for profile_id, profile in emulator_profiles.items():
            emu_type = profile.get("type", "")
            path = profile.get("path", "")
            adb = profile.get("adb_path")
            default_addr = profile.get("default_address")

            if emu_type and path:
                try:
                    self.register_emulator(
                        profile_id, emu_type, path, adb, default_addr,
                    )
                except (ValueError, FileNotFoundError) as e:
                    logger.warning(f"加载模拟器配置 {profile_id} 失败: {e}")

    async def start(self, emulator_id: str, index: str) -> EmulatorInfo:
        if emulator_id not in self.emulators:
            raise ValueError(f"模拟器未注册: {emulator_id}")
        return await self.emulators[emulator_id].start(index)

    async def stop(self, emulator_id: str, index: str) -> DeviceStatus:
        if emulator_id not in self.emulators:
            raise ValueError(f"模拟器未注册: {emulator_id}")
        return await self.emulators[emulator_id].stop(index)

    async def get_status(self, emulator_id: str, index: str) -> DeviceStatus:
        if emulator_id not in self.emulators:
            raise ValueError(f"模拟器未注册: {emulator_id}")
        return await self.emulators[emulator_id].get_status(index)

    async def get_info(
        self,
        emulator_id: Optional[str] = None,
        index: Optional[str] = None,
    ) -> Dict[str, Dict[str, EmulatorInfo]]:
        result: Dict[str, Dict[str, EmulatorInfo]] = {}
        if emulator_id is not None:
            if emulator_id not in self.emulators:
                raise ValueError(f"模拟器未注册: {emulator_id}")
            result[emulator_id] = await self.emulators[emulator_id].get_info(index)
        else:
            for emu_id, emu in self.emulators.items():
                try:
                    result[emu_id] = await emu.get_info(index)
                except Exception as e:
                    logger.warning(f"获取 {emu_id} 信息失败: {e}")
        return result

    async def wait_ready(
        self, emulator_id: str, index: str, timeout: float = 120
    ) -> bool:
        if emulator_id not in self.emulators:
            raise ValueError(f"模拟器未注册: {emulator_id}")
        return await self.emulators[emulator_id].wait_ready(index, timeout)
