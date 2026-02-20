"""肉鸽测试脚本 - 独立运行"""
import asyncio
import json
import sys
import time
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)

# 将父目录加入 sys.path
project_dir = Path(__file__).parent
parent_dir = project_dir.parent
sys.path.insert(0, str(parent_dir))

import importlib.util

for name in list(sys.modules.keys()):
    if "AgentAutoGame" in name:
        del sys.modules[name]

spec = importlib.util.spec_from_file_location(
    "AgentAutoGame_main",
    str(project_dir / "__init__.py"),
    submodule_search_locations=[str(project_dir)],
)
pkg = importlib.util.module_from_spec(spec)
sys.modules["AgentAutoGame_main"] = pkg
sys.modules[pkg.__name__] = pkg
spec.loader.exec_module(pkg)


async def main():
    from AgentAutoGame_main.agent import MAAAgent

    agent = MAAAgent()
    print("=== MAAAgent init OK ===")

    # Step 1: 配置 MAA 路径
    cfg_result = await agent.handle_handoff({
        "tool_name": "configure_maa",
        "maa_path": r"D:\NagaAssistance\MaaAssistantArknights",
    })
    cfg = json.loads(cfg_result)
    print(f"配置结果: {cfg['status']} - {cfg['message']}")
    if cfg["status"] != "success":
        print("配置失败，退出")
        return

    # Step 2: 执行水月肉鸽
    print("\n=== 开始执行水月肉鸽 ===")
    start = time.time()
    result = await agent.handle_handoff({
        "tool_name": "execute_task",
        "preset": "水月肉鸽",
    })
    elapsed = time.time() - start

    result_data = json.loads(result)
    print(f"\n=== 完成 ({elapsed:.1f}s) ===")
    print(json.dumps(result_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
