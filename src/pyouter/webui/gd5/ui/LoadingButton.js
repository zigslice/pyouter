import { Component } from '../engine/index.js';
import { Button } from './button.js';
import { cx, loadUi } from './util.js';

/**
 * LoadingButton — async action button (Loading Button).
 *
 * Click → busy color + dots/spin indicator → ignores further clicks
 * until the promise settles → back to plain text.
 *
 * @param {object} [deps]
 * @param {string} [deps.text]
 * @param {string} [deps.loadingText]
 * @param {'primary'|'default'|'ghost'|'danger'|'text'} [deps.type] idle type
 * @param {'primary'|'default'|'ghost'|'danger'|'text'} [deps.loadingType] busy type (default primary)
 * @param {'sm'|'md'|'lg'} [deps.size]
 * @param {boolean} [deps.block]
 * @param {'dots'|'spin'} [deps.indicator]
 * @param {boolean} [deps.disabled]
 * @param {() => (void|Promise<void>)} [deps.onClick]
 * @param {(err: unknown) => void} [deps.onError]
 * @param {string} [deps.className]
 */
export class LoadingButton extends Component {
  constructor(deps = {}) {
    super(deps);
    this.state.data.text = deps.text ?? 'Submit';
    this.state.data.loadingText = deps.loadingText ?? deps.text ?? 'Submit';
    this.state.data.type = deps.type ?? 'default';
    this.state.data.loadingType = deps.loadingType ?? 'primary';
    this.state.data.size = deps.size ?? 'md';
    this.state.data.block = !!deps.block;
    this.state.data.indicator = deps.indicator === 'spin' ? 'spin' : 'dots';
    this.state.data.disabled = !!deps.disabled;
    this.state.data.className = deps.className || '';
    this.state.data.loading = false;
    this._onClick = deps.onClick || null;
    this._onError = deps.onError || null;
    this._pending = false;
  }

  async mount(host, params = {}) {
    await loadUi();
    return super.mount(host, params);
  }

  isLoading() {
    return !!this.state.data.loading;
  }

  setDisabled(disabled) {
    this.setData({ disabled: !!disabled }, { refresh: !!this._mounted });
    return this;
  }

  setText(text) {
    this.setData({ text: String(text ?? '') }, { refresh: !!this._mounted });
    return this;
  }

  /**
   * Programmatically run the action (same lock as click).
   * @returns {Promise<void>}
   */
  async trigger() {
    return this._run();
  }

  async _run() {
    if (this._pending || this.state.data.loading || this.state.data.disabled) return;
    this._pending = true;
    this.setData({ loading: true }, { refresh: !!this._mounted });
    try {
      await this._onClick?.();
    } catch (err) {
      this._onError?.(err);
      throw err;
    } finally {
      this._pending = false;
      if (this._mounted) {
        this.setData({ loading: false });
      } else {
        this.state.data.loading = false;
      }
    }
  }

  render() {
    const d = this.state.data;
    const busy = !!d.loading;

    this.ensureShell(
      (ids) => ids.gdLbRoot,
      ({ div }) => {
        div({ id: 'gdLbRoot', className: 'gd-loading-button' });
      }
    );

    const root = this.ids().gdLbRoot;
    if (!root) return;

    root.textContent = '';
    root.appendChild(
      Button({
        type: busy ? d.loadingType : d.type,
        size: d.size,
        block: d.block,
        text: d.text,
        loadingText: d.loadingText,
        loading: busy,
        indicator: d.indicator,
        disabled: d.disabled,
        className: cx('gd-loading-button__btn', d.className),
        onClick: () => {
          void this._run();
        },
      }).dom()
    );
  }
}

/**
 * @param {object} options
 * @param {HTMLElement|string} [host]
 */
export function createLoadingButton(options = {}, host) {
  const btn = new LoadingButton(options);
  const elHost =
    typeof host === 'string'
      ? typeof document !== 'undefined'
        ? document.getElementById(host)
        : null
      : host;
  if (elHost) void btn.mount(elHost);
  return btn;
}

/** Alias */
export const AsyncButton = LoadingButton;
