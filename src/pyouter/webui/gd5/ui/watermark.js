import { cx, el, omit } from './util.js';

/**
 * Watermark — tiled text overlay (antd Watermark, simplified).
 * @param {object} [props]
 * @param {string|string[]} [props.content]
 * @param {number} [props.gap] px between tiles
 * @param {number} [props.fontSize]
 * @param {string} [props.color]
 */
export function Watermark(props = {}, ...children) {
  const {
    content = 'gd5',
    gap = 120,
    fontSize = 14,
    color = 'rgba(0,0,0,0.08)',
    className,
    rotate = -22,
  } = props;

  const text = Array.isArray(content) ? content.join('  ') : String(content);
  const svg = encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${gap}" height="${gap}">` +
      `<text x="50%" y="50%" fill="${color}" font-size="${fontSize}" ` +
      `font-family="sans-serif" text-anchor="middle" dominant-baseline="middle" ` +
      `transform="rotate(${rotate} ${gap / 2} ${gap / 2})">${text}</text></svg>`
  );

  return el(
    'div',
    {
      ...omit(props, ['content', 'gap', 'fontSize', 'color', 'className', 'rotate']),
      className: cx('gd-watermark', className),
    },
    el('div', {
      className: 'gd-watermark__layer',
      style: {
        backgroundImage: `url("data:image/svg+xml,${svg}")`,
        backgroundSize: `${gap}px ${gap}px`,
      },
      attrs: { 'aria-hidden': 'true' },
    }),
    el('div', { className: 'gd-watermark__content' }, ...children)
  );
}
