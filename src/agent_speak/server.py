"""FastMCP 实例 + set_session / render_artifact / wait_user_feedback 三件套。

设计原则
--------
1. AI 只负责"画出来"——输出纯静态 HTML(用 ass-* 语义类 + data-ai-id 锚点),
   不写 onClick/useState/onChange,不写 <script>、不写 <style>。
2. 浏览器 host 负责"收回来"——批注、表单收集、提交,都在 host 一侧实现,
   不依赖 AI 代码的正确性。
3. 固定流程,消除"一次同步一次异步"的歧义:
   - set_session:**会话第一步(必做)**。选皮肤(模版/自定义 CSS)+ 拿 URL 交给
     用户打开(预热 SSE 连接)+ 把皮肤源码与 render 的 html 写法契约回传给 AI。
   - render_artifact:把 HTML 推到已打开的页面,**同步阻塞**等用户提交,最多
     max_wait_seconds(默认 180)。一次调用同时完成"推 + 收",省掉一次大模型往返。
     提交→{feedback};超时或页面没连上→{pending}(页面没连上时立即返回、不空等)。
   - wait_user_feedback:render 返回 {pending} 后,阻塞续等用户提交。
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import webbrowser
from pathlib import Path
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError

from .session import CONFIG, SESSIONS, get_or_create, stdio_sid
from .template import (
    TEMPLATES,
    chrome_vars_css,
    compose_styles_css,
    parse_css_rules,
    template_css,
    template_guide,
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
        "chrome_css": chrome_vars_css(state.template),
        "template": state.template,
    })


def _finalize(state) -> dict[str, Any]:
    if state.error:
        err = state.error
        state.error = None
        raise ToolError(err)
    return {"feedback": state.submitted_data}


REGISTER_DOC = """**渲染html第一步(必做)**:选定页面皮肤,拿到要交给用户打开的 URL,
并取得 render_artifact 的 html 写法契约。

做五件事:
  1. 选皮肤——`template` 选一套内置模版(**默认且推荐 "报纸"**),
     和/或 `css` 注册你自己的命名类。
  2. 返回 `url`:**把它交给用户,让他现在就打开**——页面会先显示"等待内容中",
     这一步把 SSE 连接预热好,之后每次 render_artifact 都能直接同步拿反馈。
  3. 返回 `preset_css`:所选模版的**完整 CSS 源码**(含 @apply 实际内容),
     让你写自定义类时配色/间距能跟模版对齐。
  4. 返回 `render_html_contract`:render_artifact 的 `html` 参数到底怎么写
     (语义类清单、data-ai-id 锚点、提交规则)——**render 之前务必照它写**。
  5. 返回 `template_guide`:这套模版适合什么内容、版面节奏怎么排(长材料的
     层级 / 重心 / 留白思路)——照着它编排,别只是套对类名。

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
"""


# render_artifact 的 html 写法契约。**故意不放进 RENDER_DOC**(那是常驻 tool
# description,每轮都吃 token),而是由 set_session 在运行时通过 render_html_contract
# 字段返回一次——AI 在会话第一步就拿到,render 时照着写即可。
HTML_CONTRACT = """`html` 写法契约:
- 纯 HTML(通过 innerHTML 注入)。**禁止** React/JSX/useState。
- **默认就用 ass-* 语义类**(set_session 选的模版已注入,跟 host 风格统一):
    布局:`ass-panel`(卡片) `ass-section` `ass-row`(横排) `ass-col`(竖排)
    文字:`ass-h1` `ass-h2` `ass-hint`(小灰字) `ass-code` `ass-kbd` `ass-divider`
    表单:`ass-field`(label+控件容器) `ass-label` `ass-input` `ass-textarea`
          `ass-select` `ass-check-row`
    按钮:`ass-btn`(基类,必带)+ `ass-btn-primary`/`ass-btn-ghost`/`ass-btn-danger`
          —— 仅纯展示用,**绝不**拿来做提交(提交见下)。
    提示:`ass-alert` + `ass-alert-info`/`ass-alert-warn`/`ass-alert-danger`
  能用预设类表达的版式就别再手堆 Tailwind 工具类。需要新类就去 set_session 注册,
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
- 代码块:用标准 `<pre><code class="language-xxx">` 写法,host 自动语法高亮(highlight.js),
  不需要手动上色。行内代码用 `<code class="ass-code">`。示例:
    <pre><code class="language-python">def hello():
        print("world")</code></pre>
- Mermaid 图表:用 `<pre class="mermaid">` 写法,host 按需加载 Mermaid.js 并自动渲染为
  SVG。支持 flowchart / sequence / gantt / classDiagram / stateDiagram / pie / mindmap 等。
  示例:
    <pre class="mermaid">graph TD
      A[开始] --> B{条件}
      B -->|是| C[结果1]
      B -->|否| D[结果2]</pre>
- 每次 render 都会**替换**上一份 artifact,清空批注和表单状态。用户提交后页面**故意不关**,
  供下一份 artifact 复用同一 tab。
- `<img-ai>` 图片元素（host 接管生成、显示、编辑,AI 只写声明）:
  属性:
    data-ai-id  — 必填。稳定标识,跨 render 保留已选图片。
    prompt      — 生图提示词,**语言与报告正文保持一致**(中文报告写中文 prompt)。有 prompt 时 host **自动生成**并在占位区显示加载动画。
    image-id    — 预上传图片 ID（通过 upload_url 上传后拿到的）。有此属性时**直接显示**,
                  不触发生成。适用于用户已有素材、或外部工具已生成好图片的场景。
    placeholder — 占位文字。无 prompt 也无 image-id 时显示虚线框 + 此文字,
                  等用户在画布面板里手动粘贴/生成/指派。不写则默认"等待图片"。
  优先级: image-id > 已有指派(跨 render 保留) > prompt(自动生成) > placeholder(纯占位)
  三种典型写法:
    ① 需要 AI 生图:
       <img-ai data-ai-id="hero" prompt="赛博朋克城市夜景"></img-ai>
    ② 使用预上传图片:
       <img-ai data-ai-id="hero" image-id="abc123"></img-ai>
    ③ 纯占位,等用户操作:
       <img-ai data-ai-id="section-img" placeholder="第二节配图"></img-ai>
  上传图片(render 之前调,拿 image-id):
    set_session 返回 upload_url(含当前会话 sid),客户端直接 HTTP POST:
      curl -X POST {upload_url} -H "Content-Type: application/json" \
           -d '{"data": "data:image/png;base64,iVBOR...", "label": "素材描述"}'
      → {"ok": true, "image_id": "abc123", "url": "/assets/..."}
    拿到 image_id 后在 html 里写 image-id="abc123" 即可。
  规则:
    • 同一个 data-ai-id 跨 render 保留——用户选好的图不会因为你改了文案而丢失。
      **改文案/调布局时保持 ID 不变**。需要全新图片才换 ID。
    • 不要给 <img-ai> 写 src——host 自动填充。
    • 用户可随时通过右下角「🎨 图片」按钮打开画布面板,在所有图片的共享池里
      生成新变体、粘贴/拖放外部图片、右键选参考图编辑、指派到任意槽位。
    • 提交时 feedback 里的 image_results 会告知每个槽位最终用了哪张图及其 prompt。
"""


RENDER_DOC = """把一份 UI artifact 推给用户,并**同步阻塞**等他提交反馈(固定最多 180 秒)。

前置:先调过 set_session 进行预热

参数:
  • html:纯 HTML 字符串,**写法见 set_session 返回的 `render_html_contract`**。
"""


WAIT_DOC = """render_artifact 获取结果，可设置最多等待时间"""


@mcp.tool(description=REGISTER_DOC)
async def set_session(
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

    base = CONFIG.base_url.rstrip("/")
    return {
        "sid": sid,
        "url": _url(sid),
        "upload_url": f"{base}/api/{sid}/upload",
        "template": state.template,
        "available_templates": list(TEMPLATES),
        "preset_css": template_css(state.template),
        "custom_css": compose_styles_css(state.styles),
        "added_or_updated": sorted(added),
        "connected": connected,
        "render_html_contract": HTML_CONTRACT,
        "template_guide": template_guide(state.template),
        "next_step": next_step,
    }


RENDER_WAIT_SECONDS = 180  # 推送后同步阻塞等用户提交的固定时长。


@mcp.tool(description=RENDER_DOC)
async def render_artifact(
    html: str,
    ctx: Context,
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
    if not connected:
        # 页面还没连上,堵塞等待毫无意义(用户根本看不到 artifact、不可能提交)。
        # artifact 已缓存,用户之后打开/重连 URL 时 ui_events 会自动补推,所以这里
        # 不等待,立即返回 pending,让 AI 去提醒用户打开 URL。
        return {
            "sid": sid,
            "url": _url(sid),
            "connected": False,
            "status": "pending",
            "next_step": (
                f"artifact 已缓存,但页面还没连上——用户可能还没打开 URL。提醒他打开:"
                f"\n    {_url(sid)}\n打开后他就会看到内容;之后用 wait_user_feedback 取反馈。"
            ),
        }

    await state.sse_writer.send("artifact", {
        "html": html,
        "preset_css": template_css(state.template),
        "session_css": compose_styles_css(state.styles),
        "chrome_css": chrome_vars_css(state.template),
    })

    try:
        await asyncio.wait_for(state.submit_event.wait(), timeout=RENDER_WAIT_SECONDS)
    except asyncio.TimeoutError:
        return {
            "sid": sid,
            "url": _url(sid),
            "connected": True,
            "status": "pending",
            "next_step": (
                "render 成功、页面在线,但这段时间用户还没提交。URL 没变、页面没问题,"
                "**不要重推**。继续等就再调 wait_user_feedback。"
            ),
        }

    return {
        "sid": sid,
        "url": _url(sid),
        "connected": connected,
        "template": state.template,
        **_finalize(state),
    }


@mcp.tool(description=WAIT_DOC)
async def wait_user_feedback(
    ctx: Context,
    max_wait_seconds: int = 60,
) -> dict[str, Any]:
    sid = ctx.session_id or stdio_sid()
    state = SESSIONS.get(sid)
    if state is None:
        raise ToolError(
            "本会话还没渲染过 artifact——先调 set_session,再 render_artifact。"
        )

    if state.submit_event.is_set():
        return {"template": state.template, **_finalize(state)}

    # 始终阻塞等用户提交,上限 3 分钟;超时抛 ToolError(不是故障,可再调一次接着等)。
    wait = max(1, min(int(max_wait_seconds), 180))
    try:
        await asyncio.wait_for(state.submit_event.wait(), timeout=wait)
    except asyncio.TimeoutError:
        raise ToolError(
            f"用户暂时还没回复——这 {wait} 秒里他没提交。这是正常的等待超时,"
            f"**不是渲染失败或服务端故障**,artifact 还在他页面上,**不要重推**。"
            f"想继续等就再调一次 wait_user_feedback。"
            f"(URL 仅供参考,不需要重发:{_url(sid)})"
        )
    return {"template": state.template, **_finalize(state)}


