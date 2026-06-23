"""模版预设库:CSS 皮肤 + 壳子主题 + 排版引导 + 配图风格建议。

每套模版由四层组成:
  1. 内容 CSS(_*_CSS)— .artifact-root 下的 ass-* 语义类
  2. 壳子主题(CHROME_THEMES)— --asc-* 变量,让 host UI 跟内容同步换肤
  3. 排版引导(TEMPLATE_GUIDES)— 皮肤气质 + 色盘 + 编排建议
  4. 配图风格(IMAGE_STYLE_GUIDES)— 建议的图片生成风格(非强制)

新增模版只需在本文件里加对应的四层数据,渲染引擎(template.py)无需改动。
"""
from __future__ import annotations


# ───── 模版 CSS ─────
#
# 每套模版定义**同一组 ass-* 语义类**,只是视觉 token 不同——这样 AI 写的 HTML
# 一个字都不用改,set_session 切换模版即换皮肤。选择器都带 `.artifact-root`
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

  /* —— Code Blocks (highlight.js) —— */
  .artifact-root pre { margin: 1em 0; }
  .artifact-root pre code.hljs { display: block; padding: 1em; overflow-x: auto; background: #1a1a1a; color: #f4ecd8; border: 2px solid #1a1a1a; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.875rem; line-height: 1.7; }
  .artifact-root .hljs-keyword,
  .artifact-root .hljs-selector-tag { color: #e07b53; font-weight: bold; }
  .artifact-root .hljs-string,
  .artifact-root .hljs-doctag { color: #b8bb26; }
  .artifact-root .hljs-comment { color: #6b6b6b; font-style: italic; }
  .artifact-root .hljs-number,
  .artifact-root .hljs-literal { color: #d4a959; }
  .artifact-root .hljs-title,
  .artifact-root .hljs-title.function_ { color: #f4ecd8; font-weight: bold; }
  .artifact-root .hljs-built_in { color: #e8a87c; }
  .artifact-root .hljs-type,
  .artifact-root .hljs-title.class_ { color: #c76c6c; }
  .artifact-root .hljs-attr,
  .artifact-root .hljs-variable { color: #d4a959; }
  .artifact-root .hljs-meta { color: #8b6b4a; }
  .artifact-root .hljs-punctuation { color: #a09880; }
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

  /* —— Code Blocks (highlight.js) —— */
  .artifact-root pre { margin: 1em 0; }
  .artifact-root pre code.hljs { display: block; padding: 1em; overflow-x: auto; background: #f6f8fa; color: #24292f; border: 1px solid #d0d7de; border-radius: 0.75rem; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.875rem; line-height: 1.7; }
  .artifact-root .hljs-keyword,
  .artifact-root .hljs-selector-tag { color: #cf222e; }
  .artifact-root .hljs-string,
  .artifact-root .hljs-doctag { color: #0a3069; }
  .artifact-root .hljs-comment { color: #6e7781; font-style: italic; }
  .artifact-root .hljs-number,
  .artifact-root .hljs-literal { color: #0550ae; }
  .artifact-root .hljs-title,
  .artifact-root .hljs-title.function_ { color: #8250df; }
  .artifact-root .hljs-built_in { color: #0550ae; }
  .artifact-root .hljs-type,
  .artifact-root .hljs-title.class_ { color: #953800; }
  .artifact-root .hljs-attr,
  .artifact-root .hljs-variable { color: #0550ae; }
  .artifact-root .hljs-meta { color: #6e7781; }
  .artifact-root .hljs-punctuation { color: #57606a; }
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

  /* —— Code Blocks (highlight.js) —— */
  .artifact-root pre { margin: 1em 0; }
  .artifact-root pre code.hljs { display: block; padding: 1em; overflow-x: auto; background: #0d1117; color: #c9d1d9; border: 1px solid rgba(34,211,238,0.2); border-radius: 0.75rem; box-shadow: 0 0 16px rgba(34,211,238,0.06); font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.875rem; line-height: 1.7; }
  .artifact-root .hljs-keyword,
  .artifact-root .hljs-selector-tag { color: #ff79c6; }
  .artifact-root .hljs-string,
  .artifact-root .hljs-doctag { color: #a5d6ff; }
  .artifact-root .hljs-comment { color: #8b949e; font-style: italic; }
  .artifact-root .hljs-number,
  .artifact-root .hljs-literal { color: #79c0ff; }
  .artifact-root .hljs-title,
  .artifact-root .hljs-title.function_ { color: #d2a8ff; }
  .artifact-root .hljs-built_in { color: #22d3ee; }
  .artifact-root .hljs-type,
  .artifact-root .hljs-title.class_ { color: #7ee787; }
  .artifact-root .hljs-attr,
  .artifact-root .hljs-variable { color: #79c0ff; }
  .artifact-root .hljs-meta { color: #636e7b; }
  .artifact-root .hljs-punctuation { color: #6e7681; }
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

  /* —— Code Blocks (highlight.js) —— */
  .artifact-root pre { margin: 1em 0; }
  .artifact-root pre code.hljs { display: block; padding: 1em; overflow-x: auto; background: #fef2f8; color: #4a4458; border: 1px solid #f9a8d4; border-radius: 1.5rem; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.875rem; line-height: 1.7; }
  .artifact-root .hljs-keyword,
  .artifact-root .hljs-selector-tag { color: #d946ef; }
  .artifact-root .hljs-string,
  .artifact-root .hljs-doctag { color: #059669; }
  .artifact-root .hljs-comment { color: #9ca3af; font-style: italic; }
  .artifact-root .hljs-number,
  .artifact-root .hljs-literal { color: #6366f1; }
  .artifact-root .hljs-title,
  .artifact-root .hljs-title.function_ { color: #ec4899; font-weight: 600; }
  .artifact-root .hljs-built_in { color: #8b5cf6; }
  .artifact-root .hljs-type,
  .artifact-root .hljs-title.class_ { color: #db2777; }
  .artifact-root .hljs-attr,
  .artifact-root .hljs-variable { color: #7c3aed; }
  .artifact-root .hljs-meta { color: #a1a1aa; }
  .artifact-root .hljs-punctuation { color: #a8a29e; }
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

  /* —— Code Blocks (highlight.js) —— */
  .artifact-root pre { margin: 1em 0; }
  .artifact-root pre code.hljs { display: block; padding: 1em; overflow-x: auto; background: #18181b; color: #fafafa; border: 1px solid #27272a; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.875rem; line-height: 1.7; }
  .artifact-root .hljs-keyword,
  .artifact-root .hljs-selector-tag { color: #fb923c; font-weight: bold; }
  .artifact-root .hljs-string,
  .artifact-root .hljs-doctag { color: #86efac; }
  .artifact-root .hljs-comment { color: #71717a; font-style: italic; }
  .artifact-root .hljs-number,
  .artifact-root .hljs-literal { color: #fbbf24; }
  .artifact-root .hljs-title,
  .artifact-root .hljs-title.function_ { color: #fafafa; font-weight: bold; }
  .artifact-root .hljs-built_in { color: #f97316; }
  .artifact-root .hljs-type,
  .artifact-root .hljs-title.class_ { color: #fb923c; }
  .artifact-root .hljs-attr,
  .artifact-root .hljs-variable { color: #fdba74; }
  .artifact-root .hljs-meta { color: #52525b; }
  .artifact-root .hljs-punctuation { color: #71717a; }
"""


# ───── 模版注册表 ─────

DEFAULT_TEMPLATE = "报纸"

TEMPLATES: dict[str, str] = {
    "报纸": _NEWSPAPER_CSS,
    "极简白": _MINIMAL_CSS,
    "暗夜霓虹": _CYBER_CSS,
    "柔和糖果": _CANDY_CSS,
    "杂志大刊": _MAGAZINE_CSS,
}


# ───── Mermaid 主题映射 ─────

MERMAID_THEMES: dict[str, str] = {
    "报纸": "base",
    "极简白": "base",
    "暗夜霓虹": "base",
    "柔和糖果": "base",
    "杂志大刊": "base",
}

# cScale0-6 覆盖 7 个色阶;若图表分类超过 7 个,超出部分会回退到 Mermaid 默认彩色。
# 客户端可在 mermaid 代码块顶部用 %%{init:{"theme":"base","themeVariables":{...}}}%%
# 自行追加 cScale7+ 来覆盖更多色阶。
MERMAID_THEME_VARS: dict[str, dict[str, str]] = {
    "报纸": {
        "primaryColor": "#f4ecd8",
        "primaryTextColor": "#1a1a1a",
        "primaryBorderColor": "#1a1a1a",
        "secondaryColor": "#e9e0ca",
        "secondaryTextColor": "#1a1a1a",
        "secondaryBorderColor": "#6b6b6b",
        "tertiaryColor": "#fffaf0",
        "tertiaryTextColor": "#1a1a1a",
        "tertiaryBorderColor": "#8b6b4a",
        "lineColor": "#1a1a1a",
        "textColor": "#1a1a1a",
        "mainBkg": "#f4ecd8",
        "nodeBorder": "#1a1a1a",
        "clusterBkg": "#ebe3cf",
        "clusterBorder": "#1a1a1a",
        "titleColor": "#1a1a1a",
        "edgeLabelBackground": "#f4ecd8",
        "actorBkg": "#f4ecd8",
        "actorBorder": "#1a1a1a",
        "actorTextColor": "#1a1a1a",
        "signalColor": "#1a1a1a",
        "signalTextColor": "#1a1a1a",
        "cScale0": "#f4ecd8",
        "cScale1": "#e8dfc9",
        "cScale2": "#d8cdb5",
        "cScale3": "#f0e4cc",
        "cScale4": "#ebe3cf",
        "cScale5": "#ddd3ba",
        "cScale6": "#f7f0de",
        "cScaleLabel0": "#1a1a1a",
        "cScaleLabel1": "#1a1a1a",
        "cScaleLabel2": "#1a1a1a",
        "cScaleLabel3": "#1a1a1a",
        "cScaleLabel4": "#1a1a1a",
        "cScaleLabel5": "#1a1a1a",
        "cScaleLabel6": "#1a1a1a",
    },
    "极简白": {
        "primaryColor": "#dbeafe",
        "primaryTextColor": "#1e293b",
        "primaryBorderColor": "#93c5fd",
        "secondaryColor": "#f1f5f9",
        "secondaryTextColor": "#334155",
        "secondaryBorderColor": "#cbd5e1",
        "tertiaryColor": "#e2e8f0",
        "tertiaryTextColor": "#334155",
        "tertiaryBorderColor": "#94a3b8",
        "lineColor": "#64748b",
        "textColor": "#334155",
        "mainBkg": "#dbeafe",
        "nodeBorder": "#93c5fd",
        "clusterBkg": "#f8fafc",
        "clusterBorder": "#cbd5e1",
        "titleColor": "#0f172a",
        "edgeLabelBackground": "#ffffff",
        "actorBkg": "#dbeafe",
        "actorBorder": "#93c5fd",
        "actorTextColor": "#1e293b",
        "signalColor": "#64748b",
        "signalTextColor": "#334155",
        "cScale0": "#dbeafe",
        "cScale1": "#e0e7ff",
        "cScale2": "#e2e8f0",
        "cScale3": "#ede9fe",
        "cScale4": "#f1f5f9",
        "cScale5": "#cffafe",
        "cScale6": "#e0f2fe",
        "cScaleLabel0": "#1e3a5f",
        "cScaleLabel1": "#312e81",
        "cScaleLabel2": "#334155",
        "cScaleLabel3": "#3b0764",
        "cScaleLabel4": "#334155",
        "cScaleLabel5": "#164e63",
        "cScaleLabel6": "#0c4a6e",
    },
    "暗夜霓虹": {
        "primaryColor": "#164e63",
        "primaryTextColor": "#e2e8f0",
        "primaryBorderColor": "#22d3ee",
        "secondaryColor": "#1e293b",
        "secondaryTextColor": "#e2e8f0",
        "secondaryBorderColor": "#64748b",
        "tertiaryColor": "#4c1d95",
        "tertiaryTextColor": "#e2e8f0",
        "tertiaryBorderColor": "#a78bfa",
        "lineColor": "#22d3ee",
        "textColor": "#e2e8f0",
        "mainBkg": "#164e63",
        "nodeBorder": "#22d3ee",
        "clusterBkg": "#0f172a",
        "clusterBorder": "#22d3ee",
        "titleColor": "#22d3ee",
        "edgeLabelBackground": "#111827",
        "actorBkg": "#164e63",
        "actorBorder": "#22d3ee",
        "actorTextColor": "#e2e8f0",
        "signalColor": "#22d3ee",
        "signalTextColor": "#e2e8f0",
        "cScale0": "#164e63",
        "cScale1": "#701a75",
        "cScale2": "#1e3a5f",
        "cScale3": "#4c1d95",
        "cScale4": "#14532d",
        "cScale5": "#7c2d12",
        "cScale6": "#1e1b4b",
        "cScaleLabel0": "#e2e8f0",
        "cScaleLabel1": "#e2e8f0",
        "cScaleLabel2": "#e2e8f0",
        "cScaleLabel3": "#e2e8f0",
        "cScaleLabel4": "#e2e8f0",
        "cScaleLabel5": "#e2e8f0",
        "cScaleLabel6": "#e2e8f0",
    },
    "柔和糖果": {
        "primaryColor": "#fce7f3",
        "primaryTextColor": "#4a3a44",
        "primaryBorderColor": "#f9a8d4",
        "secondaryColor": "#f3e8ff",
        "secondaryTextColor": "#4a3a44",
        "secondaryBorderColor": "#d8b4fe",
        "tertiaryColor": "#fdf2f8",
        "tertiaryTextColor": "#4a3a44",
        "tertiaryBorderColor": "#fbcfe8",
        "lineColor": "#ec4899",
        "textColor": "#4a3a44",
        "mainBkg": "#fce7f3",
        "nodeBorder": "#f9a8d4",
        "clusterBkg": "#fdf2f8",
        "clusterBorder": "#fbcfe8",
        "titleColor": "#be185d",
        "edgeLabelBackground": "#ffffff",
        "actorBkg": "#fce7f3",
        "actorBorder": "#f9a8d4",
        "actorTextColor": "#4a3a44",
        "signalColor": "#ec4899",
        "signalTextColor": "#4a3a44",
        "cScale0": "#fce7f3",
        "cScale1": "#f3e8ff",
        "cScale2": "#fdf2f8",
        "cScale3": "#ede9fe",
        "cScale4": "#fff1f2",
        "cScale5": "#fae8ff",
        "cScale6": "#ffe4e6",
        "cScaleLabel0": "#831843",
        "cScaleLabel1": "#581c87",
        "cScaleLabel2": "#831843",
        "cScaleLabel3": "#3b0764",
        "cScaleLabel4": "#881337",
        "cScaleLabel5": "#86198f",
        "cScaleLabel6": "#9f1239",
    },
    "杂志大刊": {
        "primaryColor": "#f5f5f5",
        "primaryTextColor": "#111111",
        "primaryBorderColor": "#111111",
        "secondaryColor": "#fff7ed",
        "secondaryTextColor": "#111111",
        "secondaryBorderColor": "#ea580c",
        "tertiaryColor": "#e5e5e5",
        "tertiaryTextColor": "#111111",
        "tertiaryBorderColor": "#737373",
        "lineColor": "#111111",
        "textColor": "#111111",
        "mainBkg": "#f5f5f5",
        "nodeBorder": "#111111",
        "clusterBkg": "#fafafa",
        "clusterBorder": "#111111",
        "titleColor": "#111111",
        "edgeLabelBackground": "#ffffff",
        "actorBkg": "#f5f5f5",
        "actorBorder": "#111111",
        "actorTextColor": "#111111",
        "signalColor": "#111111",
        "signalTextColor": "#111111",
        "cScale0": "#f5f5f5",
        "cScale1": "#fff7ed",
        "cScale2": "#e5e5e5",
        "cScale3": "#ffedd5",
        "cScale4": "#fafafa",
        "cScale5": "#d4d4d4",
        "cScale6": "#fed7aa",
        "cScaleLabel0": "#111111",
        "cScaleLabel1": "#9a3412",
        "cScaleLabel2": "#111111",
        "cScaleLabel3": "#9a3412",
        "cScaleLabel4": "#111111",
        "cScaleLabel5": "#111111",
        "cScaleLabel6": "#9a3412",
    },
}


# ───── 排版引导 ─────

_EDITORIAL_TIPS = (
    "排长材料时:第一屏先点明这是什么(大纲 / 提案 / 方案);主体结构作视觉重心,"
    "「目的」「总结」等辅助信息压低字号和权重;关键观点克制突出,别处处加粗;"
    "确保窄屏能自然单列阅读。"
)

_CSS_DISCIPLINE = (
    "【自定义 CSS 纪律】写 set_session(css=...) 注册新类时,必须与当前模版视觉统一:\n"
    "1. 圆角:沿用 preset_css 里已有的 rounded-* 值(如模版用 rounded-none 就全部直角,"
    "用 rounded-xl 就统一大圆角),不要在同一页面混用不同圆角策略。\n"
    "2. 配色:只用下面列出的模版色盘,不要引入色盘之外的颜色。背景/文字/边框/强调色"
    "都从色盘取值,保持整体和谐。\n"
    "3. 阴影与边框:复用 preset_css 里的 shadow-* 和 border-* 风格,不要自行发明新的"
    "阴影或边框样式。\n"
    "4. 字体:不要覆盖 font-family,模版已设好衬线/无衬线策略。\n"
    "做法:先读 set_session 返回的 preset_css,从中提取圆角、配色、阴影规则,逐条对齐。"
)

TEMPLATE_GUIDES: dict[str, str] = {
    "报纸": "复古报纸 / 海报风(粗双线分隔、衬线大标题、暗红点缀)。最适合长材料审核"
            "——大纲、提案、汇报稿。主标题可大胆放大,用 ass-divider 的粗线切分大章节,"
            "营造版面感。\n"
            "色盘:底色 #e9e0ca / 面板 #f4ecd8 / 主墨 #1a1a1a / 强调暗红 #8b1e1e / "
            "次灰 #6b6b6b / 输入底 #fffaf0。圆角策略:rounded-none(全部直角)。"
            "阴影:硬偏移 shadow-[4px_4px_0_#1a1a1a]。边框:粗实线 border-2 border-[#1a1a1a]。",
    "极简白": "现代 SaaS 风(纯白、细灰边、克制蓝)。最适合表单、设置、确认这类功能性界面。"
              "靠留白和层级说话,别堆装饰;辅助说明交给 ass-hint;尽量一屏一个焦点。\n"
              "色盘:底色 #fafafa / 面板白 #ffffff / 文字 slate-700~900 / 强调蓝 blue-600 / "
              "边框 slate-200~300。圆角策略:rounded-xl(大圆角)~rounded-lg。"
              "阴影:柔和 shadow-sm。边框:细灰 border border-slate-200。",
    "暗夜霓虹": "深色霓虹风(暗底、青 / 品红发光)。适合技术、数据、代码、监控类内容。"
                "冷色克制,靠 accent 点睛而非铺满;代码用 ass-code;信息密度可偏高,但务必分组。\n"
                "色盘:底色 #0a0e14 / 面板 #111827 / 文字 slate-200 / 强调青 cyan-400~500 / "
                "副强调品红 fuchsia-300~600 / 边框 cyan-500/30。圆角策略:rounded-xl(大圆角)~rounded-lg。"
                "阴影:发光 shadow-[0_0_24px_rgba(34,211,238,0.10)]。边框:半透明霓虹 border-cyan-500/30。",
    "柔和糖果": "圆角粉调、亲和风。适合轻量问卷、上手向导、面向非技术用户的交互。"
                "语气友好,圆角与留白让人放松;一次别问太多;多用 ass-hint 解释字段。\n"
                "色盘:底色 #fbf0f7 / 面板白 #ffffff / 文字 slate-600~700 / 强调粉 pink-500~600 / "
                "副紫 purple-500 / 边框 pink-100~200。圆角策略:rounded-3xl~rounded-2xl(超大圆角/胶囊)。"
                "阴影:粉色辉光 shadow-[0_8px_28px_rgba(236,72,153,0.10)]。边框:淡粉 border-pink-100。",
    "杂志大刊": "大字号橙调编辑风(强对比、硬朗无圆角)。适合观点、特辑、重点推荐。"
                "用大标题 + hero 制造冲击;栏目少而精;让一个核心主张占据视觉中心。\n"
                "色盘:底色白 #ffffff / 面板白 #ffffff / 主墨 neutral-900 / 强调橙 orange-600 / "
                "次灰 neutral-500。圆角策略:rounded-none(全部直角)。"
                "阴影:无或硬偏移。边框:粗黑 border border-neutral-900,输入用下划线 border-b-2。",
}


# ───── 配图风格建议 ─────
#
# 每套模版配一段"建议图片风格",随 set_session 返回,让 AI 写 <img-ai> 的 prompt
# 时有风格锚点。这只是建议——客户端每张图都可以参考但不强制。

IMAGE_STYLE_GUIDES: dict[str, str] = {
    "报纸": (
        "建议图片风格:简洁墨线插图 / 速写风报刊插画\n"
        "画面干净利落,以黑白或棕褐单色线稿为主,线条流畅简练,留白充足。"
        "色调限制在 sepia / 棕黑,可用暗红 #8b1e1e 作点缀强调。\n"
        "参考 prompt 关键词:黑白墨线插画, 简笔速写, 简报插图, "
        "棕褐单色调, 干净线稿, 留白构图\n"
        "避免:彩色照片、3D 渲染、渐变、复杂纹理——保持简洁报刊感。"
    ),
    "极简白": (
        "建议图片风格:扁平矢量 / 线性图标风\n"
        "画面干净简洁,使用几何化的简约形状,柔和低饱和配色,纯白背景,无渐变无纹理,"
        "大量留白,类似 Notion / Dropbox 品牌插画的现代商务风格。"
        "可用蓝色 #2563eb 作强调点缀。\n"
        "参考 prompt 关键词:扁平矢量插画, 极简线稿, 柔和低饱和色, 纯白背景, "
        "几何简约形状, 现代商务插画风格, 克制配色, 蓝色强调\n"
        "避免:复杂纹理、浓烈色彩、手绘质感——跟 SaaS 极简风不搭。"
    ),
    "暗夜霓虹": (
        "建议图片风格:赛博朋克 / 霓虹渲染\n"
        "画面以深色为底,搭配青色 #22d3ee 的霓虹发光效果,带有未来科技感。可使用 HUD 界面"
        "元素、扫描线、粒子特效等数字化视觉语言。\n"
        "参考 prompt 关键词:赛博朋克霓虹风, 深色背景, 青色霓虹发光, 数字渲染, "
        "合成波美学, 未来科技 HUD 界面, 荧光边缘光\n"
        "避免:暖色调、自然质感、手绘——跟冷色科技风冲突。"
    ),
    "柔和糖果": (
        "建议图片风格:绘本水彩 / 儿童插画\n"
        "画面温暖柔和,使用粉色和薰衣草色系的淡彩水彩,笔触细腻,造型圆润可爱。"
        "整体氛围友好亲和,像翻开一本治愈系绘本。\n"
        "参考 prompt 关键词:儿童绘本水彩插画, 柔和粉紫淡彩, 温暖柔光, "
        "可爱圆润造型, 细腻笔触, 梦幻温馨氛围, 奶油纸张质感\n"
        "避免:硬朗线条、高对比、暗色调——跟柔和亲和的气质冲突。"
    ),
    "杂志大刊": (
        "建议图片风格:高对比摄影 / 杂志大片\n"
        "画面强调戏剧性光影,深黑与高光形成强烈对比,整体去饱和但保留橙色调作为视觉锚点。"
        "构图大胆,浅景深,有时尚杂志社论的质感。\n"
        "参考 prompt 关键词:高对比编辑摄影, 戏剧性侧光, 深黑与高光, "
        "去饱和色调加暖橙强调, 电影感构图, 浅景深, 时尚杂志大片质感\n"
        "避免:卡通、扁平矢量、低对比——跟杂志的冲击力不匹配。"
    ),
}


# ───── 壳子主题(host chrome themes)─────
#
# 每套模版除了 ass-* 内容样式,再配一套"壳子" token,注入 #ass-chrome-vars 槽,
# 覆盖 HTML <head> :root 里的报纸默认值。于是右下角工具栏 / 日记本 / 预览弹窗 /
# 教程弹窗 / 提交遮罩 / 批注徽章全都跟内容区同一套配色,不再总是报纸的米黄+墨黑。
# token 取值刻意跟对应模版的内容配色对齐(底色 / 文字 / 强调 / 字体 / 圆角 / 阴影)。
# 语义命名让深浅主题自动正确:on-surface 既做文字也做描边,反白小块用 surface
# 当文字色,故暗色模版下也读得清;更淡的叠色由壳子 CSS 用 color-mix 从这几个基色推出。
_SANS = 'ui-sans-serif, system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif'
_SERIF = 'Georgia, "Songti SC", "Source Han Serif SC", "Noto Serif CJK SC", serif'

CHROME_THEMES: dict[str, dict[str, str]] = {
    "报纸": {
        "--asc-page": "#e9e0ca",
        "--asc-surface": "#f4ecd8",
        "--asc-on-surface": "#1a1a1a",
        "--asc-accent": "#8b1e1e",
        "--asc-accent-2": "#6b1414",
        "--asc-muted": "#6b6b6b",
        "--asc-field": "#fffaf0",
        "--asc-send": "#2d7148",
        "--asc-send-2": "#1f5634",
        "--asc-font": _SERIF,
        "--asc-radius": "0px",
        "--asc-shadow": "4px 4px 0 var(--asc-on-surface)",
        "--asc-shadow-lg": "8px 8px 0 var(--asc-on-surface)",
    },
    "极简白": {
        "--asc-page": "#fafafa",
        "--asc-surface": "#ffffff",
        "--asc-on-surface": "#0f172a",
        "--asc-accent": "#2563eb",
        "--asc-accent-2": "#1d4ed8",
        "--asc-muted": "#94a3b8",
        "--asc-field": "#ffffff",
        "--asc-send": "#16a34a",
        "--asc-send-2": "#15803d",
        "--asc-font": _SANS,
        "--asc-radius": "12px",
        "--asc-shadow": "0 6px 20px rgba(15,23,42,0.10)",
        "--asc-shadow-lg": "0 20px 50px rgba(15,23,42,0.20)",
    },
    "暗夜霓虹": {
        "--asc-page": "#0a0e14",
        "--asc-surface": "#111827",
        "--asc-on-surface": "#e2e8f0",
        "--asc-accent": "#22d3ee",
        "--asc-accent-2": "#06b6d4",
        "--asc-muted": "#64748b",
        "--asc-field": "#0d1420",
        "--asc-send": "#10b981",
        "--asc-send-2": "#059669",
        "--asc-font": _SANS,
        "--asc-radius": "12px",
        "--asc-shadow": "0 0 22px rgba(34,211,238,0.20)",
        "--asc-shadow-lg": "0 0 46px rgba(34,211,238,0.28)",
    },
    "柔和糖果": {
        "--asc-page": "#fbf0f7",
        "--asc-surface": "#ffffff",
        "--asc-on-surface": "#4a3a44",
        "--asc-accent": "#ec4899",
        "--asc-accent-2": "#db2777",
        "--asc-muted": "#a78b9c",
        "--asc-field": "#ffffff",
        "--asc-send": "#22c55e",
        "--asc-send-2": "#16a34a",
        "--asc-font": _SANS,
        "--asc-radius": "24px",
        "--asc-shadow": "0 10px 30px rgba(236,72,153,0.18)",
        "--asc-shadow-lg": "0 24px 56px rgba(236,72,153,0.26)",
    },
    "杂志大刊": {
        "--asc-page": "#ffffff",
        "--asc-surface": "#ffffff",
        "--asc-on-surface": "#111111",
        "--asc-accent": "#ea580c",
        "--asc-accent-2": "#c2410c",
        "--asc-muted": "#737373",
        "--asc-field": "#ffffff",
        "--asc-send": "#16a34a",
        "--asc-send-2": "#15803d",
        "--asc-font": _SANS,
        "--asc-radius": "0px",
        "--asc-shadow": "5px 5px 0 var(--asc-on-surface)",
        "--asc-shadow-lg": "8px 8px 0 var(--asc-on-surface)",
    },
}


# ───── 查询函数 ─────

def template_css(name: str | None) -> str:
    """取某套模版的预设 CSS 源码;未知/空名回退到默认模版。"""
    return TEMPLATES.get(name or "", TEMPLATES[DEFAULT_TEMPLATE])


def chrome_vars_css(name: str | None) -> str:
    """取某套模版的"壳子主题"CSS(注入 #ass-chrome-vars 槽)。

    返回一段 `:root { --asc-*: ...; }`,覆盖 HTML 里 :root 的报纸默认值,
    让右下角工具栏 / 日记本 / 弹窗 / 遮罩跟模版同步换肤。未知/空名回退默认模版。
    """
    tokens = CHROME_THEMES.get(name or "", CHROME_THEMES[DEFAULT_TEMPLATE])
    lines = "\n".join(f"    {k}: {v};" for k, v in tokens.items())
    return ":root {\n" + lines + "\n}"


def template_guide(name: str | None) -> str:
    """取某套模版的排版引导(皮肤气质 + 色盘 + 编排思路 + CSS 纪律);未知/空名回退默认模版。"""
    base = TEMPLATE_GUIDES.get(name or "", TEMPLATE_GUIDES[DEFAULT_TEMPLATE])
    return base + "\n" + _EDITORIAL_TIPS + "\n" + _CSS_DISCIPLINE


def mermaid_init_config(name: str | None) -> dict:
    """取某套模版的完整 mermaid.initialize() 配置(theme + themeVariables)。"""
    key = name or DEFAULT_TEMPLATE
    theme = MERMAID_THEMES.get(key, MERMAID_THEMES[DEFAULT_TEMPLATE])
    theme_vars = MERMAID_THEME_VARS.get(key, MERMAID_THEME_VARS[DEFAULT_TEMPLATE])
    return {"theme": theme, "themeVariables": theme_vars}


def mermaid_configs_json() -> str:
    """将所有模版的 Mermaid 配置序列化为 JS 对象字面量,供注入 HTML 模板。"""
    import json
    configs = {}
    for key in TEMPLATES:
        configs[key] = mermaid_init_config(key)
    return json.dumps(configs, ensure_ascii=False)


def image_style_guide(name: str | None) -> str:
    """取某套模版的配图风格建议;未知/空名回退默认模版。"""
    return IMAGE_STYLE_GUIDES.get(
        name or "", IMAGE_STYLE_GUIDES[DEFAULT_TEMPLATE]
    )
