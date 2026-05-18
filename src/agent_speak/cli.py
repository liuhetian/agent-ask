"""命令行入口。stdio 与 streamable-http 双模式。"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import uvicorn
from starlette.applications import Starlette

from . import http_routes
from .server import mcp
from .session import CONFIG, stdio_sid


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agent-speak",
        description="Let LLMs answer with React components via MCP.",
    )
    p.add_argument("--host", default="127.0.0.1", help="bind host (default 127.0.0.1)")
    p.add_argument("--port", type=int, default=11002, help="bind port (default 11002)")
    p.add_argument("--no-open", action="store_true", help="do not auto-open browser (stdio mode)")
    p.add_argument("--http", action="store_true", help="serve MCP over streamable-http instead of stdio")
    p.add_argument(
        "--public-url",
        default=None,
        help="public base URL the browser will hit (required for --http)",
    )
    p.add_argument("--log-level", default="warning")
    return p


async def _run_stdio(host: str, port: int) -> None:
    """stdio 模式:同进程内并行跑 MCP stdio 与本地 HTTP server。"""
    app = Starlette(routes=http_routes.ROUTES)
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=CONFIG_LOG_LEVEL,
        lifespan="off",
        access_log=False,
    )
    server = uvicorn.Server(config)
    http_task = asyncio.create_task(server.serve(), name="agent-speak-http")
    try:
        # stdio 模式下用一个固定 sid,方便提前打开浏览器调试
        print(f"agent-speak stdio session: http://{host}:{port}/ui/{stdio_sid()}", file=sys.stderr)
        await mcp.run_stdio_async()
    finally:
        server.should_exit = True
        await http_task


async def _run_http(host: str, port: int) -> None:
    """HTTP 模式:FastMCP 自带的 ASGI app 上挂表单路由。"""
    http_routes.register_on_mcp(mcp)
    await mcp.run_http_async(transport="http", host=host, port=port)


CONFIG_LOG_LEVEL = "warning"


def main() -> None:
    args = _build_arg_parser().parse_args()
    global CONFIG_LOG_LEVEL
    CONFIG_LOG_LEVEL = args.log_level
    logging.basicConfig(level=args.log_level.upper())

    CONFIG.auto_open = not args.no_open

    if args.http:
        if not args.public_url:
            print("error: --http requires --public-url", file=sys.stderr)
            sys.exit(2)
        CONFIG.stdio_mode = False
        CONFIG.base_url = args.public_url.rstrip("/")
        asyncio.run(_run_http(args.host, args.port))
    else:
        CONFIG.stdio_mode = True
        CONFIG.base_url = f"http://{args.host}:{args.port}"
        asyncio.run(_run_stdio(args.host, args.port))


if __name__ == "__main__":
    main()
