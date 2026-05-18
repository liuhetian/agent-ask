# agent-speak

让 LLM 用富 UI 而非 markdown 跟你对话——AI 输出一段静态 HTML,你在浏览器里批注、填表、提交,结构化反馈再回到 LLM。

## 这是什么

`agent-speak` 是一个 MCP server,把 AI 的输出从"长 markdown"变成"可交互页面"。它对外只有两个工具:

- `render_artifact(html)` — 把一段带 Tailwind 样式、带 `data-ai-id` 锚点的静态 HTML 推给用户的浏览器 tab。
- `wait_user_feedback(sid, mode, max_wait_seconds)` — 取回用户的提交。

核心约定:**AI 永远不写交互代码**(没有 `onClick`、`useState`、`<script>`)。所有交互——悬停高亮、批注、表单收集、提交——全部由 host(浏览器壳)负责。AI 写错了也只会"画得难看",绝不会卡住提交链路。

无 Redis、无数据库、无 Node、无 React。一个 Python 进程 + 约 200 行原生 JS。

![agent-ask](agent-ask.png)

## 用户能做什么

页面右下角永远有一个"日记本 + 工具栏"。工具栏从左到右是:

- **批注**(默认开启,开/关切换)——开启时,鼠标悬停在任何 `data-ai-id` 元素上会出蓝色高亮,**直接点击**即可在日记本里写一条批注。已批注的元素会在右上角内角嵌一个红色数字徽章,点徽章回去编辑或删除。
- **预览**——发送前看一眼到底要回传什么 `{user_comments, user_form_inputs}`。
- **发送**(绿色)——把批注 + 所有表单字段(`<input>` / `<textarea>` / `<select>` / `<checkbox>` …)打包回传给 AI。
- **?**——使用教程(首次也会自动弹一次)。

提交完页面**不会关闭**,顶上会盖一层"请保持页面打开"的提示,等下一稿推过来时自动消失。

## 两种渲染路径

调 `render_artifact(html)` 时,server 自己判断当前 sid 的 SSE 是否还活着:

### A) 首次渲染(或上一个 tab 已关闭)`reused_tab=false`

**立即返回** `{sid, url, status:"pending", next_step}`,**不阻塞**。返回里的 `next_step` 会指引 LLM:

1. 先把 URL 告诉用户、问"你现在就开还是事后再看"。
2. 据回答选后续姿势:
   - **事后看 / 转给别人**(默认,异步):什么工具都不调。等用户主动问"回了没",再调一次 `wait_user_feedback(sid)`(默认 `mode="poll"`,立即返回 `{feedback}` 或 `{pending: true, url}`)。
   - **现在就填**(交互):调 `wait_user_feedback(sid, mode="wait", max_wait_seconds=60)`,阻塞最多 60 秒(硬上限 180s);超时抛 `ToolError`,由 LLM 自己决定重试 `wait` 还是降级 `poll`。

### B) 复用 tab(SSE 已在线)`reused_tab=true`

用户上一稿提交后没关页面,新 artifact 通过 SSE 直接推过去——这时 `render_artifact` **自身就阻塞最多 3 分钟等用户提交**,然后直接返回 `{sid, url, reused_tab:true, feedback:{...}}`。LLM 不必再调 `wait_user_feedback`,也不必再把 URL 念一遍。

> 注意:3 分钟的同步阻塞可能超过某些 MCP 客户端的默认工具超时。如果客户端提前中止,服务端状态仍在——再用 `wait_user_feedback(sid, mode="wait")` 接回去即可。

## `wait_user_feedback` 两种模式

| mode | 行为 | 用途 |
| --- | --- | --- |
| `"poll"` (默认) | 立即返回 `{feedback}` 或 `{pending: true, url}` | 异步审批场景。**不要自动重试**,等用户来问。 |
| `"wait"` | 阻塞最多 `max_wait_seconds`(钳制在 1–180s)。提交则返回 `{feedback}`,**超时抛 `ToolError`**(不会返回 `{pending}`)。 | 用户当面、正盯着屏幕。超时强制 LLM 做明确选择。 |

## 启动

仓库根目录,装好 `uv`:

```bash
uv sync                                # 一次性,建好 .venv
uv run agent-speak                     # stdio 模式,127.0.0.1:11002,自动开浏览器
uv run agent-speak --port 11003        # 换端口
uv run agent-speak --no-open           # 别自动开浏览器
uv run agent-speak --http \            # streamable-http 模式
        --public-url https://ask.example.com \
        --host 0.0.0.0 --port 8000
```

发布到 PyPI 之后可以直接 `uvx agent-speak` / `uv tool install agent-speak`。

## 接入 MCP 客户端

### 本地 stdio

仓库内开发期:

```json
{
  "mcpServers": {
    "agent-speak": {
      "command": "uv",
      "args": ["run", "--directory", "/abs/path/to/agent-speak", "agent-speak"]
    }
  }
}
```

发布到 PyPI 之后:

```json
{ "mcpServers": { "agent-speak": { "command": "uvx", "args": ["agent-speak"] } } }
```

### 公网 streamable-http

把 `agent-speak --http --public-url https://ask.example.com ...` 跑在 TLS 反代后面(Caddyfile 例:`ask.example.com { reverse_proxy localhost:8000 }`),客户端配置:

```json
{ "url": "https://ask.example.com/mcp", "transport": "streamable-http" }
```

## 写一个 artifact

在 LLM 里直接传一段纯 HTML 字符串给 `render_artifact`:

```html
<div class="p-8 max-w-md mx-auto">
  <h1 data-ai-id="title" class="text-2xl font-semibold mb-4">
    新项目配置
  </h1>
  <label for="n" class="block text-sm mb-1">项目名</label>
  <input id="n" data-ai-id="project-name" type="text"
         class="block w-full border rounded px-3 py-2 mb-4" />
  <label class="flex items-center gap-2 text-sm">
    <input data-ai-id="want-auth" type="checkbox" /> 需要登录
  </label>
</div>
```

成功的提交返回:

```json
{
  "feedback": {
    "user_comments": [
      { "target_id": "title", "element_html_hint": "<h1 ...>新项目配置</h1>",
        "instruction": "改成更轻松的语气" }
    ],
    "user_form_inputs": [
      { "ai_id": "project-name", "label": "项目名", "name": null,
        "type": "text", "value": "agent-speak" },
      { "ai_id": "want-auth", "label": "需要登录", "name": null,
        "type": "checkbox", "value": true }
    ]
  }
}
```

### `html` 参数的契约

- **纯 HTML**(通过 `innerHTML` 注入)。不能有 React、JSX、useState。
- **样式必须用 Tailwind 工具类**(CDN 已预加载)。`<style>` 块和 `<link rel="stylesheet">` 在注入时会被剥掉(否则会污染整页、冲掉 host 的工具栏/日记本),不要依赖它们。行内 `style="..."` 属性保留作为应急通道,但优先用 Tailwind。
- **HTML 里不能有交互**:`<script>`、`<iframe>`、`<object>`、`<embed>`、`<link>`、`<meta>`、`<base>`、`<html>`、`<head>`、`<body>` 这些标签注入时会被剥;所有 `on*` 属性(`onclick`、`onchange` …)也会被剥。所有交互都由 host 接管。
- 每个有意义的元素都加一个稳定、描述清晰的 `data-ai-id="kebab-case-id"`,host 通过它寻址、批注和回传。
- 每个 `<input>` / `<textarea>` / `<select>` 都配 `<label>`(包裹式或用 `for=` 都行),host 会自动把人类可读的标签和值绑在一起。
- 同一个 sid 复用同一个浏览器 tab——每次 `render_artifact` 都会**替换**上一份 artifact,清空已有批注和表单值。
- 提交后页面**故意不关**,显示"请保持此页面打开"。下一稿推过来时自动消失。

完整范例见 [`examples/artifact.html`](examples/artifact.html)。

## 局限

- 无持久化。重启后正在等的会话全丢。
- 一个 sid 只能有一个活跃浏览器 tab——后开的 tab 接管,先开的 tab 会被告知"已在别处打开"。
- 无鉴权。URL 里的 sid 是 UUID 强度的,猜不出来,但**任何拿到 URL 的人都能提交**。不要在公开场合贴出来。
- AI 不能写 JS 交互。拖拽、tab 切换、多步向导这类**必须**拆成多轮 artifact 交换(每次 `render_artifact` 都会替换前一份)。
- 浏览器要求支持 EventSource 与 `CSS.escape`(2023 年以后的现代浏览器都行)。
