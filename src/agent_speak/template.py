"""浏览器 HTML 壳 + 纯 vanilla JS host。

Host 的核心职责:
- 自动锚点:AI 写普通 HTML 即可,不必手写 data-ai-id。注入后 host 给白名单内
  尚未带锚点的元素补一个会话内唯一的 data-ai-id(见 ensureAnchors),让任意有
  意义的元素都能被批注;AI 自己写的 data-ai-id 优先保留。
- DOM Inspector:右下角日记本里的"批注"开关(默认开),开启时悬停 data-ai-id
  节点显示蓝色高亮 + 提示,点击进入编辑;关闭仅停掉嗅探,日记本本身始终在。
- 日记本:右下角的小本子,始终可见。一条条记录,空也是本子。底部动作:
  发送(走预览弹窗确认流程)。
- 元素徽章:每条已保存的批注在元素内部右上角投一个黄色数字徽章
  (放在元素内部以避免靠边时被裁掉),点徽章即可回去编辑。
- Uncontrolled Form Harvest:扫描 input/textarea/select。
- 安全:innerHTML 注入后剥掉 on* 内联事件。
- 顶部不再有 toolbar,对 artifact 侵入最小。
- 提交后展示"请保持此页面打开"横幅,下一份 artifact 推过来时自动消失。
"""
from __future__ import annotations

import re

from .presets import (
    CHROME_THEMES,
    DEFAULT_TEMPLATE,
    IMAGE_STYLE_GUIDES,
    MERMAID_THEMES,
    MERMAID_THEME_VARS,
    TEMPLATES,
    TEMPLATE_GUIDES,
    chrome_vars_css,
    image_style_guide,
    mermaid_configs_json,
    mermaid_init_config,
    template_css,
    template_guide,
)


# 项目 logo(见 assets/logo.svg)的 base64,内联进 <head> 当 favicon——
# 渲染页面 / 导出 HTML 的浏览器标签页都打这个图标,不额外发请求。
LOGO_FAVICON_B64 = (
    "PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA2NCA2NCIgZml"
    "sbD0ibm9uZSI+PGRlZnM+PG1hc2sgaWQ9ImMiPjxyZWN0IHg9IjExIiB5PSIxMyIgd2lkdGg9IjQyIiBoZW"
    "lnaHQ9IjMwIiByeD0iMTMiIGZpbGw9IiNmZmYiLz48cGF0aCBkPSJNMjMgNDAgUTE2IDUwIDEyLjUgNTEgU"
    "TE1LjUgNDYuNSAxOS41IDQxLjUgWiIgZmlsbD0iI2ZmZiIvPjxwYXRoIGQ9Ik0yOCAyMiBMMjMuNSAyOCBM"
    "MjggMzQiIHN0cm9rZT0iIzAwMCIgc3Ryb2tlLXdpZHRoPSIzIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN"
    "0cm9rZS1saW5lam9pbj0icm91bmQiLz48cGF0aCBkPSJNMzYgMjIgTDQwLjUgMjggTDM2IDM0IiBzdHJva2"
    "U9IiMwMDAiIHN0cm9rZS13aWR0aD0iMyIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpva"
    "W49InJvdW5kIi8+PC9tYXNrPjwvZGVmcz48cmVjdCB3aWR0aD0iNjQiIGhlaWdodD0iNjQiIHJ4PSIxNiIg"
    "ZmlsbD0iI2VmZTZkNCIvPjxyZWN0IHg9IjkiIHk9IjExIiB3aWR0aD0iNDYiIGhlaWdodD0iNDQiIGZpbGw"
    "9IiMzYTMzMzAiIG1hc2s9InVybCgjYykiLz48cGF0aCBkPSJNMzUgMjEgTDI5IDM1IiBzdHJva2U9IiNjMj"
    "cwM2QiIHN0cm9rZS13aWR0aD0iMyIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIi8+PC9zdmc+"
)


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>agent-speak</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,__FAVICON_B64__">
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js"></script>
<style>
  /* ───── host 壳子(右下角工具栏 / 日记本 / 弹窗 / 遮罩)的主题 token ─────
     这里是默认值(报纸风)。set_session 选模版时,#ass-chrome-vars 槽会注入
     一段同名变量覆盖它(源码顺序更靠后 → 同特异性下生效),于是整个壳子的
     底色 / 文字 / 强调色 / 字体 / 圆角 / 阴影都跟着模版走。语义命名(surface /
     on-surface / accent…)让深浅主题自动正确:on-surface 既是文字也是描边,
     反白小块用 surface 做文字色,故暗色模版下也读得清。派生的浅淡叠色用
     color-mix 从这几个基色推导,不必逐个再开 token。 */
  :root {
    --asc-page:        #e9e0ca;   /* 页面整体底色(container 外) */
    --asc-surface:     #f4ecd8;   /* 壳子面板底色(工具栏 / 日记本 / 卡片) */
    --asc-on-surface:  #1a1a1a;   /* 面板上的文字 + 描边(主墨色) */
    --asc-accent:      #8b1e1e;   /* 强调色(序号 / 徽章 / 焦点环) */
    --asc-accent-2:    #6b1414;   /* 强调色更深一档(hover) */
    --asc-muted:       #6b6b6b;   /* 次要灰字 */
    --asc-field:       #fffaf0;   /* 输入框底色 */
    --asc-send:        #2d7148;   /* 发送按钮(全局唯一的"去"动作色) */
    --asc-send-2:      #1f5634;   /* 发送按钮 hover */
    --asc-font:        Georgia, "Songti SC", "Source Han Serif SC", "Noto Serif CJK SC", serif;
    --asc-radius:      0px;       /* 壳子圆角 */
    --asc-shadow:      4px 4px 0 var(--asc-on-surface);   /* 工具栏 / 日记本投影 */
    --asc-shadow-lg:   8px 8px 0 var(--asc-on-surface);   /* 弹窗投影 */
    --asc-dock-w:      290px;     /* 右下角一摞(日记本 / 控制栏 / 设置面板)统一宽度 */
  }

  html, body { height: 100%; margin: 0; }
  body { background: var(--asc-page); color: var(--asc-on-surface); font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; }

  #container {
    min-height: 100vh;
    padding: 32px;
    box-sizing: border-box;
  }
  #container[data-frozen="true"] { opacity: 0.5; pointer-events: none; }

  /* Crosshair while inspecting — scoped to artifact only */
  body.inspecting #container,
  body.inspecting #container * { cursor: crosshair !important; }

  /* Hover highlight overlay */
  #highlight {
    position: fixed; pointer-events: none; z-index: 8000;
    border: 2px solid var(--asc-accent); border-radius: 4px;
    background: color-mix(in srgb, var(--asc-accent) 8%, transparent);
    transition: top 80ms ease-out, left 80ms ease-out, width 80ms ease-out, height 80ms ease-out;
    display: none;
  }
  #highlight .label {
    position: absolute; top: -24px; left: -2px;
    background: var(--asc-accent); color: white;
    font-size: 11px; padding: 3px 8px;
    border-radius: 4px 4px 0 0;
    white-space: nowrap; font-weight: 500;
    display: flex; align-items: center; gap: 4px;
  }
  #highlight .label.bottom {
    top: auto; bottom: -24px;
    border-radius: 0 0 4px 4px;
  }

  /* Annotated nodes inside container — dark-red ink outline */
  #container [data-as-annotated="true"] {
    outline: 2px solid var(--asc-accent);
    outline-offset: 1px;
    border-radius: var(--asc-radius);
  }

  /* Floating number badges INSIDE the top-right corner of annotated elements */
  #badge-layer {
    position: fixed; inset: 0;
    pointer-events: none; z-index: 8500;
  }
  .anno-badge {
    position: absolute;
    width: 22px; height: 22px;
    border-radius: 50%;
    background: var(--asc-accent);
    color: var(--asc-surface);
    font-family: var(--asc-font);
    font-size: 11px; font-weight: 900;
    font-style: italic;
    display: flex; align-items: center; justify-content: center;
    border: 2px solid var(--asc-surface);
    box-shadow: 0 2px 6px color-mix(in srgb, var(--asc-on-surface) 30%, transparent);
    transform: translateX(-100%);
    pointer-events: auto;
    cursor: pointer;
    transition: transform 120ms, background 120ms;
  }
  .anno-badge:hover {
    transform: translateX(-100%) scale(1.18);
    background: var(--asc-accent-2);
  }
  .anno-badge.active {
    background: var(--asc-on-surface); color: var(--asc-surface);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--asc-on-surface) 30%, transparent), 0 2px 6px color-mix(in srgb, var(--asc-on-surface) 30%, transparent);
  }

  /* ───── bottom-right notebook (page + always-on toolbar) ───── */
  #notebook {
    position: fixed; bottom: 16px; right: 16px;
    z-index: 9200;
    display: none;           /* shown after first artifact arrives */
    flex-direction: column;
    align-items: flex-end;
    gap: 8px;
    font-size: 13px;
  }
  #notebook.visible { display: flex; }

  /* The page itself — only visible while inspect mode is on */
  .nb-page {
    box-sizing: border-box;
    width: var(--asc-dock-w);
    background: var(--asc-surface);
    border: 2px solid var(--asc-on-surface);
    border-radius: var(--asc-radius);
    box-shadow: var(--asc-shadow);
    overflow: hidden;
    display: flex; flex-direction: column;
    max-height: 60vh;
    color: var(--asc-on-surface);
    font-family: var(--asc-font);
    transform-origin: bottom right;
    transition: max-height 280ms ease, opacity 220ms ease,
                transform 220ms ease;
  }
  #notebook.mode-off .nb-page {
    max-height: 0; opacity: 0;
    transform: translateY(8px) scale(0.92);
    pointer-events: none;
    border-color: transparent;
    box-shadow: none;
  }

  /* Newspaper masthead */
  .nb-header {
    display: flex; align-items: baseline; justify-content: space-between;
    padding: 12px 16px 8px;
    background: transparent;
    border-bottom: 3px double var(--asc-on-surface);
    color: var(--asc-on-surface);
    user-select: none;
  }
  .nb-title {
    display: inline-flex; align-items: baseline; gap: 8px;
    font-family: inherit;
    font-weight: 900;
    font-size: 18px;
    line-height: 1;
    letter-spacing: 0.02em;
    text-transform: uppercase;
  }
  .nb-title > span:first-child { font-size: 16px; }
  .nb-count {
    font-family: inherit;
    font-style: italic;
    font-weight: 700;
    font-size: 14px;
    color: var(--asc-accent);
    background: transparent;
    padding: 0;
    min-width: 0;
  }

  /* Plain paper body — no lines, let the typography breathe */
  .nb-body {
    flex: 1;
    overflow: auto;
    min-height: 96px;
    background: transparent;
  }

  /* Edit area inside the notebook body */
  #edit-area {
    padding: 12px 16px;
    border-bottom: 2px solid var(--asc-on-surface);
    background: color-mix(in srgb, var(--asc-on-surface) 4%, transparent);
  }
  #edit-area.hidden { display: none; }
  #edit-area .target-id {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 10px;
    color: var(--asc-surface);
    background: var(--asc-on-surface);
    padding: 3px 8px;
    border-radius: var(--asc-radius);
    letter-spacing: 0.04em;
    margin-bottom: 8px; display: inline-block;
    max-width: 100%; overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap;
  }
  #edit-area textarea {
    width: 100%; height: 76px; box-sizing: border-box;
    border: 1px solid var(--asc-on-surface); border-radius: var(--asc-radius);
    padding: 8px;
    font-size: 13px; resize: vertical;
    font-family: inherit; color: var(--asc-on-surface);
    background: var(--asc-field);
  }
  #edit-area textarea:focus {
    outline: 0;
    border-color: var(--asc-accent);
    box-shadow: inset 0 0 0 1px var(--asc-accent);
  }
  #edit-area .row {
    display: flex; justify-content: space-between; align-items: center;
    margin-top: 8px; gap: 8px;
  }
  #edit-area button {
    border: 1px solid var(--asc-on-surface);
    border-radius: var(--asc-radius);
    padding: 5px 12px;
    font-family: inherit;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    cursor: pointer;
    background: transparent;
    color: var(--asc-on-surface);
  }
  #edit-area .delete {
    border-color: var(--asc-accent); color: var(--asc-accent);
  }
  #edit-area .delete:hover { background: var(--asc-accent); color: var(--asc-surface); }
  #edit-area .right-btns { display: flex; gap: 6px; }
  #edit-area .cancel:hover { background: color-mix(in srgb, var(--asc-on-surface) 8%, transparent); }
  #edit-area .save { background: var(--asc-on-surface); color: var(--asc-surface); }
  #edit-area .save:hover { background: var(--asc-accent); border-color: var(--asc-accent); }

  /* Notebook entries — newspaper article fragments */
  #anno-list .empty {
    padding: 26px 18px;
    text-align: center;
    color: var(--asc-muted); font-size: 13px; line-height: 1.7;
    font-style: italic;
  }
  #anno-list .item {
    display: flex; gap: 12px;
    padding: 10px 16px;
    cursor: pointer;
    border-bottom: 1px solid color-mix(in srgb, var(--asc-on-surface) 18%, transparent);
    transition: background 100ms;
  }
  #anno-list .item:last-child { border-bottom: 0; }
  #anno-list .item:hover { background: color-mix(in srgb, var(--asc-on-surface) 5%, transparent); }
  #anno-list .item.editing { background: color-mix(in srgb, var(--asc-accent) 10%, transparent); }
  #anno-list .num {
    flex-shrink: 0;
    font-family: inherit;
    font-weight: 900;
    font-size: 22px;
    line-height: 1;
    color: var(--asc-accent);
    min-width: 22px;
    padding-top: 2px;
    font-style: italic;
  }
  #anno-list .item.editing .num { color: var(--asc-on-surface); }
  #anno-list .item-body { flex: 1; min-width: 0; }
  #anno-list .aid {
    font-family: ui-monospace, monospace;
    font-size: 10px;
    color: var(--asc-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 2px;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  #anno-list .text {
    font-family: inherit;
    font-size: 14px;
    color: var(--asc-on-surface);
    line-height: 1.5;
    overflow: hidden; text-overflow: ellipsis;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  }

  /* Newspaper-stamp toolbar: solid block with hard offset shadow */
  .nb-toolbar {
    display: flex; align-items: stretch;
    box-sizing: border-box;
    width: fit-content;   /* 随按钮数量伸缩;右对齐 → 展开时向左加长(日记本/设置面板用 JS 跟随其宽度) */
    background: var(--asc-surface);
    border: 2px solid var(--asc-on-surface);
    border-radius: var(--asc-radius);
    box-shadow: var(--asc-shadow);
    font-family: var(--asc-font);
    overflow: hidden;
  }
  .nb-toolbar > * + * { border-left: 1px solid var(--asc-on-surface); }
  .nb-toolbar button {
    background: transparent;
    border: 0;
    border-radius: 0;
    padding: 18px 5px;
    font-family: inherit;
    font-size: 12px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.10em;
    color: var(--asc-on-surface);
    cursor: pointer;
    display: inline-flex; align-items: center; justify-content: center; gap: 5px;
    line-height: 1;
    white-space: nowrap;   /* 永不换行,避免被挤压成两行而抬高整条栏 */
  }
  .nb-toolbar button:hover { background: color-mix(in srgb, var(--asc-on-surface) 8%, transparent); }
  .nb-toolbar button:focus { outline: none; }
  .nb-toolbar button:focus-visible {
    outline: 2px solid var(--asc-accent);
    outline-offset: -2px;
  }

  /* 三个主按钮(批注 / 图片 / 发送)固定等宽,不随展开收起伸缩,始终稳定不被挤压 */
  #mode-btn, #img-panel-btn, #preview-send-btn {
    flex: 0 0 84px;
    justify-content: center;
  }
  #mode-btn .indicator {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--asc-muted); flex-shrink: 0;
  }
  #mode-btn.on {
    background: var(--asc-on-surface); color: var(--asc-surface);
  }
  #mode-btn.on:hover { background: color-mix(in srgb, var(--asc-on-surface), #ffffff 14%); }
  #mode-btn.on .indicator {
    background: var(--asc-surface);
    animation: pulse-paper 1.6s infinite;
  }
  @keyframes pulse-paper {
    0%, 100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--asc-surface) 70%, transparent); }
    50%      { box-shadow: 0 0 0 5px transparent; }
  }

  /* PREVIEW-SEND — the green primary action, fills remaining space */
  #preview-send-btn {
    flex: 0 0 84px;
    justify-content: center;   /* "发送"二字水平居中 */
    background: var(--asc-send);
    color: var(--asc-surface);
  }
  #preview-send-btn:not(:disabled):hover { background: var(--asc-send-2); }
  #preview-send-btn:disabled {
    background: color-mix(in srgb, var(--asc-on-surface) 12%, transparent);
    color: color-mix(in srgb, var(--asc-on-surface) 32%, transparent);
    cursor: not-allowed;
  }
  #preview-send-btn:disabled:hover { background: color-mix(in srgb, var(--asc-on-surface) 12%, transparent); }

  /* help-btn font tweaks (base handled by #settings-btn, #help-btn block above) */
  #help-btn { font-style: italic; font-weight: 900; }

  /* More toggle — collapse/expand extra buttons (inherits .nb-toolbar button base) */
  #more-btn {
    padding: 0 12px;
    color: var(--asc-muted);
    transition: transform 180ms;
  }
  #more-btn:hover { color: var(--asc-on-surface); }
  .nb-toolbar .nb-extra { display: none; }
  .nb-toolbar.expanded .nb-extra { display: inline-flex; }
  .nb-toolbar.expanded #more-btn { transform: scaleX(-1); }

  /* Extra buttons (⚙ ?) — same metrics as other toolbar buttons */
  #settings-btn,
  #help-btn {
    padding: 0 12px;
    color: var(--asc-muted);
  }
  #settings-btn:hover,
  #help-btn:hover { color: var(--asc-on-surface); }

  /* Settings panel — fixed, floating above the toolbar */
  #settings-panel {
    position: fixed;
    bottom: 62px; right: 16px;
    z-index: 9200;
    box-sizing: border-box;
    width: var(--asc-dock-w);
    background: var(--asc-surface);
    border: 2px solid var(--asc-on-surface);
    border-radius: var(--asc-radius);
    box-shadow: var(--asc-shadow);
    font-family: var(--asc-font);
    padding: 12px 16px;
    color: var(--asc-on-surface);
  }
  #settings-panel.hidden { display: none; }
  .sp-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 8px 0;
  }
  .sp-row + .sp-row {
    border-top: 1px solid color-mix(in srgb, var(--asc-on-surface) 18%, transparent);
  }
  .sp-row label {
    font-weight: 700; font-size: 13px;
  }
  .sp-row select {
    border: 1px solid var(--asc-on-surface); border-radius: var(--asc-radius);
    background: var(--asc-field); color: var(--asc-on-surface);
    padding: 4px 8px; font-size: 12px; font-family: inherit; font-weight: 700;
  }

  /* ───── 模拟下拉框(.asc-select):JS 把原生 <select> 隐藏后生成,
     外观完全跟随壳子主题 token,与导出按钮等控件风格统一 ───── */
  .asc-select { position: relative; width: 150px; font-family: inherit; }
  /* trigger 与导出按钮统一为 32px 高(box-sizing 含边框),两栏等高 */
  .asc-select .asc-cs-trigger {
    display: flex; align-items: center; justify-content: center;
    position: relative;
    box-sizing: border-box;
    width: 100%; height: 32px;
    padding: 0 10px;
    border: 1px solid var(--asc-on-surface); border-radius: var(--asc-radius);
    background: var(--asc-field); color: var(--asc-on-surface);
    font-family: inherit; font-size: 12px; font-weight: 900; line-height: 1.4;
    text-transform: uppercase; letter-spacing: 0.08em;
    cursor: pointer;
  }
  .asc-select.open .asc-cs-trigger {
    border-color: var(--asc-accent);
    box-shadow: inset 0 0 0 1px var(--asc-accent);
  }
  .asc-select .asc-cs-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .asc-select .asc-cs-arrow {
    position: absolute; right: 10px;
    width: 0; height: 0;
    border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-top: 6px solid var(--asc-on-surface);
    transition: transform 150ms;
  }
  .asc-select.open .asc-cs-arrow { transform: rotate(180deg); }
  /* 面板在右下角,菜单向上展开(bottom 锚定 trigger 顶边),避免被视口底部裁掉;无阴影 */
  .asc-select .asc-cs-menu {
    position: absolute; left: 0; right: 0; bottom: calc(100% + 4px);
    z-index: 30; margin: 0; padding: 0; list-style: none;
    border: 2px solid var(--asc-on-surface); background: var(--asc-surface);
    max-height: 240px; overflow-y: auto; display: none;
    scrollbar-width: thin; scrollbar-color: var(--asc-on-surface) var(--asc-surface);
  }
  .asc-select.open .asc-cs-menu { display: block; }
  /* 模拟滚动条:跟随主题墨色 */
  .asc-select .asc-cs-menu::-webkit-scrollbar { width: 10px; }
  .asc-select .asc-cs-menu::-webkit-scrollbar-track {
    background: var(--asc-surface); border-left: 2px solid var(--asc-on-surface);
  }
  .asc-select .asc-cs-menu::-webkit-scrollbar-thumb {
    background: var(--asc-on-surface); border: 2px solid var(--asc-surface);
  }
  .asc-select .asc-cs-menu::-webkit-scrollbar-thumb:hover { background: var(--asc-accent); }
  .asc-select .asc-cs-option {
    padding: 8px 10px; font-size: 12px; font-weight: 900;
    text-transform: uppercase; letter-spacing: 0.08em; text-align: center;
    color: var(--asc-on-surface); cursor: pointer;
    border-bottom: 1px solid color-mix(in srgb, var(--asc-on-surface) 15%, transparent);
    white-space: nowrap;
  }
  .asc-select .asc-cs-option:last-child { border-bottom: 0; }
  .asc-select .asc-cs-option.selected { color: var(--asc-accent); }
  .asc-select .asc-cs-option:hover,
  .asc-select .asc-cs-option.active { background: var(--asc-on-surface); color: var(--asc-surface); }

  /* 导出按钮:与上方下拉框同宽(150)同高(32),两栏右侧控件左右边缘对齐 */
  #export-btn {
    box-sizing: border-box;
    width: 150px; height: 32px;
    display: inline-flex; align-items: center; justify-content: center;
    padding: 0 14px;
  }

  /* ───── tutorial modal — newspaper poster with 3 tabs + knockout caps ───── */
  #tutorial-modal {
    position: fixed; inset: 0; z-index: 9700;
    display: flex; align-items: center; justify-content: center;
    background: color-mix(in srgb, var(--asc-on-surface) 55%, transparent);
    backdrop-filter: blur(2px);
    -webkit-backdrop-filter: blur(2px);
    padding: 24px;
  }
  #tutorial-modal.hidden { display: none; }
  #tutorial-modal .t-card {
    background: var(--asc-surface);
    width: min(640px, 100%);
    max-height: 88vh;
    border: 3px solid var(--asc-on-surface);
    border-radius: var(--asc-radius);
    box-shadow: var(--asc-shadow-lg);
    display: flex; flex-direction: column;
    overflow: hidden;
    color: var(--asc-on-surface);
    font-family: var(--asc-font);
  }

  /* Compact head */
  #tutorial-modal .t-head {
    display: flex; align-items: flex-start; justify-content: space-between;
    padding: 16px 24px 12px;
    border-bottom: 4px double var(--asc-on-surface);
  }
  #tutorial-modal .t-kicker {
    display: block;
    font-size: 10px; font-weight: 700;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    color: var(--asc-accent);
    margin-bottom: 4px;
  }
  #tutorial-modal .t-title {
    font-weight: 900;
    font-size: 22px;
    line-height: 1.1;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    display: block;
  }
  #tutorial-modal .t-close {
    border: 0; background: transparent; cursor: pointer;
    font-family: var(--asc-font);
    font-size: 26px; color: var(--asc-on-surface); line-height: 1;
    padding: 0 4px;
  }
  #tutorial-modal .t-close:hover { color: var(--asc-accent); }

  /* Tab strip — 3 equal cells, active = knockout */
  #tutorial-modal .t-tabs {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    border-bottom: 3px solid var(--asc-on-surface);
    background: var(--asc-surface);
  }
  #tutorial-modal .t-tab {
    background: transparent;
    border: 0;
    border-right: 1px solid color-mix(in srgb, var(--asc-on-surface) 20%, transparent);
    padding: 14px 8px 12px;
    cursor: pointer;
    display: flex; flex-direction: column; align-items: center; gap: 4px;
    font-family: inherit;
    color: var(--asc-on-surface);
    transition: background 120ms;
  }
  #tutorial-modal .t-tab:last-child { border-right: 0; }
  #tutorial-modal .t-tab:hover { background: color-mix(in srgb, var(--asc-on-surface) 5%, transparent); }
  #tutorial-modal .t-tab-num {
    font-family: var(--asc-font);
    font-style: italic;
    font-weight: 900;
    font-size: 26px;
    line-height: 1;
    color: var(--asc-accent);
  }
  #tutorial-modal .t-tab-label {
    font-weight: 800;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: var(--asc-on-surface);
  }
  #tutorial-modal .t-tab.active { background: var(--asc-on-surface); }
  #tutorial-modal .t-tab.active .t-tab-num,
  #tutorial-modal .t-tab.active .t-tab-label {
    color: var(--asc-surface);
  }
  #tutorial-modal .t-tab:focus { outline: none; }
  #tutorial-modal .t-tab:focus-visible {
    outline: 2px solid var(--asc-accent); outline-offset: -2px;
  }

  /* Body holds 3 panes, only .active visible */
  #tutorial-modal .t-body {
    flex: 1; overflow: auto;
    padding: 22px 28px 8px;
    font-size: 14.5px;
    line-height: 1.75;
  }
  #tutorial-modal .t-pane { display: none; }
  #tutorial-modal .t-pane.active { display: block; }

  /* Big drop-cap "阴字" block + pane heading */
  #tutorial-modal .t-pane-grid {
    display: grid;
    grid-template-columns: 80px 1fr;
    gap: 18px;
    align-items: start;
    margin-bottom: 14px;
  }
  #tutorial-modal .t-numblock {
    width: 80px; height: 80px;
    background: var(--asc-on-surface);
    color: var(--asc-surface);
    font-family: var(--asc-font);
    font-style: italic;
    font-weight: 900;
    font-size: 44px;
    line-height: 1;
    display: flex; align-items: center; justify-content: center;
  }
  #tutorial-modal .t-pane-content { padding-top: 4px; }
  #tutorial-modal .t-pane-content .t-tag {
    display: inline-block;
    font-size: 10px; font-weight: 700;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: var(--asc-accent);
    margin-bottom: 4px;
  }
  #tutorial-modal .t-pane-content h4 {
    font-family: inherit;
    font-weight: 900;
    font-size: 22px;
    line-height: 1.15;
    letter-spacing: 0.02em;
    margin: 0;
  }

  /* Pane text — sparse, generous */
  #tutorial-modal .t-pane p {
    margin: 12px 0;
    font-size: 14.5px;
    line-height: 1.8;
  }
  #tutorial-modal .t-pane p.highlight {
    border-left: 4px solid var(--asc-accent);
    padding: 4px 0 4px 14px;
    margin: 16px 0;
    font-style: italic;
    color: var(--asc-on-surface);
  }
  #tutorial-modal .t-pane p.huge {
    font-size: 32px;
    font-weight: 900;
    line-height: 1.2;
    letter-spacing: 0.02em;
    margin: 18px 0;
    background: var(--asc-on-surface);
    color: var(--asc-surface);
    padding: 14px 18px;
    display: inline-block;
  }
  #tutorial-modal .t-pane strong { font-weight: 900; }
  #tutorial-modal .t-pane em { font-style: italic; color: var(--asc-muted); }
  #tutorial-modal .t-pane a {
    color: var(--asc-accent);
    font-style: italic;
    text-decoration: underline;
    text-decoration-color: color-mix(in srgb, var(--asc-accent) 40%, transparent);
  }
  #tutorial-modal .t-pane a:hover { text-decoration-color: var(--asc-accent); }
  #tutorial-modal .t-pane .t-source {
    font-size: 12px; color: var(--asc-muted);
    font-style: italic; margin-top: 8px;
  }

  /* Step list inside tab 02 — big italic red numerals */
  #tutorial-modal .t-steps {
    list-style: none;
    margin: 18px 0 0; padding: 0;
    counter-reset: step;
  }
  #tutorial-modal .t-steps li {
    display: grid;
    grid-template-columns: 48px 1fr;
    column-gap: 14px;
    row-gap: 2px;
    padding: 14px 0;
    border-bottom: 1px solid color-mix(in srgb, var(--asc-on-surface) 18%, transparent);
    align-items: start;
  }
  #tutorial-modal .t-steps li:last-child { border-bottom: 0; }
  #tutorial-modal .t-steps li::before {
    counter-increment: step;
    content: counter(step);
    grid-column: 1;
    grid-row: 1 / span 2;
    align-self: start;
    font-family: var(--asc-font);
    font-style: italic;
    font-weight: 900;
    font-size: 36px;
    line-height: 1;
    color: var(--asc-accent);
    text-align: right;
  }
  /* Keep both <strong> and <span> in the wide right column */
  #tutorial-modal .t-steps li > * { grid-column: 2; }
  #tutorial-modal .t-steps li strong {
    display: block;
    font-size: 14px;
    font-weight: 900;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  #tutorial-modal .t-steps li span { color: var(--asc-on-surface); font-size: 13.5px; }

  /* Footer */
  #tutorial-modal .t-foot {
    display: flex; justify-content: flex-end; gap: 8px;
    padding: 14px 28px;
    border-top: 4px double var(--asc-on-surface);
    background: color-mix(in srgb, var(--asc-on-surface) 3%, transparent);
  }
  #tutorial-modal .t-ok {
    background: var(--asc-on-surface);
    color: var(--asc-surface);
    border: 2px solid var(--asc-on-surface);
    border-radius: var(--asc-radius);
    padding: 8px 22px;
    font-family: inherit;
    font-size: 12px; font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    cursor: pointer;
  }
  #tutorial-modal .t-ok:hover {
    background: var(--asc-accent);
    border-color: var(--asc-accent);
  }

  /* Settings pane */
  #tutorial-modal .t-settings { padding-top: 4px; }
  #tutorial-modal .t-setting-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 0;
    border-bottom: 1px solid color-mix(in srgb, var(--asc-on-surface) 18%, transparent);
  }
  #tutorial-modal .t-setting-row:last-child { border-bottom: 0; }
  #tutorial-modal .t-setting-row label {
    font-weight: 700; font-size: 14px;
  }
  #tutorial-modal .t-setting-row select {
    border: 1px solid var(--asc-on-surface); border-radius: var(--asc-radius);
    background: var(--asc-field); color: var(--asc-on-surface);
    padding: 5px 10px; font-size: 13px; font-family: inherit; font-weight: 700;
  }
  /* 导出按钮:tutorial-modal 与 settings-panel 共用同一套报纸风样式
     (此前选择器误限定在 #tutorial-modal 下,设置面板里的按钮拿不到字体) */
  .t-export-btn {
    background: var(--asc-on-surface); color: var(--asc-surface);
    border: 2px solid var(--asc-on-surface); border-radius: var(--asc-radius);
    padding: 5px 14px; font-family: inherit; font-size: 12px; font-weight: 900;
    text-transform: uppercase; letter-spacing: 0.08em; cursor: pointer;
  }
  .t-export-btn:hover {
    background: var(--asc-accent); border-color: var(--asc-accent);
  }
  .t-export-btn:disabled {
    opacity: 0.4; cursor: not-allowed;
  }
  .t-export-btn:disabled:hover {
    background: var(--asc-on-surface); border-color: var(--asc-on-surface);
  }

  /* ───── preview modal — same vintage palette ───── */
  #preview-modal {
    position: fixed; inset: 0; z-index: 9500;
    display: flex; align-items: center; justify-content: center;
    background: color-mix(in srgb, var(--asc-on-surface) 45%, transparent);
    backdrop-filter: blur(2px);
    padding: 24px;
  }
  #preview-modal.hidden { display: none; }
  #preview-modal .modal-card {
    background: var(--asc-surface);
    width: min(560px, 100%);
    max-height: 82vh;
    border: 3px solid var(--asc-on-surface);
    border-radius: var(--asc-radius);
    box-shadow: var(--asc-shadow-lg);
    display: flex; flex-direction: column;
    overflow: hidden;
    color: var(--asc-on-surface);
    font-family: var(--asc-font);
  }
  #preview-modal header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 16px 24px 12px;
    border-bottom: 3px double var(--asc-on-surface);
    font-family: inherit;
    font-weight: 900;
    font-size: 18px;
    text-transform: uppercase;
    letter-spacing: 0.02em;
    color: var(--asc-on-surface);
    background: transparent;
  }
  #preview-modal header .close {
    border: 0; background: transparent; cursor: pointer;
    font-family: var(--asc-font);
    font-size: 26px; color: var(--asc-on-surface); line-height: 1;
    padding: 0 4px;
    font-weight: 400;
  }
  #preview-modal header .close:hover { color: var(--asc-accent); }
  #preview-modal .modal-body {
    flex: 1; overflow: auto;
    padding: 14px 24px;
    font-size: 14px; line-height: 1.65;
  }
  #preview-modal footer {
    display: flex; justify-content: flex-end; gap: 8px;
    padding: 12px 24px;
    border-top: 3px double var(--asc-on-surface);
    background: color-mix(in srgb, var(--asc-on-surface) 3%, transparent);
  }
  #preview-modal footer button {
    border: 2px solid var(--asc-on-surface);
    border-radius: var(--asc-radius);
    padding: 6px 18px;
    font-family: inherit;
    font-size: 11px;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 0.10em;
    cursor: pointer;
    background: transparent;
    color: var(--asc-on-surface);
  }
  #preview-modal .modal-cancel:hover { background: color-mix(in srgb, var(--asc-on-surface) 8%, transparent); }
  #preview-modal .modal-send {
    background: var(--asc-on-surface);
    color: var(--asc-surface);
  }
  #preview-modal .modal-send:hover {
    background: var(--asc-accent); border-color: var(--asc-accent);
  }
  #preview-modal .section { margin-bottom: 14px; }
  #preview-modal .section h3 {
    font-family: inherit;
    font-size: 11px;
    font-weight: 900;
    color: var(--asc-accent);
    text-transform: uppercase;
    letter-spacing: 0.20em;
    margin: 8px 0 6px;
    padding-bottom: 4px;
    border-bottom: 2px solid var(--asc-on-surface);
  }
  #preview-modal .section .empty {
    color: var(--asc-muted); font-size: 13px;
    font-style: italic; padding: 4px 0;
  }
  #preview-modal .p-item {
    display: flex; gap: 12px;
    padding: 7px 0;
    border-bottom: 1px solid color-mix(in srgb, var(--asc-on-surface) 15%, transparent);
  }
  #preview-modal .p-item:last-child { border-bottom: 0; }
  #preview-modal .p-item .num {
    flex-shrink: 0;
    font-family: var(--asc-font);
    font-weight: 900;
    font-style: italic;
    font-size: 20px;
    line-height: 1;
    color: var(--asc-accent);
    padding-top: 2px;
    min-width: 22px;
  }
  #preview-modal .p-item .meta {
    font-family: ui-monospace, monospace;
    font-size: 10px;
    color: var(--asc-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 2px;
  }
  #preview-modal .p-item .text {
    font-family: inherit;
    font-size: 14px;
    color: var(--asc-on-surface);
    line-height: 1.55;
    word-wrap: break-word;
  }

  /* Status panel (centered, full viewport — no toolbar anymore) */
  #status .panel {
    position: fixed; inset: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 16px;
  }

  /* Post-submit overlay — newspaper cream + dark ink, red accent */
  #submit-overlay {
    position: fixed; inset: 0;
    background: color-mix(in srgb, var(--asc-surface) 93%, transparent);
    backdrop-filter: blur(3px);
    -webkit-backdrop-filter: blur(3px);
    z-index: 9100;  /* below notebook (9200), so user can still operate it */
    display: flex;
    flex-direction: column;
    align-items: center; justify-content: center;
    text-align: center;
    padding: 32px;
    color: var(--asc-on-surface);
    font-family: var(--asc-font);
    opacity: 0; pointer-events: none;
    transition: opacity 240ms ease;
  }
  #submit-overlay.visible { opacity: 1; pointer-events: auto; }
  #submit-overlay .icon {
    font-size: 14px; font-weight: 700;
    color: var(--asc-accent);
    letter-spacing: 0.32em;
    text-transform: uppercase;
    margin-bottom: 10px;
  }
  #submit-overlay .title {
    font-family: inherit;
    font-size: 38px; font-weight: 900;
    color: var(--asc-on-surface);
    margin: 0 auto 14px;
    letter-spacing: 0.02em;
    line-height: 1.05;
    text-transform: uppercase;
    display: inline-flex; align-items: center; gap: 14px;
    padding: 8px 0;
    border-top: 3px double var(--asc-on-surface);
    border-bottom: 3px double var(--asc-on-surface);
  }
  #submit-overlay .pulse-dot {
    display: inline-block;
    width: 12px; height: 12px; border-radius: 50%;
    background: var(--asc-accent);
    animation: pulse-ink 1.6s infinite;
  }
  @keyframes pulse-ink {
    0%, 100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--asc-accent) 45%, transparent); }
    50%      { box-shadow: 0 0 0 9px transparent; }
  }
  #submit-overlay .subtitle {
    font-family: inherit;
    font-size: 15px; color: var(--asc-on-surface);
    line-height: 1.75; max-width: 440px;
    margin-top: 6px;
  }
  #submit-overlay .subtitle strong { color: var(--asc-accent); font-weight: 900; }

  /* ───── img-ai placeholder & paint badge ───── */
  img-ai {
    display: block;
    position: relative;
    min-height: 120px;
    border: 1px solid color-mix(in srgb, var(--asc-on-surface, #1a1a1a) 12%, transparent);
    overflow: hidden;
  }
  img-ai img {
    display: block; width: 100%; height: auto;
    object-fit: contain;
    margin: 0 auto;
    cursor: zoom-in;
  }
  img-ai .imgai-placeholder {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    padding: 24px; gap: 8px; min-height: 120px;
    color: var(--asc-muted, #6b6b6b); font-size: 13px; text-align: center;
  }
  img-ai .imgai-placeholder .spinner {
    width: 24px; height: 24px; border: 3px solid color-mix(in srgb, var(--asc-on-surface) 15%, transparent);
    border-top-color: var(--asc-accent); border-radius: 50%;
    animation: imgai-spin 0.8s linear infinite;
  }
  @keyframes imgai-spin { to { transform: rotate(360deg); } }
  img-ai .imgai-badge {
    position: absolute; top: 6px; right: 6px;
    width: 28px; height: 28px; border-radius: 50%;
    background: var(--asc-accent); color: var(--asc-surface, #f4ecd8);
    font-size: 14px; display: flex; align-items: center; justify-content: center;
    cursor: pointer; border: 2px solid var(--asc-surface, #f4ecd8);
    box-shadow: 0 2px 6px rgba(0,0,0,0.2);
    opacity: 0; transition: opacity 150ms;
    z-index: 10;
  }
  img-ai:hover .imgai-badge, img-ai .imgai-badge.visible { opacity: 1; }
  img-ai .imgai-badge:hover { transform: scale(1.1); }

  /* ───── image lightbox (click-to-zoom overlay) ───── */
  #img-lightbox {
    position: fixed; inset: 0; z-index: 9800;
    display: flex; align-items: center; justify-content: center;
    background: rgba(0,0,0,0.82);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
    cursor: zoom-out;
    padding: 24px;
  }
  #img-lightbox.hidden { display: none; }
  #img-lightbox img {
    max-width: 90vw; max-height: 90vh;
    object-fit: contain;
    border-radius: 4px;
    box-shadow: 0 8px 40px rgba(0,0,0,0.5);
  }
  #img-lightbox .lb-close {
    position: absolute; top: 16px; right: 20px;
    background: transparent; border: 0; cursor: pointer;
    font-size: 32px; color: #fff; line-height: 1;
    text-shadow: 0 2px 8px rgba(0,0,0,0.6);
  }
  #img-lightbox .lb-close:hover { color: var(--asc-accent, #ec4899); }

  /* ───── disabled image button in toolbar ───── */
  #img-panel-btn.disabled {
    opacity: 0.38;
    cursor: not-allowed;
  }
  #img-panel-btn.disabled:hover {
    background: transparent;
  }

  /* ───── image hint toast ───── */
  #img-hint-toast {
    position: fixed;
    bottom: 80px; right: 16px;
    z-index: 9300;
    background: var(--asc-surface);
    border: 2px solid var(--asc-on-surface);
    border-radius: var(--asc-radius);
    box-shadow: var(--asc-shadow);
    padding: 14px 18px;
    max-width: 340px;
    font-family: var(--asc-font);
    font-size: 13px;
    line-height: 1.6;
    color: var(--asc-on-surface);
    opacity: 0; pointer-events: none;
    transform: translateY(8px);
    transition: opacity 220ms, transform 220ms;
  }
  #img-hint-toast.visible {
    opacity: 1; pointer-events: auto;
    transform: translateY(0);
  }
  #img-hint-toast .toast-title {
    font-weight: 900; font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--asc-accent);
    margin-bottom: 6px;
  }
  #img-hint-toast code {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 11px;
    background: color-mix(in srgb, var(--asc-on-surface) 8%, transparent);
    padding: 1px 5px;
    border-radius: 2px;
  }

  /* ───── image canvas modal (full viewport overlay like preview) ───── */
  #img-modal {
    position: fixed; inset: 0; z-index: 9500;
    display: flex; align-items: center; justify-content: center;
    background: color-mix(in srgb, var(--asc-on-surface) 45%, transparent);
    backdrop-filter: blur(2px);
    padding: 24px;
  }
  #img-modal.hidden { display: none; }
  #img-modal .modal-card {
    background: var(--asc-surface);
    width: min(640px, 100%);
    max-height: 82vh;
    border: 3px solid var(--asc-on-surface);
    border-radius: var(--asc-radius);
    box-shadow: var(--asc-shadow-lg);
    display: flex; flex-direction: column;
    overflow: hidden;
    color: var(--asc-on-surface);
    font-family: var(--asc-font);
  }
  #img-modal header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 16px 24px 12px;
    border-bottom: 3px double var(--asc-on-surface);
    font-family: inherit;
    font-weight: 900;
    font-size: 18px;
    text-transform: uppercase;
    letter-spacing: 0.02em;
    color: var(--asc-on-surface);
    background: transparent;
  }
  #img-modal header .close {
    border: 0; background: transparent; cursor: pointer;
    font-family: var(--asc-font);
    font-size: 26px; color: var(--asc-on-surface); line-height: 1;
    padding: 0 4px;
    font-weight: 400;
  }
  #img-modal header .close:hover { color: var(--asc-accent); }
  #img-modal header select {
    border: 1px solid var(--asc-on-surface); border-radius: var(--asc-radius);
    background: var(--asc-field, #fffaf0); color: var(--asc-on-surface);
    padding: 3px 8px; font-size: 11px; font-family: inherit; font-weight: 700;
    max-width: 200px;
  }
  #img-modal .img-prompt-row {
    display: flex; gap: 8px; padding: 14px 24px;
    border-bottom: 1px solid color-mix(in srgb, var(--asc-on-surface) 18%, transparent);
  }
  #img-modal .img-prompt-row textarea {
    flex: 1; height: 56px; border: 1px solid var(--asc-on-surface);
    border-radius: var(--asc-radius); padding: 8px 10px;
    font-size: 13px; resize: none; font-family: inherit;
    color: var(--asc-on-surface); background: var(--asc-field, #fffaf0);
  }
  #img-modal .img-prompt-row textarea:focus { outline: 0; border-color: var(--asc-accent); }
  #img-modal .img-prompt-row .gen-controls {
    display: flex; flex-direction: column; gap: 4px; align-self: flex-end;
  }
  #img-modal .img-prompt-row .gen-controls select {
    border: 1px solid var(--asc-on-surface); border-radius: var(--asc-radius);
    background: var(--asc-field); color: var(--asc-on-surface);
    padding: 2px 6px; font-size: 11px; font-family: inherit; font-weight: 700;
  }
  #img-modal .img-prompt-row button {
    padding: 6px 16px;
    background: var(--asc-on-surface); color: var(--asc-surface);
    border: 2px solid var(--asc-on-surface); border-radius: var(--asc-radius);
    font-family: inherit; font-size: 11px; font-weight: 900;
    text-transform: uppercase; letter-spacing: 0.08em; cursor: pointer;
  }
  #img-modal .img-prompt-row button:hover { background: var(--asc-accent); border-color: var(--asc-accent); }
  #img-modal .img-prompt-row button:disabled { opacity: 0.4; cursor: not-allowed; }
  #img-modal .img-grid {
    flex: 1; overflow: auto; padding: 14px 24px;
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;
    min-height: 120px;
  }
  #img-modal .img-grid .empty-grid {
    grid-column: 1 / -1; text-align: center;
    color: var(--asc-muted); font-size: 13px; font-style: italic;
    padding: 32px 0;
  }
  #img-modal .img-grid .img-thumb {
    position: relative; cursor: pointer;
    border: 2px solid transparent; border-radius: var(--asc-radius);
    overflow: hidden; aspect-ratio: 1;
    transition: border-color 120ms;
  }
  #img-modal .img-grid .img-thumb img {
    width: 100%; height: 100%; object-fit: cover; display: block;
  }
  #img-modal .img-grid .img-thumb.generating {
    border: 2px dashed color-mix(in srgb, var(--asc-on-surface) 25%, transparent);
    cursor: default;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 6px;
    background: color-mix(in srgb, var(--asc-on-surface) 4%, transparent);
  }
  #img-modal .img-grid .img-thumb.generating .ph-spinner {
    width: 20px; height: 20px;
    border: 2px solid color-mix(in srgb, var(--asc-on-surface) 15%, transparent);
    border-top-color: var(--asc-accent);
    border-radius: 50%;
    animation: imgai-spin 0.8s linear infinite;
  }
  #img-modal .img-grid .img-thumb.generating .ph-text {
    font-size: 10px; color: var(--asc-muted);
    text-align: center; padding: 0 4px;
    overflow: hidden; text-overflow: ellipsis;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    word-break: break-all;
  }
  #img-modal .img-grid .img-thumb.gen-error {
    border-color: var(--asc-accent);
    border-style: dashed;
    cursor: default;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 4px;
    background: color-mix(in srgb, var(--asc-accent) 5%, transparent);
  }
  #img-modal .img-grid .img-thumb.gen-error .ph-text {
    font-size: 10px; color: var(--asc-accent); text-align: center; padding: 0 4px;
  }
  #img-modal .img-grid .img-thumb.selected {
    border-color: var(--asc-send);
    box-shadow: 0 0 0 2px var(--asc-send);
  }
  #img-modal .img-grid .img-thumb.ref {
    border-color: var(--asc-accent);
    box-shadow: 0 0 0 2px var(--asc-accent);
  }
  #img-modal .img-grid .img-thumb .tag {
    position: absolute; bottom: 3px; left: 3px;
    font-size: 9px; font-weight: 700; padding: 1px 6px;
    border-radius: 3px; color: white;
  }
  #img-modal .img-grid .img-thumb .tag.sel-tag { background: var(--asc-send); }
  #img-modal .img-grid .img-thumb .tag.ref-tag { background: var(--asc-accent); }
  #img-modal footer {
    display: flex; justify-content: space-between; align-items: center; gap: 8px;
    padding: 12px 24px;
    border-top: 3px double var(--asc-on-surface);
    background: color-mix(in srgb, var(--asc-on-surface) 3%, transparent);
    font-size: 12px;
  }
  #img-modal footer .hint { color: var(--asc-muted); font-style: italic; }
  #img-modal footer button {
    border: 2px solid var(--asc-on-surface);
    border-radius: var(--asc-radius);
    padding: 6px 18px;
    font-family: inherit;
    font-size: 11px;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 0.10em;
    cursor: pointer;
    background: var(--asc-send);
    color: var(--asc-surface);
    border-color: var(--asc-send);
  }
  #img-modal footer button:hover { background: var(--asc-send-2); border-color: var(--asc-send-2); }
</style>
<!-- 壳子主题变量:set_session 选模版时注入对应的 :root{ --asc-* } 覆盖上面的默认值。
     纯 CSS(非 tailwindcss),立即生效、无需等 Tailwind 编译,避免壳子闪一下报纸风。
     源码见本文件底部 CHROME_THEMES。空串时壳子用上面 :root 的报纸默认。 -->
<style id="ass-chrome-vars">__CHROME_VARS__</style>
<!-- 模版预设语义类(set_session 选哪套就注入哪套;所有模版共用同一组 ass-* 类名)。
     默认报纸风格;切换模版时这里整段被替换。源码见本文件底部 TEMPLATES。 -->
<style id="ass-preset-styles" type="text/tailwindcss">__PRESET_STYLES__</style>
<!-- 会话级自定义 CSS:set_session(css=...) 注入的命名类规则。
     type="text/tailwindcss" 让 Tailwind play CDN 编译里面的 @apply。 -->
<style id="ass-session-styles" type="text/tailwindcss">__INITIAL_STYLES__</style>
</head>
<body>
<div id="container" class="artifact-root"></div>
<div id="highlight"></div>
<div id="badge-layer"></div>
<div id="notebook">
  <div class="nb-page">
    <header class="nb-header">
      <span class="nb-title"><span>📓</span><span>批注</span></span>
      <span class="nb-count" id="anno-count">0</span>
    </header>
    <div class="nb-body">
      <div id="edit-area" class="hidden"></div>
      <div id="anno-list"></div>
    </div>
  </div>
  <div class="nb-toolbar">
    <button id="more-btn" type="button" title="更多" aria-label="更多">›</button>
    <button id="help-btn" class="nb-extra" type="button" title="使用教程" aria-label="帮助">?</button>
    <button id="settings-btn" class="nb-extra" type="button" title="设置" aria-label="设置">⚙</button>
    <button id="mode-btn" class="on" type="button" title="批注模式开关">
      <span class="indicator"></span>
      <span id="mode-label">批注中</span>
    </button>
    <button id="img-panel-btn" class="disabled" type="button" title="图片画布">🎨 图片 <span id="img-count">0</span></button>
    <button id="preview-send-btn" type="button" disabled title="发送给 AI">发送</button>
  </div>
</div>
<div id="settings-panel" class="hidden">
  <div class="sp-row">
    <label>模版</label>
    <select id="tpl-select"></select>
  </div>
  <div class="sp-row">
    <label>导出</label>
    <button class="t-export-btn" id="export-btn" type="button" disabled>下载 HTML</button>
  </div>
</div>
<div id="preview-modal" class="hidden">
  <div class="modal-card">
    <header>
      <span>📤 预览要发送的内容</span>
      <button class="close" type="button">×</button>
    </header>
    <div class="modal-body" id="preview-body"></div>
    <footer>
      <button class="modal-cancel" type="button">关闭</button>
      <button class="modal-send" type="button">确认发送</button>
    </footer>
  </div>
</div>
<div id="img-modal" class="hidden">
  <div class="modal-card">
    <header>
      <span>🎨 图片画布</span>
      <div style="display:flex;align-items:center;gap:10px">
        <select id="img-slot-select"></select>
        <button class="close" type="button">×</button>
      </div>
    </header>
    <div class="img-prompt-row">
      <textarea id="img-prompt" placeholder="描述你想要的图片…"></textarea>
      <div class="gen-controls">
        <select id="img-n-select">
          <option value="1">×1</option><option value="2">×2</option><option value="3">×3</option><option value="4" selected>×4</option>
        </select>
        <button id="img-gen-btn" type="button">生成</button>
      </div>
    </div>
    <div class="img-grid" id="img-grid">
      <div class="empty-grid">还没有图片<br>生成、粘贴或拖放添加</div>
    </div>
    <footer>
      <span class="hint">左键选定 · 右键设为参考</span>
      <button id="img-use-btn" type="button">✓ 使用选中</button>
    </footer>
  </div>
</div>
<div id="tutorial-modal" class="hidden">
  <div class="t-card">
    <div class="t-head">
      <div>
        <span class="t-kicker">A Manifesto · No. 01</span>
        <span class="t-title">用 HTML 和 AI 交互</span>
      </div>
      <button class="t-close" type="button" aria-label="关闭">×</button>
    </div>

    <div class="t-tabs">
      <button class="t-tab active" data-tab="why" type="button">
        <span class="t-tab-num">01</span>
        <span class="t-tab-label">为何 HTML</span>
      </button>
      <button class="t-tab" data-tab="how" type="button">
        <span class="t-tab-num">02</span>
        <span class="t-tab-label">四步用法</span>
      </button>
      <button class="t-tab" data-tab="after" type="button">
        <span class="t-tab-num">03</span>
        <span class="t-tab-label">发送之后</span>
      </button>
    </div>

    <div class="t-body">
      <section class="t-pane active" data-pane="why">
        <div class="t-pane-grid">
          <div class="t-numblock">01</div>
          <div class="t-pane-content">
            <span class="t-tag">Why HTML</span>
            <h4>不是 markdown</h4>
          </div>
        </div>
        <p>
          这个工具源自 <strong>Anthropic 的一个想法</strong>:让 AI
          <strong>输出 HTML 而不是 markdown</strong>,
          人则通过 HTML <strong>跟 AI 进行交互</strong>。
        </p>
        <p>
          AI 写的东西越来越复杂,<strong>100 行以上的 markdown 几乎没人能读完</strong>。
          HTML 装得下表格、设计、SVG 插图、代码、交互控件——浏览器原生就能看。
        </p>
        <p class="highlight">
          但 HTML 默认是单向的。<strong>agent-speak 补上的另一半</strong>——
          让你直接在 AI 写的 HTML 上改、批注、勾选,把结构化反馈回传给 AI。
          这种来回叫做 <em>in the loop</em>。
        </p>
        <p class="t-source">
          ↗ <a href="https://x.com/trq212/status/2052809885763747935" target="_blank" rel="noopener">Thariq · The Unreasonable Effectiveness of HTML</a>
        </p>
      </section>

      <section class="t-pane" data-pane="how">
        <div class="t-pane-grid">
          <div class="t-numblock">02</div>
          <div class="t-pane-content">
            <span class="t-tag">How to use</span>
            <h4>四步, 把意见送回去</h4>
          </div>
        </div>
        <ol class="t-steps">
          <li>
            <strong>填表单</strong>
            <span>页面上任意 input / checkbox / select 自由填,host 自动收集所有值</span>
          </li>
          <li>
            <strong>批注模式默认开</strong>
            <span>右下角工具栏的"批注"按钮在闪,说明正在嗅探</span>
          </li>
          <li>
            <strong>点元素批注</strong>
            <span>鼠标停在元素上 → 蓝框出现 → 点击 → 在便签里写"这块改成…"</span>
          </li>
          <li>
            <strong>发送</strong>
            <span>点"发送"——绿色按钮,对照内容后确认发送</span>
          </li>
        </ol>
      </section>

      <section class="t-pane" data-pane="after">
        <div class="t-pane-grid">
          <div class="t-numblock">03</div>
          <div class="t-pane-content">
            <span class="t-tag">Stay open</span>
            <h4>发送之后 · 别 关</h4>
          </div>
        </div>
        <p class="huge">不要关掉页面。</p>
        <p>
          AI 改完会把下一稿<strong>直接推回这里</strong>,你接着改就行——
          这就是闭环。<em>关掉就断了。</em>
        </p>
        <p class="t-source">
          想再读一遍?点右下角药丸里的 <strong>?</strong>。
        </p>
      </section>
    </div>

    <div class="t-foot">
      <button class="t-ok" type="button">知道了, 开干</button>
    </div>
  </div>
</div>
<div id="submit-overlay">
  <div class="icon">— 通讯回执 · DISPATCH —</div>
  <div class="title"><span class="pulse-dot"></span>已发送给 AI</div>
  <div class="subtitle">
    请<strong>保持此页面打开</strong>,后续内容会自动出现在这里。<br>
    关闭后,AI 将无法继续与你交互。
  </div>
</div>
<div id="img-lightbox" class="hidden">
  <button class="lb-close" type="button" aria-label="关闭">×</button>
  <img src="" alt="">
</div>
<div id="img-hint-toast">
  <div class="toast-title">如何添加图片</div>
  在对话中告诉 AI：<br>
  <code>请在 HTML 中使用 &lt;img-ai&gt; 标签添加图片占位</code><br>
  AI 会在文档中插入图片槽位，届时可在此生成或上传图片。
</div>
<div id="status"></div>

<script>
(function(){
  const SID = "__SID__";
  const ASS_TEMPLATES = __TEMPLATE_LIST__;
  let assCurrentTemplate = "__CURRENT_TEMPLATE__";
  const container = document.getElementById('container');
  const highlight = document.getElementById('highlight');
  const statusEl = document.getElementById('status');
  const badgeLayer = document.getElementById('badge-layer');
  const notebook = document.getElementById('notebook');
  const annoCount = document.getElementById('anno-count');
  const editArea = document.getElementById('edit-area');
  const annoList = document.getElementById('anno-list');
  const modeBtn = document.getElementById('mode-btn');
  const modeLabel = document.getElementById('mode-label');
  const previewSendBtn = document.getElementById('preview-send-btn');
  const previewModal = document.getElementById('preview-modal');
  const previewBody = document.getElementById('preview-body');
  const submitOverlay = document.getElementById('submit-overlay');
  const tutorialModal = document.getElementById('tutorial-modal');
  const helpBtn = document.getElementById('help-btn');
  const imgModal = document.getElementById('img-modal');
  const imgLightbox = document.getElementById('img-lightbox');
  const imgHintToast = document.getElementById('img-hint-toast');

  const TUTORIAL_SEEN_KEY = 'agent-speak.tutorial.seen.v1';
  let firstArtifactSeen = false;

  /** ai_id -> {instruction, html_hint} (insertion-order = display order) */
  const annotations = new Map();
  let hasArtifact = false;
  let isInspecting = true;   // 批注模式常开
  let editingId = null;

  // ───── img-ai state ─────
  const imgPanelBtn = document.getElementById('img-panel-btn');
  const imgCount = document.getElementById('img-count');
  const imgSlotSelect = document.getElementById('img-slot-select');
  const imgPrompt = document.getElementById('img-prompt');
  const imgGenBtn = document.getElementById('img-gen-btn');
  const imgGrid = document.getElementById('img-grid');
  const imgUseBtn = document.getElementById('img-use-btn');

  let imgPanelOpen = false;
  let activeImgSlot = null;   // current ai_id shown in panel
  // ai_id -> { prompt, variants: [{image_id, url, prompt}], selected_id, ref_ids: Set }
  const imgSlots = new Map();

  // ───── status panel ─────
  function showStatus(html, color) {
    statusEl.innerHTML = `<div class="panel ${color || 'text-gray-500'}">${html}</div>`;
  }
  function clearStatus() { statusEl.innerHTML = ''; }
  showStatus('正在连接...');

  // ───── helpers ─────
  function findAnnotatable(el) {
    while (el && el !== container && el !== document.body) {
      if (el.getAttribute && el.getAttribute('data-ai-id')) return el;
      el = el.parentElement;
    }
    return null;
  }
  function truncate(s, n) { return s.length > n ? s.slice(0, n) + '…' : s; }
  function escHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }
  function findElByAid(id) {
    return container.querySelector(`[data-ai-id="${CSS.escape(id)}"]`);
  }

  function sanitizeInjected() {
    container.querySelectorAll('*').forEach(el => {
      [...el.attributes].forEach(attr => {
        if (attr.name.toLowerCase().startsWith('on')) el.removeAttribute(attr.name);
      });
    });
    // <script> never executes via innerHTML anyway, but strip for cleanliness.
    // <style>/<link>/<base>/<meta>/<html>/<head>/<body> however CAN leak page-wide
    // styling or break document semantics when AI accidentally emits them.
    container.querySelectorAll(
      'script, style, link, base, meta, html, head, body, iframe, object, embed'
    ).forEach(el => el.remove());
  }

  // 自动锚点:AI 不必手写 data-ai-id。innerHTML 注入并 sanitize 之后,给白
  // 名单内、尚未带锚点的元素补一个会话内唯一的 data-ai-id,让任意有意义的
  // 元素都能被悬停/批注;回传时配合 element_html_hint,AI 仍能认出是哪块。
  // 纯文字修饰(span/strong/em…)与 SVG 内部节点不在白名单,避免选到碎片。
  // 每次 render 都是全新 DOM(annotations 已清空),故序号只需单次渲染内唯一。
  const ANCHOR_TAGS = new Set([
    'DIV','SECTION','ARTICLE','HEADER','FOOTER','ASIDE','NAV','MAIN','FIGURE','FIGCAPTION',
    'P','H1','H2','H3','H4','H5','H6','BLOCKQUOTE','PRE','HR',
    'UL','OL','LI','DL','DT','DD',
    'TABLE','THEAD','TBODY','TFOOT','TR','TD','TH','CAPTION',
    'FORM','FIELDSET','LEGEND','LABEL','INPUT','TEXTAREA','SELECT','BUTTON',
    'A','IMG','IMG-AI','SVG','VIDEO','AUDIO','CANVAS','PICTURE',
    'DETAILS','SUMMARY',
  ]);
  function ensureAnchors() {
    const used = new Set();
    container.querySelectorAll('[data-ai-id]').forEach(el => used.add(el.getAttribute('data-ai-id')));
    let n = 0;
    container.querySelectorAll('*').forEach(el => {
      if (el.hasAttribute('data-ai-id')) return;
      if (!ANCHOR_TAGS.has(el.tagName.toUpperCase())) return;
      let id;
      do { id = 'auto-' + el.tagName.toLowerCase() + '-' + (++n); } while (used.has(id));
      used.add(id);
      el.setAttribute('data-ai-id', id);
    });
  }

  function updateSendBtn() {
    previewSendBtn.disabled = !hasArtifact;
    previewSendBtn.title = hasArtifact ? '发送给 AI' : '等待 artifact';
  }

  function refreshAnnotationOutlines() {
    container.querySelectorAll('[data-as-annotated]').forEach(el => el.removeAttribute('data-as-annotated'));
    annotations.forEach((_, id) => {
      const el = findElByAid(id);
      if (el) el.setAttribute('data-as-annotated', 'true');
    });
  }

  // ───── inspect mode ─────
  function setInspecting(v) {
    isInspecting = !!v;
    document.body.classList.toggle('inspecting', isInspecting);
    modeBtn.classList.toggle('on', isInspecting);
    notebook.classList.toggle('mode-off', !isInspecting);
    modeLabel.textContent = isInspecting ? '批注中' : '批注';
    // 批注小窗与设置小窗互斥:批注模式开启(批注小窗出现)时收起设置面板
    if (isInspecting) settingsPanel.classList.add('hidden');
    if (!isInspecting) {
      hideHighlight();
      editingId = null;
    }
    updatePanel();
  }
  modeBtn.addEventListener('click', () => setInspecting(!isInspecting));

  // ───── hover highlight ─────
  function showHighlight(el) {
    const r = el.getBoundingClientRect();
    highlight.style.display = 'block';
    highlight.style.top = (r.top - 2) + 'px';
    highlight.style.left = (r.left - 2) + 'px';
    highlight.style.width = r.width + 'px';
    highlight.style.height = r.height + 'px';
    const labelBelow = r.top < 28;
    highlight.innerHTML = `<div class="label${labelBelow ? ' bottom' : ''}">📌 点击添加批注</div>`;
  }
  function hideHighlight() { highlight.style.display = 'none'; }

  container.addEventListener('mousemove', (e) => {
    if (!hasArtifact || !isInspecting) { hideHighlight(); return; }
    const t = findAnnotatable(e.target);
    if (t) showHighlight(t); else hideHighlight();
  });
  container.addEventListener('mouseleave', hideHighlight);

  container.addEventListener('click', (e) => {
    if (!hasArtifact || !isInspecting) return;
    const t = findAnnotatable(e.target);
    if (!t) return;
    e.preventDefault();
    e.stopPropagation();
    editingId = t.getAttribute('data-ai-id');
    updatePanel();
  }, true);

  // ───── element-level number badges (inside top-right of element) ─────
  function renderBadges() {
    if (!hasArtifact) { badgeLayer.innerHTML = ''; return; }
    let html = '';
    let i = 0;
    for (const [id] of annotations) {
      i++;
      html += `<div class="anno-badge" data-id="${escHtml(id)}">${i}</div>`;
    }
    badgeLayer.innerHTML = html;
    positionBadges();
  }
  function positionBadges() {
    badgeLayer.querySelectorAll('.anno-badge').forEach(badge => {
      const id = badge.dataset.id;
      const el = findElByAid(id);
      if (!el) { badge.style.display = 'none'; return; }
      const r = el.getBoundingClientRect();
      // Sit INSIDE the element's top-right corner with a small padding so we
      // don't get clipped when the element hugs the page edge. The badge is
      // anchored by its right edge via transform: translateX(-100%).
      badge.style.display = 'flex';
      badge.style.top = (r.top + 4) + 'px';
      badge.style.left = (r.left + r.width - 4) + 'px';
      badge.classList.toggle('active', editingId === id);
    });
  }
  let repositionRaf = 0;
  function scheduleReposition() {
    if (repositionRaf) return;
    repositionRaf = requestAnimationFrame(() => {
      repositionRaf = 0;
      positionBadges();
    });
  }
  window.addEventListener('scroll', scheduleReposition, true);
  window.addEventListener('resize', scheduleReposition);

  badgeLayer.addEventListener('click', (e) => {
    const badge = e.target.closest('.anno-badge');
    if (!badge) return;
    editingId = badge.dataset.id;
    if (!isInspecting) setInspecting(true);
    else updatePanel();
  });

  // ───── notebook rendering ─────
  function updatePanel() {
    const count = annotations.size;
    annoCount.textContent = String(count);

    notebook.classList.toggle('visible', hasArtifact);

    // edit area
    if (editingId && isInspecting) {
      const existing = annotations.get(editingId);
      editArea.innerHTML = `
        <div class="target-id">#${escHtml(editingId)}</div>
        <textarea placeholder="告诉 AI 这一块要怎么改…"></textarea>
        <div class="row">
          <button class="delete" type="button" ${existing ? '' : 'style="visibility:hidden"'}>删除</button>
          <div class="right-btns">
            <button class="cancel" type="button">取消</button>
            <button class="save" type="button">保存</button>
          </div>
        </div>`;
      const ta = editArea.querySelector('textarea');
      ta.value = existing ? existing.instruction : '';
      editArea.classList.remove('hidden');
      setTimeout(() => ta.focus(), 0);
    } else {
      editArea.classList.add('hidden');
      editArea.innerHTML = '';
    }

    // list (or empty state)
    if (count === 0) {
      annoList.innerHTML = isInspecting
        ? '<div class="empty">还没有批注 ✨<br>把鼠标移到页面元素上,<br>点击就能记下一条</div>'
        : '<div class="empty">还没有批注<br>开启"批注"模式,<br>就能在页面上添加</div>';
    } else {
      annoList.innerHTML = [...annotations.entries()].map(([id, a], i) => `
        <div class="item${editingId === id ? ' editing' : ''}" data-id="${escHtml(id)}">
          <div class="num">${i + 1}</div>
          <div class="item-body">
            <div class="aid">#${escHtml(id)}</div>
            <div class="text">${escHtml(a.instruction)}</div>
          </div>
        </div>`).join('');
    }

    refreshAnnotationOutlines();
    renderBadges();
    updateSendBtn();
  }

  editArea.addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    if (btn.classList.contains('cancel')) {
      editingId = null;
      updatePanel();
      return;
    }
    if (!editingId) return;
    if (btn.classList.contains('delete')) {
      annotations.delete(editingId);
      editingId = null;
      updatePanel();
    } else if (btn.classList.contains('save')) {
      const text = editArea.querySelector('textarea').value.trim();
      const target = findElByAid(editingId);
      if (!text) {
        annotations.delete(editingId);
      } else if (target) {
        annotations.set(editingId, {
          instruction: text,
          html_hint: truncate(target.outerHTML, 300),
        });
      }
      editingId = null;
      updatePanel();
    }
  });

  annoList.addEventListener('click', (e) => {
    const item = e.target.closest('.item');
    if (!item) return;
    editingId = item.dataset.id;
    if (!isInspecting) setInspecting(true);
    else updatePanel();
  });

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (!imgLightbox.classList.contains('hidden')) { closeLightbox(); return; }
      if (!tutorialModal.classList.contains('hidden')) { closeTutorial(); return; }
      if (!previewModal.classList.contains('hidden')) { closePreview(); return; }
      if (!imgModal.classList.contains('hidden')) { closeImgModal(); return; }
      if (editingId) { editingId = null; updatePanel(); }
    }
  });

  // ───── mermaid lazy load ─────
  const MERMAID_CDNS = [
    'https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js',
    'https://unpkg.com/mermaid@11.4.1/dist/mermaid.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/mermaid/11.4.1/mermaid.min.js',
  ];
  const MERMAID_CONFIGS = __MERMAID_CONFIGS__;
  let mermaidLoaded = false;
  let mermaidLoading = false;

  function normalizeMermaidBlocks() {
    container.querySelectorAll('pre > code.language-mermaid').forEach(code => {
      const pre = code.parentElement;
      pre.classList.add('mermaid');
      pre.textContent = code.textContent;
    });
  }

  function mermaidNodes() {
    return container.querySelectorAll('pre.mermaid:not([data-mermaid-processed])');
  }

  function showMermaidError(node, msg) {
    node.setAttribute('data-mermaid-processed', 'error');
    node.style.cssText = 'border:2px dashed #c00;padding:1em;background:color-mix(in srgb,#c00 6%,transparent);font-size:13px;white-space:pre-wrap;';
    node.innerHTML = '<strong style="color:#c00">Mermaid 渲染失败</strong>\n' + escHtml(msg) + '\n\n' + escHtml(node.textContent);
  }

  function loadMermaidCDN(index) {
    if (index >= MERMAID_CDNS.length) {
      mermaidLoading = false;
      console.error('all mermaid CDNs failed');
      mermaidNodes().forEach(n => showMermaidError(n, '所有 CDN 均加载失败'));
      return;
    }
    const url = MERMAID_CDNS[index];
    const s = document.createElement('script');
    s.src = url;
    s.onload = () => {
      mermaidLoaded = true;
      mermaidLoading = false;
      doMermaidRun();
    };
    s.onerror = () => {
      console.warn('mermaid CDN failed: ' + url + ', trying next...');
      s.remove();
      loadMermaidCDN(index + 1);
    };
    document.head.appendChild(s);
  }

  function maybeRunMermaid() {
    const raw = container.querySelectorAll('pre.mermaid, code.language-mermaid');
    if (raw.length === 0) return;
    normalizeMermaidBlocks();
    if (mermaidLoaded) { doMermaidRun(); return; }
    if (mermaidLoading) return;
    mermaidLoading = true;
    loadMermaidCDN(0);
  }

  function doMermaidRun() {
    const cfg = MERMAID_CONFIGS[assCurrentTemplate] || MERMAID_CONFIGS['报纸'] || { theme: 'neutral' };
    window.mermaid.initialize({ startOnLoad: false, ...cfg });
    const nodes = mermaidNodes();
    if (nodes.length === 0) return;
    window.mermaid.run({ nodes: nodes }).catch(err => {
      console.error('mermaid.run() failed', err);
      mermaidNodes().forEach(n => showMermaidError(n, String(err)));
    });
  }

  // ───── artifact render ─────
  function renderArtifact(html) {
    container.innerHTML = html;
    sanitizeInjected();
    ensureAnchors();
    if (typeof hljs !== 'undefined') container.querySelectorAll('pre code').forEach(el => {
      if (el.classList.contains('language-mermaid') || el.closest('pre.mermaid')) return;
      hljs.highlightElement(el);
    });
    maybeRunMermaid();
    container.dataset.frozen = 'false';
    annotations.clear();
    editingId = null;
    hasArtifact = true;
    hideHighlight();
    hideSubmitOverlay();
    clearStatus();
    setInspecting(isInspecting);
    maybeShowFirstTimeTutorial();
    initImgAi();
    updateExportBtn();
  }

  function showSubmitOverlay() { submitOverlay.classList.add('visible'); }
  function hideSubmitOverlay() { submitOverlay.classList.remove('visible'); }

  // ───── form harvest ─────
  function inferLabel(el) {
    if (el.id) {
      const lbl = container.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (lbl) return lbl.innerText.trim();
    }
    const parentLbl = el.closest('label');
    if (parentLbl) return parentLbl.innerText.trim();
    const prev = el.previousElementSibling;
    if (prev && prev.tagName === 'LABEL') return prev.innerText.trim();
    return null;
  }
  function harvestForms() {
    const out = [];
    container.querySelectorAll('input, textarea, select').forEach(el => {
      const type = (el.type || el.tagName).toLowerCase();
      let value;
      if (type === 'checkbox' || type === 'radio') value = !!el.checked;
      else if (el.tagName === 'SELECT' && el.multiple) value = [...el.selectedOptions].map(o => o.value);
      else value = el.value;
      out.push({
        ai_id: el.getAttribute('data-ai-id'),
        label: inferLabel(el),
        name: el.getAttribute('name') || null,
        type,
        value,
      });
    });
    return out;
  }

  function buildPayload() {
    // Collect image assignments
    const assignments = imgSlots._assignments || {};
    const imageResults = [];
    container.querySelectorAll('img-ai').forEach(el => {
      const aiId = el.getAttribute('data-ai-id');
      const imageId = assignments[aiId];
      if (imageId) {
        const img = imgSlots.get(imageId);
        imageResults.push({
          ai_id: aiId,
          image_id: imageId,
          url: `/assets/${SID}/${imageId}.png`,
          prompt: img ? img.prompt : '',
          source: img ? img.source : '',
        });
      }
    });
    return {
      user_comments: [...annotations.entries()].map(([id, a]) => ({
        target_id: id,
        element_html_hint: a.html_hint,
        instruction: a.instruction,
      })),
      user_form_inputs: harvestForms(),
      image_results: imageResults,
    };
  }

  // ───── preview modal ─────
  function openPreview() {
    if (!hasArtifact) return;
    closeImgModal();
    setInspecting(false);
    const payload = buildPayload();
    const comments = payload.user_comments;
    const forms = payload.user_form_inputs;
    let html = '';

    html += '<div class="section">';
    html += `<h3>批注 · ${comments.length}</h3>`;
    if (comments.length === 0) {
      html += '<div class="empty">无批注</div>';
    } else {
      html += comments.map((c, i) => `
        <div class="p-item">
          <div class="num">${i + 1}</div>
          <div>
            <div class="meta">#${escHtml(c.target_id)}</div>
            <div class="text">${escHtml(c.instruction)}</div>
          </div>
        </div>`).join('');
    }
    html += '</div>';

    html += '<div class="section">';
    html += `<h3>表单字段 · ${forms.length}</h3>`;
    if (forms.length === 0) {
      html += '<div class="empty">无表单字段</div>';
    } else {
      html += forms.map(f => {
        const label = f.label || f.ai_id || f.name || f.type;
        let val = f.value;
        if (typeof val === 'boolean') val = val ? '✓ 已选中' : '✗ 未选中';
        else if (Array.isArray(val)) val = val.length ? val.join(', ') : '(空)';
        else val = String(val || '') || '(空)';
        return `
        <div class="p-item">
          <div>
            <div class="meta">${escHtml(label)}</div>
            <div class="text">${escHtml(val)}</div>
          </div>
        </div>`;
      }).join('');
    }
    html += '</div>';

    previewBody.innerHTML = html;
    previewModal.classList.remove('hidden');
  }
  function closePreview() {
    previewModal.classList.add('hidden');
    setInspecting(true);
  }

  previewSendBtn.addEventListener('click', openPreview);

  // ───── tutorial modal ─────
  const tutorialTabs = tutorialModal.querySelectorAll('.t-tab');
  const tutorialPanes = tutorialModal.querySelectorAll('.t-pane');
  function activateTutorialTab(key) {
    tutorialTabs.forEach(t => t.classList.toggle('active', t.dataset.tab === key));
    tutorialPanes.forEach(p => p.classList.toggle('active', p.dataset.pane === key));
  }
  function openTutorial() {
    activateTutorialTab('why');   // always reset to first tab on open
    tutorialModal.classList.remove('hidden');
  }
  function closeTutorial() {
    tutorialModal.classList.add('hidden');
    try { localStorage.setItem(TUTORIAL_SEEN_KEY, '1'); } catch (e) {}
  }
  function maybeShowFirstTimeTutorial() {
    if (firstArtifactSeen) return;
    firstArtifactSeen = true;
    let seen = false;
    try { seen = localStorage.getItem(TUTORIAL_SEEN_KEY) === '1'; } catch (e) {}
    if (!seen) setTimeout(openTutorial, 400);
  }
  helpBtn.addEventListener('click', openTutorial);
  tutorialTabs.forEach(tab => {
    tab.addEventListener('click', () => activateTutorialTab(tab.dataset.tab));
  });
  let tutorialMouseDownTarget = null;
  tutorialModal.addEventListener('mousedown', (e) => { tutorialMouseDownTarget = e.target; });
  tutorialModal.addEventListener('click', (e) => {
    if (e.target === tutorialModal && tutorialMouseDownTarget === tutorialModal) { closeTutorial(); return; }
    const btn = e.target.closest('button');
    if (!btn) return;
    if (btn.classList.contains('t-close') || btn.classList.contains('t-ok')) {
      closeTutorial();
    }
  });
  // ───── more toggle (collapse ⚙ and ?) ─────
  const moreBtn = document.getElementById('more-btn');
  const toolbar = document.querySelector('.nb-toolbar');
  moreBtn.addEventListener('click', () => {
    const expanding = !toolbar.classList.contains('expanded');
    toolbar.classList.toggle('expanded');
    if (!expanding) settingsPanel.classList.add('hidden');
  });

  // 控制栏宽度随展开/收起伸缩;日记本与设置面板用 --asc-dock-w 跟随其实时宽度,
  // 始终右对齐成一摞(三者都 box-sizing:border-box,故 width=控制栏 offsetWidth 即总宽相等)。
  if (window.ResizeObserver) {
    const syncDockWidth = () => {
      const w = toolbar.offsetWidth;
      if (w) document.documentElement.style.setProperty('--asc-dock-w', w + 'px');
    };
    new ResizeObserver(syncDockWidth).observe(toolbar);
  }

  // ───── settings panel (⚙ button) ─────
  const settingsBtn = document.getElementById('settings-btn');
  const settingsPanel = document.getElementById('settings-panel');
  const tplSelect = document.getElementById('tpl-select');
  const exportBtn = document.getElementById('export-btn');

  settingsBtn.addEventListener('click', () => {
    const willShow = settingsPanel.classList.contains('hidden');
    settingsPanel.classList.toggle('hidden');
    // 设置小窗与批注小窗互斥:设置弹出时关掉批注模式(批注小窗随之收起)
    if (willShow && isInspecting) setInspecting(false);
  });

  ASS_TEMPLATES.forEach(t => {
    const opt = document.createElement('option');
    opt.value = t; opt.textContent = t;
    if (t === assCurrentTemplate) opt.selected = true;
    tplSelect.appendChild(opt);
  });
  // 把原生 <select> 增强成跟随壳子主题的模拟下拉框(原生框被隐藏,仍作数据源)
  buildAscSelect(tplSelect);

  tplSelect.addEventListener('change', async () => {
    try {
      const res = await fetch(`/ui/${SID}/switch-template`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template: tplSelect.value }),
      });
      if (res.ok) assCurrentTemplate = tplSelect.value;
    } catch (e) { console.error('switch template failed', e); }
  });

  exportBtn.addEventListener('click', () => {
    if (hasArtifact) window.open(`/ui/${SID}/export`, '_blank');
  });

  function updateExportBtn() {
    exportBtn.disabled = !hasArtifact;
  }

  // ───── 模拟下拉框:把原生 <select> 增强成跟随主题的列表 ─────
  function closeAscSelects(except) {
    document.querySelectorAll('.asc-select.open').forEach(w => {
      if (w !== except && w._close) w._close();
    });
  }
  document.addEventListener('click', () => closeAscSelects(null));

  function buildAscSelect(sel) {
    sel.style.display = 'none';
    const wrap = document.createElement('div');
    wrap.className = 'asc-select';
    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'asc-cs-trigger';
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    const label = document.createElement('span');
    label.className = 'asc-cs-label';
    const arrow = document.createElement('span');
    arrow.className = 'asc-cs-arrow';
    trigger.appendChild(label);
    trigger.appendChild(arrow);
    const menu = document.createElement('ul');
    menu.className = 'asc-cs-menu';
    menu.setAttribute('role', 'listbox');

    let activeIdx = -1;
    function setActive(i) {
      const items = menu.children;
      for (let k = 0; k < items.length; k++) items[k].classList.toggle('active', k === i);
      activeIdx = i;
      if (i >= 0 && items[i]) items[i].scrollIntoView({ block: 'nearest' });
    }
    // 同步触发器文字与高亮项(也用于外部改值后回填,见 applyStyles)
    function syncLabel() {
      const opt = sel.options[sel.selectedIndex];
      label.textContent = opt ? opt.textContent.trim() : '';
      const items = menu.children;
      for (let k = 0; k < items.length; k++) items[k].classList.toggle('selected', k === sel.selectedIndex);
    }
    function close() {
      wrap.classList.remove('open');
      trigger.setAttribute('aria-expanded', 'false');
      setActive(-1);
    }
    function open() {
      closeAscSelects(wrap);
      wrap.classList.add('open');
      trigger.setAttribute('aria-expanded', 'true');
      setActive(sel.selectedIndex);
    }
    function choose(i) {
      sel.selectedIndex = i;
      syncLabel();
      close();
      sel.dispatchEvent(new Event('change', { bubbles: true }));
    }
    wrap._close = close;
    sel._ascSync = syncLabel;

    Array.prototype.forEach.call(sel.options, (opt, i) => {
      const li = document.createElement('li');
      li.className = 'asc-cs-option' + (i === sel.selectedIndex ? ' selected' : '');
      li.setAttribute('role', 'option');
      li.textContent = opt.textContent.trim();
      li.addEventListener('click', (e) => { e.stopPropagation(); choose(i); });
      menu.appendChild(li);
    });
    syncLabel();

    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      if (wrap.classList.contains('open')) close(); else open();
    });
    trigger.addEventListener('keydown', (e) => {
      const n = menu.children.length;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        if (!wrap.classList.contains('open')) { open(); return; }
        let ni = activeIdx + (e.key === 'ArrowDown' ? 1 : -1);
        if (ni < 0) ni = 0;
        if (ni >= n) ni = n - 1;
        setActive(ni);
      } else if (e.key === 'Enter' || e.key === ' ') {
        if (wrap.classList.contains('open')) {
          e.preventDefault();
          if (activeIdx >= 0) choose(activeIdx);
        }
      } else if (e.key === 'Escape') {
        close();
      }
    });

    wrap.appendChild(trigger);
    wrap.appendChild(menu);
    sel.parentNode.insertBefore(wrap, sel.nextSibling);
  }

  let previewMouseDownTarget = null;
  previewModal.addEventListener('mousedown', (e) => { previewMouseDownTarget = e.target; });
  previewModal.addEventListener('click', (e) => {
    if (e.target === previewModal && previewMouseDownTarget === previewModal) { closePreview(); return; }
    const btn = e.target.closest('button');
    if (!btn) return;
    if (btn.classList.contains('close') || btn.classList.contains('modal-cancel')) closePreview();
    else if (btn.classList.contains('modal-send')) { closePreview(); doSubmit(); }
  });

  // ───── submit ─────
  async function doSubmit() {
    if (!hasArtifact) return;
    const payload = buildPayload();
    container.dataset.frozen = 'true';
    previewSendBtn.disabled = true;
    setInspecting(false);
    try {
      await fetch(`/ui/${SID}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      showSubmitOverlay();
    } catch (err) {
      console.error('submit failed', err);
    }
  }

  // ───── img-ai: shared canvas logic ─────
  function openImgModal(forceAiId) {
    if (forceAiId) activeImgSlot = forceAiId;
    imgPanelOpen = true;
    setInspecting(false);
    imgModal.classList.remove('hidden');
    refreshImgPanel();
  }
  function closeImgModal() {
    imgPanelOpen = false;
    imgModal.classList.add('hidden');
    setInspecting(true);
  }
  function toggleImgPanel(forceAiId) {
    if (imgPanelOpen && !forceAiId) closeImgModal();
    else openImgModal(forceAiId);
  }
  imgPanelBtn.addEventListener('click', () => {
    if (imgPanelBtn.classList.contains('disabled')) { showImgHint(); return; }
    toggleImgPanel();
  });
  let imgModalMouseDownTarget = null;
  imgModal.addEventListener('mousedown', (e) => { imgModalMouseDownTarget = e.target; });
  imgModal.addEventListener('click', (e) => {
    if (e.target === imgModal && imgModalMouseDownTarget === imgModal) closeImgModal();
    const btn = e.target.closest('button');
    if (btn && btn.classList.contains('close')) closeImgModal();
  });

  function getImgAiSlots() {
    return [...container.querySelectorAll('img-ai')].map(el => ({
      aiId: el.getAttribute('data-ai-id'),
      prompt: el.getAttribute('prompt') || '',
      placeholder: el.getAttribute('placeholder') || '',
      imageId: el.getAttribute('image-id') || '',
    }));
  }

  async function loadPool() {
    try {
      const r = await fetch(`/api/${SID}/image-pool`);
      const d = await r.json();
      if (!d.ok) return;
      imgSlots.clear();
      d.images.forEach(img => imgSlots.set(img.image_id, img));
      // store assignments
      imgSlots._assignments = d.assignments || {};
    } catch(e) { console.error('loadPool', e); }
  }

  function refreshImgPanel() {
    const slots = getImgAiSlots();
    const assignments = imgSlots._assignments || {};

    // Update slot selector
    imgSlotSelect.innerHTML = slots.map(s =>
      `<option value="${escHtml(s.aiId)}" ${s.aiId === activeImgSlot ? 'selected' : ''}>${escHtml(s.aiId)}</option>`
    ).join('');
    if (slots.length && !activeImgSlot) activeImgSlot = slots[0].aiId;

    // Fill prompt from slot if empty
    if (activeImgSlot && !imgPrompt.value) {
      const sl = slots.find(s => s.aiId === activeImgSlot);
      if (sl && sl.prompt) imgPrompt.value = sl.prompt;
    }

    // Render grid — preserve in-flight placeholders
    const pendingEls = [...imgGrid.querySelectorAll('.img-thumb.generating, .img-thumb.gen-error')];
    const images = [...imgSlots.values()].filter(v => v.image_id);
    if (images.length === 0 && pendingEls.length === 0) {
      imgGrid.innerHTML = '<div class="empty-grid">还没有图片<br>生成、粘贴或拖放添加</div>';
    } else {
      imgGrid.innerHTML = images.map(img => {
        const assignedTo = Object.entries(assignments).find(([,v]) => v === img.image_id);
        const isAssigned = assignedTo && assignedTo[0] === activeImgSlot;
        return `<div class="img-thumb ${isAssigned ? 'selected' : ''}" data-imgid="${img.image_id}" title="${escHtml(img.prompt || img.label || img.source)}">
          <img src="${img.url}" loading="lazy">
          ${isAssigned ? '<span class="tag sel-tag">✓</span>' : ''}
          ${assignedTo ? `<span class="tag ref-tag">${escHtml(assignedTo[0]).slice(0,8)}</span>` : ''}
        </div>`;
      }).join('');
      pendingEls.forEach(el => imgGrid.appendChild(el));
    }
  }

  imgSlotSelect.addEventListener('change', () => {
    activeImgSlot = imgSlotSelect.value;
    imgPrompt.value = '';
    const sl = getImgAiSlots().find(s => s.aiId === activeImgSlot);
    if (sl && sl.prompt) imgPrompt.value = sl.prompt;
    refreshImgPanel();
  });

  // Generate (non-blocking, with placeholders)
  const imgNSelect = document.getElementById('img-n-select');
  let batchCounter = 0;

  function insertPlaceholders(n, prompt) {
    const batchId = ++batchCounter;
    const ids = [];
    // Remove empty-grid hint if present
    const emptyHint = imgGrid.querySelector('.empty-grid');
    if (emptyHint) emptyHint.remove();
    for (let i = 0; i < n; i++) {
      const phId = `ph-${batchId}-${i}`;
      ids.push(phId);
      const div = document.createElement('div');
      div.className = 'img-thumb generating';
      div.dataset.phid = phId;
      div.innerHTML = `<div class="ph-spinner"></div><div class="ph-text">${escHtml(truncate(prompt, 30))}</div>`;
      imgGrid.appendChild(div);
    }
    return ids;
  }

  function resolvePlaceholder(phId, img) {
    const ph = imgGrid.querySelector(`[data-phid="${CSS.escape(phId)}"]`);
    if (!ph) return;
    ph.className = 'img-thumb';
    ph.dataset.imgid = img.image_id;
    delete ph.dataset.phid;
    ph.innerHTML = `<img src="${img.url}" loading="lazy">`;
    ph.style.cursor = 'pointer';
  }

  function failPlaceholder(phId, errMsg) {
    const ph = imgGrid.querySelector(`[data-phid="${CSS.escape(phId)}"]`);
    if (!ph) return;
    ph.className = 'img-thumb gen-error';
    ph.innerHTML = `<div class="ph-text">⚠ ${escHtml(truncate(errMsg, 40))}</div>`;
  }

  imgGenBtn.addEventListener('click', () => {
    const prompt = imgPrompt.value.trim();
    if (!prompt) return;
    const n = parseInt(imgNSelect.value) || 4;
    const refIds = [];
    imgGrid.querySelectorAll('.img-thumb.ref').forEach(el => {
      if (el.dataset.imgid) refIds.push(el.dataset.imgid);
    });
    const phIds = insertPlaceholders(n, prompt);
    const slotForAutoAssign = activeImgSlot;

    fetch(`/api/${SID}/generate`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ prompt, n, reference_ids: refIds }),
    })
    .then(r => r.json())
    .then(async d => {
      if (d.ok && d.images) {
        let firstId = null;
        d.images.forEach((img, i) => {
          imgSlots.set(img.image_id, { image_id: img.image_id, url: img.url, prompt, source: 'generated', label: '' });
          if (!firstId) firstId = img.image_id;
          if (phIds[i]) resolvePlaceholder(phIds[i], img);
        });
        // Auto-assign first image if slot has no image yet
        const assignments = imgSlots._assignments || {};
        if (slotForAutoAssign && !assignments[slotForAutoAssign] && firstId) {
          await assignImage(slotForAutoAssign, firstId);
          syncImgAiElements();
        }
      } else {
        phIds.forEach(id => failPlaceholder(id, d.error || 'unknown'));
      }
    })
    .catch(e => {
      phIds.forEach(id => failPlaceholder(id, e.message));
    });
  });

  // Click to assign, right-click to mark as reference (ignore placeholders)
  imgGrid.addEventListener('click', async (e) => {
    const thumb = e.target.closest('.img-thumb');
    if (!thumb || !thumb.dataset.imgid || !activeImgSlot) return;
    await assignImage(activeImgSlot, thumb.dataset.imgid);
    refreshImgPanel();
    syncImgAiElements();
  });
  imgGrid.addEventListener('contextmenu', (e) => {
    const thumb = e.target.closest('.img-thumb');
    if (!thumb || !thumb.dataset.imgid) return;
    e.preventDefault();
    thumb.classList.toggle('ref');
  });

  async function assignImage(aiId, imageId) {
    try {
      await fetch(`/api/${SID}/assign-image`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ ai_id: aiId, image_id: imageId }),
      });
      if (!imgSlots._assignments) imgSlots._assignments = {};
      imgSlots._assignments[aiId] = imageId;
    } catch(e) { console.error('assign', e); }
  }

  // "Use selected" button
  imgUseBtn.addEventListener('click', () => {
    syncImgAiElements();
    closeImgModal();
  });

  // Sync img-ai elements with assignments
  function syncImgAiElements() {
    const assignments = imgSlots._assignments || {};
    container.querySelectorAll('img-ai').forEach(el => {
      const aiId = el.getAttribute('data-ai-id');
      const imageId = assignments[aiId];
      if (imageId) {
        const img = el.querySelector('img') || document.createElement('img');
        img.src = `/assets/${SID}/${imageId}.png`;
        const w = el.getAttribute('width'), h = el.getAttribute('height');
        if (w) { img.style.maxWidth = w; el.style.maxWidth = w; }
        if (h) { img.style.maxHeight = h; el.style.maxHeight = h; }
        if (!el.querySelector('img')) {
          el.innerHTML = '';
          el.appendChild(img);
        }
        // Add paint badge
        let badge = el.querySelector('.imgai-badge');
        if (!badge) {
          badge = document.createElement('div');
          badge.className = 'imgai-badge visible';
          badge.innerHTML = '🎨';
          badge.addEventListener('click', (ev) => {
            ev.stopPropagation();
            toggleImgPanel(aiId);
          });
          el.appendChild(badge);
        }
      } else {
        // Show placeholder
        const ph = el.getAttribute('placeholder') || el.getAttribute('prompt') || '等待图片…';
        if (!el.querySelector('.imgai-placeholder')) {
          el.innerHTML = `<div class="imgai-placeholder"><div>${escHtml(ph)}</div></div>`;
          let badge = document.createElement('div');
          badge.className = 'imgai-badge visible';
          badge.innerHTML = '🎨';
          badge.addEventListener('click', (ev) => {
            ev.stopPropagation();
            toggleImgPanel(aiId);
          });
          el.appendChild(badge);
        }
      }
    });
  }

  // Paste / Drop into panel
  document.addEventListener('paste', async (e) => {
    if (!imgPanelOpen) return;
    const items = e.clipboardData && e.clipboardData.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        e.preventDefault();
        const blob = item.getAsFile();
        await uploadBlob(blob, 'pasted');
        return;
      }
    }
  });

  imgModal.addEventListener('dragover', (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; });
  imgModal.addEventListener('drop', async (e) => {
    e.preventDefault();
    for (const file of e.dataTransfer.files) {
      if (file.type.startsWith('image/')) {
        await uploadBlob(file, 'uploaded');
      }
    }
  });

  async function uploadBlob(blob, source) {
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const r = await fetch(`/api/${SID}/upload`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ data: reader.result, source }),
        });
        const d = await r.json();
        if (d.ok) {
          imgSlots.set(d.image_id, { image_id: d.image_id, url: d.url, prompt: '', source, label: '' });
          // Auto-assign if slot empty
          const assignments = imgSlots._assignments || {};
          if (activeImgSlot && !assignments[activeImgSlot]) {
            await assignImage(activeImgSlot, d.image_id);
          }
          refreshImgPanel();
          syncImgAiElements();
        }
      } catch(e) { console.error('upload', e); }
    };
    reader.readAsDataURL(blob);
  }

  // After artifact render, scan img-ai and set up
  function initImgAi() {
    const slots = getImgAiSlots();
    const count = slots.length;
    imgPanelBtn.style.display = '';
    imgPanelBtn.classList.toggle('disabled', count === 0);
    imgCount.textContent = String(count);

    if (count > 0) {
      loadPool().then(() => {
        const assignments = imgSlots._assignments || {};
        slots.forEach(s => {
          // 优先级: image-id 属性 > 已有指派(跨render) > prompt(自动生成) > placeholder
          if (s.imageId && !assignments[s.aiId]) {
            // image-id 属性:预上传图片,直接指派(不需要生成)
            if (imgSlots.has(s.imageId) || true) {
              assignments[s.aiId] = s.imageId;
              if (!imgSlots._assignments) imgSlots._assignments = {};
              imgSlots._assignments[s.aiId] = s.imageId;
              // 同步通知服务端
              fetch(`/api/${SID}/assign-image`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ ai_id: s.aiId, image_id: s.imageId }),
              }).catch(() => {});
            }
          }
        });
        syncImgAiElements();
        // 对有 prompt 且无指派的槽位自动生成
        slots.forEach(s => {
          if (s.prompt && !assignments[s.aiId]) {
            autoGenerate(s.aiId, s.prompt);
          }
        });
      });
    }
  }

  async function autoGenerate(aiId, prompt) {
    const el = container.querySelector(`img-ai[data-ai-id="${CSS.escape(aiId)}"]`);
    if (el) {
      el.innerHTML = `<div class="imgai-placeholder"><div class="spinner"></div><div>生成中…</div><div style="font-size:11px;margin-top:4px;max-width:200px;word-break:break-all">${escHtml(prompt)}</div></div>`;
      // 加上画笔角标,即使在生成中也能打开画布
      const badge = document.createElement('div');
      badge.className = 'imgai-badge visible';
      badge.innerHTML = '🎨';
      badge.addEventListener('click', (ev) => { ev.stopPropagation(); toggleImgPanel(aiId); });
      el.appendChild(badge);
    }
    try {
      const r = await fetch(`/api/${SID}/generate`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ prompt, n: 1, size: (el && el.getAttribute('size')) || '1024x1024' }),
      });
      const d = await r.json();
      if (d.ok && d.images && d.images.length) {
        const first = d.images[0];
        imgSlots.set(first.image_id, { image_id: first.image_id, url: first.url, prompt, source: 'generated', label: '' });
        await assignImage(aiId, first.image_id);
        refreshImgPanel();
        syncImgAiElements();
      } else {
        const ph = el && el.querySelector('.imgai-placeholder');
        if (ph) ph.innerHTML =
          `<div style="color:var(--asc-accent)">⚠ 生成失败</div><div style="font-size:11px">${escHtml(d.error||'')}</div>`;
      }
    } catch(e) {
      console.error('autoGenerate', e);
      const ph = el && el.querySelector('.imgai-placeholder');
      if (ph) ph.innerHTML =
        `<div style="color:var(--asc-accent)">⚠ 生成失败</div><div style="font-size:11px">${escHtml(e.message)}</div>`;
    }
  }

  // ───── image lightbox (click-to-zoom) ─────
  function openLightbox(src) {
    imgLightbox.querySelector('img').src = src;
    imgLightbox.classList.remove('hidden');
  }
  function closeLightbox() {
    imgLightbox.classList.add('hidden');
    imgLightbox.querySelector('img').src = '';
  }
  imgLightbox.addEventListener('click', (e) => {
    if (e.target === imgLightbox || e.target.classList.contains('lb-close')) closeLightbox();
  });
  container.addEventListener('click', (e) => {
    const img = e.target.closest('img-ai img');
    if (img && img.src) { e.stopPropagation(); openLightbox(img.src); }
  });

  // ───── image hint toast ─────
  let hintToastTimer = null;
  function showImgHint() {
    imgHintToast.classList.add('visible');
    clearTimeout(hintToastTimer);
    hintToastTimer = setTimeout(() => imgHintToast.classList.remove('visible'), 5000);
  }
  imgHintToast.addEventListener('click', () => {
    imgHintToast.classList.remove('visible');
    clearTimeout(hintToastTimer);
  });

  // ───── SSE wire ─────
  function reportError(kind, err) {
    fetch(`/ui/${SID}/error`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: kind,
        message: String(err && err.message || err),
        stack: err && err.stack || null,
      }),
    }).catch(() => {});
  }

  let everConnected = false;
  const es = new EventSource(`/ui/${SID}/events`);
  es.addEventListener('open', () => {
    everConnected = true;
    if (!hasArtifact) showStatus('等待 AI 发送内容...', 'text-gray-400');
  });
  function upsertStyleSlot(id, css) {
    const el = document.getElementById(id);
    if (!el) return;
    if (typeof css === 'string' && el.textContent !== css) el.textContent = css;
  }
  function applyStyles(d) {
    // 壳子主题变量(ass-chrome-vars)+ 模版预设(ass-preset-styles)
    // + 会话自定义(ass-session-styles)分槽更新。换模版时三槽一起热刷新,
    // 右下角工具栏 / 日记本 / 弹窗随之换肤。chrome_css 缺省时不动壳子主题。
    if (d.chrome_css !== undefined) upsertStyleSlot('ass-chrome-vars', d.chrome_css);
    upsertStyleSlot('ass-preset-styles', d.preset_css);
    upsertStyleSlot('ass-session-styles', d.session_css);
    if (d.template) {
      assCurrentTemplate = d.template;
      tplSelect.value = d.template;
      if (tplSelect._ascSync) tplSelect._ascSync();   // 回填模拟下拉的显示文字
    }
  }
  // set_session 单独调用(不跟 render)时热更新样式:只换皮肤,不动 artifact。
  es.addEventListener('styles', (e) => {
    try { applyStyles(JSON.parse(e.data)); }
    catch (err) { console.error('styles update failed', err); }
  });
  es.addEventListener('artifact', (e) => {
    try {
      const d = JSON.parse(e.data);
      applyStyles(d);
      renderArtifact(d.html || '');
    } catch (err) {
      console.error('render failed', err);
      reportError('render', err);
      showStatus('⚠️ 渲染失败,等待新内容...', 'text-red-500');
    }
  });
  es.addEventListener('taken-over', () => {
    es.close();
    container.innerHTML = '';
    badgeLayer.innerHTML = '';
    hasArtifact = false;
    notebook.classList.remove('visible');
    hideSubmitOverlay();
    showStatus('ℹ️ 此标签已在别处打开', 'text-gray-500');
  });
  es.addEventListener('end', () => {
    es.close();
    container.innerHTML = '';
    badgeLayer.innerHTML = '';
    hasArtifact = false;
    notebook.classList.remove('visible');
    hideSubmitOverlay();
    showStatus('✅ 对话已结束,可关闭此页面', 'text-green-600');
  });
  es.addEventListener('error', () => {
    if (es.readyState === EventSource.CLOSED) {
      if (everConnected) showStatus('✅ 对话已结束,可关闭此页面', 'text-green-600');
      else showStatus('⚠️ 无法连接服务器', 'text-red-500');
    }
  });
})();
</script>
</body>
</html>
"""


def render_html(
    sid: str,
    preset_css: str = "",
    session_css: str = "",
    chrome_css: str = "",
    template_name: str = "",
) -> str:
    tpl_list = "[" + ",".join(f'"{k}"' for k in TEMPLATES) + "]"
    tpl_name = template_name or DEFAULT_TEMPLATE
    return (
        HTML_TEMPLATE
        .replace("__SID__", sid)
        .replace("__CHROME_VARS__", chrome_css)
        .replace("__PRESET_STYLES__", preset_css)
        .replace("__INITIAL_STYLES__", session_css)
        .replace("__TEMPLATE_LIST__", tpl_list)
        .replace("__CURRENT_TEMPLATE__", tpl_name)
        .replace("__MERMAID_CONFIGS__", mermaid_configs_json())
        .replace("__FAVICON_B64__", LOGO_FAVICON_B64)
    )


# ───── 导出模板(无 host 壳子的独立 HTML)─────

EXPORT_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>agent-speak export</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,__FAVICON_B64__">
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/highlight.min.js"></script>
<style type="text/tailwindcss">__PRESET_STYLES__</style>
<style type="text/tailwindcss">__SESSION_STYLES__</style>
</head>
<body>
<div class="artifact-root">__HTML__</div>
<script>
hljs.highlightAll();
(function(){
  var els = document.querySelectorAll('pre.mermaid');
  if (!els.length) return;
  var s = document.createElement('script');
  var cdns = ['https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js','https://unpkg.com/mermaid@11.4.1/dist/mermaid.min.js'];
  function tryLoad(i) {
    if (i >= cdns.length) return;
    var s = document.createElement('script');
    s.src = cdns[i];
    s.onload = function(){ mermaid.initialize(__MERMAID_INIT_CONFIG__); mermaid.run({nodes:els}); };
    s.onerror = function(){ s.remove(); tryLoad(i+1); };
    document.head.appendChild(s);
  }
  tryLoad(0);
})();
</script>
</body>
</html>
"""


def export_html(
    html: str,
    preset_css: str = "",
    session_css: str = "",
    template_name: str = "",
) -> str:
    import json
    cfg = mermaid_init_config(template_name)
    cfg["startOnLoad"] = False
    return (
        EXPORT_TEMPLATE
        .replace("__PRESET_STYLES__", preset_css)
        .replace("__SESSION_STYLES__", session_css)
        .replace("__HTML__", html)
        .replace("__MERMAID_INIT_CONFIG__", json.dumps(cfg, ensure_ascii=False))
        .replace("__FAVICON_B64__", LOGO_FAVICON_B64)
    )


# ───── 会话级自定义 CSS 的解析/拼装 ─────
#
# 约定:set_session(css="...") 收一段扁平 CSS——一个选择器一条规则、不嵌套、
# 不 @media。用最小正则解析成 {selector: body};不符合的规则被静默丢弃
# (AI 看返回值的 styles 字段就能知道哪条生效了)。规则体推荐 @apply,也可裸 CSS。

# 匹配最浅一层的 selector { body }。嵌套花括号会让本式直接失配,从而丢弃,
# 这是我们希望的安全副作用——不会错切。
_FLAT_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)


def parse_css_rules(css: str) -> dict[str, str]:
    """把一段扁平 CSS 解析成 {selector: body}。

    例:'.card { @apply p-4; } .pill { @apply text-xs; }'
       → {'.card': '@apply p-4', '.pill': '@apply text-xs'}
    """
    rules: dict[str, str] = {}
    for r in _FLAT_RULE.finditer(css or ""):
        sel = r.group(1).strip()
        body = r.group(2).strip().rstrip(";").strip()
        if sel and body:
            rules[sel] = body
    return rules


def compose_styles_css(rules: dict[str, str]) -> str:
    """把自定义规则拼成最终注入页面的 CSS 字符串。

    所有选择器加 `.artifact-root ` 前缀,避免污染壳子(工具栏/日记本)。
    """
    if not rules:
        return ""
    lines = []
    for sel, body in rules.items():
        body = body.rstrip(";").strip()
        lines.append(f".artifact-root {sel} {{ {body}; }}")
    return "\n".join(lines)



# ───── 以下符号从 presets 重导出,保持外部 import 路径不变 ─────
__all__ = [
    "HTML_TEMPLATE", "EXPORT_TEMPLATE",
    "render_html", "export_html",
    "parse_css_rules", "compose_styles_css",
    # 从 presets 重导出
    "TEMPLATES", "DEFAULT_TEMPLATE", "CHROME_THEMES",
    "MERMAID_THEMES", "MERMAID_THEME_VARS", "TEMPLATE_GUIDES", "IMAGE_STYLE_GUIDES",
    "template_css", "chrome_vars_css", "template_guide", "image_style_guide",
    "mermaid_init_config", "mermaid_configs_json",
]
