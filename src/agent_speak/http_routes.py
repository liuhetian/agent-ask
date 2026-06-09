"""Starlette HTTP 路由。可被挂到 FastMCP 或独立 Starlette app 上。"""
from __future__ import annotations

import json
import logging

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from .session import SESSIONS, SSEClient, get_or_create
from .template import chrome_vars_css, compose_styles_css, render_html, template_css


logger = logging.getLogger("agent_speak.http")


async def ui_root(request: Request) -> HTMLResponse:
    sid = request.path_params["sid"]
    # 把模版预设 + 会话自定义样式内联到初始 HTML(用户刷新/新 tab 接管时),
    # 避免要等下一次 SSE 事件才生效。会话不存在时用默认模版。
    state = SESSIONS.get(sid)
    name = state.template if state else None
    preset_css = template_css(name)
    session_css = compose_styles_css(state.styles) if state else ""
    chrome_css = chrome_vars_css(name)
    return HTMLResponse(render_html(sid, preset_css, session_css, chrome_css))


async def ui_events(request: Request) -> StreamingResponse:
    sid = request.path_params["sid"]
    state = get_or_create(sid)

    # 替换旧连接(若有)
    if state.sse_writer is not None:
        old = state.sse_writer
        await old.send("taken-over", {})
        await old.close()

    writer = SSEClient()
    state.sse_writer = writer

    # 上线即把当前 artifact 推过去(若未提交);否则至少把当前皮肤推过去,
    # 让"等待内容中"的空壳页也带上已选模版的样式。
    if state.artifact_html is not None and not state.submit_event.is_set():
        await writer.send("artifact", {
            "html": state.artifact_html,
            "preset_css": template_css(state.template),
            "session_css": compose_styles_css(state.styles),
            "chrome_css": chrome_vars_css(state.template),
        })
    else:
        await writer.send("styles", {
            "preset_css": template_css(state.template),
            "session_css": compose_styles_css(state.styles),
            "chrome_css": chrome_vars_css(state.template),
        })

    async def gen():
        # 立即推一个 retry 提示,然后开始正常流
        yield b": connected\nretry: 2000\n\n"
        try:
            async for chunk in writer.stream():
                yield chunk
        finally:
            # 仅当我们仍然是 active writer 才清掉
            cur = SESSIONS.get(sid)
            if cur is not None and cur.sse_writer is writer:
                cur.sse_writer = None

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def ui_submit(request: Request) -> JSONResponse:
    sid = request.path_params["sid"]
    state = SESSIONS.get(sid)
    if state is None:
        return JSONResponse({"ok": False, "error": "unknown session"}, status_code=404)
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)
    state.submitted_data = data
    state.error = None
    state.submit_event.set()
    return JSONResponse({"ok": True})


async def ui_error(request: Request) -> JSONResponse:
    sid = request.path_params["sid"]
    state = SESSIONS.get(sid)
    if state is None:
        return JSONResponse({"ok": False, "error": "unknown session"}, status_code=404)
    try:
        body = await request.json()
    except json.JSONDecodeError:
        body = {"message": "unknown render error"}
    msg = body.get("message") or "render error"
    kind = body.get("type") or "render"
    state.error = f"[{kind}] {msg}"
    state.submitted_data = None
    state.submit_event.set()
    return JSONResponse({"ok": True})


ROUTES: list[Route] = [
    Route("/ui/{sid}", ui_root, methods=["GET"]),
    Route("/ui/{sid}/events", ui_events, methods=["GET"]),
    Route("/ui/{sid}/submit", ui_submit, methods=["POST"]),
    Route("/ui/{sid}/error", ui_error, methods=["POST"]),
]


def register_on_mcp(mcp) -> None:
    """把 ROUTES 注册到 FastMCP 实例上(用于 HTTP 模式)。"""
    for route in ROUTES:
        mcp.custom_route(route.path, methods=list(route.methods or ["GET"]))(route.endpoint)
