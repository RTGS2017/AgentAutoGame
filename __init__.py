"""MAA Control MCP Service v5.0

重构版：移除外部依赖，整合 ADB 自动发现、通知推送、定时调度、多脚本管理。
"""

from .agent import MAAAgent
from .core.task_presets import get_preset, list_presets
from .core.config import MAAConfig
from .enhanced import (
    EnhancedMAAExecutor,
    MAATaskConfig,
    EmulatorManager,
    AdbDiscovery,
    TaskNotifier,
    TaskScheduler,
    ScriptProfileManager,
)

__all__ = [
    'MAAAgent',
    'get_preset',
    'list_presets',
    'MAAConfig',
    'EnhancedMAAExecutor',
    'MAATaskConfig',
    'EmulatorManager',
    'AdbDiscovery',
    'TaskNotifier',
    'TaskScheduler',
    'ScriptProfileManager',
]

__version__ = '5.0.0'
