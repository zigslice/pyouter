import { cx, el, omit } from './util.js';

/**
 * ProgressBar — determinate or indeterminate.
 * @param {object} [props]
 * @param {number} [props.percent] 0–100; omit for indeterminate
 * @param {'sm'|'md'|'lg'} [props.size]
 * @param {boolean} [props.showInfo]
 */
export function ProgressBar(props = {}) {
  const { percent, size = 'md', showInfo = false, className } = props;
  const indeterminate = percent == null;
  const pct = Math.max(0, Math.min(100, Number(percent) || 0));
  return el(
    'div',
    {
      ...omit(props, ['percent', 'size', 'showInfo', 'className']),
      className: cx('gd-progress', `gd-progress--${size}`, className),
      role: 'progressbar',
      attrs: indeterminate
        ? { 'aria-valuemin': '0', 'aria-valuemax': '100' }
        : {
            'aria-valuenow': String(pct),
            'aria-valuemin': '0',
            'aria-valuemax': '100',
          },
    },
    el(
      'div',
      { className: 'gd-progress__track' },
      el('div', {
        className: cx('gd-progress__bar', indeterminate && 'gd-progress__bar--indeterminate'),
        style: indeterminate ? undefined : { width: `${pct}%` },
      })
    ),
    showInfo && !indeterminate
      ? el('span', { className: 'gd-progress__info', text: `${Math.round(pct)}%` })
      : null
  );
}

/**
 * ProgressRing — circular progress (SVG).
 * @param {object} [props]
 * @param {number} [props.percent]
 * @param {number} [props.size] px
 * @param {number} [props.strokeWidth]
 */
export function ProgressRing(props = {}) {
  const { percent = 0, size = 48, strokeWidth = 4, className } = props;
  const pct = Math.max(0, Math.min(100, Number(percent) || 0));
  const r = (size - strokeWidth) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (pct / 100) * c;

  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', `0 0 ${size} ${size}`);
  svg.setAttribute('width', String(size));
  svg.setAttribute('height', String(size));
  svg.setAttribute('class', 'gd-progress-ring__svg');

  const track = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  track.setAttribute('class', 'gd-progress-ring__track');
  track.setAttribute('cx', String(size / 2));
  track.setAttribute('cy', String(size / 2));
  track.setAttribute('r', String(r));
  track.setAttribute('fill', 'none');
  track.setAttribute('stroke-width', String(strokeWidth));

  const bar = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  bar.setAttribute('class', 'gd-progress-ring__bar');
  bar.setAttribute('cx', String(size / 2));
  bar.setAttribute('cy', String(size / 2));
  bar.setAttribute('r', String(r));
  bar.setAttribute('fill', 'none');
  bar.setAttribute('stroke-width', String(strokeWidth));
  bar.setAttribute('stroke-dasharray', String(c));
  bar.setAttribute('stroke-dashoffset', String(offset));
  bar.setAttribute('transform', `rotate(-90 ${size / 2} ${size / 2})`);

  svg.appendChild(track);
  svg.appendChild(bar);
  const svgEl = { e: svg, dom: () => svg };

  return el(
    'div',
    {
      ...omit(props, ['percent', 'size', 'strokeWidth', 'className']),
      className: cx('gd-progress-ring', className),
      role: 'progressbar',
      attrs: {
        'aria-valuenow': String(pct),
        'aria-valuemin': '0',
        'aria-valuemax': '100',
      },
      style: { width: `${size}px`, height: `${size}px` },
    },
    svgEl,
    el('span', { className: 'gd-progress-ring__label', text: `${Math.round(pct)}%` })
  );
}

/** Meter — capacity / level gauge. */
export function Meter(props = {}) {
  const { value = 0, min = 0, max = 100, low, high, optimum, className, label } = props;
  return el(
    'div',
    { className: cx('gd-meter', className) },
    label != null ? el('div', { className: 'gd-meter__label', text: label }) : null,
    el('meter', {
      ...omit(props, ['className', 'label']),
      className: 'gd-meter__control',
      value,
      min,
      max,
      ...(low != null ? { low } : {}),
      ...(high != null ? { high } : {}),
      ...(optimum != null ? { optimum } : {}),
    })
  );
}
