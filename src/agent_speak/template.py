"""浏览器 HTML 壳 + 纯 vanilla JS host。

Host 的核心职责:
- 自动锚点:AI 写普通 HTML 即可,不必手写 data-ai-id。注入后 host 给白名单内
  尚未带锚点的元素补一个会话内唯一的 data-ai-id(见 ensureAnchors),让任意有
  意义的元素都能被批注;AI 自己写的 data-ai-id 优先保留。
- DOM Inspector:右下角日记本里的"批注"开关(默认开),开启时悬停 data-ai-id
  节点显示蓝色高亮 + 提示,点击进入编辑;关闭仅停掉嗅探,日记本本身始终在。
- 日记本:右下角的小本子,始终可见。一条条记录,空也是本子。底部三个动作:
  模式切换 / 预览要发送的 payload / 直接发送。
- 元素徽章:每条已保存的批注在元素内部右上角投一个黄色数字徽章
  (放在元素内部以避免靠边时被裁掉),点徽章即可回去编辑。
- Uncontrolled Form Harvest:扫描 input/textarea/select。
- 安全:innerHTML 注入后剥掉 on* 内联事件。
- 顶部不再有 toolbar,对 artifact 侵入最小。
- 提交后展示"请保持此页面打开"横幅,下一份 artifact 推过来时自动消失。
"""
from __future__ import annotations

import re


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>agent-speak</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  html, body { height: 100%; margin: 0; }
  body { background: #e9e0ca; color: #1a1a1a; font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; }

  #container {
    min-height: 100vh;
    max-width: 880px;
    margin: 0 auto;
    padding: 32px 20px;
    box-sizing: border-box;
  }
  #container[data-frozen="true"] { opacity: 0.5; pointer-events: none; }

  /* Crosshair while inspecting — scoped to artifact only */
  body.inspecting #container,
  body.inspecting #container * { cursor: crosshair !important; }

  /* Hover highlight overlay */
  #highlight {
    position: fixed; pointer-events: none; z-index: 8000;
    border: 2px solid #2563eb; border-radius: 4px;
    background: rgba(37,99,235,0.08);
    transition: top 80ms ease-out, left 80ms ease-out, width 80ms ease-out, height 80ms ease-out;
    display: none;
  }
  #highlight .label {
    position: absolute; top: -24px; left: -2px;
    background: #2563eb; color: white;
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
    outline: 2px solid #8b1e1e;
    outline-offset: 1px;
    border-radius: 0;
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
    background: #8b1e1e;
    color: #f4ecd8;
    font-family: Georgia, serif;
    font-size: 11px; font-weight: 900;
    font-style: italic;
    display: flex; align-items: center; justify-content: center;
    border: 2px solid #f4ecd8;
    box-shadow: 0 2px 6px rgba(26,26,26,0.30);
    transform: translateX(-100%);
    pointer-events: auto;
    cursor: pointer;
    transition: transform 120ms, background 120ms;
  }
  .anno-badge:hover {
    transform: translateX(-100%) scale(1.18);
    background: #6b1414;
  }
  .anno-badge.active {
    background: #1a1a1a; color: #f4ecd8;
    box-shadow: 0 0 0 3px rgba(26,26,26,0.30), 0 2px 6px rgba(26,26,26,0.30);
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
    width: 320px;
    background: #f4ecd8;
    border: 2px solid #1a1a1a;
    border-radius: 0;
    box-shadow: 4px 4px 0 #1a1a1a;
    overflow: hidden;
    display: flex; flex-direction: column;
    max-height: 60vh;
    color: #1a1a1a;
    font-family: Georgia, "Songti SC", "Source Han Serif SC", "Noto Serif CJK SC", serif;
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
    border-bottom: 3px double #1a1a1a;
    color: #1a1a1a;
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
    color: #8b1e1e;
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
    border-bottom: 2px solid #1a1a1a;
    background: rgba(26, 26, 26, 0.04);
  }
  #edit-area.hidden { display: none; }
  #edit-area .target-id {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 10px;
    color: #f4ecd8;
    background: #1a1a1a;
    padding: 3px 8px;
    border-radius: 0;
    letter-spacing: 0.04em;
    margin-bottom: 8px; display: inline-block;
    max-width: 100%; overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap;
  }
  #edit-area textarea {
    width: 100%; height: 76px; box-sizing: border-box;
    border: 1px solid #1a1a1a; border-radius: 0;
    padding: 8px;
    font-size: 13px; resize: vertical;
    font-family: inherit; color: #1a1a1a;
    background: #fffaf0;
  }
  #edit-area textarea:focus {
    outline: 0;
    border-color: #8b1e1e;
    box-shadow: inset 0 0 0 1px #8b1e1e;
  }
  #edit-area .row {
    display: flex; justify-content: space-between; align-items: center;
    margin-top: 8px; gap: 8px;
  }
  #edit-area button {
    border: 1px solid #1a1a1a;
    border-radius: 0;
    padding: 5px 12px;
    font-family: inherit;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    cursor: pointer;
    background: transparent;
    color: #1a1a1a;
  }
  #edit-area .delete {
    border-color: #8b1e1e; color: #8b1e1e;
  }
  #edit-area .delete:hover { background: #8b1e1e; color: #f4ecd8; }
  #edit-area .right-btns { display: flex; gap: 6px; }
  #edit-area .cancel:hover { background: rgba(26,26,26,0.08); }
  #edit-area .save { background: #1a1a1a; color: #f4ecd8; }
  #edit-area .save:hover { background: #8b1e1e; border-color: #8b1e1e; }

  /* Notebook entries — newspaper article fragments */
  #anno-list .empty {
    padding: 26px 18px;
    text-align: center;
    color: #6b6b6b; font-size: 13px; line-height: 1.7;
    font-style: italic;
  }
  #anno-list .item {
    display: flex; gap: 12px;
    padding: 10px 16px;
    cursor: pointer;
    border-bottom: 1px solid rgba(26, 26, 26, 0.18);
    transition: background 100ms;
  }
  #anno-list .item:last-child { border-bottom: 0; }
  #anno-list .item:hover { background: rgba(26, 26, 26, 0.05); }
  #anno-list .item.editing { background: rgba(139, 30, 30, 0.10); }
  #anno-list .num {
    flex-shrink: 0;
    font-family: inherit;
    font-weight: 900;
    font-size: 22px;
    line-height: 1;
    color: #8b1e1e;
    min-width: 22px;
    padding-top: 2px;
    font-style: italic;
  }
  #anno-list .item.editing .num { color: #1a1a1a; }
  #anno-list .item-body { flex: 1; min-width: 0; }
  #anno-list .aid {
    font-family: ui-monospace, monospace;
    font-size: 10px;
    color: #6b6b6b;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 2px;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  #anno-list .text {
    font-family: inherit;
    font-size: 14px;
    color: #1a1a1a;
    line-height: 1.5;
    overflow: hidden; text-overflow: ellipsis;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  }

  /* Newspaper-stamp toolbar: solid block with hard offset shadow */
  .nb-toolbar {
    display: inline-flex; align-items: stretch;
    background: #f4ecd8;
    border: 2px solid #1a1a1a;
    border-radius: 0;
    box-shadow: 4px 4px 0 #1a1a1a;
    font-family: Georgia, "Songti SC", "Source Han Serif SC", "Noto Serif CJK SC", serif;
  }
  .nb-toolbar > * + * { border-left: 1px solid #1a1a1a; }
  .nb-toolbar button {
    background: transparent;
    border: 0;
    border-radius: 0;
    padding: 10px 17px;
    font-family: inherit;
    font-size: 12px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.10em;
    color: #1a1a1a;
    cursor: pointer;
    display: inline-flex; align-items: center; gap: 7px;
    line-height: 1;
  }
  .nb-toolbar button:hover { background: rgba(26, 26, 26, 0.08); }
  .nb-toolbar button:focus { outline: none; }
  .nb-toolbar button:focus-visible {
    outline: 2px solid #8b1e1e;
    outline-offset: -2px;
  }

  #mode-btn .indicator {
    width: 8px; height: 8px; border-radius: 50%;
    background: #6b6b6b; flex-shrink: 0;
  }
  #mode-btn.on {
    background: #1a1a1a; color: #f4ecd8;
  }
  #mode-btn.on:hover { background: #2a2a2a; }
  #mode-btn.on .indicator {
    background: #f4ecd8;
    animation: pulse-paper 1.6s infinite;
  }
  @keyframes pulse-paper {
    0%, 100% { box-shadow: 0 0 0 0 rgba(244, 236, 216, 0.7); }
    50%      { box-shadow: 0 0 0 5px rgba(244, 236, 216, 0); }
  }

  /* SEND — the only green in the whole UI, always visible primary action */
  #send-btn {
    background: #2d7148;
    color: #f4ecd8;
  }
  #send-btn:not(:disabled):hover { background: #1f5634; }
  #send-btn:disabled {
    background: rgba(26, 26, 26, 0.12);
    color: rgba(26, 26, 26, 0.32);
    cursor: not-allowed;
  }
  #send-btn:disabled:hover { background: rgba(26, 26, 26, 0.12); }

  /* Small help/question-mark — same toolbar family */
  #help-btn {
    padding: 0 12px;
    font-family: Georgia, serif;
    font-size: 15px;
    font-weight: 900;
    font-style: italic;
    color: #6b6b6b;
    background: transparent;
    border: 0;
    border-radius: 0;
    line-height: 1;
    cursor: pointer;
  }
  #help-btn:hover { background: rgba(26,26,26,0.08); color: #1a1a1a; }
  #help-btn:focus { outline: none; }
  #help-btn:focus-visible {
    outline: 2px solid #8b1e1e;
    outline-offset: -2px;
  }

  /* ───── tutorial modal — newspaper poster with 3 tabs + knockout caps ───── */
  #tutorial-modal {
    position: fixed; inset: 0; z-index: 9700;
    display: flex; align-items: center; justify-content: center;
    background: rgba(26, 26, 26, 0.55);
    backdrop-filter: blur(2px);
    -webkit-backdrop-filter: blur(2px);
    padding: 24px;
  }
  #tutorial-modal.hidden { display: none; }
  #tutorial-modal .t-card {
    background: #f4ecd8;
    width: min(640px, 100%);
    max-height: 88vh;
    border: 3px solid #1a1a1a;
    border-radius: 0;
    box-shadow: 8px 8px 0 #1a1a1a;
    display: flex; flex-direction: column;
    overflow: hidden;
    color: #1a1a1a;
    font-family: Georgia, "Songti SC", "Source Han Serif SC", "Noto Serif CJK SC", serif;
  }

  /* Compact head */
  #tutorial-modal .t-head {
    display: flex; align-items: flex-start; justify-content: space-between;
    padding: 16px 24px 12px;
    border-bottom: 4px double #1a1a1a;
  }
  #tutorial-modal .t-kicker {
    display: block;
    font-size: 10px; font-weight: 700;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    color: #8b1e1e;
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
    font-family: Georgia, serif;
    font-size: 26px; color: #1a1a1a; line-height: 1;
    padding: 0 4px;
  }
  #tutorial-modal .t-close:hover { color: #8b1e1e; }

  /* Tab strip — 3 equal cells, active = knockout */
  #tutorial-modal .t-tabs {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    border-bottom: 3px solid #1a1a1a;
    background: #f4ecd8;
  }
  #tutorial-modal .t-tab {
    background: transparent;
    border: 0;
    border-right: 1px solid rgba(26,26,26,0.2);
    padding: 14px 8px 12px;
    cursor: pointer;
    display: flex; flex-direction: column; align-items: center; gap: 4px;
    font-family: inherit;
    color: #1a1a1a;
    transition: background 120ms;
  }
  #tutorial-modal .t-tab:last-child { border-right: 0; }
  #tutorial-modal .t-tab:hover { background: rgba(26,26,26,0.05); }
  #tutorial-modal .t-tab-num {
    font-family: Georgia, serif;
    font-style: italic;
    font-weight: 900;
    font-size: 26px;
    line-height: 1;
    color: #8b1e1e;
  }
  #tutorial-modal .t-tab-label {
    font-weight: 800;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: #1a1a1a;
  }
  #tutorial-modal .t-tab.active { background: #1a1a1a; }
  #tutorial-modal .t-tab.active .t-tab-num,
  #tutorial-modal .t-tab.active .t-tab-label {
    color: #f4ecd8;
  }
  #tutorial-modal .t-tab:focus { outline: none; }
  #tutorial-modal .t-tab:focus-visible {
    outline: 2px solid #8b1e1e; outline-offset: -2px;
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
    background: #1a1a1a;
    color: #f4ecd8;
    font-family: Georgia, serif;
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
    color: #8b1e1e;
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
    border-left: 4px solid #8b1e1e;
    padding: 4px 0 4px 14px;
    margin: 16px 0;
    font-style: italic;
    color: #1a1a1a;
  }
  #tutorial-modal .t-pane p.huge {
    font-size: 32px;
    font-weight: 900;
    line-height: 1.2;
    letter-spacing: 0.02em;
    margin: 18px 0;
    background: #1a1a1a;
    color: #f4ecd8;
    padding: 14px 18px;
    display: inline-block;
  }
  #tutorial-modal .t-pane strong { font-weight: 900; }
  #tutorial-modal .t-pane em { font-style: italic; color: #6b6b6b; }
  #tutorial-modal .t-pane a {
    color: #8b1e1e;
    font-style: italic;
    text-decoration: underline;
    text-decoration-color: rgba(139, 30, 30, 0.4);
  }
  #tutorial-modal .t-pane a:hover { text-decoration-color: #8b1e1e; }
  #tutorial-modal .t-pane .t-source {
    font-size: 12px; color: #6b6b6b;
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
    border-bottom: 1px solid rgba(26,26,26,0.18);
    align-items: start;
  }
  #tutorial-modal .t-steps li:last-child { border-bottom: 0; }
  #tutorial-modal .t-steps li::before {
    counter-increment: step;
    content: counter(step);
    grid-column: 1;
    grid-row: 1 / span 2;
    align-self: start;
    font-family: Georgia, serif;
    font-style: italic;
    font-weight: 900;
    font-size: 36px;
    line-height: 1;
    color: #8b1e1e;
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
  #tutorial-modal .t-steps li span { color: #1a1a1a; font-size: 13.5px; }

  /* Footer */
  #tutorial-modal .t-foot {
    display: flex; justify-content: flex-end; gap: 8px;
    padding: 14px 28px;
    border-top: 4px double #1a1a1a;
    background: rgba(26, 26, 26, 0.03);
  }
  #tutorial-modal .t-ok {
    background: #1a1a1a;
    color: #f4ecd8;
    border: 2px solid #1a1a1a;
    border-radius: 0;
    padding: 8px 22px;
    font-family: inherit;
    font-size: 12px; font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    cursor: pointer;
  }
  #tutorial-modal .t-ok:hover {
    background: #8b1e1e;
    border-color: #8b1e1e;
  }

  /* ───── preview modal — same vintage palette ───── */
  #preview-modal {
    position: fixed; inset: 0; z-index: 9500;
    display: flex; align-items: center; justify-content: center;
    background: rgba(26, 26, 26, 0.45);
    backdrop-filter: blur(2px);
    padding: 24px;
  }
  #preview-modal.hidden { display: none; }
  #preview-modal .modal-card {
    background: #f4ecd8;
    width: min(560px, 100%);
    max-height: 82vh;
    border: 3px solid #1a1a1a;
    border-radius: 0;
    box-shadow: 6px 6px 0 #1a1a1a;
    display: flex; flex-direction: column;
    overflow: hidden;
    color: #1a1a1a;
    font-family: Georgia, "Songti SC", "Source Han Serif SC", "Noto Serif CJK SC", serif;
  }
  #preview-modal header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 16px 24px 12px;
    border-bottom: 3px double #1a1a1a;
    font-family: inherit;
    font-weight: 900;
    font-size: 18px;
    text-transform: uppercase;
    letter-spacing: 0.02em;
    color: #1a1a1a;
    background: transparent;
  }
  #preview-modal header .close {
    border: 0; background: transparent; cursor: pointer;
    font-family: Georgia, serif;
    font-size: 26px; color: #1a1a1a; line-height: 1;
    padding: 0 4px;
    font-weight: 400;
  }
  #preview-modal header .close:hover { color: #8b1e1e; }
  #preview-modal .modal-body {
    flex: 1; overflow: auto;
    padding: 14px 24px;
    font-size: 14px; line-height: 1.65;
  }
  #preview-modal footer {
    display: flex; justify-content: flex-end; gap: 8px;
    padding: 12px 24px;
    border-top: 3px double #1a1a1a;
    background: rgba(26, 26, 26, 0.03);
  }
  #preview-modal footer button {
    border: 2px solid #1a1a1a;
    border-radius: 0;
    padding: 6px 18px;
    font-family: inherit;
    font-size: 11px;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 0.10em;
    cursor: pointer;
    background: transparent;
    color: #1a1a1a;
  }
  #preview-modal .modal-cancel:hover { background: rgba(26,26,26,0.08); }
  #preview-modal .modal-send {
    background: #1a1a1a;
    color: #f4ecd8;
  }
  #preview-modal .modal-send:hover {
    background: #8b1e1e; border-color: #8b1e1e;
  }
  #preview-modal .section { margin-bottom: 14px; }
  #preview-modal .section h3 {
    font-family: inherit;
    font-size: 11px;
    font-weight: 900;
    color: #8b1e1e;
    text-transform: uppercase;
    letter-spacing: 0.20em;
    margin: 8px 0 6px;
    padding-bottom: 4px;
    border-bottom: 2px solid #1a1a1a;
  }
  #preview-modal .section .empty {
    color: #6b6b6b; font-size: 13px;
    font-style: italic; padding: 4px 0;
  }
  #preview-modal .p-item {
    display: flex; gap: 12px;
    padding: 7px 0;
    border-bottom: 1px solid rgba(26, 26, 26, 0.15);
  }
  #preview-modal .p-item:last-child { border-bottom: 0; }
  #preview-modal .p-item .num {
    flex-shrink: 0;
    font-family: Georgia, serif;
    font-weight: 900;
    font-style: italic;
    font-size: 20px;
    line-height: 1;
    color: #8b1e1e;
    padding-top: 2px;
    min-width: 22px;
  }
  #preview-modal .p-item .meta {
    font-family: ui-monospace, monospace;
    font-size: 10px;
    color: #6b6b6b;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 2px;
  }
  #preview-modal .p-item .text {
    font-family: inherit;
    font-size: 14px;
    color: #1a1a1a;
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
    background: rgba(244, 236, 216, 0.93);
    backdrop-filter: blur(3px);
    -webkit-backdrop-filter: blur(3px);
    z-index: 9100;  /* below notebook (9200), so user can still operate it */
    display: flex;
    flex-direction: column;
    align-items: center; justify-content: center;
    text-align: center;
    padding: 32px;
    color: #1a1a1a;
    font-family: Georgia, "Songti SC", "Source Han Serif SC", "Noto Serif CJK SC", serif;
    opacity: 0; pointer-events: none;
    transition: opacity 240ms ease;
  }
  #submit-overlay.visible { opacity: 1; pointer-events: auto; }
  #submit-overlay .icon {
    font-size: 14px; font-weight: 700;
    color: #8b1e1e;
    letter-spacing: 0.32em;
    text-transform: uppercase;
    margin-bottom: 10px;
  }
  #submit-overlay .title {
    font-family: inherit;
    font-size: 38px; font-weight: 900;
    color: #1a1a1a;
    margin: 0 auto 14px;
    letter-spacing: 0.02em;
    line-height: 1.05;
    text-transform: uppercase;
    display: inline-flex; align-items: center; gap: 14px;
    padding: 8px 0;
    border-top: 3px double #1a1a1a;
    border-bottom: 3px double #1a1a1a;
  }
  #submit-overlay .pulse-dot {
    display: inline-block;
    width: 12px; height: 12px; border-radius: 50%;
    background: #8b1e1e;
    animation: pulse-ink 1.6s infinite;
  }
  @keyframes pulse-ink {
    0%, 100% { box-shadow: 0 0 0 0 rgba(139, 30, 30, 0.45); }
    50%      { box-shadow: 0 0 0 9px rgba(139, 30, 30, 0); }
  }
  #submit-overlay .subtitle {
    font-family: inherit;
    font-size: 15px; color: #1a1a1a;
    line-height: 1.75; max-width: 440px;
    margin-top: 6px;
  }
  #submit-overlay .subtitle strong { color: #8b1e1e; font-weight: 900; }
</style>
<!-- 模版预设语义类(register_css 选哪套就注入哪套;所有模版共用同一组 ass-* 类名)。
     默认报纸风格;切换模版时这里整段被替换。源码见本文件底部 TEMPLATES。 -->
<style id="ass-preset-styles" type="text/tailwindcss">__PRESET_STYLES__</style>
<!-- 会话级自定义 CSS:register_css(css=...) 注入的命名类规则。
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
    <button id="mode-btn" class="on" type="button" title="批注模式开关">
      <span class="indicator"></span>
      <span id="mode-label">批注中</span>
    </button>
    <button id="preview-btn" type="button" title="预览发送内容">预览</button>
    <button id="send-btn" type="button" disabled title="发送给 AI">发送</button>
    <button id="help-btn" type="button" title="使用教程" aria-label="帮助">?</button>
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
            <span>右下角药丸的"批注"按钮在闪,说明正在嗅探</span>
          </li>
          <li>
            <strong>点元素批注</strong>
            <span>鼠标停在元素上 → 蓝框出现 → 点击 → 在便签里写"这块改成…"</span>
          </li>
          <li>
            <strong>预览 然后发送</strong>
            <span>点"预览"对照内容,确认后点"发送"——绿色按钮,最显眼那个</span>
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
<div id="status"></div>

<script>
(function(){
  const SID = "__SID__";
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
  const previewBtn = document.getElementById('preview-btn');
  const sendBtn = document.getElementById('send-btn');
  const previewModal = document.getElementById('preview-modal');
  const previewBody = document.getElementById('preview-body');
  const submitOverlay = document.getElementById('submit-overlay');
  const tutorialModal = document.getElementById('tutorial-modal');
  const helpBtn = document.getElementById('help-btn');

  const TUTORIAL_SEEN_KEY = 'agent-speak.tutorial.seen.v1';
  let firstArtifactSeen = false;

  /** ai_id -> {instruction, html_hint} (insertion-order = display order) */
  const annotations = new Map();
  let hasArtifact = false;
  let isInspecting = true;   // 默认打开
  let editingId = null;

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
    'A','IMG','SVG','VIDEO','AUDIO','CANVAS','PICTURE',
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
    const formCount = container.querySelectorAll('input, textarea, select').length;
    const total = annotations.size + formCount;
    sendBtn.disabled = !hasArtifact;
    // surface useful count in the title attribute
    sendBtn.title = hasArtifact ? `发送 ${total} 项内容给 AI` : '等待 artifact';
    previewBtn.disabled = !hasArtifact;
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
        : '<div class="empty">还没有批注<br>开启上方"批注"模式,<br>就能在页面上添加</div>';
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
      if (!tutorialModal.classList.contains('hidden')) { closeTutorial(); return; }
      if (!previewModal.classList.contains('hidden')) { closePreview(); return; }
      if (editingId) { editingId = null; updatePanel(); }
      else if (isInspecting) setInspecting(false);
    }
  });

  // ───── artifact render ─────
  function renderArtifact(html) {
    container.innerHTML = html;
    sanitizeInjected();
    ensureAnchors();
    container.dataset.frozen = 'false';
    annotations.clear();
    editingId = null;
    hasArtifact = true;
    hideHighlight();
    hideSubmitOverlay();
    clearStatus();
    setInspecting(isInspecting);
    maybeShowFirstTimeTutorial();
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
    return {
      user_comments: [...annotations.entries()].map(([id, a]) => ({
        target_id: id,
        element_html_hint: a.html_hint,
        instruction: a.instruction,
      })),
      user_form_inputs: harvestForms(),
    };
  }

  // ───── preview modal ─────
  function openPreview() {
    if (!hasArtifact) return;
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
  function closePreview() { previewModal.classList.add('hidden'); }

  previewBtn.addEventListener('click', openPreview);

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
  tutorialModal.addEventListener('click', (e) => {
    if (e.target === tutorialModal) { closeTutorial(); return; }
    const btn = e.target.closest('button');
    if (!btn) return;
    if (btn.classList.contains('t-close') || btn.classList.contains('t-ok')) {
      closeTutorial();
    }
  });
  previewModal.addEventListener('click', (e) => {
    if (e.target === previewModal) { closePreview(); return; }
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
    sendBtn.disabled = true;
    previewBtn.disabled = true;
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
  sendBtn.addEventListener('click', doSubmit);

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
    // 模版预设(ass-preset-styles)+ 会话自定义(ass-session-styles)分槽更新。
    upsertStyleSlot('ass-preset-styles', d.preset_css);
    upsertStyleSlot('ass-session-styles', d.session_css);
  }
  // register_css 单独调用(不跟 render)时热更新样式:只换皮肤,不动 artifact。
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


def render_html(sid: str, preset_css: str = "", session_css: str = "") -> str:
    return (
        HTML_TEMPLATE
        .replace("__SID__", sid)
        .replace("__PRESET_STYLES__", preset_css)
        .replace("__INITIAL_STYLES__", session_css)
    )


# ───── 会话级自定义 CSS 的解析/拼装 ─────
#
# 约定:register_css(css="...") 收一段扁平 CSS——一个选择器一条规则、不嵌套、
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


def template_css(name: str | None) -> str:
    """取某套模版的预设 CSS 源码;未知/空名回退到默认模版。"""
    return TEMPLATES.get(name or "", TEMPLATES[DEFAULT_TEMPLATE])


# ───── 模版库 ─────
#
# 每套模版定义**同一组 ass-* 语义类**,只是视觉 token 不同——这样 AI 写的 HTML
# 一个字都不用改,register_css 切换模版即换皮肤。选择器都带 `.artifact-root`
# 前缀(只作用于内容区,不碰 host 工具条);每套自带一条 body 底色让风格完整。
# 类清单:布局 ass-panel/section/row/col;文字 ass-h1/h2/hint/code/kbd/divider;
# 表单 ass-field/label/input/textarea/select/check-row;
# 按钮 ass-btn + primary/ghost/danger;提示 ass-alert + info/warn/danger。

_NEWSPAPER_CSS = """
  /* 内容区整体定调:深墨色文字 + 衬线(含中文衬线回退) */
  body { @apply bg-[#e9e0ca]; }
  .artifact-root { @apply text-[#1a1a1a]; font-family: Georgia, "Songti SC", "Source Han Serif SC", "Noto Serif CJK SC", serif; }

  /* —— Layout —— */
  .artifact-root .ass-panel    { @apply bg-[#f4ecd8] rounded-none border-2 border-[#1a1a1a] shadow-[4px_4px_0_#1a1a1a] p-6 mb-4; }
  .artifact-root .ass-section  { @apply mb-4; }
  .artifact-root .ass-row      { @apply flex items-center gap-3; }
  .artifact-root .ass-col      { @apply flex flex-col gap-3; }

  /* —— Typography —— */
  .artifact-root .ass-h1       { @apply text-2xl font-black uppercase tracking-wide text-[#1a1a1a] mb-3 pb-2 border-b-[3px] border-double border-[#1a1a1a]; }
  .artifact-root .ass-h2       { @apply text-lg font-black uppercase tracking-wide text-[#1a1a1a] mb-2; }
  .artifact-root .ass-hint     { @apply text-xs italic text-[#6b6b6b]; }
  .artifact-root .ass-code     { @apply font-mono text-sm bg-[#1a1a1a] text-[#f4ecd8] px-1.5 py-0.5 rounded-none; }
  .artifact-root .ass-kbd      { @apply font-mono text-xs bg-[#fffaf0] border border-[#1a1a1a] rounded-none px-1.5 py-0.5; }
  .artifact-root .ass-divider  { @apply border-t-[3px] border-double border-[#1a1a1a] my-4; }

  /* —— Forms —— */
  .artifact-root .ass-field    { @apply flex flex-col mb-3; }
  .artifact-root .ass-label    { @apply block text-sm font-bold text-[#1a1a1a] mb-1; }
  .artifact-root .ass-input,
  .artifact-root .ass-textarea,
  .artifact-root .ass-select   { @apply block w-full rounded-none border border-[#1a1a1a] bg-[#fffaf0] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#8b1e1e] focus:border-[#8b1e1e]; }
  .artifact-root .ass-textarea { @apply min-h-[6rem]; }
  .artifact-root .ass-check-row{ @apply flex items-center gap-2 text-sm text-[#1a1a1a]; }

  /* —— Buttons:base + variant —— */
  .artifact-root .ass-btn          { @apply inline-flex items-center justify-center gap-1.5 rounded-none border border-[#1a1a1a] px-3.5 py-2 text-sm font-bold uppercase tracking-wider transition-colors disabled:opacity-50 cursor-pointer; }
  .artifact-root .ass-btn-primary  { @apply bg-[#1a1a1a] text-[#f4ecd8] hover:bg-[#8b1e1e] hover:border-[#8b1e1e]; }
  .artifact-root .ass-btn-ghost    { @apply bg-transparent text-[#1a1a1a] border border-[#1a1a1a] hover:bg-[rgba(26,26,26,0.08)]; }
  .artifact-root .ass-btn-danger   { @apply bg-[#8b1e1e] text-[#f4ecd8] border-[#8b1e1e] hover:bg-[#6b1414]; }

  /* —— Alerts —— */
  .artifact-root .ass-alert         { @apply rounded-none border-l-4 p-3 text-sm; }
  .artifact-root .ass-alert-info    { @apply bg-[#fffaf0] border-[#1a1a1a] text-[#1a1a1a]; }
  .artifact-root .ass-alert-warn    { @apply bg-[#f7eccf] border-[#b8860b] text-[#7a5a00]; }
  .artifact-root .ass-alert-danger  { @apply bg-[#f7e3e3] border-[#8b1e1e] text-[#8b1e1e]; }
"""

_MINIMAL_CSS = """
  /* 极简白:现代 SaaS,纯白 + 细灰边 + 留白 + 克制蓝色 */
  body { @apply bg-[#fafafa]; }
  .artifact-root { @apply text-slate-700; font-family: ui-sans-serif, system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }

  /* —— Layout —— */
  .artifact-root .ass-panel    { @apply bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-4; }
  .artifact-root .ass-section  { @apply mb-4; }
  .artifact-root .ass-row      { @apply flex items-center gap-3; }
  .artifact-root .ass-col      { @apply flex flex-col gap-3; }

  /* —— Typography —— */
  .artifact-root .ass-h1       { @apply text-2xl font-semibold tracking-tight text-slate-900 mb-2; }
  .artifact-root .ass-h2       { @apply text-lg font-semibold text-slate-900 mb-2; }
  .artifact-root .ass-hint     { @apply text-xs text-slate-400; }
  .artifact-root .ass-code     { @apply font-mono text-sm bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded; }
  .artifact-root .ass-kbd      { @apply font-mono text-xs bg-white border border-slate-300 rounded px-1.5 py-0.5 shadow-sm; }
  .artifact-root .ass-divider  { @apply border-t border-slate-200 my-4; }

  /* —— Forms —— */
  .artifact-root .ass-field    { @apply flex flex-col mb-3; }
  .artifact-root .ass-label    { @apply block text-sm font-medium text-slate-700 mb-1; }
  .artifact-root .ass-input,
  .artifact-root .ass-textarea,
  .artifact-root .ass-select   { @apply block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500; }
  .artifact-root .ass-textarea { @apply min-h-[6rem]; }
  .artifact-root .ass-check-row{ @apply flex items-center gap-2 text-sm text-slate-700; }

  /* —— Buttons —— */
  .artifact-root .ass-btn          { @apply inline-flex items-center justify-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors disabled:opacity-50 cursor-pointer; }
  .artifact-root .ass-btn-primary  { @apply bg-blue-600 text-white hover:bg-blue-700; }
  .artifact-root .ass-btn-ghost    { @apply bg-white text-slate-700 border border-slate-300 hover:bg-slate-50; }
  .artifact-root .ass-btn-danger   { @apply bg-red-600 text-white hover:bg-red-700; }

  /* —— Alerts —— */
  .artifact-root .ass-alert         { @apply rounded-lg border p-3 text-sm; }
  .artifact-root .ass-alert-info    { @apply bg-blue-50 border-blue-200 text-blue-800; }
  .artifact-root .ass-alert-warn    { @apply bg-amber-50 border-amber-200 text-amber-800; }
  .artifact-root .ass-alert-danger  { @apply bg-red-50 border-red-200 text-red-800; }
"""

_CYBER_CSS = """
  /* 暗夜霓虹:深色底 + 霓虹青/品红 + 发光 */
  body { @apply bg-[#0a0e14]; }
  .artifact-root { @apply text-slate-200; font-family: ui-sans-serif, system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }

  /* —— Layout —— */
  .artifact-root .ass-panel    { @apply bg-[#111827] rounded-xl border border-cyan-500/30 shadow-[0_0_24px_rgba(34,211,238,0.10)] p-6 mb-4; }
  .artifact-root .ass-section  { @apply mb-4; }
  .artifact-root .ass-row      { @apply flex items-center gap-3; }
  .artifact-root .ass-col      { @apply flex flex-col gap-3; }

  /* —— Typography —— */
  .artifact-root .ass-h1       { @apply text-2xl font-bold tracking-tight text-cyan-300 mb-3 pb-2 border-b border-cyan-500/30; text-shadow: 0 0 14px rgba(34,211,238,0.45); }
  .artifact-root .ass-h2       { @apply text-lg font-bold text-fuchsia-300 mb-2; }
  .artifact-root .ass-hint     { @apply text-xs text-slate-500; }
  .artifact-root .ass-code     { @apply font-mono text-sm bg-black/50 text-cyan-300 px-1.5 py-0.5 rounded border border-cyan-500/20; }
  .artifact-root .ass-kbd      { @apply font-mono text-xs bg-[#1f2937] border border-slate-600 rounded px-1.5 py-0.5 text-slate-200; }
  .artifact-root .ass-divider  { @apply border-t border-cyan-500/20 my-4; }

  /* —— Forms —— */
  .artifact-root .ass-field    { @apply flex flex-col mb-3; }
  .artifact-root .ass-label    { @apply block text-sm font-medium text-cyan-200 mb-1; }
  .artifact-root .ass-input,
  .artifact-root .ass-textarea,
  .artifact-root .ass-select   { @apply block w-full rounded-lg border border-slate-600 bg-[#0d1420] px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-400/40 focus:border-cyan-400; }
  .artifact-root .ass-textarea { @apply min-h-[6rem]; }
  .artifact-root .ass-check-row{ @apply flex items-center gap-2 text-sm text-slate-200; }

  /* —— Buttons —— */
  .artifact-root .ass-btn          { @apply inline-flex items-center justify-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-semibold transition-all disabled:opacity-50 cursor-pointer; }
  .artifact-root .ass-btn-primary  { @apply bg-cyan-500 text-[#0a0e14] hover:bg-cyan-400 shadow-[0_0_16px_rgba(34,211,238,0.45)]; }
  .artifact-root .ass-btn-ghost    { @apply bg-transparent text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500/10; }
  .artifact-root .ass-btn-danger   { @apply bg-fuchsia-600 text-white hover:bg-fuchsia-500 shadow-[0_0_16px_rgba(217,70,239,0.45)]; }

  /* —— Alerts —— */
  .artifact-root .ass-alert         { @apply rounded-lg border-l-4 p-3 text-sm; }
  .artifact-root .ass-alert-info    { @apply bg-cyan-500/10 border-cyan-400 text-cyan-200; }
  .artifact-root .ass-alert-warn    { @apply bg-amber-500/10 border-amber-400 text-amber-200; }
  .artifact-root .ass-alert-danger  { @apply bg-fuchsia-500/10 border-fuchsia-400 text-fuchsia-200; }
"""

_CANDY_CSS = """
  /* 柔和糖果:粉彩暖底 + 大圆角 + 柔和阴影 + 粉紫强调 */
  body { @apply bg-[#fbf0f7]; }
  .artifact-root { @apply text-slate-700; font-family: ui-sans-serif, system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }

  /* —— Layout —— */
  .artifact-root .ass-panel    { @apply bg-white rounded-3xl border border-pink-100 shadow-[0_8px_28px_rgba(236,72,153,0.10)] p-6 mb-4; }
  .artifact-root .ass-section  { @apply mb-4; }
  .artifact-root .ass-row      { @apply flex items-center gap-3; }
  .artifact-root .ass-col      { @apply flex flex-col gap-3; }

  /* —— Typography —— */
  .artifact-root .ass-h1       { @apply text-2xl font-bold text-pink-600 mb-2; }
  .artifact-root .ass-h2       { @apply text-lg font-bold text-purple-500 mb-2; }
  .artifact-root .ass-hint     { @apply text-xs text-slate-400; }
  .artifact-root .ass-code     { @apply font-mono text-sm bg-pink-50 text-pink-600 px-2 py-0.5 rounded-full; }
  .artifact-root .ass-kbd      { @apply font-mono text-xs bg-white border border-pink-200 rounded-lg px-1.5 py-0.5; }
  .artifact-root .ass-divider  { @apply border-t border-pink-100 my-4; }

  /* —— Forms —— */
  .artifact-root .ass-field    { @apply flex flex-col mb-3; }
  .artifact-root .ass-label    { @apply block text-sm font-semibold text-slate-600 mb-1; }
  .artifact-root .ass-input,
  .artifact-root .ass-textarea,
  .artifact-root .ass-select   { @apply block w-full rounded-2xl border border-pink-200 bg-white px-4 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-pink-300 focus:border-pink-400; }
  .artifact-root .ass-textarea { @apply min-h-[6rem]; }
  .artifact-root .ass-check-row{ @apply flex items-center gap-2 text-sm text-slate-600; }

  /* —— Buttons —— */
  .artifact-root .ass-btn          { @apply inline-flex items-center justify-center gap-1.5 rounded-full px-4 py-2 text-sm font-semibold transition-colors disabled:opacity-50 cursor-pointer; }
  .artifact-root .ass-btn-primary  { @apply bg-pink-500 text-white hover:bg-pink-600; }
  .artifact-root .ass-btn-ghost    { @apply bg-white text-pink-600 border border-pink-200 hover:bg-pink-50; }
  .artifact-root .ass-btn-danger   { @apply bg-rose-500 text-white hover:bg-rose-600; }

  /* —— Alerts —— */
  .artifact-root .ass-alert         { @apply rounded-2xl border p-3 text-sm; }
  .artifact-root .ass-alert-info    { @apply bg-sky-50 border-sky-200 text-sky-700; }
  .artifact-root .ass-alert-warn    { @apply bg-amber-50 border-amber-200 text-amber-700; }
  .artifact-root .ass-alert-danger  { @apply bg-rose-50 border-rose-200 text-rose-700; }
"""

_MAGAZINE_CSS = """
  /* 杂志大刊:黑白高对比 + 鲜橙强调 + 粗黑标题 + 下划线式输入 */
  body { @apply bg-white; }
  .artifact-root { @apply text-neutral-900; font-family: Georgia, "Songti SC", "Source Han Serif SC", "Noto Serif CJK SC", serif; }

  /* —— Layout —— */
  .artifact-root .ass-panel    { @apply bg-white rounded-none border border-neutral-900 p-6 mb-4; }
  .artifact-root .ass-section  { @apply mb-5; }
  .artifact-root .ass-row      { @apply flex items-center gap-3; }
  .artifact-root .ass-col      { @apply flex flex-col gap-3; }

  /* —— Typography(标题用无衬线粗体,正文衬线) —— */
  .artifact-root .ass-h1       { @apply text-3xl font-black tracking-tight text-neutral-900 mb-3 leading-none; font-family: ui-sans-serif, system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }
  .artifact-root .ass-h2       { @apply text-xl font-black uppercase tracking-wide text-orange-600 mb-2; font-family: ui-sans-serif, system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }
  .artifact-root .ass-hint     { @apply text-xs italic text-neutral-500; }
  .artifact-root .ass-code     { @apply font-mono text-sm bg-neutral-900 text-white px-1.5 py-0.5; }
  .artifact-root .ass-kbd      { @apply font-mono text-xs bg-white border border-neutral-900 px-1.5 py-0.5; }
  .artifact-root .ass-divider  { @apply border-t-2 border-neutral-900 my-5; }

  /* —— Forms —— */
  .artifact-root .ass-field    { @apply flex flex-col mb-3; }
  .artifact-root .ass-label    { @apply block text-sm font-bold uppercase tracking-wide text-neutral-900 mb-1; font-family: ui-sans-serif, system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }
  .artifact-root .ass-input,
  .artifact-root .ass-textarea,
  .artifact-root .ass-select   { @apply block w-full rounded-none border-0 border-b-2 border-neutral-900 bg-transparent px-1 py-2 text-sm text-neutral-900 focus:outline-none focus:border-orange-600; }
  .artifact-root .ass-textarea { @apply min-h-[6rem] border-2 border-neutral-900 px-2; }
  .artifact-root .ass-check-row{ @apply flex items-center gap-2 text-sm text-neutral-900; }

  /* —— Buttons —— */
  .artifact-root .ass-btn          { @apply inline-flex items-center justify-center gap-1.5 rounded-none px-4 py-2 text-sm font-bold uppercase tracking-wide transition-colors disabled:opacity-50 cursor-pointer; font-family: ui-sans-serif, system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }
  .artifact-root .ass-btn-primary  { @apply bg-orange-600 text-white hover:bg-neutral-900; }
  .artifact-root .ass-btn-ghost    { @apply bg-white text-neutral-900 border border-neutral-900 hover:bg-neutral-100; }
  .artifact-root .ass-btn-danger   { @apply bg-neutral-900 text-white hover:bg-orange-600; }

  /* —— Alerts —— */
  .artifact-root .ass-alert         { @apply rounded-none border-l-4 p-3 text-sm; }
  .artifact-root .ass-alert-info    { @apply bg-neutral-100 border-neutral-900 text-neutral-900; }
  .artifact-root .ass-alert-warn    { @apply bg-orange-50 border-orange-600 text-orange-800; }
  .artifact-root .ass-alert-danger  { @apply bg-red-50 border-red-600 text-red-700; }
"""

DEFAULT_TEMPLATE = "报纸"

TEMPLATES: dict[str, str] = {
    "报纸": _NEWSPAPER_CSS,
    "极简白": _MINIMAL_CSS,
    "暗夜霓虹": _CYBER_CSS,
    "柔和糖果": _CANDY_CSS,
    "杂志大刊": _MAGAZINE_CSS,
}
