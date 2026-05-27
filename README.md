# agent-speak

让 AI 用富 UI 而非 markdown 跟你对话——AI 输出一段静态 HTML,你在浏览器里批注、填表、提交,结构化反馈再回到 AI。

## 这是什么

`agent-speak` 是一个 MCP server,把 AI 的输出从"长 markdown"变成"可交互页面"。它对外只暴露两件事:

- **把一份 UI 推给用户**——AI 提交一段带 Tailwind 样式、带稳定锚点的静态 HTML,服务端送到对应用户的浏览器 tab 里。
- **取回用户的反馈**——用户填完表单、写完批注、点了发送之后,前端壳子把所有内容打包成结构化反馈回传给 AI。

核心约定:**AI 永远不写交互代码**(没有事件绑定、没有状态、没有脚本)。所有交互——悬停高亮、批注、表单收集、提交——全部由浏览器这一侧的壳子负责。AI 写错了也只会"画得难看",绝不会卡住提交链路。

无 Redis、无数据库、无 Node、无 React。一个 Python 进程 + 约 200 行原生 JS。

![agent-ask](agent-ask.png)

## 用户能做什么

页面右下角永远有一个"日记本 + 工具栏"。工具栏从左到右是:

- **批注**(默认开启,可开关)——开启时,鼠标悬停在任何 AI 锚定的元素上会出蓝色高亮,**直接点击**即可在日记本里写一条批注。已批注的元素会在右上角内角嵌一个红色数字徽章,点徽章回去编辑或删除。
- **预览**——发送前看一眼到底要回传什么。
- **发送**(绿色)——把所有批注和表单字段(输入框、文本域、下拉框、勾选框……)打包回传给 AI。
- **?**——使用教程(首次也会自动弹一次)。

提交完页面**不会关闭**,顶上会盖一层"请保持页面打开"的提示,等下一稿推过来时自动消失。

## 两种渲染路径

服务端每次推一份新 UI 时,会自己判断当前会话的浏览器 tab 是否还连着:

### A) 首次推送,或上次的 tab 已关闭

服务端**立即返回**待处理状态(只有 URL,还没有反馈),**不阻塞**。AI 收到后该做的事:

1. 先把 URL 告诉用户,问他"现在就开还是事后再看"。
2. 据回答选后续姿势:
   - **事后再看 / 转交别人**(默认,异步):什么工具都不调。等用户主动问"回了没",再去调取反馈工具(默认是"查一次就返回",立即给到当前进度)。
   - **现在就填**(交互):调取反馈工具的"同步等待"模式,阻塞最多 60 秒(硬上限 3 分钟);超时由 AI 自己决定是继续等,还是降级到"查一次就返回"。

### B) 复用上一个 tab(浏览器仍在线)

用户上一稿提交后没关页面,新一稿通过推送直接送上去——这时**推送本身就内置了等待**,最多挂 3 分钟等用户提交:

- 提交了:直接把反馈一并捎回来,AI 不必再调取反馈工具,也不必再把 URL 念一遍。
- 这 3 分钟用户没动:**仍然算推送成功**(不是失败、不是渲染挂掉),只是用户慢了一拍。返回里写明"render 成功,用户尚未提交,URL 不变",AI 自己决定是继续调取反馈工具等,还是把控制权交还给对话。

> 注意:这 3 分钟的同步阻塞可能超过某些 MCP 客户端的默认工具超时。如果客户端提前中止,服务端状态仍在——AI 再去调一次取反馈工具接回来即可。

## 取反馈工具的两种模式

| 模式 | 行为 | 用途 |
| --- | --- | --- |
| 查一次就返回(默认) | 立即返回:已提交则给反馈,否则给"还没提交 + URL" | 异步审批场景。**不要自动重试**,等用户来问。 |
| 同步等待 | 阻塞最多指定秒数(钳制在 1–180 秒)。提交则返回反馈;**超时抛错**(不返回"还没提交")。 | 用户当面、正盯着屏幕。超时强制 AI 做明确选择。 |

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

### 直接用公网托管版(最快)

不想自己跑,直接接已经部署好的实例:

```json
{
  "mcpServers": {
    "agent-ask": {
      "url": "https://agent-ask.liuhetian.work/mcp",
      "transport": "streamable-http"
    }
  }
}
```

加进你的 MCP 客户端配置(Claude Code、Claude Desktop 等)就能用。无需安装、无需端口、无需反代。

> 公网实例无鉴权,会话 URL 是 UUID 强度的——别在公开场合贴出来。介意隐私就跑本地 stdio。

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

## 写一份 UI

把一段纯 HTML 字符串交给推送工具,服务端就会把它送到用户的浏览器 tab 里:

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

用户提交后,反馈大概长这样:

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

### HTML 的几条契约

- **纯 HTML**(通过 innerHTML 注入),不能写 React / JSX / 任何状态。
- **样式只能用 Tailwind 工具类**(CDN 已预加载)。`<style>` 块和外链样式表会在注入时被剥掉(否则会污染整页、冲掉前端壳子),不要依赖。行内样式属性保留作为应急通道,但请优先用 Tailwind。
- **不能有任何交互代码**:`<script>`、`<iframe>`、`<object>`、`<embed>`、`<link>`、`<meta>`、`<base>`、`<html>`、`<head>`、`<body>` 这些标签注入时会被剥;所有事件属性(`onclick`、`onchange` ……)也会被剥。所有交互都由前端壳子接管。
- 每个有意义的元素都加一个稳定、描述清晰的 `data-ai-id="kebab-case-id"` 锚点,前端壳子通过它寻址、批注、回传。
- 每个表单输入都配一个 `<label>`(包裹式或用 `for=` 都行),前端壳子会自动把人类可读的标签和值绑在一起。
- 每次推送都会**替换**上一份 UI,清空已有批注和表单值。同一会话内复用同一个 tab。
- 用户提交后页面**故意不关**,只在顶部盖一层"请保持此页面打开"的提示,以便下一稿直接复用同一个 tab。

完整范例见 [`examples/artifact.html`](examples/artifact.html)。

## 局限

- 无持久化。重启后正在等的会话全丢。
- 一份会话只能对应一个活跃的浏览器 tab——后开的接管,先开的会被告知"已在别处打开"。
- 无鉴权。URL 里的会话标识是 UUID 强度的,猜不出来,但**任何拿到 URL 的人都能提交**。不要在公开场合贴出来。
- AI 不能写 JS 交互。拖拽、tab 切换、多步向导这类**必须**拆成多轮 UI 交换(每次推送都会替换前一份)。
- 浏览器要求支持事件源(EventSource)与 `CSS.escape`(2023 年以后的现代浏览器都行)。

## 感谢

[linux.do](https://linux.do)
