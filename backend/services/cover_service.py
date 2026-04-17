"""OmniPublish V2.0 — 封面制作服务"""

import asyncio
import json
import os
import sys
from pathlib import Path

from services.pipeline_service import pipeline_service

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from make_cover import make_cover, LAYOUT_CONFIG


def _validate_folder_path(path: str):
    """校验文件夹路径，防止路径穿越攻击。"""
    import os
    real = os.path.realpath(path)
    # 必须是已存在的目录
    if not os.path.isdir(real):
        raise ValueError(f"目录不存在: {path}")
    # 禁止包含 .. 的路径穿越
    if ".." in path:
        raise ValueError("路径不允许包含 '..'")


class CoverService:
    """封面制作服务。"""

    def get_layouts(self) -> dict:
        """获取可用布局列表。"""
        return {
            k: {"width": v["width"], "height": v["height"], "panels": v["count"]}
            for k, v in LAYOUT_CONFIG.items()
        }

    async def generate_candidates(self, task_id: int, folder_path: str,
                                   layout: str = "triple",
                                   head_margin: float = 0.15) -> list:
        """生成封面。"""
        _validate_folder_path(folder_path)
        await pipeline_service.update_step_status(task_id, step=3, status="running")
        await pipeline_service.add_log(
            task_id, f"开始生成封面: layout={layout}", step=3
        )

        try:
            # 输出到 {素材文件夹}/readytopublish/
            output_dir = os.path.join(folder_path, "readytopublish")
            os.makedirs(output_dir, exist_ok=True)

            cover_path = await asyncio.to_thread(
                make_cover, folder_path, output_dir, layout, head_margin, 95
            )

            if not cover_path:
                raise RuntimeError("未能生成封面")

            # 存储绝对路径（前端通过 preview API 访问）
            abs_paths = [cover_path]

            # 更新数据库
            from database import get_pool
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE tasks SET cover_candidates = $1, cover_layout = $2, updated_at = CURRENT_TIMESTAMP WHERE id = $3",
                    json.dumps(abs_paths, ensure_ascii=False), layout, task_id,
                )

            # 状态：等待用户确认
            await pipeline_service.update_step_status(
                task_id, step=3, status="awaiting_confirm",
                data={"candidates": abs_paths, "count": 1},
            )
            await pipeline_service.add_log(
                task_id, f"封面生成完成", step=3
            )

            return abs_paths

        except Exception as e:
            await pipeline_service.update_step_status(
                task_id, step=3, status="failed", error=str(e)
            )
            await pipeline_service.add_log(task_id, f"封面生成失败: {e}", step=3, level="error")
            raise

    async def confirm_cover(self, task_id: int, cover_index: int) -> str:
        """确认选中的封面，推进到 Step 5。"""
        from database import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT cover_candidates FROM tasks WHERE id = $1", task_id,
            )
            if not row:
                raise ValueError("任务不存在")

            candidates = json.loads(row["cover_candidates"] or "[]")

            # 如果 cover_candidates 为空，尝试从素材目录自动扫描封面文件
            if not candidates:
                folder_row = await conn.fetchrow("SELECT folder_path FROM tasks WHERE id = $1", task_id)
                if folder_row and folder_row["folder_path"]:
                    folder = folder_row["folder_path"]
                    cover_files = sorted([
                        os.path.join(folder, f) for f in os.listdir(folder)
                        if "_cover_" in f.lower() or f.endswith(("_cover_A.jpg", "_cover_B.jpg", "_cover_C.jpg"))
                    ])
                    if cover_files:
                        candidates = cover_files
                        # 补存到数据库
                        await conn.execute(
                            "UPDATE tasks SET cover_candidates = $1 WHERE id = $2",
                            json.dumps(candidates, ensure_ascii=False), task_id,
                        )

            if not candidates:
                raise ValueError("没有可用的封面候选，请先点击「生成封面候选」")
            if cover_index < 0 or cover_index >= len(candidates):
                raise ValueError(f"封面索引超出范围: {cover_index}，有效范围 0-{len(candidates) - 1}")

            cover_path = candidates[cover_index]
            await conn.execute(
                "UPDATE tasks SET cover_path = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
                cover_path, task_id,
            )
            # 重置水印状态，确保进入水印步骤时显示方案预览
            await conn.execute(
                "UPDATE platform_tasks SET wm_status = 'pending', wm_progress = 0, wm_error = NULL WHERE task_id = $1",
                task_id,
            )

        # 推进到 Step 5
        await pipeline_service.advance_step(task_id, from_step=3, to_step=4)
        await pipeline_service.add_log(
            task_id, f"封面已确认: 候选 {chr(65 + cover_index)}", step=3
        )

        return cover_path

    async def generate_per_platform(
        self, task_id: int, folder_path: str,
        platform_configs: list,
    ) -> dict:
        """为每个平台独立生成封面。

        Args:
            platform_configs: [{platform_id, platform_name, layout, head_margin, size}]

        Returns:
            {platform_id: cover_path}
        """
        _validate_folder_path(folder_path)
        await pipeline_service.update_step_status(task_id, step=3, status="running")

        results = {}

        async def _gen_one(cfg: dict) -> tuple:
            pid = cfg["platform_id"]
            pname = cfg["platform_name"].replace(" ", "_").replace("/", "_")
            layout = cfg.get("layout", "triple")
            head_margin = cfg.get("head_margin", 0.15)
            out_dir = os.path.join(folder_path, "readytopublish", pname)
            os.makedirs(out_dir, exist_ok=True)

            cover_path = await asyncio.to_thread(
                make_cover, folder_path, out_dir, layout, head_margin, 95
            )
            return pid, cover_path or ""

        tasks = [_gen_one(cfg) for cfg in platform_configs]
        for coro in asyncio.as_completed(tasks):
            pid, path = await coro
            results[pid] = path

        # 写入 platform_tasks.cover_path / cover_layout
        from database import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            for cfg in platform_configs:
                pid = cfg["platform_id"]
                path = results.get(pid, "")
                layout = cfg.get("layout", "triple")
                await conn.execute(
                    "UPDATE platform_tasks SET cover_path = $1, cover_layout = $2 WHERE task_id = $3 AND platform_id = $4",
                    path, layout, task_id, pid,
                )

        # 同时更新 tasks.cover_candidates（取所有平台的封面路径）
        all_covers = [p for p in results.values() if p]
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE tasks SET cover_candidates = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
                json.dumps(all_covers, ensure_ascii=False), task_id,
            )

        await pipeline_service.update_step_status(
            task_id, step=3, status="awaiting_confirm",
            data={"platform_covers": {str(k): v for k, v in results.items()}, "count": len(all_covers)},
        )
        await pipeline_service.add_log(
            task_id, f"多平台封面生成完成: {len(all_covers)} 张", step=3
        )
        return results

    async def confirm_cover_per_platform(
        self, task_id: int, platform_covers: dict,
    ) -> str:
        """确认各平台独立封面，推进到 Step 5。

        Args:
            platform_covers: {platform_id: cover_path}
        """
        from database import get_pool
        pool = await get_pool()
        first_cover = ""
        async with pool.acquire() as conn:
            for pid, path in platform_covers.items():
                await conn.execute(
                    "UPDATE platform_tasks SET cover_path = $1 WHERE task_id = $2 AND platform_id = $3",
                    path, task_id, int(pid),
                )
                if not first_cover and path:
                    first_cover = path
            # 也更新 tasks.cover_path 为第一个有效封面（兼容旧逻辑）
            if first_cover:
                await conn.execute(
                    "UPDATE tasks SET cover_path = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2",
                    first_cover, task_id,
                )
            # 重置水印状态
            await conn.execute(
                "UPDATE platform_tasks SET wm_status = 'pending', wm_progress = 0, wm_error = NULL WHERE task_id = $1",
                task_id,
            )

        await pipeline_service.advance_step(task_id, from_step=3, to_step=4)
        await pipeline_service.add_log(
            task_id, f"多平台封面已确认: {len(platform_covers)} 个平台", step=3
        )
        return first_cover


cover_service = CoverService()
