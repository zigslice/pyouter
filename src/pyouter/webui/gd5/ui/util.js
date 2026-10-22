import { D, adoptStyles } from '../engine/index.js';

/** @type {Promise<void>|null} */
let stylesPromise = null;

/**
 * Load gd5 UI kit stylesheet once (co-located CSS).
 * Apps can also `<link>` `src/ui/css/ui.css` for zero FOUC.
 */
export function loadUi() {
  if (!stylesPromise) {
    stylesPromise = adoptStyles(new URL('./css/ui.css', import.meta.url)).then(async () => {
      const jelly = await import('./jelly.js');
      jelly.ensureJelly();
      jelly.applyRememberedJelly();
    });
  }
  return stylesPromise;
}

/** Kick off style load from primitives (non-blocking). */
export function ensureUiStyles() {
  void loadUi();
}

/**
 * @param {...(string|false|null|undefined|Array)} parts
 */
export function cx(...parts) {
  const out = [];
  const walk = (list) => {
    for (const part of list) {
      if (!part) continue;
      if (Array.isArray(part)) walk(part);
      else out.push(String(part));
    }
  };
  walk(parts);
  return out.join(' ').replace(/\s+/g, ' ').trim();
}

/**
 * Create a real-DOM node via a fresh D (safe as child of another tree).
 * @param {string} tag
 * @param {object} [props]
 * @param {...any} children
 */
export function el(tag, props, ...children) {
  ensureUiStyles();
  const d = new D();
  return d.el(tag, props || {}, ...children);
}

/**
 * Strip UI-specific props before forwarding to DOM.
 * @param {object} props
 * @param {string[]} keys
 */
export function omit(props, keys) {
  const skip = new Set(keys);
  const out = {};
  for (const k in props) {
    if (!skip.has(k)) out[k] = props[k];
  }
  return out;
}
