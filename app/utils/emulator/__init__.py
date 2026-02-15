#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2025 MoeSnowyFox
#   Copyright © 2025-2026 AUTO-MAS Team

#   This file is part of AUTO-MAS.

#   AUTO-MAS is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published
#   by the Free Software Foundation, either version 3 of the License,
#   or (at your option) any later version.

#   AUTO-MAS is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
#   the GNU General Public License for more details.

#   You should have received a copy of the GNU General Public License
#   along with AUTO-MAS. If not, see <https://www.gnu.org/licenses/>.

#   Contact: DLmaster_361@163.com

__version__ = "5.0.0"
__author__ = "DLmaster361 <DLmaster_361@163.com>"
__license__ = "GPL-3.0 license"

try:
    from .mumu import MumuManager
    from .ldplayer import LDManager
    from .general import GeneralDeviceManager
    from . import tools as emulator_tools

    async def search_all_emulators() -> list[dict[str, str]]:
        return await emulator_tools.search_all_emulators()

    async def find_emulator_root_path(path: str, emulator_type: str) -> str:
        return await emulator_tools.find_emulator_root_path(path, emulator_type)
except Exception:
    MumuManager = None
    LDManager = None
    GeneralDeviceManager = None

    async def search_all_emulators() -> list[dict[str, str]]:
        return []

    async def find_emulator_root_path(path: str, emulator_type: str) -> str:
        _ = emulator_type
        return path


EMULATOR_TYPE_BOOK = (
    {
        "mumu": MumuManager,
        "ldplayer": LDManager,
        "general": GeneralDeviceManager,
    }
    if MumuManager is not None
    and LDManager is not None
    and GeneralDeviceManager is not None
    else {}
)

__all__ = [
    "MumuManager",
    "LDManager",
    "GeneralDeviceManager",
    "search_all_emulators",
    "find_emulator_root_path",
    "EMULATOR_TYPE_BOOK",
]
