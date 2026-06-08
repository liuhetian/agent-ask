"""FastMCP 实例 + register_css / render_artifact / wait_user_feedback 三件套。

设计原则
--------
1. AI 只负责"画出来"——输出纯静态 HTML(用 ass-* 语义类 + data-ai-id 锚点),
   不写 onClick/useState/onChange,不写 <script>、不写 <style>。
2. 浏览器 host 负责"收回来"——批注、表单收集、提交,都在 host 一侧实现,
   不依赖 AI 代码的正确性。
3. 固定两步流程,消除"一次同步一次异步"的歧义:
   - register_css:会话第一步。选皮肤(模版/自定义 CSS)+ 拿 URL 交给用户打开
     (预热 SSE 连接)+ 把皮肤源码回传给 AI。
   - render_artifact:把 HTML 推到已打开的页面,**同步阻塞**等用户提交,
     最多 max_wait_seconds(默认 180)。提交→返回 {feedback};超时→{pending}。
     一次工具调用同时完成"推 + 收",省掉一次大模型往返。
   - wait_user_feedback:render 超时后续等(wait),或异步查询(poll)。
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
from .template import (
    TEMPLATES,
    compose_styles_css,
    parse_css_rules,
    template_css,
)


logger = logging.getLogger("agent_speak.server")

mcp = FastMCP(name="agent-speak")


def _url(sid: str) -> str:
    return f"{CONFIG.base_url.rstrip('/')}/ui/{sid}"


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


async def _push_styles(state) -> None:
    """把当前模版预设 + 会话自定义样式推到已打开页面(SSE 在线时)。"""
    if state.sse_writer is None:
        return
    await state.sse_writer.send("styles", {
        "preset_css": template_css(state.template),
        "session_css": compose_styles_css(state.styles),
    })


def _finalize(state) -> dict[str, Any]:
    if state.error:
        err = state.error
        state.error = None
        raise ToolError(err)
    return {"feedback": state.submitted_data}


REGISTER_DOC = """**会话第一步(必做)**:选定页面皮肤,并拿到要交给用户打开的 URL。

做三件事:
  1. 选皮肤——`template` 选一套内置模版(**默认且推荐 "报纸"**),
     和/或 `css` 注册你自己的命名类。
  2. 返回 `url`:**把它交给用户,让他现在就打开**——页面会先显示"等待内容中",
     这一步把 SSE 连接预热好,之后每次 render_artifact 都能直接同步拿反馈。
  3. 返回 `preset_css`:所选模版的**完整 CSS 源码**(含 @apply 实际内容),
     让你写自定义类时配色/间距能跟模版对齐。

参数:
  • template:模版名,二选一地传。可选值见返回的 `available_templates`,
    目前有:报纸 / 极简白 / 暗夜霓虹 / 柔和糖果 / 杂志大刊。不传则沿用当前(默认报纸)。
  • css:一段扁平 CSS,注册成会话自定义类,叠加在模版之上。契约:
      - 一个选择器一条规则,**不要嵌套、不要 @media、不要逗号串选择器**(会被静默丢弃)。
      - 规则体推荐 `@apply <tailwind 工具类...>;`,也可裸 CSS 属性。
      例:`.tag { @apply inline-block text-xs px-2 py-0.5 rounded-full; }`
    选择器会自动加 `.artifact-root` 前缀(只作用于内容区)。
  • reset:true 则先清空已注册的自定义类再添加(模版不受影响)。

**可反复调用**:中途想加新类、换模版、或清空重来,再调一次即可——若用户页面
已打开,样式会**热更新**(不重渲染 artifact)。

所有模版**共用同一组 ass-* 语义类**,所以换模版时你的 HTML 一个字都不用改。
返回 {sid, url, template, available_templates, preset_css, custom_css, connected}。
"""


RENDER_DOC = """把一份 UI artifact 推给用户,并**同步阻塞**等他提交反馈。

前置:应先调过 register_css(它把 URL 交给用户、预热了连接)。本工具把 HTML 通过
SSE 推到那个已打开的页面,然后阻塞最多 `max_wait_seconds` 秒(默认 180,上限 180)
等用户填表单 / 写批注 / 点「发送」。

按返回值判断下一步:
  • {feedback: {...}, sid, url, connected}
        用户已提交。直接用 feedback。这是一次工具调用同时完成了"推 + 收"。
  • {status: "pending", sid, url, connected: true}
        推送成功、页面在线,但这段时间内用户还没提交。**不是失败,别重推**。
        下一步调 wait_user_feedback 继续等(mode="wait")或交还控制权(mode="poll")。
  • {status: "pending", sid, url, connected: false}
        页面还没连上(用户可能没打开 register_css 给的 URL)。提醒用户打开那个
        URL;artifact 已缓存,他一打开就会看到。之后用 wait_user_feedback 取反馈。

参数:
  • html:纯 HTML 字符串(见下方契约)。
  • max_wait_seconds:同步阻塞上限,默认 180,钳制到 [1, 180]。
    异步场景(用户说稍后再看)可传较小值快速返回 pending,再用 poll。

`html` 契约:
- 纯 HTML(通过 innerHTML 注入)。**禁止** React/JSX/useState。
- **默认就用 ass-* 语义类**(register_css 选的模版已注入,跟 host 风格统一):
    布局:`ass-panel`(卡片) `ass-section` `ass-row`(横排) `ass-col`(竖排)
    文字:`ass-h1` `ass-h2` `ass-hint`(小灰字) `ass-code` `ass-kbd` `ass-divider`
    表单:`ass-field`(label+控件容器) `ass-label` `ass-input` `ass-textarea`
          `ass-select` `ass-check-row`
    按钮:`ass-btn`(基类,必带)+ `ass-btn-primary`/`ass-btn-ghost`/`ass-btn-danger`
          —— 仅纯展示用,**绝不**拿来做提交(提交见下)。
    提示:`ass-alert` + `ass-alert-info`/`ass-alert-warn`/`ass-alert-danger`
  能用预设类表达的版式就别再手堆 Tailwind 工具类。需要新类就去 register_css 注册,
  **不要**在 html 里写 `<style>`(会被剥掉)。
  示例:
    <div class="ass-panel">
      <h1 class="ass-h1">新项目</h1>
      <div class="ass-field">
        <label class="ass-label" for="n">项目名</label>
        <input id="n" data-ai-id="name" class="ass-input" />
      </div>
      <p class="ass-hint">填完点右下角「发送」即可提交。</p>
    </div>
- **HTML 里不能有任何交互。** `<script>`/`<style>`/`<iframe>`/`<link>`/`<meta>` 等会被
  剥掉;每个 `on*` 属性(onclick…)也会被剥。所有交互——悬停高亮、批注、表单收集、
  提交——都由 host 接管。
- **不要自己写"提交/发送/确定"按钮。** 提交只由 host 右下角工具栏的绿色「发送」完成。
  你只管把 `<input>`/`<select>`/`<textarea>` 和它们的 `<label>`、`data-ai-id` 写好。
- 每个有意义的元素加一个稳定的 `data-ai-id="kebab-case-id"`,host 靠它寻址/批注/回传。
- 每个表单输入配一个 `<label>`(包裹或 `for=`),host 会把标签和值一起回传。
- 每次 render 都会**替换**上一份 artifact,清空批注和表单状态。用户提交后页面**故意不关**,
  供下一份 artifact 复用同一 tab。
"""


WAIT_DOC = """取回用户对 render_artifact 那份 artifact 的反馈。通常在 render_artifact
返回 {status:"pending"} 之后调——也就是同步阻塞等满了还没等到提交时的续等手段。

两种模式:
  mode="poll"(默认——异步/审批流,安全)
      立即返回,不等待。已提交则返回 {feedback};否则返回 {pending: true, url}。
      **不要自动重试**——等用户主动来问("回了吗?")再调下一次。

  mode="wait"(交互流——用户正盯着屏幕)
      阻塞最多 `max_wait_seconds`(钳制在 [1, 180])等提交。提交则返回 {feedback}。
      **超时会抛 ToolError**(不是返回 {pending}),强制你浮上来做决定:再调一次
      mode="wait" 继续等,或降级 mode="poll"。

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


@mcp.tool(description=REGISTER_DOC)
async def register_css(
    ctx: Context,
    template: str | None = None,
    css: str | None = None,
    reset: bool = False,
) -> dict[str, Any]:
    sid = ctx.session_id or stdio_sid()
    state = get_or_create(sid)

    if template is not None:
        if template not in TEMPLATES:
            raise ToolError(
                f"未知模版 {template!r}。可选:{', '.join(TEMPLATES)}"
            )
        state.template = template

    if reset:
        state.styles.clear()

    added: dict[str, str] = {}
    if css:
        added = parse_css_rules(css)
        state.styles.update(added)

    # 若用户页面已打开,热更新样式(只换皮肤,不动 artifact)。
    await _push_styles(state)

    # stdio 调试模式:首次 register 时自动开浏览器预热(HTTP 部署用不到)。
    if CONFIG.stdio_mode and not state.opened and CONFIG.auto_open:
        try:
            webbrowser.open(_url(sid))
        except Exception:  # noqa: BLE001
            logger.debug("webbrowser.open failed", exc_info=True)
        state.opened = True

    connected = state.sse_writer is not None
    if connected:
        next_step = (
            "皮肤已更新,用户页面在线、已热刷新。直接继续 render_artifact 即可。"
        )
    else:
        next_step = (
            f"**把这个 URL 交给用户,让他现在就打开**(打开后能预热连接,后续 "
            f"render 才能同步拿反馈):\n    {_url(sid)}\n"
            f"页面会先显示\"等待内容中\",这是正常的——你下一步 render_artifact "
            f"推内容过去他就能看到。"
        )

    return {
        "sid": sid,
        "url": _url(sid),
        "template": state.template,
        "available_templates": list(TEMPLATES),
        "preset_css": template_css(state.template),
        "custom_css": compose_styles_css(state.styles),
        "added_or_updated": sorted(added),
        "connected": connected,
        "next_step": next_step,
    }


@mcp.tool(description=RENDER_DOC)
async def render_artifact(
    html: str,
    ctx: Context,
    max_wait_seconds: int = 180,
) -> dict[str, Any]:
    sid = ctx.session_id or stdio_sid()
    state = get_or_create(sid)

    state.artifact_html = html
    state.submit_event = asyncio.Event()
    # submitted_data 故意不清:AI 可能重复查询,保留上一次结果。新一轮是否完成
    # 由 submit_event 决定,与 submitted_data 是否有值无关。
    state.error = None

    _archive_artifact(sid, html)  # 归档保留原文,可回放 AI 原始输入

    connected = state.sse_writer is not None
    if connected:
        await state.sse_writer.send("artifact", {
            "html": html,
            "preset_css": template_css(state.template),
            "session_css": compose_styles_css(state.styles),
        })

    wait = max(1, min(int(max_wait_seconds), 180))
    try:
        await asyncio.wait_for(state.submit_event.wait(), timeout=wait)
    except asyncio.TimeoutError:
        if connected:
            next_step = (
                "render 成功、页面在线,但这段时间用户还没提交。URL 没变、页面没问题,"
                "**不要重推**。继续等就调 wait_user_feedback(mode='wait');把控制权"
                "交还对话就调 mode='poll'。"
            )
        else:
            next_step = (
                f"artifact 已缓存,但页面还没连上——用户可能还没打开 URL。提醒他打开:"
                f"\n    {_url(sid)}\n打开后他就会看到内容;之后用 wait_user_feedback 取反馈。"
            )
        return {
            "sid": sid,
            "url": _url(sid),
            "connected": connected,
            "status": "pending",
            "next_step": next_step,
        }

    return {
        "sid": sid,
        "url": _url(sid),
        "connected": connected,
        **_finalize(state),
    }


@mcp.tool(description=WAIT_DOC)
async def wait_user_feedback(
    ctx: Context,
    mode: Literal["poll", "wait"] = "poll",
    max_wait_seconds: int = 60,
) -> dict[str, Any]:
    sid = ctx.session_id or stdio_sid()
    state = SESSIONS.get(sid)
    if state is None:
        raise ToolError(
            "本会话还没渲染过 artifact——先调 register_css,再 render_artifact。"
        )

    if state.submit_event.is_set():
        return _finalize(state)

    if mode == "poll":
        return {"pending": True, "url": _url(sid)}

    # mode == "wait": bounded by 3 minutes; raise on timeout
    wait = max(1, min(int(max_wait_seconds), 180))
    try:
        await asyncio.wait_for(state.submit_event.wait(), timeout=wait)
    except asyncio.TimeoutError:
        raise ToolError(
            f"用户暂时还没回复——这 {wait} 秒里他没提交。这是正常的等待超时,"
            f"**不是渲染失败或服务端故障**,artifact 还在他页面上,**不要重推**。\n\n"
            f"接下来由你决定:\n"
            f"  • 继续等:再调一次 wait_user_feedback(mode='wait', max_wait_seconds=...)。\n"
            f"  • 把控制权交还对话:切到 mode='poll',等用户之后主动来问。\n"
            f"(URL 仅供参考,不需要重发:{_url(sid)})"
        )
    return _finalize(state)
