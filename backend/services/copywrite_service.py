"""OmniPublish V2.0 — 文案生成服务

直接 import copywrite_gen.py 的核心函数，不走 subprocess。
"""

import asyncio
import sys
import os
from pathlib import Path
from typing import Optional

from config import settings, PROMPTS_DIR
from services.pipeline_service import pipeline_service

# 将 scripts 目录加入 Python 路径
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from copywrite_gen import build_system_prompt, build_user_prompt, call_api, parse_result


class CopywriteService:
    """AI 文案生成服务。"""

    async def generate(self, task_id: int, params: dict) -> dict:
        """异步生成文案（单平台，向后兼容）。"""
        await pipeline_service.update_step_status(task_id, step=1, status="running")
        await pipeline_service.add_log(task_id, f"开始 AI 文案生成 (文风: {params.get('style', '默认')})", step=1)

        try:
            result = await self._call_ai(params)

            await pipeline_service.update_step_status(
                task_id, step=1, status="awaiting_confirm", data=result
            )
            await pipeline_service.add_log(
                task_id, f"文案生成完成: {result.get('title', '')[:30]}...", step=1
            )
            return result

        except Exception as e:
            error_msg = str(e)
            await pipeline_service.update_step_status(
                task_id, step=1, status="failed", error=error_msg
            )
            await pipeline_service.add_log(task_id, f"文案生成失败: {error_msg}", step=1, level="error")
            raise

    async def generate_per_platform(self, task_id: int, base_params: dict, platforms: list) -> dict:
        """为每个平台独立生成差异化文案（并行调用）。

        Args:
            task_id: 任务 ID
            base_params: 公共输入 {protagonist, event, photos, video_desc, style,
                         title_range, kw_count, body_len, paragraphs, author}
            platforms: [{id, name, categories, default_author}]

        Returns:
            {platform_id: {title, keywords, body, author, category}}
        """
        await pipeline_service.update_step_status(task_id, step=1, status="running")
        await pipeline_service.add_log(
            task_id,
            f"开始为 {len(platforms)} 个平台并行生成文案 (文风: {base_params.get('style', '默认')})",
            step=1,
        )

        async def _gen_one(plat: dict) -> tuple:
            """为单个平台生成文案。"""
            p = dict(base_params)
            # 使用该平台的分类库
            p["categories"] = plat.get("categories", [])
            # 使用该平台的默认作者（若有），否则用用户填的
            author = plat.get("default_author", "")
            if author:
                p["author"] = author
            try:
                result = await self._call_ai(p)
                return (plat["id"], result)
            except Exception as e:
                await pipeline_service.add_log(
                    task_id,
                    f"平台 {plat.get('name', plat['id'])} 文案生成失败: {e}",
                    step=1, level="error",
                )
                return (plat["id"], None)

        try:
            results = await asyncio.gather(*[_gen_one(p) for p in platforms])
            out = {}
            for pid, result in results:
                if result:
                    out[pid] = result

            if not out:
                raise ValueError("所有平台的文案生成均失败")

            await pipeline_service.update_step_status(
                task_id, step=1, status="awaiting_confirm", data={"per_platform": True}
            )
            await pipeline_service.add_log(
                task_id,
                f"文案生成完成: {len(out)}/{len(platforms)} 个平台成功",
                step=1,
            )
            return out

        except Exception as e:
            error_msg = str(e)
            await pipeline_service.update_step_status(
                task_id, step=1, status="failed", error=error_msg
            )
            await pipeline_service.add_log(task_id, f"文案生成失败: {error_msg}", step=1, level="error")
            raise

    async def _call_ai(self, params: dict) -> dict:
        """构建 prompt 并调用 AI API。"""
        style = params.get("style", "反转打脸风")
        prompts_dir = str(PROMPTS_DIR)
        system_prompt = build_system_prompt(prompts_dir, style)

        class _Args:
            pass
        args = _Args()
        args.protagonist = params.get("protagonist", "")
        args.event = params.get("event", "")
        args.photos = params.get("photos", "")
        args.video_desc = params.get("video_desc", "")
        args.title_range = params.get("title_range", "28")
        args.kw_count = params.get("kw_count", 10)
        args.body_len = params.get("body_len", 400)
        args.paragraphs = params.get("paragraphs", 3)
        args.author = params.get("author", "编辑")
        args.category = ",".join(params.get("categories", []))

        user_prompt = build_user_prompt(args)

        api_base = settings.api_base
        api_key = settings.api_key
        model = settings.cw_model

        if not api_key:
            raise ValueError("未配置 API Key，无法生成文案。请在 config.json 中设置 api_key")

        full_text = await asyncio.to_thread(
            call_api, system_prompt, user_prompt, api_base, api_key, model
        )

        return parse_result(full_text, args.author, args.category)


# 全局单例
copywrite_service = CopywriteService()
