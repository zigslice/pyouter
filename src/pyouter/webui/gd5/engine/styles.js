/**
 * 组件样式注入（引擎）
 *
 * 无 bundler：用 `new URL('./X.css', import.meta.url)` 旁挂 CSS，
 * mount 时按 key 注入一次，unmount 不移除（多实例共享）。
 *
 * Component `static styles` 默认自动 scope：作者仍写 `.toolbar` /
 * `className: 'toolbar'`，引擎注入时改写成
 * `[data-gd-c="ToolbarComponent"] .toolbar`，并在 host 上打标。
 * 使用方零前缀噪音。`static stylesScoped = false` 可关闭。
 */

/** Host / CSS 上的 scope 属性名（作者不必手写） */
export const STYLE_SCOPE_ATTR = 'data-gd-c';

/** @type {Map<string, Promise<void>>} */
const adopted = new Map();

/**
 * @param {string|URL} spec
 * @returns {string}
 */
function styleKey(spec) {
  if (spec instanceof URL) return spec.href;
  if (typeof spec === 'string') {
    if (isStylesheetRef(spec)) {
      try {
        return new URL(spec, globalThis.location?.href || 'http://local/').href;
      } catch {
        return spec;
      }
    }
    return `css:${fnv1a(spec)}`;
  }
  throw new Error('adoptStyles: unsupported spec');
}

/**
 * 路径 / URL 才当 stylesheet；含 `{` 的字符串当 CSS 文本。
 * @param {string} s
 */
function isStylesheetRef(s) {
  if (typeof s !== 'string') return false;
  if (s.includes('{')) return false;
  return (
    s.endsWith('.css') ||
    s.startsWith('./') ||
    s.startsWith('../') ||
    s.startsWith('/') ||
    s.startsWith('http://') ||
    s.startsWith('https://') ||
    s.startsWith('blob:')
  );
}

/** @param {string} str */
function fnv1a(str) {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16);
}

/**
 * Scope id for a Component class (override with `static styleScope`).
 * @param {Function|{name?:string,styleScope?:string}|null|undefined} Ctor
 * @returns {string}
 */
export function styleScopeId(Ctor) {
  if (!Ctor) return 'Component';
  if (typeof Ctor.styleScope === 'string' && Ctor.styleScope.trim()) {
    return Ctor.styleScope.trim();
  }
  return Ctor.name || 'Component';
}

/**
 * @param {string} scopeId
 * @returns {string}
 */
export function styleScopeSelector(scopeId) {
  const safe = String(scopeId).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  return `[${STYLE_SCOPE_ATTR}="${safe}"]`;
}

/**
 * Stamp scope attr on a component host. No-op when scoping disabled.
 * @param {Element|{setAttribute?:Function,dataset?:DOMStringMap}|null} host
 * @param {Function} Ctor
 */
export function applyStyleScope(host, Ctor) {
  if (!host || !Ctor || Ctor.styles == null || Ctor.stylesScoped === false) return;
  const id = styleScopeId(Ctor);
  if (typeof host.setAttribute === 'function') {
    host.setAttribute(STYLE_SCOPE_ATTR, id);
  } else if (host.dataset && typeof host.dataset === 'object') {
    host.dataset.gdC = id;
  } else {
    host[STYLE_SCOPE_ATTR] = id;
  }
}

/**
 * Rewrite CSS so every rule is limited to `[data-gd-c="…"]` descendants.
 * Authors keep writing `.toolbar` — no prefix in source.
 *
 * @param {string} cssText
 * @param {string} scopeId
 * @returns {string}
 */
export function scopeCssText(cssText, scopeId) {
  const css = String(cssText ?? '');
  if (!css.trim() || !scopeId) return css;
  const scope = styleScopeSelector(scopeId);
  return transformStyleSheet(css, scope);
}

/**
 * @param {string} sel
 * @param {string} scope
 */
function prefixSelector(sel, scope) {
  const s = sel.trim();
  if (!s) return s;
  if (s === ':root' || s === 'html' || s === 'body') return s;
  if (s.startsWith(':root') || s.startsWith('html ') || s.startsWith('html:') || s.startsWith('html[')) {
    return s;
  }
  if (s.startsWith('body ') || s.startsWith('body:') || s.startsWith('body[')) return s;
  if (s.startsWith(scope)) return s;
  if (s === ':scope' || s === '&') return scope;
  if (s.startsWith(':scope') || s.startsWith('&')) {
    return scope + s.slice(s.startsWith(':scope') ? 6 : 1);
  }
  return `${scope} ${s}`;
}

/**
 * @param {string} selectorList
 * @param {string} scope
 */
function prefixSelectorList(selectorList, scope) {
  return selectorList
    .split(',')
    .map((part) => prefixSelector(part, scope))
    .join(', ');
}

/**
 * Advance past comments / strings starting at `i`.
 * @param {string} css
 * @param {number} i
 * @param {number} n
 * @returns {{ i: number, chunk: string }|null}
 */
function takeCommentOrString(css, i, n) {
  if (css[i] === '/' && css[i + 1] === '*') {
    const end = css.indexOf('*/', i + 2);
    const j = end < 0 ? n : end + 2;
    return { i: j, chunk: css.slice(i, j) };
  }
  if (css[i] === '"' || css[i] === "'") {
    const q = css[i];
    let j = i + 1;
    while (j < n) {
      if (css[j] === '\\') {
        j += 2;
        continue;
      }
      if (css[j] === q) {
        j += 1;
        break;
      }
      j += 1;
    }
    return { i: j, chunk: css.slice(i, j) };
  }
  return null;
}

/**
 * Read a `{ … }` block starting at `i` (must be `{`).
 * @param {string} css
 * @param {number} i
 * @param {number} n
 */
function takeBlock(css, i, n) {
  let depth = 0;
  let j = i;
  while (j < n) {
    const cos = takeCommentOrString(css, j, n);
    if (cos) {
      j = cos.i;
      continue;
    }
    if (css[j] === '{') depth += 1;
    else if (css[j] === '}') {
      depth -= 1;
      j += 1;
      if (depth === 0) break;
      continue;
    }
    j += 1;
  }
  return { i: j, chunk: css.slice(i, j) };
}

/**
 * Brace-aware stylesheet transform.
 * @param {string} css
 * @param {string} scope
 */
function transformStyleSheet(css, scope) {
  let out = '';
  let i = 0;
  const n = css.length;

  while (i < n) {
    const cos = takeCommentOrString(css, i, n);
    if (cos) {
      out += cos.chunk;
      i = cos.i;
      continue;
    }

    if (/\s/.test(css[i])) {
      out += css[i];
      i += 1;
      continue;
    }

    // Prelude until `{` or `;`
    let prelude = '';
    while (i < n) {
      const inner = takeCommentOrString(css, i, n);
      if (inner) {
        prelude += inner.chunk;
        i = inner.i;
        continue;
      }
      if (css[i] === '{' || css[i] === ';') break;
      prelude += css[i];
      i += 1;
    }

    if (i >= n) {
      out += prelude;
      break;
    }

    if (css[i] === ';') {
      out += prelude + ';';
      i += 1;
      continue;
    }

    const trimmed = prelude.trim();
    const block = takeBlock(css, i, n);
    i = block.i;

    if (trimmed.startsWith('@')) {
      const atName = trimmed.match(/^@([a-zA-Z-]+)/)?.[1]?.toLowerCase() || '';
      if (
        atName === 'media' ||
        atName === 'supports' ||
        atName === 'layer' ||
        atName === 'document' ||
        atName === 'container'
      ) {
        const inner = block.chunk.slice(1, -1);
        out += prelude + '{' + transformStyleSheet(inner, scope) + '}';
        continue;
      }
      // @keyframes / @font-face / @property / @page — keep global
      out += prelude + block.chunk;
      continue;
    }

    out += prefixSelectorList(prelude, scope) + block.chunk;
  }

  return out;
}

/**
 * 注入一份样式（URL / 相对路径 / CSS 文本），相同 key 只注入一次。
 * 全局、无 scope（UI kit / 手动调用）。
 * @param {string|URL} spec
 * @param {string} [key]
 * @returns {Promise<void>}
 */
export function adoptStyles(spec, key) {
  const id = key || styleKey(spec);
  if (adopted.has(id)) return adopted.get(id);

  const done = inject(spec, id);
  adopted.set(id, done);
  return done;
}

/**
 * @param {string} text
 * @param {string} id
 * @returns {Promise<void>}
 */
function injectStyleText(text, id) {
  if (typeof document === 'undefined' || !document.head) {
    return Promise.resolve();
  }
  const style = document.createElement('style');
  style.dataset.componentStyle = id;
  style.textContent = text;
  document.head.appendChild(style);
  return Promise.resolve();
}

/**
 * Fetch stylesheet text for scoping (URL / path → text).
 * @param {string|URL} spec
 * @returns {Promise<string>}
 */
async function loadCssText(spec) {
  if (typeof spec === 'string' && !isStylesheetRef(spec)) {
    return spec;
  }
  const href = spec instanceof URL ? spec.href : String(spec);
  if (typeof fetch !== 'function') {
    throw new Error(`adoptStyles: fetch unavailable for ${href}`);
  }
  const res = await fetch(href);
  if (!res.ok) {
    throw new Error(`adoptStyles: failed to load ${href} (${res.status})`);
  }
  return res.text();
}

/**
 * Adopt one Component style entry, optionally scoped.
 * @param {string|URL} spec
 * @param {string|null} scopeId
 * @returns {Promise<void>}
 */
async function adoptComponentStyle(spec, scopeId) {
  if (!scopeId) {
    return adoptStyles(spec);
  }

  const id = `scoped:${scopeId}:${styleKey(spec)}`;
  if (adopted.has(id)) return adopted.get(id);

  const done = (async () => {
    try {
      const text = await loadCssText(spec);
      await injectStyleText(scopeCssText(text, scopeId), id);
    } catch (err) {
      // Fallback: unscoped <link> so the page still paints
      console.warn('[adoptStyles] scoped load failed, falling back to link:', err);
      await inject(spec, id);
    }
  })();

  adopted.set(id, done);
  return done;
}

/**
 * 读取 Component 子类的 `static styles`（单项或数组）并注入。
 * 默认按组件名自动 scope；`static stylesScoped = false` 关闭。
 * @param {typeof import('./component.js').Component} Ctor
 */
export async function adoptStylesFor(Ctor) {
  if (!Ctor || Ctor.styles == null) return;
  const scoped = Ctor.stylesScoped !== false;
  const scopeId = scoped ? styleScopeId(Ctor) : null;
  const list = Array.isArray(Ctor.styles) ? Ctor.styles : [Ctor.styles];
  await Promise.all(list.map((item) => adoptComponentStyle(item, scopeId)));
}

/** @returns {string[]} */
export function adoptedStyleKeys() {
  return [...adopted.keys()];
}

/** 测试用：清空登记（不移除已插入的 DOM） */
export function resetAdoptedStyles() {
  adopted.clear();
}

/**
 * @param {string|URL} spec
 * @param {string} id
 */
function inject(spec, id) {
  if (typeof document === 'undefined' || !document.head) {
    return Promise.resolve();
  }

  if (spec instanceof URL || (typeof spec === 'string' && isStylesheetRef(spec))) {
    const href = spec instanceof URL ? spec.href : spec;
    return new Promise((resolve, reject) => {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = href;
      link.dataset.componentStyle = id;
      link.onload = () => resolve();
      link.onerror = () => reject(new Error(`adoptStyles: failed to load ${href}`));
      document.head.appendChild(link);
    });
  }

  if (typeof spec === 'string') {
    return injectStyleText(spec, id);
  }

  return Promise.reject(new Error('adoptStyles: unsupported spec'));
}
