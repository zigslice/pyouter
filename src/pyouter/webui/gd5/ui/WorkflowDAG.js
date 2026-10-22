import { Component } from '../engine/index.js';
import { Drawer } from './Drawer.js';
import { cx, el, loadUi, omit } from './util.js';

/**
 * @typedef {{ key: string, title?: string, status?: string, description?: string, meta?: object }} WfNode
 * @typedef {{ key: string, title?: string, nodes?: WfNode[] }} WfColumn
 * @typedef {{ from: string, to: string }} WfEdge
 */

/**
 * WorkflowDAG — multi-column DAG canvas.
 *
 * - Scroll in all directions
 * - Drag blank area to pan the viewport
 * - Click a node → right Drawer with details
 *
 *   const wf = new WorkflowDAG({});
 *   await wf.mount(hostEl);
 *   wf.setGraph({ columns, edges });
 */
export class WorkflowDAG extends Component {
  constructor(deps = {}) {
    super(deps);
    this.state.data.columns = [];
    this.state.data.edges = [];
    this.state.data.selectedKey = null;
    /** @type {(node: WfNode) => string|HTMLElement|{dom(): HTMLElement}|null|undefined} */
    this._renderDetail = deps.renderDetail || null;
    this._onNodeClick = deps.onNodeClick || null;
    this._drawer = new Drawer({});
    this._panning = false;
    this._panStart = null;
    this._edgeRaf = 0;
  }

  /**
   * @param {HTMLElement|string} host
   * @param {object} [params]
   */
  async mount(host, params = {}) {
    await loadUi();
    await super.mount(host, params);
    await this._drawer.mount(
      typeof document !== 'undefined' ? document.body : null
    );
    return this;
  }

  componentDidUnMount() {
    this._drawer.unmount();
    if (this._edgeRaf) cancelAnimationFrame(this._edgeRaf);
  }

  /**
   * Replace graph data and refresh.
   * @param {{ columns?: WfColumn[], edges?: WfEdge[], selectedKey?: string|null }} graph
   */
  setGraph(graph = {}) {
    this.setData(
      {
        columns: graph.columns ?? this.state.data.columns,
        edges: graph.edges ?? this.state.data.edges,
        selectedKey:
          graph.selectedKey !== undefined
            ? graph.selectedKey
            : this.state.data.selectedKey,
      },
      { refresh: !!this._mounted }
    );
    return this;
  }

  /** @param {(node: WfNode) => any} fn */
  setRenderDetail(fn) {
    this._renderDetail = fn;
    return this;
  }

  /** @param {(node: WfNode, ctx: { openDrawer: Function }) => void} fn */
  setOnNodeClick(fn) {
    this._onNodeClick = fn;
    return this;
  }

  findNode(key) {
    for (const col of this.state.data.columns || []) {
      for (const n of col.nodes || []) {
        if (n.key === key) return n;
      }
    }
    return null;
  }

  openDrawerFor(node) {
    if (!node) return this;
    const custom = this._renderDetail?.(node);
    let content = '';
    if (typeof custom === 'string') {
      content = custom;
    } else if (!custom) {
      const bits = [
        node.description || '',
        node.status ? `Status: ${node.status}` : '',
        node.key ? `Key: ${node.key}` : '',
      ].filter(Boolean);
      content = bits.join('\n\n') || 'No details.';
    }

    this._drawer.open({
      title: node.title || node.key,
      content,
      placement: 'right',
      size: 'md',
      onClose: () => {
        this.setData({ selectedKey: null }, { refresh: false });
        this._syncSelection();
      },
    });

    if (custom && typeof custom !== 'string') {
      const body = this._drawer.ids().gdDrawerBody;
      if (body) {
        body.textContent = '';
        const dom = typeof custom.dom === 'function' ? custom.dom() : custom;
        if (dom) body.appendChild(dom);
      }
    }
    return this;
  }

  componentDidAttachEvents() {
    const viewport = this.ids().gdWfViewport;
    if (!viewport) return;

    this.on(viewport, 'pointerdown', (e) => this._onPointerDown(e));
    this.on(viewport, 'pointermove', (e) => this._onPointerMove(e));
    this.on(viewport, 'pointerup', (e) => this._onPointerUp(e));
    this.on(viewport, 'pointercancel', (e) => this._onPointerUp(e));
    this.on(viewport, 'scroll', () => this._scheduleEdges());
    this.on(window, 'resize', () => this._scheduleEdges());
  }

  _onPointerDown(e) {
    if (e.button !== 0) return;
    if (e.target.closest?.('.gd-workflow__node')) return;
    const viewport = this.ids().gdWfViewport;
    if (!viewport) return;
    this._panning = true;
    this._panStart = {
      x: e.clientX,
      y: e.clientY,
      left: viewport.scrollLeft,
      top: viewport.scrollTop,
    };
    viewport.classList.add('is-panning');
    try {
      viewport.setPointerCapture(e.pointerId);
    } catch {
      /* ignore */
    }
    e.preventDefault();
  }

  _onPointerMove(e) {
    if (!this._panning || !this._panStart) return;
    const viewport = this.ids().gdWfViewport;
    if (!viewport) return;
    const dx = e.clientX - this._panStart.x;
    const dy = e.clientY - this._panStart.y;
    viewport.scrollLeft = this._panStart.left - dx;
    viewport.scrollTop = this._panStart.top - dy;
  }

  _onPointerUp(e) {
    if (!this._panning) return;
    this._panning = false;
    this._panStart = null;
    const viewport = this.ids().gdWfViewport;
    viewport?.classList.remove('is-panning');
    try {
      viewport?.releasePointerCapture?.(e.pointerId);
    } catch {
      /* ignore */
    }
  }

  _scheduleEdges() {
    if (typeof requestAnimationFrame !== 'function') {
      this._drawEdges();
      return;
    }
    if (this._edgeRaf) cancelAnimationFrame(this._edgeRaf);
    this._edgeRaf = requestAnimationFrame(() => {
      this._edgeRaf = 0;
      this._drawEdges();
    });
  }

  _syncSelection() {
    const key = this.state.data.selectedKey;
    const root = this.ids().gdWfRoot;
    if (!root) return;
    root.querySelectorAll('.gd-workflow__node').forEach((nodeEl) => {
      nodeEl.classList.toggle(
        'gd-workflow__node--selected',
        nodeEl.getAttribute('data-node-key') === key
      );
    });
  }

  _ensureSvg() {
    const host = this.ids().gdWfEdgesHost;
    if (!host) return null;
    let svg = this.ids().gdWfEdges;
    if (svg && svg.parentNode === host) return svg;
    host.textContent = '';
    svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'gd-workflow__edges');
    svg.id = 'gdWfEdges';
    host.appendChild(svg);
    if (!this.state.ref) this.state.ref = { class: {}, id: {}, key: {} };
    if (!this.state.ref.id) this.state.ref.id = {};
    this.state.ref.id.gdWfEdges = svg;
    return svg;
  }

  _drawEdges() {
    const canvas = this.ids().gdWfCanvas;
    const svg = this._ensureSvg();
    if (!canvas || !svg) return;

    const edges = this.state.data.edges || [];
    const cRect = canvas.getBoundingClientRect();
    const paths = [];

    for (const edge of edges) {
      const esc =
        typeof CSS !== 'undefined' && CSS.escape
          ? CSS.escape
          : (s) => String(s).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
      const fromEl = canvas.querySelector(
        `[data-node-key="${esc(String(edge.from))}"]`
      );
      const toEl = canvas.querySelector(
        `[data-node-key="${esc(String(edge.to))}"]`
      );
      if (!fromEl || !toEl) continue;
      const a = fromEl.getBoundingClientRect();
      const b = toEl.getBoundingClientRect();
      const x1 = a.right - cRect.left;
      const y1 = a.top + a.height / 2 - cRect.top;
      const x2 = b.left - cRect.left;
      const y2 = b.top + b.height / 2 - cRect.top;
      const dx = Math.max(48, Math.abs(x2 - x1) * 0.5);
      paths.push(
        `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`
      );
    }

    const w = Math.max(canvas.scrollWidth, canvas.offsetWidth, 1);
    const h = Math.max(canvas.scrollHeight, canvas.offsetHeight, 1);
    svg.setAttribute('width', String(w));
    svg.setAttribute('height', String(h));
    svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
    svg.innerHTML = `<defs>
      <marker id="gdWfArrow" viewBox="0 0 10 10" refX="9" refY="5"
        markerWidth="7" markerHeight="7" orient="auto">
        <path d="M 0 0 L 10 5 L 0 10 z" class="gd-workflow__arrow"></path>
      </marker>
    </defs>${paths
      .map(
        (d) =>
          `<path class="gd-workflow__edge" d="${d}" fill="none" marker-end="url(#gdWfArrow)"></path>`
      )
      .join('')}`;
  }

  _onNodeActivate(node) {
    this.setData({ selectedKey: node.key }, { refresh: false });
    this._syncSelection();
    if (this._onNodeClick) {
      this._onNodeClick(node, {
        openDrawer: () => this.openDrawerFor(node),
      });
    } else {
      this.openDrawerFor(node);
    }
  }

  render() {
    const { columns, selectedKey } = this.state.data;

    this.ensureShell(
      (ids) => ids.gdWfRoot,
      ({ div }) => {
        div(
          { id: 'gdWfRoot', className: 'gd-workflow' },
          div(
            {
              id: 'gdWfViewport',
              className: 'gd-workflow__viewport',
              attrs: { tabindex: '0' },
            },
            div(
              { id: 'gdWfCanvas', className: 'gd-workflow__canvas' },
              div({
                id: 'gdWfEdgesHost',
                className: 'gd-workflow__edges-host',
              }),
              div({ id: 'gdWfColumns', className: 'gd-workflow__columns' })
            )
          ),
          div({
            className: 'gd-workflow__hint',
            text: 'Scroll or drag blank area to pan · Click a node for details',
          })
        );
      }
    );

    const colsHost = this.ids().gdWfColumns;
    if (!colsHost) return;

    colsHost.textContent = '';
    for (const col of columns || []) {
      const colEl = el(
        'div',
        {
          className: 'gd-workflow__column',
          attrs: { 'data-column-key': col.key || '' },
        },
        el('div', {
          className: 'gd-workflow__column-title',
          text: col.title || col.key || '',
        }),
        el(
          'div',
          { className: 'gd-workflow__column-body' },
          ...(col.nodes || []).map((node) => {
            const kids = [
              el('div', {
                className: 'gd-workflow__node-title',
                text: node.title || node.key,
              }),
            ];
            if (node.status) {
              kids.push(
                el('div', {
                  className: 'gd-workflow__node-status',
                  text: node.status,
                })
              );
            }
            if (node.description) {
              kids.push(
                el('div', {
                  className: 'gd-workflow__node-desc',
                  text: node.description,
                })
              );
            }
            return el(
              'button',
              {
                type: 'button',
                className: cx(
                  'gd-workflow__node',
                  node.status && `gd-workflow__node--${node.status}`,
                  selectedKey === node.key && 'gd-workflow__node--selected'
                ),
                attrs: { 'data-node-key': node.key },
                onClick: (e) => {
                  e.stopPropagation();
                  this._onNodeActivate(node);
                },
              },
              ...kids
            );
          })
        )
      );
      colsHost.appendChild(colEl.dom());
    }

    this._ensureSvg();
    this._scheduleEdges();
  }
}

/**
 * Lightweight static board (no pan / Drawer). Prefer WorkflowDAG Component.
 */
export function WorkflowBoard(props = {}) {
  const { columns = [], className, selectedKey, onNodeClick } = props;
  return el(
    'div',
    {
      ...omit(props, [
        'columns',
        'className',
        'selectedKey',
        'onNodeClick',
        'edges',
      ]),
      className: cx('gd-workflow gd-workflow--static', className),
    },
    el(
      'div',
      { className: 'gd-workflow__columns' },
      ...columns.map((col) =>
        el(
          'div',
          { className: 'gd-workflow__column' },
          el('div', {
            className: 'gd-workflow__column-title',
            text: col.title || col.key || '',
          }),
          el(
            'div',
            { className: 'gd-workflow__column-body' },
            ...(col.nodes || []).map((node) =>
              el('button', {
                type: 'button',
                className: cx(
                  'gd-workflow__node',
                  selectedKey === node.key && 'gd-workflow__node--selected'
                ),
                text: node.title || node.key,
                onClick: () => onNodeClick?.(node),
              })
            )
          )
        )
      )
    )
  );
}
