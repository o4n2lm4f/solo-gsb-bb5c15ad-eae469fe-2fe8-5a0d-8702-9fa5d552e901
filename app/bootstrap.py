"""容器启动初始化：构建内置单位表，确认服务在对外提供前就绪。

Dockerfile / Compose 通过该入口启动：先完成一次性初始化
（内置单位表约 1700+ 名称），成功后再拉起 Uvicorn。
"""
from __future__ import annotations

import logging
import os
import sys

from .units import build_registry

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("engineering_calc.bootstrap")


def initialize() -> None:
    registry = build_registry()
    logger.info("初始化完成：内置单位表 %d 个名称已就绪", len(registry.units))


def main() -> None:
    initialize()
    host = os.environ.get("HOST", "0.0.0.0")
    port = os.environ.get("PORT", "8000")
    logger.info("启动 Uvicorn：http://%s:%s（接口文档 /docs）", host, port)
    os.execv(sys.executable, [
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", host, "--port", port,
    ])


if __name__ == "__main__":
    main()
