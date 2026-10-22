import { Component } from '../engine/index.js';
import { cx, loadUi } from './util.js';

export const DEFAULT_PELE_URL = 'https://cdn.jsdelivr.net/npm/pele@1.6.0/dist/pele.js';

export const DEFAULT_PELE_SOURCE = `flowchart LR
  Ask[Ask] --> Plan[Plan]
  Plan --> Edit[Edit]
  Edit --> Test[Test]
  Test --> Done[Done]`;

/** @type {Promise<any>|null} */
let pelePromise = null;

/**
 * Load Pele once (CDN ESM or inject `{ mount, render }`).
 * @param {string|object} [spec]
 */
export function loadPele(spec = DEFAULT_PELE_URL) {
  if (
    spec &&
    typeof spec === 'object' &&
    (typeof spec.mount === 'function' || typeof spec.render === 'function')
  ) {
    return Promise.resolve(spec);
  }
  if (!pelePromise) {
    const url = typeof spec === 'string' && spec ? spec : DEFAULT_PELE_URL;
    pelePromise = import(/* @vite-ignore */ url).then((mod) => mod.default || mod);
  }
  return pelePromise;
}

/**
 * Pele Mermaid→SVG host — same composition as TodoList / SparkView.
 */
export class PeleViewView extends Component {
  /**
   * @param {object} [deps]
   * @param {string} [deps.source] Mermaid source
   * @param {string|number} [deps.height]
   * @param {string|number} [deps.width]
   * @param {string} [deps.className]
   * @param {string|object} [deps.pele] CDN URL or `{ mount, render }`
   * @param {object} [deps.options] Pele mount/render options
   * @param {boolean} [deps.zoom]
   * @param {(ctx:{
   *   pele:any, mounted:any, result:any, host:HTMLElement, component:PeleViewView
   * })=> (void|(()=>void)|Promise<void|(()=>void)>)} [deps.onReady]
   * @param {(error:unknown)=>void} [deps.onError]
   */
  constructor(deps = {}) {
    super(deps);
    this.state.data.source = deps.source ?? DEFAULT_PELE_SOURCE;
    this.state.data.height = deps.height ?? 280;
    this.state.data.width = deps.width ?? '100%';
    this.state.data.className = deps.className || '';
    this._peleSpec = deps.pele ?? DEFAULT_PELE_URL;
    this._options = deps.options || {};
    this._zoom = deps.zoom;
    this._onReady = typeof deps.onReady === 'function' ? deps.onReady.bind(this) : null;
    this._onError = typeof deps.onError === 'function' ? deps.onError.bind(this) : null;
    this._pele = null;
    this._mountedDiagram = null;
    this._disposeUser = null;
    this._started = false;
    this._initing = false;
  }

  async mount(host, params = {}) {
    await loadUi();
    return super.mount(host, params);
  }

  getMounted() {
    return this._mountedDiagram;
  }

  getResult() {
    return this._mountedDiagram?.result;
  }

  getContext() {
    return {
      pele: this._pele,
      mounted: this._mountedDiagram,
      result: this._mountedDiagram?.result,
      host: this.ids().gdPeleHost,
      component: this,
    };
  }

  /**
   * Update Mermaid source (forwards to Pele mount().update).
   * @param {string} source
   * @param {object} [options]
   */
  setSource(source, options) {
    this.state.data.source = String(source ?? '');
    if (this._mountedDiagram?.update) {
      this._mountedDiagram.update(this.state.data.source, options);
    } else if (this._mounted) {
      this.refresh();
    }
    return this;
  }

  refreshDiagram() {
    this._mountedDiagram?.refresh?.();
    return this;
  }

  componentDidUnMount() {
    try {
      this._disposeUser?.();
    } catch {
      /* ignore */
    }
    this._disposeUser = null;
    try {
      this._mountedDiagram?.destroy?.();
    } catch {
      /* ignore */
    }
    this._mountedDiagram = null;
    this._pele = null;
    this._started = false;
  }

  async _ensureDiagram() {
    const host = this.ids().gdPeleHost;
    if (!host || this._started || this._initing) return;
    this._initing = true;
    try {
      const pele = await loadPele(this._peleSpec);
      const liveHost = this.ids().gdPeleHost;
      if (this._started || !liveHost) return;
      this._pele = pele;

      if (typeof pele.mount !== 'function') {
        throw new Error('PeleView: pele.mount missing — need pele package');
      }

      const opts = {
        ...this._options,
        onError: (err) => {
          this._onError?.(err);
          this._options.onError?.(err);
        },
      };
      if (this._zoom !== undefined) opts.zoom = this._zoom;

      liveHost.textContent = '';
      this._mountedDiagram = pele.mount(liveHost, this.state.data.source || '', opts);
      this._started = true;

      const maybeDispose = await this._onReady?.(this.getContext());
      if (typeof maybeDispose === 'function') this._disposeUser = maybeDispose;
    } catch (err) {
      this._started = false;
      const liveHost = this.ids().gdPeleHost;
      if (liveHost) {
        liveHost.textContent = '';
        const msg = document.createElement?.('div');
        if (msg) {
          msg.className = 'gd-pele__error';
          msg.textContent = `PeleView failed: ${err?.message || err}`;
          liveHost.appendChild(msg);
        }
      }
      this._onError?.(err);
      throw err;
    } finally {
      this._initing = false;
    }
  }

  render() {
    const { height, width, className } = this.state.data;
    const h = typeof height === 'number' ? `${height}px` : String(height);
    const w = typeof width === 'number' ? `${width}px` : String(width);

    this.ensureShell(
      (ids) => ids.gdPeleRoot,
      ({ div }) => {
        div(
          {
            id: 'gdPeleRoot',
            className: cx('gd-pele', className),
            style: { width: w, height: h },
          },
          div({
            id: 'gdPeleHost',
            className: 'gd-pele__host pele',
            style: { width: '100%', height: '100%', overflow: 'auto' },
          })
        );
      }
    );

    // Source change after first mount → update in place
    if (this._mountedDiagram && this._started) {
      const cur = this._mountedDiagram.source;
      if (cur !== this.state.data.source) {
        this._mountedDiagram.update?.(this.state.data.source || '');
      }
      return;
    }

    if (this._mounted || this.host()) {
      void this._ensureDiagram();
    }
  }
}

/**
 * PeleView — Mermaid diagram host (obsidianmd/pele), nested like TodoList:
 *
 * ```js
 * div(
 *   { id: 'root' },
 *   PeleView({
 *     source: 'flowchart LR\\n  A --> B',
 *     onReady({ mounted }) { … },
 *   })
 * )
 * ```
 *
 * @param {object} [props]
 * @returns {PeleViewView}
 */
export function PeleView(props = {}) {
  return new PeleViewView(props);
}

/** Alias */
export const MermaidView = PeleView;

export function createPeleView(options = {}, host) {
  const view = PeleView(options);
  const elHost =
    typeof host === 'string'
      ? typeof document !== 'undefined'
        ? document.getElementById(host)
        : null
      : host;
  if (elHost) void view.mount(elHost);
  return view;
}
