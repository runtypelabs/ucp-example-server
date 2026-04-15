"""Home page for the UCP demo server."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()

WIDGET_SNIPPET = """<!-- Runtype Persona Chat Widget -->
<script
  src="https://cdn.jsdelivr.net/npm/@runtypelabs/persona@latest/dist/install.global.js"
  data-config='{"version":"latest","windowKey":"ucpAgent","config":{"apiUrl":"https://api.runtype.com","clientToken":"__RUNTYPE_TOKEN__","parserType":"json","theme":{"palette":{"colors":{"primary":{"500":"#0F766E","600":"#0D6D64"},"gray":{"50":"#FAFAF9","100":"#F5F5F4","200":"#E7E5E4","500":"#78716C","900":"#1C1917"}},"typography":{"fontFamily":{"sans":"Manrope, system-ui, sans-serif"}},"radius":{"md":"6px","lg":"8px"}},"components":{"header":{"background":"#0F766E","titleForeground":"#FFFFFF","subtitleForeground":"rgba(255,255,255,0.8)","actionIconForeground":"rgba(255,255,255,0.9)","iconBackground":"rgba(255,255,255,0.15)","iconForeground":"#FFFFFF"}}},"launcher":{"enabled":true,"title":"UCP Shopping Agent","subtitle":"Buy flowers with AI over UCP","position":"bottom-right"},"features":{"showReasoning":true,"showToolCalls":true,"scrollToBottom":{"enabled":true,"iconName":"arrow-down","label":""},"toolCallDisplay":{"collapsedMode":"tool-name","activePreview":false,"grouped":true,"previewMaxLines":2,"expandable":true,"loadingAnimation":"shimmer"},"reasoningDisplay":{"activePreview":true,"previewMaxLines":3,"expandable":true}},"toolCall":{"activeTextTemplate":"Calling {toolName}... ~{duration}~","completeTextTemplate":"Finished {toolName} ~{duration}~"}}}'
></script>"""

HOME_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>UCP Demo Server</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #FAFAF9;
    --surface: #FFFFFF;
    --surface-alt: #F5F5F4;
    --fg: #1C1917;
    --muted: #78716C;
    --muted-light: #A8A29E;
    --accent: #0F766E;
    --accent-subtle: #F0FDFA;
    --border: #E7E5E4;
    --code-bg: #1C1917;
    --code-fg: #D6D3D1;
    --green: #059669;
    --green-bg: #ECFDF5;
    --red: #DC2626;
    --red-bg: #FEF2F2;
    --orange: #D97706;
    --radius: 6px;
  }

  /* Dark theme — applied when user picks "dark" OR system prefers dark with no override */
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #141413;
      --surface: #1C1C1A;
      --surface-alt: #232321;
      --fg: #E8E6E3;
      --muted: #9C9891;
      --muted-light: #6B6860;
      --accent: #2DD4BF;
      --accent-subtle: #0F2B27;
      --border: #2E2E2B;
      --code-bg: #0E0E0D;
      --code-fg: #D6D3D1;
      --green: #34D399;
      --green-bg: #0B2618;
      --red: #F87171;
      --red-bg: #2D1111;
      --orange: #FBBF24;
    }
  }
  [data-theme="dark"] {
    --bg: #141413;
    --surface: #1C1C1A;
    --surface-alt: #232321;
    --fg: #E8E6E3;
    --muted: #9C9891;
    --muted-light: #6B6860;
    --accent: #2DD4BF;
    --accent-subtle: #0F2B27;
    --border: #2E2E2B;
    --code-bg: #0E0E0D;
    --code-fg: #D6D3D1;
    --green: #34D399;
    --green-bg: #0B2618;
    --red: #F87171;
    --red-bg: #2D1111;
    --orange: #FBBF24;
  }

  *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
  html { scroll-behavior: smooth; }
  body {
    font-family: 'Manrope', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg);
    color: var(--fg);
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
  .container { max-width: 760px; margin: 0 auto; padding: 3.5rem 1.5rem 4rem; }

  /* Header */
  header { margin-bottom: 3rem; }
  .version-tag {
    font-family: 'Fira Code', monospace;
    font-size: 0.72rem;
    color: var(--accent);
    font-weight: 500;
    letter-spacing: 0.02em;
    margin-bottom: 0.5rem;
  }
  h1 {
    font-size: 1.65rem;
    font-weight: 800;
    letter-spacing: -0.035em;
    line-height: 1.2;
    color: var(--fg);
  }
  .subtitle {
    color: var(--muted);
    font-size: 0.925rem;
    margin-top: 0.625rem;
    line-height: 1.65;
    max-width: 560px;
  }
  .subtitle a { color: var(--accent); font-weight: 600; }

  /* Section headings */
  h2 {
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--muted);
    margin: 3.5rem 0 1.25rem;
  }

  p, li { color: var(--muted); font-size: 0.9rem; }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }

  /* Code */
  code {
    font-family: 'Fira Code', 'SF Mono', monospace;
    font-size: 0.8em;
    background: var(--surface-alt);
    padding: 0.15em 0.4em;
    border-radius: 3px;
    color: var(--fg);
  }
  pre {
    position: relative;
    background: var(--code-bg);
    border-radius: var(--radius);
    padding: 1rem 1.25rem;
    overflow-x: auto;
    margin: 0.75rem 0;
  }
  .copy-btn {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 4px;
    color: var(--code-fg);
    font-family: 'Fira Code', monospace;
    font-size: 0.65rem;
    padding: 0.25rem 0.5rem;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.15s, background 0.15s;
  }
  pre:hover .copy-btn { opacity: 1; }
  .copy-btn:hover { background: rgba(255,255,255,0.15); }
  .copy-btn.copied { color: #6EE7B7; }
  pre code {
    background: none;
    padding: 0;
    color: var(--code-fg);
    font-size: 0.78rem;
    line-height: 1.7;
  }
  .string { color: #6EE7B7; }

  /* Tables */
  table { width: 100%; border-collapse: collapse; margin: 0.75rem 0; font-size: 0.875rem; }
  th {
    text-align: left;
    padding: 0.5rem 0.75rem 0.5rem 0;
    border-bottom: 1.5px solid var(--fg);
    font-weight: 700;
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--muted);
  }
  td { padding: 0.55rem 0.75rem 0.55rem 0; border-bottom: 1px solid var(--border); color: var(--muted); }
  td code { font-size: 0.8rem; }

  /* Search */
  .search-bar { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
  .search-bar input {
    flex: 1;
    padding: 0.55rem 0.875rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--fg);
    font-family: inherit;
    font-size: 0.875rem;
    outline: none;
    transition: border-color 0.2s;
  }
  .search-bar input:focus { border-color: var(--accent); }
  .search-bar input::placeholder { color: var(--muted-light); }
  .search-bar button {
    padding: 0.55rem 1.25rem;
    background: var(--fg);
    color: var(--bg);
    border: none;
    border-radius: var(--radius);
    font-family: inherit;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s;
  }
  .search-bar button:hover { opacity: 0.8; }

  /* Product grid */
  .product-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 0.625rem; margin: 0.5rem 0; }
  .product {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.875rem 1rem;
    cursor: pointer;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .product:hover { border-color: var(--accent); box-shadow: 0 1px 8px rgba(0,0,0,0.04); }
  .product .name { font-weight: 700; font-size: 0.9rem; color: var(--fg); margin-bottom: 0.2rem; }
  .product .desc { color: var(--muted); font-size: 0.78rem; margin-bottom: 0.4rem; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.5; }
  .product .meta { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; }
  .product .price { color: var(--green); font-weight: 700; font-size: 0.95rem; font-family: 'Fira Code', monospace; }
  .product .id-label { color: var(--muted-light); font-size: 0.65rem; font-family: 'Fira Code', monospace; margin-top: 0.4rem; }
  .product .cats { margin-top: 0.35rem; display: flex; flex-wrap: wrap; gap: 0.25rem; }
  .product .cat { font-size: 0.6rem; padding: 0.1rem 0.4rem; border-radius: 3px; background: var(--surface-alt); color: var(--muted); font-weight: 500; }
  .product-loading { color: var(--muted); text-align: center; padding: 2rem; font-size: 0.875rem; }
  .result-count { color: var(--muted); font-size: 0.78rem; margin-bottom: 0.5rem; }
  .pagination { display: flex; justify-content: center; margin-top: 0.75rem; }
  .pagination button {
    padding: 0.35rem 0.875rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--fg);
    font-family: inherit;
    font-size: 0.8rem;
    cursor: pointer;
    transition: border-color 0.15s;
  }
  .pagination button:hover { border-color: var(--accent); }
  .pagination button:disabled { opacity: 0.3; cursor: default; }

  /* Badges */
  .badge { display: inline-block; font-size: 0.7rem; font-weight: 600; padding: 0.15rem 0.5rem; border-radius: 3px; }
  .badge.green { background: var(--green-bg); color: var(--green); }
  .badge.sm { font-size: 0.6rem; padding: 0.1rem 0.4rem; }
  .badge.stock { background: var(--green-bg); color: var(--green); }
  .badge.oos { background: var(--red-bg); color: var(--red); }

  /* Detail panel */
  .detail-panel {
    background: var(--surface);
    border: 1.5px solid var(--accent);
    border-radius: var(--radius);
    padding: 1.5rem;
    margin: 1rem 0;
    display: none;
  }
  .detail-panel h3 { font-size: 1.1rem; font-weight: 700; margin-bottom: 0.4rem; }
  .detail-panel .detail-desc { color: var(--muted); font-size: 0.875rem; margin-bottom: 0.75rem; }
  .detail-close { float: right; background: none; border: none; color: var(--muted-light); font-size: 1.2rem; cursor: pointer; padding: 0 0.25rem; }
  .detail-close:hover { color: var(--fg); }
  .detail-json { margin-top: 1rem; }
  .detail-json summary { color: var(--accent); cursor: pointer; font-size: 0.8rem; font-weight: 600; }
  .detail-json pre { max-height: 250px; overflow-y: auto; margin-top: 0.5rem; }

  /* Option picker */
  .option-picker { margin: 0.75rem 0; display: flex; flex-wrap: wrap; gap: 1rem; }
  .option-group { display: flex; flex-direction: column; gap: 0.35rem; }
  .option-group .option-label { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); font-weight: 700; }
  .option-values { display: flex; flex-wrap: wrap; gap: 0.3rem; }
  .option-chip {
    padding: 0.3rem 0.7rem;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    font-size: 0.78rem;
    font-family: inherit;
    cursor: pointer;
    background: var(--surface);
    color: var(--fg);
    transition: border-color 0.15s, background 0.15s, color 0.15s;
  }
  .option-chip:hover { border-color: var(--accent); }
  .option-chip.selected { background: var(--fg); border-color: var(--fg); color: var(--bg); font-weight: 600; }
  .option-chip.unavailable { opacity: 0.4; text-decoration: line-through; }
  .option-chip.unavailable.selected { opacity: 0.7; }
  .option-chip.no-exist { opacity: 0.2; cursor: not-allowed; }

  .detail-variant-info {
    margin-top: 0.75rem;
    padding: 0.625rem 0.75rem;
    background: var(--surface-alt);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    font-size: 0.85rem;
  }
  .detail-variant-info .variant-title { font-weight: 600; }
  .detail-variant-info .variant-id { font-family: 'Fira Code', monospace; font-size: 0.7rem; color: var(--muted); margin-top: 0.15rem; }

  /* Fulfillment toggle */
  .fulfillment-toggle { display: flex; gap: 0; border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; margin: 0.5rem 0; }
  .fulfillment-toggle button {
    flex: 1;
    padding: 0.45rem 1rem;
    background: var(--surface);
    border: none;
    color: var(--muted);
    font-family: inherit;
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.15s;
  }
  .fulfillment-toggle button.active { background: var(--fg); color: var(--bg); font-weight: 600; }
  .fulfillment-toggle button:hover:not(.active) { color: var(--fg); }

  /* Selected item bar */
  .selected-item-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    background: var(--accent-subtle);
    border: 1px solid var(--accent);
    border-radius: var(--radius);
    margin-bottom: 0.75rem;
    font-size: 0.78rem;
  }
  .selected-item-bar .item-label { color: var(--accent); font-weight: 700; white-space: nowrap; }
  .selected-item-bar .item-name { color: var(--fg); font-weight: 500; }
  .selected-item-bar .item-id { color: var(--muted); font-family: 'Fira Code', monospace; font-size: 0.7rem; }
  .selected-item-bar .item-clear { margin-left: auto; background: none; border: none; color: var(--muted-light); cursor: pointer; font-size: 0.9rem; padding: 0 0.25rem; }
  .selected-item-bar .item-clear:hover { color: var(--fg); }
  .use-item-btn {
    display: inline-block;
    margin-top: 0.75rem;
    padding: 0.35rem 0.875rem;
    background: transparent;
    color: var(--accent);
    border: 1.5px solid var(--accent);
    border-radius: var(--radius);
    font-size: 0.78rem;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }
  .use-item-btn:hover { background: var(--accent); color: white; }

  /* Tabs */
  .checkout-tabs { margin: 1.5rem 0; }
  .tab-bar { display: flex; gap: 0; border-bottom: 1px solid var(--border); }
  .tab-btn {
    padding: 0.55rem 1rem;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--muted);
    font-family: inherit;
    font-size: 0.85rem;
    font-weight: 500;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
  }
  .tab-btn:hover { color: var(--fg); }
  .tab-btn.active { color: var(--fg); border-bottom-color: var(--fg); font-weight: 600; }
  .tab-panel { display: none; padding: 0.5rem 0 0; }
  .tab-panel.active { display: block; }

  /* Steps */
  .step { display: flex; gap: 0.75rem; margin: 1.25rem 0; }
  .step-num {
    flex-shrink: 0;
    min-width: 1.5rem;
    height: 1.5rem;
    padding: 0 0.3rem;
    font-family: 'Fira Code', monospace;
    font-size: 0.68rem;
    font-weight: 500;
    color: var(--muted);
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1.5px solid var(--border);
    border-radius: 4px;
    margin-top: 0.15rem;
  }
  .step-content { flex: 1; }
  .step-content strong { color: var(--fg); font-size: 0.925rem; font-weight: 700; }
  .step-content p { margin-top: 0.2rem; }

  .try-btn {
    display: inline-block;
    margin-top: 0.5rem;
    padding: 0.35rem 0.875rem;
    background: transparent;
    color: var(--accent);
    border: 1.5px solid var(--accent);
    border-radius: var(--radius);
    font-family: inherit;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }
  .try-btn:hover { background: var(--accent); color: white; }

  .response-box {
    background: var(--code-bg);
    border-radius: var(--radius);
    padding: 1rem;
    margin-top: 0.5rem;
    display: none;
    max-height: 300px;
    overflow-y: auto;
  }
  .response-box pre { background: none; border: none; padding: 0; margin: 0; }

  /* Links */
  .links { display: flex; flex-wrap: wrap; gap: 0.4rem 1.25rem; margin: 0.25rem 0; }
  .links a { font-size: 0.875rem; font-weight: 500; }

  /* Footer */
  footer {
    margin-top: 4rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--border);
    color: var(--muted-light);
    font-size: 0.8rem;
    text-align: center;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.3rem;
  }
  footer a { color: var(--accent); }

  /* Runtype logo invert for dark mode */
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) .runtype-logo { filter: invert(1); }
  }
  [data-theme="dark"] .runtype-logo { filter: invert(1); }

  /* Theme toggle */
  .theme-toggle {
    display: inline-flex;
    gap: 0;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    vertical-align: middle;
    margin-left: 0.75rem;
  }
  .theme-toggle button {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 1.75rem;
    padding: 0;
    background: transparent;
    border: none;
    color: var(--muted-light);
    cursor: pointer;
    transition: color 0.15s, background 0.15s;
  }
  .theme-toggle button:hover { color: var(--fg); background: var(--surface-alt); }
  .theme-toggle button.active { color: var(--fg); background: var(--surface-alt); }
  .theme-toggle button svg { width: 14px; height: 14px; }

  /* GitHub button */
  .github-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.35rem 0.75rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--fg);
    font-family: inherit;
    font-size: 0.8rem;
    font-weight: 600;
    text-decoration: none;
    transition: border-color 0.15s, background 0.15s;
  }
  .github-btn:hover { border-color: var(--accent); background: var(--surface-alt); text-decoration: none; }
  .github-btn svg { flex-shrink: 0; }
</style>
</head>
<body>
<div class="container">
  <header>
    <div style="display:flex;align-items:center;justify-content:space-between">
      <div class="version-tag">v2026-04-08</div>
      <div class="theme-toggle" id="themeToggle">
        <button data-theme-value="light" title="Light"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg></button>
        <button data-theme-value="system" title="System"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg></button>
        <button data-theme-value="dark" title="Dark"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg></button>
      </div>
    </div>
    <h1>UCP Demo Server</h1>
    <p class="subtitle">A reference implementation of the <a href="https://ucp.dev">Universal Commerce Protocol</a>. All endpoints are live — test your UCP client against the reference flower shop.</p>
    <a href="https://github.com/runtypelabs/ucp-example-server" class="github-btn" target="_blank" rel="noopener" style="margin-top:0.75rem"><svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>View on GitHub</a>
  </header>

  <h2>Try the AI Shopping Agent</h2>
  <p>Open the chat widget in the bottom-right to browse products, add to cart, and complete
  a purchase &mdash; every UCP API call is visible as a tool invocation.</p>
  <div style="display:flex;flex-wrap:wrap;gap:0.5rem;margin:0.75rem 0">
    <span style="font-family:'Fira Code',monospace;font-size:0.75rem;padding:6px 12px;background:var(--accent-subtle);color:var(--accent);border:1px solid var(--border);border-radius:var(--radius);cursor:pointer" onclick="sendToAgent('What flowers do you have?')">&ldquo;What flowers do you have?&rdquo;</span>
    <span style="font-family:'Fira Code',monospace;font-size:0.75rem;padding:6px 12px;background:var(--accent-subtle);color:var(--accent);border:1px solid var(--border);border-radius:var(--radius);cursor:pointer" onclick="sendToAgent(&quot;I'd like a dozen red roses&quot;)">&ldquo;I'd like a dozen red roses&rdquo;</span>
    <span style="font-family:'Fira Code',monospace;font-size:0.75rem;padding:6px 12px;background:var(--accent-subtle);color:var(--accent);border:1px solid var(--border);border-radius:var(--radius);cursor:pointer" onclick="sendToAgent('Ship to Portland, OR 97201')">&ldquo;Ship to Portland, OR 97201&rdquo;</span>
    <span style="font-family:'Fira Code',monospace;font-size:0.75rem;padding:6px 12px;background:var(--accent-subtle);color:var(--accent);border:1px solid var(--border);border-radius:var(--radius);cursor:pointer" onclick="sendToAgent('Complete my order')">&ldquo;Complete my order&rdquo;</span>
  </div>

  <h2>Catalog</h2>
  <div class="search-bar">
    <input type="text" id="searchInput" placeholder="Search products..." />
    <button onclick="searchCatalog()">Search</button>
  </div>
  <div class="result-count" id="resultCount"></div>
  <div class="product-grid" id="productGrid">
    <div class="product-loading">Loading catalog...</div>
  </div>
  <div class="pagination" id="pagination"></div>
  <div class="detail-panel" id="detailPanel"></div>

  <h2>Quick Start</h2>
  <div class="selected-item-bar" id="selectedItemBar" style="display:none">
    <span class="item-label">Using:</span>
    <span class="item-name" id="selectedItemName"></span>
    <span class="item-id" id="selectedItemId"></span>
    <button class="item-clear" onclick="clearSelectedItem()" title="Reset to default">&times;</button>
  </div>

  <div class="step">
    <div class="step-num">1</div>
    <div class="step-content">
      <strong>Discover capabilities</strong>
      <p>Fetch the merchant profile to see supported services and payment handlers.</p>
      <pre><code>curl {{BASE}}/.well-known/ucp</code></pre>
      <button class="try-btn" onclick="tryIt(this, '/.well-known/ucp', 'GET')">Try it</button>
      <div class="response-box"><pre><code></code></pre></div>
    </div>
  </div>

  <div class="step">
    <div class="step-num">2</div>
    <div class="step-content">
      <strong>Search the catalog</strong>
      <p>Use the catalog search endpoint to discover products.</p>
      <pre><code>curl -X POST {{BASE}}/catalog/search \\
  -H <span class="string">"Content-Type: application/json"</span> \\
  -H <span class="string">'UCP-Agent: profile="https://agent.example/profile"'</span> \\
  -H <span class="string">"request-signature: test"</span> \\
  -H <span class="string">"request-id: &lt;unique-id&gt;"</span> \\
  -d <span class="string">'{"query": "roses", "pagination": {"limit": 5}}'</span></code></pre>
      <button class="try-btn" onclick="trySearch(this)">Try it</button>
      <div class="response-box"><pre><code></code></pre></div>
    </div>
  </div>

  <div class="checkout-tabs">
    <div class="tab-bar">
      <button class="tab-btn active" onclick="switchTab('direct')">Direct checkout</button>
      <button class="tab-btn" onclick="switchTab('cart')">Via cart</button>
    </div>
    <div class="tab-panel active" id="tab-direct">
      <div class="step" style="margin-top:0">
        <div class="step-num">3</div>
        <div class="step-content">
          <strong>Create a checkout</strong>
          <p>Go straight to checkout with line items. Choose a fulfillment method:</p>
          <div class="fulfillment-toggle">
            <button class="active" onclick="setFulfillment('shipping', this)">Shipping</button>
            <button onclick="setFulfillment('pickup', this)">Pickup</button>
          </div>
          <pre><code id="checkoutCurl"></code></pre>
          <button class="try-btn" onclick="tryCheckout(this)">Try it</button>
          <div class="response-box"><pre><code></code></pre></div>
        </div>
      </div>
    </div>
    <div class="tab-panel" id="tab-cart">
      <div class="step" style="margin-top:0">
        <div class="step-num">3a</div>
        <div class="step-content">
          <strong>Create a cart</strong>
          <p>Add items to a lightweight cart for exploration.</p>
          <pre><code id="cartCurl"></code></pre>
          <button class="try-btn" onclick="tryCart(this)">Try it</button>
          <div class="response-box"><pre><code></code></pre></div>
        </div>
      </div>
      <div class="step">
        <div class="step-num">3b</div>
        <div class="step-content">
          <strong>Convert cart to checkout</strong>
          <p>Pass <code>cart_id</code> to create a checkout from the cart.</p>
          <pre><code>curl -X POST {{BASE}}/checkout-sessions \\
  -H <span class="string">"Content-Type: application/json"</span> \\
  -H <span class="string">'UCP-Agent: profile="https://agent.example/profile"'</span> \\
  -H <span class="string">"request-signature: test"</span> \\
  -H <span class="string">"idempotency-key: &lt;unique-key&gt;"</span> \\
  -H <span class="string">"request-id: &lt;unique-id&gt;"</span> \\
  -d <span class="string">'{"cart_id": "&lt;cart-id&gt;"}'</span></code></pre>
          <button class="try-btn" onclick="tryCartCheckout(this)">Try it</button>
          <div class="response-box"><pre><code></code></pre></div>
        </div>
      </div>
    </div>
  </div>

  <div class="step">
    <div class="step-num">4</div>
    <div class="step-content">
      <strong>Apply a discount</strong>
      <p>Update the checkout with a discount code:</p>
      <div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin:0.75rem 0">
        <button class="option-chip selected" onclick="selectDiscount('10OFF', this)"><code>10OFF</code> 10% off</button>
        <button class="option-chip" onclick="selectDiscount('WELCOME20', this)"><code>WELCOME20</code> 20% off</button>
        <button class="option-chip" onclick="selectDiscount('FIXED500', this)"><code>FIXED500</code> $5 off</button>
      </div>
      <button class="try-btn" onclick="tryDiscount(this)">Apply to checkout</button>
      <div class="response-box"><pre><code></code></pre></div>
    </div>
  </div>

  <h2>Endpoints</h2>
  <table>
    <tr><th>Method</th><th>Path</th><th>Description</th></tr>
    <tr><td><code>GET</code></td><td><code>/.well-known/ucp</code></td><td>Discovery profile</td></tr>
    <tr><td colspan="3" style="color:var(--accent);font-weight:700;font-size:0.62rem;text-transform:uppercase;letter-spacing:0.1em;padding-top:0.75rem;border-bottom:none;">Catalog</td></tr>
    <tr><td><code>POST</code></td><td><code>/catalog/search</code></td><td>Search products</td></tr>
    <tr><td><code>POST</code></td><td><code>/catalog/lookup</code></td><td>Batch lookup by IDs</td></tr>
    <tr><td><code>POST</code></td><td><code>/catalog/product</code></td><td>Get product detail</td></tr>
    <tr><td colspan="3" style="color:var(--accent);font-weight:700;font-size:0.62rem;text-transform:uppercase;letter-spacing:0.1em;padding-top:0.75rem;border-bottom:none;">Cart</td></tr>
    <tr><td><code>POST</code></td><td><code>/carts</code></td><td>Create cart</td></tr>
    <tr><td><code>GET</code></td><td><code>/carts/{id}</code></td><td>Get cart</td></tr>
    <tr><td><code>PUT</code></td><td><code>/carts/{id}</code></td><td>Update cart</td></tr>
    <tr><td><code>POST</code></td><td><code>/carts/{id}/cancel</code></td><td>Cancel cart</td></tr>
    <tr><td colspan="3" style="color:var(--accent);font-weight:700;font-size:0.62rem;text-transform:uppercase;letter-spacing:0.1em;padding-top:0.75rem;border-bottom:none;">Checkout</td></tr>
    <tr><td><code>POST</code></td><td><code>/checkout-sessions</code></td><td>Create checkout</td></tr>
    <tr><td><code>GET</code></td><td><code>/checkout-sessions/{id}</code></td><td>Get checkout</td></tr>
    <tr><td><code>PUT</code></td><td><code>/checkout-sessions/{id}</code></td><td>Update checkout</td></tr>
    <tr><td><code>POST</code></td><td><code>/checkout-sessions/{id}/complete</code></td><td>Complete checkout</td></tr>
    <tr><td><code>POST</code></td><td><code>/checkout-sessions/{id}/cancel</code></td><td>Cancel checkout</td></tr>
    <tr><td colspan="3" style="color:var(--accent);font-weight:700;font-size:0.62rem;text-transform:uppercase;letter-spacing:0.1em;padding-top:0.75rem;border-bottom:none;">Orders</td></tr>
    <tr><td><code>GET</code></td><td><code>/orders/{id}</code></td><td>Get order</td></tr>
    <tr><td><code>PUT</code></td><td><code>/orders/{id}</code></td><td>Update order</td></tr>
  </table>

  <h2>Required Headers</h2>
  <table>
    <tr><th>Header</th><th>Value</th><th>Required</th></tr>
    <tr><td><code>UCP-Agent</code></td><td><code>profile="https://agent.example/profile"</code></td><td>All requests</td></tr>
    <tr><td><code>Signature</code></td><td><code>sig=:test:</code> (bypasses validation)</td><td>All requests</td></tr>
    <tr><td><code>Request-Id</code></td><td>Any unique string</td><td>All requests</td></tr>
    <tr><td><code>Idempotency-Key</code></td><td>Any unique string</td><td>POST / PUT (checkout, cart)</td></tr>
  </table>

  <h2>Links</h2>
  <div class="links">
    <a href="https://ucp.dev">UCP Specification</a>
    <a href="https://github.com/Universal-Commerce-Protocol/ucp/releases/tag/v2026-04-08">v2026-04-08 Release</a>
    <a href="https://github.com/Universal-Commerce-Protocol/samples">Samples Repo</a>
    <a href="https://developers.googleblog.com/under-the-hood-universal-commerce-protocol-ucp/">Blog Post</a>
    <a href="/docs">OpenAPI Docs</a>
  </div>

  <footer>
    Shipped with <svg style="display:inline-block;vertical-align:middle;margin:0 0.15rem" width="14" height="14" viewBox="0 0 24 24" fill="#DC2626" xmlns="http://www.w3.org/2000/svg"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg> by <a href="https://runtype.com" target="_blank" rel="noopener"><img class="runtype-logo" src="https://www.runtype.com/runtype-text-only.svg" alt="Runtype" style="display:inline-block;vertical-align:middle;height:0.9em;margin-left:0.2rem;margin-top:1px" /></a>
  </footer>
</div>

<script>
// --- Theme toggle ---
(function() {
  const stored = localStorage.getItem('ucp-theme') || 'system';
  applyTheme(stored);

  document.getElementById('themeToggle').addEventListener('click', function(e) {
    const btn = e.target.closest('button[data-theme-value]');
    if (!btn) return;
    const value = btn.dataset.themeValue;
    localStorage.setItem('ucp-theme', value);
    applyTheme(value);
  });

  function applyTheme(value) {
    if (value === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark');
    } else if (value === 'light') {
      document.documentElement.setAttribute('data-theme', 'light');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
    document.querySelectorAll('#themeToggle button').forEach(function(b) {
      b.classList.toggle('active', b.dataset.themeValue === value);
    });
  }
})();

const BASE = window.location.origin;
const UCP_HEADERS = {
  'Content-Type': 'application/json',
  'UCP-Agent': 'profile="https://agent.example/profile"',
  'Signature': 'sig=:test:',
  'Request-Id': 'homepage-' + Date.now(),
};

function sendToAgent(text) {
  if (!window.ucpAgent) return;
  window.ucpAgent.submitMessage(text);
}

document.querySelectorAll('code').forEach(el => {
  el.innerHTML = el.innerHTML.replace(/{{BASE}}/g, BASE);
});

// --- Catalog search ---
let currentCursor = null;
let currentQuery = '';

document.getElementById('searchInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') searchCatalog();
});

async function searchCatalog(cursor) {
  const grid = document.getElementById('productGrid');
  const countEl = document.getElementById('resultCount');
  const query = document.getElementById('searchInput').value.trim();
  currentQuery = query;

  grid.innerHTML = '<div class="product-loading">Searching...</div>';
  countEl.textContent = '';

  const body = { query, pagination: { limit: 6 } };
  if (cursor) body.pagination.cursor = cursor;

  try {
    const res = await fetch(BASE + '/catalog/search', {
      method: 'POST', headers: UCP_HEADERS,
      body: JSON.stringify(body),
    });
    const data = await res.json();
    renderProducts(data.products);
    renderPagination(data.pagination);
    const total = data.pagination.total_count;
    if (total !== undefined) {
      countEl.textContent = total + ' product' + (total !== 1 ? 's' : '') + (query ? ' matching "' + query + '"' : '');
    }
  } catch(e) {
    grid.innerHTML = '<div class="product-loading">Error: ' + e.message + '</div>';
  }
}

function renderProducts(products) {
  const grid = document.getElementById('productGrid');
  if (!products || products.length === 0) {
    grid.innerHTML = '<div class="product-loading">No products found</div>';
    return;
  }
  grid.innerHTML = products.map(p => {
    const variant = p.variants && p.variants[0];
    const price = variant && variant.price ? '$' + (variant.price.amount / 100).toFixed(2) : '';
    const available = variant && variant.availability ? variant.availability.available : true;
    const status = available ? 'In stock' : 'Out of stock';
    const statusClass = available ? 'stock' : 'oos';
    const desc = p.description && p.description.plain ? p.description.plain : '';
    const cats = (p.categories || []).map(c => '<span class="cat">' + c.value + '</span>').join('');
    return '<div class="product" onclick="showDetail(\\''+p.id+'\\')">' +
      '<div class="name">' + p.title + '</div>' +
      (desc ? '<div class="desc">' + desc + '</div>' : '') +
      '<div class="meta">' +
        '<span class="price">' + price + '</span>' +
        '<span class="badge sm ' + statusClass + '">' + status + '</span>' +
      '</div>' +
      '<div class="id-label">' + p.id + '</div>' +
      (cats ? '<div class="cats">' + cats + '</div>' : '') +
    '</div>';
  }).join('');
}

function renderPagination(pg) {
  const el = document.getElementById('pagination');
  if (!pg) { el.innerHTML = ''; return; }
  currentCursor = pg.cursor;
  el.innerHTML = pg.has_next_page
    ? '<button onclick="searchCatalog(\\''+pg.cursor+'\\')">Load more</button>'
    : '';
}

let currentDetailProductId = null;
let currentSelections = [];
let currentDetailVariant = null;  // { id, title, productId, productTitle }

// Selected item for cart/checkout (persists across detail panel close)
let selectedItem = null;

function setSelectedItem(itemId, title, variantTitle) {
  selectedItem = { id: itemId, title: title, variantTitle: variantTitle };
  const bar = document.getElementById('selectedItemBar');
  document.getElementById('selectedItemName').textContent = variantTitle || title;
  document.getElementById('selectedItemId').textContent = itemId;
  bar.style.display = 'flex';
  updateCurlExamples();
}

function clearSelectedItem() {
  selectedItem = null;
  document.getElementById('selectedItemBar').style.display = 'none';
  updateCurlExamples();
}

function getItemForRequest() {
  if (selectedItem) return { id: selectedItem.id, title: selectedItem.variantTitle || selectedItem.title };
  return { id: 'bouquet_roses', title: 'Rose Bouquet' };
}

async function showDetail(productId, selected) {
  currentDetailProductId = productId;
  const panel = document.getElementById('detailPanel');
  panel.style.display = 'block';
  panel.innerHTML = '<div class="product-loading">Loading...</div>';
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  const reqBody = { id: productId };
  if (selected && selected.length > 0) {
    reqBody.selected = selected;
    reqBody.preferences = selected.map(s => s.name);
  }

  try {
    const res = await fetch(BASE + '/catalog/product', {
      method: 'POST', headers: UCP_HEADERS,
      body: JSON.stringify(reqBody),
    });
    const data = await res.json();
    const p = data.product;
    if (!p) {
      panel.innerHTML = '<button class="detail-close" onclick="this.parentElement.style.display=\\'none\\'">&times;</button><p>Product not found</p>';
      return;
    }

    // Track effective selections from response
    currentSelections = p.selected || [];

    const variant = p.variants && p.variants[0];
    const price = variant && variant.price ? '$' + (variant.price.amount / 100).toFixed(2) : 'N/A';
    const avail = variant && variant.availability;
    const status = avail ? (avail.available ? 'In stock' : avail.status.replace(/_/g,' ')) : 'Unknown';
    const statusClass = avail && avail.available ? 'stock' : 'oos';
    const desc = p.description && p.description.plain ? p.description.plain : '';

    // Track current variant for use-in-checkout
    currentDetailVariant = variant ? {
      id: variant.id, title: variant.title || variant.id,
      productId: p.id, productTitle: p.title,
    } : { id: p.id, title: p.title, productId: p.id, productTitle: p.title };

    // Build option picker UI
    let optionHtml = '';
    if (p.options && p.options.length > 0) {
      optionHtml = '<div class="option-picker">';
      for (const opt of p.options) {
        const selectedVal = currentSelections.find(s => s.name === opt.name);
        optionHtml += '<div class="option-group"><span class="option-label">' + opt.name + '</span><div class="option-values">';
        for (const val of opt.values) {
          let cls = 'option-chip';
          if (selectedVal && selectedVal.label === val.label) cls += ' selected';
          if (val.exists === false) cls += ' no-exist';
          else if (val.available === false) cls += ' unavailable';
          const disabled = val.exists === false ? ' disabled' : '';
          optionHtml += '<button class="' + cls + '"' + disabled + ' onclick="selectOption(\\'' + p.id + '\\', \\'' + opt.name + '\\', \\'' + val.label + '\\')">' + val.label + '</button>';
        }
        optionHtml += '</div></div>';
      }
      optionHtml += '</div>';
    }

    // Variant info + use button
    let variantHtml = '';
    if (variant) {
      const hasOptions = p.options && p.options.length > 0;
      const displayName = hasOptions ? (variant.title || variant.id) : p.title;
      variantHtml = '<div class="detail-variant-info">' +
        '<span class="variant-title">' + (variant.title || variant.id) + '</span>' +
        ' <span class="badge sm ' + statusClass + '">' + status + '</span>' +
        '<div class="variant-id">variant: ' + variant.id + (variant.sku ? ' &middot; SKU: ' + variant.sku : '') + '</div>' +
      '</div>' +
      '<button class="use-item-btn" onclick="useCurrentVariant()">Use in cart / checkout</button>';
    }

    panel.innerHTML =
      '<button class="detail-close" onclick="this.parentElement.style.display=\\'none\\'">&times;</button>' +
      '<h3>' + p.title + ' <span style="color:var(--green);font-weight:700;font-size:1.1rem">' + price + '</span></h3>' +
      (desc ? '<div class="detail-desc">' + desc + '</div>' : '') +
      optionHtml +
      variantHtml +
      '<details class="detail-json"><summary>Raw UCP response</summary><pre><code>' + JSON.stringify(data, null, 2) + '</code></pre></details>';
  } catch(e) {
    panel.innerHTML = '<button class="detail-close" onclick="this.parentElement.style.display=\\'none\\'">&times;</button><p>Error: ' + e.message + '</p>';
  }
}

function selectOption(productId, optName, optLabel) {
  let newSelections = currentSelections.filter(s => s.name !== optName);
  newSelections.push({ name: optName, label: optLabel });
  showDetail(productId, newSelections);
}

function useCurrentVariant() {
  if (!currentDetailVariant) return;
  const v = currentDetailVariant;
  // Use variant ID if product has options, otherwise product ID
  const useId = v.id !== v.productId ? v.id : v.productId;
  const displayTitle = v.id !== v.productId
    ? v.productTitle + ' - ' + v.title
    : v.productTitle;
  setSelectedItem(useId, v.productTitle, displayTitle);
}

// --- Try-it buttons ---
async function tryIt(btn, path, method) {
  const box = btn.nextElementSibling;
  const code = box.querySelector('code');
  box.style.display = 'block';
  code.textContent = 'Loading...';
  try {
    const res = await fetch(BASE + path, {method});
    const data = await res.json();
    code.textContent = JSON.stringify(data, null, 2);
  } catch(e) { code.textContent = 'Error: ' + e.message; }
}

async function trySearch(btn) {
  const box = btn.nextElementSibling;
  const code = box.querySelector('code');
  box.style.display = 'block';
  code.textContent = 'Loading...';
  try {
    const res = await fetch(BASE + '/catalog/search', {
      method: 'POST', headers: UCP_HEADERS,
      body: JSON.stringify({ query: 'roses', pagination: { limit: 5 } }),
    });
    const data = await res.json();
    code.textContent = JSON.stringify(data, null, 2);
  } catch(e) { code.textContent = 'Error: ' + e.message; }
}

async function tryCart(btn) {
  const box = btn.nextElementSibling;
  const code = box.querySelector('code');
  box.style.display = 'block';
  code.textContent = 'Loading...';
  const key = 'demo-cart-' + Date.now() + '-' + Math.random().toString(36).slice(2,8);
  const item = getItemForRequest();
  try {
    const res = await fetch(BASE + '/carts', {
      method: 'POST',
      headers: { ...UCP_HEADERS, 'idempotency-key': key },
      body: JSON.stringify({
        line_items: [
          {item: {id: item.id, title: item.title}, quantity: 2},
        ],
      }),
    });
    const data = await res.json();
    if (data.id) lastCartId = data.id;
    code.textContent = JSON.stringify(data, null, 2);
  } catch(e) { code.textContent = 'Error: ' + e.message; }
}

function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelector('.tab-btn[onclick*="' + tab + '"]').classList.add('active');
  document.getElementById('tab-' + tab).classList.add('active');
}

let lastCartId = null;
let lastCheckoutId = null;
let selectedDiscountCode = '10OFF';

async function tryCartCheckout(btn) {
  const box = btn.nextElementSibling;
  const code = box.querySelector('code');
  box.style.display = 'block';

  if (!lastCartId) {
    code.textContent = 'No cart created yet. Click "Try it" on step 3a first.';
    return;
  }

  code.textContent = 'Converting cart ' + lastCartId.slice(0,12) + '... to checkout...';
  const key = 'demo-c2c-' + Date.now() + '-' + Math.random().toString(36).slice(2,8);
  try {
    const res = await fetch(BASE + '/checkout-sessions', {
      method: 'POST',
      headers: { ...UCP_HEADERS, 'idempotency-key': key },
      body: JSON.stringify({ cart_id: lastCartId, line_items: [] }),
    });
    const data = await res.json();
    if (data.id) lastCheckoutId = data.id;
    code.textContent = JSON.stringify(data, null, 2);
  } catch(e) { code.textContent = 'Error: ' + e.message; }
}

let selectedFulfillment = 'shipping';

function setFulfillment(mode, btn) {
  selectedFulfillment = mode;
  btn.parentElement.querySelectorAll('button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  updateCurlExamples();
}

function updateCurlExamples() {
  var item = getItemForRequest();
  var NL = String.fromCharCode(10);
  var BS = String.fromCharCode(92);

  // Cart curl
  var cartEl = document.getElementById('cartCurl');
  if (cartEl) {
    var cartBody = JSON.stringify({line_items: [{item: {id: item.id}, quantity: 2}]});
    cartEl.textContent = [
      'curl -X POST ' + BASE + '/carts ' + BS,
      '  -H "Content-Type: application/json" ' + BS,
      '  -H "Signature: sig=:test:" ' + BS,
      '  -H "Idempotency-Key: <unique-key>" ' + BS,
      '  -H "Request-Id: <unique-id>" ' + BS,
      "  -d '" + cartBody + "'",
    ].join(NL);
  }

  // Checkout curl
  var checkoutEl = document.getElementById('checkoutCurl');
  if (checkoutEl) {
    var checkoutBody = {
      line_items: [{item: {id: item.id, title: item.title}, quantity: 1}],
      buyer: {full_name: 'Jane Doe', email: 'jane@example.com'},
      fulfillment: selectedFulfillment === 'pickup'
        ? {methods: [{type: 'pickup', destinations: [{name: 'Downtown Flower Shop'}]}]}
        : {methods: [{type: 'shipping', destinations: [{address_country: 'US', postal_code: '97201'}]}]},
      payment: {instruments: []},
    };
    checkoutEl.textContent = [
      'curl -X POST ' + BASE + '/checkout-sessions ' + BS,
      '  -H "Content-Type: application/json" ' + BS,
      '  -H "Signature: sig=:test:" ' + BS,
      '  -H "Idempotency-Key: <unique-key>" ' + BS,
      '  -H "Request-Id: <unique-id>" ' + BS,
      "  -d '" + JSON.stringify(checkoutBody, null, 2) + "'",
    ].join(NL);
  }
}

async function tryCheckout(btn) {
  const box = btn.nextElementSibling;
  const code = box.querySelector('code');
  box.style.display = 'block';
  code.textContent = 'Loading...';
  const key = 'demo-' + Date.now() + '-' + Math.random().toString(36).slice(2,8);
  const item = getItemForRequest();

  const body = {
    line_items: [{item: {id: item.id, title: item.title}, quantity: 1}],
    buyer: {full_name: 'Jane Doe', email: 'jane@example.com'},
    payment: {instruments: []},
  };

  if (selectedFulfillment === 'pickup') {
    body.fulfillment = {
      methods: [{
        type: 'pickup',
        destinations: [{name: 'Downtown Flower Shop'}],
      }],
    };
  } else {
    body.fulfillment = {
      methods: [{
        type: 'shipping',
        destinations: [{address_country: 'US', postal_code: '97201', address_region: 'OR', address_locality: 'Portland', street_address: '123 Main St'}],
      }],
    };
  }

  try {
    const res = await fetch(BASE + '/checkout-sessions', {
      method: 'POST',
      headers: { ...UCP_HEADERS, 'idempotency-key': key },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (data.id) lastCheckoutId = data.id;
    code.textContent = JSON.stringify(data, null, 2);
  } catch(e) { code.textContent = 'Error: ' + e.message; }
}

function selectDiscount(code, btn) {
  selectedDiscountCode = code;
  btn.parentElement.querySelectorAll('.option-chip').forEach(b => b.classList.remove('selected'));
  btn.classList.add('selected');
}

async function tryDiscount(btn) {
  var box = btn.nextElementSibling;
  var code = box.querySelector('code');
  box.style.display = 'block';

  if (!lastCheckoutId) {
    code.textContent = 'No checkout created yet. Click "Try it" on step 3 first.';
    return;
  }

  code.textContent = 'Applying ' + selectedDiscountCode + ' to checkout ' + lastCheckoutId.slice(0,12) + '...';
  var key = 'demo-discount-' + Date.now() + '-' + Math.random().toString(36).slice(2,8);
  try {
    var res = await fetch(BASE + '/checkout-sessions/' + lastCheckoutId, {
      method: 'PUT',
      headers: { ...UCP_HEADERS, 'idempotency-key': key },
      body: JSON.stringify({ discounts: { codes: [selectedDiscountCode] } }),
    });
    var data = await res.json();
    code.textContent = JSON.stringify(data, null, 2);
  } catch(e) { code.textContent = 'Error: ' + e.message; }
}

// --- Copy buttons ---
function copyCode(btn) {
  var code = btn.parentElement.querySelector('code');
  if (!code) return;
  navigator.clipboard.writeText(code.textContent).then(function() {
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(function() { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 1500);
  });
}

function injectCopyButtons() {
  document.querySelectorAll('.step-content > pre').forEach(function(pre) {
    if (pre.querySelector('.copy-btn')) return;
    var btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.textContent = 'Copy';
    btn.onclick = function() { copyCode(btn); };
    pre.appendChild(btn);
  });
}

// Initialize on page load
updateCurlExamples();
injectCopyButtons();
searchCatalog();
</script>

{{RUNTYPE_WIDGET}}

</body>
</html>"""


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
  token = getattr(request.app.state, "runtype_client_token", None)
  widget = WIDGET_SNIPPET.replace("__RUNTYPE_TOKEN__", token) if token else ""
  return HOME_HTML.replace("{{RUNTYPE_WIDGET}}", widget)
