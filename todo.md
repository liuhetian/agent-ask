# TODO

## CSS 自由度提升

### 03 scope `<style>` — 优先做

最大增益项。允许 AI 在 HTML 里写 `<style>` 块，注入前自动 scope 化 + 安全过滤。

**实现：**
- [ ] sanitizeInjected() 不再删 `<style>`，改为提取内容做处理后重新注入
- [ ] 所有选择器自动加 `.artifact-root` 前缀
- [ ] at-rule（@media、@supports 等）保留外壳，内部选择器加前缀

**安全过滤：**
- [ ] 剥掉 `@import url(...)`（外链请求 → 隐私指纹/数据外泄）
- [ ] 过滤所有 `url()` 值（background、list-style、cursor 等属性中的外链请求）
- [ ] 禁 `position: fixed`（逃出 .artifact-root 容器 → 覆盖 host 工具栏 → 点击劫持）
- [ ] 封顶 `z-index`（防止叠在 host UI 之上，host 工具栏 z-index 9200+）
- [ ] 考虑是否也禁 `position: absolute`（在容器内 absolute 是合理的，但 escape 到容器外也有风险——如果容器没有 `position: relative` 就会逃逸；确认容器已有定位上下文即可放行）

**对 render_html_contract 的更新：**
- [ ] 告知 AI 可以写 `<style>`，会被自动 scope 化
- [ ] 说明 @import / url() / position:fixed / 高 z-index 会被过滤及原因

### 01 @keyframes — 顺手做

从"完全没有动效"到"有克制的动效"是质变。报告类内容动效本就该克制，日常频率低于 03。

**实现：**
- [ ] set_session(css=...) 的解析器 `_FLAT_RULE` 识别 `@keyframes name { ... }` at-rule
- [ ] @keyframes 块**不加** `.artifact-root` 前缀（加了就坏），原样透传
- [ ] 引用端的选择器规则照常加 `.artifact-root` 前缀
- [ ] scope `<style>`（03）中同理：提取 @keyframes 块单独处理，不前缀化

**scope `<style>` 做了之后这条自动覆盖大半**——AI 直接在 `<style>` 里写 @keyframes 即可，set_session 侧的解析器扩展变成 nice-to-have。

### 02 @font-face — 改为"模版预置字体"

原方案（开放 @font-face）增益最小、成本最高。改为模版侧预置：

**替代方案：**
- [ ] 每套模版预置 1-2 款自托管装饰字体（比如报纸模版加一款老宋体/黑体变体）
- [ ] 字体文件放 static 目录，模版 CSS 里写好 @font-face
- [ ] template_guide 里告知 AI 可用的 font-family 名称
- [ ] AI 直接 `font-family: "xxx"` 引用，零解析、零安全风险

---

**安全备忘：**

> "CSS 不能执行代码"≠"CSS 零安全风险"
>
> 两类非代码风险：
> 1. **外链请求**：@import / url() 可发起外链 → 隐私指纹、数据外泄
> 2. **视觉层劫持**：position:fixed + 高 z-index 逃出容器 → 覆盖 host 提交按钮 → 点击劫持
>
> agent-speak 的信任模型是"AI 只写死内容，所有提交只走 host 绿色发送按钮"。
> 放开 CSS 时必须确保这个基础不被动摇。

---

## 复制 Markdown 方案（待定）

在设置面板加"复制 Markdown"按钮，把 artifact HTML 转回 Markdown 复制到剪贴板。

**技术方案:**
1. CDN 加载 Turndown.js (7.2.0) — HTML→Markdown 转换库
2. 设置面板"导出"行下方加一行"复制" → "复制 Markdown"按钮
3. 渲染前用 `rawArtifactHtml` 保存原始 HTML（mermaid/hljs 处理前的干净版本）
4. Mermaid 渲染前把源码存到 `data-mermaid-src` 属性，转换时还原为 ` ```mermaid ` 代码块
5. 自定义 Turndown 规则:
   - `pre.mermaid` → fenced code block (```mermaid)
   - `img-ai` → `![alt](src)`
   - `table` → GFM 表格（自写规则，不依赖 turndown-plugin-gfm）
   - 剥离 `data-ai-id` 等 host 属性
6. 剪贴板不可用时降级为下载 `.md` 文件

---

## 带外 HTTP 增量编辑方案（远程部署，待实现）

解决"改几个字要重新生成整份 HTML"——大文档多轮批注时，每轮全量重发 HTML 的输出 token 浪费。

**前提：聚焦远程 HTTP 模式**（agent-ask.liuhetian.work）。本地 stdio 共享文件系统的场景已有成熟方案（如 codex 自带批注），不做。

### 关键结论

远程 server 读不到本地磁盘，且 MCP tool 参数只能传字符串/JSON、传不了文件字节。所以 **`render_artifact(file=路径)` 不可行**。正确通道是**带外 HTTP**：HTML 字节走 curl 直传 server，绕开 LLM 输出流（复用现有图片上传 `/api/{sid}/upload` 的模式）。

### 三通道分工（最终架构，谁都不抛弃）

| 通道 | 职责 | 甜区 |
|---|---|---|
| `render_artifact(html=)` | 全量送入：传参零 shell 转义、自带推+等+收 | 首稿、短内容、大改 |
| curl 阻塞 `POST /api/{sid}/render` | 在已存原文上做增量 diff，server 阻塞、响应体带回 feedback | 大文档 + 局部小改 + 多轮 |
| `wait_user_feedback` | 取已持久化的 feedback | 两条路线超时后的接力兜底 |

**选路判据** `H − D > C`（H=全量 HTML 大小，D=改动 diff 量，C=curl 路线多出的往返开销）：
- H 大、D 小（长文档局部小改）→ curl
- H 小（短内容）或 D≈H（接近重写）→ render 覆盖
- 决策权交给 AI（它知道 H 和 D），不全压一边

### curl 改动工作流（大文档甜区）

1. `curl -s .../api/{sid}/artifact -o .html-render/{sid}.html` —— 拉 server 已存原文到本地（绕开 token；**惰性**：要改才下，一稿过不碰文件系统）
2. AI `Read` 定位 → `Edit` 改几行（只输出 diff）
3. `curl --data-binary @file POST .../api/{sid}/render` —— server 阻塞等提交、响应体带回 feedback（一次 Bash 调用完成推+等+收，**不需再调 wait**）

成本：curl 路线 = Edit + curl 阻塞 = 2 次往返；render 覆盖 = 1 次往返。

### 实现要点

- [ ] 新增上传 `POST /api/{sid}/render`：读 body(text/html) → 存 `state.artifact_html` → `_archive_artifact` → SSE 推 → 阻塞等 `submit_event` → 响应体返回 feedback（超时返回 pending）
- [ ] 新增下载 `GET /api/{sid}/artifact`：返回 `state.artifact_html` **原文**（带 img-ai / ass-* 类，不是 `/export` 那种图片内联后的成品）
- [ ] **长度阈值触发引导**：`render_artifact` 收到的 `len(html)` ≥ 阈值时，返回结果里附带「切 curl 工作流」引导——含下载命令（`curl -s …/artifact -o 本地文件`）+ Edit 提示 + 上传命令（`curl --data-binary @文件 POST …/render`）+ 可推导的 render_url / artifact_url。这是 B 型即时提醒（见下「触发与可达性」），与 contract 常驻规则互为冗余。**阈值起点建议 8000 字符**（`len(html)`，混合中文 HTML ≈ 3–4K token；更短的重发成本低、用 render 覆盖更省一次往返），上线后按实际观测在 6000–10000 间调整。
- [ ] 端点 URL **可推导**（sid 已知即可拼），set_session 顺带返回 render_url / artifact_url 即可，不需要 server 现生成下载链接
- [ ] contract（`render_html_contract`，常驻、只返回一次）新增：长内容改动走 下载→Edit→curl 工作流 + 选路判据
- [ ] sanitize **不用动**（剥 script/style/on* 在浏览器侧，server 只存和推）
- [ ] 信任模型：`/render`、`/artifact` 都是 sid 即能力——与现有图片端点一致，可接受

### 触发与可达性

- "该切 curl 工作流"**不能只活在某次返回值里**——终端批注（打断 wait）、上下文压缩、新会话都会让这种运行时一次性信号丢失。
- 解法：① 工作流规则沉淀进 **contract 常驻**；② 端点 URL **可推导**（sid 已知）；③ AI **自主**按 H、D 选路。server 的"过长提醒"只是冗余强化，不是唯一触发源。
- 若保留 server 提醒：用 **B 型**（render 收到过长就**立刻返回**引导、不等提交）而非 A 型（等提交后随 feedback 返回）——B 型引导在用户任何操作之前就送达 AI，对网页/终端都可达。

### 被否方案（存档备查）

- **`render_artifact(file=路径)`**：远程 server 读不到本地路径；MCP 参数传不了文件字节。
- **把 HTML 原文塞进 render 返回值让 AI 落盘**：原文进 AI 输入 token，且 AI 还得 `Write` 才能落盘=输出 token，**双亏**。
- **过长就拒绝渲染、立刻让客户端重来**：白烧首稿输出 token + 流程更复杂（server 要回退、客户端要重发）。修正：server 收到时 HTML 已在手（`state.artifact_html`），照常渲染即可，不该拒绝。
- **全部走 curl 抛弃 render**：首稿 curl 是纯亏——HTML 现生成、不在文件里，inline 进命令是 shell 转义地狱 + 全量 token，先 Write 落盘又是全量 token + 多一次调用。render 传参零转义、一次搞定。（curl 阻塞确实能带回 feedback，"等+收"非 render 独有；但"首稿全量送入"render 不可替代。）
