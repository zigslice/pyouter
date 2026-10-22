import { Component } from '../engine/index.js';
import { loadUi } from './util.js';

/**
 * Lightbox — click-to-enlarge image overlay.
 */
export class Lightbox extends Component {
  constructor(deps = {}) {
    super(deps);
    this.state.data.open = false;
    this.state.data.src = '';
    this.state.data.alt = '';
    this._portal = null;
  }

  async mount(host = typeof document !== 'undefined' ? document.body : null, params = {}) {
    const target =
      typeof host === 'string' ? document.getElementById(host) : host || document.body;
    if (!target) throw new Error('Lightbox.mount: host not found');
    if (!this._portal) {
      this._portal = document.createElement('div');
      this._portal.className = 'gd-lightbox-portal';
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

  open({ src, alt } = {}) {
    this.setData({ open: true, src: src || '', alt: alt || '' });
    return this;
  }

  close() {
    this.setData({ open: false });
    return this;
  }

  componentDidAttachEvents() {
    this.on(window, 'keydown', (e) => {
      if (e.key === 'Escape' && this.state.data.open) this.close();
    });
  }

  render() {
    const { open, src, alt } = this.state.data;
    this.ensureShell(
      (ids) => ids.gdLightboxRoot,
      ({ div, img, button }) => {
        div(
          { className: 'gd-lightbox-root', id: 'gdLightboxRoot' },
          div({
            className: 'gd-lightbox-mask',
            id: 'gdLightboxMask',
            onClick: () => this.close(),
          }),
          div(
            { className: 'gd-lightbox__stage', id: 'gdLightboxStage' },
            img({ id: 'gdLightboxImg', className: 'gd-lightbox__img', src: '', alt: '' }),
            button({
              type: 'button',
              className: 'gd-lightbox__close',
              id: 'gdLightboxClose',
              text: '×',
              onClick: () => this.close(),
            })
          )
        );
      }
    );
    const root = this.ids().gdLightboxRoot;
    const image = this.ids().gdLightboxImg;
    if (root) root.classList.toggle('is-open', !!open);
    if (image) {
      image.src = src || '';
      image.alt = alt || '';
    }
  }
}
