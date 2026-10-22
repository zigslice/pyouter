import { Component } from '../engine/index.js';
import { loadUi } from './util.js';

/**
 * CommandPalette — keyboard-first searchable action launcher.
 *
 *   const cmd = new CommandPalette({});
 *   await cmd.mount();
 *   cmd.open({ items: [{ id, label, onSelect }] });
 */
export class CommandPalette extends Component {
  constructor(deps = {}) {
    super(deps);
    this.state.data.open = false;
    this.state.data.query = '';
    this.state.data.items = [];
    this._portal = null;
  }

  async mount(host = typeof document !== 'undefined' ? document.body : null, params = {}) {
    const target =
      typeof host === 'string' ? document.getElementById(host) : host || document.body;
    if (!target) throw new Error('CommandPalette.mount: host not found');
    if (!this._portal) {
      this._portal = document.createElement('div');
      this._portal.className = 'gd-cmd-portal';
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
    this.setData({
      open: true,
      query: '',
      items: options.items || this.state.data.items,
    });
    return this;
  }

  close() {
    this.setData({ open: false, query: '' });
    return this;
  }

  componentDidAttachEvents() {
    this.on(window, 'keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (this.state.data.open) this.close();
        else this.open();
      } else if (e.key === 'Escape' && this.state.data.open) {
        this.close();
      }
    });
  }

  render() {
    const { open, query, items } = this.state.data;
    const q = query.toLowerCase();
    const filtered = items.filter((it) =>
      String(it.label || '')
        .toLowerCase()
        .includes(q)
    );

    this.ensureShell(
      (ids) => ids.gdCmdRoot,
      ({ div, input }) => {
        div(
          { className: 'gd-cmd-root', id: 'gdCmdRoot' },
          div({
            className: 'gd-cmd-mask',
            id: 'gdCmdMask',
            onClick: () => this.close(),
          }),
          div(
            { className: 'gd-cmd', id: 'gdCmdPanel' },
            input({
              id: 'gdCmdInput',
              className: 'gd-cmd__input',
              placeholder: 'Type a command…',
              onInput: (e) => this.setData({ query: e.target.value }),
            }),
            div({ className: 'gd-cmd__list', id: 'gdCmdList' })
          )
        );
      }
    );

    const root = this.ids().gdCmdRoot;
    const list = this.ids().gdCmdList;
    const inputEl = this.ids().gdCmdInput;
    if (root) root.classList.toggle('is-open', !!open);
    if (inputEl && open && document.activeElement !== inputEl) {
      queueMicrotask(() => inputEl.focus());
    }
    if (list) {
      list.textContent = '';
      for (const it of filtered) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'gd-cmd__item';
        btn.textContent = it.label;
        btn.addEventListener('click', () => {
          it.onSelect?.(it);
          this.close();
        });
        list.appendChild(btn);
      }
      if (!filtered.length) {
        const empty = document.createElement('div');
        empty.className = 'gd-cmd__empty';
        empty.textContent = 'No results';
        list.appendChild(empty);
      }
    }
  }
}
