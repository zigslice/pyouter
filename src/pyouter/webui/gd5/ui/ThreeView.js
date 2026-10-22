import { Component } from '../engine/index.js';
import { cx, loadUi } from './util.js';

const DEFAULT_THREE_URL = 'https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js';

/** @type {Promise<any>|null} */
let threePromise = null;

/**
 * Load three.js once (CDN ESM or inject THREE namespace).
 * @param {string|object} [spec]
 */
export function loadThree(spec = DEFAULT_THREE_URL) {
  if (spec && typeof spec === 'object' && (spec.WebGLRenderer || spec.Scene)) {
    return Promise.resolve(spec);
  }
  if (!threePromise) {
    const url = typeof spec === 'string' && spec ? spec : DEFAULT_THREE_URL;
    threePromise = import(/* @vite-ignore */ url).then((mod) => mod.default || mod);
  }
  return threePromise;
}

/**
 * Three.js host Component — same composition as TodoList.
 */
export class ThreeViewView extends Component {
  /**
   * @param {object} [deps]
   * @param {string|number} [deps.height]
   * @param {string|number} [deps.width]
   * @param {string} [deps.className]
   * @param {string|object} [deps.three] CDN URL or THREE namespace
   * @param {number} [deps.background] clear color hex
   * @param {(ctx:{
   *   THREE:any, scene:any, camera:any, renderer:any, host:HTMLElement, component:ThreeViewView
   * })=> (void|(()=>void)|Promise<void|(()=>void)>)} [deps.onInit]
   * @param {(dt:number, ctx:object)=>void} [deps.onFrame]
   */
  constructor(deps = {}) {
    super(deps);
    this.state.data.height = deps.height ?? 320;
    this.state.data.width = deps.width ?? '100%';
    this.state.data.className = deps.className || '';
    this.state.data.background = deps.background ?? 0xf5f5f5;
    this._threeSpec = deps.three ?? DEFAULT_THREE_URL;
    this._onInit = typeof deps.onInit === 'function' ? deps.onInit.bind(this) : null;
    this._onFrame = typeof deps.onFrame === 'function' ? deps.onFrame.bind(this) : null;
    this._THREE = null;
    this._scene = null;
    this._camera = null;
    this._renderer = null;
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
      scene: this._scene,
      camera: this._camera,
      renderer: this._renderer,
      host: this.ids().gdThreeHost,
      component: this,
    };
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
    this._renderer?.dispose?.();
    this._renderer?.domElement?.remove?.();
    this._renderer = null;
    this._scene = null;
    this._camera = null;
    this._THREE = null;
    this._started = false;
  }

  _sizeHost() {
    const host = this.ids().gdThreeHost;
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
      this._onFrame?.(dt, this.getContext());
      this._renderer?.render?.(this._scene, this._camera);
      this._loop(t1);
    });
  };

  async _ensureScene() {
    if (!this.ids().gdThreeHost || this._started || this._initing) return;
    this._initing = true;
    try {
      const THREE = await loadThree(this._threeSpec);
      const host = this.ids().gdThreeHost;
      if (this._started || !host) return;
      this._THREE = THREE;
      const { w, h } = this._sizeHost();

      this._scene = new THREE.Scene();
      this._camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 1000);
      this._camera.position.set(0, 0.6, 2.4);

      this._renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      this._renderer.setPixelRatio(Math.min(2, globalThis.devicePixelRatio || 1));
      this._renderer.setSize(w, h, false);
      this._renderer.setClearColor(this.state.data.background, 1);
      host.textContent = '';
      host.appendChild(this._renderer.domElement);

      if (typeof ResizeObserver !== 'undefined') {
        this._ro = new ResizeObserver(() => this._syncSize());
        this._ro.observe(host);
      }

      const maybeDispose = await this._onInit?.(this.getContext());
      if (typeof maybeDispose === 'function') this._disposeUser = maybeDispose;

      // Default demo content if onInit did not add meshes
      if (!this._onInit && this._scene.children.length === 0) {
        const light = new THREE.DirectionalLight(0xffffff, 1.1);
        light.position.set(2, 3, 4);
        this._scene.add(light);
        this._scene.add(new THREE.AmbientLight(0xffffff, 0.45));
        const mesh = new THREE.Mesh(
          new THREE.BoxGeometry(0.8, 0.8, 0.8),
          new THREE.MeshStandardMaterial({ color: 0xe86a17, metalness: 0.2, roughness: 0.45 })
        );
        this._scene.add(mesh);
        this._onFrame = (dt) => {
          mesh.rotation.x += dt * 0.7;
          mesh.rotation.y += dt * 1.1;
        };
      }

      this._started = true;
      this._loop(performance.now());
    } catch (err) {
      this._started = false;
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
      (ids) => ids.gdThreeRoot,
      ({ div }) => {
        div(
          {
            id: 'gdThreeRoot',
            className: cx('gd-three', className),
            style: { width: w, height: h },
          },
          div({
            id: 'gdThreeHost',
            className: 'gd-three__host',
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
 * ThreeView — Three.js scene host, nested like TodoList:
 *
 * ```js
 * div(
 *   { id: 'root' },
 *   ThreeView({
 *     height: 360,
 *     onInit({ THREE, scene }) {
 *       scene.add(new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshNormalMaterial()));
 *     },
 *   })
 * )
 * ```
 *
 * @param {object} [props]
 * @returns {ThreeViewView}
 */
export function ThreeView(props = {}) {
  return new ThreeViewView(props);
}

/** Alias */
export const ThreeScene = ThreeView;

export function createThreeView(options = {}, host) {
  const view = ThreeView(options);
  const elHost =
    typeof host === 'string'
      ? typeof document !== 'undefined'
        ? document.getElementById(host)
        : null
      : host;
  if (elHost) void view.mount(elHost);
  return view;
}
