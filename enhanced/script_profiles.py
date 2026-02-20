"""多脚本配置管理 - 支持多账号/多脚本配置"""

import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from ..core.task_presets import get_preset, merge_preset_with_params

logger = logging.getLogger(__name__)


@dataclass
class ScriptProfile:
    """脚本配置"""
    name: str                               # 显示名称
    emulator_profile: Optional[str] = None  # 关联的模拟器配置 ID
    client_type: str = "Official"           # 客户端类型
    account_name: str = ""                  # 账号名称
    preset: str = "daily_full"              # 预设任务名称
    connect_address: Optional[str] = None   # 覆盖连接地址（可选）
    medicine_count: int = 0                 # 理智药数量
    stone_count: int = 0                    # 源石数量
    stage: str = "1-7"                      # 刷图关卡
    post_action: str = "NoAction"           # 任务后动作
    custom_tasks: Dict[str, bool] = field(default_factory=dict)  # 自定义任务开关

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScriptProfile":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


class ScriptProfileManager:
    """
    脚本配置管理器

    通过 MAAConfig 持久化脚本配置，支持多账号/多配置管理。
    """

    def __init__(self, config):
        """
        Args:
            config: MAAConfig 实例
        """
        self.config = config

    def list_profiles(self) -> Dict[str, Dict[str, Any]]:
        """列出所有脚本配置"""
        return self.config.get_script_profiles()

    def get_profile(self, profile_id: str) -> Optional[ScriptProfile]:
        """获取指定脚本配置"""
        data = self.config.get_script_profile(profile_id)
        if data is None:
            return None
        return ScriptProfile.from_dict(data)

    def create_profile(self, profile_id: str, profile: ScriptProfile) -> None:
        """创建脚本配置"""
        self.config.set_script_profile(profile_id, profile.to_dict())
        logger.info(f"已创建脚本配置: {profile_id} ({profile.name})")

    def update_profile(self, profile_id: str, **kwargs: Any) -> bool:
        """更新脚本配置的部分字段"""
        data = self.config.get_script_profile(profile_id)
        if data is None:
            return False
        data.update(kwargs)
        self.config.set_script_profile(profile_id, data)
        return True

    def delete_profile(self, profile_id: str) -> bool:
        """删除脚本配置"""
        result = self.config.delete_script_profile(profile_id)
        if result:
            logger.info(f"已删除脚本配置: {profile_id}")
        return result

    def build_task_params(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """
        将脚本配置转换为 execute_task 所需的参数字典

        先解析 preset 为完整任务配置（含 tasks 字典），再叠加 profile 的覆盖参数。

        Returns:
            任务参数字典，如果配置不存在则返回 None
        """
        profile = self.get_profile(profile_id)
        if profile is None:
            return None

        # 解析预设 → 获取完整的 tasks 字典和默认参数
        preset_config = get_preset(profile.preset)
        if preset_config is None:
            logger.warning(f"脚本配置 {profile_id} 引用了不存在的预设: {profile.preset}")
            preset_config = {"tasks": {"StartUp": True}}
        else:
            # 移除预设元数据
            preset_config.pop("name", None)
            preset_config.pop("description", None)

        # 叠加 profile 的覆盖参数
        overrides: Dict[str, Any] = {
            "client_type": profile.client_type,
            "account_name": profile.account_name,
            "post_action": profile.post_action,
        }

        if profile.connect_address:
            overrides["connect_address"] = profile.connect_address

        if profile.emulator_profile:
            overrides["emulator_profile"] = profile.emulator_profile

        if profile.medicine_count > 0:
            overrides["medicine_count"] = profile.medicine_count

        if profile.stone_count > 0:
            overrides["stone_count"] = profile.stone_count

        if profile.stage and profile.stage != "1-7":
            overrides["stage"] = profile.stage

        # custom_tasks 完全替换预设的 tasks（用户想精确控制运行哪些任务）
        if profile.custom_tasks:
            preset_config["tasks"] = profile.custom_tasks

        params = merge_preset_with_params(preset_config, overrides)
        return params


if __name__ == "__main__":
    # 简单测试
    profile = ScriptProfile(
        name="主账号",
        emulator_profile="default",
        client_type="Official",
        preset="daily_full",
    )
    print("Profile:", profile.to_dict())

    restored = ScriptProfile.from_dict(profile.to_dict())
    print("Restored:", restored)
