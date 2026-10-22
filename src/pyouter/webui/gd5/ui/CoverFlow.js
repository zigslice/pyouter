import { Component } from '../engine/index.js';
import { cx, el, loadUi } from './util.js';

/** Pixels of drag that map to one card before the curve. */
const COVERFLOW_PITCH = 86;

/**
 * Normalize items to a stable shape.
 * @param {Array<string|object>} items
 * @returns {Array<{key:string,title:string,subtitle?:string,image?:string,color?:string,content?:any,raw:any}>}
 */
export function normalizeCoverFlowItems(items = []) {
  return (items || []).map((item, i) => {
    if (item == null || typeof item === 'string' || typeof item === 'number') {
      const title = String(item ?? '');
      return { key: `item-${i}`, title, raw: item };
    }
    const key = String(item.key ?? item.id ?? `item-${i}`);
    return {
      key,
      title: String(item.title ?? item.label ?? item.name ?? key),
      subtitle: item.subtitle != null ? String(item.subtitle) : item.desc != null ? String(item.desc) : undefined,
      image: item.image || item.src || undefined,
      color: item.color || undefined,
      content: item.content,
      raw: item,
    };
  });
}

/**
 * Map a horizontal drag to card slots.
 * Short drags resist (sub-linear); long drags accelerate past one-card-per-pitch.
 * Positive dx (drag right) yields positive slots (toward previous cards).
 * @param {number} dx
 * @param {number} [pitch]
 */
export function coverFlowDragSlots(dx, pitch = COVERFLOW_PITCH) {
  if (!pitch) return 0;
  const t = dx / pitch;
  if (t === 0) return 0;
  const sign = Math.sign(t);
  return sign * Math.pow(Math.abs(t), 1.4);
}

/**
 * Card index after a drag is released.
 * Distance uses the non-linear slot curve. `velocity` (px/ms) then adds
 * extra slots — about one card at 1px/ms — so a flick travels further
 * without pushing a moderate drag through the curve a second time.
 * Dragging left (dx < 0) advances to the next card.
 * @param {{origin:number,dx:number,velocity?:number,pitch?:number,count:number,loop?:boolean}} opts
 */
export function coverFlowSettleIndex({ origin, dx, velocity = 0, pitch = COVERFLOW_PITCH, count, loop = true }) {
  if (!count) return 0;
  const speed = Math.max(-1.2, Math.min(1.2, velocity || 0));
  let slots = coverFlowDragSlots(dx, pitch) + speed * 0.85;
  if (count > 1) {
    const limit = count - 1;
    if (slots > limit) slots = limit;
    else if (slots < -limit) slots = -limit;
  }
  const raw = origin - slots;
  const rounded = Math.round(raw);
  if (loop) return wrapIndex(rounded, count);
  return clampIndex(rounded, count);
}

/**
 * Shortest signed distance from a fractional position to card `i`.
 * With `loop`, the seam stays continuous (the first card sits just past the last).
 * @param {number} i
 * @param {number} pos
 * @param {number} count
 * @param {boolean} loop
 */
export function coverFlowOffset(i, pos, count, loop) {
  let d = i - pos;
  if (!loop || count <= 1) return d;
  d -= count * Math.round(d / count);
  return d;
}

/**
 * CoverFlow — Apple Cover Flow / game character-select style carousel.
 * Center card faces forward; neighbors tilt & stack in perspective.
 * Drag and touch follow the pointer, then ease onto a card. A longer or
 * faster swipe crosses more than one card.
 *
 * Also known as: Cover Flow, coverflow carousel, 3D card carousel.
 *
 * @param {object} [deps]
 * @param {Array} [deps.items]
 * @param {number} [deps.index]
 * @param {number} [deps.defaultIndex]
 * @param {boolean} [deps.loop]
 * @param {number} [deps.sideCount] cards visible each side (default 2)
 * @param {number} [deps.height]
 * @param {(index:number,item:object)=>void} [deps.onChange]
 * @param {(index:number,item:object)=>void} [deps.onSelect]
 */
export class CoverFlow extends Component {
  constructor(deps = {}) {
    super(deps);
    const items = normalizeCoverFlowItems(deps.items);
    const initial =
      Number.isFinite(deps.index) ? deps.index : Number.isFinite(deps.defaultIndex) ? deps.defaultIndex : 0;
    this.state.data.items = items;
    this.state.data.index = clampIndex(initial, items.length);
    this.state.data.loop = deps.loop !== false;
    this.state.data.sideCount = Math.max(1, Math.min(4, deps.sideCount ?? 2));
    this.state.data.height = deps.height ?? 320;
    this._onChange = deps.onChange || null;
    this._onSelect = deps.onSelect || null;
    this._drag = null;
    /** @type {number|null} fractional position while dragging or gliding */
    this._pos = null;
    this._raf = 0;
    this._suppressClick = false;
  }

  async mount(host, params = {}) {
    await loadUi();
    return super.mount(host, params);
  }

  componentDidUnMount() {
    this._drag = null;
    this._stopMotion(false);
  }

  setItems(items) {
    this._drag = null;
    this._stopMotion(false);
    const next = normalizeCoverFlowItems(items);
    this.setData(
      {
        items: next,
        index: clampIndex(this.state.data.index, next.length),
      },
      { refresh: !!this._mounted }
    );
    return this;
  }

  getIndex() {
    return this.state.data.index;
  }

  getActiveItem() {
    const { items, index } = this.state.data;
    return items[index] || null;
  }

  setIndex(index, { emit = true } = {}) {
    this._drag = null;
    this._stopMotion(false);
    const { items, loop } = this.state.data;
    if (!items.length) return this;
    const next = loop ? wrapIndex(index, items.length) : clampIndex(index, items.length);
    if (next === this.state.data.index) {
      if (this._mounted) this._applyPose();
      return this;
    }
    this.setData({ index: next }, { refresh: !!this._mounted });
    if (emit) this._onChange?.(next, items[next]);
    return this;
  }

  next() {
    return this.setIndex(this.state.data.index + 1);
  }

  prev() {
    return this.setIndex(this.state.data.index - 1);
  }

  componentDidAttachEvents() {
    const stage = this.ids().gdCfStage;
    if (!stage) return;

    this.on(stage, 'pointerdown', (e) => {
      if (e.button != null && e.button !== 0) return;
      if (this._drag && e.pointerId != null && this._drag.pointerId !== e.pointerId) return;
      this._stopMotion(true);
      const now = e.timeStamp || nowMs();
      this._drag = {
        pointerId: e.pointerId,
        x0: e.clientX,
        x: e.clientX,
        t: now,
        vx: 0,
        moved: false,
        origin: this._pos == null ? this.state.data.index : this._pos,
      };
      try {
        stage.setPointerCapture?.(e.pointerId);
      } catch {
        /* synthetic or already-released pointers */
      }
    });

    this.on(
      stage,
      'pointermove',
      (e) => {
        const drag = this._drag;
        if (!drag || (e.pointerId != null && e.pointerId !== drag.pointerId)) return;
        const dx = e.clientX - drag.x0;
        const now = e.timeStamp || nowMs();
        const dt = now - drag.t;
        if (dt > 0 && dt < 120) {
          // Floor the sample window so a burst of events in one frame cannot
          // look like dozens of pixels per millisecond.
          const inst = (e.clientX - drag.x) / Math.max(dt, 16);
          const blended = drag.vx * 0.55 + inst * 0.45;
          drag.vx = Math.max(-1.2, Math.min(1.2, blended));
        } else if (dt >= 120) {
          drag.vx = 0;
        }
        drag.x = e.clientX;
        drag.t = now;
        if (Math.abs(dx) > 6) {
          drag.moved = true;
          e.preventDefault?.();
          this._follow(dx);
        }
      },
      { passive: false }
    );

    this.on(stage, 'pointerup', (e) => {
      const drag = this._drag;
      if (!drag || (e.pointerId != null && e.pointerId !== drag.pointerId)) return;
      const dx = e.clientX - drag.x0;
      const moved = drag.moved;
      let vx = drag.vx;
      const idle = (e.timeStamp || nowMs()) - drag.t;
      if (idle > 80) vx = 0;
      this._drag = null;
      try {
        stage.releasePointerCapture?.(e.pointerId);
      } catch {
        /* ignore */
      }
      if (!moved) return;
      this._armClickSuppress();
      this._release(drag.origin, dx, vx);
    });

    this.on(stage, 'pointercancel', (e) => this._abortDrag(e));
    this.on(stage, 'lostpointercapture', (e) => this._abortDrag(e));

    this.on(stage, 'keydown', (e) => {
      if (e.key === 'ArrowRight') {
        e.preventDefault();
        this.next();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        this.prev();
      } else if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const item = this.getActiveItem();
        if (item) this._onSelect?.(this.state.data.index, item);
      }
    });
  }

  _armClickSuppress() {
    this._suppressClick = true;
    setTimeout(() => {
      this._suppressClick = false;
    }, 0);
  }

  _abortDrag(e) {
    const drag = this._drag;
    if (!drag) return;
    if (e?.pointerId != null && e.pointerId !== drag.pointerId) return;
    const moved = drag.moved;
    const origin = drag.origin;
    this._drag = null;
    if (!moved) return;
    this._armClickSuppress();
    const from = this._pos == null ? origin : this._pos;
    this._glide(from, Math.round(origin));
  }

  _follow(dx) {
    const { items, loop } = this.state.data;
    const count = items.length;
    if (!count || !this._drag) return;
    this._pos = livePosition(this._drag.origin, dx, count, loop);
    this._setLive(true);
    this._applyPose();
  }

  _release(origin, dx, velocity) {
    const { items, loop } = this.state.data;
    const count = items.length;
    if (!count) return;
    const index = coverFlowSettleIndex({ origin, dx, velocity, count, loop });
    const from = this._pos == null ? origin : this._pos;
    let target = index;
    if (loop && count > 1) {
      let best = index;
      let bestDist = Infinity;
      for (const cand of [index - count, index, index + count]) {
        const dist = Math.abs(cand - from);
        if (dist < bestDist) {
          best = cand;
          bestDist = dist;
        }
      }
      target = best;
    }
    if (prefersReducedMotion() || typeof globalThis.requestAnimationFrame !== 'function') {
      this._finish(target);
      return;
    }
    this._glide(from, target);
  }

  _glide(from, to) {
    this._stopRaf();
    const delta = to - from;
    if (Math.abs(delta) < 0.0001 || prefersReducedMotion() || typeof globalThis.requestAnimationFrame !== 'function') {
      this._finish(to);
      return;
    }
    const duration = Math.min(680, 280 + Math.abs(delta) * 110);
    const t0 = nowMs();
    this._setLive(true);
    const step = (now) => {
      if (!this.isMounted()) return;
      const u = Math.min(1, (now - t0) / duration);
      const eased = 1 - (1 - u) ** 3;
      this._pos = from + delta * eased;
      this._applyPose();
      if (u < 1) this._raf = globalThis.requestAnimationFrame(step);
      else this._finish(to);
    };
    this._raf = globalThis.requestAnimationFrame(step);
  }

  _finish(unwrapped) {
    this._raf = 0;
    const { items, loop } = this.state.data;
    const count = items.length;
    const index = !count
      ? 0
      : loop
        ? wrapIndex(Math.round(unwrapped), count)
        : clampIndex(Math.round(unwrapped), count);
    this._pos = null;
    this._setLive(false);
    if (index !== this.state.data.index) this.setIndex(index);
    else if (this._mounted) this._applyPose();
  }

  _stopRaf() {
    if (this._raf) {
      globalThis.cancelAnimationFrame?.(this._raf);
      this._raf = 0;
    }
  }

  /**
   * @param {boolean} keepPos keep the fractional position (grab during a glide)
   */
  _stopMotion(keepPos) {
    this._stopRaf();
    if (!keepPos) {
      this._pos = null;
      this._setLive(false);
    }
  }

  _setLive(on) {
    this.ids().gdCfRoot?.classList?.toggle('gd-coverflow--live', on);
  }

  _cardStyle(offset, sideCount) {
    const abs = Math.abs(offset);
    const curve = abs === 0 ? 0 : Math.pow(abs, 0.82);
    const x = Math.sign(offset) * 78 * curve;
    const rot = -Math.sign(offset) * 42 * Math.min(curve, 1);
    const z = -curve * 70;
    let scale = abs === 0 ? 1 : Math.max(0.78, 1 - curve * 0.1);
    let opacity = abs === 0 ? 1 : Math.max(0.45, 1 - curve * 0.22);
    if (abs > sideCount) opacity *= Math.max(0, 1 - (abs - sideCount) / 0.45);
    const hidden = abs > sideCount + 0.45;
    if (hidden) opacity = 0;
    return {
      opacity: String(opacity),
      transform: `translate(-50%, -50%) translateX(${x}px) translateZ(${z}px) rotateY(${rot}deg) scale(${scale})`,
      zIndex: String(100 - Math.round(abs * 10)),
      pointerEvents: hidden ? 'none' : 'auto',
    };
  }

  _applyPose() {
    const stage = this.ids().gdCfStage;
    if (!stage?.querySelectorAll) return;
    const { items, sideCount, loop, index } = this.state.data;
    const count = items.length;
    const pos = this._pos == null ? index : this._pos;
    const cards = [...stage.querySelectorAll('.gd-coverflow__card')];
    let nearest = index;
    let nearestAbs = Infinity;
    const posed = cards.map((card) => {
      const i = Number(card.getAttribute('data-index'));
      const offset = coverFlowOffset(i, pos, count, loop);
      const abs = Math.abs(offset);
      if (abs < nearestAbs) {
        nearestAbs = abs;
        nearest = i;
      }
      return { card, i, offset };
    });
    for (const { card, i, offset } of posed) {
      const style = this._cardStyle(offset, sideCount);
      card.style.opacity = style.opacity;
      card.style.transform = style.transform;
      card.style.zIndex = style.zIndex;
      card.style.pointerEvents = style.pointerEvents;
      card.setAttribute('data-offset', String(offset));
      const active = i === nearest;
      card.classList.toggle('gd-coverflow__card--active', active);
      card.setAttribute('aria-current', active ? 'true' : 'false');
      if ('tabIndex' in card) card.tabIndex = active ? 0 : -1;
    }
    const dots = this.ids().gdCfDots;
    if (dots?.querySelectorAll && count) {
      const activeDot = loop ? wrapIndex(Math.round(pos), count) : clampIndex(Math.round(pos), count);
      [...dots.querySelectorAll('.gd-coverflow__dot')].forEach((dot, i) => {
        dot.classList.toggle('gd-coverflow__dot--active', i === activeDot);
        dot.setAttribute('aria-current', i === activeDot ? 'true' : 'false');
      });
    }
    this._syncCaption(nearest);
  }

  _syncCaption(nearest) {
    const caption = this.ids().gdCfCaption;
    if (!caption) return;
    const { items, loop } = this.state.data;
    const count = items.length;
    if (!count) return;
    const i = loop ? wrapIndex(nearest, count) : clampIndex(nearest, count);
    const item = items[i];
    if (!item) return;
    const titleEl = caption.querySelector?.('.gd-coverflow__caption-title');
    if (titleEl) titleEl.textContent = item.title;
    const subEl = caption.querySelector?.('.gd-coverflow__caption-sub');
    if (item.subtitle) {
      if (subEl) subEl.textContent = item.subtitle;
      else if (typeof document !== 'undefined') {
        const created = document.createElement('div');
        created.className = 'gd-coverflow__caption-sub';
        created.textContent = item.subtitle;
        caption.appendChild(created);
      }
    } else if (subEl?.remove) {
      subEl.remove();
    }
  }

  _renderCard(item, offset, index) {
    const { sideCount } = this.state.data;
    const style = this._cardStyle(offset, sideCount);
    const active = offset === 0;
    const kids = [];

    if (item.image) {
      kids.push(
        el('img', {
          className: 'gd-coverflow__img',
          attrs: { src: item.image, alt: item.title, draggable: 'false' },
        })
      );
    } else {
      kids.push(
        el('div', {
          className: 'gd-coverflow__art',
          style: item.color ? { background: item.color } : undefined,
          text: item.title.slice(0, 1).toUpperCase(),
        })
      );
    }

    kids.push(
      el(
        'div',
        { className: 'gd-coverflow__meta' },
        el('div', { className: 'gd-coverflow__title', text: item.title }),
        item.subtitle
          ? el('div', { className: 'gd-coverflow__subtitle', text: item.subtitle })
          : null
      )
    );

    if (item.content) kids.push(item.content);

    return el(
      'button',
      {
        type: 'button',
        className: cx('gd-coverflow__card', active && 'gd-coverflow__card--active'),
        style,
        attrs: {
          'data-offset': String(offset),
          'data-index': String(index),
          'aria-current': active ? 'true' : 'false',
          tabindex: active ? '0' : '-1',
        },
        onClick: (e) => {
          e.preventDefault();
          if (this._suppressClick || this._drag?.moved || this._raf) return;
          if (offset === 0) {
            this._onSelect?.(index, item);
            return;
          }
          this.setIndex(index);
        },
      },
      ...kids
    );
  }

  render() {
    const { items, index, height, loop } = this.state.data;
    const count = items.length;

    this.ensureShell(
      (ids) => ids.gdCfRoot,
      ({ div, button }) => {
        div(
          {
            id: 'gdCfRoot',
            className: 'gd-coverflow',
            attrs: { role: 'group', 'aria-roledescription': 'coverflow carousel' },
          },
          div({
            id: 'gdCfStage',
            className: 'gd-coverflow__stage',
            attrs: { tabindex: '0', 'aria-label': 'Cover Flow' },
          }),
          div(
            { id: 'gdCfControls', className: 'gd-coverflow__controls' },
            button({
              type: 'button',
              id: 'gdCfPrev',
              className: 'gd-btn gd-btn--default gd-btn--sm gd-coverflow__arrow',
              text: '‹',
              attrs: { 'aria-label': 'Previous' },
              onClick: () => this.prev(),
            }),
            div({ id: 'gdCfCaption', className: 'gd-coverflow__caption' }),
            button({
              type: 'button',
              id: 'gdCfNext',
              className: 'gd-btn gd-btn--default gd-btn--sm gd-coverflow__arrow',
              text: '›',
              attrs: { 'aria-label': 'Next' },
              onClick: () => this.next(),
            })
          ),
          div({ id: 'gdCfDots', className: 'gd-coverflow__dots' })
        );
        void button;
      }
    );

    const root = this.ids().gdCfRoot;
    const stage = this.ids().gdCfStage;
    const caption = this.ids().gdCfCaption;
    const dots = this.ids().gdCfDots;
    const prev = this.ids().gdCfPrev;
    const next = this.ids().gdCfNext;

    if (root) root.style.setProperty('--gd-coverflow-h', typeof height === 'number' ? `${height}px` : String(height));
    if (stage) {
      stage.style.height = typeof height === 'number' ? `${height}px` : String(height);
      stage.textContent = '';
      if (!count) {
        stage.appendChild(
          el('div', { className: 'gd-coverflow__empty', text: 'No cards' }).dom()
        );
      } else {
        for (let i = 0; i < count; i++) {
          const offset = coverFlowOffset(i, index, count, loop);
          stage.appendChild(this._renderCard(items[i], offset, i).dom());
        }
      }
    }

    const active = items[index];
    if (caption) {
      caption.textContent = '';
      if (active) {
        caption.appendChild(el('div', { className: 'gd-coverflow__caption-title', text: active.title }).dom());
        if (active.subtitle) {
          caption.appendChild(
            el('div', { className: 'gd-coverflow__caption-sub', text: active.subtitle }).dom()
          );
        }
      }
    }

    if (dots) {
      dots.textContent = '';
      for (let i = 0; i < count; i++) {
        dots.appendChild(
          el('button', {
            type: 'button',
            className: cx('gd-coverflow__dot', i === index && 'gd-coverflow__dot--active'),
            attrs: { 'aria-label': `Go to ${items[i].title}`, 'aria-current': i === index ? 'true' : 'false' },
            onClick: () => this.setIndex(i),
          }).dom()
        );
      }
    }

    if (prev) prev.disabled = !loop && index <= 0;
    if (next) next.disabled = !loop && index >= count - 1;
  }
}

function clampIndex(i, len) {
  if (!len) return 0;
  return Math.max(0, Math.min(len - 1, Number(i) || 0));
}

function wrapIndex(i, len) {
  if (!len) return 0;
  return ((Number(i) % len) + len) % len;
}

/**
 * Fractional position while the pointer is down.
 * Past either end (when not looping) the extra distance rubber-bands.
 */
function livePosition(origin, dx, count, loop) {
  const pos = origin - coverFlowDragSlots(dx);
  if (loop || count <= 1) return pos;
  if (pos < 0) return rubber(pos);
  if (pos > count - 1) return count - 1 + rubber(pos - (count - 1));
  return pos;
}

function rubber(over) {
  const sign = Math.sign(over);
  if (!sign) return 0;
  return sign * Math.pow(Math.abs(over), 0.65) * 0.45;
}

function prefersReducedMotion() {
  return globalThis.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches === true;
}

function nowMs() {
  return globalThis.performance?.now?.() ?? Date.now();
}

/**
 * @param {Array} items
 * @param {HTMLElement|string} host
 * @param {object} [options]
 */
export function createCoverFlow(items, host, options = {}) {
  const cf = new CoverFlow({ ...options, items });
  const elHost =
    typeof host === 'string'
      ? typeof document !== 'undefined'
        ? document.getElementById(host)
        : null
      : host;
  if (elHost) void cf.mount(elHost);
  return cf;
}

/** Alias names people search for */
export const Coverflow = CoverFlow;
export const CoverflowCarousel = CoverFlow;
