"""Self-contained HTML for the local pyouter web ui."""

import json

PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>pyouter</title>
<style>
  :root {
    --bg: #ffffff;
    --bg-raised: #f6f5f3;
    --bg-sunken: #f3f2f0;
    --line: #e6e4e1;
    --line-strong: #d5d2cd;
    --text: #1c1c1e;
    --muted: #6e6e73;
    --faint: #8e8e93;
    --accent: #e8943a;
    --accent-ink: #ffffff;
    --icon: #f0a04a;
    --ok: #2f9e44;
    --err: #d64545;
    --run: #e8943a;
    --wait: #e0a15a;
    --shadow: 0 10px 24px rgba(28, 28, 30, 0.06);
    --sans: "Avenir Next", "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", "Microsoft YaHei", sans-serif;
    --mono: "Sarasa Mono SC", "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
    --serif: Georgia, "Songti SC", "Noto Serif SC", serif;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    font-size: 14px;
    line-height: 1.45;
  }
  button, input { font: inherit; color: inherit; }
  button { cursor: pointer; }
  button:disabled { cursor: not-allowed; opacity: 0.45; }
  .app { height: 100%; display: flex; flex-direction: column; min-height: 0; }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 12px 18px;
    border-bottom: 1px solid var(--line);
    background: #ffffff;
  }
  .brand { display: flex; align-items: center; gap: 10px; min-width: 0; }
  .brand svg { color: var(--icon); flex: none; }
  .brand strong {
    font-family: var(--serif);
    font-size: 22px;
    font-weight: 600;
    letter-spacing: -0.04em;
  }
  .brand em {
    font-style: normal;
    color: #9a5b16;
    background: #f8ead6;
    border-radius: 999px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 700;
  }
  .header-meta { display: flex; align-items: center; gap: 14px; color: var(--muted); font-family: var(--mono); font-size: 12px; }
  .header-meta .live[data-on="1"] { color: var(--run); }
  .shell {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: 320px minmax(0, 1fr);
  }
  aside {
    min-height: 0;
    display: flex;
    flex-direction: column;
    border-right: 1px solid var(--line);
    background: var(--bg-raised);
  }
  .aside-bar, .log-bar, .section-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .aside-bar { padding: 14px 14px 8px; }
  .aside-bar h2, .section-head h3, .log-bar h3 {
    margin: 0;
    font-size: 12px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    font-weight: 700;
  }
  .text-btn {
    border: 0;
    background: transparent;
    color: var(--muted);
    padding: 0;
  }
  .text-btn:hover { color: var(--text); }
  .search-wrap { padding: 0 14px 10px; }
  input[type="search"] {
    width: 100%;
    background: var(--bg-sunken);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 8px 10px;
  }
  input[type="search"]:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
  .tree { flex: 1; min-height: 0; overflow: auto; padding: 0 8px 12px; }
  .tree-row {
    display: grid;
    grid-template-columns: 16px 8px minmax(0, 1fr) auto auto;
    align-items: center;
    gap: 6px;
    width: 100%;
    margin: 1px 0;
    padding: 5px 6px;
    border: 0;
    border-radius: 8px;
    background: transparent;
    text-align: left;
    user-select: none;
  }
  .tree-row:hover { background: #f3f1ee; }
  .tree-row.selected { background: #f8ead6; box-shadow: inset 2px 0 0 var(--icon); }
  .twist, .run-mini {
    border: 0;
    background: transparent;
    color: var(--icon);
    padding: 0;
    width: 16px;
    height: 18px;
    line-height: 18px;
  }
  .twist.spacer { visibility: hidden; }
  .run-mini {
    width: 22px;
    height: 22px;
    border-radius: 6px;
    color: var(--icon);
    background: #fff8ef;
    border: 1px solid #f3d2a8;
    font-size: 11px;
  }
  .run-mini:hover { background: #f8ead6; }
  .tree-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .tree-kind { color: var(--faint); font-size: 11px; }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 99px;
    background: var(--icon);
  }
  .dot[data-status="pending"] { background: var(--wait); }
  .dot[data-status="running"] {
    background: var(--run);
    animation: pulse 1.4s infinite;
  }
  .dot[data-status="success"] { background: var(--ok); }
  .dot[data-status="error"] { background: var(--err); }
  .dot[data-status="cancelled"] { background: var(--wait); }
  @keyframes pulse {
    70% { box-shadow: 0 0 0 6px rgba(255, 176, 103, 0); }
    100% { box-shadow: 0 0 0 0 rgba(255, 176, 103, 0); }
  }
  .aside-foot {
    padding: 10px 14px 14px;
    color: var(--faint);
    font-size: 12px;
    border-top: 1px solid var(--line);
  }
  main { min-height: 0; display: flex; flex-direction: column; background: var(--bg); }
  #main { flex: 1; min-height: 0; display: flex; flex-direction: column; }
  .detail-top { flex: none; max-height: 58%; overflow: auto; padding: 18px 22px 8px; }
  .crumbs { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; margin-bottom: 8px; }
  .crumbs button {
    border: 0;
    background: transparent;
    color: var(--muted);
    padding: 0;
    font-family: var(--mono);
    font-size: 12px;
  }
  .crumbs button:hover, .crumbs button.current { color: var(--text); }
  .crumbs span { color: var(--faint); }
  .title-row { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
  .title-row h1 {
    margin: 0;
    font-family: var(--serif);
    font-size: 32px;
    font-weight: 600;
    letter-spacing: -0.03em;
  }
  .badges { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
  .pill {
    border-radius: 999px;
    padding: 3px 8px;
    font-size: 12px;
    background: #f3f2f0;
    color: var(--muted);
  }
  .pill.running { color: #9a5b16; background: #f8ead6; }
  .pill.pending { color: #9a5b16; background: #f8ead6; }
  .pill.success { color: var(--ok); background: #e8f6ec; }
  .pill.error { color: var(--err); background: #fdecec; }
  .pill.cancelled { color: var(--muted); background: #f3f2f0; }
  .signature, .path-code, .doc {
    font-family: var(--mono);
    font-size: 12px;
    color: var(--muted);
  }
  .doc { white-space: pre-wrap; max-height: 4.6em; overflow: auto; margin: 8px 0; }
  .status-row, .actions, .command {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }
  .status-row { margin-top: 12px; }
  .status-row strong { font-size: 16px; }
  .error-banner {
    margin-top: 10px;
    padding: 8px 10px;
    border-radius: 8px;
    background: rgba(240, 153, 136, 0.12);
    color: var(--err);
    white-space: pre-wrap;
  }
  .actions { margin-top: 12px; }
  .primary, .ghost, .danger {
    border-radius: 8px;
    padding: 8px 14px;
    border: 1px solid transparent;
  }
  .primary { background: #5c5c5e; color: #ffffff; font-weight: 650; }
  .primary:hover { background: #3f3f41; }
  .ghost, .danger { background: #f3f2f0; color: var(--text); }
  .ghost { border-color: transparent; }
  .ghost:hover { background: #e8e6e3; }
  .danger { border-color: var(--err); color: var(--err); }
  .command {
    margin-top: 12px;
    padding: 8px 10px;
    border-radius: 8px;
    background: var(--bg-sunken);
    border: 1px solid var(--line);
    justify-content: space-between;
  }
  .path-code { color: var(--text); overflow-wrap: anywhere; }
  .section { margin-top: 16px; }
  .map {
    margin-top: 8px;
    max-height: 240px;
    overflow: auto;
    padding-bottom: 4px;
  }
  .map-note { color: var(--faint); font-size: 12px; margin-bottom: 6px; }
  .card {
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 10px;
    background: var(--bg-raised);
  }
  .card.selected { background: #fff8ef; border-color: #f3d2a8; box-shadow: none; }
  .card-top { display: flex; align-items: center; gap: 8px; }
  .card-name {
    border: 0;
    background: transparent;
    padding: 0;
    font-weight: 700;
    text-align: left;
  }
  .card-meta { color: var(--muted); font-size: 12px; font-family: var(--mono); margin-top: 2px; }
  .card-kids {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 10px;
    margin-left: 8px;
    padding-left: 10px;
    border-left: 1px dashed var(--line-strong);
  }
  .log-wrap { flex: 1; min-height: 0; display: flex; flex-direction: column; padding: 0 22px 16px; }
  .log-bar { padding: 8px 0; }
  .log {
    flex: 1;
    min-height: 140px;
    overflow: auto;
    background: var(--bg-sunken);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 8px 0;
    box-shadow: var(--shadow);
    font-family: var(--mono);
    font-size: 12.5px;
  }
  .log-line { display: grid; grid-template-columns: 36px 72px minmax(0, 1fr); gap: 8px; padding: 2px 12px; }
  .log-line .gutter { color: var(--faint); }
  .log-line .ts { color: var(--faint); }
  .log-line .msg { white-space: pre-wrap; overflow-wrap: anywhere; }
  .log-line.stderr .msg { color: var(--err); }
  .log-line.meta .msg { color: #9a5b16; }
  .empty { color: var(--muted); padding: 18px 12px; }
  #toast {
    position: fixed;
    left: 50%;
    bottom: 18px;
    transform: translateX(-50%) translateY(12px);
    background: #ffffff;
    color: var(--text);
    border: 1px solid var(--line-strong);
    border-radius: 999px;
    padding: 8px 14px;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.15s ease, transform 0.15s ease;
  }
  #toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
  @media (max-width: 860px) {
    .shell { grid-template-columns: 1fr; grid-template-rows: minmax(200px, 36vh) minmax(0, 1fr); }
    .title-row h1 { font-size: 26px; }
    .detail-top, .log-wrap { padding-left: 14px; padding-right: 14px; }
  }
  @media (prefers-reduced-motion: reduce) {
    .dot[data-status="running"] { animation: none; }
  }
</style>
</head>
<body>
<div class="app">
  <header>
    <div class="brand">
      <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
        <rect x="2" y="3" width="8" height="6" rx="1.5" fill="currentColor"></rect>
        <rect x="14" y="3" width="8" height="6" rx="1.5" fill="currentColor" opacity="0.55"></rect>
        <rect x="8" y="15" width="8" height="6" rx="1.5" fill="currentColor"></rect>
        <path d="M6 9v3h12V9M12 12v3" stroke="currentColor" fill="none"></path>
      </svg>
      <strong>pyouter</strong>
      <em>本机</em>
    </div>
    <div class="header-meta">
      <span id="endpoint"></span>
      <span id="running" class="live">空闲</span>
    </div>
  </header>
  <div class="shell">
    <aside>
      <div class="aside-bar">
        <h2>目录</h2>
        <span>
          <button class="text-btn" id="expand-all" type="button">全部展开</button>
          <button class="text-btn" id="collapse-all" type="button">全部折叠</button>
        </span>
      </div>
      <div class="search-wrap">
        <input id="search" type="search" placeholder="搜索路由路径" aria-label="搜索路由路径">
      </div>
      <div id="counts" class="aside-foot" style="border: 0; padding-bottom: 6px;"></div>
      <div id="tree" class="tree" role="tree"></div>
      <div class="aside-foot">单击查看，双击或 ▶ 执行</div>
    </aside>
    <main>
      <div id="main"></div>
    </main>
  </div>
</div>
<div id="toast" role="status"></div>
<script>
const BOOT = /*__BOOT__*/null || {};
const STATUS_LABEL = {idle: "空闲", pending: "等待", running: "运行中", success: "成功", error: "失败", cancelled: "已取消"};
const KIND_LABEL = {router: "路由", function: "函数", object: "对象"};
const state = {tree: null, nodes: {}, selected: "", seq: 0, filter: "", expanded: new Set(), script: BOOT.script || "pyouter"};

function h(tag, props, kids) {
  const node = document.createElement(tag);
  Object.entries(props || {}).forEach(([key, value]) => {
    if (value == null || value === false) return;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2).toLowerCase(), value);
    else node.setAttribute(key, value === true ? "" : String(value));
  });
  (kids || []).forEach((kid) => {
    if (kid == null || kid === false) return;
    node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  });
  return node;
}
function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function overlaps(left, right) {
  if (left === right) return true;
  if (left === "" || right === "") return true;
  return left.startsWith(right + ".") || right.startsWith(left + ".");
}
function nodeState(path) {
  return state.nodes[path] || {status: "idle", logs: [], error: null, started_at: null, finished_at: null, owner: null};
}
function findNode(node, path) {
  if (!node) return null;
  if (node.path === path) return node;
  for (const child of node.children || []) {
    const found = findNode(child, path);
    if (found) return found;
  }
  return null;
}
function textMatch(node, filter) {
  const blob = ((node.path || "") + " " + (node.name || "") + " " + (node.target || "")).toLowerCase();
  return blob.includes(filter);
}
function subtreeVisible(node, filter) {
  if (!filter || textMatch(node, filter)) return true;
  return (node.children || []).some((child) => subtreeVisible(child, filter));
}
function expandAll(node) {
  if (!node) return;
  if ((node.children || []).length) state.expanded.add(node.path);
  (node.children || []).forEach(expandAll);
}
function formatTime(ts) {
  if (!ts) return "";
  const date = new Date(ts * 1000);
  const pad = (value) => String(value).padStart(2, "0");
  return pad(date.getHours()) + ":" + pad(date.getMinutes()) + ":" + pad(date.getSeconds());
}
function formatDuration(start, end) {
  if (!start) return "—";
  const ms = ((end || Date.now() / 1000) - start) * 1000;
  if (ms < 1000) return Math.max(0, Math.round(ms)) + " ms";
  if (ms < 60000) return (ms / 1000).toFixed(2) + " s";
  const seconds = Math.floor(ms / 1000);
  return Math.floor(seconds / 60) + " m " + (seconds % 60) + " s";
}
function shellQuote(value) {
  if (/^[A-Za-z0-9._+/-]+$/.test(value)) return value;
  return '"' + value + '"';
}
function commandFor(path) {
  const script = shellQuote(state.script || "app.py");
  if (!path) return "python " + script + " --web";
  return "python " + script + " " + shellQuote(path);
}
function gutter(stream) {
  if (stream === "stderr") return "err";
  if (stream === "meta") return "·";
  return "out";
}
let toastTimer = 0;
function toast(message) {
  const node = document.getElementById("toast");
  node.textContent = message;
  node.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.classList.remove("show"), 2400);
}
function copyText(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => toast("已复制命令")).catch(() => toast(text));
    return;
  }
  toast(text);
}
async function run(path) {
  let response;
  try {
    response = await fetch("/api/run", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({path: path}),
    });
  } catch (error) {
    toast("无法连接本机服务");
    return;
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok) toast(data.error || "执行失败");
}
async function stop(path) {
  let response;
  try {
    response = await fetch("/api/stop", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({path: path}),
    });
  } catch (error) {
    toast("无法连接本机服务");
    return;
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok) toast(data.error || "无法停止");
}
function activeOwner(path) {
  for (const [key, node] of Object.entries(state.nodes)) {
    if (node.status !== "running" && node.status !== "pending") continue;
    if (!overlaps(key, path)) continue;
    return node.owner != null ? node.owner : key;
  }
  return null;
}
function childStats(path) {
  const stats = {running: 0, pending: 0, success: 0, error: 0, cancelled: 0};
  for (const [key, node] of Object.entries(state.nodes)) {
    if (key === path) continue;
    if (path !== "" && !key.startsWith(path + ".")) continue;
    if (stats[node.status] != null) stats[node.status] += 1;
  }
  return stats;
}
function renderTreeNode(node, depth, filter) {
  const children = node.children || [];
  const showAll = !filter || textMatch(node, filter);
  const kids = showAll ? children : children.filter((child) => subtreeVisible(child, filter));
  if (filter && !showAll && !kids.length) return [];
  const open = filter ? true : state.expanded.has(node.path);
  const status = nodeState(node.path).status;
  const row = h("div", {
    class: "tree-row" + (state.selected === node.path ? " selected" : ""),
    role: "treeitem",
    "data-path": node.path,
    "aria-selected": state.selected === node.path ? "true" : "false",
    title: (node.path || "(root)") + " · 单击查看，双击执行",
    onclick: () => select(node.path),
    ondblclick: (event) => {
      if (event.target.closest && event.target.closest("button")) return;
      event.preventDefault();
      select(node.path);
      run(node.path);
    },
  }, [
    h("button", {
      class: "twist" + (children.length ? "" : " spacer"),
      type: "button",
      title: open ? "折叠" : "展开",
      onclick: (event) => {
        event.stopPropagation();
        if (!children.length) return;
        if (state.expanded.has(node.path)) state.expanded.delete(node.path);
        else state.expanded.add(node.path);
        renderTree();
      },
      text: children.length ? (open ? "▾" : "▸") : "",
    }),
    h("span", {class: "dot", "data-status": status}),
    h("span", {class: "tree-name", text: node.name || "(root)"}),
    h("span", {class: "tree-kind", text: KIND_LABEL[node.kind] || node.kind || ""}),
    h("button", {
      class: "run-mini",
      type: "button",
      title: "执行 " + (node.path || "(root)"),
      "aria-label": "执行 " + (node.path || "(root)"),
      onclick: (event) => {
        event.stopPropagation();
        select(node.path);
        run(node.path);
      },
      text: "▶",
    }),
  ]);
  row.style.paddingLeft = (8 + depth * 14) + "px";
  const rows = [row];
  if (open) kids.forEach((child) => rows.push(...renderTreeNode(child, depth + 1, filter)));
  return rows;
}
function renderTree() {
  const host = document.getElementById("tree");
  clear(host);
  if (!state.tree) return;
  const filter = state.filter.trim().toLowerCase();
  const rows = renderTreeNode(state.tree, 0, filter);
  if (!rows.length) {
    host.append(h("div", {class: "empty", text: "没有匹配的路由"}));
    return;
  }
  const frag = document.createDocumentFragment();
  rows.forEach((row) => frag.append(row));
  host.append(frag);
}
function updateDots() {
  document.querySelectorAll(".tree-row").forEach((row) => {
    const dot = row.querySelector(".dot");
    if (dot) dot.dataset.status = nodeState(row.getAttribute("data-path")).status;
  });
}
function updateCounts() {
  let routers = 0;
  let actions = 0;
  const visit = (node) => {
    if (!node) return;
    if (node.type === "router") routers += 1;
    else actions += 1;
    (node.children || []).forEach(visit);
  };
  visit(state.tree);
  document.getElementById("counts").textContent = "路由 " + Math.max(routers - 1, 0) + " · 动作 " + actions;
}
function updateChrome() {
  const active = Object.values(state.nodes).filter((node) => node.status === "running" || node.status === "pending").length;
  const running = document.getElementById("running");
  running.textContent = active ? active + " 个节点执行中" : "空闲";
  running.dataset.on = active ? "1" : "0";
  document.getElementById("endpoint").textContent = location.host;
}
function select(path) {
  state.selected = path || "";
  document.querySelectorAll(".tree-row").forEach((row) => {
    const on = row.getAttribute("data-path") === state.selected;
    row.classList.toggle("selected", on);
    row.setAttribute("aria-selected", on ? "true" : "false");
  });
  const current = document.querySelector('.tree-row[data-path="' + (window.CSS && CSS.escape ? CSS.escape(state.selected) : state.selected) + '"]');
  if (current) current.scrollIntoView({block: "nearest"});
  renderMain(true);
}
function renderCard(node, depth) {
  const info = nodeState(node.path);
  const card = h("div", {class: "card" + (node.path === state.selected ? " selected" : "")}, [
    h("div", {class: "card-top"}, [
      h("button", {class: "card-name", type: "button", onclick: () => select(node.path), text: node.name || "(root)"}),
      h("span", {class: "pill " + (info.status || "idle"), text: STATUS_LABEL[info.status] || info.status}),
      h("button", {
        class: "run-mini",
        type: "button",
        title: "执行",
        "aria-label": "执行 " + (node.path || "(root)"),
        onclick: () => { select(node.path); run(node.path); },
        text: "▶",
      }),
    ]),
    h("div", {class: "card-meta", text: (KIND_LABEL[node.kind] || "") + (node.target ? " · " + node.target : "")}),
  ]);
  const children = node.children || [];
  if (children.length && depth < 2) {
    const wrap = h("div", {class: "card-kids"});
    children.forEach((child) => wrap.append(renderCard(child, depth + 1)));
    card.append(wrap);
  } else if (children.length) {
    card.append(h("div", {class: "map-note", text: "还有 " + children.length + " 个子节点，可在左侧目录继续查看"}));
  }
  return card;
}
function renderMain(fromSelect) {
  const host = document.getElementById("main");
  const prev = host.querySelector("[data-log]");
  let atBottom = true;
  let scrollTop = 0;
  if (prev && !fromSelect) {
    atBottom = prev.scrollHeight - prev.scrollTop - prev.clientHeight < 40;
    scrollTop = prev.scrollTop;
  }
  clear(host);
  if (!state.tree) {
    host.append(h("div", {class: "empty", text: "正在加载路由…"}));
    return;
  }
  const node = findNode(state.tree, state.selected || "");
  if (!node) {
    host.append(h("div", {class: "empty", text: "未找到这个节点"}));
    return;
  }
  const info = nodeState(node.path);
  const status = info.status || "idle";
  const crumbs = h("div", {class: "crumbs"});
  const parts = node.path ? node.path.split(".") : [];
  const crumbNodes = [state.tree];
  let currentPath = "";
  parts.forEach((part) => {
    currentPath = currentPath ? currentPath + "." + part : part;
    const found = findNode(state.tree, currentPath);
    if (found) crumbNodes.push(found);
  });
  crumbNodes.forEach((crumb, index) => {
    if (index) crumbs.append(h("span", {text: "/"}));
    crumbs.append(h("button", {
      type: "button",
      class: crumb.path === node.path ? "current" : "",
      onclick: () => select(crumb.path),
      text: crumb.name || "(root)",
    }));
  });
  const owner = activeOwner(node.path);
  const actions = h("div", {class: "actions"});
  if (owner === null) {
    actions.append(h("button", {class: "primary", type: "button", onclick: () => run(node.path), text: "执行"}));
  } else {
    actions.append(h("button", {class: "danger", type: "button", onclick: () => stop(node.path), text: "停止"}));
    actions.append(h("span", {class: "signature", text: owner === node.path ? "此节点正在执行" : "相关节点正在执行：" + (owner || "(root)")}));
  }
  const command = commandFor(node.path);
  const stats = childStats(node.path);
  const statBits = [];
  if (stats.running) statBits.push("运行 " + stats.running);
  if (stats.pending) statBits.push("等待 " + stats.pending);
  if (stats.success) statBits.push("成功 " + stats.success);
  if (stats.error) statBits.push("失败 " + stats.error);
  if (stats.cancelled) statBits.push("已取消 " + stats.cancelled);
  let mapNode = node;
  let mapNote = node.type === "router" ? "当前路由及其子节点" : "";
  if (node.type !== "router") {
    const parentPath = node.path.includes(".") ? node.path.slice(0, node.path.lastIndexOf(".")) : "";
    mapNode = findNode(state.tree, parentPath) || node;
    mapNote = "叶子节点挂在上一级路由下，高亮的是当前节点";
  }
  const top = h("div", {class: "detail-top"}, [
    crumbs,
    h("div", {class: "title-row"}, [
      h("h1", {text: node.name || "(root)"}),
      h("div", {class: "badges"}, [
        h("span", {class: "pill", text: KIND_LABEL[node.kind] || node.type}),
        h("span", {class: "pill " + status, text: STATUS_LABEL[status] || status}),
      ]),
    ]),
    h("div", {class: "path-code", text: node.path || "(root)"}),
    node.signature || node.target ? h("div", {class: "signature", text: (node.target || "") + (node.signature || "")}) : null,
    node.doc ? h("div", {class: "doc", text: node.doc}) : null,
    h("div", {class: "status-row"}, [
      h("strong", {"data-duration": "1", text: formatDuration(info.started_at, status === "running" || status === "pending" ? null : info.finished_at)}),
      h("span", {class: "signature", text: statBits.length ? "子节点 " + statBits.join(" · ") : (node.type === "router" ? "还没有子节点执行记录" : "")}),
    ]),
    info.error ? h("div", {class: "error-banner", role: "alert", text: info.error}) : null,
    actions,
    h("div", {class: "command"}, [
      h("code", {class: "path-code", text: command}),
      h("button", {class: "ghost", type: "button", onclick: () => copyText(command), text: "复制命令"}),
    ]),
    h("div", {class: "section"}, [
      h("div", {class: "section-head"}, [h("h3", {text: "路由图"})]),
      mapNote ? h("div", {class: "map-note", text: mapNote}) : null,
      h("div", {class: "map"}, [renderCard(mapNode, 0)]),
    ]),
  ]);
  const logs = info.logs || [];
  const logBox = h("div", {class: "log", "data-log": "1"});
  if (!logs.length) {
    logBox.append(h("div", {class: "empty", text: "还没有日志。执行此节点后，标准输出和标准错误会显示在这里。"}));
  } else {
    logs.forEach((line) => {
      logBox.append(h("div", {class: "log-line " + (line.stream || "stdout")}, [
        h("span", {class: "gutter", text: gutter(line.stream)}),
        h("span", {class: "ts", text: formatTime(line.ts)}),
        h("span", {class: "msg", text: line.message}),
      ]));
    });
  }
  const logWrap = h("div", {class: "log-wrap"}, [
    h("div", {class: "log-bar"}, [
      h("h3", {text: "日志"}),
      h("span", {class: "signature", text: logs.length ? logs.length + " 行" : ""}),
    ]),
    logBox,
  ]);
  host.append(top, logWrap);
  if (fromSelect || atBottom) logBox.scrollTop = logBox.scrollHeight;
  else logBox.scrollTop = scrollTop;
}
function applyEvent(event) {
  const node = state.nodes[event.path] || {status: "idle", logs: [], error: null, started_at: null, finished_at: null, owner: null};
  state.nodes[event.path] = node;
  if (event.type === "reset") {
    node.logs = [];
    node.error = null;
    node.started_at = null;
    node.finished_at = null;
    node.owner = null;
  } else if (event.type === "status") {
    node.status = event.status;
    node.error = event.error;
    node.started_at = event.started_at;
    node.finished_at = event.finished_at;
    node.owner = event.owner;
  } else if (event.type === "log") {
    node.logs = node.logs || [];
    node.logs.push({ts: event.ts, stream: event.stream, message: event.message});
  }
}
async function poll() {
  try {
    const response = await fetch("/api/events?since=" + state.seq);
    const data = await response.json();
    if (data.gap) {
      const snap = await (await fetch("/api/snapshot")).json();
      state.nodes = snap.nodes || {};
      state.seq = snap.seq || 0;
      updateDots();
      renderMain(false);
    } else if (data.events && data.events.length) {
      state.seq = data.seq;
      let dirty = false;
      data.events.forEach((event) => {
        applyEvent(event);
        if (overlaps(event.path || "", state.selected || "")) dirty = true;
      });
      updateDots();
      if (dirty) renderMain(false);
    } else {
      state.seq = data.seq;
    }
    updateChrome();
  } catch (error) {
    /* keep polling; the server may be restarting */
  }
  setTimeout(poll, 400);
}
async function boot() {
  const snap = await (await fetch("/api/snapshot")).json();
  state.tree = snap.tree;
  state.nodes = snap.nodes || {};
  state.seq = snap.seq || 0;
  state.script = snap.script || state.script;
  expandAll(state.tree);
  updateCounts();
  renderTree();
  const focus = BOOT.focus || snap.focus || "";
  if (focus && !findNode(state.tree, focus)) {
    toast("未找到路径 " + focus);
    select("");
  } else {
    select(focus);
  }
  updateChrome();
  poll();
}
document.getElementById("search").addEventListener("input", (event) => {
  state.filter = event.target.value;
  renderTree();
});
document.getElementById("expand-all").addEventListener("click", () => {
  expandAll(state.tree);
  renderTree();
});
document.getElementById("collapse-all").addEventListener("click", () => {
  state.expanded = new Set();
  renderTree();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "/" && document.activeElement && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") {
    event.preventDefault();
    document.getElementById("search").focus();
  }
});
setInterval(() => {
  const info = nodeState(state.selected);
  if (info.status !== "running" && info.status !== "pending") return;
  const el = document.querySelector("[data-duration]");
  if (el) el.textContent = formatDuration(info.started_at, null);
}, 500);
document.getElementById("endpoint").textContent = location.host;
document.getElementById("main").append(h("div", {class: "empty", text: "正在加载路由…"}));
boot().catch(() => toast("无法加载路由"));
</script>
</body>
</html>
"""


def render_page(boot):
    payload = json.dumps(boot or {}, ensure_ascii=False).replace("<", "\\u003c")
    return PAGE.replace("/*__BOOT__*/null", payload)
