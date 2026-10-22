import { Component } from '../engine/index.js';
import { loadUi } from './util.js';

/**
 * Notification — top-right notice stack (antd Notification).
 * Distinct from Toast (bottom snackbar).
 *
 *   const n = new Notification({});
 *   await n.mount();
 *   n.open({ message: 'Title', description: '…', type: 'info' });
 */
export class Notification extends Component {
  constructor(deps = {}) {
    super(deps);
    this.state.data.items = [];
    this._portal = null;
    this._seq = 0;
  }

  async mount(host = typeof document !== 'undefined' ? document.body : null, params = {}) {
    const target =
      typeof host === 'string' ? document.getElementById(host) : host || document.body;
    if (!target) throw new Error('Notification.mount: host not found');
    if (!this._portal) {
      this._portal = document.createElement('div');
      this._portal.className = 'gd-notification-portal';
      target.appendChild(this._portal);
    }
    return super.mount(this._portal, params);
  }

  componentDidUnMount() {
    if (this._portal?.parentNode) this._portal.parentNode.removeChild(this._portal);
    this._portal = null;
  }

  async componentDidMount() {
    await loadUi();
  }

  /**
   * @param {object} options
   * @param {string} options.message
   * @param {string} [options.description]
   * @param {'info'|'success'|'warning'|'error'} [options.type]
   * @param {number} [options.duration]
   */
  open(options = {}) {
    const id = ++this._seq;
    const item = {
      id,
      message: options.message || '',
      description: options.description || '',
      type: options.type || 'info',
    };
    this.setData({ items: [...this.state.data.items, item] });
    const duration = options.duration ?? 4500;
    if (duration > 0) setTimeout(() => this.close(id), duration);
    return id;
  }

  close(id) {
    this.setData({ items: this.state.data.items.filter((it) => it.id !== id) });
  }

  success(opts) {
    return this.open({ ...opts, type: 'success' });
  }
  error(opts) {
    return this.open({ ...opts, type: 'error' });
  }
  warning(opts) {
    return this.open({ ...opts, type: 'warning' });
  }
  info(opts) {
    return this.open({ ...opts, type: 'info' });
  }

  render() {
    const { items } = this.state.data;
    const host = this.host();
    if (!host) return;
    host.textContent = '';
    const root = document.createElement('div');
    root.className = 'gd-notification-root';
    root.setAttribute('aria-live', 'polite');
    for (const item of items) {
      const node = document.createElement('div');
      node.className = `gd-notification gd-notification--${item.type}`;
      const title = document.createElement('div');
      title.className = 'gd-notification__message';
      title.textContent = item.message;
      node.appendChild(title);
      if (item.description) {
        const desc = document.createElement('div');
        desc.className = 'gd-notification__desc';
        desc.textContent = item.description;
        node.appendChild(desc);
      }
      const close = document.createElement('button');
      close.type = 'button';
      close.className = 'gd-notification__close';
      close.textContent = '×';
      close.addEventListener('click', () => this.close(item.id));
      node.appendChild(close);
      root.appendChild(node);
    }
    host.appendChild(root);
  }
}

/**
 * Message API helper — thin alias over Toast-like bottom notices.
 * Prefer `Toast` for snackbars; this mirrors antd `message` naming via Notification.open short form.
 */
export function messageApi(notification) {
  return {
    success: (text) => notification?.open({ message: text, type: 'success', duration: 2500 }),
    error: (text) => notification?.open({ message: text, type: 'error', duration: 2500 }),
    info: (text) => notification?.open({ message: text, type: 'info', duration: 2500 }),
    warning: (text) => notification?.open({ message: text, type: 'warning', duration: 2500 }),
  };
}
