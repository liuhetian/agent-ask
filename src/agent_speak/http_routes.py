"""Starlette HTTP 路由。可被挂到 FastMCP 或独立 Starlette app 上。"""
from __future__ import annotations

import base64
import json
import logging
import uuid

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from .session import CONFIG, SESSIONS, PoolImage, SSEClient, get_or_create
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


def _get_openai_client():
    from openai import AsyncOpenAI
    return AsyncOpenAI(
        api_key=CONFIG.openai_api_key,
        base_url=CONFIG.openai_base_url,
    )


async def _extract_png(img_data) -> bytes:
    """从 OpenAI 响应的单张图片数据里提取 PNG bytes。"""
    if img_data.b64_json:
        return base64.b64decode(img_data.b64_json)
    if img_data.url:
        import httpx
        async with httpx.AsyncClient() as hc:
            dl = await hc.get(img_data.url)
            return dl.content
    raise ValueError("no image data in response")


async def api_image_generate(request: Request) -> JSONResponse:
    """POST /api/{sid}/generate — 批量生图,存入共享 image_pool。

    参数 n (1-4, 默认 1): 一次生成几张。
    generate 模式用 API 原生 n 参数;edit 模式不支持 n,改用并发请求。
    """
    sid = request.path_params["sid"]
    state = SESSIONS.get(sid)
    if state is None:
        return JSONResponse({"ok": False, "error": "unknown session"}, status_code=404)
    if not CONFIG.openai_api_key:
        return JSONResponse({"ok": False, "error": "OPENAI_API_KEY not configured"}, status_code=500)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)

    prompt = body.get("prompt", "")
    size = body.get("size", "1024x1024")
    n = max(1, min(int(body.get("n", 1)), 4))
    reference_ids = body.get("reference_ids", [])

    if not prompt:
        return JSONResponse({"ok": False, "error": "prompt required"}, status_code=400)

    allowed_sizes = {"1024x1024", "1536x1024", "1024x1536", "auto"}
    if size not in allowed_sizes:
        size = "auto"

    client = _get_openai_client()

    try:
        ref_images = []
        for rid in (reference_ids or [])[:3]:
            img = state.image_pool.get(rid)
            if img:
                ref_images.append(img.png_bytes)

        if ref_images:
            import asyncio
            import io

            async def _one_edit():
                return await client.images.edit(
                    model=CONFIG.openai_image_model,
                    image=io.BytesIO(ref_images[0]),
                    prompt=prompt,
                    size=size,
                )

            resps = await asyncio.gather(*[_one_edit() for _ in range(n)])
            all_img_data = [r.data[0] for r in resps]
        else:
            resp = await client.images.generate(
                model=CONFIG.openai_image_model,
                prompt=prompt,
                size=size,
                n=n,
            )
            all_img_data = list(resp.data)

    except Exception as exc:
        logger.error("image generation failed", exc_info=True)
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    results = []
    for img_data in all_img_data:
        try:
            png_bytes = await _extract_png(img_data)
        except Exception:
            continue
        image_id = uuid.uuid4().hex[:12]
        state.image_pool[image_id] = PoolImage(
            image_id=image_id, png_bytes=png_bytes, source="generated", prompt=prompt,
        )
        results.append({"image_id": image_id, "url": f"/assets/{sid}/{image_id}.png"})

    return JSONResponse({
        "ok": True,
        "images": results,
        "pool_size": len(state.image_pool),
    })


async def api_image_upload(request: Request) -> JSONResponse:
    """POST /api/{sid}/upload — 浏览器粘贴/拖放/选文件上传图片到 pool。"""
    sid = request.path_params["sid"]
    state = SESSIONS.get(sid)
    if state is None:
        return JSONResponse({"ok": False, "error": "unknown session"}, status_code=404)

    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)
        b64 = body.get("data", "")
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        try:
            png_bytes = base64.b64decode(b64)
        except Exception:
            return JSONResponse({"ok": False, "error": "invalid base64"}, status_code=400)
        source = body.get("source", "pasted")
        label = body.get("label", "")
    else:
        png_bytes = await request.body()
        source = "uploaded"
        label = ""

    if len(png_bytes) < 8:
        return JSONResponse({"ok": False, "error": "empty image"}, status_code=400)

    image_id = uuid.uuid4().hex[:12]
    state.image_pool[image_id] = PoolImage(
        image_id=image_id, png_bytes=png_bytes, source=source, label=label,
    )

    return JSONResponse({
        "ok": True,
        "image_id": image_id,
        "url": f"/assets/{sid}/{image_id}.png",
        "pool_size": len(state.image_pool),
    })


async def api_image_assign(request: Request) -> JSONResponse:
    """POST /api/{sid}/assign-image — 把 pool 里一张图指派给某个 img-ai 槽位。"""
    sid = request.path_params["sid"]
    state = SESSIONS.get(sid)
    if state is None:
        return JSONResponse({"ok": False, "error": "unknown session"}, status_code=404)
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)

    ai_id = body.get("ai_id", "")
    image_id = body.get("image_id", "")

    if not ai_id:
        return JSONResponse({"ok": False, "error": "ai_id required"}, status_code=400)
    if image_id and image_id not in state.image_pool:
        return JSONResponse({"ok": False, "error": "unknown image_id"}, status_code=404)

    if image_id:
        state.image_assignments[ai_id] = image_id
    else:
        state.image_assignments.pop(ai_id, None)

    return JSONResponse({"ok": True})


async def api_image_pool(request: Request) -> JSONResponse:
    """GET /api/{sid}/image-pool — 返回 pool 里所有图片 + 槽位分配。"""
    sid = request.path_params["sid"]
    state = SESSIONS.get(sid)
    if state is None:
        return JSONResponse({"ok": False, "error": "unknown session"}, status_code=404)

    images = [
        {
            "image_id": img.image_id,
            "url": f"/assets/{sid}/{img.image_id}.png",
            "source": img.source,
            "prompt": img.prompt,
            "label": img.label,
        }
        for img in state.image_pool.values()
    ]
    return JSONResponse({
        "ok": True,
        "images": images,
        "assignments": dict(state.image_assignments),
    })


async def asset_serve(request: Request) -> Response:
    """GET /assets/{sid}/{filename} — 提供图片访问。"""
    sid = request.path_params["sid"]
    filename = request.path_params["filename"]
    image_id = filename.rsplit(".", 1)[0] if "." in filename else filename

    state = SESSIONS.get(sid)
    if state is None:
        return Response(status_code=404)

    img = state.image_pool.get(image_id)
    if img is None:
        return Response(status_code=404)

    return Response(
        content=img.png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "max-age=3600"},
    )


ROUTES: list[Route] = [
    Route("/ui/{sid}", ui_root, methods=["GET"]),
    Route("/ui/{sid}/events", ui_events, methods=["GET"]),
    Route("/ui/{sid}/submit", ui_submit, methods=["POST"]),
    Route("/ui/{sid}/error", ui_error, methods=["POST"]),
    Route("/api/{sid}/generate", api_image_generate, methods=["POST"]),
    Route("/api/{sid}/upload", api_image_upload, methods=["POST"]),
    Route("/api/{sid}/assign-image", api_image_assign, methods=["POST"]),
    Route("/api/{sid}/image-pool", api_image_pool, methods=["GET"]),
    Route("/assets/{sid}/{filename}", asset_serve, methods=["GET"]),
]


def register_on_mcp(mcp) -> None:
    """把 ROUTES 注册到 FastMCP 实例上(用于 HTTP 模式)。"""
    for route in ROUTES:
        mcp.custom_route(route.path, methods=list(route.methods or ["GET"]))(route.endpoint)
