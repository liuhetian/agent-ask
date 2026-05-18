# Agent-Speak PRD

## 1. 背景与目标

### 为什么是 HTML,不是 markdown

LLM 早期主要用 markdown 跟人对话——简单、可移植、支持基本富文本。但**当 AI 写的东西越来越复杂**(长方案、设计稿、研究报告、表格数据),**markdown 就撑不住了**。Anthropic 工程师 Thariq 在 [*"Using Claude Code: The Unreasonable Effectiveness of HTML"*](https://x.com/trq212/status/2052809885763747935) 里把这个判断说得很清楚:

- 100 行以上的 markdown 几乎没人会从头读完,更别说让别人读了
- AI 用 ASCII 画图、用 unicode 估颜色,都是"被 markdown 卡住"的代偿行为
- HTML 能装下**表格、CSS 设计、SVG 插图、代码片段、甚至交互控件**,信息密度高得多,**浏览器原生就能看**,扔到云上一个 link 就能分享
- 用 HTML 沟通的好处是「**you feel more in the loop**」——你真的在场参与,而不是无脑信任 AI 的判断

但 HTML 默认是**单向**的——AI 写出来,你只能看。要真正闭环,还差关键的另一半:**让用户在 AI 写的 HTML 上直接改、批注、勾选**,然后把结构化反馈回传给 AI。原文里"Custom Editing Interfaces"那一节专门讲了这个模式:为某次具体任务**捏一个一次性的 HTML 编辑器,末尾带一个"导出回 prompt"按钮**——`agent-speak` 把它从"每次让 Claude 现造一个 editor + 现写一个 copy 按钮"工程化成了通用工具:**AI 写出 artifact,host 自动负责收集和回传**。

### 目标

给 LLM 一对工具 `render_artifact(html)` + `wait_user_feedback(sid)`,让它把"产物"以纯静态 HTML 的形式贴到用户浏览器里;用户**直接改文案、填表单、点击右下角"批注模式"开关后点节点写批注**,提交后 LLM 收到结构化的 `{user_comments, user_form_inputs}`。LLM 因此能用富 UI 而非纯文本跟用户来回。

**核心设计**——Host vs. Artifact 解耦：
- **Artifact 层**：AI 只输出 HTML + Tailwind + `data-ai-id` 锚点。**禁止**写 `<script>` / `onClick` / 状态。
- **Host 层**：浏览器里的前端基座负责悬停高亮、批注、表单 uncontrolled harvest、提交。AI 写错也踩不死 host。

**核心原则**：
- 最小、优雅、零外部依赖（无 React、无 Babel、无 Redis、无 DB、无 Node binary）
- 单进程、单文件包、内存即状态
- 公网部署 + 本地 stdio 同一份代码

---

## 2. 核心交互模型

> **整个 LLM 对话 ↔ 一个浏览器标签页。** LLM 调 `render_artifact` 把 HTML 推到标签页。**第一次调用立即返回** `{sid, url, status:"pending", reused_tab:false, next_step}`,让 LLM 把 URL 交给用户;**之后每一次复用 (`reused_tab:true`) 直接同步阻塞最多 3 分钟**收用户提交并返回 `{feedback}`,免得 LLM 走 `next_step` 还要再调一次 `wait_user_feedback`。所有可能阻塞的等待都受 3 分钟硬上限保护。

三种场景：

| 场景 | 用户故事 | 实际流程 |
|---|---|---|
| **首次 · 异步审批**（默认） | "把这份发给领导审" — 用户暂时不在 | `render_artifact` → 用户说"发给某人了" → LLM **不主动调任何东西** → 几小时后用户问"批了没?" → `wait_user_feedback(sid)`(默认 `mode="poll"`)一次性查询 |
| **首次 · 当面交互** | "帮我配一下项目" — 用户现在就在屏幕前 | `render_artifact` → 用户确认能打开 → `wait_user_feedback(sid, mode="wait")`,3 分钟内提交则收到 feedback;超时 ToolError,由 LLM 决定再 wait 还是改 poll |
| **复用 · 第二次起渲染** | 第二轮、第三轮迭代的"再来一稿" | `render_artifact` 自动检测 `state.sse_writer is not None` (浏览器还连着) → 新 HTML 通过 SSE 直接推过去 → **同步阻塞至多 180s** → 直接返回 `{feedback}`。LLM 不需要再调 `wait_user_feedback`,也不需要再跟用户说一次 URL |

为什么 `render_artifact` + `wait_user_feedback` 这一对工具：MCP 规范里没有"工具返回后再推结果"的语义。首次调用必须**立即拿到 URL** 念给用户(他还没打开就阻塞 = 永远不会有提交)；后续调用浏览器已在线,直接在 `render_artifact` 内部等就够了——这种"按场景自适应"的安排让 LLM 在最常见的"AI 来回多轮迭代 artifact"场景里只用一次工具调用。

时序：

### 首次 · 当面交互（mode="wait"）

```
LLM client                       agent-speak                       浏览器
   │
   │ tool: render_artifact(h) ──────►│
   │ ◄─ {sid,url,status:"pending",reused_tab:false,next_step} ─│ stdio: webbrowser.open(url)
   │                                                   ◄── GET /ui/{sid} ──
   │                                                   ── HTML 壳 ────────►
   │                                                   ◄── SSE /events ────
   │                                  │ (sse_writer 上线后,把 artifact_html push 出去)
   │                                                              (innerHTML)
   │ 询问用户:"现在能打开吗?"  → 能
   │ tool: wait_user_feedback(sid, mode="wait", max_wait=60) ►│
   │                                  │ asyncio.wait_for(event, 60s)
   │                                  │      ◄── POST /submit ─────────────
   │ ◄── {feedback:{...}} ──────────│      event.set()
```

### 复用 · 第二轮起（render_artifact 内部已 wait）

```
LLM client                       agent-speak                       浏览器
   │ (此时 state.sse_writer != None,用户上次提交后没关 tab)
   │ tool: render_artifact(h2) ─────►│
   │                                  │ ── 'artifact'(h2) ──── SSE ────────►
   │                                  │                       (innerHTML 替换)
   │                                  │ asyncio.wait_for(event, 180s)
   │                                  │      ◄── POST /submit ─────────────
   │ ◄── {sid,url,reused_tab:true,feedback:{...}} ──│      event.set()
```

### 首次 · 异步审批（mode="poll"）

```
LLM client                       agent-speak                       浏览器
   │
   │ tool: render_artifact(h) ──────►│
   │ ◄── {sid,url,next_step} ───────│
   │ 询问用户:"现在能打开吗?"  → 等下,我先发给领导
   │ [LLM 不调任何 wait 工具,回到对话]
   │
   │   ...   (几小时后)   ...                              ◄── 用户/领导随时打开
   │                                                          填表、批注、提交 ──
   │ 用户:"批了没?"
   │ tool: wait_user_feedback(sid, mode="poll") ─►│
   │                                  │ event.is_set()? → yes
   │ ◄── {feedback:{...}} ──────────│
   │
   │ (若未提交则)                     │
   │ ◄── {pending:true,url} ────────│  LLM 告诉用户"还没,链接是 url"
```

---

## 3. 架构

```
LLM client (Claude Code / Cursor / claude.ai 等)
       │ MCP over stdio  OR  streamable-http
       ▼
┌───────────────────────────────────────────────┐
│ agent-speak 进程 (单进程,单 uvicorn worker)   │
│                                                │
│  FastMCP server                                │
│   ├─ render_artifact(html)        → {sid,url}  │
│   └─ wait_user_feedback(sid, ...) → {feedback} │
│                                                │
│  Starlette HTTP routes                         │
│   ├─ GET  /ui/{sid}          → HTML 壳         │
│   ├─ GET  /ui/{sid}/events   → SSE 通道        │
│   ├─ POST /ui/{sid}/submit   → 提交结构化反馈  │
│   └─ POST /ui/{sid}/error    → 浏览器错误上报  │
│                                                │
│  内存 SESSIONS: dict[sid, SessionState]        │
└───────────────────────────────────────────────┘
       │ HTTP
       ▼
浏览器标签页 (vanilla JS host,无 React,无 Babel)
```

- **不分进程**：MCP server + HTTP routes 全部 in-process
- **不分端口**：HTTP 模式下 FastMCP 和 host 路由共享一个 Starlette app
- **不需要 Redis**：所有状态在 `SESSIONS` dict 里
- **不需要 React / Babel / dnd-kit**：浏览器侧约 200 行 vanilla JS

---

## 4. Tool API

两个工具，搭配使用。所有可能阻塞的等待都受 3 分钟硬上限保护。

### 4.1 `render_artifact`

```python
@mcp.tool
async def render_artifact(html: str, ctx: Context) -> dict:
    """
    把一份 UI artifact 推给用户。LLM 不需要按 session 状态推理,只看返回
    字段决定下一步——服务端会自己判断要不要在这一次调用里同步阻塞、把
    feedback 一并捎回来:

      • {feedback, sid, url, reused_tab: true}
          用户已经提交了。直接用 feedback,不要再调 wait_user_feedback,
          也不要再把 URL 念给用户。
      • {status: "pending", next_step, sid, url, reused_tab: false}
          用户还没看到这份 artifact。严格按 next_step 走——先把 URL 告诉
          用户,再据"现在就填 / 稍后再看"分别调 wait / poll。

    抛 ToolError:artifact 已送达,但服务端挂起期间没等到提交。补救:
    调 wait_user_feedback(sid, mode="wait" | "poll")。

    内部行为(LLM 不必关心):
    - 首次(SSE 未连)立即返回 pending + next_step。
    - 复用(SSE 已连)同步阻塞最多 180s 等用户提交,直接返回 feedback。

    副作用:
    - stdio 模式下首次调用会顺便 webbrowser.open(url)。
    - 每次调用都把 HTML 落地到 <archive_dir>/<sid>/<timestamp>.html
      (见 §5.4);失败只 warn 日志,不抛。

    `html` 契约:
    - 纯 HTML(innerHTML 注入)。**禁止** React、JSX。
    - **样式必须用 Tailwind 工具类**(CDN 已预加载)。
      `<style>` 块和 `<link rel="stylesheet">` 会被剥;行内 style 属性
      保留作为应急通道,但不鼓励。
    - **禁止** `<script>` / 内联 on* 事件 / useState。host 负责所有交互。
      `<script>` / `<iframe>` / `<object>` / `<embed>` / `<link>` /
      `<meta>` / `<base>` / `<html>` / `<head>` / `<body>` 这些标签会
      被剥,`on*` 属性也会被剥。
    - 每个有意义的元素必须带 data-ai-id="kebab-case-id"。
    - 每个表单输入都建议配 <label>(包裹式或 for= 都行)。
    """
```

返回 `next_step` （仅 `reused_tab:false` 时存在）形如（按运行 mode 自适应；URL 内联进文本里让 LLM 直接引用）：

**stdio 模式**：
> 第 1 步(必做,在调用任何其他工具之前):告诉用户你已经为他打开了一个浏览器 tab,并附上这个 URL 作为备用——万一没自动弹出:
>     http://127.0.0.1:11002/ui/abc123
> 然后问他:"看到了吗?现在就填,还是稍后再看 / 转交给别人?"
>
> 第 2 步(根据他的回答):
>   • 稍后 / 已转交(默认——异步,安全):**不要调任何工具**……
>   • 现在就填(交互):调 wait_user_feedback(sid, mode="wait", ...)……
> **绝不**在做完第 1 步前调 wait_user_feedback——用户不知道 URL 就提交不了,你会永远阻塞。

**http 模式**：将第 1 步措辞改为"把这个 URL 交给用户——他必须自己打开,服务端没法替他打开"。

复用分支不返回 `next_step`,直接同步阻塞到拿 feedback 或超时 ToolError。

设计要点：
1. **首次 vs 复用语义分叉对 LLM 透明**:首次必须把 URL 念给用户(浏览器还没开),所以立即返回 pending;复用浏览器已经在线,artifact 一推就显示,把"等用户提交"内置进 `render_artifact` 直接返回 feedback。LLM **只看返回字段**(`feedback` 还是 `next_step`)就知道该干嘛,不需要推理 SSE 状态。
2. 把 URL **内联**进 `next_step` 字符串里,LLM 不用解读返回结构就能直接引用。
3. 用"第 1 步(必做,在调用任何其他工具之前)"+"绝不在做完第 1 步前调 wait_user_feedback"双重否定句锁死先后顺序——避免 LLM 跳过"告诉用户 URL"直接开等。
4. stdio / http 文案不同:stdio 强调"已自动打开 + 万一没弹出来这是链接";http 强调"用户必须自己打开,服务器开不了"。
5. **客户端超时警示**:3 分钟阻塞超过部分 MCP 客户端默认 tool timeout(如 Claude Code 是 60s)。如果客户端先 abort,服务端 SessionState 仍保留,LLM 调 `wait_user_feedback(sid, mode="wait" or "poll")` 即可续上等待。

### 4.2 `wait_user_feedback`

```python
@mcp.tool
async def wait_user_feedback(
    sid: str,
    mode: Literal["poll", "wait"] = "poll",
    max_wait_seconds: int = 60,
    ctx: Context | None = None,
) -> dict:
    """
    用途:
    - 首次 render_artifact 之后的跟进调用(按 next_step 决定 poll 还是 wait)。
    - 复用模式下 render_artifact 抛 ToolError 或被客户端 abort 后的恢复路径
      (sid 和 SessionState 都保留着)。

    mode="poll"(默认,更安全)
        立即返回。异步 / 审批流。**不要自动重试**——等用户主动来问。
    mode="wait"
        阻塞最多 max_wait_seconds(钳制在 [1, 180])等用户提交。交互流。
        **超时抛 ToolError**(不是返回 pending),强制 LLM 做明确决定:
        重试还是降级。

    成功返回:
      {"feedback": {...}}               — 用户点了发送
      {"pending": true, "url": "..."}   — poll 模式,还没提交
    host 渲染出错或 wait 模式超时会抛 ToolError。
    """
```

为什么 `poll` 是默认：一次性查询永远不会让任何工具调用阻塞超过几十毫秒，对长流程（审批、过夜等待）是安全的。`wait` 模式必须由 LLM 显式选择，并且超时不会"静默退回 pending"——而是 ToolError，强制 LLM 来一次决策。

### 4.3 反馈 payload 形状

```json
{
  "user_comments": [
    {
      "target_id": "hero-title",
      "element_html_hint": "<h1 data-ai-id=\"hero-title\" class=\"text-3xl\">旧标题</h1>",
      "instruction": "改成赛博朋克风格"
    }
  ],
  "user_form_inputs": [
    {
      "ai_id": "project-name",
      "label": "项目名称",
      "name": null,
      "type": "text",
      "value": "用户填写的新名字"
    }
  ]
}
```

- `target_id` 是 AI 在 HTML 里写的 `data-ai-id`
- `element_html_hint` 是被批注节点的 outerHTML 截到 300 字符，给 AI 一点 grounding
- form 元素 checkbox/radio 的 `value` 是 bool；multi-select 是数组；其余是字符串
- `label` 由 host 推断：`label[for=id]` → 最近的 `<label>` 祖先 → 前一个兄弟 label

`ctx` 由 FastMCP 自动注入，LLM 不可见。

---

## 5. 服务端行为

### 5.1 内存模型 & Config

```python
@dataclass
class Config:
    base_url: str = "http://127.0.0.1:11002"
    stdio_mode: bool = True
    auto_open: bool = True
    # 每次 render_artifact 把 HTML 落地到 <archive_dir>/<sid>/<timestamp>.html。
    # 相对路径相对于进程 cwd。设为 None / 空串可关闭。
    archive_dir: str | None = "artifacts"

CONFIG = Config()

@dataclass
class SessionState:
    sid: str
    artifact_html: str | None = None
    sse_writer: SSEClient | None = None      # 0 or 1
    submit_event: asyncio.Event = field(default_factory=asyncio.Event)
    submitted_data: Any = None               # {user_comments, user_form_inputs}
    error: str | None = None
    opened: bool = False                     # 是否已 webbrowser.open 过

SESSIONS: dict[str, SessionState] = {}
```

`sid = ctx.session_id`（HTTP 模式 FastMCP 提供）或 `stdio_sid()`（stdio 模式进程级 UUID）。

**复用判定**：`is_reuse = state.sse_writer is not None` — SSE 还活着即视为浏览器 tab 在线。`http_routes.ui_events` 在 SSE 生成器 finally 里会把自己摘下 (`cur.sse_writer = None`),所以这是可靠信号。

### 5.2 HTTP 路由

| 路由 | 行为 |
|---|---|
| `GET /ui/{sid}` | 返回固定 HTML 壳。不校验 sid（沙包 sid 也能拿到壳，但没数据） |
| `GET /ui/{sid}/events` | 建立 SSE。若该 sid 已有连接，向旧连接发 `taken-over` 并关闭它；连上后立即把 `artifact_html`（如有）push 出去 |
| `POST /ui/{sid}/submit` | body 是 `{user_comments, user_form_inputs}`；写入 `submitted_data`；set `submit_event` |
| `POST /ui/{sid}/error` | body 是 `{type, message, stack?}`；写入 `error`；set `submit_event` |

### 5.3 工具体逻辑

```python
async def render_artifact(html, ctx):
    sid = ctx.session_id or stdio_sid()
    state = SESSIONS.setdefault(sid, SessionState(sid=sid))

    is_reuse = state.sse_writer is not None    # 浏览器 tab 还活着?

    state.artifact_html = html
    state.submit_event = asyncio.Event()
    state.submitted_data = None
    state.error = None

    _archive_artifact(sid, html)                # 落地一份,失败只 warn

    if is_reuse:
        await state.sse_writer.send("artifact", {"html": html})

    url = f"{CONFIG.base_url}/ui/{sid}"
    if CONFIG.stdio_mode and not state.opened and CONFIG.auto_open:
        webbrowser.open(url)
        state.opened = True

    # 复用分支:浏览器铁定在线,直接把"等用户提交"内置进 render,
    # 免得 AI 走 next_step 走偏(忘了 wait 或用了 poll)。
    if is_reuse:
        try:
            await asyncio.wait_for(state.submit_event.wait(), timeout=180)
        except asyncio.TimeoutError:
            raise ToolError("... user did not submit within 3 minutes ...")
        return {"sid": sid, "url": url, "reused_tab": True, **_finalize(state)}

    return {
        "sid": sid, "url": url,
        "status": "pending", "reused_tab": False,
        "next_step": _build_next_step(url, is_reuse=False),
    }


async def wait_user_feedback(sid, mode="poll", max_wait_seconds=60, ctx=None):
    state = SESSIONS.get(sid)
    if state is None:
        raise ToolError(f"unknown session: {sid}")
    if state.submit_event.is_set():
        return _finalize(state)
    if mode == "poll":
        return {"pending": True, "url": f"{CONFIG.base_url}/ui/{sid}"}
    # mode == "wait"
    wait = max(1, min(int(max_wait_seconds), 180))  # 3 分钟硬上限
    try:
        await asyncio.wait_for(state.submit_event.wait(), timeout=wait)
    except asyncio.TimeoutError:
        raise ToolError(
            f"wait_user_feedback(mode='wait') timed out after {wait}s. "
            f"Retry mode='wait' or switch to mode='poll'."
        )
    return _finalize(state)
```

设计要点：
- `render_artifact` **首次不阻塞**（瞬时返回 URL + `next_step`,让 LLM 第一时间把链接给用户），**复用时同步阻塞**（浏览器已在,内置 wait 省一次 round-trip）。两种分支都受 180s 硬上限保护。
- `next_step` 是文档级别的"行为引导"，把"问用户能不能打开 → 据此选 wait/poll"这一段经验直接喂进 LLM 的工具结果里，不依赖 system prompt。
- `wait_user_feedback`：
  - **默认 `mode="poll"`**：一次性查询，O(1) 返回，**不**消耗 `max_wait_seconds`。对长流程安全。
  - `mode="wait"`：用 `asyncio.wait_for` 在 server 端高效等待（不轮询），**3 分钟硬上限**，超时抛 ToolError 而非返回 pending——避免 LLM 进入"调用→pending→再调用"的隐形死循环。
- 浏览器 SSE 已连：直接 push 新 artifact；未连：依赖 stdio 自动开浏览器或 LLM 自己把 URL 念给用户。
- 错误从 `state.error` 取出后清空，避免同一个错误反复被读到。

### 5.4 Artifact Archive

每次 `render_artifact` 把 HTML 落地到 `<CONFIG.archive_dir>/<sid>/<YYYYMMDD-HHMMSS-mmm>.html`：

- 默认 `archive_dir = "artifacts"`（相对进程 cwd），设 `None` / 空串可关闭
- 失败不抛错（`logger.warning`），不阻塞主流程
- 文件名是毫秒时间戳，按字典序排序 = 渲染顺序
- 保存的是裸 artifact HTML（不带 host 壳），方便 debug "AI 这次给的到底是啥"
- `.gitignore` 已忽略 `artifacts/`

### 5.5 Session 清理

MCP 连接断开 → 删 `SESSIONS[sid]` + 关 SSE 通道。具体钩子用 FastMCP 的连接 lifespan（fallback 是周期性扫描死连接）。无超时、无 LRU、无持久化。

---

## 6. 浏览器端（Host）

### 6.1 设计原则：对 artifact 侵入最小

Host UI **完全收纳到右下角**，artifact 区域占满整个视口顶部到底部。无顶部 toolbar、无侧栏。所有 host 控件挤在右下角一个 ~320px 宽的小日记本里。

### 6.2 HTML 壳组成

一个 string 写在 `template.py`。包含：

- Tailwind play CDN（唯一外部依赖，供 AI artifact 写 utility class 时用；host 自身基本不用 Tailwind）
- 一段 `<style>` 定义所有 host 元素样式
- 一段 vanilla `<script>`：
  1. 创建 `EventSource(/ui/{sid}/events)`
  2. 监听 `artifact` 事件 → `container.innerHTML = html` + sanitize → 触发 host UI 重置
  3. 监听 `taken-over` / `end` → 显示对应状态页 + 清空 notebook
  4. 渲染异常 try/catch → POST `/ui/{sid}/error`
  5. 注册各种 host 控件的事件 handler

### 6.3 Host UI 组件

| 组件 | 位置 | 行为 |
|---|---|---|
| `#container` | 占满视口 | AI HTML 注入这里 |
| `#highlight` | 跟随鼠标 | 嗅探模式下,蓝色边框 + "📌 点击添加批注"角标盖在被 hover 的 `[data-ai-id]` 元素上 |
| `#badge-layer` | `fixed inset:0` | 每条已保存的批注在元素**内部右上角**投一个琥珀色编号徽章(`top: r.top + 4; left: r.left + r.width - 4; transform: translateX(-100%)`),与列表序号一致;点击徽章回到 notebook 编辑;scroll/resize 用 rAF 节流跟随 |
| `#notebook` > `.nb-page` | 右下角浮层 | "日记本纸页":头部"📓 批注 N"、横线纸感 body、可滚动条目列表、虚线分隔。**仅在批注模式开启时显示**;关闭则缩放淡出 |
| `#notebook` > `.nb-toolbar` | 右下角悬浮胶囊 | **始终可见**(artifact 加载后)。三个按钮:`[●批注中/批注]`(模式切换,蓝色脉冲指示开)、`[预览]`(打开预览 modal)、`[发送]`(直接提交) |
| `#preview-modal` | 居中 modal | 点"预览"后弹出,分组展示要发送的 `批注 N条 / 表单字段 N条`;有"关闭"和"确认发送"两个按钮 |
| `#submit-overlay` | 全屏遮罩 | 提交后铺一层 `rgba(249,250,251,0.86)` + `backdrop-filter: blur(3px)`,居中大字 "✉️ ● 已发送给 AI · 请保持此页面打开,后续内容会自动出现在这里"。z-index 9100,低于 notebook,所以用户仍可操作 toolbar |
| `#status` | 全屏 | 仅在还没收到 artifact / 会话结束等状态显示 |

### 6.4 批注流程

1. **进入批注**:右下角胶囊里的"批注"按钮默认 ON。开启时 `body.inspecting` 给 `#container` 套 crosshair cursor,日记本纸页弹出
2. **悬停**:鼠标在 artifact 上移动,`findAnnotatable()` 沿父链找到最近的 `[data-ai-id]`,绘制 `#highlight` 覆盖
3. **点击**:`e.preventDefault() + stopPropagation()`(阻止 input 等元素的默认行为),把 `editingId` 设为该 ai_id,日记本纸页弹出 textarea + 取消/保存/删除按钮
4. **保存**:写入 `annotations: Map<ai_id, {instruction, html_hint}>`,html_hint 是 `outerHTML.slice(0, 300)`
5. **回去编辑**:点列表条目或元素上的编号徽章,把 editingId 设回去
6. **预览**:把当前 annotations + harvested forms 渲染成结构化 list 到 modal
7. **发送**:`POST /ui/{sid}/submit` with `{user_comments, user_form_inputs}`,frozen container + 显示 submit-overlay

### 6.5 Host 状态

```
container.innerHTML  // 当前 artifact 的实际 DOM
annotations          // Map<ai_id, {instruction, html_hint}> (插入顺序 = 显示顺序)
hasArtifact          // 是否已接收过至少一份 artifact
isInspecting         // 批注模式开关(默认 true)
editingId            // 当前在编辑哪个 ai_id (null = 不在编辑)
```

每次新 artifact 进来 → 清空 `annotations` + 重置 `editingId` + 替换 innerHTML + 恢复 inspect ON + 隐藏 submit-overlay。

### 6.6 状态显示

| 状态 | 显示 |
|---|---|
| 连接中 | 居中 "正在连接..." |
| 等待 AI 发送内容 | 居中 "等待 AI 发送内容..." |
| Artifact 展示 | container + 右下角 notebook + (可选)highlight/badges |
| 已提交等下一份 | container 冻结 + 全屏半透明遮罩 + "已发送给 AI · 请保持此页面打开" |
| 渲染失败 | "⚠️ 渲染失败,等待新内容..."（详细 console.error）|
| 会话结束 | "✅ 对话已结束,可关闭此页面" |
| 被新标签替换 | "ℹ️ 此标签已在别处打开" |

### 6.7 安全 / Sanitize

- AI HTML 通过 `element.innerHTML` 注入：浏览器原生 **不会执行** 内嵌 `<script>` 标签
- inline `onclick="..."` 等事件会触发；host 注入后扫一遍 DOM 剥掉所有 `on*` 属性
- **加固**:`<style> / <link> / <base> / <meta> / <html> / <head> / <body> / <iframe> / <object> / <embed>` 这些标签即使被 AI 误塞进 artifact 也会**全局影响整页**(尤其 `<style>`),所以一并 `el.remove()`
- 不做 iframe sandbox、不做更深 sanitization：信任 AI 不会恶意（PRD §9）

### 6.8 Tailwind 边界

- Tailwind Play CDN 加载,主要服务 AI artifact(其 `<input class="block w-full rounded-md ...">` 这类全靠它)
- Host 自身基本不依赖 Tailwind(全部手写 CSS)。唯一例外是 `showStatus()` 里几个文字颜色 utility(`text-gray-500` 等)。即使 CDN 拉取失败,host 核心 UI 也能正常显示
- Tailwind Preflight 全局 reset 会影响 host 元素;host CSS 把所有 `border / background / padding / font` 显式写出,避免被 reset 弄坏

---

## 7. 部署

### 7.1 入口

```toml
[project.scripts]
agent-speak = "agent_speak.cli:main"
```

CLI：

```
agent-speak                                              # stdio,127.0.0.1:11002,自动开浏览器
agent-speak --port 11003                                 # 改端口
agent-speak --no-open                                    # 不自动开浏览器
agent-speak --http --public-url https://your.domain      # 公网模式,必传 --public-url
            --host 0.0.0.0 --port 8000
```

### 7.2 公网

- `--public-url` 必传，否则 fail-fast 退出
- HTTPS 用户自己用 Caddy / Nginx 反代
- Caddyfile：`ask.your.domain { reverse_proxy localhost:8000 }`
- MCP client config：`{"url": "https://ask.your.domain/mcp", "transport": "streamable-http"}`

### 7.3 本地 stdio

未发布前用本地路径（开发期）：
```json
{"mcpServers": {"agent-speak": {
  "command": "uv",
  "args": ["run", "--directory", "/abs/path/to/agent-speak", "agent-speak"]
}}}
```
发布到 PyPI 后：
```json
{"mcpServers": {"agent-speak": {"command": "uvx", "args": ["agent-speak"]}}}
```

---

## 8. 已知限制

- 服务重启所有进行中的会话丢失（archive 只是 debug 用的 HTML 快照,不能恢复 SessionState）
- MCP 连接中断 = 会话死亡（无重连恢复）
- 多浏览器标签：后开的赢，先开的被踢
- 用户跑路：阻塞调用(`wait_user_feedback(mode="wait")` 或复用模式的 `render_artifact`)180s 后 ToolError；轮询(`mode="poll"`)直接回 `pending`，LLM 自己决定要不要继续等
- 复用 `render_artifact` 同步阻塞 180s 可能超过 MCP 客户端默认 tool timeout（如 Claude Code ~60s）；客户端 abort 后调 `wait_user_feedback(sid)` 续上即可
- 公网部署多租户：通过不可猜测的 sid（UUID）隔离，无身份认证；sid 泄露 = 他人可看/可提交
- AI 写交互逻辑被禁掉——拖拽、tab、折叠、多步 wizard 不能在 artifact 里实现，只能拆成多轮 ask
- 仅支持现代浏览器（EventSource + `CSS.escape` + `backdrop-filter`，2023+ 主流浏览器都行）

---

## 9. 显式不做

- ❌ 服务端 schema 校验（自由派：AI 提交什么 AI 自己拿什么）
- ❌ iframe sandbox（信任 AI；不过 host 会剥掉 `<style>/<link>/<meta>` 等可全局污染的标签作为基础加固，见 §6.7）
- ❌ 持久化 / Redis / DB（artifact archive 只是给开发者看的 HTML 快照,不参与运行时状态）
- ❌ 横向扩展 / 多 worker process
- ❌ 自动 HTTPS / Let's Encrypt 集成
- ❌ 鉴权 / 登录
- ❌ React / 组件库（artifact 是纯 HTML）
- ❌ 富文本编辑器 / 图表库 / 表格库（按需再加）
- ❌ 浏览器中间态回传（不流式，仅 final submit）
- ❌ 多会话标签 / 标签内多视图
- ❌ AI 写 JS 交互（拖拽、tab、折叠等场景靠多轮反馈而非单页内交互）

---

## 10. 文件结构

```
agent-speak/
├── pyproject.toml
├── README.md
├── PRD.md
├── .gitignore           # 忽略 artifacts/(本地 HTML 快照)
├── src/agent_speak/
│   ├── __init__.py
│   ├── cli.py           # 参数解析 + stdio/http transport 切换
│   ├── server.py        # FastMCP 实例 + render_artifact + wait_user_feedback + _archive_artifact
│   ├── http_routes.py   # Starlette 路由
│   ├── session.py       # Config + SessionState + SESSIONS + SSEClient
│   └── template.py      # HTML 壳字符串 + vanilla host JS (notebook / badges / overlay)
├── examples/
│   └── artifact.html
└── artifacts/           # 运行时落地的每次 render HTML(<sid>/<ts>.html);git ignore
```

依赖（pyproject）：

```toml
dependencies = [
    "fastmcp>=3.3.1",
    "starlette>=1.0.0",
    "uvicorn>=0.47.0",
]
```

Vanilla host 把 React / Babel / @dnd-kit 全砍了，运行期只剩 Tailwind 一个 CDN。
