"""MAA Agent v4.0 测试脚本"""

import asyncio
import json
from pathlib import Path
import sys

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent_maa_control import MAAAgent
from agent_maa_control.core.task_presets import get_preset, TASK_PRESETS


async def test_list_presets():
    """测试列出预设"""
    print("=" * 60)
    print("测试: 列出预设任务")
    print("=" * 60)
    
    agent = MAAAgent()
    result = await agent.handle_handoff({"tool_name": "list_presets"})
    data = json.loads(result)
    
    print(f"状态: {data['status']}")
    if data['status'] == 'success':
        print(f"预设数量: {len(data['data']['presets'])}")
        for preset in data['data']['presets'][:3]:
            print(f"  - {preset['name']}")
    print()


async def test_get_status():
    """测试获取状态"""
    print("=" * 60)
    print("测试: 获取状态")
    print("=" * 60)
    
    agent = MAAAgent()
    result = await agent.handle_handoff({"tool_name": "get_status"})
    data = json.loads(result)
    
    print(f"状态: {data['status']}")
    if 'data' in data:
        config = data['data'].get('configuration', {})
        print(f"MAA路径: {config.get('maa_path', '未配置')}")
        print(f"连接地址: {config.get('connect_address', '未配置')}")
    print()


async def test_preset_resolution():
    """测试预设解析"""
    print("=" * 60)
    print("测试: 预设解析")
    print("=" * 60)
    
    test_cases = ["收基建", "日常", "刷理智", "daily_full"]
    
    for preset_name in test_cases:
        preset = get_preset(preset_name)
        if preset:
            print(f"✅ '{preset_name}' -> {preset.get('name', '未知')}")
        else:
            print(f"❌ '{preset_name}' -> 未找到")
    print()


async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print(" " * 15 + "MAA Agent v4.0 测试")
    print("=" * 60 + "\n")
    
    await test_preset_resolution()
    await test_list_presets()
    await test_get_status()
    
    print("=" * 60)
    print(" " * 20 + "测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
