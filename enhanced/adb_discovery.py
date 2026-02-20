"""ADB 自动发现模块。

扫描正在运行的模拟器进程，自动推断 ADB 路径和连接地址。
支持 MuMu / LDPlayer / BlueStacks / Nox(夜神) / MEmu(逍遥)。
"""

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredDevice:
    """发现的设备信息"""
    emulator_type: str          # "mumu" / "ldplayer" / "bluestacks" / "unknown"
    serial: str                 # ADB 连接地址，如 "127.0.0.1:16384"
    adb_path: Optional[str] = None      # ADB 可执行文件路径
    emulator_path: Optional[str] = None  # 模拟器管理工具路径（MuMuManager / dnconsole）
    index: str = "0"            # 模拟器实例索引


# ---- 模拟器进程识别配置 ----

@dataclass
class _EmulatorDef:
    """模拟器识别定义"""
    name: str               # 内部类型名
    keyword: str            # 进程名关键字
    adb_candidates: List[str] = field(default_factory=list)  # ADB 相对路径候选
    manager_candidates: List[str] = field(default_factory=list)  # 管理工具相对路径候选


_EMULATOR_DEFS: List[_EmulatorDef] = [
    _EmulatorDef(
        name="mumu",
        keyword="MuMuPlayer.exe",
        adb_candidates=[
            "vmonitor/bin/adb_server.exe",
            "MuMu/emulator/nemu/vmonitor/bin/adb_server.exe",
            "adb.exe",
        ],
        manager_candidates=[
            "MuMuManager.exe",
            "../MuMuManager.exe",
            "../../MuMuManager.exe",
            "../shell/MuMuManager.exe",
        ],
    ),
    _EmulatorDef(
        name="mumu_v5",
        keyword="MuMuNxDevice.exe",
        adb_candidates=[
            "../../../nx_main/adb.exe",
            "adb.exe",
        ],
        manager_candidates=[
            "../../../../MuMuManager.exe",
            "../../../MuMuManager.exe",
        ],
    ),
    # MuMu 后台服务进程（模拟器未启动时也在运行，用于发现安装位置）
    _EmulatorDef(
        name="mumu_service",
        keyword="MuMuNxMain.exe",
        adb_candidates=[
            "adb_server.exe",
            "adb.exe",
        ],
        manager_candidates=[
            "MuMuManager.exe",
        ],
    ),
    _EmulatorDef(
        name="ldplayer",
        keyword="dnplayer",
        adb_candidates=["adb.exe"],
        manager_candidates=["dnconsole.exe"],
    ),
    _EmulatorDef(
        name="bluestacks",
        keyword="HD-Player",
        adb_candidates=[
            "HD-Adb.exe",
            "Engine/ProgramFiles/HD-Adb.exe",
        ],
        manager_candidates=[],
    ),
    _EmulatorDef(
        name="nox",
        keyword="Nox.exe",
        adb_candidates=[
            "nox_adb.exe",
            "adb.exe",
        ],
        manager_candidates=[
            "Nox.exe",
        ],
    ),
    _EmulatorDef(
        name="nox_vm",
        keyword="NoxVMHandle",
        adb_candidates=[
            "../nox_adb.exe",
            "../adb.exe",
        ],
        manager_candidates=[
            "../Nox.exe",
        ],
    ),
    _EmulatorDef(
        name="memu",
        keyword="MEmu.exe",
        adb_candidates=[
            "adb.exe",
            "../adb.exe",
        ],
        manager_candidates=[
            "MEmuConsole.exe",
            "memuc.exe",
        ],
    ),
]


class AdbDiscovery:
    """
    ADB 自动发现

    扫描正在运行的进程，识别已知模拟器，推算 ADB 路径和连接地址。
    支持 MuMu12 / LDPlayer / BlueStacks / Nox(夜神) / MEmu(逍遥)。
    """

    def discover(self) -> List[DiscoveredDevice]:
        """
        主入口 - 扫描进程发现模拟器并获取 ADB 地址

        Returns:
            发现的设备列表
        """
        devices: List[DiscoveredDevice] = []

        # 1. 通过进程扫描已知模拟器
        emulators = self._scan_emulator_processes()
        logger.info(f"发现 {len(emulators)} 个模拟器进程")

        for emu_def, pid, exe_path in emulators:
            base_dir = Path(exe_path).parent

            # 解析 ADB 路径
            adb_path = self._resolve_path(base_dir, emu_def.adb_candidates)

            # 解析管理工具路径
            manager_path = self._resolve_path(base_dir, emu_def.manager_candidates)

            # 根据类型获取设备
            emu_type = emu_def.name
            if emu_type.startswith("mumu"):
                emu_type = "mumu"

            if emu_def.name in ("mumu", "mumu_v5", "mumu_service") and manager_path:
                mumu_devices = self._get_mumu_devices(manager_path)
                for dev in mumu_devices:
                    dev.adb_path = str(adb_path) if adb_path else dev.adb_path
                    dev.emulator_path = str(manager_path)
                    dev.emulator_type = "mumu"
                    devices.append(dev)

            elif emu_def.name == "ldplayer" and manager_path:
                ld_devices = self._get_ldplayer_devices(manager_path)
                for dev in ld_devices:
                    dev.adb_path = str(adb_path) if adb_path else dev.adb_path
                    dev.emulator_path = str(manager_path)
                    devices.append(dev)

            elif emu_def.name == "bluestacks":
                # BlueStacks 使用常见端口
                for serial in ["127.0.0.1:5555", "127.0.0.1:5556",
                               "127.0.0.1:5565", "127.0.0.1:5575"]:
                    devices.append(DiscoveredDevice(
                        emulator_type="bluestacks",
                        serial=serial,
                        adb_path=str(adb_path) if adb_path else None,
                        emulator_path=str(manager_path) if manager_path else None,
                    ))

            elif emu_def.name in ("nox", "nox_vm"):
                # 夜神模拟器: 默认端口 62001, 多开 +2
                serial = "127.0.0.1:62001"
                devices.append(DiscoveredDevice(
                    emulator_type="nox",
                    serial=serial,
                    adb_path=str(adb_path) if adb_path else None,
                    emulator_path=str(manager_path) if manager_path else None,
                ))

            elif emu_def.name == "memu":
                # MEmu/逍遥模拟器: 默认端口 21503, 多开 +10
                serial = "127.0.0.1:21503"
                devices.append(DiscoveredDevice(
                    emulator_type="memu",
                    serial=serial,
                    adb_path=str(adb_path) if adb_path else None,
                    emulator_path=str(manager_path) if manager_path else None,
                ))

        # 2. 如果没有找到任何模拟器，尝试 adb devices 回退
        if not devices:
            adb_devices = self._get_devices_from_adb()
            devices.extend(adb_devices)

        # 去重
        seen_serials: set = set()
        unique_devices: List[DiscoveredDevice] = []
        for dev in devices:
            if dev.serial not in seen_serials:
                seen_serials.add(dev.serial)
                unique_devices.append(dev)

        logger.info(f"共发现 {len(unique_devices)} 个设备")
        return unique_devices

    def _scan_emulator_processes(self) -> List[tuple]:
        """扫描进程，返回 (EmulatorDef, pid, exe_path) 列表"""
        try:
            import psutil
        except ImportError:
            logger.warning("psutil 不可用，无法扫描进程")
            return []

        results = []
        seen_pids: set = set()

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                info = proc.info
                pid = info.get("pid", 0)
                name = info.get("name", "")

                if pid in seen_pids:
                    continue

                for emu_def in _EMULATOR_DEFS:
                    if emu_def.keyword and emu_def.keyword.lower() in name.lower():
                        try:
                            exe_path = proc.exe()
                            results.append((emu_def, pid, exe_path))
                            seen_pids.add(pid)
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            pass
                        break

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return results

    def _resolve_path(
        self, base_dir: Path, candidates: List[str]
    ) -> Optional[Path]:
        """从候选相对路径中找到第一个存在的文件"""
        for rel in candidates:
            path = (base_dir / rel).resolve()
            if path.exists():
                return path
        return None

    def _get_mumu_devices(self, manager_path: str) -> List[DiscoveredDevice]:
        """
        通过 MuMuManager.exe info -v all 获取 MuMu 设备列表

        解析 JSON 获取 adb_host_ip 和 adb_port。
        """
        devices: List[DiscoveredDevice] = []
        try:
            result = subprocess.run(
                [manager_path, "info", "-v", "all"],
                capture_output=True, timeout=15, check=False,
            )
            if result.returncode != 0:
                stdout_text = result.stdout.decode("utf-8", errors="ignore") if result.stdout else ""
                logger.warning(f"MuMuManager info 失败: {stdout_text}")
                return devices

            raw_stdout = result.stdout.decode("utf-8", errors="ignore").strip()
            data = json.loads(raw_stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
            logger.warning(f"MuMu 设备发现失败: {e}")
            return devices

        def _parse_device(obj: dict) -> Optional[DiscoveredDevice]:
            index = str(obj.get("index", 0))
            ip = obj.get("adb_host_ip")
            port = obj.get("adb_port")
            if isinstance(ip, str) and port is not None:
                return DiscoveredDevice(
                    emulator_type="mumu",
                    serial=f"{ip}:{port}",
                    index=index,
                )
            # 模拟器已安装但未运行：无 ADB 地址，仍返回设备信息
            if "index" in obj:
                return DiscoveredDevice(
                    emulator_type="mumu",
                    serial="not_running",
                    index=index,
                )
            return None

        # 单个设备（直接 dict）
        if isinstance(data, dict) and ("adb_host_ip" in data or "index" in data):
            dev = _parse_device(data)
            if dev:
                devices.append(dev)
        # 多个设备（嵌套 dict）
        elif isinstance(data, dict):
            for value in data.values():
                if isinstance(value, dict) and ("adb_host_ip" in value or "index" in value):
                    dev = _parse_device(value)
                    if dev:
                        devices.append(dev)

        return devices

    def _get_ldplayer_devices(self, manager_path: str) -> List[DiscoveredDevice]:
        """
        通过 dnconsole.exe list2 获取 LDPlayer 设备列表

        解析 10 字段 CSV，使用 psutil 获取 ADB 端口。
        """
        devices: List[DiscoveredDevice] = []
        try:
            result = subprocess.run(
                [manager_path, "list2"],
                capture_output=True, timeout=15, check=False,
            )
            if result.returncode != 0:
                stdout_text = result.stdout.decode("utf-8", errors="ignore") if result.stdout else ""
                logger.warning(f"dnconsole list2 失败: {stdout_text}")
                return devices
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.warning(f"LDPlayer 设备发现失败: {e}")
            return devices

        stdout_text = result.stdout.decode("utf-8", errors="ignore").strip()
        for line in stdout_text.splitlines():
            parts = line.strip().split(",")
            if len(parts) < 10:
                continue

            try:
                idx = parts[0]
                in_android = int(parts[4])
                vbox_pid = int(parts[6])

                if in_android == 0:
                    continue  # 设备未运行

                # 尝试通过 psutil 获取 ADB 端口
                adb_port = self._get_ldplayer_adb_port(vbox_pid)
                if adb_port:
                    serial = f"127.0.0.1:{adb_port}"
                else:
                    serial = f"emulator-{5554 + int(idx) * 2}"

                devices.append(DiscoveredDevice(
                    emulator_type="ldplayer",
                    serial=serial,
                    index=idx,
                ))
            except (ValueError, IndexError):
                continue

        return devices

    def _get_ldplayer_adb_port(self, vbox_pid: int) -> Optional[int]:
        """使用 psutil 从 vbox 进程的网络连接中获取 ADB 端口"""
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

    def _get_devices_from_adb(self) -> List[DiscoveredDevice]:
        """回退：直接运行 adb devices 获取设备列表"""
        adb_path = shutil.which("adb")
        if not adb_path:
            return []

        try:
            result = subprocess.run(
                [adb_path, "devices"],
                capture_output=True, timeout=15, check=False,
            )
            if result.returncode != 0:
                return []
        except (subprocess.TimeoutExpired, OSError):
            return []

        stdout_text = result.stdout.decode("utf-8", errors="ignore") if result.stdout else ""
        devices: List[DiscoveredDevice] = []
        for line in stdout_text.splitlines()[1:]:
            line = line.strip()
            if not line or "\t" not in line:
                continue
            serial, status = line.split("\t", 1)
            if status.strip() in ("device", "offline", "unauthorized"):
                devices.append(DiscoveredDevice(
                    emulator_type="unknown",
                    serial=serial,
                    adb_path=adb_path,
                ))

        return devices


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    discovery = AdbDiscovery()
    found = discovery.discover()
    print(f"\n发现 {len(found)} 个设备:")
    for i, dev in enumerate(found, 1):
        print(f"  {i}. [{dev.emulator_type}] {dev.serial} "
              f"(index={dev.index}, manager={dev.emulator_path})")
