---
name: agent-ask
description: 复杂的交互时, 例如需要grill-me或者plan-mode做计划时可以用这个skill, 把内容渲染为html, 便于用户更好的交互和返回数据.
---

# 报纸海报式审核页排版 Skill

## 适用场景

当需要把一份已经定稿的中文大纲、提案、汇报说明或审核材料，整理成可快速过目的网页时，使用本技能。目标不是改写内容，而是通过更有节奏的文字排版，让材料像一张“报纸 / 海报式提案页”：大标题、有栏目、有重点、有留白。

## 设计风格

整体风格是复古报纸 / 海报风：米黄色纸张底色、近黑色粗线分隔、少量暗红作为章节标记，依靠大字号标题和强对比排版制造视觉冲击。

CSS 关键词：`editorial newspaper layout`、`vintage paper background`、`bold serif typography`、`thick black rules`、`muted red accents`、`poster-like hierarchy`。

## 排版原则

1. 内容不改写，只整理层级、分组和视觉节奏。
2. 第一屏必须明确说明材料是什么，例如“AI 工具实践分享大纲”。
3. 主标题可以大胆放大，副标题和摘要保持可读。
4. 大章节之间使用粗线分隔，形成报纸版面感。
5. 子项目不要滥用横线，优先通过换行、留白、标题粗细和列间距区分。
6. “目的”“总结”等辅助信息应低于主体结构的视觉权重。
7. 四个或多个主体部分应成为页面视觉重心，标题要大，栏目要清楚。
8. 关键观点可以用粗黑底或左侧粗竖线突出，但不要过多。
9. 如果用于 agent-ask 审核，每个语义块都要加稳定的 `data-ai-id`，方便批注。

## 推荐结构

1. Masthead：材料标签、预计时长、主标题、副标题、摘要。
2. Purpose：分享目的，字号低于主体部分，子项靠留白区分。
3. Timing：时间分配，可用小方块展示分钟数。
4. Structure：主体分享结构，是页面视觉核心。
5. Conclusion：总结和结束观点，字号适中，不抢主体。
6. Materials：预计展示材料，可用轻量方框列出。

## CSS 取向

- 背景色：`#f3efe4`
- 主文字：`#151515`
- 辅助文字：`#2e2a24` 或 `#595247`
- 点缀红：`#8a2f1b`
- 字体：优先使用宋体 / serif，如 `"Songti SC", "Noto Serif CJK SC", Georgia, serif`
- 线条：大分隔使用 `4px solid #151515`，小卡片边框使用 `2px solid #151515`
- 圆角：不使用或极少使用，保持报纸硬朗感

## agent-ask 注意事项

渲染到 agent-ask 时，只提交 plain HTML，不使用 `<script>`、内联事件或交互逻辑。所有可批注元素都应带 `data-ai-id`，命名稳定且语义化，例如：

agent-ask 的 artifact 容器可能不会按预期保留或应用 `<style>` 中的自定义 CSS。为了避免页面退化成纯文本，提交给 agent-ask 的版本应优先把视觉样式写成 Tailwind utility class，直接挂在元素的 `class` 属性上；不要依赖 `<style>`、`body` 样式、`:root` 变量或外部 CSS 来承载关键版式。

```html
<section data-ai-id="purpose-section">...</section>
<h3 data-ai-id="part-1-title">看了就能变强的通用小技巧</h3>
<p data-ai-id="closing-statement">思考可以部分外包，理解不能外包。</p>
```

## 质量检查

交付前检查：

- 标题是否明确包含材料类型，如“大纲”“方案”“提案”。
- 是否存在过多横线导致页面嘈杂。
- 主体结构是否比目的和结论更突出。
- 子项目标题是否足够醒目。
- 移动端是否能自然单列阅读。
- HTML 独立文件是否内置 CSS，可直接打开。
- agent-ask 页面是否实际呈现出报纸版式，而不是只显示未套样式的纯文本。
