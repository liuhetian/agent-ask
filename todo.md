# CSS 自由度提升 TODO

## 03 scope `<style>` — 优先做

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

## 01 @keyframes — 顺手做

从"完全没有动效"到"有克制的动效"是质变。报告类内容动效本就该克制，日常频率低于 03。

**实现：**
- [ ] set_session(css=...) 的解析器 `_FLAT_RULE` 识别 `@keyframes name { ... }` at-rule
- [ ] @keyframes 块**不加** `.artifact-root` 前缀（加了就坏），原样透传
- [ ] 引用端的选择器规则照常加 `.artifact-root` 前缀
- [ ] scope `<style>`（03）中同理：提取 @keyframes 块单独处理，不前缀化

**scope `<style>` 做了之后这条自动覆盖大半**——AI 直接在 `<style>` 里写 @keyframes 即可，set_session 侧的解析器扩展变成 nice-to-have。

## 02 @font-face — 改为"模版预置字体"

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
