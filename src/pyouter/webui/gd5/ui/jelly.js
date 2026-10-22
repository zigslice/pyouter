/**
 * Global jelly switch, peer to the theme.
 *
 *   setJelly(true)   // <html data-gd-jelly="on">, remembered as gd5-jelly
 *   setJelly(false)
 *   getJelly()
 *
 * Hosts are marked data-gd-jelly-host="solid" (primary/default buttons,
 * chips, FABs). A canvas membrane attaches only when the nearest
 * [data-gd-jelly] ancestor is "on" and motion is allowed.
 */

import { Switch } from './control.js';
import { DEFAULT_CONFIG, JellyBody, traceSmoothPath } from './jelly-body.js';
import { el } from './util.js';

export const JELLY_ATTR = 'data-gd-jelly';
export const JELLY_HOST_ATTR = 'data-gd-jelly-host';
export const JELLY_KEY = 'gd5-jelly';

const LIVE_CLASS = 'gd-jelly-live';
const PIXEL_KEYS = [
  'insideHeldBulgeAmount',
  'insideHeldHaloAmount',
  'insideHeldDepthAmount',
  'outsideHeldDentAmount',
  'outsideHeldSideBulgeAmount',
  'outsideHeldDepthAmount',
  'axisDepth',
  'maxDepthIn',
  'maxDepthOut',
  'maxDent',
  'maxBulge',
  'insideLocalBulgeImpulse',
  'insideLocalHoldBulgeForce',
  'depthImpulse',
  'depthBulgeImpulse',
  'outsideDentImpulse',
  'outsideSideBulgeImpulse',
  'outsideOppositeBulgeImpulse',
  'outsideHoldForce',
  'outsideHoldDepthForce',
];

/** @type {boolean} */
let current = false;
/** @type {boolean} */
let observing = false;
/** @type {MutationObserver|null} */
let observer = null;
/** @type {boolean} */
let scanQueued = false;
/** @type {Map<Element, object>} */
const hosts = new Map();
/** @type {Set<object>} */
const active = new Set();
/** @type {number} */
let rafId = 0;
/** @type {number} */
let lastTime = 0;

/**
 * Scale pixel-valued jelly defaults. Index-unit values stay put.
 * Defaults are tuned for a ~62px control; gd5 controls are smaller.
 * @param {number} minSide
 */
export function scaleJellyConfig(minSide) {
  const k = Math.max(0.42, Math.min(1, minSide / 62));
  /** @type {Record<string, number>} */
  const config = {};
  for (const key of PIXEL_KEYS) config[key] = DEFAULT_CONFIG[key] * k;
  config.samples = DEFAULT_CONFIG.samples;
  return { k, config };
}

/**
 * @param {HTMLElement|Document|null|undefined} target
 * @returns {HTMLElement|null}
 */
function resolveEl(target) {
  if (target && target.nodeType === 9) return /** @type {Document} */ (target).documentElement;
  if (target && target.nodeType === 1) return /** @type {HTMLElement} */ (target);
  if (typeof document === 'undefined') return null;
  return document.documentElement || null;
}

/**
 * @param {HTMLElement|Document} [target]
 * @returns {boolean}
 */
export function getJelly(target) {
  const el = resolveEl(target);
  const fromDom = el?.getAttribute?.(JELLY_ATTR);
  if (fromDom === 'on') return true;
  if (fromDom === 'off') return false;
  return current;
}

/**
 * @param {boolean} on
 * @param {HTMLElement|Document} [target]  omit to set <html> and persist
 * @returns {boolean}
 */
export function setJelly(on, target) {
  const enabled = !!on;
  const el = resolveEl(target);
  if (el?.setAttribute) el.setAttribute(JELLY_ATTR, enabled ? 'on' : 'off');
  const root = typeof document !== 'undefined' ? document.documentElement : null;
  if (!target || el === root) {
    current = enabled;
    try {
      localStorage.setItem(JELLY_KEY, enabled ? 'on' : 'off');
    } catch {
      /* private mode */
    }
  }
  ensureJelly();
  refresh();
  return enabled;
}

/**
 * The same switch the catalog uses. Checked state follows getJelly() at click time,
 * so a product toolbar can keep the node without rebuilding the page.
 * @param {object} [props]
 * @param {string} [props.label]
 * @param {(on: boolean) => void} [props.onChange]
 */
export function JellySwitch(props = {}) {
  const label = props.label == null ? '果冻' : props.label;
  return el(
    'span',
    { className: 'gd-jelly-switch' },
    label
      ? el('span', { className: 'gd-jelly-switch__label', text: label })
      : null,
    Switch({
      checked: getJelly(),
      attrs: { 'aria-label': '果冻效果' },
      onChange: (_next, event) => {
        const next = !getJelly();
        setJelly(next);
        const button = event?.currentTarget;
        if (button?.classList) {
          button.classList.toggle('gd-switch--checked', next);
          button.setAttribute?.('aria-checked', next ? 'true' : 'false');
        }
        props.onChange?.(next);
      },
    })
  );
}

/** Restore the document switch from localStorage. No-op when unset. */
export function applyRememberedJelly() {
  let saved = null;
  try {
    saved = localStorage.getItem(JELLY_KEY);
  } catch {
    return;
  }
  if (saved == null) return;
  const on = saved === 'on' || saved === 'true' || saved === '1';
  const off = saved === 'off' || saved === 'false' || saved === '0';
  if (!on && !off) return;
  const root = typeof document !== 'undefined' ? document.documentElement : null;
  if (root?.setAttribute) root.setAttribute(JELLY_ATTR, on ? 'on' : 'off');
  current = on;
  ensureJelly();
  refresh();
}

/** Watch the document for hosts and for the switch attribute. Safe to call twice. */
export function ensureJelly() {
  if (observing) return;
  if (typeof document === 'undefined' || typeof MutationObserver === 'undefined') return;
  const root = document.documentElement;
  if (!root) return;
  observing = true;
  observer = new MutationObserver(() => scheduleScan());
  observer.observe(root, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: [JELLY_ATTR, JELLY_HOST_ATTR, 'data-gd-theme', 'data-gd-jelly-motion'],
  });
  scheduleScan();
}

function scheduleScan() {
  if (scanQueued) return;
  scanQueued = true;
  const run = () => {
    scanQueued = false;
    refresh();
  };
  if (typeof queueMicrotask === 'function') queueMicrotask(run);
  else setTimeout(run, 0);
}

function motionReduced() {
  const root = typeof document !== 'undefined' ? document.documentElement : null;
  if (root?.getAttribute?.('data-gd-jelly-motion') === 'reduce') return true;
  try {
    return globalThis.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches === true;
  } catch {
    return false;
  }
}

/**
 * Nearest ancestor wins, so a ConfigProvider can turn a subtree off.
 * @param {Element} node
 */
function jellyOnFor(node) {
  const scope = node.closest?.(`[${JELLY_ATTR}]`);
  if (!scope) return false;
  return scope.getAttribute(JELLY_ATTR) === 'on';
}

function wantsLive(node) {
  if (!jellyOnFor(node) || motionReduced()) return false;
  if (node.closest?.('.gd-split-btn')) return false;
  return true;
}

const PRODUCT_BUTTONS = '.btn--primary, .btn--secondary, .btn--ghost, .btn--danger';

function adoptPressableButtons() {
  if (typeof document === 'undefined' || typeof document.querySelectorAll !== 'function') return;
  for (const node of document.querySelectorAll(PRODUCT_BUTTONS)) {
    if (node.getAttribute(JELLY_HOST_ATTR) === 'solid') continue;
    if (node.closest?.('.gd-split-btn')) continue;
    node.setAttribute(JELLY_HOST_ATTR, 'solid');
  }
}

function refresh() {
  if (typeof document === 'undefined' || typeof document.querySelectorAll !== 'function') return;
  adoptPressableButtons();
  const nodes = document.querySelectorAll(`[${JELLY_HOST_ATTR}="solid"]`);
  const seen = new Set();
  for (const node of nodes) {
    seen.add(node);
    if (wantsLive(node)) attach(node);
    else detach(node);
  }
  for (const node of [...hosts.keys()]) {
    if (!seen.has(node) || node.isConnected === false) detach(node);
  }
}

/**
 * @param {Element} host
 */
function attach(host) {
  const existing = hosts.get(host);
  if (existing) {
    if (existing.canvas.isConnected) {
      host.classList.add(LIVE_CLASS);
      poke(existing, 48);
      return;
    }
    detach(host);
  }
  const canvas = document.createElement('canvas');
  canvas.className = 'gd-jelly-canvas';
  canvas.setAttribute('aria-hidden', 'true');
  host.prepend(canvas);
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    canvas.remove();
    return;
  }
  /** @type {object} */
  const rec = {
    host,
    canvas,
    ctx,
    body: null,
    w: 0,
    h: 0,
    pad: 0,
    dpr: 1,
    awakeUntil: 0,
    positioned: false,
    listeners: [],
    observer: null,
  };
  const pos = getComputedStyle(host).position;
  if (pos === 'static') {
    host.style.position = 'relative';
    rec.positioned = true;
  }
  host.classList.add(LIVE_CLASS);
  bindInput(rec);
  hosts.set(host, rec);
  if (typeof ResizeObserver !== 'undefined') {
    rec.observer = new ResizeObserver(() => {
      syncSize(rec);
      poke(rec, 48);
    });
    rec.observer.observe(host);
  }
  syncSize(rec);
  poke(rec, 48);
}

/**
 * @param {Element} host
 */
function detach(host) {
  const rec = hosts.get(host);
  if (!rec) return;
  hosts.delete(host);
  active.delete(rec);
  host.classList.remove(LIVE_CLASS);
  if (rec.positioned) host.style.position = '';
  rec.observer?.disconnect();
  for (const [type, fn] of rec.listeners) host.removeEventListener(type, fn);
  rec.canvas?.remove();
}

/**
 * @param {object} rec
 */
function bindInput(rec) {
  const { host } = rec;
  const listen = (type, fn) => {
    host.addEventListener(type, fn);
    rec.listeners.push([type, fn]);
  };
  listen('pointerdown', (event) => {
    if (event.button != null && event.button !== 0) return;
    if (host.disabled || motionReduced() || !rec.body) return;
    try {
      host.setPointerCapture?.(event.pointerId);
    } catch {
      /* already released */
    }
    const point = localFromEvent(rec, event);
    rec.body.pressAtLocal(point.x, point.y);
    poke(rec, 800);
  });
  listen('pointermove', (event) => {
    if (!rec.body?.state.pointerActive) return;
    const point = localFromEvent(rec, event);
    rec.body.moveToLocal(point.x, point.y);
    poke(rec, 800);
  });
  const release = () => {
    if (!rec.body?.state.pointerActive) return;
    rec.body.release();
    poke(rec, 700);
  };
  listen('pointerup', release);
  listen('pointercancel', release);
  listen('lostpointercapture', release);
  listen('pointerenter', () => poke(rec, 220));
  listen('pointerleave', () => {
    if (rec.body?.state.pointerActive) rec.body.release();
    poke(rec, 220);
  });
  if (host.tagName === 'BUTTON') {
    listen('keydown', (event) => {
      if (event.repeat) return;
      if (event.key !== 'Enter' && event.key !== ' ') return;
      if (host.disabled || motionReduced() || !rec.body) return;
      rec.body.centerPulse(1);
      poke(rec, 700);
    });
    listen('keyup', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      if (!rec.body) return;
      rec.body.release();
      poke(rec, 700);
    });
    listen('blur', () => {
      if (!rec.body?.state.pointerActive && rec.body) rec.body.release();
      poke(rec, 400);
    });
  }
}

/**
 * @param {object} rec
 * @param {PointerEvent} event
 */
function localFromEvent(rec, event) {
  const rect = rec.host.getBoundingClientRect();
  const width = rect.width || rec.body.width;
  const height = rect.height || rec.body.height;
  const x = ((event.clientX - rect.left) / width) * rec.body.width - rec.body.width / 2;
  const y = ((event.clientY - rect.top) / height) * rec.body.height - rec.body.height / 2;
  return { x, y };
}

/**
 * @param {object} rec
 */
function syncSize(rec) {
  const w = rec.host.offsetWidth;
  const h = rec.host.offsetHeight;
  if (w < 2 || h < 2) return;
  const dpr = Math.min(globalThis.devicePixelRatio || 1, 3);
  if (rec.body && w === rec.w && h === rec.h && dpr === rec.dpr) return;
  rec.w = w;
  rec.h = h;
  rec.dpr = dpr;
  const minSide = Math.min(w, h);
  const { k, config } = scaleJellyConfig(minSide);
  const pad = Math.ceil(48 * k);
  rec.pad = pad;
  rec.canvas.width = Math.ceil((w + pad * 2) * dpr);
  rec.canvas.height = Math.ceil((h + pad * 2) * dpr);
  rec.canvas.style.width = `${w + pad * 2}px`;
  rec.canvas.style.height = `${h + pad * 2}px`;
  const radius = minSide / 2;
  if (!rec.body) rec.body = new JellyBody({ width: w, height: h, radius, config });
  else {
    Object.assign(rec.body.config, config);
    rec.body.resize(w, h, radius);
  }
}

/**
 * @param {Element} host
 * @param {string} name
 */
function readToken(host, name) {
  const raw = getComputedStyle(host).getPropertyValue(name).trim();
  if (!raw || raw.startsWith('var(')) return '';
  return raw;
}

/**
 * @param {Element} host
 */
function readFill(host) {
  const raw = readToken(host, '--gd-jelly-fill');
  if (raw === 'transparent' || raw === 'rgba(0, 0, 0, 0)') return 'rgba(0, 0, 0, 0)';
  if (raw) return raw;
  let probe = host.querySelector?.(':scope > .gd-jelly-probe');
  if (!probe) {
    probe = document.createElement('span');
    probe.className = 'gd-jelly-probe';
    probe.setAttribute('aria-hidden', 'true');
    host.appendChild(probe);
  }
  const color = getComputedStyle(probe).backgroundColor;
  if (!color || color === 'transparent' || color === 'rgba(0, 0, 0, 0)') return '#e86a17';
  return color;
}

/**
 * @param {object} rec
 */
function paint(rec) {
  if (!rec.body) return;
  const { ctx, canvas, body, pad, dpr } = rec;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, canvas.width / dpr, canvas.height / dpr);
  ctx.save();
  ctx.translate(pad + body.width / 2, pad + body.height / 2);
  ctx.rotate(body.state.rotateZ);
  const points = body.getSurfacePoints().map((point) => body.projectPoint(point));
  traceSmoothPath(ctx, points, body.config.curveTension);
  ctx.fillStyle = readFill(rec.host);
  ctx.fill();
  const edge = readToken(rec.host, '--gd-jelly-edge');
  if (edge && edge !== 'transparent' && edge !== 'rgba(0, 0, 0, 0)') {
    ctx.strokeStyle = edge;
    ctx.lineWidth = 1;
    ctx.stroke();
  }
  ctx.restore();
}

/**
 * @param {object} rec
 * @param {number} ms
 */
function poke(rec, ms) {
  rec.awakeUntil = now() + ms;
  active.add(rec);
  if (!rafId) {
    lastTime = now();
    rafId = raf(loop);
  }
}

function now() {
  return globalThis.performance?.now?.() ?? Date.now();
}

function raf(fn) {
  if (typeof globalThis.requestAnimationFrame === 'function') return globalThis.requestAnimationFrame(fn);
  return 0;
}

function loop(t) {
  rafId = 0;
  const dt = Math.min(0.033, Math.max(0, (t - lastTime) / 1000));
  lastTime = t;
  for (const rec of [...active]) {
    if (rec.host.isConnected === false) {
      detach(rec.host);
      continue;
    }
    syncSize(rec);
    if (rec.body) {
      rec.body.update(dt);
      paint(rec);
    }
    const held = !!rec.body?.state.pointerActive;
    if (!held && rec.body?.isResting() && t >= rec.awakeUntil) active.delete(rec);
  }
  if (active.size) rafId = raf(loop);
}
