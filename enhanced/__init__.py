"""v5.0 增强功能模块"""

from .process_manager import EnhancedProcessManager, ProcessRunner
from .log_monitor import EnhancedLogMonitor
from .emulator_manager import (
    EmulatorManager,
    EmulatorInfo,
    BaseEmulator,
    LDPlayerEmulator,
    MuMuEmulator,
    BlueStacksEmulator,
    NoxEmulator,
    GeneralEmulator,
    DeviceStatus,
)
from .executor import (
    EnhancedMAAExecutor,
    MAATaskConfig,
    MAAExecutionResult,
)
from .adb_discovery import AdbDiscovery, DiscoveredDevice
from .notification import TaskNotifier
from .scheduler import TaskScheduler
from .script_profiles import ScriptProfileManager, ScriptProfile

__all__ = [
    'EnhancedProcessManager',
    'ProcessRunner',
    'EnhancedLogMonitor',
    'EmulatorManager',
    'EmulatorInfo',
    'BaseEmulator',
    'LDPlayerEmulator',
    'MuMuEmulator',
    'BlueStacksEmulator',
    'NoxEmulator',
    'GeneralEmulator',
    'DeviceStatus',
    'EnhancedMAAExecutor',
    'MAATaskConfig',
    'MAAExecutionResult',
    'AdbDiscovery',
    'DiscoveredDevice',
    'TaskNotifier',
    'TaskScheduler',
    'ScriptProfileManager',
    'ScriptProfile',
]
