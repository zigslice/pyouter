import { Component } from '../engine/index.js';
import { cx, el, loadUi } from './util.js';

export const JSON_TREE_ROW_H = 22;
const OVERSCAN = 8;

/**
 * @param {unknown} val
 * @returns {'null'|'boolean'|'number'|'string'|'array'|'object'}
 */
export function jsonValueType(val) {
  if (val === null) return 'null';
  const t = typeof val;
  if (t === 'number' || t === 'boolean' || t === 'string') return t;
  if (Array.isArray(val)) return 'array';
  if (t === 'object') return 'object';
  throw new Error(`Unsupported JSON type: ${Object.prototype.toString.call(val)}`);
}

/**
 * @param {string} parentPath
 * @param {string|number} key
 * @param {'object'|'array'} parentType
 */
export function jsonChildPath(parentPath, key, parentType) {
  if (parentType === 'array') return `${parentPath}[${key}]`;
  const safe = String(key).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
  return `${parentPath}['${safe}']`;
}

/**
 * Flatten JSON into visible rows given an expanded path set.
 * Cost is proportional to currently expanded nodes (not full tree size when collapsed).
 * @param {unknown} data
 * @param {Set<string>} expanded
 * @param {{ sortKeys?: boolean }} [opts]
 * @returns {Array<object>}
 */
export function flattenJsonTree(data, expanded, opts = {}) {
  const sortKeys = opts.sortKeys !== false;
  const rows = [];

  const walk = (value, path, key, depth, isLast) => {
    let type;
    try {
      type = jsonValueType(value);
    } catch {
      return;
    }
    const complex = type === 'object' || type === 'array';
    const childCount = complex
      ? type === 'array'
        ? value.length
        : Object.keys(value).length
      : 0;
    const isExpanded = complex && childCount > 0 && expanded.has(path);

    rows.push({
      path,
      key,
      value,
      type,
      depth,
      isLast,
      complex,
      childCount,
      expanded: isExpanded,
    });

    if (!isExpanded) return;

    if (type === 'array') {
      const last = value.length - 1;
      for (let i = 0; i < value.length; i++) {
        walk(value[i], jsonChildPath(path, i, 'array'), i, depth + 1, i === last);
      }
      return;
    }

    const keys = Object.keys(value);
    if (sortKeys) keys.sort();
    const last = keys.length - 1;
    for (let i = 0; i < keys.length; i++) {
      const k = keys[i];
      walk(value[k], jsonChildPath(path, k, 'object'), k, depth + 1, i === last);
    }
  };

  walk(data, '$', null, 0, true);
  return rows;
}

function collectComplexPaths(data, filter) {
  const out = [];
  const walk = (value, path) => {
    let type;
    try {
      type = jsonValueType(value);
    } catch {
      return;
    }
    if (type !== 'object' && type !== 'array') return;
    const childCount = type === 'array' ? value.length : Object.keys(value).length;
    if (childCount === 0) return;
    const node = { path, type, childCount, value, label: path === '$' ? null : path };
    if (!filter || filter(node)) out.push(path);
    if (type === 'array') {
      value.forEach((v, i) => walk(v, jsonChildPath(path, i, 'array')));
    } else {
      Object.keys(value)
        .sort()
        .forEach((k) => walk(value[k], jsonChildPath(path, k, 'object')));
    }
  };
  walk(data, '$');
  return out;
}

function previewComplex(type, childCount) {
  if (type === 'array') return childCount ? `[${childCount}]` : '[]';
  return childCount ? `{${childCount}}` : '{}';
}

function formatPrimitive(type, value) {
  if (type === 'string') return JSON.stringify(value);
  if (type === 'null') return 'null';
  return String(value);
}

/**
 * JsonTree — high-performance virtualized JSON viewer.
 *
 * Inspired by jsonTreeViewer (expand / mark / JSONPath), styled with gd5 themes.
 * Only visible rows are in the DOM; collapse keeps large subtrees cheap.
 *
 *   const jt = new JsonTree({ height: 360 });
 *   await jt.mount(host);
 *   jt.loadData(data);
 *   jt.expand(); jt.collapse();
 */
export class JsonTree extends Component {
  constructor(deps = {}) {
    super(deps);
    this.state.data.data = deps.data ?? null;
    this.state.data.height = deps.height ?? 360;
    this.state.data.expanded = new Set();
    this.state.data.marked = new Set();
    this.state.data.scrollTop = 0;
    this.state.data.sortKeys = deps.sortKeys !== false;
    this.state.data.rootLabel = deps.rootLabel ?? null;
    this._onPath = deps.onPath || null;
    this._defaultExpand =
      deps.defaultExpand === undefined ? 1 : deps.defaultExpand;
  }

  async mount(host, params = {}) {
    await loadUi();
    return super.mount(host, params);
  }

  /**
   * @param {unknown} data
   */
  loadData(data) {
    const expanded = new Set();
    if (data != null) {
      this._applyDefaultExpand(data, expanded);
    }
    this.setData(
      {
        data,
        expanded,
        marked: new Set(),
        scrollTop: 0,
      },
      { refresh: !!this._mounted }
    );
    return this;
  }

  _applyDefaultExpand(data, expanded) {
    const level = this._defaultExpand;
    if (level === true || level === 'all') {
      for (const p of collectComplexPaths(data)) expanded.add(p);
      return;
    }
    if (level === false || level === 0) return;
    if (typeof level === 'number') {
      const walk = (value, path, depth) => {
        let type;
        try {
          type = jsonValueType(value);
        } catch {
          return;
        }
        if (type !== 'object' && type !== 'array') return;
        const n = type === 'array' ? value.length : Object.keys(value).length;
        if (n === 0) return;
        if (depth < level) expanded.add(path);
        if (depth + 1 >= level) return;
        if (type === 'array') {
          value.forEach((v, i) =>
            walk(v, jsonChildPath(path, i, 'array'), depth + 1)
          );
        } else {
          Object.keys(value)
            .sort()
            .forEach((k) =>
              walk(value[k], jsonChildPath(path, k, 'object'), depth + 1)
            );
        }
      };
      walk(data, '$', 0);
    }
  }

  /** Expand all, or nodes matching filter(node). */
  expand(filter) {
    const data = this.state.data.data;
    if (data == null) return this;
    const next = new Set(this.state.data.expanded);
    for (const p of collectComplexPaths(data, filter)) next.add(p);
    this.setData({ expanded: next }, { refresh: !!this._mounted });
    return this;
  }

  collapse() {
    this.setData({ expanded: new Set() }, { refresh: !!this._mounted });
    return this;
  }

  unmarkAll() {
    this.setData({ marked: new Set() }, { refresh: !!this._mounted });
    return this;
  }

  getJSONPath(path) {
    return path || '$';
  }

  _rows() {
    const { data, expanded, sortKeys } = this.state.data;
    if (data == null) return [];
    return flattenJsonTree(data, expanded, { sortKeys });
  }

  componentDidAttachEvents() {
    const viewport = this.ids().gdJtViewport;
    if (!viewport) return;
    this.on(viewport, 'scroll', () => {
      this.state.data.scrollTop = viewport.scrollTop;
      this._paintWindow();
    });
  }

  _togglePath(path, recursive) {
    const data = this.state.data.data;
    const expanded = new Set(this.state.data.expanded);
    const open = expanded.has(path);
    if (!recursive) {
      if (open) expanded.delete(path);
      else expanded.add(path);
    } else {
      const rows = flattenJsonTree(data, new Set([...expanded, path]), {
        sortKeys: this.state.data.sortKeys,
      });
      const row = rows.find((r) => r.path === path);
      if (!row?.complex) return;
      if (open) {
        for (const p of [...expanded]) {
          if (
            p === path ||
            p.startsWith(`${path}[`) ||
            p.startsWith(`${path}['`)
          ) {
            expanded.delete(p);
          }
        }
      } else {
        for (const p of collectComplexPaths(row.value)) {
          expanded.add(p === '$' ? path : path + p.slice(1));
        }
      }
    }
    this.setData({ expanded }, { refresh: false });
    this._paintWindow(true);
  }

  _toggleMark(path) {
    const marked = new Set(this.state.data.marked);
    if (marked.has(path)) marked.delete(path);
    else marked.add(path);
    this.setData({ marked }, { refresh: false });
    this._paintWindow(true);
  }

  _onRowClick(row, e) {
    if (e.shiftKey) {
      e.preventDefault();
      const path = this.getJSONPath(row.path);
      if (this._onPath) this._onPath(path, row);
      else if (typeof window !== 'undefined') window.alert?.(path);
      return;
    }
    if (e.altKey) {
      e.preventDefault();
      this._toggleMark(row.path);
      return;
    }
    if (!row.complex || row.childCount === 0) return;
    this._togglePath(row.path, !!(e.ctrlKey || e.metaKey));
  }

  _renderRow(row) {
    const marked = this.state.data.marked.has(row.path);
    const indent = row.depth * 16;
    const kids = [];

    if (row.complex && row.childCount > 0) {
      kids.push(
        el('button', {
          type: 'button',
          className: cx(
            'gd-json-tree__twist',
            row.expanded && 'gd-json-tree__twist--open'
          ),
          attrs: { 'aria-label': row.expanded ? 'Collapse' : 'Expand' },
          onClick: (e) => {
            e.stopPropagation();
            this._togglePath(row.path, !!(e.ctrlKey || e.metaKey));
          },
        })
      );
    } else {
      kids.push(el('span', { className: 'gd-json-tree__twist gd-json-tree__twist--leaf' }));
    }

    if (row.key != null) {
      const label =
        typeof row.key === 'number' ? String(row.key) : JSON.stringify(String(row.key));
      kids.push(el('span', { className: 'gd-json-tree__key', text: label }));
      kids.push(el('span', { className: 'gd-json-tree__colon', text: ':' }));
    } else if (this.state.data.rootLabel) {
      kids.push(
        el('span', {
          className: 'gd-json-tree__key',
          text: this.state.data.rootLabel,
        })
      );
      kids.push(el('span', { className: 'gd-json-tree__colon', text: ':' }));
    }

    if (row.complex) {
      if (row.expanded) {
        kids.push(
          el('span', {
            className: 'gd-json-tree__punct',
            text: row.type === 'array' ? '[' : '{',
          })
        );
      } else {
        kids.push(
          el('span', {
            className: cx('gd-json-tree__preview', `gd-json-tree__value--${row.type}`),
            text: previewComplex(row.type, row.childCount),
          })
        );
      }
    } else {
      kids.push(
        el('span', {
          className: cx('gd-json-tree__value', `gd-json-tree__value--${row.type}`),
          text: formatPrimitive(row.type, row.value),
        })
      );
    }

    if (!row.isLast && !(row.complex && row.expanded)) {
      kids.push(el('span', { className: 'gd-json-tree__punct', text: ',' }));
    }

    return el(
      'div',
      {
        className: cx(
          'gd-json-tree__row',
          row.complex && 'gd-json-tree__row--complex',
          marked && 'gd-json-tree__row--marked',
          row.expanded && 'gd-json-tree__row--expanded'
        ),
        style: {
          height: `${JSON_TREE_ROW_H}px`,
          paddingLeft: `${indent + 4}px`,
        },
        attrs: { 'data-path': row.path, role: 'treeitem' },
        onClick: (e) => this._onRowClick(row, e),
      },
      ...kids
    );
  }

  _paintWindow(force = false) {
    const viewport = this.ids().gdJtViewport;
    const windowEl = this.ids().gdJtWindow;
    const spacerTop = this.ids().gdJtPadTop;
    const spacerBot = this.ids().gdJtPadBot;
    if (!viewport || !windowEl || !spacerTop || !spacerBot) return;

    const rows = this._rows();
    const total = rows.length;
    const scrollTop = viewport.scrollTop;
    const viewH = viewport.clientHeight || this.state.data.height;
    const start = Math.max(0, Math.floor(scrollTop / JSON_TREE_ROW_H) - OVERSCAN);
    const visible = Math.ceil(viewH / JSON_TREE_ROW_H) + OVERSCAN * 2;
    const end = Math.min(total, start + visible);
    const topH = start * JSON_TREE_ROW_H;
    const botH = Math.max(0, (total - end) * JSON_TREE_ROW_H);

    spacerTop.style.height = `${topH}px`;
    spacerBot.style.height = `${botH}px`;

    const sig = `${start}:${end}:${total}:${this.state.data.expanded.size}:${this.state.data.marked.size}`;
    if (!force && windowEl.dataset.sig === sig) return;
    windowEl.dataset.sig = sig;

    windowEl.textContent = '';
    for (let i = start; i < end; i++) {
      windowEl.appendChild(this._renderRow(rows[i]).dom());
    }
  }

  render() {
    const { height, data } = this.state.data;

    this.ensureShell(
      (ids) => ids.gdJtRoot,
      ({ div }) => {
        div(
          { id: 'gdJtRoot', className: 'gd-json-tree' },
          div({
            id: 'gdJtToolbar',
            className: 'gd-json-tree__toolbar',
          }),
          div(
            {
              id: 'gdJtViewport',
              className: 'gd-json-tree__viewport',
              style: { height: `${height}px` },
              attrs: { role: 'tree', tabindex: '0' },
            },
            div({ id: 'gdJtPadTop', className: 'gd-json-tree__spacer' }),
            div({ id: 'gdJtWindow', className: 'gd-json-tree__window' }),
            div({ id: 'gdJtPadBot', className: 'gd-json-tree__spacer' })
          ),
          div({
            className: 'gd-json-tree__hint',
            text: 'Click expand · Ctrl/⌘+click recursive · Alt+click mark · Shift+click path',
          })
        );
      }
    );

    const toolbar = this.ids().gdJtToolbar;
    if (toolbar && !toolbar.dataset.ready) {
      toolbar.dataset.ready = '1';
      toolbar.appendChild(
        el('button', {
          type: 'button',
          className: 'gd-btn gd-btn--default gd-btn--sm',
          text: 'Expand all',
          onClick: () => this.expand(),
        }).dom()
      );
      toolbar.appendChild(
        el('button', {
          type: 'button',
          className: 'gd-btn gd-btn--default gd-btn--sm',
          text: 'Collapse all',
          onClick: () => this.collapse(),
        }).dom()
      );
      toolbar.appendChild(
        el('button', {
          type: 'button',
          className: 'gd-btn gd-btn--text gd-btn--sm',
          text: 'Unmark',
          onClick: () => this.unmarkAll(),
        }).dom()
      );
    }

    const viewport = this.ids().gdJtViewport;
    if (viewport) viewport.style.height = `${height}px`;

    if (data == null) {
      const win = this.ids().gdJtWindow;
      if (win) {
        win.textContent = '';
        win.appendChild(
          el('div', {
            className: 'gd-json-tree__empty',
            text: 'No JSON loaded',
          }).dom()
        );
      }
      return;
    }

    this._paintWindow(true);
  }
}

/**
 * Lightweight factory wrapper: mounts a JsonTree into a host element node.
 * Prefer `new JsonTree()` for expand/collapse control.
 */
export function createJsonTree(data, host, options = {}) {
  const jt = new JsonTree({ ...options, data });
  const elHost =
    typeof host === 'string'
      ? typeof document !== 'undefined'
        ? document.getElementById(host)
        : null
      : host;
  if (elHost) {
    void jt.mount(elHost).then(() => jt.loadData(data));
  } else {
    jt.loadData(data);
  }
  return jt;
}
