"""配置管理模块 - 替代 agent_comms，使用 JSON 文件持久化所有配置"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_FILE = _PROJECT_ROOT / ".agent_maa_config.json"

_DEFAULT_CONFIG = {
    "maa_path": None,
    "connect_address": None,
    "callback_url": "http://localhost:8000/ui_notification",
    "emulator_profiles": {},
    "script_profiles": {},
    "schedules": {},
    "last_params": {},
}


class MAAConfig:
    """
    MAA 配置管理（单例模式）

    使用项目根目录下的 .agent_maa_config.json 持久化所有配置，
    替代原先依赖的 agent_comms.config 模块。
    """

    _instance: Optional["MAAConfig"] = None
    _data: Dict[str, Any] = {}

    def __new__(cls) -> "MAAConfig":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    # ---- 内部 I/O ----

    def _load(self) -> None:
        if _CONFIG_FILE.exists():
            try:
                self._data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"配置文件读取失败，使用默认配置: {e}")
                self._data = dict(_DEFAULT_CONFIG)
        else:
            self._data = dict(_DEFAULT_CONFIG)

        # 合并缺失的默认键
        for key, default_val in _DEFAULT_CONFIG.items():
            if key not in self._data:
                self._data[key] = default_val

    def _save(self) -> None:
        try:
            _CONFIG_FILE.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error(f"配置文件保存失败: {e}")

    def reload(self) -> None:
        self._load()

    # ---- MAA 路径 ----

    def get_maa_path(self) -> Optional[str]:
        return self._data.get("maa_path")

    def set_maa_path(self, path: str) -> None:
        self._data["maa_path"] = path
        self._save()

    def validate_maa_path(self, path: Optional[str] = None) -> tuple[bool, str]:
        p = path or self.get_maa_path()
        if not p:
            return False, "MAA 路径未配置"
        maa_dir = Path(p)
        if not maa_dir.exists():
            return False, f"路径不存在: {p}"
        if not maa_dir.is_dir():
            return False, f"路径不是目录: {p}"
        maa_exe = maa_dir / "MAA.exe"
        if not maa_exe.exists():
            return False, f"未找到 MAA.exe: {maa_exe}"
        config_dir = maa_dir / "config"
        if not config_dir.exists():
            return False, f"未找到 config 目录: {config_dir}"
        return True, "路径有效"

    def get_maa_exe_path(self) -> Optional[Path]:
        p = self.get_maa_path()
        if p:
            return Path(p) / "MAA.exe"
        return None

    def get_maa_config_dir(self) -> Optional[Path]:
        p = self.get_maa_path()
        if p:
            return Path(p) / "config"
        return None

    # ---- 连接地址 ----

    def get_connect_address(self) -> Optional[str]:
        return self._data.get("connect_address")

    def set_connect_address(self, address: str) -> None:
        self._data["connect_address"] = address
        self._save()

    # ---- 模拟器配置 ----

    def get_emulator_profiles(self) -> Dict[str, Any]:
        return self._data.get("emulator_profiles", {})

    def set_emulator_profiles(self, profiles: Dict[str, Any]) -> None:
        self._data["emulator_profiles"] = profiles
        self._save()

    def get_emulator_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        return self.get_emulator_profiles().get(profile_id)

    def set_emulator_profile(self, profile_id: str, profile: Dict[str, Any]) -> None:
        profiles = self.get_emulator_profiles()
        profiles[profile_id] = profile
        self._data["emulator_profiles"] = profiles
        self._save()

    def delete_emulator_profile(self, profile_id: str) -> bool:
        profiles = self.get_emulator_profiles()
        if profile_id in profiles:
            del profiles[profile_id]
            self._data["emulator_profiles"] = profiles
            self._save()
            return True
        return False

    # ---- 脚本配置 ----

    def get_script_profiles(self) -> Dict[str, Any]:
        return self._data.get("script_profiles", {})

    def set_script_profiles(self, profiles: Dict[str, Any]) -> None:
        self._data["script_profiles"] = profiles
        self._save()

    def get_script_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        return self.get_script_profiles().get(profile_id)

    def set_script_profile(self, profile_id: str, profile: Dict[str, Any]) -> None:
        profiles = self.get_script_profiles()
        profiles[profile_id] = profile
        self._data["script_profiles"] = profiles
        self._save()

    def delete_script_profile(self, profile_id: str) -> bool:
        profiles = self.get_script_profiles()
        if profile_id in profiles:
            del profiles[profile_id]
            self._data["script_profiles"] = profiles
            self._save()
            return True
        return False

    # ---- 定时任务 ----

    def get_schedules(self) -> Dict[str, Any]:
        return self._data.get("schedules", {})

    def set_schedules(self, schedules: Dict[str, Any]) -> None:
        self._data["schedules"] = schedules
        self._save()

    def get_schedule(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        return self.get_schedules().get(schedule_id)

    def set_schedule(self, schedule_id: str, schedule: Dict[str, Any]) -> None:
        schedules = self.get_schedules()
        schedules[schedule_id] = schedule
        self._data["schedules"] = schedules
        self._save()

    def delete_schedule(self, schedule_id: str) -> bool:
        schedules = self.get_schedules()
        if schedule_id in schedules:
            del schedules[schedule_id]
            self._data["schedules"] = schedules
            self._save()
            return True
        return False

    # ---- 上次任务参数 ----

    def get_last_params(self, task_type: str) -> Dict[str, Any]:
        """获取指定任务类型的上次使用参数"""
        return self._data.get("last_params", {}).get(task_type, {})

    def get_all_last_params(self) -> Dict[str, Dict[str, Any]]:
        """获取所有任务类型的上次使用参数"""
        return self._data.get("last_params", {})

    def set_last_params(self, task_type: str, params: Dict[str, Any]) -> None:
        """保存指定任务类型的本次参数"""
        if "last_params" not in self._data:
            self._data["last_params"] = {}
        self._data["last_params"][task_type] = params
        self._save()

    # ---- 通知回调 ----

    def get_callback_url(self) -> Optional[str]:
        return self._data.get("callback_url")

    def set_callback_url(self, url: str) -> None:
        self._data["callback_url"] = url
        self._save()

    # ---- 批量更新 ----

    def update(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if key in _DEFAULT_CONFIG:
                self._data[key] = value
        self._save()

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._data)


if __name__ == "__main__":
    config = MAAConfig()
    print("当前配置:", json.dumps(config.to_dict(), ensure_ascii=False, indent=2))

    # 测试读写
    config.set_maa_path(r"C:\path\to\MaaAssistantArknights")  # 示例：替换为你的 MAA 安装目录
    valid, msg = config.validate_maa_path()
    print(f"路径验证: {valid} - {msg}")

    config.set_emulator_profile("default", {
        "type": "mumu",
        "path": r"D:\MuMuPlayer\MuMuManager.exe",
        "index": "0",
    })
    print("模拟器配置:", config.get_emulator_profiles())

    print("保存后配置:", json.dumps(config.to_dict(), ensure_ascii=False, indent=2))
