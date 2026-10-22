import { Component } from '../engine/index.js';
import { cx, loadUi } from './util.js';

const DEFAULT_ECHARTS_URL = 'https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.esm.min.js';

/** @type {Promise<any>|null} */
let echartsPromise = null;

/**
 * Load ECharts once (CDN ESM or inject `echarts` module).
 * @param {string|object} [spec] module URL or `{ init, … }` namespace
 */
export function loadEcharts(spec = DEFAULT_ECHARTS_URL) {
  if (spec && typeof spec === 'object' && typeof spec.init === 'function') {
    return Promise.resolve(spec);
  }
  if (!echartsPromise) {
    const url = typeof spec === 'string' && spec ? spec : DEFAULT_ECHARTS_URL;
    echartsPromise = import(/* @vite-ignore */ url).then((mod) => mod.default || mod);
  }
  return echartsPromise;
}

/**
 * ECharts host Component — same composition as TodoList.
 */
export class EChartView extends Component {
  /**
   * @param {object} [deps]
   * @param {object} [deps.option] ECharts option
   * @param {string|number} [deps.height]
   * @param {string|number} [deps.width]
   * @param {string} [deps.className]
   * @param {string|object} [deps.echarts] CDN URL or echarts namespace
   * @param {boolean} [deps.autoResize]
   * @param {(chart:any, echarts:any)=>void} [deps.onReady]
   */
  constructor(deps = {}) {
    super(deps);
    this.state.data.option = deps.option || {};
    this.state.data.height = deps.height ?? 320;
    this.state.data.width = deps.width ?? '100%';
    this.state.data.className = deps.className || '';
    this._echartsSpec = deps.echarts ?? DEFAULT_ECHARTS_URL;
    this._autoResize = deps.autoResize !== false;
    this._onReady = typeof deps.onReady === 'function' ? deps.onReady : null;
    this._chart = null;
    this._ro = null;
    this._initing = false;
  }

  async mount(host, params = {}) {
    await loadUi();
    return super.mount(host, params);
  }

  getChart() {
    return this._chart;
  }

  setOption(option, notMerge = false) {
    this.state.data.option = option || {};
    if (this._chart) this._chart.setOption(this.state.data.option, notMerge);
    else if (this._mounted) this.refresh();
    return this;
  }

  resize() {
    this._chart?.resize?.();
    return this;
  }

  componentDidUnMount() {
    this._ro?.disconnect?.();
    this._ro = null;
    this._chart?.dispose?.();
    this._chart = null;
  }

  async componentDidMount() {
    // Chart inits after first paint (host must exist).
  }

  async _ensureChart() {
    const host = this.ids().gdEchartHost;
    if (!host || this._chart || this._initing) return;
    this._initing = true;
    try {
      const echarts = await loadEcharts(this._echartsSpec);
      if (this._chart || !this.ids().gdEchartHost) return;
      this._chart = echarts.init(host);
      this._chart.setOption(this.state.data.option || {});
      if (this._autoResize && typeof ResizeObserver !== 'undefined') {
        this._ro = new ResizeObserver(() => this._chart?.resize?.());
        this._ro.observe(host);
      }
      this._onReady?.(this._chart, echarts);
    } finally {
      this._initing = false;
    }
  }

  render() {
    const { height, width, className } = this.state.data;
    const h = typeof height === 'number' ? `${height}px` : String(height);
    const w = typeof width === 'number' ? `${width}px` : String(width);

    this.ensureShell(
      (ids) => ids.gdEchartRoot,
      ({ div }) => {
        div(
          {
            id: 'gdEchartRoot',
            className: cx('gd-echart', className),
            style: { width: w, height: h },
          },
          div({
            id: 'gdEchartHost',
            className: 'gd-echart__host',
            style: { width: '100%', height: '100%' },
          })
        );
      }
    );

    if (this._mounted || this.host()) {
      void this._ensureChart();
    }
  }
}

/**
 * EChart — call inline like TodoList / Button:
 *
 * ```js
 * div(
 *   { id: 'root' },
 *   EChart({ option: { xAxis: {}, yAxis: {}, series: [{ type: 'bar', data: [1,2,3] }] } }),
 *   ThreeView({ onInit(ctx) { … } })
 * )
 * ```
 *
 * @param {object} [props]
 * @returns {EChartView}
 */
export function EChart(props = {}) {
  return new EChartView(props);
}

export function createEChart(options = {}, host) {
  const chart = EChart(options);
  const elHost =
    typeof host === 'string'
      ? typeof document !== 'undefined'
        ? document.getElementById(host)
        : null
      : host;
  if (elHost) void chart.mount(elHost);
  return chart;
}
