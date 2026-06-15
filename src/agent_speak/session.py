"""Session 状态与全局运行期配置。所有状态在内存里。"""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Config:
    base_url: str = "http://127.0.0.1:11002"
    stdio_mode: bool = True
    auto_open: bool = True
    # 每次 render_artifact 把 HTML 落地到 <archive_dir>/<sid>/<timestamp>.html。
    # 相对路径相对于进程 cwd。设为 None / 空串可关闭。
    archive_dir: str | None = "artifacts"
    # OpenAI 兼容图片生成 API
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_image_model: str = "gpt-image-2"


CONFIG = Config()


class SSEClient:
    """单个 SSE 连接的发件队列。仅 1 个并发消费者。"""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[tuple[str, Any] | None] = asyncio.Queue()
        self.closed: bool = False

    async def send(self, event: str, data: Any) -> None:
        if self.closed:
            return
        await self.queue.put((event, data))

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        await self.queue.put(None)

    async def stream(self):
        try:
            while True:
                item = await self.queue.get()
                if item is None:
                    break
                event, data = item
                payload = json.dumps(data, ensure_ascii=False)
                yield f"event: {event}\ndata: {payload}\n\n".encode("utf-8")
        finally:
            self.closed = True


@dataclass
class PoolImage:
    """画布 pool 里的一张图。"""
    image_id: str
    png_bytes: bytes
    source: str          # "generated" | "uploaded" | "pasted"
    prompt: str = ""     # 生成时的 prompt(上传/粘贴为空）
    label: str = ""      # 用户可编辑的标签

@dataclass
class SessionState:
    sid: str
    artifact_html: str | None = None
    # 当前激活的模版名(set_session 选定)。决定注入哪套 ass-* 预设。
    # 默认报纸;字面值需与 template.DEFAULT_TEMPLATE 一致。
    template: str = "报纸"
    # 会话级自定义 CSS:AI 通过 set_session(css=...) 注册的命名类。
    # key 是选择器(".card"),value 是规则体("@apply bg-white shadow ..." 或裸 CSS)。
    # 仅内存,不落地。drop(sid) 时随会话一起消失。
    styles: dict[str, str] = field(default_factory=dict)
    sse_writer: SSEClient | None = None
    submit_event: asyncio.Event = field(default_factory=asyncio.Event)
    submitted_data: Any = None  # 结构化 feedback: {user_comments, user_form_inputs}
    error: str | None = None
    opened: bool = False
    # 共享图片池:所有生成/上传/粘贴的图片,跨 render 保留
    image_pool: dict[str, PoolImage] = field(default_factory=dict)  # image_id -> PoolImage
    # 槽位分配:img-ai 的 data-ai-id -> 被指派的 image_id
    image_assignments: dict[str, str] = field(default_factory=dict)


SESSIONS: dict[str, SessionState] = {}


# stdio 模式下没有真正的 session id 概念,用一个进程级的固定 id
_STDIO_SID = uuid.uuid4().hex[:16]


def stdio_sid() -> str:
    return _STDIO_SID


def get_or_create(sid: str) -> SessionState:
    state = SESSIONS.get(sid)
    if state is None:
        state = SessionState(sid=sid)
        SESSIONS[sid] = state
    return state


async def drop(sid: str) -> None:
    state = SESSIONS.pop(sid, None)
    if state is None:
        return
    if state.sse_writer is not None:
        await state.sse_writer.send("end", {})
        await state.sse_writer.close()
    if not state.submit_event.is_set():
        state.error = "session closed"
        state.submit_event.set()
