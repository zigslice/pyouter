import { KIND_LABEL, LAYER_LABEL, STATUS_LABEL, UI_LABEL } from "./labels.js";

const BOOT =
  typeof window !== "undefined" && window.__PYOUTER_BOOT__
    ? window.__PYOUTER_BOOT__
    : {};

export const state = {
  tree: null,
  nodes: {},
  selected: "",
  seq: 0,
  filter: "",
  expanded: new Set(),
  script: BOOT.script || "pyouter",
  mode: BOOT.mode || "app",
  here: "",
  focus: BOOT.focus || "",
  live: false,
};

const listeners = new Set();

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function notify() {
  for (const fn of [...listeners]) fn(state);
}

export function runtimeMode() {
  return state.mode === "runtime";
}

export function overlaps(left, right) {
  if (left === right) return true;
  if (left === "" || right === "") return true;
  return left.startsWith(right + ".") || right.startsWith(left + ".");
}

export function nodeState(path) {
  return (
    state.nodes[path] || {
      status: "idle",
      logs: [],
      error: null,
      started_at: null,
      finished_at: null,
      owner: null,
    }
  );
}

export function findNode(node, path) {
  if (!node) return null;
  if (node.path === path) return node;
  for (const child of node.children || []) {
    const found = findNode(child, path);
    if (found) return found;
  }
  return null;
}

export function layerKind(node) {
  if (!node) return "";
  if (node.layer && LAYER_LABEL[node.layer]) return node.layer;
  return "";
}

export function httpLabel(node) {
  if (!node || node.kind !== "web" || !node.rule) return "";
  return ((node.method || "") + " " + node.rule).trim();
}

export function kindText(node) {
  if (!node) return "";
  const layer = layerKind(node);
  if (layer) return LAYER_LABEL[layer];
  const http = httpLabel(node);
  if (http) return http;
  if (node.route_type === "web" && node.kind === "router") return "服务";
  if (node.route_type === "docker" && node.kind === "router") return "容器";
  if (node.route_type === "compose" && node.kind === "router") return "编排";
  if (node.route_type === "ssh" && node.kind === "router") return "主机";
  if (node.route_type === "cluster" && node.kind === "router") return "集群";
  return KIND_LABEL[node.kind] || node.kind || "";
}

export function kindName(node) {
  if (!node) return "";
  const layer = layerKind(node);
  if (layer) return LAYER_LABEL[layer];
  if (node.kind === "web") return KIND_LABEL.web;
  if (node.kind === "docker") return KIND_LABEL.docker;
  if (node.kind === "ssh") return KIND_LABEL.ssh;
  if (node.route_type === "web" && node.kind === "router") return "服务";
  if (node.route_type === "docker" && node.kind === "router") return "容器";
  if (node.route_type === "compose" && node.kind === "router") return "编排";
  if (node.route_type === "ssh" && node.kind === "router") return "主机";
  if (node.route_type === "cluster" && node.kind === "router") return "集群";
  return KIND_LABEL[node.kind] || node.kind || "";
}

export function statusDot(status) {
  if (status === "running") return "processing";
  if (status === "pending") return "away";
  if (status === "success") return "success";
  if (status === "error") return "error";
  if (status === "cancelled") return "warning";
  return "offline";
}

export function tagColor(status) {
  if (status === "success") return "primary";
  if (status === "error") return "danger";
  return "default";
}

export function textMatch(node, filter) {
  const blob = (
    (node.path || "") +
    " " +
    (node.name || "") +
    " " +
    (node.target || "")
  ).toLowerCase();
  return blob.includes(filter);
}

export function subtreeVisible(node, filter) {
  if (!filter || textMatch(node, filter)) return true;
  return (node.children || []).some((child) => subtreeVisible(child, filter));
}

export function expandAll(node, into = state.expanded) {
  if (!node) return into;
  if ((node.children || []).length) into.add(node.path);
  for (const child of node.children || []) expandAll(child, into);
  return into;
}

export function collectExpanded(node, into = []) {
  if (!node) return into;
  if ((node.children || []).length && state.expanded.has(node.path)) {
    into.push(node.path || "__root__");
  }
  for (const child of node.children || []) collectExpanded(child, into);
  return into;
}

export function toTreeData(node, filter = "") {
  if (!node) return [];
  const normalized = (filter || "").trim().toLowerCase();

  const convert = (item) => {
    const children = item.children || [];
    const showAll = !normalized || textMatch(item, normalized);
    const kids = showAll
      ? children
      : children.filter((child) => subtreeVisible(child, normalized));
    if (normalized && !showAll && !kids.length) return null;
    const status = nodeState(item.path).status;
    const kind = kindText(item);
    const mark =
      status && status !== "idle"
        ? ` · ${STATUS_LABEL[status] || status}`
        : kind
          ? ` · ${kind}`
          : "";
    const key = item.path === "" ? "__root__" : item.path;
    const entry = {
      key,
      path: item.path,
      title: (item.name || "(root)") + mark,
      node: item,
    };
    if (kids.length) {
      entry.children = kids.map(convert).filter(Boolean);
    }
    return entry;
  };

  const root = convert(node);
  return root ? [root] : [];
}

export function formatTime(ts) {
  if (!ts) return "";
  const date = new Date(ts * 1000);
  const pad = (value) => String(value).padStart(2, "0");
  return (
    pad(date.getHours()) +
    ":" +
    pad(date.getMinutes()) +
    ":" +
    pad(date.getSeconds())
  );
}

export function formatDuration(start, end) {
  if (!start) return "—";
  const ms = ((end || Date.now() / 1000) - start) * 1000;
  if (ms < 1000) return Math.max(0, Math.round(ms)) + " ms";
  if (ms < 60000) return (ms / 1000).toFixed(2) + " s";
  const seconds = Math.floor(ms / 1000);
  return Math.floor(seconds / 60) + " m " + (seconds % 60) + " s";
}

export function shellQuote(value) {
  if (/^[A-Za-z0-9._+/-]+$/.test(value)) return value;
  return '"' + value + '"';
}

export function commandFor(path) {
  const script = shellQuote(state.script || "app.py");
  if (!path) return "python " + script + " --web";
  return "python " + script + " " + shellQuote(path);
}

export function activeOwner(path) {
  for (const [key, node] of Object.entries(state.nodes)) {
    if (node.status !== "running" && node.status !== "pending") continue;
    if (!overlaps(key, path)) continue;
    return node.owner != null ? node.owner : key;
  }
  return null;
}

export function childStats(path) {
  const stats = {
    running: 0,
    pending: 0,
    success: 0,
    error: 0,
    cancelled: 0,
  };
  for (const [key, node] of Object.entries(state.nodes)) {
    if (key === path) continue;
    if (path !== "" && !key.startsWith(path + ".")) continue;
    if (stats[node.status] != null) stats[node.status] += 1;
  }
  return stats;
}

export function applyEvent(event) {
  const node =
    state.nodes[event.path] || {
      status: "idle",
      logs: [],
      error: null,
      started_at: null,
      finished_at: null,
      owner: null,
    };
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
    node.logs.push({
      ts: event.ts,
      stream: event.stream,
      message: event.message,
    });
  }
}

export function applySnap(snap) {
  state.tree = snap.tree;
  state.mode = snap.mode || state.mode;
  state.here = snap.here || "";
  if (snap.script) state.script = snap.script;
  if (snap.focus != null && snap.focus !== "") state.focus = snap.focus;
}

export async function fetchSnapshot() {
  const snap = await (await fetch("/api/snapshot")).json();
  applySnap(snap);
  state.nodes = snap.nodes || {};
  state.seq = snap.seq || 0;
  state.live = true;
  notify();
  return snap;
}

export async function pollEvents() {
  try {
    const response = await fetch("/api/events?since=" + state.seq);
    const data = await response.json();
    if (data.gap) {
      await fetchSnapshot();
      return;
    }
    if (data.events && data.events.length) {
      state.seq = data.seq;
      data.events.forEach(applyEvent);
      notify();
    } else {
      state.seq = data.seq;
    }
    state.live = true;
  } catch (_error) {
    state.live = false;
    notify();
  }
}

export async function runPath(path) {
  const response = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "执行失败");
  }
  return data;
}

export async function stopPath(path) {
  const response = await fetch("/api/stop", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "无法停止");
  }
  return data;
}

export function selectPath(path) {
  state.selected = path || "";
  notify();
}

export { KIND_LABEL, LAYER_LABEL, STATUS_LABEL, UI_LABEL, BOOT };
