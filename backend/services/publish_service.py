"""OmniPublish V2.0 — 上传发布服务（占位模块）

完整版包含：CMS 登录、图片/视频上传到 CDN、视频切片轮询、帖子发布等功能。
请从预装包获取完整版本，覆盖此文件即可使用。
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from config import settings
from services.pipeline_service import pipeline_service
from database import get_pool

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from publish_api import RemotePublishClient, parse_txt_file, build_markdown


class PublishService:
    """上传发布服务（占位）。完整版支持多平台并行发布、视频切片、自动重试。"""

    SLICE_POLL_INTERVAL = 10
    SLICE_MAX_WAIT = 600
    SLICE_MAX_RETRIES = 2

    def __init__(self):
        self._platform_locks: dict = {}

    def _get_lock(self, platform_id: int) -> asyncio.Semaphore:
        if platform_id not in self._platform_locks:
            self._platform_locks[platform_id] = asyncio.Semaphore(1)
        return self._platform_locks[platform_id]

    async def publish_platforms(self, task_id: int, platform_ids: list = None, skip_video: bool = False):
        """发布指定平台（占位）。"""
        await pipeline_service.add_log(
            task_id,
            "发布插件未安装。请从预装包获取完整的 publish_service.py 和 publish_api.py。",
            step=5, level="error"
        )
        raise NotImplementedError("发布插件未安装，请从预装包获取完整版本")

    async def retry_platform(self, task_id: int, platform_id: int, skip_video: bool = False):
        """重试单个平台发布（占位）。"""
        raise NotImplementedError("发布插件未安装，请从预装包获取完整版本")

    async def upload_video_only(self, task_id: int, platform_id: int):
        """仅上传视频（占位）。"""
        raise NotImplementedError("发布插件未安装，请从预装包获取完整版本")


publish_service = PublishService()
