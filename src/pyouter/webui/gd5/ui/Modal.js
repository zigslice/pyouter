import { Component } from '../engine/index.js';
import { loadUi } from './util.js';

/**
 * Modal — full Component (overlay lifecycle).
 *
 *   const modal = new Modal({ navigator, logger });
 *   await modal.mount(document.body);
 *   modal.open({ title: 'Confirm', content: 'Delete item?', onOk: () => … });
 */
export class Modal extends Component {
  constructor(deps = {}) {
    super(deps);
    this.state.data.open = false;
    this.state.data.title = '';
    this.state.data.content = '';
    this.state.data.okText = 'OK';
    this.state.data.cancelText = 'Cancel';
    this.state.data.size = 'md';
    this._onOk = null;
    this._onCancel = null;
    /** @type {HTMLElement|null} outer portal node (never clears document.body) */
    this._portal = null;
  }

  /**
   * Mount into a dedicated portal under `host` (default `document.body`).
   * Avoids `paint` → `D.clear(body)` wiping the page.
   * @param {HTMLElement|string} [host]
   * @param {object} [params]
   */
  async mount(host = typeof document !== 'undefined' ? document.body : null, params = {}) {
    const target =
      typeof host === 'string' ? document.getElementById(host) : host || document.body;
    if (!target) throw new Error('Modal.mount: host not found');

    if (!this._portal) {
      this._portal = document.createElement('div');
      this._portal.className = 'gd-modal-portal';
      target.appendChild(this._portal);
    }
    return super.mount(this._portal, params);
  }

  componentDidUnMount() {
    if (this._portal?.parentNode) {
      this._portal.parentNode.removeChild(this._portal);
    }
    this._portal = null;
  }

  async componentDidMount() {
    await loadUi();
  }

  /**
   * @param {object} [options]
   * @param {string} [options.title]
   * @param {string} [options.content]
   * @param {string} [options.okText]
   * @param {string} [options.cancelText]
   * @param {'sm'|'md'|'lg'} [options.size]
   * @param {function} [options.onOk]
   * @param {function} [options.onCancel]
   */
  open(options = {}) {
    this._onOk = options.onOk || null;
    this._onCancel = options.onCancel || null;
    this.setData({
      open: true,
      title: options.title ?? this.state.data.title,
      content: options.content ?? this.state.data.content,
      okText: options.okText ?? 'OK',
      cancelText: options.cancelText ?? 'Cancel',
      size: options.size ?? 'md',
    });
    return this;
  }

  close() {
    this.setData({ open: false });
    return this;
  }

  componentDidAttachEvents() {
    this.on(window, 'keydown', (event) => {
      if (event.key === 'Escape' && this.state.data.open) this._cancel();
    });
  }

  _ok() {
    this._onOk?.();
    this.close();
  }

  _cancel() {
    this._onCancel?.();
    this.close();
  }

  render() {
    const { open, title, content, okText, cancelText, size } = this.state.data;

    this.ensureShell(
      (ids) => ids.gdModalRoot,
      ({ div, button }) => {
        div(
          { className: 'gd-modal-root', id: 'gdModalRoot' },
          div({
            className: 'gd-modal-mask',
            id: 'gdModalMask',
            onClick: () => this._cancel(),
          }),
          div(
            { className: 'gd-modal-wrap', id: 'gdModalWrap' },
            div(
              { className: 'gd-modal', id: 'gdModalPanel' },
              div(
                { className: 'gd-modal__header', id: 'gdModalHeader' },
                div({ className: 'gd-modal__title', id: 'gdModalTitle', text: title }),
                button({
                  id: 'gdModalClose',
                  type: 'button',
                  className: 'gd-btn gd-btn--text gd-btn--sm',
                  text: '×',
                  onClick: () => this._cancel(),
                })
              ),
              div({ className: 'gd-modal__body', id: 'gdModalBody', text: content }),
              div(
                { className: 'gd-modal__footer', id: 'gdModalFooter' },
                button({
                  id: 'gdModalCancel',
                  type: 'button',
                  className: 'gd-btn gd-btn--ghost gd-btn--md',
                  text: cancelText,
                  onClick: () => this._cancel(),
                }),
                button({
                  id: 'gdModalOk',
                  type: 'button',
                  className: 'gd-btn gd-btn--primary gd-btn--md',
                  text: okText,
                  onClick: () => this._ok(),
                })
              )
            )
          )
        );
      }
    );

    const root = this.ids().gdModalRoot;
    const panel = this.ids().gdModalPanel;
    const titleEl = this.ids().gdModalTitle;
    const body = this.ids().gdModalBody;
    const ok = this.ids().gdModalOk;
    const cancel = this.ids().gdModalCancel;

    if (root) root.classList.toggle('is-open', !!open);
    if (panel) {
      panel.className = `gd-modal${size && size !== 'md' ? ` gd-modal--${size}` : ''}`;
    }
    if (titleEl) titleEl.textContent = title || '';
    if (body) body.textContent = content || '';
    if (ok) ok.textContent = okText || 'OK';
    if (cancel) cancel.textContent = cancelText || 'Cancel';
  }
}
