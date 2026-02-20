"""通知模块 - 通过 HTTP POST 推送任务进度到配置的 UI 通知端点（如 /ui_notification）。"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False
    logger.debug("httpx 不可用，通知功能将静默降级为空操作")


class TaskNotifier:
    """
    任务通知器

    通过 HTTP POST 将状态/结果推送到配置的 UI 通知端点。
    使用 asyncio.create_task 实现 fire-and-forget，永不阻塞主流程。

    支持的 action:
      - show_tool_status: 显示工具状态（可自动隐藏）
      - hide_tool_status: 隐藏工具状态

    注意: notify_result 现在也使用 show_tool_status + auto_hide，
    不再推入聊天队列，避免与 AI 总结重复显示。
    """

    def __init__(
        self,
        callback_url: Optional[str] = None,
        session_id: str = "maa_agent",
    ):
        self.callback_url = callback_url or "http://localhost:8000/ui_notification"
        self.session_id = session_id
        self._client: Optional["httpx.AsyncClient"] = None

    def _get_client(self) -> Optional["httpx.AsyncClient"]:
        if not _HAS_HTTPX:
            return None
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=5.0)
        return self._client

    async def _post(self, payload: dict) -> None:
        client = self._get_client()
        if client is None:
            return
        try:
            payload["session_id"] = self.session_id
            await client.post(self.callback_url, json=payload)
        except Exception as e:
            logger.debug(f"通知发送失败（静默忽略）: {e}")

    def _fire_and_forget(self, payload: dict) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._post(payload))
        except RuntimeError:
            pass

    def notify_status(self, status_text: str, auto_hide_ms: int = 0) -> None:
        """
        推送状态通知（show_tool_status）

        Args:
            status_text: 状态文字
            auto_hide_ms: 自动隐藏毫秒数，0 表示不自动隐藏
        """
        self._fire_and_forget({
            "action": "show_tool_status",
            "status_text": status_text,
            "auto_hide_ms": auto_hide_ms,
        })

    def notify_result(self, message: str, auto_hide_ms: int = 8000) -> None:
        """
        推送最终结果通知（show_tool_status + auto_hide）

        使用 show_tool_status 而非 show_tool_ai_response，
        避免结果被推入聊天队列导致与 AI 总结重复显示。

        Args:
            message: 结果消息
            auto_hide_ms: 自动隐藏毫秒数，默认 8 秒后隐藏
        """
        self._fire_and_forget({
            "action": "show_tool_status",
            "status_text": message,
            "auto_hide_ms": auto_hide_ms,
        })

    def hide_status(self) -> None:
        """隐藏工具状态"""
        self._fire_and_forget({
            "action": "hide_tool_status",
        })

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


if __name__ == "__main__":
    async def _test():
        notifier = TaskNotifier()
        notifier.notify_status("MAA 正在启动...", auto_hide_ms=5000)
        await asyncio.sleep(1)
        notifier.notify_result("MAA 任务已完成")  # 使用 show_tool_status + auto_hide
        await asyncio.sleep(1)
        await notifier.close()

    asyncio.run(_test())
