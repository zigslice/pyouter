import { D, bind } from './element.js';
import { adoptStyles, adoptStylesFor, applyStyleScope } from './styles.js';

/**
 * paint / ensureShell 建树期间的组合父组件。
 * Component.dom() 用它登记子组件，便于父 unmount 时卸掉。
 * @type {Component|null}
 */
let composeParent = null;

/**
 * 迷你实模式 HTML 组件规范（引擎）
 *
 * this.state = {
 *   data: {}, // 视图展示所依赖的数据
 *   ref: {}   // 视图 HTML Element 的索引
 * };
 *
 * 两种挂载方式（同一套生命周期）：
 * 1. 页面：ComponentRender.navigate → mount(页槽)
 * 2. 组合：像 div 一样写进 ensureShell / bind 树（Component 有 .dom()，与 Element 同形）
 *
 * 样式与组件同目录：
 *   static styles = new URL('./FooComponent.css', import.meta.url);
 * mount 时按 key 注入一次（见 adoptStyles）。
 *
 * 刷新约定（Mount 之后）：
 * - setData(patch) 合并 this.state.data，并默认调用 refresh()
 * - refresh() 默认再跑 render()；AttachEvents 只在首次 mount
 * - render 用 ensureShell 建壳，refresh 路径不要 D.clear 整棵树（否则事件丢失）
 * - ensureShell 只建一次 → 子组件只挂一次
 *
 * 易错点由引擎收掉：
 * - paint / ensureShell：不必手写 clear → bind → get → append
 * - 子组件组合：`div({ id: 'root' }, this.child)`，与 React 把 <Child /> 写进树同形
 * - DOM 事件写在 props（onClick…）；window 等用 on()，unmount 自动卸
 * - unmount 默认卸组合子组件 + 清宿主 DOM + 重置 ref（DidUnMount 只做业务清理）
 * - 样式旁挂 + mount 注入，不必在 index.html 堆全量 CSS
 * - `static styles` 默认自动 scope：CSS / className 仍写 `.toolbar`，引擎改写选择器并在 host 打 `data-gd-c`；`stylesScoped = false` 关闭
 * - navigator / logger：页面由 ComponentRender 注入；子组件由父写入 deps，用法同为 this.navigator
 *
 * API 一览：docs/api.md
 */
export class Component {
  /**
   * 可选：旁挂样式。URL | CSS 文本 | 数组。
   * @type {string|URL|Array<string|URL>|null}
   */
  static styles = null;

  /**
   * 是否对 `static styles` 自动 scope（默认 true）。
   * 作者不写前缀；注入时改写成 `[data-gd-c="Name"] …`。
   * @type {boolean}
   */
  static stylesScoped = true;

  /**
   * 覆盖 scope id（默认用 class name）。
   * @type {string|null}
   */
  static styleScope = null;

  /** @see {adoptStyles} */
  static adoptStyles = adoptStyles;

  /** @see {adoptStylesFor} */
  static adoptStylesFor = adoptStylesFor;

  /**
   * @param {object} [deps]
   * @param {object} [deps.navigator] 页栈遥控器（页面由引擎注入；子组件通常不需要）
   * @param {import('./log.js').Logger} [deps.logger]
   * @param {(self: Component) => void} [deps.onMount] mount 完成后回调（组合后初始化数据等）
   */
  constructor(deps = {}) {
    this._host = null;
    this._mounted = false;
    this._listeners = [];
    /** @type {Component[]} */
    this._slotted = [];
    this.state = { data: {}, ref: {} };
    this.navigator = deps.navigator ?? null;
    this.logger = deps.logger ?? null;
    this._onMount = typeof deps.onMount === 'function' ? deps.onMount : null;
  }

  /**
   * 当前宿主 DOM（页槽或父组件给出的 mount 点）
   * @returns {HTMLElement|null}
   */
  host() {
    return this._host;
  }

  /**
   * 是否已 mount（含页内子组件）
   */
  isMounted() {
    return this._mounted;
  }

  /**
   * `this.state.ref.id` 快捷访问（AttachEvents / sync 常用）
   * @returns {Record<string, HTMLElement>}
   */
  ids() {
    return this.state.ref?.id || {};
  }

  /**
   * `this.state.ref.key` 快捷访问
   * @returns {Record<string, HTMLElement>}
   */
  keys() {
    return this.state.ref?.key || {};
  }

  /**
   * 与 Element.dom 同形：作为 bind / el() 树的子节点时被调用。
   * 像 React 里把 `<TodoList />` 写进 `<div>…</div>` —— 直接 `div({}, this.todoList)`。
   *
   * 插入 `display: contents` 宿主，入树后自动 mount；布局由子组件自己的根节点承担。
   * @returns {HTMLElement}
   */
  dom() {
    if (typeof document === 'undefined') {
      throw new Error('Component.dom: no document');
    }
    const host = document.createElement('div');
    host.style.display = 'contents';
    host.setAttribute('data-gd-slot', this.constructor?.name || 'Component');

    const parent = composeParent;
    if (parent && !parent._slotted.includes(this)) {
      parent._slotted.push(this);
    }

    queueMicrotask(() => {
      void this.mount(host);
    });
    return host;
  }

  /**
   * 挂到宿主并走完整生命周期（页面与页内组合共用）。
   * @param {string|HTMLElement} host id 或元素
   * @param {object} [params]
   */
  async mount(host, params = {}) {
    if (this._mounted) {
      this.refresh();
      return this;
    }
    this._host = typeof host === 'string' ? document.getElementById(host) : host;
    if (!this._host) {
      throw new Error('Component.mount: host not found');
    }
    await adoptStylesFor(this.constructor);
    applyStyleScope(this._host, this.constructor);
    await this.componentDidMount(params);
    this.render();
    this.componentDidAttachEvents();
    this._mounted = true;
    this._onMount?.(this);
    return this;
  }

  /**
   * 卸载：先卸组合子组件，再业务 DidUnMount，再卸监听、清宿主、重置 ref。
   */
  unmount() {
    if (!this._mounted) return;
    this._unmountSlots();
    this.componentDidUnMount();
    this._teardown();
    this._mounted = false;
    this._host = null;
  }

  /**
   * 可选：需要包一层真实宿主（className / style / onMount）时用。
   * 普通组合请直接把子组件当 children：`div({}, this.child)`。
   *
   * @param {Component} child
   * @param {object} [hostProps]
   * @returns {import('./element.js').Element|Component}
   */
  slot(child, hostProps = {}) {
    if (!child || typeof child.mount !== 'function') {
      throw new Error('Component.slot: expected a Component');
    }
    const { onMount, ...domProps } = hostProps;
    if (typeof onMount === 'function') {
      child._onMount = onMount;
    }
    if (Object.keys(domProps).length === 0) {
      return child;
    }
    const d = new D();
    const host = d.el('div', domProps);
    const hostEl = host.dom();
    if (!this._slotted.includes(child)) {
      this._slotted.push(child);
    }
    queueMicrotask(() => {
      void child.mount(hostEl);
    });
    return host;
  }

  /**
   * 合并视图数据并刷新。
   * @param {object} patch
   * @param {{ refresh?: boolean }} [options] refresh 默认 true
   */
  setData(patch = {}, options = {}) {
    if (!this.state) {
      this.state = { data: {}, ref: {} };
    }
    if (!this.state.data || typeof this.state.data !== 'object') {
      this.state.data = {};
    }
    Object.assign(this.state.data, patch);
    if (options.refresh !== false) {
      this.refresh();
    }
    return this.state.data;
  }

  /**
   * Mount 之后的刷新入口：默认再次 render()。
   * 不重新 AttachEvents / 不走 UnMount。
   */
  refresh() {
    this.render();
  }

  /**
   * 清宿主 → bind 建树 → 写入 state.ref → append。
   * 只用于「整棵重建」；可刷新壳请用 ensureShell。
   * 建树期间子 Component 可直接作 children（走 .dom()）。
   * @param {(api: ReturnType<typeof bind>) => void} build
   * @param {HTMLElement} [host]
   */
  paint(build, host = this.host()) {
    if (!host) {
      throw new Error('Component.paint: no host');
    }
    this._unmountSlots();
    D.clear(host);
    const api = bind();
    api.slot = (child, hostProps) => this.slot(child, hostProps);
    const prev = composeParent;
    composeParent = this;
    try {
      build(api);
    } finally {
      composeParent = prev;
    }
    const [ref, root] = api.get();
    this.state.ref = ref;
    if (root) host.appendChild(root);
    return ref;
  }

  /**
   * 壳只建一次：probe(ids) 已有则跳过，否则 paint。
   * @param {(ids: Record<string, HTMLElement>) => any} probe
   * @param {(api: ReturnType<typeof bind>) => void} build
   * @returns {boolean} true = 本次新建了壳
   */
  ensureShell(probe, build) {
    if (probe(this.ids())) return false;
    this.paint(build);
    return true;
  }

  /**
   * 绑事件并登记，unmount 时自动 removeEventListener。
   * @param {EventTarget|null|undefined} target
   * @param {string} type
   * @param {EventListener} handler
   * @param {boolean|AddEventListenerOptions} [options]
   */
  on(target, type, handler, options) {
    if (!target) return this;
    target.addEventListener(type, handler, options);
    this._listeners.push({ target, type, handler, options });
    return this;
  }

  /**
   * this.ids()[id] 上绑事件（同上，自动清理）。
   * @param {string} id
   * @param {string} type
   * @param {EventListener} handler
   * @param {boolean|AddEventListenerOptions} [options]
   */
  onId(id, type, handler, options) {
    return this.on(this.ids()[id], type, handler, options);
  }

  /** @private */
  _unmountSlots() {
    const kids = this._slotted;
    this._slotted = [];
    for (const child of kids) {
      try {
        child.unmount();
      } catch {
        /* ignore */
      }
    }
  }

  /** @private */
  _teardown() {
    for (const { target, type, handler, options } of this._listeners) {
      try {
        target.removeEventListener(type, handler, options);
      } catch {
        /* ignore */
      }
    }
    this._listeners = [];
    const host = this._host;
    if (host) D.clear(host);
    this.state.ref = {};
  }

  /** virtual method — 业务挂载（取数、订阅前准备） */
  async componentDidMount() {}

  /**
   * virtual method — 业务卸载（卸订阅、停动画等）。
   * 不必再 D.clear(host) / 重置 ref：unmount 会统一做。
   */
  componentDidUnMount() {}

  /** virtual method — 首次 render 之后绑事件（用 on / onId） */
  componentDidAttachEvents() {}

  /** virtual method — 绑定 state.data → DOM；壳用 ensureShell */
  render() {}
}
