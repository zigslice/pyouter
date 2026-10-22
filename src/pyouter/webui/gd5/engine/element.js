/**
 * 创建一个 HTML Element（引擎）
 *
 * 属性约定：
 * - className：真实 CSS class，可多个
 * - id → ref.id；key → ref.key
 * - text / dataset / style / attrs
 * - onClick / onChange / …：声明式事件（→ addEventListener）
 * - events: { click: fn }：补充非标准名
 * - 其它字段：DOM 属性
 *
 * 组合（降噪）：
 * - 尾参 children：`d.div(props, child1, child2)`（仍支持 `.childList`）
 * - children 可以是 Element、文本，或 **Component**（与 Element 同有 `.dom()`，像 React 里写 `<Child />`）
 * - `bind(d)` / `D.tags()`：解构短名 + `h`
 * - `d.map(list, render, keyOf)`：列表自动带 key
 *
 * 事件写在 props 里，与 DOM 同处；壳用 ensureShell 只建一次，监听随节点生命周期。
 * window / document 等非树内目标仍用 Component.on。
 */

/** onDoubleClick → dblclick 等特例 */
const EVENT_NAME_SPECIAL = {
  doubleclick: 'dblclick',
};

/**
 * `onClick` → `click`；`onPointerDown` → `pointerdown`。
 * @param {string} prop
 * @returns {string|null}
 */
export function domEventType(prop) {
  if (typeof prop !== 'string' || prop.length < 3 || !prop.startsWith('on')) return null;
  const third = prop.charCodeAt(2);
  if (third < 65 || third > 90) return null; // 必须 on + 大写
  const raw = prop.slice(2).toLowerCase();
  return EVENT_NAME_SPECIAL[raw] || raw;
}

/**
 * 从 props 拆出事件并绑到 el，返回其余属性。
 * @param {HTMLElement} el
 * @param {Record<string, any>} props
 */
export function applyDomEvents(el, props) {
  const rest = {};
  for (const name in props) {
    const value = props[name];
    if (name === 'events' && value && typeof value === 'object') {
      for (const type in value) {
        if (typeof value[type] === 'function') {
          el.addEventListener(type, value[type]);
        }
      }
      continue;
    }
    const type = domEventType(name);
    if (type && typeof value === 'function') {
      el.addEventListener(type, value);
      continue;
    }
    rest[name] = value;
  }
  return rest;
}

function isPlainProps(value) {
  return (
    value != null &&
    typeof value === 'object' &&
    !Array.isArray(value) &&
    typeof value.dom !== 'function'
  );
}

function flattenChildren(children) {
  const out = [];
  const walk = (list) => {
    for (const item of list) {
      if (item == null || item === false) continue;
      if (Array.isArray(item)) walk(item);
      else out.push(item);
    }
  };
  walk(children);
  return out;
}

export class Element {
  constructor(ref, tag, attributes = {}) {
    this.ref = ref;

    const e = document.createElement(tag);
    const {
      text,
      className,
      id,
      key,
      dataset,
      style,
      attrs,
      events,
      ...rawProps
    } = attributes;

    const props = applyDomEvents(e, { ...rawProps, events });

    if (className != null) {
      e.className = className;
      this.ref.class[className] = e;
    }

    if (id != null) {
      e.id = id;
      if (this.ref.id[id]) {
        console.warn(`[D] duplicated id: ${id}`);
      }
      this.ref.id[id] = e;
    }

    if (key != null) {
      if (!this.ref.key) this.ref.key = {};
      if (this.ref.key[key]) {
        console.warn(`[D] duplicated key: ${key}`);
      }
      this.ref.key[key] = e;
    }

    if (text != null) {
      e.innerText = text;
    }

    if (dataset && typeof dataset === 'object') {
      Object.assign(e.dataset, dataset);
    }

    if (style != null) {
      if (typeof style === 'string') {
        e.style.cssText = style;
      } else if (typeof style === 'object') {
        Object.assign(e.style, style);
      }
    }

    if (attrs && typeof attrs === 'object') {
      for (const name in attrs) {
        if (attrs[name] != null) e.setAttribute(name, attrs[name]);
      }
    }

    for (const name in props) {
      const value = props[name];
      if (value != null) {
        e[name] = value;
      }
    }

    this.e = e;
  }

  childList(list) {
    appendKids(this, list);
    return this;
  }

  dom() {
    return this.e;
  }
}

function appendKids(element, children) {
  for (const kid of flattenChildren(children)) {
    if (typeof kid === 'string' || typeof kid === 'number') {
      element.e.appendChild(document.createTextNode(String(kid)));
    } else if (kid && typeof kid.dom === 'function') {
      element.e.appendChild(kid.dom());
    }
  }
}

const TAGS = [
  'div',
  'img',
  'b',
  's',
  'strong',
  'section',
  'li',
  'ul',
  'button',
  'input',
  'iframe',
  'header',
  'aside',
  'main',
  'h1',
  'h2',
  'p',
  'span',
  'label',
  'textarea',
];

/**
 * @example
 * const d = new D();
 * d.div({ className: 'box', id: 'home' },
 *   d.div({ className: 'title', text: 'Hi' }),
 *   d.p({ text: 'body' }),
 * );
 *
 * const { div, button, get, map, h } = bind();
 * div({ className: 'row' },
 *   ...map(items, (item, i, key) => button({ key, text: item.label }), (item) => item.id),
 * );
 */
export class D {
  constructor() {
    this.ref = { class: {}, id: {}, key: {} };
    this.root = null;
  }

  /** 解构短名：`const { div, h, map, get } = D.tags()` */
  static tags() {
    return bind(new D());
  }

  div(props, ...children) {
    return this._create('div', props, ...children);
  }

  img(props, ...children) {
    return this._create('img', props, ...children);
  }

  b(props, ...children) {
    return this._create('b', props, ...children);
  }

  s(props, ...children) {
    return this._create('s', props, ...children);
  }

  strong(props, ...children) {
    return this._create('strong', props, ...children);
  }

  section(props, ...children) {
    return this._create('section', props, ...children);
  }

  li(props, ...children) {
    return this._create('li', props, ...children);
  }

  ul(props, ...children) {
    return this._create('ul', props, ...children);
  }

  button(props, ...children) {
    return this._create('button', props, ...children);
  }

  input(props, ...children) {
    return this._create('input', props, ...children);
  }

  iframe(props, ...children) {
    return this._create('iframe', props, ...children);
  }

  header(props, ...children) {
    return this._create('header', props, ...children);
  }

  aside(props, ...children) {
    return this._create('aside', props, ...children);
  }

  main(props, ...children) {
    return this._create('main', props, ...children);
  }

  h1(props, ...children) {
    return this._create('h1', props, ...children);
  }

  h2(props, ...children) {
    return this._create('h2', props, ...children);
  }

  p(props, ...children) {
    return this._create('p', props, ...children);
  }

  span(props, ...children) {
    return this._create('span', props, ...children);
  }

  label(props, ...children) {
    return this._create('label', props, ...children);
  }

  textarea(props, ...children) {
    return this._create('textarea', props, ...children);
  }

  /** 任意标签：d.el('nav', props, ...children) */
  el(tag, props, ...children) {
    return this._create(tag, props, ...children);
  }

  /**
   * 列表渲染：自动把 keyOf(item) 传给 render，并写入 ref.key。
   * @param {Array} list
   * @param {(item, index, key) => Element} render
   * @param {(item, index) => string|number} [keyOf]
   */
  map(list, render, keyOf = (_item, index) => String(index)) {
    return (list || []).map((item, index) => {
      const key = keyOf(item, index);
      const node = render(item, index, key);
      if (node && node.e && key != null) {
        this.ref.key[key] = node.e;
      }
      return node;
    });
  }

  _create(tag, props, ...children) {
    let attrs = {};
    let kids = children;

    if (!isPlainProps(props)) {
      kids = props === undefined ? children : [props, ...children];
      attrs = {};
    } else {
      attrs = props || {};
    }

    const e = new Element(this.ref, tag, attrs);
    const flat = flattenChildren(kids);
    if (flat.length) appendKids(e, flat);

    // 尾参求值时子节点先创建，会暂时占住 root；若本节点包住了当前 root，提升为自己
    const wrapsRoot = flat.some(
      (k) => k && typeof k.dom === 'function' && (k === this.root || k.e === this.root?.e)
    );
    if (this.root == null || wrapsRoot) {
      this.root = e;
    }
    return e;
  }

  get() {
    return [this.ref, this.root.dom()];
  }

  static clear(e) {
    if (e == null) return;
    while (e.firstChild) {
      e.removeChild(e.firstChild);
    }
  }
}

/**
 * Component class?: has mount + render on prototype (avoids importing Component here).
 * @param {unknown} type
 */
function isComponentClass(type) {
  return (
    typeof type === 'function' &&
    type.prototype != null &&
    type.prototype.constructor === type &&
    typeof type.prototype.mount === 'function' &&
    typeof type.prototype.render === 'function'
  );
}

/**
 * 绑定到同一个 D 实例，便于解构短名。
 * @param {D} [d]
 */
export function bind(d = new D()) {
  const api = {
    d,
    /**
     * Hyperscript: DOM tag, UI primitive, or Component class / factory.
     * `h(TodoList, { items })` / `h(CoverFlow, { items })` — React createElement 同形。
     * @param {string|Function} type
     * @param {object} [props]
     * @param {...any} children
     */
    h(type, props, ...children) {
      if (isComponentClass(type)) {
        return new type(props || {});
      }
      if (typeof type === 'function') {
        return type(props || {}, ...children);
      }
      return d.el(type, props, ...children);
    },
    map(list, render, keyOf) {
      return d.map(list, render, keyOf);
    },
    get() {
      return d.get();
    },
    clear: D.clear,
  };

  for (const tag of TAGS) {
    api[tag] = (props, ...children) => d[tag](props, ...children);
  }

  return api;
}
