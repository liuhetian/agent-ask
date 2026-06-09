# agent-speak

让 AI 用富 UI 而非 markdown 跟你对话——AI 输出一段静态 HTML,你在浏览器里批注、填表、提交,结构化反馈再回到 AI。

## 这是什么

`agent-speak` 是一个 MCP server,把 AI 的输出从"长 markdown"变成"可交互页面"。它对外暴露三件事:

- **注册皮肤(`set_session`)**——会话第一步。选一套内置模版(报纸 / 极简白 / 暗夜霓虹 / 柔和糖果 / 杂志大刊)或注册自定义 CSS,拿到要交给用户打开的 URL(打开后预热连接),并把模版的完整 CSS 源码、以及 `render_artifact` 的 HTML 写法契约一并回传给 AI 参考。
- **推一份 UI(`render_artifact`)**——AI 提交一段用 `ass-*` 语义类、带稳定锚点的静态 HTML,服务端推到用户已打开的 tab,然后**同步阻塞**等用户提交,一次工具调用就把反馈带回来(省掉一次大模型往返)。页面还没连上时**立即返回 URL、不空等**。
- **取回反馈(`wait_user_feedback`)**——render 超时还没等到时的续等 / 异步查询手段。

所有模版**共用同一组 `ass-*` 语义类**,所以换模版时 AI 的 HTML 一个字都不用改——切的只是皮肤。

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

## 渲染流程

固定顺序,没有"一次同步一次异步"的分支——心智模型统一:

### 1) `set_session`——选皮肤 + 给 URL + 发契约

会话开场调一次:选模版(默认 `报纸`)或传一段自定义 `css`。返回里有:

- `url`:**交给用户,让他现在就打开**。页面先显示"等待内容中",这一步把 SSE 连接预热好——之后每次 render 都能直接同步拿反馈。
- `preset_css`:所选模版的完整 CSS 源码(`@apply` 的实际内容),方便 AI 写自定义类时跟模版对齐。
- `render_html_contract`:`render_artifact` 的 `html` 参数怎么写(语义类清单、`data-ai-id` 锚点、提交规则)。这段契约**只在这里返回一次**,不塞进 render 的常驻 tool description,省 token。
- `available_templates`:可选模版清单。

可**反复调用**:中途加新类、换模版、`reset` 清空都行;用户页面已开的话,样式**热更新**,不重渲染。

### 2) `render_artifact`——推 UI + 同步等反馈

把 HTML 推到已打开的页面,然后**同步阻塞**最多 `max_wait_seconds`(默认 180、上限 180)等用户提交:

- **提交了**:返回 `{feedback}`。一次工具调用同时完成"推 + 收",不必再调别的工具。
- **超时 / 页面没连上**:返回 `{status:"pending", connected}`。`connected:true` = 页面在线、只是用户慢了一拍(**别重推**);`connected:false` = 用户还没打开 URL——**此时立即返回、不空等**,把 `url` 交给用户打开即可(artifact 已缓存,一打开就看到)。两种都用下面的 `wait_user_feedback` 接力。

> 注意:同步阻塞可能超过某些 MCP 客户端的默认工具超时。客户端提前中止时服务端状态仍在——再调一次 `wait_user_feedback` 接回来即可。

### 3) `wait_user_feedback`——续等

render 返回 `{pending}` 后接力等用户提交:阻塞最多 `max_wait_seconds`(默认 60、钳制在 1–180 秒)。提交则返回 `{feedback}`;**超时抛错**——这不是故障,artifact 还在页面上,想继续等再调一次即可(**别重推**)。

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

先 `set_session` 选好皮肤(它会把 `html` 写法契约一起返回),再把一段纯 HTML 交给 `render_artifact`——优先用 `ass-*` 语义类(跟所选模版风格统一,无需自己堆样式):

```html
<div class="ass-panel">
  <h1 data-ai-id="title" class="ass-h1">新项目配置</h1>
  <div class="ass-field">
    <label for="n" class="ass-label">项目名</label>
    <input id="n" data-ai-id="project-name" type="text" class="ass-input" />
  </div>
  <label class="ass-check-row">
    <input data-ai-id="want-auth" type="checkbox" /> 需要登录
  </label>
</div>
```

预设类清单:布局 `ass-panel`/`ass-section`/`ass-row`/`ass-col`;文字 `ass-h1`/`ass-h2`/`ass-hint`/`ass-code`/`ass-kbd`/`ass-divider`;表单 `ass-field`/`ass-label`/`ass-input`/`ass-textarea`/`ass-select`/`ass-check-row`;按钮 `ass-btn` + `ass-btn-primary`/`ass-btn-ghost`/`ass-btn-danger`;提示 `ass-alert` + `ass-alert-info`/`ass-alert-warn`/`ass-alert-danger`。需要新类就去 `set_session(css=...)` 注册,别在 HTML 里写 `<style>`。

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
- **样式优先用 `ass-*` 预设类**(模版已注入),其次 Tailwind 工具类(CDN 已预加载)。要自定义类去 `set_session(css=...)` 注册。`<style>` 块和外链样式表会在注入时被剥掉(否则会污染整页、冲掉前端壳子),不要在 HTML 里写。行内样式属性保留作为应急通道,但请优先用预设类。
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
