import { Component } from '../engine/index.js';
import { loadUi } from './util.js';

/**
 * Toast / Snackbar — brief non-blocking message stack.
 *
 *   const toast = new Toast({});
 *   await toast.mount();
 *   toast.show({ message: 'Saved', type: 'success' });
 */
export class Toast extends Component {
  constructor(deps = {}) {
    super(deps);
    this.state.data.items = [];
    this._portal = null;
    this._seq = 0;
  }

  async mount(host = typeof document !== 'undefined' ? document.body : null, params = {}) {
    const target =
      typeof host === 'string' ? document.getElementById(host) : host || document.body;
    if (!target) throw new Error('Toast.mount: host not found');
    if (!this._portal) {
      this._portal = document.createElement('div');
      this._portal.className = 'gd-toast-portal';
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
   * @param {'info'|'success'|'warning'|'error'} [options.type]
   * @param {number} [options.duration] ms; 0 = sticky
   */
  show(options = {}) {
    const id = ++this._seq;
    const item = {
      id,
      message: options.message || '',
      type: options.type || 'info',
    };
    this.setData({ items: [...this.state.data.items, item] });
    const duration = options.duration ?? 3000;
    if (duration > 0) {
      setTimeout(() => this.dismiss(id), duration);
    }
    return id;
  }

  dismiss(id) {
    this.setData({ items: this.state.data.items.filter((it) => it.id !== id) });
  }

  render() {
    const { items } = this.state.data;
    // Always rebuild list (small)
    const host = this.host();
    if (!host) return;
    host.textContent = '';
    const root = document.createElement('div');
    root.className = 'gd-toast-root';
    root.setAttribute('aria-live', 'polite');
    for (const item of items) {
      const node = document.createElement('div');
      node.className = `gd-toast gd-toast--${item.type}`;
      node.setAttribute('role', 'status');
      node.textContent = item.message;
      const close = document.createElement('button');
      close.type = 'button';
      close.className = 'gd-toast__close';
      close.textContent = '×';
      close.addEventListener('click', () => this.dismiss(item.id));
      node.appendChild(close);
      root.appendChild(node);
    }
    host.appendChild(root);
  }
}
