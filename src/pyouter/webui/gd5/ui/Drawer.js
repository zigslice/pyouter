import { Component } from '../engine/index.js';
import { loadUi } from './util.js';

/**
 * Drawer / Sheet / NavDrawer — side or bottom overlay panel.
 *
 *   const drawer = new Drawer({});
 *   await drawer.mount();
 *   drawer.open({ title: 'Menu', content, placement: 'left' });
 */
export class Drawer extends Component {
  constructor(deps = {}) {
    super(deps);
    this.state.data.open = false;
    this.state.data.title = '';
    this.state.data.content = '';
    this.state.data.placement = 'right'; // left | right | bottom | top
    this.state.data.size = 'md';
    this._portal = null;
    this._onClose = null;
  }

  async mount(host = typeof document !== 'undefined' ? document.body : null, params = {}) {
    const target =
      typeof host === 'string' ? document.getElementById(host) : host || document.body;
    if (!target) throw new Error('Drawer.mount: host not found');
    if (!this._portal) {
      this._portal = document.createElement('div');
      this._portal.className = 'gd-drawer-portal';
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

  open(options = {}) {
    this._onClose = options.onClose || null;
    this.setData({
      open: true,
      title: options.title ?? this.state.data.title,
      content: options.content ?? this.state.data.content,
      placement: options.placement ?? 'right',
      size: options.size ?? 'md',
    });
    return this;
  }

  close() {
    this._onClose?.();
    this.setData({ open: false });
    return this;
  }

  componentDidAttachEvents() {
    this.on(window, 'keydown', (event) => {
      if (event.key === 'Escape' && this.state.data.open) this.close();
    });
  }

  render() {
    const { open, title, content, placement, size } = this.state.data;
    this.ensureShell(
      (ids) => ids.gdDrawerRoot,
      ({ div, button }) => {
        div(
          { className: 'gd-drawer-root', id: 'gdDrawerRoot' },
          div({
            className: 'gd-drawer-mask',
            id: 'gdDrawerMask',
            onClick: () => this.close(),
          }),
          div(
            {
              className: `gd-drawer gd-drawer--${placement} gd-drawer--${size}`,
              id: 'gdDrawerPanel',
            },
            div(
              { className: 'gd-drawer__header', id: 'gdDrawerHeader' },
              div({ className: 'gd-drawer__title', id: 'gdDrawerTitle', text: title }),
              button({
                type: 'button',
                className: 'gd-btn gd-btn--text gd-btn--sm',
                id: 'gdDrawerClose',
                text: '×',
                onClick: () => this.close(),
              })
            ),
            div({ className: 'gd-drawer__body', id: 'gdDrawerBody', text: content })
          )
        );
      }
    );

    const root = this.ids().gdDrawerRoot;
    const titleEl = this.ids().gdDrawerTitle;
    const body = this.ids().gdDrawerBody;
    const panel = this.ids().gdDrawerPanel;
    if (root) root.classList.toggle('is-open', !!open);
    if (titleEl) titleEl.textContent = title || '';
    if (body) body.textContent = typeof content === 'string' ? content : body.textContent;
    if (panel) {
      panel.className = `gd-drawer gd-drawer--${placement} gd-drawer--${size}`;
    }
  }
}

/** Alias */
export class Sheet extends Drawer {}
