"""FastMCP 实例 + render_artifact / wait_user_feedback 两件套。

设计原则
--------
1. AI 只负责"画出来"——输出纯静态 HTML(Tailwind 样式 + data-ai-id 锚点),
   不写 onClick/useState/onChange,不写 <script>。
2. 浏览器 host 负责"收回来"——批注、表单收集、提交,都在 host 一侧实现,
   不依赖 AI 代码的正确性。
3. 任何一次 MCP 工具调用都必须能在客户端默认超时内返回:
   - render_artifact:推 HTML 到浏览器,立即返回 {sid,url,next_step}
   - wait_user_feedback:
       mode="wait" → 短超时阻塞等提交(适用于"用户当面"场景)
       mode="poll" → 一次性查询,立即返回(适用于"异步审批"场景)
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import webbrowser
from pathlib import Path
from typing import Any, Literal

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from .session import CONFIG, SESSIONS, get_or_create, stdio_sid


logger = logging.getLogger("agent_speak.server")

mcp = FastMCP(name="agent-speak")


def _archive_artifact(sid: str, html: str) -> None:
    """落地一份 HTML 到 <archive_dir>/<sid>/<ts>.html。失败不抛,只记日志。"""
    if not CONFIG.archive_dir:
        return
    try:
        d = Path(CONFIG.archive_dir) / sid
        d.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        (d / f"{ts}.html").write_text(html, encoding="utf-8")
    except Exception:  # noqa: BLE001
        logger.warning("archive failed for sid=%s", sid, exc_info=True)


def _build_next_step(url: str, *, is_reuse: bool) -> str:
    """生成给 LLM 的下一步行动指引。

    - 首次(浏览器未连):必须先把 URL 交给用户,再据交互场景选 wait/poll。
    - 复用(SSE 已活):用户上次提交后保持了页面打开,新 artifact 已直接推过去,
      默认进入 wait 模式等 3 分钟即可,不需要再问用户。
    """
    if is_reuse:
        return (
            "用户上一份 artifact 提交后没关浏览器 tab,新 artifact 已通过 "
            "SSE 直接推送过去。你**不需要**再把 URL 念给用户,也**不需要**"
            "问他是否能看到。\n\n"
            "下一步:调 wait_user_feedback(sid, mode=\"wait\", "
            "max_wait_seconds=180) 同步阻塞最多 3 分钟等他提交。超时会抛 "
            "ToolError,你来明确决定:再调一次 mode=\"wait\" 继续等,或者"
            "降级 mode=\"poll\" 让用户回来时主动来问。\n\n"
            f"(URL 仅供参考,不要再发给用户:{url})"
        )

    if CONFIG.stdio_mode:
        step1 = (
            f"第 1 步(必做,在调用任何其他工具之前):告诉用户你已经为他"
            f"打开了一个浏览器 tab,并附上这个 URL 作为备用——万一没自动"
            f"弹出:\n"
            f"    {url}\n"
            f"然后问他:\"看到了吗?现在就填,还是稍后再看 / 转交给别人?\""
        )
    else:
        step1 = (
            f"第 1 步(必做,在调用任何其他工具之前):把这个 URL 交给用户"
            f"——他必须自己打开,服务端没法替他打开:\n"
            f"    {url}\n"
            f"然后问他:\"能现在就打开填完吗?还是稍后再看 / 转交给别人?\""
        )
    step2 = (
        "第 2 步(根据他的回答):\n"
        "  • 稍后 / 已转交(默认——异步,安全):**不要调任何工具**。"
        "把控制权交还给对话。等用户之后主动问\"回了没\"时,再调一次 "
        "wait_user_feedback(sid)——默认 mode=\"poll\",立即返回。\n"
        "  • 现在就填(交互):调 wait_user_feedback(sid, mode=\"wait\", "
        "max_wait_seconds=60),阻塞最多 60 秒(硬上限 180s);超时抛 "
        "ToolError——处理方式:再调一次 mode=\"wait\" 继续等,或降级 "
        "mode=\"poll\"。\n"
        "**绝不**在做完第 1 步前调 wait_user_feedback——用户不知道 URL "
        "就提交不了,你会永远阻塞在那里。\n\n"
        "提示:用户提交后页面**故意保持打开**,留给下一份 artifact 复用。"
        "如果本次 MCP 会话稍后再调 render_artifact 而他的 tab 还活着,"
        "下一次返回的 next_step 会跳过第 1 步,直接让你进 wait 模式。"
    )
    return f"{step1}\n\n{step2}"


RENDER_DOC = """把一份 UI artifact 推给用户。用户可以填写任意表单字段;开启
工具栏上的"批注模式"开关后(默认就开),点击任意带 data-ai-id 的元素就能写
一条批注。点"发送"后,host 会把 {user_comments, user_form_inputs} 结构化
反馈回传给你。

**按返回值的字段判断下一步,不要按 session 状态推理**——服务端会自己决定要不
要在这一次调用里同步阻塞、把 feedback 一并捎回来。你只看返回里有什么:

  • {feedback: {...}, sid, url, reused_tab: true}
        用户已经提交过了。直接用 feedback,**不要**再调 wait_user_feedback,
        **也不要**再把 URL 念给用户——artifact 是通过 SSE 直接推到他那个
        还活着的 tab 里的,他第一时间就看到了。

  • {status: "pending", next_step, sid, url, reused_tab: false}
        首次推送(浏览器还没连上),用户还没看到这份 artifact。**严格按
        next_step 的指引走**——通常是:先把 URL 告诉用户,然后根据他
        "现在就填 / 稍后再看"分别调 wait_user_feedback 的 wait / poll
        模式。漏掉这一步会死锁:用户拿不到 URL 就没法提交,你会永远等
        不到反馈。

  • {status: "pending", next_step, sid, url, reused_tab: true}
        复用 tab 分支,内置的 3 分钟同步等待结束了,用户还没提交。
        **这就是个正常的"还在等"状态,不是渲染失败、不是服务端故障。**
        URL 不变,artifact 还在用户屏幕上,**不要**再调 render_artifact
        重推一版。下一步看 next_step:继续等就调 wait_user_feedback 的
        wait 模式;把控制权交还给对话就调 poll 模式。

`html` 契约:
- 纯 HTML(通过 innerHTML 注入)。**禁止** React、JSX、useState。
- **样式必须用 Tailwind 工具类。** Tailwind CDN 已预加载。`<style>` 块和
  `<link rel="stylesheet">` 标签在注入时会被剥掉(它们会污染整页样式、冲
  掉 host 的工具栏/日记本),**不要依赖它们**。行内 `style="..."` 属性会
  保留作为应急通道,但请优先用 Tailwind 类,以便和 host 视觉风格统一。
- **HTML 里不能有任何交互。** `<script>`、`<iframe>`、`<object>`、
  `<embed>`、`<link>`、`<meta>`、`<base>`、`<html>`、`<head>`、`<body>`
  这些标签会被剥掉;每一个 `on*` 属性(`onclick`、`onchange`……)也会被
  剥。所有交互——悬停高亮、批注编辑、表单收集、提交——都由 host 接管。
- 每一个有意义的元素都加一个稳定、描述清晰的 `data-ai-id="kebab-case-id"`,
  host 通过它寻址、批注、回传。例:
    <h1 data-ai-id="hero-title" class="text-3xl font-bold">...</h1>
    <input data-ai-id="project-name" type="text" class="border ..." />
- 每个表单输入都配一个 `<label>`(包裹式或 `for=` 都行),host 会把这个
  人类可读的标签和值一起回传。
- 每次 `render_artifact` 都会**替换**上一份 artifact,清空它的批注和表单
  状态。用户提交后页面**故意不关**,显示"请保持此页面打开",这样同一
  会话后续 artifact 可以复用同一个 tab。
"""


WAIT_DOC = """取回用户对 `render_artifact` 推过去那份 artifact 的反馈。
两种模式:

  mode="poll"(默认——异步/审批流,安全)
      立即返回,不等待。如果用户已经提交,返回 {feedback};否则返回
      {pending: true, url}。**不要自动重试**——等用户主动来问
      ("回了吗?")再调下一次。它被设为默认,是因为它绝不会静默消耗时间。

  mode="wait"(交互流——用户正盯着屏幕)
      阻塞最多 `max_wait_seconds`(钳制在 [1, 180],也就是 3 分钟上限)
      等用户提交。提交则返回 {feedback}。**超时会抛 ToolError**
      (不是返回 {pending}),强制你浮上水面做明确决定:再调一次
      mode="wait" 继续等,或降级到 mode="poll"。仅在用户正活跃参与时用。

成功返回(二选一):
  {"feedback": {...}}                — 用户点了发送;payload 见下。
  {"pending": true, "url": "..."}    — poll 模式,还没提交。

反馈 payload 结构:
  {
    "user_comments": [
      {"target_id": "<data-ai-id>",
       "element_html_hint": "<截断后的 outerHTML,约 300 字符>",
       "instruction": "<用户写的内容>"}, ...
    ],
    "user_form_inputs": [
      {"ai_id": "<data-ai-id 或 null>",
       "label": "<推断出的标签文本或 null>",
       "name": "<input 的 name 属性或 null>",
       "type": "text|textarea|select|checkbox|radio|...",
       "value": "<文本/选项是字符串,复选/单选是布尔>"}, ...
    ]
  }

host 渲染出错(比如 AI 写的 HTML 无法注入)会抛 ToolError。
"""


@mcp.tool(description=RENDER_DOC)
async def render_artifact(html: str, ctx: Context) -> dict[str, Any]:
    sid = ctx.session_id or stdio_sid()
    state = get_or_create(sid)

    # 复用判定:SSE 还活着 = 用户上次没关 tab,新 artifact 直接推过去即可。
    is_reuse = state.sse_writer is not None

    state.artifact_html = html
    state.submit_event = asyncio.Event()
    # submitted_data 故意不清:AI 可能重复查询(怕错过),保留上一次的结果
    # 让 wait_user_feedback 总能返回"最近一次已提交"的内容。新一轮是否完成
    # 由 submit_event 决定,与 submitted_data 是否有值无关。
    state.error = None

    _archive_artifact(sid, html)

    if is_reuse:
        await state.sse_writer.send("artifact", {"html": html})

    url = f"{CONFIG.base_url.rstrip('/')}/ui/{sid}"

    if CONFIG.stdio_mode and not state.opened and CONFIG.auto_open:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            logger.debug("webbrowser.open failed", exc_info=True)
        state.opened = True

    # 复用分支:浏览器铁定在线,直接把"等用户提交"内置进 render,
    # 免得 AI 走 next_step 走偏(忘了 wait 或用了 poll)。
    if is_reuse:
        try:
            await asyncio.wait_for(state.submit_event.wait(), timeout=180)
        except asyncio.TimeoutError:
            # 渲染本身是成功的——artifact 已经推到用户那边了,只是这 3 分钟
            # 内他还没提交。**不要**把这当成失败抛出去:对 AI 来说,这就是
            # 一个正常的"还在等提交"状态,URL 不变,页面也没动。
            return {
                "sid": sid,
                "url": url,
                "reused_tab": True,
                "status": "pending",
                "next_step": (
                    "render 成功,artifact 已通过 SSE 推到用户活动 tab,但"
                    "这 3 分钟里他还没提交。URL 不变,页面没问题。\n\n"
                    "你**不需要**再把 URL 念给用户(他第一时间就看到了),"
                    "**更不要**重新调 render_artifact 重推一版。\n\n"
                    f"接下来由你决定:\n"
                    f"  • 继续等:调 wait_user_feedback(sid='{sid}', "
                    f"mode='wait', max_wait_seconds=180)。\n"
                    f"  • 把控制权交还给对话:调 wait_user_feedback("
                    f"sid='{sid}', mode='poll'),等用户之后主动来问。"
                ),
            }
        feedback = _finalize(state)  # {"feedback": ...} 或 raise ToolError
        return {
            "sid": sid,
            "url": url,
            "reused_tab": True,
            **feedback,
        }

    return {
        "sid": sid,
        "url": url,
        "status": "pending",
        "reused_tab": False,
        "next_step": _build_next_step(url, is_reuse=False),
    }


@mcp.tool(description=WAIT_DOC)
async def wait_user_feedback(
    sid: str,
    mode: Literal["poll", "wait"] = "poll",
    max_wait_seconds: int = 60,
    ctx: Context | None = None,
) -> dict[str, Any]:
    state = SESSIONS.get(sid)
    if state is None:
        raise ToolError(f"未知 session:{sid}")

    if state.submit_event.is_set():
        return _finalize(state)

    if mode == "poll":
        return {"pending": True, "url": f"{CONFIG.base_url.rstrip('/')}/ui/{sid}"}

    # mode == "wait": bounded by 3 minutes; raise on timeout
    wait = max(1, min(int(max_wait_seconds), 180))
    try:
        await asyncio.wait_for(state.submit_event.wait(), timeout=wait)
    except asyncio.TimeoutError:
        raise ToolError(
            f"用户暂时还没回复——这 {wait} 秒里他没提交。这是正常的等待"
            f"超时,**不是渲染失败或服务端故障**,artifact 还好端端在他"
            f"页面上,**不要**重新调 render_artifact 重推一版。\n\n"
            f"接下来怎么办由你决定:\n"
            f"  • 继续等:再调一次 wait_user_feedback(sid='{sid}', "
            f"mode='wait', max_wait_seconds=...)。\n"
            f"  • 把控制权交还给对话:切到 mode='poll',等用户之后主动"
            f"来问\"回了没\"。\n"
            f"(URL 仅供参考,不需要重发:{CONFIG.base_url.rstrip('/')}/ui/{sid})"
        )
    return _finalize(state)


def _finalize(state) -> dict[str, Any]:
    if state.error:
        err = state.error
        state.error = None
        raise ToolError(err)
    return {"feedback": state.submitted_data}
