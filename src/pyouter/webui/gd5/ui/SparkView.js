import { Component } from '../engine/index.js';
import { cx, loadUi } from './util.js';

/** Spark 2.x peer: three >= 0.180 */
export const DEFAULT_SPARK_THREE_URL =
  'https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js';
export const DEFAULT_SPARK_THREE_ADDONS =
  'https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/';
export const DEFAULT_SPARK_URL =
  'https://sparkjs.dev/releases/spark/2.3.1/spark.module.js';
export const DEFAULT_SPLAT_URL =
  'https://sparkjs.dev/assets/splats/butterfly.spz';

/** @type {Promise<any>|null} */
let sparkPromise = null;
/** @type {Promise<any>|null} */
let sparkThreePromise = null;

/**
 * Inject importmap for `three` / `three/addons/` / `@sparkjsdev/spark`.
 * Prefer declaring the same map in HTML `<head>` before any module script.
 * @param {{ threeUrl?: string, threeAddons?: string, sparkUrl?: string }} [opts]
 */
export function ensureSparkImportMap(opts = {}) {
  if (typeof document === 'undefined') return false;
  if (document.querySelector('script[data-gd-spark-importmap]')) return true;

  const threeUrl = opts.threeUrl || DEFAULT_SPARK_THREE_URL;
  const addonsRaw = opts.threeAddons || DEFAULT_SPARK_THREE_ADDONS;
  const addons = addonsRaw.endsWith('/') ? addonsRaw : `${addonsRaw}/`;
  const sparkUrl = opts.sparkUrl || DEFAULT_SPARK_URL;

  const script = document.createElement('script');
  script.type = 'importmap';
  script.setAttribute('data-gd-spark-importmap', '1');
  script.textContent = JSON.stringify({
    imports: {
      three: threeUrl,
      'three/addons/': addons,
      '@sparkjsdev/spark': sparkUrl,
    },
  });

  const firstModule = document.querySelector('script[type="module"]');
  if (firstModule?.parentNode) firstModule.parentNode.insertBefore(script, firstModule);
  else (document.head || document.documentElement).appendChild(script);
  return true;
}

/**
 * Load three.js for Spark (0.180+), via importmap or injected namespace.
 * @param {string|object} [spec]
 */
export function loadSparkThree(spec = DEFAULT_SPARK_THREE_URL) {
  if (spec && typeof spec === 'object' && (spec.WebGLRenderer || spec.Scene)) {
    return Promise.resolve(spec);
  }
  if (!sparkThreePromise) {
    ensureSparkImportMap({
      threeUrl: typeof spec === 'string' && spec ? spec : DEFAULT_SPARK_THREE_URL,
    });
    sparkThreePromise = import(/* @vite-ignore */ 'three').then((mod) => mod.default || mod);
  }
  return sparkThreePromise;
}

/**
 * Load @sparkjsdev/spark once (CDN ESM via importmap, or inject `{ SparkRenderer, SplatMesh }`).
 * @param {string|object} [spec]
 */
export function loadSpark(spec = DEFAULT_SPARK_URL) {
  if (
    spec &&
    typeof spec === 'object' &&
    (typeof spec.SparkRenderer === 'function' || typeof spec.SplatMesh === 'function')
  ) {
    return Promise.resolve(spec);
  }
  if (!sparkPromise) {
    const sparkUrl = typeof spec === 'string' && spec ? spec : DEFAULT_SPARK_URL;
    ensureSparkImportMap({ sparkUrl });
    sparkPromise = import(/* @vite-ignore */ '@sparkjsdev/spark').then((mod) => mod.default || mod);
  }
  return sparkPromise;
}

/**
 * Spark.js Gaussian Splatting host — same composition as TodoList / ThreeView.
 */
export class SparkViewView extends Component {
  /**
   * @param {object} [deps]
   * @param {string} [deps.url] splat URL (.spz / .ply / …); default butterfly demo asset
   * @param {boolean} [deps.autoSplat=true] create SplatMesh from `url` when true
   * @param {boolean} [deps.autoRotate=true]
   * @param {string|number} [deps.height]
   * @param {string|number} [deps.width]
   * @param {string} [deps.className]
   * @param {number} [deps.background] clear color hex
   * @param {string|object} [deps.three] three CDN URL or namespace
   * @param {string|object} [deps.spark] spark CDN URL or `{ SparkRenderer, SplatMesh }`
   * @param {object} [deps.sparkOptions] extra SparkRenderer options
   * @param {(ctx:object)=> (void|(()=>void)|Promise<void|(()=>void)>)} [deps.onReady]
   * @param {(ctx:object)=> (void|(()=>void)|Promise<void|(()=>void)>)} [deps.onInit] alias of onReady
   * @param {(dt:number, ctx:object)=>void} [deps.onFrame]
   */
  constructor(deps = {}) {
    super(deps);
    this.state.data.height = deps.height ?? 360;
    this.state.data.width = deps.width ?? '100%';
    this.state.data.className = deps.className || '';
    this.state.data.background = deps.background ?? 0x111111;
    this.state.data.url = deps.url ?? DEFAULT_SPLAT_URL;
    this.state.data.autoSplat = deps.autoSplat !== false;
    this.state.data.autoRotate = deps.autoRotate !== false;
    this._threeSpec = deps.three ?? DEFAULT_SPARK_THREE_URL;
    this._sparkSpec = deps.spark ?? DEFAULT_SPARK_URL;
    this._sparkOptions = deps.sparkOptions || {};
    const ready = deps.onReady || deps.onInit;
    this._onReady = typeof ready === 'function' ? ready.bind(this) : null;
    this._onFrame = typeof deps.onFrame === 'function' ? deps.onFrame.bind(this) : null;
    this._THREE = null;
    this._Spark = null;
    this._scene = null;
    this._camera = null;
    this._renderer = null;
    this._sparkRenderer = null;
    this._splat = null;
    this._ownedSplats = [];
    this._raf = 0;
    this._disposeUser = null;
    this._ro = null;
    this._started = false;
    this._initing = false;
  }

  async mount(host, params = {}) {
    await loadUi();
    return super.mount(host, params);
  }

  getContext() {
    return {
      THREE: this._THREE,
      Spark: this._Spark,
      scene: this._scene,
      camera: this._camera,
      renderer: this._renderer,
      spark: this._sparkRenderer,
      splat: this._splat,
      host: this.ids().gdSparkHost,
      component: this,
    };
  }

  getSpark() {
    return this._sparkRenderer;
  }

  getSplat() {
    return this._splat;
  }

  componentDidUnMount() {
    if (this._raf) cancelAnimationFrame(this._raf);
    this._raf = 0;
    this._ro?.disconnect?.();
    this._ro = null;
    try {
      this._disposeUser?.();
    } catch {
      /* ignore */
    }
    this._disposeUser = null;

    for (const mesh of this._ownedSplats) {
      try {
        this._scene?.remove?.(mesh);
        mesh.dispose?.();
      } catch {
        /* ignore */
      }
    }
    this._ownedSplats = [];
    this._splat = null;

    try {
      this._sparkRenderer?.dispose?.();
    } catch {
      /* ignore */
    }
    this._sparkRenderer = null;

    this._renderer?.dispose?.();
    this._renderer?.domElement?.remove?.();
    this._renderer = null;
    this._scene = null;
    this._camera = null;
    this._THREE = null;
    this._Spark = null;
    this._started = false;
  }

  _sizeHost() {
    const host = this.ids().gdSparkHost;
    if (!host) return { w: 1, h: 1 };
    const w = Math.max(1, host.clientWidth || host.offsetWidth || 1);
    const h = Math.max(1, host.clientHeight || host.offsetHeight || 1);
    return { w, h };
  }

  _syncSize() {
    const { w, h } = this._sizeHost();
    if (this._camera) {
      this._camera.aspect = w / h;
      this._camera.updateProjectionMatrix?.();
    }
    this._renderer?.setSize?.(w, h, false);
  }

  _loop = (t0) => {
    this._raf = requestAnimationFrame((t1) => {
      const dt = Math.min(0.05, (t1 - t0) / 1000);
      if (this.state.data.autoRotate && this._splat) {
        this._splat.rotation.y += dt * 0.45;
      }
      this._onFrame?.(dt, this.getContext());
      this._renderer?.render?.(this._scene, this._camera);
      this._loop(t1);
    });
  };

  async _ensureScene() {
    if (!this.ids().gdSparkHost || this._started || this._initing) return;
    this._initing = true;
    try {
      const [THREE, Spark] = await Promise.all([
        loadSparkThree(this._threeSpec),
        loadSpark(this._sparkSpec),
      ]);
      const host = this.ids().gdSparkHost;
      if (this._started || !host) return;

      this._THREE = THREE;
      this._Spark = Spark;
      const { w, h } = this._sizeHost();

      this._scene = new THREE.Scene();
      this._camera = new THREE.PerspectiveCamera(60, w / h, 0.01, 1000);
      this._camera.position.set(0, 0, 0.01);

      // antialias:false — required for Gaussian Splatting performance
      this._renderer = new THREE.WebGLRenderer({ antialias: false, alpha: true });
      this._renderer.setPixelRatio(Math.min(2, globalThis.devicePixelRatio || 1));
      this._renderer.setSize(w, h, false);
      this._renderer.setClearColor(this.state.data.background, 1);
      host.textContent = '';
      host.appendChild(this._renderer.domElement);

      const { SparkRenderer, SplatMesh } = Spark;
      if (typeof SparkRenderer !== 'function') {
        throw new Error('SparkView: SparkRenderer missing — need @sparkjsdev/spark 2.x');
      }

      this._sparkRenderer = new SparkRenderer({
        renderer: this._renderer,
        ...this._sparkOptions,
      });
      this._scene.add(this._sparkRenderer);

      if (this.state.data.autoSplat && this.state.data.url && typeof SplatMesh === 'function') {
        const splat = new SplatMesh({ url: this.state.data.url });
        // Match official hello-world orientation for many .spz assets
        splat.quaternion?.set?.(1, 0, 0, 0);
        splat.position?.set?.(0, 0, -3);
        this._scene.add(splat);
        this._ownedSplats.push(splat);
        this._splat = splat;
      }

      if (typeof ResizeObserver !== 'undefined') {
        this._ro = new ResizeObserver(() => this._syncSize());
        this._ro.observe(host);
      }

      const maybeDispose = await this._onReady?.(this.getContext());
      if (typeof maybeDispose === 'function') this._disposeUser = maybeDispose;

      this._started = true;
      this._loop(performance.now());
    } catch (err) {
      this._started = false;
      const host = this.ids().gdSparkHost;
      if (host && typeof host.replaceChildren === 'function') {
        const msg = document.createElement?.('div');
        if (msg) {
          msg.className = 'gd-spark__error';
          msg.textContent = `SparkView failed: ${err?.message || err}`;
          host.replaceChildren(msg);
        }
      }
      throw err;
    } finally {
      this._initing = false;
    }
  }

  render() {
    const { height, width, className } = this.state.data;
    const h = typeof height === 'number' ? `${height}px` : String(height);
    const w = typeof width === 'number' ? `${width}px` : String(width);

    this.ensureShell(
      (ids) => ids.gdSparkRoot,
      ({ div }) => {
        div(
          {
            id: 'gdSparkRoot',
            className: cx('gd-spark', className),
            style: { width: w, height: h },
          },
          div({
            id: 'gdSparkHost',
            className: 'gd-spark__host',
            style: { width: '100%', height: '100%', overflow: 'hidden' },
          })
        );
      }
    );

    if (this._mounted || this.host()) {
      void this._ensureScene();
    }
  }
}

/**
 * SparkView — Spark.js (3D Gaussian Splatting) host, nested like TodoList:
 *
 * ```js
 * div(
 *   { id: 'root' },
 *   SparkView({
 *     url: 'https://sparkjs.dev/assets/splats/butterfly.spz',
 *     onReady({ splat }) { splat.position.set(0, 0, -3); },
 *   })
 * )
 * ```
 *
 * Host page should include an importmap for `three` + `@sparkjsdev/spark` (see spark-demo.html).
 *
 * @param {object} [props]
 * @returns {SparkViewView}
 */
export function SparkView(props = {}) {
  return new SparkViewView(props);
}

/** Alias */
export const SplatView = SparkView;

export function createSparkView(options = {}, host) {
  const view = SparkView(options);
  const elHost =
    typeof host === 'string'
      ? typeof document !== 'undefined'
        ? document.getElementById(host)
        : null
      : host;
  if (elHost) void view.mount(elHost);
  return view;
}
