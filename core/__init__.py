"""核心功能模块"""

from .task_presets import get_preset, list_presets, TASK_PRESETS
from .config import MAAConfig

__all__ = ['get_preset', 'list_presets', 'TASK_PRESETS', 'MAAConfig']
